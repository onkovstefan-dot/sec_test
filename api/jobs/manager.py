import os
import signal
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional

from db import Base, engine
from utils import recreate_sqlite_db


def read_last_log_line(log_path: str, *, max_bytes: int = 64 * 1024) -> str:
    """Return last non-empty line from a log file (best-effort)."""
    try:
        if not os.path.exists(log_path):
            return "(log file not found)"
        with open(log_path, "rb") as f:
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - max_bytes), os.SEEK_SET)
            except Exception:
                f.seek(0)
            data = f.read().decode("utf-8", errors="replace")
        lines = [ln.strip() for ln in data.splitlines() if ln.strip()]
        return lines[-1] if lines else "(log is empty)"
    except Exception as e:
        return f"(failed to read log: {e})"


@dataclass
class JobState:
    running: bool = False
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    error: Optional[str] = None
    stop_requested: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "error": self.error,
            "stop_requested": self.stop_requested,
        }


class PopulateDailyValuesJob:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = JobState()
        self._proc: subprocess.Popen[str] | None = None

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return self._state.as_dict()

    def request_stop(self) -> None:
        """Request the running job to stop.

        Implementation: terminate the subprocess running populate_daily_values.
        """
        with self._lock:
            self._state.stop_requested = True
            proc = self._proc

        if proc is None:
            return

        try:
            # Graceful first
            proc.terminate()
        except Exception:
            pass

    def start(self) -> bool:
        """Start utils.populate_daily_values.main() in a background subprocess.

        Returns True if a new job was started, False if one is already running.
        """
        with self._lock:
            if self._state.running:
                return False
            self._state.running = True
            self._state.started_at = time.time()
            self._state.ended_at = None
            self._state.error = None
            self._state.stop_requested = False
            self._proc = None

        def _runner() -> None:
            try:
                # Ensure schema exists before running the job.
                Base.metadata.create_all(bind=engine)

                with self._lock:
                    if self._state.stop_requested:
                        return

                # Run as a subprocess so we can actually stop it.
                # Uses the current Python interpreter to keep venv behavior.
                cmd = [
                    sys.executable,
                    os.path.join(
                        os.path.dirname(os.path.dirname(__file__)),
                        "..",
                        "..",
                        "utils",
                        "populate_daily_values.py",
                    ),
                ]
                cmd = [os.path.normpath(p) for p in cmd]

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                with self._lock:
                    self._proc = proc

                rc = proc.wait()
                if rc != 0 and rc is not None:
                    # Best-effort error: point user to logs.
                    with self._lock:
                        self._state.error = (
                            f"populate_daily_values exited with code {rc}. "
                            "See logs/utils_populate_daily_values.log for details."
                        )
            except Exception:
                with self._lock:
                    self._state.error = traceback.format_exc()
            finally:
                # If stop was requested, ensure process is gone.
                with self._lock:
                    proc = self._proc
                if proc is not None and proc.poll() is None:
                    try:
                        proc.kill()
                    except Exception:
                        pass

                with self._lock:
                    self._proc = None
                    self._state.running = False
                    self._state.ended_at = time.time()

        t = threading.Thread(target=_runner, name="populate_daily_values", daemon=True)
        t.start()
        return True


class RecreateSqliteDbJob:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = JobState(stop_requested=False)  # stop flag unused

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            d = self._state.as_dict()
            d.pop("stop_requested", None)
            return d

    def set_error(self, message: str) -> None:
        with self._lock:
            self._state.error = message

    def start(self) -> bool:
        """Start utils.recreate_sqlite_db.main() in a daemon thread.

        WARNING: destructive (deletes data/sec.db).
        """
        with self._lock:
            if self._state.running:
                return False
            self._state.running = True
            self._state.started_at = time.time()
            self._state.ended_at = None
            self._state.error = None

        def _runner() -> None:
            try:
                recreate_sqlite_db.main()
            except Exception:
                with self._lock:
                    self._state.error = traceback.format_exc()
            finally:
                with self._lock:
                    self._state.running = False
                    self._state.ended_at = time.time()

        t = threading.Thread(target=_runner, name="recreate_sqlite_db", daemon=True)
        t.start()
        return True


class SecApiIngestJob:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = JobState()
        self._proc: subprocess.Popen[str] | None = None

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return self._state.as_dict()

    def request_stop(self) -> None:
        with self._lock:
            self._state.stop_requested = True
            proc = self._proc

        if proc is None:
            return

        try:
            proc.terminate()
        except Exception:
            pass

    def start(
        self,
        *,
        form_types: str | None = None,
        limit: int | None = None,
        workers: int | None = None,
    ) -> bool:
        """Start jobs.sec_api_ingest.main() in a background subprocess."""
        with self._lock:
            if self._state.running:
                return False
            self._state.running = True
            self._state.started_at = time.time()
            self._state.ended_at = None
            self._state.error = None
            self._state.stop_requested = False
            self._proc = None

        def _runner() -> None:
            try:
                Base.metadata.create_all(bind=engine)

                with self._lock:
                    if self._state.stop_requested:
                        return

                cmd = [
                    sys.executable,
                    os.path.join(
                        os.path.dirname(os.path.dirname(__file__)),
                        "..",
                        "..",
                        "jobs",
                        "sec_api_ingest.py",
                    ),
                ]

                if form_types:
                    cmd.extend(["--form-types", str(form_types)])
                if limit is not None:
                    cmd.extend(["--limit", str(int(limit))])
                if workers is not None:
                    cmd.extend(["--workers", str(int(workers))])

                cmd = [os.path.normpath(p) for p in cmd]

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                with self._lock:
                    self._proc = proc

                rc = proc.wait()
                if rc != 0 and rc is not None:
                    with self._lock:
                        self._state.error = (
                            f"sec_api_ingest exited with code {rc}. "
                            "See logs for details."
                        )
            except Exception:
                with self._lock:
                    self._state.error = traceback.format_exc()
            finally:
                with self._lock:
                    proc = self._proc
                if proc is not None and proc.poll() is None:
                    try:
                        proc.kill()
                    except Exception:
                        pass

                with self._lock:
                    self._proc = None
                    self._state.running = False
                    self._state.ended_at = time.time()

        t = threading.Thread(target=_runner, name="sec_api_ingest", daemon=True)
        t.start()
        return True


# Module-level singletons (same effective semantics as prior global dicts/locks in routes.py)
populate_daily_values_job = PopulateDailyValuesJob()
recreate_sqlite_db_job = RecreateSqliteDbJob()
sec_api_ingest_job = SecApiIngestJob()
