#!/usr/bin/env python3
"""
HydraTrade agent plugin CLI — thin wrappers around framework entry points.

Usage:
    python agent/plugin/hydra.py bt --variants example_ema_cross --multi-period
    python agent/plugin/hydra.py validate --variants example_ema_cross
    python agent/plugin/hydra.py ftmo --run reports/runs/<timestamp>_name
    python agent/plugin/hydra.py phasemap --start 2026-01-01 --end 2026-06-01
    python agent/plugin/hydra.py sanity --variant example_ema_cross --start 2026-03-01 --end 2026-06-01
    python agent/plugin/hydra.py newstrategy my_edge
    python agent/plugin/hydra.py newindicator my_tool
    python agent/plugin/hydra.py catalog
    python agent/plugin/hydra.py live status
    python agent/plugin/hydra.py live start --variant example_ema_cross --yes
    python agent/plugin/hydra.py order buy --volume 0.10 --sl 3300 --tp 3400 --yes
    python agent/plugin/hydra.py order sell_limit --price 3390 --volume 0.10 --yes
    python agent/plugin/hydra.py order modify_position --ticket 123456 --sl 3280 --tp 3400 --yes
    python agent/plugin/hydra.py order modify_pending --ticket 123457 --price 3385 --yes
    python agent/plugin/hydra.py order close --ticket 123456 --yes
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    return s or "unnamed"


def _latest_run_dir() -> Path | None:
    runs = ROOT / "reports" / "runs"
    if not runs.is_dir():
        return None
    dirs = sorted((d for d in runs.iterdir() if d.is_dir()), reverse=True)
    return dirs[0] if dirs else None


def _load_multi_period_raw(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_bt(args: argparse.Namespace) -> int:
    from run_custom_benchmark import main as benchmark_main

    argv = ["run_custom_benchmark.py", "--variants", args.variants, "--name", args.name]
    if args.multi_period:
        argv.append("--multi-period")
    else:
        if not args.start or not args.end:
            print("ERROR: single-window mode needs --start and --end", file=sys.stderr)
            return 2
        argv.extend(["--start", args.start, "--end", args.end])
    if args.export_trades:
        argv.append("--export-trades")
    sys.argv = argv
    benchmark_main()
    run_dir = _latest_run_dir()
    if run_dir:
        print(f"\nREPORT_DIR={run_dir}")
        print(f"SUMMARY_HTML={run_dir / 'multi_period_summary.html'}")
    return 0


def _variants_from_args(variants: str):
    from strategie.registry import get_variant

    ids = [v.strip() for v in variants.split(",") if v.strip()]
    return [get_variant(vid) for vid in ids]


def _write_report(path: Path, title: str, body_html: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><title>{title}</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; padding: 24px; }}
h1 {{ color: #f0f3f6; border-bottom: 2px solid #2dd4bf; padding-bottom: 8px; }}
.pos {{ color: #3fb950; }} .neg {{ color: #f85149; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
th, td {{ border: 1px solid #30363d; padding: 8px 10px; text-align: left; }}
th {{ background: #161b22; }}
</style></head><body>
<h1>{title}</h1>
{body_html}
</body></html>"""
    path.write_text(html, encoding="utf-8")
    return path


def _run_multi_period_benchmark(variants: str, name: str, export_trades: bool) -> Path | None:
    from analysis.multiPeriod import DEFAULT_PERIODS, format_multi_period_text, generate_multi_period_html, run_multi_period
    from analysis.runManager import create_run_dir, write_json, write_text
    from analysis.tradeExport import build_multi_period_payload, write_trades_json
    import analysis.htmlReport as hr
    from analysis.htmlReport import generate_html_report

    specs = _variants_from_args(variants)
    run_dir = create_run_dir(name)

    def on_period_done(period, period_results):
        hr.BENCHMARK_START = period.start
        hr.BENCHMARK_END = period.end
        generate_html_report(period_results, str(run_dir / f"period_{period.label}.html"))

    results = run_multi_period(specs, DEFAULT_PERIODS, on_period_done=on_period_done)
    write_text(run_dir, "multi_period_summary.txt", format_multi_period_text(results, DEFAULT_PERIODS))
    generate_multi_period_html(
        results, DEFAULT_PERIODS, str(run_dir / "multi_period_summary.html"),
        title=f"Benchmark: {name} (Multi-Period)",
    )
    write_json(run_dir, "multi_period_raw.json", {
        r.spec.variant_id: {
            "name": r.spec.name,
            "group": r.spec.group,
            "periods": r.periods,
            "aggregate": r.aggregate(),
        }
        for r in results
    })
    if export_trades:
        write_trades_json(run_dir, build_multi_period_payload(results))
    return run_dir


