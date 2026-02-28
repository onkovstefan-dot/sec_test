import os
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional


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

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return self._state.as_dict()

    def request_stop(self) -> None:
        with self._lock:
            self._state.stop_requested = True

    def start(self) -> bool:
        """Start utils.populate_daily_values.main() in a daemon thread.

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

        def _runner() -> None:
            try:
                # Lazily ensure schema exists before running the job.
                from db import Base, engine

                Base.metadata.create_all(bind=engine)

                from utils import populate_daily_values

                # cooperative stop: only prevents new run from continuing at start
                with self._lock:
                    if self._state.stop_requested:
                        return

                populate_daily_values.main()
            except Exception:
                with self._lock:
                    self._state.error = traceback.format_exc()
            finally:
                with self._lock:
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
                from utils import recreate_sqlite_db

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


# Module-level singletons (same effective semantics as prior global dicts/locks in routes.py)
populate_daily_values_job = PopulateDailyValuesJob()
recreate_sqlite_db_job = RecreateSqliteDbJob()
