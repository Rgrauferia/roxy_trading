# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
import smtplib
import subprocess
import json
import hashlib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

import requests

ALERTS_DIR = Path("alerts")
ALERTS_DIR.mkdir(exist_ok=True)

LAST_SENT_FILE = ALERTS_DIR / "last_sent.txt"
NOTIFICATION_HISTORY_FILE = ALERTS_DIR / "notification_history.jsonl"
NOTIFICATION_COOLDOWN_FILE = ALERTS_DIR / "notification_cooldowns.json"

# Channels via env vars
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
GENERIC_WEBHOOK = os.getenv("WEBHOOK_URL", "")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or "587")
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1").lower() not in {"0", "false", "no"}
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM", SMTP_USERNAME)
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")
MACOS_NOTIFICATIONS = os.getenv("MACOS_NOTIFICATIONS", "").lower() in {"1", "true", "yes"}
ALERT_COOLDOWN_MINUTES = int(os.getenv("ALERT_COOLDOWN_MINUTES", "60") or "60")

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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_history(payload: dict) -> None:
    NOTIFICATION_HISTORY_FILE.parent.mkdir(exist_ok=True)
    with NOTIFICATION_HISTORY_FILE.open("a") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def _append_notification_result(result: dict) -> None:
    payload = {"ts": _now_iso(), **result}
    payload["effective_sent"] = notification_effectively_sent(payload)
    _append_history(payload)


def _read_cooldowns() -> dict:
    if not NOTIFICATION_COOLDOWN_FILE.exists():
        return {}
    try:
        data = json.loads(NOTIFICATION_COOLDOWN_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("Failed to read notification cooldowns")
        return {}


def _write_cooldowns(payload: dict) -> None:
    NOTIFICATION_COOLDOWN_FILE.parent.mkdir(exist_ok=True)
    NOTIFICATION_COOLDOWN_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True))


def notification_cooldown_key(alert: str) -> str:
    parts = str(alert or "").split()
    if len(parts) >= 2:
        return f"{parts[0].upper()}:{parts[1].upper()}"
    return hashlib.sha256(str(alert or "").encode("utf-8")).hexdigest()[:16]


def filter_alerts_by_cooldown(alerts: Iterable[str], *, cooldown_minutes: int | None = None) -> tuple[list[str], list[str]]:
    cooldown_minutes = ALERT_COOLDOWN_MINUTES if cooldown_minutes is None else int(cooldown_minutes)
    if cooldown_minutes <= 0:
        return list(alerts or []), []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=cooldown_minutes)
    cooldowns = _read_cooldowns()
    active_cooldowns: dict[str, str] = {}
    for key, value in cooldowns.items():
        try:
            seen_at = datetime.fromisoformat(str(value))
        except ValueError:
            continue
        if seen_at > cutoff:
            active_cooldowns[key] = str(value)
    cooldowns = active_cooldowns
    sendable: list[str] = []
    skipped: list[str] = []
    for alert in alerts or []:
        key = notification_cooldown_key(alert)
        last_raw = cooldowns.get(key)
        last_seen = None
        if last_raw:
            try:
                last_seen = datetime.fromisoformat(str(last_raw))
            except ValueError:
                last_seen = None
        if last_seen is not None and last_seen > cutoff:
            skipped.append(alert)
            continue
        sendable.append(alert)
        cooldowns[key] = now.isoformat()
    _write_cooldowns(cooldowns)
    return sendable, skipped


def _read_notification_history_rows(limit: int = 50) -> tuple[list[dict], int]:
    if not NOTIFICATION_HISTORY_FILE.exists():
        return [], 0
    rows: list[dict] = []
    malformed = 0
    try:
        for line in NOTIFICATION_HISTORY_FILE.read_text().splitlines()[-limit:]:
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
            else:
                malformed += 1
    except Exception:
        logger.exception("Failed to read notification history")
        return [], 0
    return rows, malformed


def read_notification_history(limit: int = 50) -> list[dict]:
    rows, _malformed = _read_notification_history_rows(limit=limit)
    return rows


def notification_effectively_sent(row: dict) -> bool:
    if "effective_sent" in row:
        return bool(row.get("effective_sent"))
    if not bool(row.get("sent")):
        return False
    channels = row.get("channels") or []
    return bool(channels)