def cmd_validate(args: argparse.Namespace) -> int:
    from analysis.multiPeriod import DEFAULT_PERIODS

    if args.run:
        run_dir = Path(args.run)
        if not run_dir.is_absolute():
            run_dir = ROOT / run_dir
        raw_path = run_dir / "multi_period_raw.json"
        if not raw_path.is_file():
            print(f"ERROR: {raw_path} not found", file=sys.stderr)
            return 1
        raw = _load_multi_period_raw(raw_path)
    else:
        if not args.variants:
            print("ERROR: --variants or --run required", file=sys.stderr)
            return 2
        run_dir = _run_multi_period_benchmark(args.variants, args.name or "validate", args.export_trades)
        raw = _load_multi_period_raw(run_dir / "multi_period_raw.json")

    rows = []
    for vid, data in raw.items():
        agg = data.get("aggregate") or {}
        if "error" in agg:
            rows.append((data.get("name", vid), "ERROR", agg["error"], "", "", ""))
            continue
        floor = agg.get("min_return_pct", 0)
        consist = agg.get("consistency", 0)
        worst_dd = agg.get("worst_dd_pct", 0)
        worst_day = agg.get("worst_day_dd_pct", 0)
        verdict = "PASS" if floor > 0 and consist > 0 else "REVIEW"
        rows.append((
            data.get("name", vid), verdict,
            f"{floor:+.1f}%", f"{consist:+.1f}",
            f"{worst_dd:.1f}%", f"{worst_day:.1f}%",
        ))

    table = "<table><thead><tr><th>Strategy</th><th>Verdict</th><th>Floor</th>"
    table += "<th>Consistency</th><th>Worst DD</th><th>Worst day DD</th></tr></thead><tbody>"
    for name, verdict, floor, consist, dd, day in rows:
        cls = "pos" if verdict == "PASS" else "neg"
        table += f"<tr><td>{name}</td><td class='{cls}'>{verdict}</td>"
        table += f"<td>{floor}</td><td>{consist}</td><td>{dd}</td><td>{day}</td></tr>"
    table += "</tbody></table>"
    table += "<p class='neg'>Buy &amp; Hold / S&P comparison: not yet implemented in framework.</p>"

    out = run_dir / "validation_report.html"
    _write_report(out, "OOS Validation", table)
    print(f"VALIDATION_REPORT={out}")
    return 0


def cmd_ftmo(args: argparse.Namespace) -> int:
    run_dir = Path(args.run) if args.run else _latest_run_dir()
    if run_dir is None:
        print("ERROR: no run folder found", file=sys.stderr)
        return 1
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    raw_path = run_dir / "multi_period_raw.json"
    if not raw_path.is_file():
        print(f"ERROR: {raw_path} not found — run /bt or /validate first", file=sys.stderr)
        return 1
    raw = _load_multi_period_raw(raw_path)

    rows = []
    for vid, data in raw.items():
        agg = data.get("aggregate") or {}
        name = data.get("name", vid)
        if "error" in agg:
            rows.append((name, "FAIL", "no valid periods", "", ""))
            continue
        ok = (
            agg.get("all_prop_ok")
            and agg.get("all_profitable")
            and agg.get("worst_dd_pct", 99) < 10.0
            and agg.get("worst_day_dd_pct", 99) < 5.0
        )
        verdict = "PASS" if ok else "FAIL"
        rows.append((
            name, verdict,
            "yes" if agg.get("all_profitable") else "no",
            f"{agg.get('worst_dd_pct', 0):.1f}%",
            f"{agg.get('worst_day_dd_pct', 0):.1f}%",
        ))

    table = "<table><thead><tr><th>Strategy</th><th>FTMO</th><th>All windows +</th>"
    table += "<th>Worst DD</th><th>Worst day DD</th></tr></thead><tbody>"
    for name, verdict, prof, dd, day in rows:
        cls = "pos" if verdict == "PASS" else "neg"
        table += f"<tr><td>{name}</td><td class='{cls}'><strong>{verdict}</strong></td>"
        table += f"<td>{prof}</td><td>{dd}</td><td>{day}</td></tr>"
    table += "</tbody></table>"

    out = run_dir / "ftmo_report.html"
    _write_report(out, "FTMO Prop Check", table)
    print(f"FTMO_REPORT={out}")
    return 0


