"""
Issue detection for the HydraTrade Web UI.

Collects anything that could block the user and returns severity plus a concrete fix hint.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OVERRIDE_FILE = PROJECT_ROOT / "webui_config.json"


def _problem(severity: str, title: str, detail: str, hint: str, area: str) -> dict:
    return {"severity": severity, "title": title, "detail": detail, "hint": hint, "area": area}


def collect_problems(mt5_status: dict, config_dict: dict, jobs: List[dict]) -> List[dict]:
    problems: List[dict] = []

    if not mt5_status.get("package_installed", True):
        problems.append(_problem(
            "critical", "MetaTrader5 package missing",
            "The Python package 'MetaTrader5' is not installed. Without it, "
            "neither simulation nor live trading will work.",
            "Run in a terminal: python -m pip install MetaTrader5",
            "MT5",
        ))
    elif not mt5_status.get("connected"):
        problems.append(_problem(
            "critical", "No connection to MT5 terminal",
            mt5_status.get("error", "MT5 initialization failed."),
            "Start MetaTrader 5 and log in. Then click 'Refresh status' in the sidebar.",
            "MT5",
        ))
    else:
        term = mt5_status.get("terminal", {})
        if term and not term.get("market_connected"):
            problems.append(_problem(
                "critical", "MT5 has no broker connection",
                "The terminal is running but not connected to the trade server "
                "(no quotes, no orders).",
                "Check the connection indicator in the bottom-right of MT5.",
                "MT5",
            ))
        if term and not term.get("trade_allowed"):
            problems.append(_problem(
                "warning", "Algo Trading disabled in terminal",
                "The 'Algo Trading' button in MT5 is off. Backtests work, "
                "but live trading cannot place orders.",
                "Enable 'Algo Trading' in MT5 (button must be green).",
                "Live",
            ))
        if mt5_status.get("symbol_ok") is False:
            problems.append(_problem(
                "critical", f"Symbol '{config_dict.get('symbol')}' unavailable",
                mt5_status.get("symbol_error", ""),
                "Pick a valid symbol in Settings or enable it in MT5 Market Watch.",
                "Settings",
            ))

    if OVERRIDE_FILE.exists():
        try:
            with open(OVERRIDE_FILE, "r", encoding="utf-8") as f:
                json.load(f)
        except Exception:
            problems.append(_problem(
                "error", "Settings file is corrupted",
                f"{OVERRIDE_FILE.name} does not contain valid JSON. Built-in defaults are used.",
                "Save settings again from the UI — the file will be rewritten correctly.",
                "Settings",
            ))

    try:
        start = config_dict.get("simulation_start_date", "")
        end = config_dict.get("simulation_end_date", "")
        if start and end and str(end) <= str(start):
            problems.append(_problem(
                "error", "Invalid simulation window",
                f"End date ({end}) is not after start date ({start}).",
                "Set a valid date range in Settings.",
                "Settings",
            ))
    except Exception:
        pass

    hist_start = mt5_status.get("m5_history_start")
    sim_start = str(config_dict.get("simulation_start_date", ""))[:10]
    if hist_start and sim_start and sim_start < hist_start:
        problems.append(_problem(
            "warning", "Simulation start precedes available data",
            f"M5 history only goes back to {hist_start}, but simulation starts on {sim_start}. "
            f"The backtest will begin at {hist_start}.",
            "Move the start date in Settings to after the data availability date.",
            "Settings",
        ))

    for job in jobs[:15]:
        if job["status"] == "failed":
            problems.append(_problem(
                "warning", f"Run failed: {job['title']}",
                f"The run from {job['started_at'].replace('T', ' ')} did not finish successfully "
                f"(exit code {job.get('returncode')}).",
                "Open the run log under Runs — the last lines usually show the cause.",
                "Jobs",
            ))

    live_running = [j for j in jobs if j["status"] == "running" and j.get("dangerous")]
    if live_running and mt5_status.get("terminal", {}).get("trade_allowed") is False:
        problems.append(_problem(
            "critical", "Live trading running but Algo Trading is off",
            "The live job is active but cannot place orders while Algo Trading is disabled.",
            "Enable Algo Trading in MT5 immediately or stop the live job.",
            "Live",
        ))

    order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    problems.sort(key=lambda p: order.get(p["severity"], 9))
    return problems
