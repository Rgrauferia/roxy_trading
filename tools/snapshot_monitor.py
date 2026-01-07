"""Monitor snapshots and alert when no recent snapshot exists.

Usage:
    python tools/snapshot_monitor.py --threshold 15

Sends notifications via `notifier.notify_if_changed()` if snapshots are stale.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta

import storage
import notifier


def check_stale(db_path: str, threshold_minutes: int = 15):
    users = [r[0] for r in storage.list_accounts(path=db_path)]
    alerts = []
    now = datetime.utcnow()
    for u in users:
        last = storage.get_last_snapshot(u, path=db_path)
        if not last:
            alerts.append(f"{u}: no snapshots recorded")
            continue
        try:
            ts = datetime.fromisoformat(last)
        except Exception:
            alerts.append(f"{u}: invalid snapshot ts {last}")
            continue
        age = now - ts
        if age > timedelta(minutes=threshold_minutes):
            alerts.append(f"{u}: last snapshot {age} ago (ts={last})")
    if alerts:
        notifier.notify_if_changed(alerts)
    return alerts


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--threshold", type=int, default=15, help="minutes after which snapshots are considered stale")
    p.add_argument("--db", default=storage.DB_PATH)
    args = p.parse_args(argv)
    alerts = check_stale(args.db, threshold_minutes=int(args.threshold))
    if alerts:
        print("Alerts:\n", "\n".join(alerts))
    else:
        print("No stale snapshots")


if __name__ == "__main__":
    raise SystemExit(main())
