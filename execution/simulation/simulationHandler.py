from core.config import configConnection
from datetime import datetime, timedelta
from core.riskManagment import SymbolInfo
from data.trade import Trade, TradeStatus, TradeType, LONG_TYPES, SHORT_TYPES
from execution.simulation.simulationMemory import simMemory
from execution.live.mt5execution import MT5CExecution
from core.enums import TimeFrame

class simHandler:
    def __init__(self, memory: simMemory):
        # Akzeptiert die von SimulationExecution durchgereichte Instanz (Referenz)
        self.memory = memory
        # Fortlaufender Ticket-Zähler für die eindeutige Zuordnung
        self._next_ticket = 1000000
        self.config = configConnection()

    def check_and_update(self, current_candle, symbol: str) -> None:
        """Prüft alle aktiven und ausstehenden Orders gegen die aktuelle Kerze."""
        
        # --- TICKET-VALIDIERUNG ---
        # Wir stellen sicher, dass JEDER Trade im Speicher sofort ein gültiges Ticket besitzt
        self._ensure_tickets()

        # list() ist wichtig, da sich die Listen durch Aktivierungen/Schließungen im Loop verändern
        for order in list(self.memory.get_pending_orders()):
            self._check_pending_activation(order, current_candle)

        for trade in list(self.memory.get_active_trades()):
            self._check_active_limits(trade, current_candle, symbol)

    def _ensure_tickets(self) -> None:
        """
        Überprüft alle Orders in der Memory. Wenn ein Trade frisch von der Strategie 
        kommt und das Ticket noch 0 (oder None) ist, wird hier ein echtes, 
        fortlaufendes Simulations-Ticket vergeben.
        """
        # Pendings prüfen
        for order in self.memory.get_pending_orders():
            if order.ticket == 0 or order.ticket is None:
                order.ticket = self._next_ticket
                self._next_ticket += 1

        # Aktive Trades prüfen (falls eine Strategie direkt Markt-Orders wirft)
        for trade in self.memory.get_active_trades():
            if trade.ticket == 0 or trade.ticket is None:
                trade.ticket = self._next_ticket
                self._next_ticket += 1

    def _check_pending_activation(self, order: Trade, candle) -> None:
        """Prüft Pendings auf Aktivierung basierend auf der Marktmechanik."""
        triggered = False
        
        # BUY / BUY_LIMIT: fill when price falls to entry
        if order.type in [TradeType.BUY, TradeType.BUY_LIMIT]:
            if candle.low <= order.entry_price:
                triggered = True
        elif order.type == TradeType.BUY_STOP:
            if candle.high >= order.entry_price:
                triggered = True
        elif order.type == TradeType.BUY_STOP_LIMIT:
            trigger = order.trigger_price if order.trigger_price is not None else order.entry_price
            if order.notes != "armed":
                if candle.high >= trigger:
                    order.notes = "armed"
            elif candle.low <= order.entry_price:
                triggered = True
        # SELL / SELL_LIMIT: fill when price rises to entry
        elif order.type in [TradeType.SELL, TradeType.SELL_LIMIT]:
            if candle.high >= order.entry_price:
                triggered = True
        elif order.type == TradeType.SELL_STOP:
            if candle.low <= order.entry_price:
                triggered = True
        elif order.type == TradeType.SELL_STOP_LIMIT:
            trigger = order.trigger_price if order.trigger_price is not None else order.entry_price
            if order.notes != "armed":
                if candle.low <= trigger:
                    order.notes = "armed"
            elif candle.high >= order.entry_price:
                triggered = True

        if triggered:
            # Hier wird das eindeutige Ticket verwendet, um die Order zu aktivieren
            self.memory.trigger_pending_to_active(order.ticket, candle.time)

    def _check_active_limits(self, trade: Trade, candle, symbol: str) -> None:
        """Prüft SL/TP-Treffer mit Kaskaden-Filter (M1-Auflösung) bei Konflikten innerhalb einer Kerze."""
        if trade.stop_loss is None and trade.take_profit is None:
            return
            
        hit_sl = False
        hit_tp = False

        # 1. Grobe Vorprüfung auf der aktuellen Base-Kerze
        if trade.stop_loss is not None:
            if (trade.type in LONG_TYPES and candle.low <= trade.stop_loss) or \
               (trade.type in SHORT_TYPES and candle.high >= trade.stop_loss):
                hit_sl = True

        if trade.take_profit is not None:
            if (trade.type in LONG_TYPES and candle.high >= trade.take_profit) or \
               (trade.type in SHORT_TYPES and candle.low <= trade.take_profit):
                hit_tp = True

        # 2. Konfliktlösung: Was passiert, wenn BEIDES in dieser einen Kerze getroffen wurde?
        if hit_sl and hit_tp:
            candle_duration = getattr(candle, 'duration', timedelta(hours=1))

            # M1-Historie reicht beim Broker nur ~2 Monate zurück. Wenn keine M1-Daten
            # verfügbar sind, pessimistisch SL annehmen (kein Crash, fairer Worst-Case).
            try:
                m1_candles = self.memory.get_candles_between(
                    symbol=symbol,
                    timeframe=TimeFrame.M1,
                    start=candle.time,
                    end=candle.time + candle_duration
                )
            except Exception:
                m1_candles = []

            if not m1_candles:
                self._execute_close(trade, trade.stop_loss, candle.time, TradeStatus.STOPPED_OUT)
                return

            for m1_candle in m1_candles:
                sl_hit = (
                    (trade.type in LONG_TYPES and m1_candle.low <= trade.stop_loss) or
                    (trade.type in SHORT_TYPES and m1_candle.high >= trade.stop_loss)
                )

                tp_hit = (
                    (trade.type in LONG_TYPES and m1_candle.high >= trade.take_profit) or
                    (trade.type in SHORT_TYPES and m1_candle.low <= trade.take_profit)
                )

                if sl_hit and not tp_hit:
                    self._execute_close(trade, trade.stop_loss, m1_candle.time, TradeStatus.STOPPED_OUT)
                    return
                if tp_hit and not sl_hit:
                    self._execute_close(trade, trade.take_profit, m1_candle.time, TradeStatus.TAKE_PROFIT)
                    return
                if sl_hit and tp_hit:
                    self._execute_close(trade, trade.stop_loss, m1_candle.time, TradeStatus.STOPPED_OUT)
                    return

        # 3. Standardfall: Nur eines von beiden wurde im Base-Timeframe getroffen
        elif hit_sl:
            self._execute_close(trade, trade.stop_loss, candle.time, TradeStatus.STOPPED_OUT)
        elif hit_tp:
            self._execute_close(trade, trade.take_profit, candle.time, TradeStatus.TAKE_PROFIT)

    def _execute_close(self, trade: Trade, price: float, time: datetime, status: TradeStatus):
        """Berechnet das PnL, aktualisiert die Balance in der simMemory und schließt den Trade."""
        mt5exe = MT5CExecution()
        symbol_info: SymbolInfo = mt5exe.get_symbol_info(self.config.getSymbol())
        pnl = self.calc_pnl(trade, price, symbol_info, self.config.getSimAccCurency(), mt5exe)
        
        current_balance = self.memory.getBalance()
        self.memory.setBalance(current_balance + pnl)
        
        # Nun den Trade über sein Ticket sicher im Speicher schließen
        self.memory.close_trade(trade.ticket, price, time, status, pnl)

    def calc_pnl(
        self, 
        trade: Trade, 
        exit_price: float, 
        symbol_info: SymbolInfo, 
        account_currency: str = "USD", 
        fx_rate_provider = None
    ) -> float:
        """
        Berechnet das PnL exakt nach Broker-Spezifikation unter Berücksichtigung 
        von Tick-Value, Tick-Size und Währungsumrechnung.
        """
        # 1. Richtung bestimmen
        direction = 1 if trade.type in LONG_TYPES else -1
        
        # 2. Preisdifferenz in Punkten / Preisänderung ermitteln
        price_diff = exit_price - trade.entry_price
        
        # 3. PnL in der Gewinnwährung des Symbols (currency_profit) berechnen
        # Formel: (Menge in Punkten) * (Wert pro Punkt bei 1 Lot) * Lotsize
        pnl_symbol_currency = (price_diff / symbol_info.tick_size) * symbol_info.tick_value * trade.volume * direction
        
        # 4. Währungsausgleich: Wenn Symbol-Gewinnwährung != Kontowährung
        if account_currency != symbol_info.currency_profit:
            if fx_rate_provider is not None:
                # Weg A: Kontowährung ist Basis, Symbolwährung ist Quote (z.B. Konto: EUR, Symbol-Profit: USD -> Paar: EURUSD)
                pair_direct = f"{account_currency}{symbol_info.currency_profit}"
                # Weg B: Umgekehrt (z.B. Konto: USD, Symbol-Profit: EUR -> Paar: USDEUR)
                pair_inverse = f"{symbol_info.currency_profit}{account_currency}"
                
                conversion_rate = None
                
                # Versuch 1: Direktes Paar holen
                try:
                    price = fx_rate_provider.getCurrentPriceSymbole(pair_direct)
                    if price and price > 0:
                        # Wenn das PnL in USD ist und das Konto in EUR, wir haben den Kurs für EURUSD (z.B. 1.08)
                        # EUR = USD / 1.08 -> Also müssen wir durch den Kurs TEILEN
                        conversion_rate = 1.0 / price
                except Exception:
                    pass
                    
                # Versuch 2: Inverses Paar holen
                if conversion_rate is None:
                    try:
                        price = fx_rate_provider.getCurrentPriceSymbole(pair_inverse)
                        if price and price > 0:
                            # Wenn PnL in USD, Konto in EUR, Paar ist USDEUR. 
                            # EUR = USD * USDEUR -> Also direkt multiplizieren
                            conversion_rate = price
                    except Exception as e:
                        print(f"[simHandler] Currency conversion error: {e}")
                
                # Konvertierung anwenden
                if conversion_rate is not None:
                    return pnl_symbol_currency * conversion_rate
                else:
                    print(f"[simHandler] Warning: exchange rate not found, using 1.0")
            else:
                print("[simHandler] Warning: currency mismatch without fx_rate_provider!")

        return pnl_symbol_currency