def parse_notification_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def notification_history_summary(limit: int = 50, *, now: datetime | None = None) -> dict:
    rows, malformed_recent_lines = _read_notification_history_rows(limit=limit)
    reason_counts: dict[str, int] = {}
    sent_count = 0
    cooldown_skipped = 0
    local_recorded_count = 0
    for row in rows:
        reason = str(row.get("reason") or "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if notification_effectively_sent(row):
            sent_count += 1
        if reason == "recorded_local" or (not notification_effectively_sent(row) and not (row.get("channels") or [])):
            local_recorded_count += 1
        try:
            cooldown_skipped += int(row.get("cooldown_skipped") or 0)
        except (TypeError, ValueError):
            pass
    last = rows[-1] if rows else {}
    last_ts = str(last.get("ts") or "") if last else ""
    last_dt = parse_notification_timestamp(last_ts)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    last_age_minutes = round(max(0.0, (current - last_dt).total_seconds() / 60.0), 1) if last_dt is not None else None
    channels = configured_channels()
    return {
        "sample_size": len(rows),
        "malformed_recent_lines": malformed_recent_lines,
        "sent_count": sent_count,
        "suppressed_count": len(rows) - sent_count,
        "local_recorded_count": local_recorded_count,
        "cooldown_skipped": cooldown_skipped,
        "reason_counts": dict(sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))),
        "last_reason": str(last.get("reason") or "-") if last else "-",
        "last_sent": notification_effectively_sent(last) if last else False,
        "last_effective_sent": notification_effectively_sent(last) if last else False,
        "last_ts": last_ts,
        "last_age_minutes": last_age_minutes,
        "last_channels": list(last.get("channels") or []) if last else [],
        "configured_channels": channels,
        "channel_count": len(channels),
        "delivery_mode": "external" if channels else "local_file",
    }


def _safe_post(url: str, json: dict, timeout: int = 10) -> None:
    try:
        requests.post(url, json=json, timeout=timeout)
    except Exception:
        logger.exception("Failed to POST to %s", url)


def send_slack(msg: str) -> None:
    if not SLACK_WEBHOOK:
        logger.debug("Slack not configured; skipping")
        return
    payload = {"text": msg}
    _safe_post(SLACK_WEBHOOK, payload)


def send_discord(msg: str) -> None:
    if not DISCORD_WEBHOOK:
        logger.debug("Discord not configured; skipping")
        return
    payload = {"content": msg[:1900]}
    _safe_post(DISCORD_WEBHOOK, payload)


def send_webhook(msg: str) -> None:
    if not GENERIC_WEBHOOK:
        logger.debug("Generic webhook not configured; skipping")
        return
    payload = {"message": msg}
    _safe_post(GENERIC_WEBHOOK, payload)


def send_email(msg: str) -> None:
    if not (SMTP_HOST and ALERT_EMAIL_FROM and ALERT_EMAIL_TO):
        logger.debug("Email not configured; skipping")
        return

    email = EmailMessage()
    email["Subject"] = "Roxy Trading Alert"
    email["From"] = ALERT_EMAIL_FROM
    email["To"] = ALERT_EMAIL_TO
    email.set_content(msg)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if SMTP_USE_TLS:
                server.starttls()
            if SMTP_USERNAME and SMTP_PASSWORD:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(email)
    except Exception:
        logger.exception("Failed to send email alert")


def send_macos_notification(msg: str, *, force: bool = False) -> None:
    if not force and not MACOS_NOTIFICATIONS:
        logger.debug("macOS notifications not configured; skipping")
        return
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                "on run argv",
                "-e",
                'display notification (item 1 of argv) with title "Roxy Trading Alert"',
                "-e",
                "end run",
                msg[:240],
            ],
            check=False,
            text=True,
            capture_output=True,
            timeout=10,
        )
    except Exception:
        logger.exception("Failed to send macOS notification")


def configured_channels() -> list[str]:
    channels: list[str] = []
    if SLACK_WEBHOOK:
        channels.append("slack")
    if DISCORD_WEBHOOK:
        channels.append("discord")
    if GENERIC_WEBHOOK:
        channels.append("webhook")
    if SMTP_HOST and ALERT_EMAIL_FROM and ALERT_EMAIL_TO:
        channels.append("email")
    if MACOS_NOTIFICATIONS:
        channels.append("macos")
    return channels


