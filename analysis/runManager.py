"""
Run management for reports: each run gets its own unique folder.

Instead of overwriting reports/xyz.html repeatedly, each runner creates a folder
reports/runs/<YYYYMMDD_HHMMSS>_<name>/ via create_run_dir("name") and writes
all artifacts (HTML, TXT, JSON) there. No results are lost and runs remain
comparable.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

REPORTS_ROOT = Path("reports")
RUNS_ROOT = REPORTS_ROOT / "runs"


def create_run_dir(run_name: str) -> Path:
    """Create reports/runs/<timestamp>_<run_name>/ and return the path."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in run_name.strip())
    run_dir = RUNS_ROOT / f"{stamp}_{safe}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def write_json(run_dir: Path, filename: str, payload) -> Path:
    """Save raw run data as JSON (for later analysis)."""
    path = run_dir / filename

    def _default(o):
        if isinstance(o, datetime):
            return o.isoformat()
        return str(o)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=_default)
    return path


def write_text(run_dir: Path, filename: str, text: str) -> Path:
    path = run_dir / filename
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
