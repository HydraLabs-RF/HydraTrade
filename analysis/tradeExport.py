"""Per-trade export for benchmark runs (trades.json for the Web UI)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from analysis.runManager import write_json
from analysis.simulationAnalyzer import TradeAnalysis
from analysis.strategyBenchmark import VariantResult


def _row(variant_id: str, a: TradeAnalysis, period: str | None = None) -> dict:
    t = a.trade
    row = {
        "variant_id": variant_id,
        "direction": a.direction,
        "open_time": t.open_time,
        "close_time": t.close_time,
        "entry": t.entry_price,
        "exit": a.exit_price,
        "stop_loss": t.stop_loss,
        "initial_stop_loss": t.initial_stop_loss,
        "take_profit": t.take_profit,
        "volume": t.volume,
        "pnl": a.pnl,
        "r": a.reward_r,
        "outcome": a.category.value,
        "session": a.session,
        "comment": t.comment or "",
    }
    if period:
        row["period"] = period
    return row


def trades_from_variant_result(result: VariantResult) -> List[dict]:
    closed = [a for a in result.report.trades if a.trade.close_time]
    closed.sort(key=lambda a: a.trade.close_time)
    return [_row(result.spec.variant_id, a) for a in closed]


def build_single_window_payload(results: List[VariantResult]) -> dict:
    return {
        r.spec.variant_id: trades_from_variant_result(r)
        for r in results
        if "error" not in r.summary
    }


def build_multi_period_payload(multi_results) -> dict:
    out: dict = {}
    for mp in multi_results:
        by_period: Dict[str, List[dict]] = {}
        for label, vr in mp.raw.items():
            if "error" in vr.summary:
                continue
            rows = trades_from_variant_result(vr)
            if rows:
                by_period[label] = rows
        if by_period:
            out[mp.spec.variant_id] = by_period
    return out


def write_trades_json(run_dir: Path, payload: dict) -> Path | None:
    if not payload:
        return None
    total = sum(
        len(v) if isinstance(v, list) else sum(len(p) for p in v.values())
        for v in payload.values()
    )
    if total == 0:
        return None
    return write_json(run_dir, "trades.json", payload)