def cmd_phasemap(args: argparse.Namespace) -> int:
    from collections import Counter

    from core.config import configConnection
    from core.enums import TimeFrame
    from core.mt5connection import MT5Connector
    from execution.live.mt5execution import MT5CExecution
    from strategie.tools.marketPhase import MarketPhaseClassifier

    start = _parse_date(args.start)
    end = _parse_date(args.end)
    config = configConnection()
    symbol = config.getSymbol()

    connector = MT5Connector()
    connector.initialize()
    connector.set_testing_window(start, end)
    exec_layer = MT5CExecution()
    clf = MarketPhaseClassifier()

    candles = exec_layer.getHistoricalCandles(TimeFrame.D1, end, 500, symbol) or []
    candles = [c for c in candles if start <= c.time <= end]
    counts: Counter = Counter()
    rows = []
    for c in candles[-min(len(candles), 120):]:
        hist = [x for x in candles if x.time <= c.time]
        res = clf.calculate(hist)
        if res is None:
            continue
        counts[res.phase.value] += 1
        rows.append((c.time.date(), res.phase.value, f"{res.adx:.1f}", res.vr, res.direction))

    summary = "<h2>Phase distribution</h2><ul>"
    for phase, n in counts.most_common():
        summary += f"<li>{phase}: {n} days</li>"
    summary += "</ul><h2>Recent days</h2><table><thead><tr>"
    summary += "<th>Date</th><th>Phase</th><th>ADX</th><th>VR</th><th>Dir</th></tr></thead><tbody>"
    for d, ph, adx, vr, dr in rows[-40:]:
        vr_s = f"{vr:.2f}" if vr is not None else "–"
        summary += f"<tr><td>{d}</td><td>{ph}</td><td>{adx}</td><td>{vr_s}</td><td>{dr:+d}</td></tr>"
    summary += "</tbody></table>"
    summary += "<p>Routing hint: TREND → trend edges; FLAT_RANGE → mean-reversion; WHIPSAW → avoid fades.</p>"

    run_dir = ROOT / "reports" / "runs" / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_phasemap"
    run_dir.mkdir(parents=True)
    out = run_dir / "phasemap.html"
    _write_report(out, f"Market phase map — {symbol}", summary)
    print(f"PHASEMAP_REPORT={out}")
    return 0


def cmd_sanity(args: argparse.Namespace) -> int:
    from run_sanity_check import main as sanity_main

    sys.argv = [
        "run_sanity_check.py",
        "--variant", args.variant,
        "--start", args.start,
        "--end", args.end,
    ]
    sanity_main()
    run_dir = _latest_run_dir()
    if run_dir:
        print(f"SANITY_REPORT={run_dir / 'sanity_check.txt'}")
    return 0


def cmd_newstrategy(args: argparse.Namespace) -> int:
    slug = _slug(args.name)
    class_name = "".join(p.capitalize() for p in slug.split("_"))
    vid = slug if slug.startswith("example_") else f"user_{slug}"
    path = ROOT / "strategie" / "variants" / f"{slug}.py"
    if path.exists():
        print(f"ERROR: {path} already exists", file=sys.stderr)
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'''"""
Strategy: {args.name}
Register in strategie/registry.py when ready.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from data.trade import Trade
from strategie.examples.base import ExampleStrategyBase


class {class_name}(ExampleStrategyBase):
    VARIANT_ID = "{vid}"
    VARIANT_NAME = "{args.name}"
    VARIANT_GROUP = "User"

    def planTradeGrade_A(self, target_date_time: datetime | None) -> Optional[Trade]:
        # TODO: entry signal
        return None

    def adjustPendingTradeGrade_A(self, target_date_time: datetime | None) -> None:
        # TODO: stale cancel, re-price
        pass

    def manageActiveTradeGrade_A(self, target_date_time: datetime | None) -> None:
        # TODO: trailing, BE, time exit
        pass
''', encoding="utf-8")
    print(f"CREATED={path}")
    print("Next: implement hooks, add VariantSpec to strategie/registry.py, run:")
    print(f"  python agent/plugin/hydra.py sanity --variant {vid} --start YYYY-MM-DD --end YYYY-MM-DD")
    return 0