def notification_channel_status() -> list[dict[str, str | bool]]:
    return [
        {
            "channel": "macos",
            "configured": MACOS_NOTIFICATIONS,
            "requirements": "MACOS_NOTIFICATIONS=1",
            "notes": "Local desktop notification on this Mac.",
        },
        {
            "channel": "email",
            "configured": bool(SMTP_HOST and ALERT_EMAIL_FROM and ALERT_EMAIL_TO),
            "requirements": "SMTP_HOST, ALERT_EMAIL_TO, ALERT_EMAIL_FROM or SMTP_USERNAME",
            "notes": "Best for phone delivery if your email pushes notifications.",
        },
        {
            "channel": "discord",
            "configured": bool(DISCORD_WEBHOOK),
            "requirements": "DISCORD_WEBHOOK_URL",
            "notes": "Good phone alerts from a mobile app.",
        },
        {
            "channel": "slack",
            "configured": bool(SLACK_WEBHOOK),
            "requirements": "SLACK_WEBHOOK_URL",
            "notes": "Good if you already use Slack.",
        },
        {
            "channel": "webhook",
            "configured": bool(GENERIC_WEBHOOK),
            "requirements": "WEBHOOK_URL",
            "notes": "Advanced automation endpoint.",
        },
    ]


def notify_if_changed(alerts: Iterable[str]) -> dict:
    """Send alerts to configured channels when content changed.

    Uses a simple last-message file to avoid duplicate notifications.
    """
    alerts = list(alerts or [])
    if not alerts:
        logger.debug("No alerts to send")
        return {"sent": False, "reason": "no_alerts", "channels": configured_channels(), "message": ""}
    raw_msg = "\n".join(alerts)
    last = _read_last()
    if raw_msg == last:
        logger.debug("Alerts unchanged; skipping send")
        result = {
            "sent": False,
            "reason": "unchanged",
            "channels": configured_channels(),
            "message": raw_msg,
            "cooldown_skipped": 0,
        }
        _append_notification_result(result)
        return result
    alerts, skipped = filter_alerts_by_cooldown(alerts)
    if not alerts:
        msg = "\n".join(skipped)
        result = {
            "sent": False,
            "reason": "cooldown",
            "channels": configured_channels(),
            "message": msg,
            "cooldown_skipped": len(skipped),
        }
        _append_notification_result(result)
        return result
    msg = "\n".join(alerts)

    channels = configured_channels()
    header = "ROXY TRADING ALERT\n\n"
    text = header + msg
    if not channels:
        _write_last(msg)
        result = {
            "sent": False,
            "reason": "recorded_local",
            "channels": channels,
            "message": msg,
            "cooldown_skipped": len(skipped),
        }
        _append_notification_result(result)
        return result

    # send to channels (best-effort)
    send_slack(text)
    send_discord(text)
    send_webhook(text)
    send_email(text)
    send_macos_notification(text)

    _write_last(msg)
    result = {
        "sent": True,
        "reason": "changed",
        "channels": channels,
        "message": msg,
        "cooldown_skipped": len(skipped),
    }
    _append_notification_result(result)
    return result


def send_notification_message(
    message: str,
    *,
    reason: str = "message",
    header: str = "ROXY TRADING ALERT",
    force_macos: bool = False,
) -> dict:
    message = str(message or "").strip()
    if not message:
        result = {"sent": False, "reason": "empty", "channels": configured_channels(), "message": ""}
        _append_notification_result(result)
        return result

    channels = configured_channels()
    text = f"{header}\n\n{message}" if header else message
    delivered_channels = list(channels)
    if force_macos and "macos" not in delivered_channels:
        delivered_channels.append("macos")
    if not delivered_channels:
        result = {"sent": False, "reason": "recorded_local", "channels": [], "message": message}
        _append_notification_result(result)
        return result
    send_slack(text)
    send_discord(text)
    send_webhook(text)
    send_email(text)
    send_macos_notification(text, force=force_macos)
    result = {"sent": True, "reason": reason, "channels": delivered_channels, "message": message}
    _append_notification_result(result)
    return result


def send_test_macos_notification() -> dict:
    message = "Roxy test alert. Mac notifications are working."
    send_macos_notification(message, force=True)
    result = {"sent": True, "reason": "test_macos", "channels": ["macos"], "message": message}
    _append_notification_result(result)
    return result
