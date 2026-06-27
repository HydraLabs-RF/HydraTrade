from datetime import datetime
from typing import List, Optional
from core.enums import TimeFrame
from execution.simulation.simulationMemory import simMemory
from execution.simulation.simulationHandler import simHandler
from data.trade import Trade, TradeAction, TradeStatus, TradeType
from execution.live.mt5execution import MT5CExecution
from core.branding import log, print_banner
from strategie.Strategy import Strategy

class SimulationExecution:
    def __init__(self, symbol: str, start_date: datetime, end_date: datetime, timeframe: TimeFrame = TimeFrame.M5):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.timeframe = timeframe
        
        self.mt5 = MT5CExecution()
        self.memory = simMemory()
        self.handler = simHandler(self.memory)
        self.strategy = None
        self._next_ticket = 1000000

    def set_strategy(self, strategy: Strategy) -> None:
        self.strategy = strategy
        
        # Clean refactor: pass ONLY the memory, same as for the handler
        if hasattr(self.strategy, "setSimMemory"):
            self.strategy.setSimMemory(self.memory)

    def run_simulation(self) -> None:
        if not self.strategy:
            raise ValueError("Keine Strategie zugewiesen.")

        print_banner()
        log(f"Loading historical data for {self.symbol}...")
        
        # Fetch historical candles for the base timeframe
        candles_exec = self.mt5.getCandles(self.timeframe, self.symbol, self.start_date, self.end_date)
        
        log(f"Loaded {len(candles_exec)} candles.")
        
        # Loop runs candle-by-candle on the execution timeframe
        start_index = max(50, 1)
        for i in range(start_index, len(candles_exec)):
            current_candle = candles_exec[i]
            current_time = current_candle.time

            # 1. Handler checks open positions and pendings against the current candle
            self.handler.check_and_update(current_candle, self.symbol)

            # 2. Trailing + pending management
            # IMPORTANT: use list() because state can change during iteration
            self._manage_active_trades(current_time)
            self._manage_pending_trades(current_time)

            # 3. Strategy entry logic (strategy decides based on current candle time)
            new_trade_proposal = self.strategy.on_tick(current_time)

            if new_trade_proposal:
                for trade in new_trade_proposal:
                    self._process_new_strategy_signal(trade, current_time)

        log("Simulation complete.")
        self._print_results()

    # -------------------------------------------------------------------------
    # INTERNAL LOGIC HOOKS
    # -------------------------------------------------------------------------
    def _process_new_strategy_signal(self, trade: Trade, current_time: datetime) -> None:
        """Assigns a ticket and stores the new trade in memory."""
        trade.ticket = self._next_ticket
        self._next_ticket += 1
        trade.initial_time = current_time
        
        if trade.action == TradeAction.ACTION and trade.status == TradeStatus.RUNNING:
            trade.open_time = current_time
            self.memory.add_active_trade(trade)
        elif trade.status == TradeStatus.RUNNING:
            self.memory.add_active_trade(trade)
        else:
            self.memory.add_pending_order(trade)

    def _manage_pending_trades(self, current_time: datetime) -> None:
        """Lets the strategy review open limits/stops and applies modifications/deletions."""
        # Strategy returns a list of trade request objects (or None/empty list)
        pending_requests = self.strategy.adjust_pending(current_time)
        
        if not pending_requests:
            return

        for request in pending_requests:
            # Safety check: does the request object have a valid ticket?
            if isinstance(request, list):
                for inTrade in request:
                    if not inTrade or not inTrade.ticket:
                        continue
                    # Case A: modify pending order (new entry price, possibly new SL/TP)
                    if inTrade.action == TradeAction.PENDING_MODIFY:
                        self.memory.modify_pending_entry(inTrade.ticket, inTrade.entry_price)
                        # If the strategy also changed SL/TP on the pending, sync directly
                        self.memory.update_sl_tp(inTrade.ticket, inTrade.stop_loss, inTrade.take_profit)
                    
                    # Case B: delete pending order entirely
                    elif inTrade.action == TradeAction.PENDING_REMOVE:
                        # Because list() is used, deletion during the engine loop is safe.
                        # Call the corresponding delete method on simMemory here:
                        if hasattr(self.memory, "remove_pending_order"):
                            self.memory.remove_pending_order(inTrade.ticket)
                
                continue
            if not request or not request.ticket:
                continue

            # Case A: modify pending order (new entry price, possibly new SL/TP)
            if request.action == TradeAction.PENDING_MODIFY:
                self.memory.modify_pending_entry(request.ticket, request.entry_price)
                # If the strategy also changed SL/TP on the pending, sync directly
                self.memory.update_sl_tp(request.ticket, request.stop_loss, request.take_profit)
                
            # Case B: delete pending order entirely
            elif request.action == TradeAction.PENDING_REMOVE:
                # Because list() is used, deletion during the engine loop is safe.
                # Call the corresponding delete method on simMemory here:
                if hasattr(self.memory, "remove_pending_order"):
                    self.memory.remove_pending_order(request.ticket)

    def _manage_active_trades(self, current_time: datetime) -> None:
        """Lets the strategy run management for active trades (SL/TP adjustment or manual close)."""
        active_requests = self.strategy.manage_trailing(current_time)
        
        if not active_requests:
            return

        for request in active_requests:
            if not request.ticket:
                continue

            # Case A: adjust SL and TP on the running trade (trailing)
            if request.action == TradeAction.ACTION_MODIFY_SL_TP:
                self.memory.update_sl_tp(request.ticket, request.stop_loss, request.take_profit)
                
            # Case B: strategy wants to close the trade immediately/manually at market
            elif request.status == TradeStatus.CLOSED:
                exit_price = request.entry_price if request.entry_price else request.current_price
                original_trade = next(
                    (t for t in self.memory.get_active_trades() if t.ticket == request.ticket), None)
                if original_trade and exit_price:
                    self.handler._execute_close(
                        original_trade, exit_price, current_time, TradeStatus.CLOSED)

    def _print_results(self):
        closed = self.memory.get_closed_trades()
        total_pnl = sum(t.pnl for t in closed if t.pnl is not None)
        
        # Compute start balance (end balance minus total PnL) and fetch current end balance
        end_balance = self.memory.getBalance()
        currency = self.memory.getBalanceCurency()
        start_balance = end_balance - total_pnl
        
        print(f"--- HydraTrade Simulation Report ---")
        print(f"Starting balance:       {start_balance:.2f} {currency}")
        print(f"Closed trades:          {len(closed)}")
        print(f"Total P/L:              {total_pnl:.2f} {currency}")
        print(f"Ending balance:         {end_balance:.2f} {currency}")