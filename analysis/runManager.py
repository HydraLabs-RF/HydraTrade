"""
Run-Verwaltung fuer Reports: jeder Lauf bekommt einen eigenen, eindeutigen Ordner.

Statt reports/xyz.html immer wieder zu ueberschreiben, legt jeder Runner via
create_run_dir("name") einen Ordner reports/runs/<YYYYMMDD_HHMMSS>_<name>/ an
und schreibt alle Artefakte (HTML, TXT, JSON) dort hinein. Damit geht kein
Ergebnis mehr verloren und Laeufe bleiben vergleichbar.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

REPORTS_ROOT = Path("reports")
RUNS_ROOT = REPORTS_ROOT / "runs"


def create_run_dir(run_name: str) -> Path:
    """Erzeugt reports/runs/<timestamp>_<run_name>/ und gibt den Pfad zurueck."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in run_name.strip())
    run_dir = RUNS_ROOT / f"{stamp}_{safe}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def write_json(run_dir: Path, filename: str, payload) -> Path:
    """Speichert Rohdaten eines Laufs als JSON (fuer spaetere Auswertungen)."""
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
