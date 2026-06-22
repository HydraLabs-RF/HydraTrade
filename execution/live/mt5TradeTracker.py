from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import MetaTrader5 as mt5

from data.trade import Trade, TradeType, TradeStatus, TradeAction
from execution.live.mt5execution import MT5CExecution
from execution.live.liveTradeMemory import liveTradeMemory


class mt5TradeTracker:

    def __init__(self):
        self.memory = liveTradeMemory()
        self.execution = MT5CExecution()
        self._magic = mt5TradeTracker._config_magic()

    @staticmethod
    def _config_magic() -> int:
        from core.config import configConnection
        return configConnection().getMagicNumber()

    # -----------------------------------------------------------------------
    # MAPPING (MT5 -> Trade)
    # -----------------------------------------------------------------------

    @staticmethod
    def _map_position_to_trade(pos) -> Trade:
        trade_type = TradeType.BUY if pos.type == mt5.POSITION_TYPE_BUY else TradeType.SELL
        return Trade(
            symbol=pos.symbol,
            type=trade_type,
            action=TradeAction.ACTION,
            ticket=int(pos.ticket),
            entry_price=float(pos.price_open),
            volume=float(pos.volume),
            volume_initial=float(pos.volume),
            comment=pos.comment,
            stop_loss=float(pos.sl) if pos.sl > 0 else None,
            take_profit=float(pos.tp) if pos.tp > 0 else None,
            open_time=datetime.fromtimestamp(pos.time, tz=timezone.utc),
            status=TradeStatus.RUNNING,
            current_price=float(pos.price_current),
            pnl=float(pos.profit),
        )

    @staticmethod
    def _map_order_to_trade(order) -> Trade:
        type_map = {
            mt5.ORDER_TYPE_BUY_LIMIT: TradeType.BUY_LIMIT,
            mt5.ORDER_TYPE_SELL_LIMIT: TradeType.SELL_LIMIT,
            mt5.ORDER_TYPE_BUY_STOP: TradeType.BUY_STOP,
            mt5.ORDER_TYPE_SELL_STOP: TradeType.SELL_STOP,
            mt5.ORDER_TYPE_BUY_STOP_LIMIT: TradeType.BUY_STOP_LIMIT,
            mt5.ORDER_TYPE_SELL_STOP_LIMIT: TradeType.SELL_STOP_LIMIT,
            mt5.ORDER_TYPE_BUY: TradeType.BUY,
            mt5.ORDER_TYPE_SELL: TradeType.SELL,
        }
        trade_type = type_map.get(order.type, TradeType.BUY_LIMIT)
        return Trade(
            symbol=order.symbol,
            type=trade_type,
            action=TradeAction.PENDING,
            ticket=int(order.ticket),
            entry_price=float(order.price_open),
            volume=float(order.volume_initial),
            volume_initial=float(order.volume_initial),
            comment=order.comment,
            stop_loss=float(order.sl) if getattr(order, "sl", 0) and order.sl > 0 else None,
            take_profit=float(order.tp) if getattr(order, "tp", 0) and order.tp > 0 else None,
            status=TradeStatus.OPEN,
        )

    # -----------------------------------------------------------------------
    # SYNC: Memory ist Source of Truth, MT5 zum Abgleich
    # -----------------------------------------------------------------------

    def sync(self, current_time: datetime | None = None) -> None:
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        elif current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        mt5_orders = MT5CExecution.getAllOpenPendingOrder() or []
        mt5_positions = MT5CExecution.getAllOpenActivOrder() or []

        our_orders = [o for o in mt5_orders if self._is_our_trade(o)]
        our_positions = [p for p in mt5_positions if self._is_our_trade(p)]

        order_tickets = {int(o.ticket) for o in our_orders}
        position_tickets = {int(p.ticket) for p in our_positions}

        self._sync_pending_orders(our_orders, order_tickets, our_positions, current_time)
        self._sync_active_trades(our_positions, position_tickets, current_time)
        self._adopt_orphan_positions(our_positions)

    def _is_our_trade(self, mt5_obj) -> bool:
        magic = getattr(mt5_obj, "magic", 0)
        if magic == self._magic:
            return True
        comment = getattr(mt5_obj, "comment", "") or ""
        return "Grade" in comment

    def _sync_pending_orders(self, our_orders, order_tickets, our_positions, current_time) -> None:
        orders_by_ticket = {int(o.ticket): o for o in our_orders}

        for pending in list(self.memory.get_pending_orders()):
            ticket = pending.ticket
            if ticket in order_tickets:
                mt5_order = orders_by_ticket[ticket]
                self.memory.update_from_mt5_pending(
                    ticket,
                    float(mt5_order.price_open),
                    float(mt5_order.sl) if getattr(mt5_order, "sl", 0) and mt5_order.sl > 0 else None,
                    float(mt5_order.tp) if getattr(mt5_order, "tp", 0) and mt5_order.tp > 0 else None,
                )
                continue

            matched_position = self._match_position_for_pending(pending, our_positions)
            if matched_position is not None:
                self.memory.activate_pending(
                    order_ticket=ticket,
                    position_ticket=int(matched_position.ticket),
                    activation_time=current_time,
                    entry_price=float(matched_position.price_open),
                    sl=float(matched_position.sl) if matched_position.sl > 0 else None,
                    tp=float(matched_position.tp) if matched_position.tp > 0 else None,
                )
            else:
                self.memory.remove_pending_order(ticket)

    def _match_position_for_pending(self, pending: Trade, our_positions) -> object | None:
        known_positions = {t.ticket for t in self.memory.get_active_trades()}
        for pos in our_positions:
            if int(pos.ticket) in known_positions:
                continue
            if pos.symbol != pending.symbol:
                continue
            if pending.comment and pos.comment and pending.comment.strip() == pos.comment.strip():
                return pos
        return None

    def _sync_active_trades(self, our_positions, position_tickets, current_time) -> None:
        positions_by_ticket = {int(p.ticket): p for p in our_positions}

        for active in list(self.memory.get_active_trades()):
            ticket = active.ticket
            if ticket in position_tickets:
                pos = positions_by_ticket[ticket]
                self.memory.update_from_mt5_position(
                    ticket,
                    float(pos.sl) if pos.sl > 0 else None,
                    float(pos.tp) if pos.tp > 0 else None,
                    float(pos.price_current),
                    float(pos.profit),
                )
                continue

            close_price, pnl, final_status = self._resolve_closed_trade(active, current_time)
            self.memory.close_trade(ticket, close_price, current_time, final_status, pnl)

    def _resolve_closed_trade(self, trade: Trade, current_time: datetime) -> Tuple[float, float, TradeStatus]:
        start = (trade.open_time or trade.initial_time or current_time - timedelta(days=1))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        deals = MT5CExecution.getAllClosedDeals(start, current_time) or []
        relevant = [
            d for d in deals
            if getattr(d, "position_id", None) == trade.ticket
            or getattr(d, "order", None) == trade.ticket
        ]
        if not relevant and trade.comment:
            relevant = [
                d for d in deals
                if getattr(d, "comment", "") and trade.comment in d.comment
            ]

        if relevant:
            last_deal = relevant[-1]
            pnl = sum(float(d.profit) for d in relevant)
            price = float(last_deal.price)
            reason = getattr(last_deal, "reason", None)
            if reason == mt5.DEAL_REASON_SL:
                status = TradeStatus.STOPPED_OUT
            elif reason == mt5.DEAL_REASON_TP:
                status = TradeStatus.TAKE_PROFIT
            else:
                status = TradeStatus.CLOSED
            return price, pnl, status

        exit_price = trade.current_price or trade.entry_price
        return exit_price, trade.pnl or 0.0, TradeStatus.CLOSED

    def _adopt_orphan_positions(self, our_positions) -> None:
        known = {t.ticket for t in self.memory.get_active_trades()}
        known |= {t.ticket for t in self.memory.get_pending_orders()}
        for pos in our_positions:
            ticket = int(pos.ticket)
            if ticket not in known:
                self.memory.adopt_orphan_position(self._map_position_to_trade(pos))

    # -----------------------------------------------------------------------
    # REGISTRATION (nach erfolgreicher Ausführung)
    # -----------------------------------------------------------------------

    def register_pending(self, trade: Trade) -> None:
        self.memory.add_pending_order(trade)

    def register_active(self, trade: Trade) -> None:
        self.memory.add_active_trade(trade)

    def unregister_pending(self, ticket: int) -> None:
        self.memory.remove_pending_order(ticket)

    # -----------------------------------------------------------------------
    # COUNTER
    # -----------------------------------------------------------------------

    def getOpenPendingCount(self) -> int:
        return self.memory.getOpenPendingCount()

    def getActiveTradeCount(self) -> int:
        return self.memory.getActiveTradeCount()

    def getActiveA_GradeCount(self) -> int:
        return self.memory.getActiveA_GradeCount()

    def getActiveB_GradeCount(self) -> int:
        return self.memory.getActiveB_GradeCount()

    def getActiveC_GradeCount(self) -> int:
        return self.memory.getActiveC_GradeCount()

    def getPendingA_GradeCount(self) -> int:
        return self.memory.getPendingA_GradeCount()

    def getPendingB_GradeCount(self) -> int:
        return self.memory.getPendingB_GradeCount()

    def getPendingC_GradeCount(self) -> int:
        return self.memory.getPendingC_GradeCount()

    # -----------------------------------------------------------------------
    # RETRIEVE (aus Memory, nach sync())
    # -----------------------------------------------------------------------

    def getActiveA_GradeTrades(self) -> list[Trade]:
        return self.memory.getActiveA_GradeTrades()

    def getActiveA_GradeTrendTrades(self) -> list[Trade]:
        return self.memory.getActiveA_GradeTrendTrades()

    def getActiveB_GradeTrades(self) -> list[Trade]:
        return self.memory.getActiveB_GradeTrades()

    def getActiveC_GradeTrades(self) -> list[Trade]:
        return self.memory.getActiveC_GradeTrades()

    def getPendingA_GradeOrders(self) -> list[Trade]:
        return self.memory.getPendingA_GradeOrders()

    def getPendingA_GradeTrendOrders(self) -> list[Trade]:
        return self.memory.getPendingA_GradeTrendOrders()

    def getPendingA_GradeRangeOrders(self) -> list[Trade]:
        return self.memory.getPendingA_GradeRangeOrders()

    def getPendingB_GradeOrders(self) -> list[Trade]:
        return self.memory.getPendingB_GradeOrders()

    def getPendingB_GradeTrendOrders(self) -> list[Trade]:
        return self.memory.getPendingB_GradeTrendOrders()

    def getPendingB_GradeRangeOrders(self) -> list[Trade]:
        return self.memory.getPendingB_GradeRangeOrders()

    def getPendingC_GradeOrders(self) -> list[Trade]:
        return self.memory.getPendingC_GradeOrders()

    def getPendingC_GradeTrendOrders(self) -> list[Trade]:
        return self.memory.getPendingC_GradeTrendOrders()

    def getPendingC_GradeRangeOrders(self) -> list[Trade]:
        return self.memory.getPendingC_GradeRangeOrders()

    def getClosedA_GradeTrendOrders(self) -> list[Trade]:
        return self.memory.getClosedA_GradeTrendOrders()

    # -----------------------------------------------------------------------
    # CLOSED (Session-Queries über Memory + optional MT5-Historie)
    # -----------------------------------------------------------------------

    def _get_closed_deals_by_comment(self, comment_string: str,
                                     start: datetime, end: datetime) -> list[Trade]:
        deals = MT5CExecution.getAllClosedDeals(start, end)
        if not deals:
            return []
        search_str = comment_string.lower().strip()
        result = []
        for deal in deals:
            if getattr(deal, "comment", None) and search_str in deal.comment.lower():
                trade_type = TradeType.BUY if deal.type == mt5.DEAL_TYPE_BUY else TradeType.SELL
                result.append(Trade(
                    symbol=deal.symbol,
                    type=trade_type,
                    action=TradeAction.ACTION,
                    ticket=int(deal.ticket),
                    entry_price=float(deal.price),
                    volume=float(deal.volume),
                    comment=deal.comment,
                    open_time=datetime.fromtimestamp(deal.time, tz=timezone.utc),
                    close_time=datetime.fromtimestamp(deal.time, tz=timezone.utc),
                    status=TradeStatus.CLOSED,
                    pnl=float(deal.profit),
                ))
        return result

    def getClosedA_GradeCount(self, start: datetime, end: datetime) -> int:
        return len(self._get_closed_deals_by_comment("A-Grade", start, end))

    def getClosedA_GradeTrendCount(self, start: datetime, end: datetime) -> int:
        return len(self._get_closed_deals_by_comment("A-Grade Trend", start, end))

    def getClosedA_GradeRangeCount(self, start: datetime, end: datetime) -> int:
        return len(self._get_closed_deals_by_comment("A-Grade Range", start, end))

    def getClosedB_GradeCount(self, start: datetime, end: datetime) -> int:
        return len(self._get_closed_deals_by_comment("B-Grade", start, end))

    def getClosedB_GradeTrendCount(self, start: datetime, end: datetime) -> int:
        return len(self._get_closed_deals_by_comment("B-Grade Trend", start, end))

    def getClosedB_GradeRangeCount(self, start: datetime, end: datetime) -> int:
        return len(self._get_closed_deals_by_comment("B-Grade Range", start, end))

    def getClosedC_GradeCount(self, start: datetime, end: datetime) -> int:
        return len(self._get_closed_deals_by_comment("C-Grade", start, end))

    def getClosedC_GradeTrendCount(self, start: datetime, end: datetime) -> int:
        return len(self._get_closed_deals_by_comment("C-Grade Trend", start, end))

    def getClosedC_GradeRangeCount(self, start: datetime, end: datetime) -> int:
        return len(self._get_closed_deals_by_comment("C-Grade Range", start, end))

    def getClosedA_GradeDeals(self, start: datetime, end: datetime) -> list[Trade]:
        return self._get_closed_deals_by_comment("A-Grade", start, end)

    def getClosedA_GradeTrendDeals(self, start: datetime, end: datetime) -> list[Trade]:
        return self._get_closed_deals_by_comment("A-Grade Trend", start, end)

    def getClosedA_GradeRangeDeals(self, start: datetime, end: datetime) -> list[Trade]:
        return self._get_closed_deals_by_comment("A-Grade Range", start, end)

    def getClosedB_GradeDeals(self, start: datetime, end: datetime) -> list[Trade]:
        return self._get_closed_deals_by_comment("B-Grade", start, end)

    def getClosedB_GradeTrendDeals(self, start: datetime, end: datetime) -> list[Trade]:
        return self._get_closed_deals_by_comment("B-Grade Trend", start, end)

    def getClosedB_GradeRangeDeals(self, start: datetime, end: datetime) -> list[Trade]:
        return self._get_closed_deals_by_comment("B-Grade Range", start, end)

    def getClosedC_GradeDeals(self, start: datetime, end: datetime) -> list[Trade]:
        return self._get_closed_deals_by_comment("C-Grade", start, end)

    def getClosedC_GradeTrendDeals(self, start: datetime, end: datetime) -> list[Trade]:
        return self._get_closed_deals_by_comment("C-Grade Trend", start, end)

    def getClosedC_GradeRangeDeals(self, start: datetime, end: datetime) -> list[Trade]:
        return self._get_closed_deals_by_comment("C-Grade Range", start, end)
