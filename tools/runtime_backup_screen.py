from __future__ import annotations

import argparse
import json
import os
import signal
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = BASE_DIR / "tools"
LOG_DIR = BASE_DIR / "logs"
DEFAULT_SESSION_NAME = "roxy_runtime_backup"
DEFAULT_HEARTBEAT_PATH = BASE_DIR / "alerts" / "runtime_backup_daemon_heartbeat.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_utc_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def pid_is_running(pid: Any) -> bool:
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False
    if pid_int <= 0:
        return False
    try:
        os.kill(pid_int, 0)
    except OSError:
        return False
    return True


def run_command(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"{args[0]} failed"
        raise RuntimeError(message)
    return result


def screen_list() -> str:
    result = run_command(["screen", "-ls"])
    return f"{result.stdout}\n{result.stderr}"


def screen_session_exists(session_name: str = DEFAULT_SESSION_NAME) -> bool:
    listing = screen_list()
    return f".{session_name}" in listing or f"\t{session_name}" in listing


def runtime_backup_daemon_pids() -> list[int]:
    """Find daemon processes even when GNU screen lost its session socket."""
    result = run_command(["ps", "-axo", "pid=,command="])
    if result.returncode != 0:
        return []
    script = str(TOOLS_DIR / "runtime_backup_daemon.py")
    pids: list[int] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if script not in line:
            continue
        parts = line.split(maxsplit=2)
        if len(parts) < 3:
            continue
        raw_pid, executable = parts[0], parts[1]
        if not Path(executable).name.casefold().startswith("python"):
            continue
        try:
            pid = int(raw_pid)
        except (TypeError, ValueError):
            continue
        if pid > 0 and pid != os.getpid():
            pids.append(pid)
    return sorted(set(pids))


def python_path() -> Path:
    venv_python = BASE_DIR / ".venv" / "bin" / "python"
    if venv_python.exists():
        return venv_python
    return Path("python3")


def build_daemon_command(
    *,
    interval_hours: float = 24.0,
    poll_seconds: float = 300.0,
    run_at_start: bool = True,
) -> str:
    LOG_DIR.mkdir(exist_ok=True)
    args: list[str | Path] = [
        python_path(),
        "-u",
        TOOLS_DIR / "runtime_backup_daemon.py",
        "--interval-hours",
        str(float(interval_hours)),
        "--poll-seconds",
        str(float(poll_seconds)),
    ]
    if not run_at_start:
        args.append("--no-run-at-start")
    command = " ".join(shlex.quote(str(arg)) for arg in args)
    return (
        f"cd {shlex.quote(str(BASE_DIR))} "
        f"&& exec {command} "
        f">> {shlex.quote(str(LOG_DIR / 'runtime_backup_daemon.out'))} "
        f"2>> {shlex.quote(str(LOG_DIR / 'runtime_backup_daemon.err'))}"
    )


def status(
    *,
    session_name: str = DEFAULT_SESSION_NAME,
    heartbeat_path: Path = DEFAULT_HEARTBEAT_PATH,
    stale_minutes: float = 15.0,
) -> dict[str, Any]:
    heartbeat = read_json(heartbeat_path)
    generated_at = parse_utc_datetime(heartbeat.get("generated_at")) if heartbeat else None
    age_minutes = None
    if generated_at is not None:
        age_minutes = max(0.0, (utc_now() - generated_at).total_seconds() / 60.0)
    pid = heartbeat.get("pid") if heartbeat else None
    session_exists = screen_session_exists(session_name)
    pid_running = pid_is_running(pid)
    process_pids = runtime_backup_daemon_pids()
    process_count = len(process_pids)
    fresh = age_minutes is not None and age_minutes <= stale_minutes
    daemon_status = str(heartbeat.get("status") or "").upper()
    backup_status = str(heartbeat.get("last_backup_status") or "").upper()
    running = bool(pid_running and fresh and daemon_status in {"RUNNING", "DEGRADED"})
    healthy = bool(running and backup_status in {"OK", "DRY_RUN"})
    return {
        "session_name": session_name,
        "session_exists": session_exists,
        "heartbeat_path": str(heartbeat_path),
        "heartbeat_exists": bool(heartbeat),
        "heartbeat_age_minutes": age_minutes,
        "pid": pid,
        "pid_running": pid_running,
        "process_pids": process_pids,
        "process_count": process_count,
        "daemon_status": daemon_status,
        "last_backup_status": backup_status,
        "last_backup_at": heartbeat.get("last_backup_at") if heartbeat else None,
        "last_archive_path": heartbeat.get("last_archive_path") if heartbeat else None,
        "next_backup_at": heartbeat.get("next_backup_at") if heartbeat else None,
        "running": running,
        "healthy": healthy,
    }


def stop(session_name: str = DEFAULT_SESSION_NAME) -> None:
    if screen_session_exists(session_name):
        run_command(["screen", "-S", session_name, "-X", "quit"])
    pids = runtime_backup_daemon_pids()
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            continue
    deadline = time.time() + 3.0
    while time.time() < deadline and any(pid_is_running(pid) for pid in pids):
        time.sleep(0.1)


def start(
    *,
    session_name: str = DEFAULT_SESSION_NAME,
    interval_hours: float = 24.0,
    poll_seconds: float = 300.0,
    run_at_start: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    if force:
        stop(session_name)
        time.sleep(0.5)
    current = status(session_name=session_name)
    if current.get("running"):
        return {"action": "already_running", "status": current}
    command = build_daemon_command(interval_hours=interval_hours, poll_seconds=poll_seconds, run_at_start=run_at_start)
    run_command(["screen", "-dmS", session_name, "zsh", "-lc", command], check=True)
    time.sleep(1.0)
    return {"action": "started", "status": status(session_name=session_name), "command": command}


def ensure(
    *,
    session_name: str = DEFAULT_SESSION_NAME,
    interval_hours: float = 24.0,
    poll_seconds: float = 300.0,
    stale_minutes: float = 15.0,
) -> dict[str, Any]:
    current = status(session_name=session_name, stale_minutes=stale_minutes)
    if current.get("healthy") and int(current.get("process_count") or 0) <= 1:
        return {"action": "healthy", "status": current}
    duplicate_count = int(current.get("process_count") or 0)
    if current.get("session_exists") or duplicate_count:
        stop(session_name)
        time.sleep(0.5)
    started = start(
        session_name=session_name,
        interval_hours=interval_hours,
        poll_seconds=poll_seconds,
        run_at_start=duplicate_count <= 1,
        force=False,
    )
    action = "deduplicated" if duplicate_count > 1 else "restarted"
    return {"action": action, "before": current, "status": started.get("status"), "command": started.get("command")}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Control the runtime backup screen daemon.")
    parser.add_argument("command", choices=["status", "start", "stop", "ensure"])
    parser.add_argument("--session-name", default=DEFAULT_SESSION_NAME)
    parser.add_argument("--interval-hours", type=float, default=24.0)
    parser.add_argument("--poll-seconds", type=float, default=300.0)
    parser.add_argument("--stale-minutes", type=float, default=15.0)
    parser.add_argument("--no-run-at-start", dest="run_at_start", action="store_false")
    parser.add_argument("--force", action="store_true")
    parser.set_defaults(run_at_start=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "status":
        result = status(session_name=args.session_name, stale_minutes=args.stale_minutes)
    elif args.command == "start":
        result = start(
            session_name=args.session_name,
            interval_hours=args.interval_hours,
            poll_seconds=args.poll_seconds,
            run_at_start=args.run_at_start,
            force=args.force,
        )
    elif args.command == "stop":
        stop(args.session_name)
        result = {"action": "stopped", "status": status(session_name=args.session_name)}
    else:
        result = ensure(
            session_name=args.session_name,
            interval_hours=args.interval_hours,
            poll_seconds=args.poll_seconds,
            stale_minutes=args.stale_minutes,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
