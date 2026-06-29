"""
Local web server for the control UI.

Uses only the Python standard library (http.server) so no extra packages
need to be installed. The server binds exclusively to 127.0.0.1 — the UI
is reachable only on this machine.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from analysis.runManager import json_safe
from webui import catalog, mt5status, problems
from webui.jobs import JobManager

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
REPORTS_DIR = PROJECT_ROOT / "reports"
RUNS_DIR = REPORTS_DIR / "runs"
OVERRIDE_FILE = PROJECT_ROOT / "webui_config.json"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".log": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

job_manager = JobManager()
_variant_cache: list | None = None
_variant_cache_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_variants_cached() -> list:
    global _variant_cache
    with _variant_cache_lock:
        if _variant_cache is None:
            _variant_cache = catalog.get_variant_catalog()
        return _variant_cache


def read_config_dict() -> dict:
    from core.config import configConnection
    c = configConnection()
    return {
        "symbol": c.symbol,
        "timeframe": c.timeframe.name,
        "simulation_start_date": c.simulation_start_date.date().isoformat(),
        "simulation_end_date": c.simulation_end_date.date().isoformat(),
        "simEQ": c.simEQ,
        "simAccCurency": c.simAccCurency,
        "magic_number": c.magic_number,
        "order_deviation": c.order_deviation,
        "simSwapEnabled": c.simSwapEnabled,
        "simExportTradeHistory": c.simExportTradeHistory,
    }


def write_config_overrides(data: dict) -> dict:
    """Validate UI input and write webui_config.json."""
    errors = []
    out: dict = {}

    symbol = str(data.get("symbol", "")).strip()
    if symbol:
        out["symbol"] = symbol
    else:
        errors.append("Symbol must not be empty.")

    tf = str(data.get("timeframe", "")).strip()
    if tf:
        from core.enums import TimeFrame
        if tf in TimeFrame.__members__:
            out["timeframe"] = tf
        else:
            errors.append(f"Unknown timeframe: {tf}")

    for key in ("simulation_start_date", "simulation_end_date"):
        val = str(data.get(key, "")).strip()
        if val:
            try:
                datetime.fromisoformat(val)
                out[key] = val
            except ValueError:
                errors.append(f"Invalid date for {key}: {val}")

    if out.get("simulation_start_date") and out.get("simulation_end_date"):
        if out["simulation_end_date"] <= out["simulation_start_date"]:
            errors.append("End date must be after start date.")

    try:
        eq = float(data.get("simEQ", 0))
        if eq > 0:
            out["simEQ"] = eq
        else:
            errors.append("Starting capital must be greater than 0.")
    except (TypeError, ValueError):
        errors.append("Starting capital must be a number.")

    cur = str(data.get("simAccCurency", "")).strip()
    if cur:
        out["simAccCurency"] = cur

    try:
        magic = int(data.get("magic_number", 0))
        if magic > 0:
            out["magic_number"] = magic
    except (TypeError, ValueError):
        errors.append("Magic number must be an integer.")

    # Rollover/swap modeling (on by default). Accepts bool or "true"/"false".
    swap_raw = data.get("simSwapEnabled", True)
    if isinstance(swap_raw, str):
        swap_raw = swap_raw.strip().lower() not in ("false", "0", "no", "off", "")
    out["simSwapEnabled"] = bool(swap_raw)

    export_raw = data.get("simExportTradeHistory", False)
    if isinstance(export_raw, str):
        export_raw = export_raw.strip().lower() in ("true", "1", "yes", "on")
    out["simExportTradeHistory"] = bool(export_raw)

    if errors:
        return {"ok": False, "errors": errors}

    with open(OVERRIDE_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return {"ok": True, "config": read_config_dict()}


def list_runs() -> list:
    runs = []
    if RUNS_DIR.exists():
        for d in sorted(RUNS_DIR.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            files = []
            main_html = None
            for f in sorted(d.iterdir()):
                if not f.is_file():
                    continue
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "type": f.suffix.lstrip("."),
                })
            html_files = [f["name"] for f in files if f["name"].endswith(".html")]
            for preferred in ("multi_period_summary.html", "mk5_multi_period.html",
                              "mk5_full_window.html", "benchmark.html"):
                if preferred in html_files:
                    main_html = preferred
                    break
            if main_html is None and html_files:
                main_html = html_files[0]

            stamp = d.name[:15]
            try:
                created = datetime.strptime(stamp, "%Y%m%d_%H%M%S").isoformat(timespec="seconds")
            except ValueError:
                created = None
            runs.append({
                "name": d.name,
                "label": d.name[16:] if len(d.name) > 16 else d.name,
                "created": created,
                "files": files,
                "main_html": main_html,
            })
    return runs


def run_detail(run_name: str) -> dict:
    safe = Path(run_name).name  # no path traversal
    d = RUNS_DIR / safe
    if not d.is_dir():
        raise FileNotFoundError(run_name)

    detail: dict = {"name": safe, "files": [], "datasets": [], "texts": {}}
    for f in sorted(d.iterdir()):
        if not f.is_file():
            continue
        detail["files"].append({"name": f.name, "size": f.stat().st_size, "type": f.suffix.lstrip(".")})
        if f.suffix == ".json" and f.stat().st_size < 5_000_000:
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if not isinstance(data, dict) or not data:
                    continue
                first = next(iter(data.values()), {})
                kind = None
                if isinstance(first, dict) and "periods" in first:
                    kind = "multi_period"
                elif isinstance(first, dict) and ("summary" in first or "return_pct" in first):
                    kind = "single_window"
                if kind:
                    detail["datasets"].append({"file": f.name, "kind": kind, "data": data})
            except Exception:
                pass
        if f.suffix == ".txt" and f.stat().st_size < 300_000:
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fh:
                    detail["texts"][f.name] = fh.read()
            except Exception:
                pass
    trades_path = d / "trades.json"
    if trades_path.is_file() and trades_path.stat().st_size < 10_000_000:
        try:
            with open(trades_path, "r", encoding="utf-8") as fh:
                detail["trades"] = json.load(fh)
        except Exception:
            pass
    return detail


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "TradingWebUI/1.0"

    # ---- Response helpers ---------------------------------------------------

    def _send_json(self, payload, status: int = 200) -> None:
        body = json.dumps(json_safe(payload), ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status)

    def _send_file(self, path: Path, base: Path) -> None:
        try:
            resolved = path.resolve()
            base_resolved = base.resolve()
            if base_resolved not in resolved.parents and resolved != base_resolved:
                self._send_error_json("Access denied", 403)
                return
            if not resolved.is_file():
                self._send_error_json("File not found", 404)
                return
            ctype = CONTENT_TYPES.get(resolved.suffix.lower(), "application/octet-stream")
            data = resolved.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._send_error_json(f"Read error: {e}", 500)

    def _read_body_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def log_message(self, fmt, *args):  # keep console quiet
        pass

    # ---- GET ----------------------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        try:
            if path in ("/", "/index.html"):
                self._send_file(STATIC_DIR / "index.html", STATIC_DIR)
            elif path.startswith("/static/"):
                self._send_file(STATIC_DIR / path[len("/static/"):], STATIC_DIR)
            elif path.startswith("/reports/"):
                self._send_file(REPORTS_DIR / path[len("/reports/"):], REPORTS_DIR)

            elif path == "/api/status":
                cfg = read_config_dict()
                force = query.get("force", ["0"])[0] == "1"
                mt5_info = mt5status.check_status(cfg["symbol"], force=force)
                jobs = job_manager.list_jobs()
                probs = problems.collect_problems(mt5_info, cfg, jobs)
                self._send_json({
                    "mt5": mt5_info,
                    "config": cfg,
                    "jobs_running": len([j for j in jobs if j["status"] == "running"]),
                    "problems": probs,
                    "server_time": datetime.now().isoformat(timespec="seconds"),
                })

            elif path == "/api/catalog":
                self._send_json({
                    "actions": catalog.ACTIONS,
                    "variants": get_variants_cached(),
                    "groups": catalog.GROUP_INFO,
                })

            elif path == "/api/config":
                self._send_json(read_config_dict())

            elif path == "/api/jobs":
                self._send_json({"jobs": job_manager.list_jobs()})

            elif path.startswith("/api/jobs/") and path.endswith("/log"):
                job_id = path[len("/api/jobs/"):-len("/log")]
                offset = int(query.get("offset", ["0"])[0])
                self._send_json(job_manager.read_log(job_id, offset))

            elif path == "/api/runs":
                self._send_json({"runs": list_runs()})

            elif path.startswith("/api/runs/"):
                run_name = path[len("/api/runs/"):]
                self._send_json(run_detail(run_name))

            elif path == "/api/live":
                cfg = read_config_dict()
                self._send_json(mt5status.get_live_overview(cfg["symbol"]))

            else:
                self._send_error_json("Unknown path", 404)
        except KeyError as e:
            self._send_error_json(f"Not found: {e}", 404)
        except FileNotFoundError as e:
            self._send_error_json(f"Not found: {e}", 404)
        except Exception as e:
            self._send_error_json(f"Internal error: {e}", 500)

    # ---- POST -----------------------------------------------------------

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        try:
            if path == "/api/jobs":
                body = self._read_body_json()
                action_id = body.get("action_id", "")
                params = body.get("params", {}) or {}
                try:
                    action = catalog.get_action(action_id)
                except KeyError:
                    self._send_error_json(f"Unknown action: {action_id}", 404)
                    return
                try:
                    args = catalog.build_job_args(action_id, params)
                except ValueError as e:
                    self._send_error_json(str(e), 400)
                    return
                try:
                    job = job_manager.start(
                        action_id=action_id,
                        title=action["title"],
                        script=action["script"],
                        args=args,
                        dangerous=action.get("dangerous", False),
                    )
                except RuntimeError as e:
                    self._send_error_json(str(e), 409)
                    return
                self._send_json({"ok": True, "job": job.to_dict()})

            elif path.startswith("/api/jobs/") and path.endswith("/stop"):
                job_id = path[len("/api/jobs/"):-len("/stop")]
                job = job_manager.stop(job_id)
                self._send_json({"ok": True, "job": job.to_dict()})

            elif path == "/api/config":
                body = self._read_body_json()
                result = write_config_overrides(body)
                self._send_json(result, 200 if result.get("ok") else 400)

            else:
                self._send_error_json("Unknown path", 404)
        except KeyError as e:
            self._send_error_json(f"Not found: {e}", 404)
        except Exception as e:
            self._send_error_json(f"Internal error: {e}", 500)


def serve(port: int = 8350) -> None:
    from core.branding import log
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    log(f"Web UI listening on http://127.0.0.1:{port}")
    log("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.shutdown()
