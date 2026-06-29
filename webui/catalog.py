"""
HydraTrade Web UI catalog: runnable actions and example strategy registry.
"""

from __future__ import annotations

from typing import Callable, Dict, List

from strategie.registry import ALL_VARIANTS, GROUP_INFO


def get_variant_catalog() -> List[dict]:
    return [
        {
            "variant_id": v.variant_id,
            "name": v.name,
            "group": v.group,
            "description": v.description,
        }
        for v in ALL_VARIANTS
    ]


ACTIONS: List[dict] = [
    {
        "id": "custom_benchmark",
        "title": "Custom Benchmark",
        "category": "Backtest",
        "recommended": True,
        "script": "run_custom_benchmark.py",
        "duration_hint": "~1–5 min per strategy and 3-month window",
        "description": "Run any example strategy over a custom date range. "
                       "Produces an HTML report with equity curves and metrics. "
                       "Enable multi-period mode for three separate ~3-month windows "
                       "— the most robust check against overfitting.",
        "params": [
            {"name": "variants", "label": "Strategies", "type": "variants", "required": True},
            {"name": "multi_period", "label": "Multi-period mode (3 standard windows, ignores start/end)",
             "type": "bool", "default": False},
            {"name": "start", "label": "Start date", "type": "date", "default": "2026-03-01"},
            {"name": "end", "label": "End date", "type": "date", "default": "2026-06-08"},
            {"name": "name", "label": "Run name", "type": "text", "default": "custom_benchmark"},
            {"name": "export_trades", "label": "Export trade list (trades.json)",
             "type": "bool", "default": False},
        ],
    },
        "title": "Sanity Check (trade detail)",
        "category": "Analysis",
        "script": "run_sanity_check.py",
        "duration_hint": "~1–5 min",
        "description": "Lists every trade of a strategy (entry, exit, stop, volume, R-multiple, PnL). "
                       "Use before trusting simulation results or adapting a template for live use.",
        "params": [
            {"name": "variant", "label": "Strategy", "type": "variant_single", "required": True},
            {"name": "start", "label": "Start date", "type": "date", "required": True, "default": "2026-03-08"},
            {"name": "end", "label": "End date", "type": "date", "required": True, "default": "2026-06-08"},
        ],
    },
    {
        "id": "example_benchmark",
        "title": "Example Strategies Benchmark",
        "category": "Backtest",
        "script": "run_examples.py",
        "duration_hint": "~2–10 min",
        "description": "Runs all three shipped example strategies (EMA Cross, SuperTrend, Volume Profile) "
                       "over the default multi-period windows. Generates sample reports for the docs.",
        "params": [],
    },
    {
        "id": "analysis",
        "title": "Simulation Analysis",
        "category": "Analysis",
        "script": "run_analysis.py",
        "duration_hint": "~2–10 min",
        "description": "Detailed trade outcome analysis (win rate, R distribution, trailing losses) "
                       "for the configured simulation window.",
        "params": [],
    },
    {
        "id": "live_trading",
        "title": "Start Live Trading",
        "category": "Live",
        "script": "run_live.py",
        "dangerous": True,
        "duration_hint": "runs until stopped",
        "description": "Starts the live trading loop with the selected strategy on M5 bars "
                       "via the connected MT5 account. WARNING: places real orders! "
                       "You must pick a variant — there is no silent default.",
        "params": [
            {"name": "variant", "label": "Strategy", "type": "variant_single", "required": True},
        ],
    },
]


def _args_custom_benchmark(p: dict) -> List[str]:
    variants = p.get("variants") or []
    if not variants:
        raise ValueError("Select at least one strategy.")
    args = ["--variants", ",".join(variants)]
    name = (p.get("name") or "custom_benchmark").strip() or "custom_benchmark"
    args += ["--name", name]
    if p.get("multi_period"):
        args.append("--multi-period")
    else:
        if not p.get("start") or not p.get("end"):
            raise ValueError("Provide start and end dates (or enable multi-period mode).")
        if str(p["end"]) <= str(p["start"]):
            raise ValueError("End date must be after start date.")
        args += ["--start", str(p["start"]), "--end", str(p["end"])]
    if p.get("export_trades"):
        args.append("--export-trades")
    return args


def _args_sanity_check(p: dict) -> List[str]:
    if not p.get("variant"):
        raise ValueError("Select a strategy.")
    if not p.get("start") or not p.get("end"):
        raise ValueError("Provide start and end dates.")
    if str(p["end"]) <= str(p["start"]):
        raise ValueError("End date must be after start date.")
    return ["--variant", str(p["variant"]), "--start", str(p["start"]), "--end", str(p["end"])]


def _args_live(p: dict) -> List[str]:
    if not p.get("variant"):
        raise ValueError("Select a strategy before starting live trading.")
    return ["--variant", str(p["variant"])]


_ARG_BUILDERS: Dict[str, Callable[[dict], List[str]]] = {
    "custom_benchmark": _args_custom_benchmark,
    "sanity_check": _args_sanity_check,
    "live_trading": _args_live,
}


def get_action(action_id: str) -> dict:
    for a in ACTIONS:
        if a["id"] == action_id:
            return a
    raise KeyError(action_id)


def build_job_args(action_id: str, params: dict) -> List[str]:
    builder = _ARG_BUILDERS.get(action_id)
    if builder:
        return builder(params or {})
    return {}
