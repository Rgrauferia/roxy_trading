"""Scanner service using APScheduler for more robust scheduling.

This file is an alternative runner to `scanner_service.py`. It uses
`APScheduler` to schedule the `app.main` scan job and supports graceful
shutdown. Install with `pip install apscheduler`.
"""
from __future__ import annotations

import os
import signal
import sys
from logging_config import get_logger
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from app import main as run_scan

logger = get_logger("aps_scanner_service")


def job():
    logger.info("APScheduler: running scan job")
    try:
        run_scan()
    except Exception:
        logger.exception("Scheduled scan failed")


def main():
    interval_min = int(os.environ.get("SCAN_INTERVAL_MIN", "5"))
    executors = {"default": ThreadPoolExecutor(2)}
    sched = BackgroundScheduler(executors=executors)
    sched.add_job(job, "interval", minutes=interval_min, id="scanner_job", next_run_time=None)
    sched.start()
    logger.info("APScheduler scanner started (interval=%s minutes)", interval_min)

    def _shutdown(signum, frame):
        logger.info("Shutdown signal received (%s), stopping scheduler...", signum)
        sched.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # keep running
    try:
        signal.pause()
    except Exception:
        pass


if __name__ == "__main__":
    main()
