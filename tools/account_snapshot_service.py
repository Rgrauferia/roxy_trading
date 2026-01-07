"""Periodic account snapshot service.

Runs `storage.snapshot_account_point(user)` for all users at a configured interval.

Usage:
    python tools/account_snapshot_service.py --once
    python tools/account_snapshot_service.py --interval 5

Requires `apscheduler` (BlockingScheduler). The script will create missing DB entries
via `storage.create_account_if_missing()` if needed.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from typing import List

from apscheduler.schedulers.blocking import BlockingScheduler

import storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("snapshot_service")


def list_users(db_path: str) -> List[str]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT user FROM sim_accounts")
        rows = cur.fetchall()
    except Exception:
        rows = []
    conn.close()
    return [r[0] for r in rows]


def snapshot_all(db_path: str) -> None:
    users = list_users(db_path)
    if not users:
        log.info("No users found; nothing to snapshot")
        return
    for u in users:
        try:
            val = storage.snapshot_account_point(u, path=db_path)
            log.info("Snapshot for %s -> %.2f", u, float(val))
        except Exception as e:
            log.exception("Failed snapshot for %s: %s", u, e)


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--interval", type=int, default=5, help="Minutes between snapshots")
    p.add_argument("--once", action="store_true", help="Run one snapshot and exit")
    p.add_argument("--db", default=storage.DB_PATH, help="Path to SQLite DB")
    args = p.parse_args(argv)

    # ensure DB initialized
    storage.init_db(args.db)

    if args.once:
        log.info("Running single snapshot against %s", args.db)
        # ensure accounts present by listing or creating a default if empty
        users = list_users(args.db)
        if not users:
            log.info("No accounts found; creating a default 'anon' account")
            storage.create_account_if_missing("anon", path=args.db)
            users = list_users(args.db)
        snapshot_all(args.db)
        return 0

    sched = BlockingScheduler()
    sched.add_job(lambda: snapshot_all(args.db), "interval", minutes=args.interval, next_run_time=None)

    try:
        log.info("Starting snapshot service (interval=%s minutes) against %s", args.interval, args.db)
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Shutdown requested")
        return 0
    except Exception as e:
        log.exception("Scheduler error: %s", e)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
