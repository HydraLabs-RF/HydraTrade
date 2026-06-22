from typing import List, Optional
from datetime import datetime, timezone

from data.trade import Trade, TradeStatus


class liveTradeMemory:
    """Persistenter Trade-Speicher für Live-Betrieb (analog zu simMemory, ohne Balance-Simulation)."""

    def __init__(self):
        self.pending_orders: List[Trade] = []
        self.active_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
        # order_ticket -> position_ticket nach Aktivierung
        self._order_to_position: dict[int, int] = {}

    # -------------------------------------------------------------------------
    # CREATE & ADD
    # -------------------------------------------------------------------------
    def add_pending_order(self, trade: Trade) -> None:
        trade.status = TradeStatus.OPEN
        self.pending_orders.append(trade)

    def add_active_trade(self, trade: Trade) -> None:
        trade.status = TradeStatus.RUNNING
        self.active_trades.append(trade)

    # -------------------------------------------------------------------------
    # READ
    # -------------------------------------------------------------------------
    def get_pending_orders(self) -> List[Trade]:
        return self.pending_orders

    def get_active_trades(self) -> List[Trade]:
        return self.active_trades

    def get_closed_trades(self) -> List[Trade]:
        return self.closed_trades

    def find_trade_by_ticket(self, ticket: int) -> Optional[Trade]:
        for t in self.pending_orders + self.active_trades + self.closed_trades:
            if t.ticket == ticket:
                return t
        return None

    def find_pending_by_order_ticket(self, order_ticket: int) -> Optional[Trade]:
        for order in self.pending_orders:
            if order.ticket == order_ticket:
                return order
        return None

    def get_position_ticket_for_order(self, order_ticket: int) -> Optional[int]:
        return self._order_to_position.get(order_ticket)

    def getOpenPendingCount(self) -> int:
        return len(self.pending_orders)

    def getActiveTradeCount(self) -> int:
        return len(self.active_trades)

    def _count_trades_by_comment(self, comment_string: str) -> int:
        search_str = comment_string.lower().strip()
        return len([
            t for t in self.active_trades
            if t.comment and search_str in t.comment.lower()
        ])

    def getActiveA_GradeCount(self) -> int:
        return self._count_trades_by_comment("A-Grade")

    def getActiveB_GradeCount(self) -> int:
        return self._count_trades_by_comment("B-Grade")

    def getActiveC_GradeCount(self) -> int:
        return self._count_trades_by_comment("C-Grade")

    def _count_pendings_by_comment(self, comment_string: str) -> int:
        search_str = comment_string.lower().strip()
        return len([
            o for o in self.pending_orders
            if o.comment and search_str in o.comment.lower()
        ])

    def getPendingA_GradeCount(self) -> int:
        return self._count_pendings_by_comment("A-Grade")

    def getPendingB_GradeCount(self) -> int:
        return self._count_pendings_by_comment("B-Grade")

    def getPendingC_GradeCount(self) -> int:
        return self._count_pendings_by_comment("C-Grade")

    def _get_trades_by_comment(self, comment_string: str) -> List[Trade]:
        search_str = comment_string.strip().lower()
        return [
            t for t in self.active_trades
            if t.comment and t.comment.strip().lower() == search_str
        ]

    def getActiveA_GradeTrades(self) -> List[Trade]:
        return self._get_trades_by_comment("A-Grade")

    def getActiveA_GradeTrendTrades(self) -> List[Trade]:
        return self._get_trades_by_comment("A-Grade Trend")

    def getActiveB_GradeTrades(self) -> List[Trade]:
        return self._get_trades_by_comment("B-Grade")

    def getActiveC_GradeTrades(self) -> List[Trade]:
        return self._get_trades_by_comment("C-Grade")

    def _get_pendings_by_comment(self, comment_string: str) -> List[Trade]:
        search_str = comment_string.strip().lower()
        return [
            o for o in self.pending_orders
            if o.comment and o.comment.strip().lower() == search_str
        ]

    def getPendingA_GradeOrders(self) -> List[Trade]:
        return self._get_pendings_by_comment("A-Grade")

    def getPendingA_GradeTrendOrders(self) -> List[Trade]:
        return self._get_pendings_by_comment("A-Grade Trend")

    def getPendingA_GradeRangeOrders(self) -> List[Trade]:
        return self._get_pendings_by_comment("A-Grade Range")

    def getPendingB_GradeOrders(self) -> List[Trade]:
        return self._get_pendings_by_comment("B-Grade")

    def getPendingB_GradeTrendOrders(self) -> List[Trade]:
        return self._get_pendings_by_comment("B-Grade Trend")

    def getPendingB_GradeRangeOrders(self) -> List[Trade]:
        return self._get_pendings_by_comment("B-Grade Range")

    def getPendingC_GradeOrders(self) -> List[Trade]:
        return self._get_pendings_by_comment("C-Grade")

    def getPendingC_GradeTrendOrders(self) -> List[Trade]:
        return self._get_pendings_by_comment("C-Grade Trend")

    def getPendingC_GradeRangeOrders(self) -> List[Trade]:
        return self._get_pendings_by_comment("C-Grade Range")

    def _get_closed_by_comment(self, comment_string: str) -> List[Trade]:
        search_str = comment_string.strip().lower()
        return [
            t for t in self.closed_trades
            if t.comment and t.comment.strip().lower() == search_str
        ]

    def getClosedA_GradeTrendOrders(self) -> List[Trade]:
        return self._get_closed_by_comment("A-Grade Trend")

    # -------------------------------------------------------------------------
    # UPDATE
    # -------------------------------------------------------------------------
    def modify_pending_entry(self, ticket: int, new_entry_price: float) -> bool:
        for order in self.pending_orders:
            if order.ticket == ticket:
                order.entry_price = new_entry_price
                return True
        return False

    def update_sl_tp(self, ticket: int, sl: Optional[float], tp: Optional[float]) -> bool:
        trade = self.find_trade_by_ticket(ticket)
        if trade and trade.status in [TradeStatus.OPEN, TradeStatus.RUNNING, TradeStatus.TRAILING]:
            trade.stop_loss = sl
            trade.take_profit = tp
            if trade.status == TradeStatus.RUNNING and sl is not None:
                trade.status = TradeStatus.TRAILING
            return True
        return False

    def update_from_mt5_position(self, ticket: int, sl: Optional[float], tp: Optional[float],
                                 current_price: Optional[float], pnl: Optional[float]) -> None:
        trade = self.find_trade_by_ticket(ticket)
        if not trade:
            return
        trade.stop_loss = sl
        trade.take_profit = tp
        if current_price is not None:
            trade.current_price = current_price
        if pnl is not None:
            trade.pnl = pnl

    def update_from_mt5_pending(self, ticket: int, entry_price: float,
                              sl: Optional[float], tp: Optional[float]) -> None:
        trade = self.find_trade_by_ticket(ticket)
        if not trade:
            return
        trade.entry_price = entry_price
        trade.stop_loss = sl
        trade.take_profit = tp

    # -------------------------------------------------------------------------
    # STATE TRANSITIONS
    # -------------------------------------------------------------------------
    def activate_pending(self, order_ticket: int, position_ticket: int,
                         activation_time: datetime, entry_price: float,
                         sl: Optional[float], tp: Optional[float]) -> bool:
        if activation_time.tzinfo is None:
            activation_time = activation_time.replace(tzinfo=timezone.utc)

        for i, order in enumerate(self.pending_orders):
            if order.ticket == order_ticket:
                activated = self.pending_orders.pop(i)
                activated.ticket = position_ticket
                activated.status = TradeStatus.RUNNING
                activated.open_time = activation_time
                activated.entry_price = entry_price
                activated.stop_loss = sl
                activated.take_profit = tp
                self.active_trades.append(activated)
                self._order_to_position[order_ticket] = position_ticket
                return True
        return False

    def close_trade(self, ticket: int, close_price: float, close_time: datetime,
                    final_status: TradeStatus, pnl: float) -> bool:
        for i, trade in enumerate(self.active_trades):
            if trade.ticket == ticket:
                closed_trade = self.active_trades.pop(i)
                closed_trade.status = final_status
                closed_trade.close_time = close_time
                closed_trade.pnl = pnl
                closed_trade.current_price = close_price
                self.closed_trades.append(closed_trade)
                return True
        return False

    def remove_pending_order(self, ticket: int) -> bool:
        for i, order in enumerate(self.pending_orders):
            if order.ticket == ticket:
                self.pending_orders.pop(i)
                return True
        return False

    def adopt_orphan_position(self, trade: Trade) -> None:
        """Übernimmt eine Position aus MT5, die nicht in der Memory lag (z.B. nach Neustart)."""
        if self.find_trade_by_ticket(trade.ticket):
            return
        trade.status = TradeStatus.RUNNING
        self.active_trades.append(trade)
