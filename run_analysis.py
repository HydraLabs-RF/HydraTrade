"""HydraTrade — simulation outcome analysis."""

from datetime import datetime, timezone

from core.branding import log, print_banner
from core.config import configConnection
from analysis.simulationAnalyzer import run_analysis, format_report
from analysis.runManager import create_run_dir, write_text

if __name__ == "__main__":
    print_banner()
    config = configConnection()
    start = config.getSimulationStart()
    end = config.getSimulationEnd()
    run_dir = create_run_dir("analysis")

    log(f"Analysis {start.date()} -> {end.date()}")
    report = run_analysis(start, end, config.getSymbol())
    text = format_report(report)
    print(text)
    write_text(run_dir, f"analysis_{start.date()}_{end.date()}.txt", text)

    alt_start = datetime(2026, 3, 2, tzinfo=timezone.utc)
    alt_end = datetime(2026, 4, 15, tzinfo=timezone.utc)
    log(f"Comparison window {alt_start.date()} -> {alt_end.date()}")
    report2 = run_analysis(alt_start, alt_end, config.getSymbol())
    text2 = format_report(report2)
    print(text2)
    write_text(run_dir, f"analysis_{alt_start.date()}_{alt_end.date()}.txt", text2)
    log(f"Reports saved in: {run_dir}")
