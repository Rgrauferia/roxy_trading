from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from runtime_backup import DEFAULT_TARGET_DIR, create_runtime_backup, json_safe
except ImportError:
    from tools.runtime_backup import DEFAULT_TARGET_DIR, create_runtime_backup, json_safe


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_HEARTBEAT_PATH = BASE_DIR / "alerts" / "runtime_backup_daemon_heartbeat.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def write_heartbeat(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True))


def heartbeat_payload(
    *,
    status: str,
    interval_hours: float,
    poll_seconds: float,
    last_backup: dict[str, Any] | None,
    next_backup_at: datetime | None,
    message: str = "",
) -> dict[str, Any]:
    return {
        "generated_at": utc_now().isoformat(),
        "status": status,
        "pid": os.getpid(),
        "interval_hours": interval_hours,
        "poll_seconds": poll_seconds,
        "target_dir": str(DEFAULT_TARGET_DIR),
        "last_backup_status": (last_backup or {}).get("status"),
        "last_backup_at": (last_backup or {}).get("generated_at"),
        "last_archive_path": (last_backup or {}).get("archive_path"),
        "next_backup_at": next_backup_at.isoformat() if next_backup_at else None,
        "message": message,
    }


def run_backup_safely() -> tuple[dict[str, Any] | None, str]:
    try:
        return create_runtime_backup(), ""
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def run_daemon(
    *,
    heartbeat_path: Path = DEFAULT_HEARTBEAT_PATH,
    interval_hours: float = 24.0,
    poll_seconds: float = 300.0,
    run_at_start: bool = True,
    once: bool = False,
) -> int:
    last_backup: dict[str, Any] | None = None
    next_backup_at = utc_now() if run_at_start else utc_now() + timedelta(hours=interval_hours)
    write_heartbeat(
        heartbeat_path,
        heartbeat_payload(
            status="RUNNING",
            interval_hours=interval_hours,
            poll_seconds=poll_seconds,
            last_backup=last_backup,
            next_backup_at=next_backup_at,
            message="daemon started",
        ),
    )

    while True:
        current = utc_now()
        if next_backup_at is None or current >= next_backup_at:
            result, error = run_backup_safely()
            if result:
                last_backup = result
                next_backup_at = current + timedelta(hours=interval_hours)
                status = "RUNNING"
                message = "backup ok"
            else:
                next_backup_at = current + timedelta(minutes=15)
                status = "DEGRADED"
                message = error
            write_heartbeat(
                heartbeat_path,
                heartbeat_payload(
                    status=status,
                    interval_hours=interval_hours,
                    poll_seconds=poll_seconds,
                    last_backup=last_backup,
                    next_backup_at=next_backup_at,
                    message=message,
                ),
            )
            if once:
                return 0 if result else 1
        else:
            write_heartbeat(
                heartbeat_path,
                heartbeat_payload(
                    status="RUNNING",
                    interval_hours=interval_hours,
                    poll_seconds=poll_seconds,
                    last_backup=last_backup,
                    next_backup_at=next_backup_at,
                    message="waiting",
                ),
            )
            if once:
                return 0
        time.sleep(max(1.0, float(poll_seconds)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Keep runtime backups running from the current user session.")
    parser.add_argument("--heartbeat-path", default=str(DEFAULT_HEARTBEAT_PATH))
    parser.add_argument("--interval-hours", type=float, default=24.0)
    parser.add_argument("--poll-seconds", type=float, default=300.0)
    parser.add_argument("--no-run-at-start", dest="run_at_start", action="store_false")
    parser.add_argument("--once", action="store_true")
    parser.set_defaults(run_at_start=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raise SystemExit(
        run_daemon(
            heartbeat_path=Path(args.heartbeat_path),
            interval_hours=args.interval_hours,
            poll_seconds=args.poll_seconds,
            run_at_start=args.run_at_start,
            once=args.once,
        )
    )


if __name__ == "__main__":
    main()
