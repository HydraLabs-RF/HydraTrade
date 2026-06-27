"""
Post-simulation trade analysis: outcome categories, bait fill rate, RR, profit factor,
trailing losses and counterfactuals (fixed initial SL vs. current trailing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import List, Optional

from core.enums import TimeFrame
from core.config import configConnection
from core.mt5connection import MT5Connector
from data.trade import Trade, TradeStatus, TradeType
from execution.simulation.simulationMemory import simMemory
from execution.simulation.simulationMain import SimulationExecution
from execution.live.mt5execution import MT5CExecution
from strategie.registry import get_variant


class OutcomeCategory(str, Enum):
    DIRECT_TP = "DIRECT_TP"
    TP_EXCEEDED = "TP_EXCEEDED"
    DIRECT_SL = "DIRECT_SL"
    TP_NEAR_MISS = "TP_NEAR_MISS"
    SL_DESPITE_TP_DURING = "SL_DESPITE_TP_DURING"
    SL_TP_REACHED_AFTER = "SL_TP_REACHED_AFTER"


@dataclass
class BaitEvent:
    event: str
    time: datetime
    ticket: int
    entry: float
    session: str | None = None
    comment: str | None = None


@dataclass
class TradeAnalysis:
    trade: Trade
    direction: str
    session: str
    category: OutcomeCategory
    pnl: float
    risk_money: float
    reward_r: float
    mfe_price: float
    mae_price: float
    mfe_r: float
    mae_r: float
    tp_reached_during: bool
    tp_reached_after: bool
    tp_overshoot_r: float
    exit_price: float
    initial_sl: float
    counterfactual_fixed_sl: str
    counterfactual_fixed_pnl: float
    trailing_cost_pnl: float
    left_on_table_pnl: float
    left_on_table_r: float
    notes: str = ""


@dataclass
class SimulationReport:
    start: datetime
    end: datetime
    bait_placed: int = 0
    bait_filled: int = 0
    bait_expired: int = 0
    bait_fill_rate: float = 0.0
    trades: List[TradeAnalysis] = field(default_factory=list)

    @property
    def closed_a_grade(self) -> List[TradeAnalysis]:
        """Legacy filter for A-Grade Trend strategies; falls back to all trades."""
        tagged = [t for t in self.trades if t.trade.comment and "A-Grade Trend" in t.trade.comment]
        return tagged if tagged else self.trades

    def summary(self) -> dict:
        closed = self.closed_a_grade
        if not closed:
            return {"error": "No closed trades"}

        wins = [t for t in closed if t.pnl > 0]
        losses = [t for t in closed if t.pnl <= 0]
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        total_pnl = sum(t.pnl for t in closed)

        categories: dict[str, int] = {}
        for t in closed:
            categories[t.category.value] = categories.get(t.category.value, 0) + 1

        avg_win_r = sum(t.reward_r for t in wins) / len(wins) if wins else 0.0
        avg_loss_r = sum(t.mae_r for t in losses) / len(losses) if losses else 0.0

        trailing_cost = sum(t.trailing_cost_pnl for t in closed if t.trailing_cost_pnl < 0)
        left_on_table = sum(t.left_on_table_pnl for t in closed if t.left_on_table_pnl > 0)
        left_on_table_r = sum(t.left_on_table_r for t in closed if t.left_on_table_r > 0)

        same_day = sum(
            1 for t in closed
            if t.trade.open_time and t.trade.close_time
            and t.trade.open_time.date() == t.trade.close_time.date()
        )

        return {
            "trades": len(closed),
            "win_rate": len(wins) / len(closed) * 100,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else float("inf"),
            "total_pnl": total_pnl,
            "avg_win_r": avg_win_r,
            "avg_loss_r": avg_loss_r,
            "bait_placed": self.bait_placed,
            "bait_filled": self.bait_filled,
            "bait_expired": self.bait_expired,
            "bait_fill_rate_pct": self.bait_fill_rate * 100,
            "categories": categories,
            "trailing_cost_pnl": trailing_cost,
            "left_on_table_pnl": left_on_table,
            "left_on_table_r": left_on_table_r,
            "same_day_close_pct": same_day / len(closed) * 100,
        }


class AuditedSimMemory(simMemory):
    """simMemory with event log for bait analysis."""

    def __init__(self):
        super().__init__()
        self.bait_events: List[BaitEvent] = []

    def add_pending_order(self, trade: Trade) -> None:
        super().add_pending_order(trade)
        self.bait_events.append(BaitEvent(
            event="bait_placed",
            time=trade.initial_time or datetime.now(timezone.utc),
            ticket=trade.ticket,
            entry=trade.entry_price,
            comment=trade.comment,
            session=_session_label(trade.initial_time),
        ))

    def remove_pending_order(self, ticket: int) -> bool:
        order = self.find_trade_by_ticket(ticket)
        ok = super().remove_pending_order(ticket)
        if ok and order:
            self.bait_events.append(BaitEvent(
                event="bait_expired",
                time=datetime.now(timezone.utc),
                ticket=ticket,
                entry=order.entry_price,
                comment=order.comment,
                session=_session_label(order.initial_time),
            ))
        return ok

    def trigger_pending_to_active(self, ticket: int, activation_time: datetime) -> bool:
        order = self.find_trade_by_ticket(ticket)
        ok = super().trigger_pending_to_active(ticket, activation_time)
        if ok and order:
            self.bait_events.append(BaitEvent(
                event="bait_filled",
                time=activation_time,
                ticket=ticket,
                entry=order.entry_price,
                comment=order.comment,
                session=_session_label(order.initial_time),
            ))
        return ok


class AnalyzedSimulation(SimulationExecution):
    def __init__(self, symbol: str, start_date: datetime, end_date: datetime,
                 timeframe=TimeFrame.M5):
        super().__init__(symbol, start_date, end_date, timeframe)
        self.memory = AuditedSimMemory()
        self.handler.memory = self.memory

    def run_quiet(self) -> SimulationReport:
        if not self.strategy:
            raise ValueError("Keine Strategie zugewiesen.")

        candles_exec = self.mt5.getCandles(self.timeframe, self.symbol, self.start_date, self.end_date)
        start_index = max(50, 1)
        for i in range(start_index, len(candles_exec)):
            current_candle = candles_exec[i]
            current_time = current_candle.time
            self.handler.check_and_update(current_candle, self.symbol)
            self._manage_active_trades(current_time)
            self._manage_pending_trades(current_time)
            new_trade_proposal = self.strategy.on_tick(current_time)
            if new_trade_proposal:
                for trade in new_trade_proposal:
                    self._process_new_strategy_signal(trade, current_time)

        return build_report(
            memory=self.memory,
            bait_events=self.memory.bait_events,
            start=self.start_date,
            end=self.end_date,
            symbol=self.symbol,
            mt5=self.mt5,
        )


def _session_label(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    t = dt.time()
    if t.hour < 4:
        return "Asia"
    if t.hour < 11:
        return "EU"
    if t.hour < 16:
        return "US"
    return "Off"


def _is_long(trade: Trade) -> bool:
    return trade.type in [TradeType.BUY, TradeType.BUY_LIMIT, TradeType.BUY_STOP_LIMIT]


def _candles_in_range(candles, start: datetime, end: datetime):
    for c in candles:
        ct = c.time
        if ct.tzinfo is None:
            ct = ct.replace(tzinfo=timezone.utc)
        if start <= ct <= end:
            yield c


def _simulate_fixed_sl_tp(trade: Trade, candles, initial_sl: float, tp: float) -> tuple[str, float | None]:
    is_long = _is_long(trade)
    entry = trade.entry_price
    for c in candles:
        if is_long:
            sl_hit = c.low <= initial_sl
            tp_hit = c.high >= tp
        else:
            sl_hit = c.high >= initial_sl
            tp_hit = c.low <= tp
        if sl_hit and tp_hit:
            return "sl", initial_sl
        if sl_hit:
            return "sl", initial_sl
        if tp_hit:
            return "tp", tp
    return "open", None


def _pnl_estimate(trade: Trade, exit_price: float) -> float:
    direction = 1 if _is_long(trade) else -1
    return (exit_price - trade.entry_price) * trade.volume * direction * 100


def analyze_trade(trade: Trade, candles_m5: list, post_hours: int = 48) -> TradeAnalysis:
    is_long = _is_long(trade)
    entry = trade.entry_price
    tp = trade.take_profit or entry
    initial_sl = trade.initial_stop_loss or trade.stop_loss or entry
    exit_price = trade.exit_price or trade.current_price or entry
    open_time = trade.open_time or trade.initial_time
    close_time = trade.close_time or open_time

    if open_time and open_time.tzinfo is None:
        open_time = open_time.replace(tzinfo=timezone.utc)
    if close_time and close_time.tzinfo is None:
        close_time = close_time.replace(tzinfo=timezone.utc)

    risk = abs(entry - initial_sl) or 0.01

    during = list(_candles_in_range(candles_m5, open_time, close_time))
    post_end = close_time + timedelta(hours=post_hours)
    after = list(_candles_in_range(candles_m5, close_time, post_end))
    all_after_open = list(_candles_in_range(candles_m5, open_time, post_end))

    if is_long:
        mfe_price = max((c.high for c in during), default=entry)
        mae_price = min((c.low for c in during), default=entry)
        mfe_r = (mfe_price - entry) / risk
        mae_r = (entry - mae_price) / risk
        tp_reached_during = mfe_price >= tp
        tp_reached_after = any(c.high >= tp for c in after) if not tp_reached_during else False
        tp_overshoot_r = max(0.0, (mfe_price - tp) / risk) if trade.status == TradeStatus.TAKE_PROFIT else 0.0
    else:
        mfe_price = min((c.low for c in during), default=entry)
        mae_price = max((c.high for c in during), default=entry)
        mfe_r = (entry - mfe_price) / risk
        mae_r = (mae_price - entry) / risk
        tp_reached_during = mfe_price <= tp
        tp_reached_after = any(c.low <= tp for c in after) if not tp_reached_during else False
        tp_overshoot_r = max(0.0, (tp - mfe_price) / risk) if trade.status == TradeStatus.TAKE_PROFIT else 0.0

    if is_long:
        actual_r = (exit_price - entry) / risk
    else:
        actual_r = (entry - exit_price) / risk
    reward_r = actual_r

    tp_r = abs(tp - entry) / risk

    cf_result, cf_price = _simulate_fixed_sl_tp(trade, all_after_open, initial_sl, tp)
    if cf_price and is_long:
        cf_r = (cf_price - entry) / risk
    elif cf_price:
        cf_r = (entry - cf_price) / risk
    else:
        cf_r = actual_r
    cf_pnl = (trade.pnl or 0) * (cf_r / actual_r) if actual_r != 0 else 0

    actual_pnl = trade.pnl or 0
    trailing_cost = 0.0
    if trade.status == TradeStatus.STOPPED_OUT and cf_result == "tp":
        trailing_cost = (cf_r - actual_r) * risk * trade.volume * 100

    left_on_table = 0.0
    left_on_table_r = 0.0
    if trade.status == TradeStatus.STOPPED_OUT and (tp_reached_during or tp_reached_after):
        left_on_table_r = max(0.0, tp_r - max(0.0, actual_r))
        left_on_table = left_on_table_r * risk * trade.volume * 100

    category = _classify(trade, tp_reached_during, tp_reached_after, tp_overshoot_r, mfe_r, risk)

    notes = []
    if category == OutcomeCategory.SL_DESPITE_TP_DURING:
        notes.append("TP während Trade erreichbar – Trailing/SL zu eng")
    if category == OutcomeCategory.SL_TP_REACHED_AFTER:
        notes.append("Nach Stop-Out TP erreicht – Entry war gut, Exit zu früh")
    if tp_overshoot_r > 1.0:
        notes.append(f"TP um {tp_overshoot_r:.1f}R überschritten")

    return TradeAnalysis(
        trade=trade,
        direction="LONG" if is_long else "SHORT",
        session=_session_label(trade.initial_time) or "?",
        category=category,
        pnl=actual_pnl,
        risk_money=risk,
        reward_r=reward_r,
        mfe_price=mfe_price,
        mae_price=mae_price,
        mfe_r=mfe_r,
        mae_r=mae_r,
        tp_reached_during=tp_reached_during,
        tp_reached_after=tp_reached_after,
        tp_overshoot_r=tp_overshoot_r,
        exit_price=exit_price,
        initial_sl=initial_sl,
        counterfactual_fixed_sl=cf_result,
        counterfactual_fixed_pnl=cf_pnl,
        trailing_cost_pnl=trailing_cost,
        left_on_table_pnl=left_on_table,
        left_on_table_r=left_on_table_r,
        notes="; ".join(notes),
    )


def _classify(trade, tp_during, tp_after, overshoot_r, mfe_r, risk) -> OutcomeCategory:
    if trade.status == TradeStatus.TAKE_PROFIT:
        if overshoot_r >= 0.5:
            return OutcomeCategory.TP_EXCEEDED
        return OutcomeCategory.DIRECT_TP

    if trade.status == TradeStatus.STOPPED_OUT:
        if tp_during:
            return OutcomeCategory.SL_DESPITE_TP_DURING
        if tp_after:
            return OutcomeCategory.SL_TP_REACHED_AFTER
        tp_dist_r = abs((trade.take_profit or trade.entry_price) - trade.entry_price) / (risk or 0.01)
        if mfe_r >= tp_dist_r * 0.85:
            return OutcomeCategory.TP_NEAR_MISS
        return OutcomeCategory.DIRECT_SL

    return OutcomeCategory.DIRECT_SL


def build_report(memory: AuditedSimMemory, bait_events: List[BaitEvent],
                 start: datetime, end: datetime, symbol: str,
                 mt5: MT5CExecution) -> SimulationReport:
    placed = sum(1 for e in bait_events if e.event == "bait_placed" and e.comment and "A-Grade Trend" in e.comment)
    filled = sum(1 for e in bait_events if e.event == "bait_filled")
    expired = sum(1 for e in bait_events if e.event == "bait_expired" and e.comment and "A-Grade Trend" in e.comment)

    candles_m5 = mt5.getCandles(TimeFrame.M5, symbol, start - timedelta(days=1), end + timedelta(days=1))

    closed_trades = memory.get_closed_trades()
    has_a_grade = any(t.comment and "A-Grade Trend" in t.comment for t in closed_trades)

    analyses = []
    for trade in closed_trades:
        if not trade.open_time:
            continue
        if has_a_grade and (not trade.comment or "A-Grade Trend" not in trade.comment):
            continue
        analyses.append(analyze_trade(trade, candles_m5))

    return SimulationReport(
        start=start,
        end=end,
        bait_placed=placed,
        bait_filled=filled,
        bait_expired=expired,
        bait_fill_rate=filled / placed if placed else 0.0,
        trades=analyses,
    )


def run_analysis(start: datetime, end: datetime, symbol: str | None = None) -> SimulationReport:
    config = configConnection()
    config.live = False
    symbol = symbol or config.getSymbol()

    connector = MT5Connector()
    connector.initialize()
    connector.set_testing_window(start, end)

    sim = AnalyzedSimulation(symbol, start, end)
    sim.set_strategy(get_variant("example_ema_cross").factory())
    report = sim.run_quiet()
    connector.shutdown()
    return report


def format_report(report: SimulationReport) -> str:
    s = report.summary()
    lines = [
        "=" * 60,
        f"SIMULATION ANALYSE  {report.start.date()} -> {report.end.date()}",
        "=" * 60,
        "",
        "--- KÖDER (A-Grade Trend) ---",
        f"  Platziert:     {s.get('bait_placed', 0)}",
        f"  Ausgelöst:     {s.get('bait_filled', 0)}",
        f"  Verfallen:     {s.get('bait_expired', 0)}",
        f"  Fill-Rate:     {s.get('bait_fill_rate_pct', 0):.1f}%",
        "",
        "--- PERFORMANCE (ausgeführte Trades) ---",
        f"  Trades:        {s.get('trades', 0)}",
        f"  Win-Rate:      {s.get('win_rate', 0):.1f}%",
        f"  Profit-Faktor: {s.get('profit_factor', 0):.2f}",
        f"  Gesamt-PnL:    {s.get('total_pnl', 0):,.2f}",
        f"  Ø Gewinn-R:    {s.get('avg_win_r', 0):.2f}",
        f"  Ø Verlust-R:   {s.get('avg_loss_r', 0):.2f}",
        "",
        "--- OUTCOME-KATEGORIEN ---",
    ]
    for cat, count in sorted(s.get("categories", {}).items()):
        lines.append(f"  {cat}: {count}")

    lines.extend([
        "",
        "--- TRAILING / VERPASSTES POTENZIAL ---",
        f"  Trailing-Kosten (geschätzt):     {s.get('trailing_cost_pnl', 0):,.2f}",
        f"  Liegen gelassen (nach SL dann TP): {s.get('left_on_table_pnl', 0):,.2f}  ({s.get('left_on_table_r', 0):.1f}R gesamt)",
        "",
        "--- TRADE-DETAILS ---",
    ])

    for i, t in enumerate(report.closed_a_grade, 1):
        lines.append(
            f"  #{i} {t.direction} {t.session} | {t.category.value} | "
            f"PnL {t.pnl:,.0f} | MFE {t.mfe_r:.1f}R MAE {t.mae_r:.1f}R | "
            f"{'TP während' if t.tp_reached_during else ''}"
            f"{'TP danach' if t.tp_reached_after else ''} | "
            f"CF(fixed SL): {t.counterfactual_fixed_sl} | {t.notes}"
        )

    critical = [t for t in report.closed_a_grade
                if t.category in (OutcomeCategory.SL_DESPITE_TP_DURING,
                                  OutcomeCategory.SL_TP_REACHED_AFTER,
                                  OutcomeCategory.TP_EXCEEDED)]
    if critical:
        lines.extend(["", "--- KRITISCHE FÄLLE (Management prüfen) ---"])
        for t in critical:
            ot = t.trade.open_time.strftime("%Y-%m-%d %H:%M") if t.trade.open_time else "?"
            lines.append(
                f"  {ot} {t.direction} entry={t.trade.entry_price} "
                f"exit={t.exit_price:.2f} TP={t.trade.take_profit} | {t.category.value} | "
                f"liegen gelassen ~{t.left_on_table_r:.1f}R | {t.notes}"
            )

    return "\n".join(lines)
