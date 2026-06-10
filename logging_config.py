"""Logging helpers for the project.

Provides an audit logger with rotation for role changes.
"""
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def get_audit_logger(log_path: str | None = None) -> logging.Logger:
    name = "roxy.role_audit"
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    if log_path is None:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = str(log_dir / "role_audit.log")

    logger.setLevel(logging.INFO)
    # rotate daily, keep 14 days
    handler = TimedRotatingFileHandler(log_path, when="D", interval=1, backupCount=14, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s\t%(name)s\t%(message)s")
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    # also avoid propagation to root
    logger.propagate = False
    return logger
import logging


def configure_logging(level=logging.INFO):
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")


def get_logger(name: str):
    configure_logging()
    return logging.getLogger(name)
