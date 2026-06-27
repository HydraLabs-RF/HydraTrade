from core.config import configConnection
from datetime import datetime, timedelta
from core.riskManagment import SymbolInfo
from data.trade import Trade, TradeStatus, TradeType, LONG_TYPES, SHORT_TYPES
from execution.simulation.simulationMemory import simMemory
from execution.live.mt5execution import MT5CExecution
from core.enums import TimeFrame

class simHandler:
    def __init__(self, memory: simMemory):
        # Accepts the instance passed through from SimulationExecution (reference)
        self.memory = memory
        # Incrementing ticket counter for unique assignment
        self._next_ticket = 1000000
        self.config = configConnection()
        self._swap_cache = None

    def check_and_update(self, current_candle, symbol: str) -> None:
        """Checks all active and pending orders against the current candle."""
        
        # --- TICKET VALIDATION ---
        # Ensure EVERY trade in memory has a valid ticket immediately
        self._ensure_tickets()

        # list() is important because the lists change during the loop due to activations/closures
        for order in list(self.memory.get_pending_orders()):
            self._check_pending_activation(order, current_candle)

        for trade in list(self.memory.get_active_trades()):
            self._check_active_limits(trade, current_candle, symbol)

    def _ensure_tickets(self) -> None:
        """
        Checks all orders in memory. When a trade arrives fresh from the strategy
        and the ticket is still 0 (or None), a real, incrementing simulation
        ticket is assigned here.
        """
        # Check pendings
        for order in self.memory.get_pending_orders():
            if order.ticket == 0 or order.ticket is None:
                order.ticket = self._next_ticket
                self._next_ticket += 1

        # Check active trades (if a strategy places market orders directly)
        for trade in self.memory.get_active_trades():
            if trade.ticket == 0 or trade.ticket is None:
                trade.ticket = self._next_ticket
                self._next_ticket += 1

    def _check_pending_activation(self, order: Trade, candle) -> None:
        """Checks pending orders for activation based on market mechanics."""
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
            # Realistic fill price for STOP orders: a stop NEVER fills at a price
            # better than the market. If entry is already beyond the bar open when
            # triggered (stop placed below/above market or gap through the stop),
            # it fills at OPEN, not at the favorable entry price. Prevents the
            # below-market stop artifact (example SuperTrend). Limits unchanged.
            if order.type == TradeType.BUY_STOP and candle.open > order.entry_price:
                order.entry_price = candle.open
            elif order.type == TradeType.SELL_STOP and candle.open < order.entry_price:
                order.entry_price = candle.open
            # Use the unique ticket here to activate the order
            self.memory.trigger_pending_to_active(order.ticket, candle.time)

    def _check_active_limits(self, trade: Trade, candle, symbol: str) -> None:
        """Checks SL/TP hits with cascade filter (M1 resolution) when both are hit within one candle."""
        if trade.stop_loss is None and trade.take_profit is None:
            return
            
        hit_sl = False
        hit_tp = False

        # 1. Coarse pre-check on the current base candle
        if trade.stop_loss is not None:
            if (trade.type in LONG_TYPES and candle.low <= trade.stop_loss) or \
               (trade.type in SHORT_TYPES and candle.high >= trade.stop_loss):
                hit_sl = True

        if trade.take_profit is not None:
            if (trade.type in LONG_TYPES and candle.high >= trade.take_profit) or \
               (trade.type in SHORT_TYPES and candle.low <= trade.take_profit):
                hit_tp = True

        # 2. Conflict resolution: what happens when BOTH were hit in this one candle?
        if hit_sl and hit_tp:
            candle_duration = getattr(candle, 'duration', timedelta(hours=1))

            # Broker M1 history only goes back ~2 months. If no M1 data is available,
            # assume SL pessimistically (no crash, fair worst case).
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

        # 3. Standard case: only one of the two was hit on the base timeframe
        elif hit_sl:
            self._execute_close(trade, trade.stop_loss, candle.time, TradeStatus.STOPPED_OUT)
        elif hit_tp:
            self._execute_close(trade, trade.take_profit, candle.time, TradeStatus.TAKE_PROFIT)

    def _swap_params(self) -> dict:
        """Swap conditions LIVE from MT5 (no per-broker file). Cached once."""
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
        """Realized swap (money in profit currency) for overnight-held rollover
        boundaries between open_time and close_time. POINTS mode (mode 1):
        money/night = swap_points * point * (tick_value/tick_size) * volume.
        3x on the rollover3days weekday (covers the weekend)."""
        if not self.config.getSwapEnabled():
            return 0.0  # can be disabled per run (UI toggle / webui_config.simSwapEnabled)
        p = self._swap_params()
        if not p or p.get("mode") != 1:
            return 0.0  # only POINTS mode modeled (broker here = mode 1)
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
        """Calculates PnL (incl. swap/rollover), updates balance and closes the trade."""
        mt5exe = MT5CExecution()
        symbol_info: SymbolInfo = mt5exe.get_symbol_info(self.config.getSymbol())
        pnl = self.calc_pnl(trade, price, symbol_info, self.config.getSimAccCurency(), mt5exe)
        pnl += self.swap_cost(trade, time)

        current_balance = self.memory.getBalance()
        self.memory.setBalance(current_balance + pnl)
        
        # Close the trade safely in memory via its ticket
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
        Calculates PnL exactly per broker specification, accounting for
        tick value, tick size and currency conversion.
        """
        # 1. Determine direction
        direction = 1 if trade.type in LONG_TYPES else -1
        
        # 2. Determine price difference in points / price change
        price_diff = exit_price - trade.entry_price
        
        # 3. Calculate PnL in the symbol's profit currency (currency_profit)
        # Formula: (amount in points) * (value per point at 1 lot) * lot size
        pnl_symbol_currency = (price_diff / symbol_info.tick_size) * symbol_info.tick_value * trade.volume * direction
        
        # 4. Currency conversion: when symbol profit currency != account currency
        if account_currency != symbol_info.currency_profit:
            if fx_rate_provider is not None:
                # Path A: account currency is base, symbol currency is quote (e.g. account: EUR, symbol profit: USD -> pair: EURUSD)
                pair_direct = f"{account_currency}{symbol_info.currency_profit}"
                # Path B: reversed (e.g. account: USD, symbol profit: EUR -> pair: USDEUR)
                pair_inverse = f"{symbol_info.currency_profit}{account_currency}"
                
                conversion_rate = None
                
                # Attempt 1: fetch direct pair
                try:
                    price = fx_rate_provider.getCurrentPriceSymbole(pair_direct)
                    if price and price > 0:
                        # If PnL is in USD and account is in EUR, we have the EURUSD rate (e.g. 1.08)
                        # EUR = USD / 1.08 -> so we must DIVIDE by the rate
                        conversion_rate = 1.0 / price
                except Exception:
                    pass
                    
                # Attempt 2: fetch inverse pair
                if conversion_rate is None:
                    try:
                        price = fx_rate_provider.getCurrentPriceSymbole(pair_inverse)
                        if price and price > 0:
                            # If PnL is in USD, account in EUR, pair is USDEUR.
                            # EUR = USD * USDEUR -> so multiply directly
                            conversion_rate = price
                    except Exception as e:
                        print(f"[simHandler] Currency conversion error: {e}")
                
                # Apply conversion
                if conversion_rate is not None:
                    return pnl_symbol_currency * conversion_rate
                else:
                    print(f"[simHandler] Warning: exchange rate not found, using 1.0")
            else:
                print("[simHandler] Warning: currency mismatch without fx_rate_provider!")

        return pnl_symbol_currency