"""
HydraTrade example strategies benchmark (used by the web UI, but also
usable from the command line).

Simulate arbitrary variants over any time window, optionally also as a
multi-period check (3 separate ~3-month windows).

Usage:
    python run_custom_benchmark.py --start 2026-01-01 --end 2026-06-01 --variants example_ema_cross,example_supertrend
    python run_custom_benchmark.py --multi-period --variants example_volume_profile --name my_test
"""

import argparse
from datetime import datetime, timezone

from analysis.htmlReport import generate_html_report
import analysis.htmlReport as hr
from analysis.multiPeriod import (
    DEFAULT_PERIODS,
    extended_stats,
    format_multi_period_text,
    generate_multi_period_html,
    run_multi_period,
)
from analysis.runManager import create_run_dir, write_json, write_text
from analysis.strategyBenchmark import run_full_benchmark
from analysis.tradeExport import (
    build_multi_period_payload,
    build_single_window_payload,
    write_trades_json,
)
from core.config import configConnection
from strategie.registry import get_variant


def _parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def main():
    parser = argparse.ArgumentParser(description="Frei konfigurierbarer Strategie-Benchmark")
    parser.add_argument("--variants", required=True, help="Komma-Liste von Variant-IDs")
    parser.add_argument("--start", default=None, help="Startdatum YYYY-MM-DD (Einzelfenster)")
    parser.add_argument("--end", default=None, help="Enddatum YYYY-MM-DD (Einzelfenster)")
    parser.add_argument("--multi-period", action="store_true",
                        help="Statt Einzelfenster die 3 Standard-Perioden testen (robust gegen Overfitting)")
    parser.add_argument("--name", default="custom_benchmark", help="Name des Run-Ordners")
    parser.add_argument("--export-trades", action="store_true",
                        help="Write trades.json (also enabled via Settings → export trade history)")
    args = parser.parse_args()

    wanted = [v.strip() for v in args.variants.split(",") if v.strip()]
    try:
        variants = [get_variant(vid) for vid in wanted]
    except KeyError as e:
        raise SystemExit(f"FEHLER: unbekannte Variant-ID {e}")
    if not variants:
        raise SystemExit("FEHLER: keine Varianten angegeben")

    export_trades = args.export_trades or configConnection().getExportTradeHistory()

    run_dir = create_run_dir(args.name)
    print(f"Run-Ordner: {run_dir}")
    print(f"{len(variants)} Varianten:")
    for v in variants:
        print(f"  - {v.variant_id}: {v.name}")

    if args.multi_period:
        periods = DEFAULT_PERIODS
        print(f"\nMulti-Perioden-Modus: {len(periods)} Fenster\n")

        def on_period_done(period, period_results):
            hr.BENCHMARK_START = period.start
            hr.BENCHMARK_END = period.end
            out = run_dir / f"period_{period.label}.html"
            generate_html_report(period_results, str(out))
            print(f"  Perioden-Report: {out}")

        results = run_multi_period(variants, periods, on_period_done=on_period_done)
        text = format_multi_period_text(results, periods)
        print("\n" + text)
        write_text(run_dir, "multi_period_summary.txt", text)
        generate_multi_period_html(
            results, periods, str(run_dir / "multi_period_summary.html"),
            title=f"Benchmark: {args.name} (Multi-Perioden)",
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
            path = write_trades_json(run_dir, build_multi_period_payload(results))
            if path:
                print(f"Trade export: {path}")
    else:
        if not args.start or not args.end:
            raise SystemExit("FEHLER: --start und --end sind ohne --multi-period Pflicht")
        start = _parse_date(args.start)
        end = _parse_date(args.end)
        if end <= start:
            raise SystemExit("FEHLER: Enddatum muss nach dem Startdatum liegen")

        print(f"\nZeitfenster: {start.date()} -> {end.date()}\n")
        results = run_full_benchmark(start=start, end=end, variants=variants)

        hr.BENCHMARK_START = start
        hr.BENCHMARK_END = end
        path = generate_html_report(results, str(run_dir / "benchmark.html"))
        print(f"\nReport gespeichert: {path}")

        payload = {}
        for r in results:
            s = dict(r.summary)
            if "error" not in s:
                s.update(extended_stats(r))
            payload[r.spec.variant_id] = {
                "name": r.spec.name,
                "group": r.spec.group,
                "summary": s,
            }
        write_json(run_dir, "benchmark_raw.json", payload)
        if export_trades:
            path = write_trades_json(run_dir, build_single_window_payload(results))
            if path:
                print(f"Trade export: {path}")

    print(f"\nAlle Artefakte in: {run_dir}")


if __name__ == "__main__":
    main()
