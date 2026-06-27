from typing import List, Optional
from datetime import datetime, timezone
from core.config import configConnection
from data.trade import Trade, TradeStatus, TradeAction, TradeType
from execution.live.mt5execution import MT5CExecution

class simMemory:
    def __init__(self):
        # The three central storage areas (simulation state)
        self.pending_orders: List[Trade] = []
        self.active_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []

        self.execution = MT5CExecution()
        
        self.balance = configConnection().getSimEQ()
        self.balanceCurency = configConnection().getSimAccCurency()

    # -------------------------------------------------------------------------
    # CREATE & ADD (add new orders / trades)
    # -------------------------------------------------------------------------
    def add_pending_order(self, trade: Trade) -> None:
        """Adds a new pending order (limit/stop) to memory."""
        trade.status = TradeStatus.OPEN
        if trade.initial_stop_loss is None and trade.stop_loss is not None:
            trade.initial_stop_loss = trade.stop_loss
        self.pending_orders.append(trade)

    def add_active_trade(self, trade: Trade) -> None:
        """Adds a directly market-executed trade."""
        trade.status = TradeStatus.RUNNING
        if trade.initial_stop_loss is None and trade.stop_loss is not None:
            trade.initial_stop_loss = trade.stop_loss
        self.active_trades.append(trade)

    # -------------------------------------------------------------------------
    # READ & GETTER (query state)
    # -------------------------------------------------------------------------
    def get_pending_orders(self) -> List[Trade]:
        return self.pending_orders

    def get_active_trades(self) -> List[Trade]:
        return self.active_trades

    def get_closed_trades(self) -> List[Trade]:
        return self.closed_trades

    def find_trade_by_ticket(self, ticket: int) -> Optional[Trade]:
        """Finds an order or trade by ticket (searches everywhere)."""
        for t in self.pending_orders + self.active_trades + self.closed_trades:
            if t.ticket == ticket:
                return t
        return None

    # -------------------------------------------------------------------------
    # SIMULATED TRACKER INTERFACE (counterpart to mt5TradeTracker)
    # -------------------------------------------------------------------------
    def getOpenPendingCount(self) -> int:
        """Returns the number of currently waiting pending orders."""
        return len(self.pending_orders)
    
    def getActiveTradeCount(self) -> int:
        """Returns the number of all currently running (active) trades."""
        return len(self.active_trades)
    
    def _count_trades_by_comment(self, comment_string: str) -> int:
        """Internal helper to filter open positions by comment."""
        search_str = comment_string.lower().strip()
        return len([
            t for t in self.active_trades 
            if t.comment and search_str in t.comment.lower()
        ])

    def getActiveA_GradeCount(self) -> int: return self._count_trades_by_comment("A-Grade")
    def getActiveB_GradeCount(self) -> int: return self._count_trades_by_comment("B-Grade")
    def getActiveC_GradeCount(self) -> int: return self._count_trades_by_comment("C-Grade")
    
    def _count_pendings_by_comment(self, comment_string: str) -> int:
        """Internal helper to filter pending orders by comment."""
        search_str = comment_string.lower().strip()
        return len([
            o for o in self.pending_orders 
            if o.comment and search_str in o.comment.lower()
        ])

    def getPendingA_GradeCount(self) -> int: return self._count_pendings_by_comment("A-Grade")
    def getPendingB_GradeCount(self) -> int: return self._count_pendings_by_comment("B-Grade")
    def getPendingC_GradeCount(self) -> int: return self._count_pendings_by_comment("C-Grade")

    # -----------------------------------------------------------------------
    # RETRIEVE ACTIVE TRADES (fetch objects instead of counting only)
    # -----------------------------------------------------------------------
    def _get_trades_by_comment(self, comment_string: str) -> List[Trade]:
        search_str = comment_string.strip().lower()
        return [t for t in self.active_trades if t.comment and t.comment.strip().lower() == search_str]

    def getActiveA_GradeTrades(self) -> List[Trade]: return self._get_trades_by_comment("A-Grade")
    def getActiveA_GradeTrendTrades(self) -> List[Trade]: return self._get_trades_by_comment("A-Grade Trend")
    def getActiveB_GradeTrades(self) -> List[Trade]: return self._get_trades_by_comment("B-Grade")
    def getActiveC_GradeTrades(self) -> List[Trade]: return self._get_trades_by_comment("C-Grade")

    # -----------------------------------------------------------------------
    # RETRIEVE PENDING ORDERS (fetch objects instead of counting only)
    # -----------------------------------------------------------------------
    def _get_pendings_by_comment(self, comment_string: str) -> List[Trade]:
        search_str = comment_string.strip().lower()
        return [o for o in self.pending_orders if o.comment and o.comment.strip().lower() == search_str]

    def getPendingA_GradeOrders(self) -> List[Trade]: return self._get_pendings_by_comment("A-Grade")
    def getPendingA_GradeTrendOrders(self) -> List[Trade]: return self._get_pendings_by_comment("A-Grade Trend")
    def getPendingA_GradeRangeOrders(self) -> List[Trade]: return self._get_pendings_by_comment("A-Grade Range")
    def getPendingB_GradeOrders(self) -> List[Trade]: return self._get_pendings_by_comment("B-Grade")
    def getPendingB_GradeTrendOrders(self) -> List[Trade]: return self._get_pendings_by_comment("B-Grade Trend")
    def getPendingB_GradeRangeOrders(self) -> List[Trade]: return self._get_pendings_by_comment("B-Grade Range")
    def getPendingC_GradeOrders(self) -> List[Trade]: return self._get_pendings_by_comment("C-Grade")
    def getPendingC_GradeTrendOrders(self) -> List[Trade]: return self._get_pendings_by_comment("C-Grade Trend")
    def getPendingC_GradeRangeOrders(self) -> List[Trade]: return self._get_pendings_by_comment("C-Grade Range")

    def _get_closed_by_comment(self, comment_string: str) -> List[Trade]:
        search_str = comment_string.strip().lower()
        return [t for t in self.closed_trades if t.comment and t.comment.strip().lower() == search_str]
    
    def getClosedA_GradeTrendOrders(self) -> List[Trade]: return self._get_closed_by_comment("A-Grade Trend")

    # -------------------------------------------------------------------------
    # UPDATE & EDIT (change properties)
    # -------------------------------------------------------------------------
    def modify_pending_entry(self, ticket: int, new_entry_price: float) -> bool:
        """Adjusts the entry price of a pending order."""
        for order in self.pending_orders:
            if order.ticket == ticket:
                order.entry_price = new_entry_price
                return True
        return False

    def update_sl_tp(self, ticket: int, sl: Optional[float], tp: Optional[float]) -> bool:
        """Changes SL and TP of an active trade or order (important for trailing)."""
        trade = self.find_trade_by_ticket(ticket)
        if trade and trade.status in [TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.TRAILING]:
            trade.stop_loss = sl
            trade.take_profit = tp
            if trade.status == TradeStatus.RUNNING and sl is not None:
                trade.status = TradeStatus.TRAILING
            return True
        return False

    # -------------------------------------------------------------------------
    # STATE TRANSITIONS (status changes & moves)
    # -------------------------------------------------------------------------
    def trigger_pending_to_active(self, ticket: int, activation_time: datetime) -> bool:
        """Moves an order from 'pending' to 'active' when the market triggers."""
        if activation_time.tzinfo is None:
            activation_time = activation_time.replace(tzinfo=timezone.utc)
        for i, order in enumerate(self.pending_orders):
            if order.ticket == ticket:
                activated_trade = self.pending_orders.pop(i)
                activated_trade.status = TradeStatus.RUNNING
                activated_trade.open_time = activation_time
                if activated_trade.initial_stop_loss is None and activated_trade.stop_loss is not None:
                    activated_trade.initial_stop_loss = activated_trade.stop_loss
                self.active_trades.append(activated_trade)
                return True
        return False

    def close_trade(self, ticket: int, close_price: float, close_time: datetime, final_status: TradeStatus, pnl: float) -> bool:
        """Closes a trade and moves it to history."""
        for i, trade in enumerate(self.active_trades):
            if trade.ticket == ticket:
                closed_trade = self.active_trades.pop(i)
                closed_trade.status = final_status
                closed_trade.close_time = close_time
                closed_trade.pnl = pnl
                closed_trade.current_price = close_price
                closed_trade.exit_price = close_price
                self.closed_trades.append(closed_trade)
                return True
        return False

    def remove_pending_order(self, ticket: int) -> bool:
        """Removes a pending order (e.g. when the signal becomes invalid)."""
        for i, order in enumerate(self.pending_orders):
            if order.ticket == ticket:
                self.pending_orders.pop(i)
                pass  # quiet in benchmark
                return True
        return False
    
    # -------------------------------------------------------------------------
    # DATA RETRIEVAL (data interfaces)
    # -------------------------------------------------------------------------
    def get_historical_candles(self, symbol: str, timeframe, reference_time: datetime, candle_count: int):
        return self.execution.getHistoricalCandles(
            timeframe=timeframe,
            Symbol=symbol,
            reference_time=reference_time,
            candle_count=candle_count
        )
    
    def get_candles_between(self, symbol: str, timeframe, start: datetime, end: datetime) -> list:
        return self.execution.getCandlesBetween(
            timeframe=timeframe,
            Symbol=symbol,
            start=start,
            end=end
        )
    
    def get_candle_at(self, symbol: str, timeframe, reference_time: datetime):
        return self.execution.getCandleAt(
            timeframe=timeframe,
            Symbol=symbol,
            reference_time=reference_time
        )
    
    def getBalance(self):
        return self.balance
    
    def setBalance(self, newBalacne: float):
        self.balance = newBalacne

    def getBalanceCurency(self):
        return self.balanceCurency