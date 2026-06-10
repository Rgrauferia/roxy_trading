"""Simple process manager to start/stop the account snapshot service locally.

Writes a PID file to `run/snapshot.pid` and allows stopping the process.
This is intentionally simple — on production use a proper process manager.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import shutil
from pathlib import Path
from typing import Optional

RUN_DIR = Path("run")
RUN_DIR.mkdir(parents=True, exist_ok=True)
PID_FILE = RUN_DIR / "snapshot.pid"


def _python_executable() -> str:
    configured = os.environ.get("PYTHON")
    if configured and shutil.which(configured):
        return configured
    return sys.executable


def start_snapshot_service(interval: int = 5, run_once: bool = False) -> int:
    """Start the snapshot service as a background process.

    If `run_once` is True, runs the service with `--once` and returns the pid.
    """
    if PID_FILE.exists():
        raise RuntimeError(f"PID file exists: {PID_FILE}")
    cmd = [_python_executable(), "tools/account_snapshot_service.py"]
    if run_once:
        cmd.append("--once")
    else:
        cmd += ["--interval", str(interval)]

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    PID_FILE.write_text(str(p.pid))
    return p.pid


def stop_snapshot_service() -> bool:
    if not PID_FILE.exists():
        return False
    pid = int(PID_FILE.read_text())
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    PID_FILE.unlink(missing_ok=True)
    return True


def get_pid() -> Optional[int]:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text())
    except Exception:
        return None