def cmd_newindicator(args: argparse.Namespace) -> int:
    slug = _slug(args.name)
    class_name = "".join(p.capitalize() for p in slug.split("_")) + "Indicator"
    result_name = "".join(p.capitalize() for p in slug.split("_")) + "Result"
    path = ROOT / "strategie" / "tools" / f"{slug}.py"
    if path.exists():
        print(f"ERROR: {path} already exists", file=sys.stderr)
        return 1
    path.write_text(f'''"""
Indicator: {args.name}
Style: strategie/tools/ATR.py — one tool per file.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from core.config import configConnection
from core.enums import TimeFrame
from data.candle import Candle
from execution.live.mt5execution import MT5CExecution


@dataclass
class {result_name}:
    value: float


class {class_name}:
    def __init__(self, period: int = 14, timeframe: TimeFrame = TimeFrame.H1):
        self.period = period
        self.timeframe = timeframe
        self.config = configConnection()
        self.execution = MT5CExecution()

    def calculate_by_time(self, reference_time: Optional[datetime] = None) -> {result_name}:
        if reference_time is None:
            reference_time = datetime.now(timezone.utc)
        candles = self.execution.getHistoricalCandles(
            self.timeframe, reference_time, self.period * 3, self.config.getSymbol()
        )
        return self.calculate(candles or [])

    def calculate(self, candles: List[Candle]) -> {result_name}:
        if not candles:
            return {result_name}(value=0.0)
        # TODO: core math
        return {result_name}(value=0.0)
''', encoding="utf-8")
    print(f"CREATED={path}")
    return 0


def _live_status() -> int:
    """Read-only snapshot of the live account: balance/equity + open positions + pendings.
    Lets the agent MONITOR live trading before/while a strategy runs."""
    import MetaTrader5 as mt5
    from core.mt5connection import MT5Connector

    conn = MT5Connector()
    conn.initialize()
    try:
        acc = mt5.account_info()
        positions = mt5.positions_get() or []
        orders = mt5.orders_get() or []
        if acc is not None:
            print(f"ACCOUNT balance={acc.balance:.2f} equity={acc.equity:.2f} "
                  f"margin_free={acc.margin_free:.2f} currency={acc.currency}")
        print(f"OPEN_POSITIONS={len(positions)}")
        for p in positions:
            side = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
            print(f"  #{p.ticket} {p.symbol} {side} vol={p.volume} entry={p.price_open} "
                  f"sl={p.sl} tp={p.tp} pnl={p.profit:+.2f} [{p.comment}]")
        print(f"PENDING_ORDERS={len(orders)}")
        for o in orders:
            print(f"  #{o.ticket} {o.symbol} type={o.type} vol={o.volume_current} "
                  f"price={o.price_open} [{o.comment}]")
        return 0
    finally:
        conn.shutdown()


def cmd_live(args: argparse.Namespace) -> int:
    """Live trading control. `status` is read-only; `start` sends REAL orders."""
    if args.action == "status":
        return _live_status()

    # action == "start"
    from strategie.registry import get_variant

    if not args.variant:
        print("ERROR: 'live start' needs --variant <variant_id>", file=sys.stderr)
        return 2
    try:
        spec = get_variant(args.variant)
    except KeyError:
        print(f"ERROR: unknown variant {args.variant}", file=sys.stderr)
        return 1
    if spec.group == "Examples":
        print(f"REFUSED: '{args.variant}' is an EXAMPLE strategy (demo only) — never trade it live.",
              file=sys.stderr)
        return 2

    print("=== LIVE TRADING — REAL ORDERS ===")
    print(f"  variant : {spec.variant_id}  ({spec.name})")
    print("  This sends REAL orders to your MT5 account. You are responsible for risk & compliance.")
    if not args.yes:
        print("  DRY RUN — nothing started. Re-run with --yes to actually launch the live engine.")
        return 0

    import subprocess
    # Reuses the framework live entry point (its own --variant guard + example warning).
    return subprocess.call([sys.executable, "-u", str(ROOT / "run_live.py"),
                            "--variant", args.variant])


