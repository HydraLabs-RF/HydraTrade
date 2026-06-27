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
        self._swap_cache = None

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
            # Realistischer Fill-Preis fuer STOP-Orders: ein Stop fuellt NIE zu einem
            # Preis besser als der Markt. Liegt das Entry beim Ausloesen bereits
            # hinter dem Bar-Open (Stop unter/ueber Markt platziert oder Gap durch den
            # Stop), fuellt er am OPEN, nicht am guenstigen Entry-Preis. Verhindert
            # das below-market-Stop-Artefakt (example SuperTrend). Limits unberuehrt.
            if order.type == TradeType.BUY_STOP and candle.open > order.entry_price:
                order.entry_price = candle.open
            elif order.type == TradeType.SELL_STOP and candle.open < order.entry_price:
                order.entry_price = candle.open
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

            # MT5 copy_rates_range returns the boundary candle of the available
            # history (not an empty list) when the requested M1 range is too old to
            # exist -> its time/price lie MONTHS outside the window and would close
            # the trade at a completely wrong price/time. Filter strictly to window.
            window_end = candle.time + candle_duration
            m1_candles = [m for m in m1_candles if candle.time <= m.time < window_end]

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

    def _swap_params(self) -> dict:
        """Swap-Konditionen LIVE aus MT5 (kein Per-Broker-File). Einmal gecacht."""
        if self._swap_cache is None:
            import MetaTrader5 as mt5
            i = mt5.symbol_info(self.config.getSymbol())
            if i is None:
                self._swap_cache = {}
            else:
                self._swap_cache = {
                    "mode": i.swap_mode, "long": i.swap_long, "short": i.swap_short,
                    "roll3": i.swap_rollover3days, "point": i.point,
                    "tick_size": i.trade_tick_size, "tick_value": i.trade_tick_value,
                }
        return self._swap_cache

    def swap_cost(self, trade: Trade, close_time: datetime) -> float:
        """Realisierter Swap (Geld in Profit-Währung) für die über Nacht gehaltenen
        Rollover-Grenzen zwischen open_time und close_time. POINTS-Modus (mode 1):
        money/Nacht = swap_points * point * (tick_value/tick_size) * volume.
        3-fach am rollover3days-Wochentag (deckt das Wochenende ab)."""
        if not self.config.getSwapEnabled():
            return 0.0  # per Run abschaltbar (UI-Toggle / webui_config.simSwapEnabled)
        p = self._swap_params()
        if not p or p.get("mode") != 1:
            return 0.0  # nur POINTS-Modus modelliert (Broker hier = mode 1)
        open_time = trade.open_time or trade.initial_time
        if open_time is None or close_time is None:
            return 0.0
        pts = p["long"] if trade.type in LONG_TYPES else p["short"]
        if not pts or p["tick_size"] <= 0:
            return 0.0
        money_per_night = pts * p["point"] * (p["tick_value"] / p["tick_size"]) * trade.volume
        total = 0.0
        d = open_time.date()
        end = close_time.date()
        while d < end:
            d = d + timedelta(days=1)
            total += money_per_night * (3 if d.weekday() == p["roll3"] else 1)
        return total

    def _execute_close(self, trade: Trade, price: float, time: datetime, status: TradeStatus):
        """Berechnet das PnL (inkl. Swap/Rollover), aktualisiert die Balance und schließt den Trade."""
        mt5exe = MT5CExecution()
        symbol_info: SymbolInfo = mt5exe.get_symbol_info(self.config.getSymbol())
        pnl = self.calc_pnl(trade, price, symbol_info, self.config.getSimAccCurency(), mt5exe)
        pnl += self.swap_cost(trade, time)

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