# -*- coding: utf-8 -*-
import logging
import os
from pathlib import Path
from typing import Iterable

import requests

ALERTS_DIR = Path("alerts")
ALERTS_DIR.mkdir(exist_ok=True)

LAST_SENT_FILE = ALERTS_DIR / "last_sent.txt"

# Channels via env vars
TELEGRAM_TOKEN = os.getenv("TG_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID", "")
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
GENERIC_WEBHOOK = os.getenv("WEBHOOK_URL", "")

try:
    from logging_config import get_logger

    logger = get_logger("notifier")
except Exception:  # pragma: no cover - fallback
    logger = logging.getLogger("notifier")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _read_last() -> str:
    if LAST_SENT_FILE.exists():
        return LAST_SENT_FILE.read_text().strip()
    return ""


def _write_last(msg: str) -> None:
    LAST_SENT_FILE.write_text(msg)


def _safe_post(url: str, json: dict, timeout: int = 10) -> None:
    try:
        requests.post(url, json=json, timeout=timeout)
    except Exception:
        logger.exception("Failed to POST to %s", url)


def send_telegram(msg: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.debug("Telegram not configured; skipping")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    _safe_post(url, payload)


def send_slack(msg: str) -> None:
    if not SLACK_WEBHOOK:
        logger.debug("Slack not configured; skipping")
        return
    payload = {"text": msg}
    _safe_post(SLACK_WEBHOOK, payload)


def send_webhook(msg: str) -> None:
    if not GENERIC_WEBHOOK:
        logger.debug("Generic webhook not configured; skipping")
        return
    payload = {"message": msg}
    _safe_post(GENERIC_WEBHOOK, payload)


def notify_if_changed(alerts: Iterable[str]) -> None:
    """Send alerts to configured channels when content changed.

    Uses a simple last-message file to avoid duplicate notifications.
    """
    alerts = list(alerts or [])
    if not alerts:
        logger.debug("No alerts to send")
        return
    msg = "\n".join(alerts)
    last = _read_last()
    if msg == last:
        logger.debug("Alerts unchanged; skipping send")
        return

    header = "🚨 *ROXY TRADING ALERT*\n\n"
    text = header + msg

    # send to channels (best-effort)
    send_telegram(text)
    send_slack(text)
    send_webhook(text)

    _write_last(msg)
