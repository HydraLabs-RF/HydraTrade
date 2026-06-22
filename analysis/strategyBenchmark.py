"""
Benchmark runner: simulate strategies over a date range and evaluate results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from core.config import configConnection
from core.enums import TimeFrame
from core.mt5connection import MT5Connector
from analysis.simulationAnalyzer import AnalyzedSimulation, SimulationReport, build_report
from strategie.registry import ALL_VARIANTS, VariantSpec


# ~3 Monate – genug Daten, kein Chart-Overfitting auf Einzeltage
BENCHMARK_START = datetime(2026, 3, 1, tzinfo=timezone.utc)
BENCHMARK_END = datetime(2026, 6, 8, tzinfo=timezone.utc)


@dataclass
class VariantResult:
    spec: VariantSpec
    report: SimulationReport
    summary: dict
    equity_curve: List[tuple[datetime, float]] = field(default_factory=list)
    end_balance: float = 0.0


def _equity_curve_from_memory(memory, start_balance: float) -> List[tuple[datetime, float]]:
    closed = sorted(
        [t for t in memory.get_closed_trades() if t.close_time and t.pnl is not None],
        key=lambda t: t.close_time,
    )
    curve = []
    balance = start_balance
    if closed:
        curve.append((closed[0].open_time or closed[0].close_time, start_balance))
    for t in closed:
        balance += t.pnl
        curve.append((t.close_time, balance))
    return curve


def _drawdown_stats(memory, start_balance: float) -> dict:
    """
    Drawdown- und Prop-Kennzahlen aus den geschlossenen Trades (realisiert).
    - max_dd_pct: groesster Peak-to-Trough Ruecksetzer der Equity-Kurve (% vom Peak)
    - worst_below_start_pct: tiefster Stand unter Startkapital (FTMO-Floor-Logik)
    - max_daily_loss_pct: schlimmster realisierter Tagesverlust (% vom Tagesstart)
    - return_pct: Gesamtrendite
    - prop_ftmo_ok: <5% Tagesverlust UND nie unter 90% Startkapital
    - prop_bonus_ok: <2% Tagesverlust UND <10% max DD (strenger Bonus-Massstab)
    Hinweis: realisiert (ohne intraday floating) -> reale Prop-DD kann leicht hoeher sein.
    """
    closed = sorted(
        [t for t in memory.get_closed_trades() if t.close_time and t.pnl is not None],
        key=lambda t: t.close_time,
    )
    if not closed:
        return {}

    balance = start_balance
    peak = start_balance
    max_dd_pct = 0.0
    worst_below_start_pct = 0.0

    # pro Kalendertag: Tagesstart-Balance und Tagestief
    daily_start: dict = {}
    daily_min: dict = {}
    running = start_balance
    for t in closed:
        day = t.close_time.date()
        if day not in daily_start:
            daily_start[day] = running
            daily_min[day] = running
        running += t.pnl
        if running < daily_min[day]:
            daily_min[day] = running

    for t in closed:
        balance += t.pnl
        if balance > peak:
            peak = balance
        dd = (peak - balance) / peak * 100 if peak > 0 else 0.0
        if dd > max_dd_pct:
            max_dd_pct = dd
        below = (start_balance - balance) / start_balance * 100
        if below > worst_below_start_pct:
            worst_below_start_pct = below

    max_daily_loss_pct = 0.0
    for day, s in daily_start.items():
        loss = (s - daily_min[day]) / s * 100 if s > 0 else 0.0
        if loss > max_daily_loss_pct:
            max_daily_loss_pct = loss

    return_pct = (balance - start_balance) / start_balance * 100

    prop_ftmo_ok = max_daily_loss_pct < 5.0 and worst_below_start_pct < 10.0
    prop_bonus_ok = max_daily_loss_pct < 2.0 and max_dd_pct < 10.0

    return {
        "max_dd_pct": max_dd_pct,
        "worst_below_start_pct": worst_below_start_pct,
        "max_daily_loss_pct": max_daily_loss_pct,
        "return_pct": return_pct,
        "prop_ftmo_ok": prop_ftmo_ok,
        "prop_bonus_ok": prop_bonus_ok,
    }


def run_variant(
    spec: VariantSpec,
    start: datetime,
    end: datetime,
    symbol: str,
    start_balance: float,
) -> VariantResult:
    sim = AnalyzedSimulation(symbol, start, end, TimeFrame.M5)
    strategy = spec.factory()
    sim.set_strategy(strategy)
    sim.run_quiet()

    report = build_report(
        memory=sim.memory,
        bait_events=sim.memory.bait_events,
        start=start,
        end=end,
        symbol=symbol,
        mt5=sim.mt5,
    )
    summary = report.summary()
    if "error" not in summary:
        summary.update(_drawdown_stats(sim.memory, start_balance))
    equity = _equity_curve_from_memory(sim.memory, start_balance)
    end_balance = sim.memory.getBalance()

    return VariantResult(
        spec=spec,
        report=report,
        summary=summary,
        equity_curve=equity,
        end_balance=end_balance,
    )


def run_full_benchmark(
    start: datetime = BENCHMARK_START,
    end: datetime = BENCHMARK_END,
    symbol: Optional[str] = None,
    variants: Optional[List[VariantSpec]] = None,
) -> List[VariantResult]:
    config = configConnection()
    config.live = False
    symbol = symbol or config.getSymbol()
    start_balance = config.getSimEQ()

    variants = variants if variants is not None else ALL_VARIANTS

    connector = MT5Connector()
    connector.initialize()
    connector.set_testing_window(start, end)

    results: List[VariantResult] = []
    total = len(variants)
    for i, spec in enumerate(variants, 1):
        print(f"[{i}/{total}] {spec.name} ...")
        try:
            result = run_variant(spec, start, end, symbol, start_balance)
            results.append(result)
            s = result.summary
            if "error" not in s:
                print(
                    f"    -> PnL {s.get('total_pnl', 0):,.0f} | WR {s.get('win_rate', 0):.1f}% | "
                    f"PF {s.get('profit_factor', 0):.2f} | maxDD {s.get('max_dd_pct', 0):.1f}% | "
                    f"TagDD {s.get('max_daily_loss_pct', 0):.1f}%"
                )
            else:
                print(f"    -> {s['error']}")
        except Exception as e:
            print(f"    -> ERROR: {e}")

    connector.shutdown()
    return results