def cmd_order(args: argparse.Namespace) -> int:
    """Discretionary single order — the agent trades DIRECTLY, without a coded strategy.
    Anything that sends/changes an order needs --yes (real money)."""
    import MetaTrader5 as mt5
    from core.config import configConnection
    from core.mt5connection import MT5Connector
    from execution.live.mt5execution import MT5CExecution
    from data.trade import Trade, TradeAction, TradeStatus, TradeType

    entries = {
        "buy":        (TradeType.BUY,        TradeAction.ACTION,  TradeStatus.RUNNING, False),
        "sell":       (TradeType.SELL,       TradeAction.ACTION,  TradeStatus.RUNNING, False),
        "buy_limit":  (TradeType.BUY_LIMIT,  TradeAction.PENDING, TradeStatus.OPEN,    True),
        "sell_limit": (TradeType.SELL_LIMIT, TradeAction.PENDING, TradeStatus.OPEN,    True),
        "buy_stop":   (TradeType.BUY_STOP,   TradeAction.PENDING, TradeStatus.OPEN,    True),
        "sell_stop":  (TradeType.SELL_STOP,  TradeAction.PENDING, TradeStatus.OPEN,    True),
    }
    config = configConnection()
    config.live = True
    symbol = config.getSymbol()
    conn = MT5Connector()
    conn.initialize()
    try:
        exe = MT5CExecution()
        act = args.action

        if act in entries:
            if not args.volume:
                print("ERROR: entry needs --volume (lots)", file=sys.stderr)
                return 2
            ttype, taction, tstatus, needs_price = entries[act]
            if needs_price and args.price is None:
                print(f"ERROR: {act} is a pending order — needs --price", file=sys.stderr)
                return 2
            trade = Trade(
                symbol=symbol, type=ttype, action=taction, ticket=0,
                entry_price=float(args.price) if args.price is not None else 0.0,
                volume=float(args.volume), volume_initial=float(args.volume),
                comment=args.comment or "agent-manual", stop_loss=args.sl, take_profit=args.tp,
                initial_stop_loss=args.sl, status=tstatus,
            )
            where = f"price={args.price}" if needs_price else "@market"
            print(f"ORDER {act} {symbol} vol={args.volume} {where}"
                  + (f" sl={args.sl}" if args.sl else "") + (f" tp={args.tp}" if args.tp else ""))
            if not args.yes:
                print("  DRY RUN — re-run with --yes to send this REAL order.")
                return 0
            result = exe.execute_trade_request(trade)
            if result is None:
                print("ORDER_REJECTED (see error above)", file=sys.stderr)
                return 1
            print(f"ORDER_PLACED ticket={result.ticket} {act} vol={args.volume}")
            return 0

        if act == "close":
            if not args.ticket:
                print("ERROR: close needs --ticket", file=sys.stderr)
                return 2
            pos = mt5.positions_get(ticket=int(args.ticket))
            if not pos:
                print(f"ERROR: no open position #{args.ticket}", file=sys.stderr)
                return 1
            p = pos[0]
            print(f"CLOSE #{p.ticket} {p.symbol} vol={p.volume} pnl={p.profit:+.2f}")
            if not args.yes:
                print("  DRY RUN — re-run with --yes to close this position.")
                return 0
            ttype = TradeType.BUY if p.type == mt5.POSITION_TYPE_BUY else TradeType.SELL
            trade = Trade(symbol=p.symbol, type=ttype, action=TradeAction.ACTION, ticket=int(p.ticket),
                          entry_price=p.price_open, volume=p.volume, volume_initial=p.volume,
                          comment="agent-close", status=TradeStatus.CLOSED)
            ok = exe.execute_trade_request(trade)
            print("CLOSED" if ok else "CLOSE_FAILED")
            return 0 if ok else 1

        if act == "cancel":
            if not args.ticket:
                print("ERROR: cancel needs --ticket", file=sys.stderr)
                return 2
            print(f"CANCEL pending #{args.ticket}")
            if not args.yes:
                print("  DRY RUN — re-run with --yes to cancel this pending order.")
                return 0
            trade = Trade(symbol=symbol, type=TradeType.BUY_LIMIT, action=TradeAction.PENDING_REMOVE,
                          ticket=int(args.ticket), entry_price=0.0, volume=0.0)
            ok = exe.execute_trade_request(trade)
            print("CANCELLED" if ok else "CANCEL_FAILED")
            return 0 if ok else 1

        if act == "modify_position":
            if not args.ticket:
                print("ERROR: modify_position needs --ticket", file=sys.stderr)
                return 2
            if args.sl is None and args.tp is None:
                print("ERROR: modify_position needs --sl and/or --tp", file=sys.stderr)
                return 2
            pos = mt5.positions_get(ticket=int(args.ticket))
            if not pos:
                print(f"ERROR: no open position #{args.ticket}", file=sys.stderr)
                return 1
            p = pos[0]
            parts = [f"MODIFY position #{p.ticket} {p.symbol}"]
            if args.sl is not None:
                parts.append(f"sl={args.sl}")
            if args.tp is not None:
                parts.append(f"tp={args.tp}")
            print(" ".join(parts))
            if not args.yes:
                print("  DRY RUN — re-run with --yes to modify this position SL/TP.")
                return 0
            ttype = TradeType.BUY if p.type == mt5.POSITION_TYPE_BUY else TradeType.SELL
            trade = Trade(
                symbol=p.symbol, type=ttype, action=TradeAction.ACTION_MODIFY_SL_TP,
                ticket=int(p.ticket), entry_price=p.price_open, volume=p.volume,
                volume_initial=p.volume, stop_loss=args.sl, take_profit=args.tp,
                comment="agent-modify-sl", status=TradeStatus.RUNNING,
            )
            ok = exe.execute_trade_request(trade)
            print("MODIFIED" if ok else "MODIFY_FAILED")
            return 0 if ok else 1

        if act == "modify_pending":
            if not args.ticket:
                print("ERROR: modify_pending needs --ticket", file=sys.stderr)
                return 2
            if args.price is None and args.sl is None and args.tp is None:
                print("ERROR: modify_pending needs --price and/or --sl and/or --tp", file=sys.stderr)
                return 2
            orders = mt5.orders_get(ticket=int(args.ticket))
            if not orders:
                print(f"ERROR: no pending order #{args.ticket}", file=sys.stderr)
                return 1
            o = orders[0]
            new_price = float(args.price) if args.price is not None else float(o.price_open)
            parts = [f"MODIFY pending #{o.ticket} {o.symbol} price={new_price}"]
            if args.sl is not None:
                parts.append(f"sl={args.sl}")
            if args.tp is not None:
                parts.append(f"tp={args.tp}")
            print(" ".join(parts))
            if not args.yes:
                print("  DRY RUN — re-run with --yes to modify this pending order.")
                return 0
            type_map = {
                mt5.ORDER_TYPE_BUY_LIMIT: TradeType.BUY_LIMIT,
                mt5.ORDER_TYPE_SELL_LIMIT: TradeType.SELL_LIMIT,
                mt5.ORDER_TYPE_BUY_STOP: TradeType.BUY_STOP,
                mt5.ORDER_TYPE_SELL_STOP: TradeType.SELL_STOP,
            }
            ttype = type_map.get(o.type, TradeType.BUY_LIMIT)
            trade = Trade(
                symbol=o.symbol, type=ttype, action=TradeAction.PENDING_MODIFY,
                ticket=int(o.ticket), entry_price=new_price, volume=float(o.volume_current),
                volume_initial=float(o.volume_current), stop_loss=args.sl, take_profit=args.tp,
                comment="agent-modify-pending", status=TradeStatus.OPEN,
            )
            ok = exe.execute_trade_request(trade)
            print("MODIFIED" if ok else "MODIFY_FAILED")
            return 0 if ok else 1

        print(f"ERROR: unknown order action {act}", file=sys.stderr)
        return 2
    finally:
        conn.shutdown()


