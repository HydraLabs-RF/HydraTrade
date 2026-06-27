"""
Job management for the web UI.

Each action (benchmark, validation, live trading, ...) runs as its own
Python subprocess. JobManager starts, monitors, and stops these processes,
writes the log to a file, and tracks which report folders were created
during the run.

Job history is persisted as JSON under webui/jobs_data/ and survives
a server restart.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JOBS_DATA_DIR = Path(__file__).resolve().parent / "jobs_data"
RUNS_DIR = PROJECT_ROOT / "reports" / "runs"

MAX_CONCURRENT_JOBS = 2


class Job:
    def __init__(self, job_id: str, action_id: str, title: str, script: str, args: List[str],
                 dangerous: bool = False):
        self.job_id = job_id
        self.action_id = action_id
        self.title = title
        self.script = script
        self.args = args
        self.dangerous = dangerous

        self.status = "running"  # running | finished | failed | stopped
        self.returncode: Optional[int] = None
        self.started_at = datetime.now()
        self.ended_at: Optional[datetime] = None
        self.run_dirs: List[str] = []

        self.log_file = JOBS_DATA_DIR / f"{job_id}.log"
        self.meta_file = JOBS_DATA_DIR / f"{job_id}.json"
        self.process: Optional[subprocess.Popen] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "action_id": self.action_id,
            "title": self.title,
            "script": self.script,
            "args": self.args,
            "dangerous": self.dangerous,
            "status": self.status,
            "returncode": self.returncode,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "ended_at": self.ended_at.isoformat(timespec="seconds") if self.ended_at else None,
            "run_dirs": self.run_dirs,
        }

    @staticmethod
    def from_dict(d: dict) -> "Job":
        job = Job(d["job_id"], d["action_id"], d["title"], d["script"], d.get("args", []),
                  d.get("dangerous", False))
        job.status = d.get("status", "failed")
        job.returncode = d.get("returncode")
        try:
            job.started_at = datetime.fromisoformat(d["started_at"])
        except Exception:
            pass
        if d.get("ended_at"):
            try:
                job.ended_at = datetime.fromisoformat(d["ended_at"])
            except Exception:
                pass
        job.run_dirs = d.get("run_dirs", [])
        return job

    def persist(self) -> None:
        JOBS_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class JobManager:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._counter = 0
        JOBS_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._load_history()

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _load_history(self) -> None:
        for meta in sorted(JOBS_DATA_DIR.glob("*.json")):
            try:
                with open(meta, "r", encoding="utf-8") as f:
                    job = Job.from_dict(json.load(f))
                # Server was restarted -> "running" can no longer be valid
                if job.status == "running":
                    job.status = "failed"
                    job.persist()
                self._jobs[job.job_id] = job
            except Exception:
                continue

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def running_jobs(self) -> List[Job]:
        return [j for j in self._jobs.values() if j.status == "running"]

    def start(self, action_id: str, title: str, script: str, args: List[str],
              dangerous: bool = False) -> Job:
        with self._lock:
            running = self.running_jobs()
            if len(running) >= MAX_CONCURRENT_JOBS:
                raise RuntimeError(
                    f"{len(running)} jobs already running. Wait or stop a job first."
                )
            if dangerous and any(j.dangerous for j in running):
                raise RuntimeError("A live trading job is already running.")

            self._counter += 1
            job_id = f"{datetime.now():%Y%m%d_%H%M%S}_{self._counter:03d}_{action_id}"
            job = Job(job_id, action_id, title, script, args, dangerous)

            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"

            log_handle = open(job.log_file, "w", encoding="utf-8", buffering=1)
            cmd = [sys.executable, "-u", script] + args
            log_handle.write(f"$ {' '.join(cmd)}\n\n")
            try:
                job.process = subprocess.Popen(
                    cmd,
                    cwd=str(PROJECT_ROOT),
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                )
            except Exception:
                log_handle.close()
                raise

            self._jobs[job.job_id] = job
            job.persist()

        watcher = threading.Thread(target=self._watch, args=(job, log_handle), daemon=True)
        watcher.start()
        return job

    def _watch(self, job: Job, log_handle) -> None:
        try:
            returncode = job.process.wait()
        finally:
            try:
                log_handle.close()
            except Exception:
                pass
        job.returncode = returncode
        job.ended_at = datetime.now()
        if job.status != "stopped":
            job.status = "finished" if returncode == 0 else "failed"
        job.run_dirs = self._detect_run_dirs(job)
        job.persist()

    def stop(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        if job.status != "running" or not job.process:
            return job
        job.status = "stopped"
        try:
            job.process.kill()
        except Exception:
            pass
        return job

    def _detect_run_dirs(self, job: Job) -> List[str]:
        """Find report folders created during the job run."""
        if not RUNS_DIR.exists():
            return []
        found = []
        start_stamp = job.started_at.strftime("%Y%m%d_%H%M%S")
        for d in RUNS_DIR.iterdir():
            if not d.is_dir():
                continue
            # Folder name starts with YYYYMMDD_HHMMSS -> directly comparable
            prefix = d.name[:15]
            if len(prefix) == 15 and prefix >= start_stamp:
                found.append(d.name)
        return sorted(found)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_jobs(self) -> List[dict]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.started_at, reverse=True)
        return [j.to_dict() for j in jobs]

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def read_log(self, job_id: str, offset: int = 0) -> dict:
        job = self._jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        text = ""
        new_offset = offset
        if job.log_file.exists():
            with open(job.log_file, "r", encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                text = f.read()
                new_offset = f.tell()
        return {"job_id": job_id, "offset": new_offset, "content": text, "status": job.status}
