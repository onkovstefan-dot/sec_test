#!/usr/bin/env python3
"""Development restart watcher.

Use with servers started via `python3 app.py` (no Flask reloader).

Runs a tiny supervisor loop:
- starts the app as a subprocess
- watches a restart flag file (tmp/restart_requested)
- when the flag updates, restarts the subprocess

This keeps the "restart" responsibility outside the Flask process.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    root = _repo_root()
    restart_flag = os.path.join(root, "tmp", "restart_requested")

    python = sys.executable or "python3"
    cmd = [python, os.path.join(root, "app.py")]

    last_mtime = 0.0
    proc: subprocess.Popen | None = None

    def start_proc() -> subprocess.Popen:
        os.makedirs(os.path.join(root, "tmp"), exist_ok=True)
        return subprocess.Popen(cmd, cwd=root)

    def stop_proc(p: subprocess.Popen) -> None:
        if p.poll() is not None:
            return
        try:
            p.send_signal(signal.SIGTERM)
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass

    while True:
        if proc is None or proc.poll() is not None:
            proc = start_proc()

        try:
            st = os.stat(restart_flag)
            mtime = st.st_mtime
        except FileNotFoundError:
            mtime = 0.0

        if mtime and mtime > last_mtime:
            last_mtime = mtime
            print("[restart_watcher] restart requested: restarting app...")
            stop_proc(proc)
            proc = start_proc()

        time.sleep(0.5)


if __name__ == "__main__":
    raise SystemExit(main())