def cmd_catalog(_args: argparse.Namespace) -> int:
    from core.enums import TimeFrame
    from strategie.registry import ALL_VARIANTS

    tools = sorted(p.stem for p in (ROOT / "strategie" / "tools").glob("*.py"))
    print("=== Timeframes ===")
    for tf in TimeFrame:
        print(f"  {tf.name}")
    print("\n=== Indicators (strategie/tools/) ===")
    for t in tools:
        print(f"  {t}")
    print("\n=== Registered variants ===")
    for v in ALL_VARIANTS:
        print(f"  {v.variant_id}: {v.name} [{v.group}]")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="HydraTrade agent plugin")
    sub = parser.add_subparsers(dest="command", required=True)

    p_bt = sub.add_parser("bt", help="Backtest → HTML reports")
    p_bt.add_argument("--variants", required=True, help="Comma-separated variant IDs")
    p_bt.add_argument("--multi-period", action="store_true", help="Use DEFAULT_PERIODS")
    p_bt.add_argument("--start", help="YYYY-MM-DD (single window)")
    p_bt.add_argument("--end", help="YYYY-MM-DD (single window)")
    p_bt.add_argument("--name", default="agent_bt")
    p_bt.add_argument("--export-trades", action="store_true")
    p_bt.set_defaults(func=cmd_bt)

    p_val = sub.add_parser("validate", help="OOS validation report")
    p_val.add_argument("--variants", help="Run fresh multi-period benchmark")
    p_val.add_argument("--run", help="Existing reports/runs/... folder")
    p_val.add_argument("--name", default="validate")
    p_val.add_argument("--export-trades", action="store_true")
    p_val.set_defaults(func=cmd_validate)

    p_ftmo = sub.add_parser("ftmo", help="FTMO prop PASS/FAIL report")
    p_ftmo.add_argument("--run", help="reports/runs/... folder (default: latest)")
    p_ftmo.set_defaults(func=cmd_ftmo)

    p_phase = sub.add_parser("phasemap", help="Market phase classification report")
    p_phase.add_argument("--start", required=True)
    p_phase.add_argument("--end", required=True)
    p_phase.set_defaults(func=cmd_phasemap)

    p_sanity = sub.add_parser("sanity", help="Per-trade sanity check")
    p_sanity.add_argument("--variant", required=True)
    p_sanity.add_argument("--start", required=True)
    p_sanity.add_argument("--end", required=True)
    p_sanity.set_defaults(func=cmd_sanity)

    p_strat = sub.add_parser("newstrategy", help="Scaffold strategy file")
    p_strat.add_argument("name")
    p_strat.set_defaults(func=cmd_newstrategy)

    p_ind = sub.add_parser("newindicator", help="Scaffold indicator tool")
    p_ind.add_argument("name")
    p_ind.set_defaults(func=cmd_newindicator)

    p_cat = sub.add_parser("catalog", help="List timeframes, tools, variants")
    p_cat.set_defaults(func=cmd_catalog)

    p_live = sub.add_parser("live", help="Live trading: status (read-only) | start (REAL orders)")
    p_live.add_argument("action", choices=["status", "start"],
                        help="status = account/positions snapshot; start = launch live engine")
    p_live.add_argument("--variant", help="variant_id to trade live (required for start)")
    p_live.add_argument("--yes", action="store_true", help="confirm a REAL live start")
    p_live.set_defaults(func=cmd_live)

    p_order = sub.add_parser("order", help="Discretionary order — agent trades directly (REAL orders)")
    p_order.add_argument("action", choices=["buy", "sell", "buy_limit", "sell_limit",
                                            "buy_stop", "sell_stop", "close", "cancel",
                                            "modify_position", "modify_pending"],
                         help="entries; close/cancel/modify by --ticket")
    p_order.add_argument("--volume", type=float, help="lots (entries)")
    p_order.add_argument("--price", type=float, help="entry price (pending orders)")
    p_order.add_argument("--sl", type=float, help="stop-loss price")
    p_order.add_argument("--tp", type=float, help="take-profit price")
    p_order.add_argument("--ticket", type=int, help="position/order ticket (close/cancel)")
    p_order.add_argument("--comment", help="order comment")
    p_order.add_argument("--yes", action="store_true", help="confirm the REAL order")
    p_order.set_defaults(func=cmd_order)

    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyError as e:
        print(f"ERROR: unknown variant {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
