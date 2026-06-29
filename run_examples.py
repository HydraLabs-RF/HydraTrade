"""Run all example strategies and generate sample reports."""

import argparse

from analysis.htmlReport import generate_html_report
import analysis.htmlReport as hr
from analysis.multiPeriod import (
    DEFAULT_PERIODS,
    format_multi_period_text,
    generate_multi_period_html,
    run_multi_period,
)
from analysis.runManager import create_run_dir, write_json, write_text
from analysis.tradeExport import build_multi_period_payload, write_trades_json
from core.branding import log, print_banner
from core.config import configConnection
from strategie.registry import ALL_VARIANTS


def main():
    parser = argparse.ArgumentParser(description="HydraTrade example strategies benchmark")
    parser.add_argument("--name", default="example_strategies", help="Run folder name")
    args = parser.parse_args()

    print_banner()
    variants = ALL_VARIANTS
    run_dir = create_run_dir(args.name)
    log(f"Run folder: {run_dir}")
    log(f"Testing {len(variants)} example strategies across {len(DEFAULT_PERIODS)} periods")

    def on_period_done(period, period_results):
        hr.BENCHMARK_START = period.start
        hr.BENCHMARK_END = period.end
        out = run_dir / f"period_{period.label}.html"
        generate_html_report(period_results, str(out))
        log(f"Period report: {out.name}")

    results = run_multi_period(variants, DEFAULT_PERIODS, on_period_done=on_period_done)
    text = format_multi_period_text(results, DEFAULT_PERIODS)
    print("\n" + text)
    write_text(run_dir, "multi_period_summary.txt", text)
    generate_multi_period_html(
        results, DEFAULT_PERIODS, str(run_dir / "multi_period_summary.html"),
        title="HydraTrade — Example Strategies (Multi-Period)",
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
    if configConnection().getExportTradeHistory():
        path = write_trades_json(run_dir, build_multi_period_payload(results))
        if path:
            log(f"Trade export: {path.name}")
    log(f"All artifacts in: {run_dir}")


if __name__ == "__main__":
    main()
