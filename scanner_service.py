"""Simple scheduler to run the scanner periodically.

Usage: python scanner_service.py
Configure interval (minutes) with environment variable `SCAN_INTERVAL_MIN`.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime

try:
    # prefer project logging setup when available
    from logging_config import get_logger
except Exception:  # pragma: no cover - optional
    get_logger = None

from app import main as run_scan

logger: logging.Logger
if get_logger is not None:
    logger = get_logger("scanner_service")
else:
    logger = logging.getLogger("scanner_service")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def job() -> None:
    """Run one scan iteration and catch errors."""
    ts = datetime.now().isoformat()
    logger.info("Starting scheduled scan: %s", ts)
    try:
        run_scan()
    except Exception:
        logger.exception("Scheduled scan failed")
    else:
        logger.info("Scheduled scan finished: %s", ts)


def main() -> None:
    interval_min = int(os.environ.get("SCAN_INTERVAL_MIN", "5"))
    interval_sec = max(10, interval_min * 60)
    logger.info("Scanner service starting (interval=%s minutes)", interval_min)
    # simple loop avoids adding new heavy dependencies; reliable and easy to run in Docker
    try:
        while True:
            start = time.time()
            job()
            elapsed = time.time() - start
            sleep_for = interval_sec - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
    except KeyboardInterrupt:
        logger.info("Scanner service stopped by user")


if __name__ == "__main__":
    main()
