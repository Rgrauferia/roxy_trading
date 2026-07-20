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

from durable_storage import atomic_write_text, exclusive_file_lock

ALERTS_DIR = Path("alerts")
ALERTS_DIR.mkdir(exist_ok=True)

LAST_SENT_FILE = ALERTS_DIR / "last_sent.txt"
NOTIFICATION_HISTORY_FILE = ALERTS_DIR / "notification_history.jsonl"
NOTIFICATION_COOLDOWN_FILE = ALERTS_DIR / "notification_cooldowns.json"
NOTIFICATION_HISTORY_MAX_LINES = 500
NOTIFICATION_HISTORY_MAX_BYTES = 1_000_000
NOTIFICATION_HISTORY_MIN_LINES = 120

# Channels via env vars
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
GENERIC_WEBHOOK = os.getenv("WEBHOOK_URL", "")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")
PUSHOVER_APP_TOKEN = os.getenv("PUSHOVER_APP_TOKEN", "")
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
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


def _history_repeat_count(row: dict) -> int:
    try:
        return max(1, int(row.get("repeat_count") or 1))
    except (TypeError, ValueError):
        return 1


def _history_compaction_key(row: dict) -> tuple | None:
    if notification_effectively_sent(row):
        return None
    if row.get("channels") or []:
        return None
    return (
        str(row.get("reason") or ""),
        str(row.get("incident_key") or ""),
        str(row.get("message") or ""),
        bool(row.get("sent")),
        bool(row.get("effective_sent")),
    )


def _merge_history_repeat(previous: dict, current: dict) -> dict:
    merged = dict(previous)
    previous_count = _history_repeat_count(previous)
    current_count = _history_repeat_count(current)
    merged["repeat_count"] = previous_count + current_count
    merged["last_ts"] = str(
        current.get("last_ts")
        or current.get("ts")
        or previous.get("last_ts")
        or previous.get("ts")
        or ""
    )
    if current.get("last_message") or current.get("message"):
        merged["last_message"] = str(current.get("last_message") or current.get("message") or "")
    try:
        merged["cooldown_skipped"] = int(previous.get("cooldown_skipped") or 0) + int(current.get("cooldown_skipped") or 0)
    except (TypeError, ValueError):
        pass
    return merged


def _compact_history_items(items: list[dict | str]) -> list[dict | str]:
    compacted: list[dict | str] = []
    for item in items:
        if not isinstance(item, dict):
            compacted.append(item)
            continue
        if compacted and isinstance(compacted[-1], dict):
            previous = compacted[-1]
            previous_key = _history_compaction_key(previous)
            current_key = _history_compaction_key(item)
            if previous_key is not None and previous_key == current_key:
                compacted[-1] = _merge_history_repeat(previous, item)
                continue
        compacted.append(item)
    return compacted


def _serialize_history_item(item: dict | str) -> str:
    if isinstance(item, dict):
        return json.dumps(item, sort_keys=True)
    return item


def _append_history_unlocked(
    payload: dict,
    *,
    max_lines: int = NOTIFICATION_HISTORY_MAX_LINES,
    max_bytes: int | None = NOTIFICATION_HISTORY_MAX_BYTES,
    min_lines: int = NOTIFICATION_HISTORY_MIN_LINES,
) -> None:
    NOTIFICATION_HISTORY_FILE.parent.mkdir(exist_ok=True)
    max_lines = max(1, int(max_lines))
    max_bytes = max(0, int(max_bytes)) if max_bytes is not None else 0
    min_lines = max(1, min(int(min_lines), max_lines))
    existing = NOTIFICATION_HISTORY_FILE.read_text(errors="replace").splitlines() if NOTIFICATION_HISTORY_FILE.exists() else []
    items: list[dict | str] = []
    for line in existing:
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            items.append(line)
            continue
        items.append(parsed if isinstance(parsed, dict) else line)
    items.append(dict(payload))
    lines = [_serialize_history_item(item) for item in _compact_history_items(items)]
    lines = lines[-max_lines:]
    if max_bytes:
        kept: list[str] = []
        total_bytes = 1
        for item in reversed(lines):
            item_bytes = len(item.encode()) + 1
            if kept and len(kept) >= min_lines and total_bytes + item_bytes > max_bytes:
                break
            kept.append(item)
            total_bytes += item_bytes
        lines = list(reversed(kept))
    atomic_write_text("\n".join(lines) + "\n", NOTIFICATION_HISTORY_FILE)


def _append_history(
    payload: dict,
    *,
    max_lines: int = NOTIFICATION_HISTORY_MAX_LINES,
    max_bytes: int | None = NOTIFICATION_HISTORY_MAX_BYTES,
    min_lines: int = NOTIFICATION_HISTORY_MIN_LINES,
) -> None:
    with exclusive_file_lock(NOTIFICATION_HISTORY_FILE):
        _append_history_unlocked(
            payload,
            max_lines=max_lines,
            max_bytes=max_bytes,
            min_lines=min_lines,
        )


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
    atomic_write_text(json.dumps(payload, indent=2, sort_keys=True), NOTIFICATION_COOLDOWN_FILE)


def notification_cooldown_key(alert: str) -> str:
    parts = str(alert or "").split()
    if len(parts) >= 2:
        return f"{parts[0].upper()}:{parts[1].upper()}"
    return hashlib.sha256(str(alert or "").encode("utf-8")).hexdigest()[:16]


def _filter_alerts_by_cooldown_unlocked(
    alerts: Iterable[str], *, cooldown_minutes: int | None = None
) -> tuple[list[str], list[str]]:
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


def filter_alerts_by_cooldown(
    alerts: Iterable[str], *, cooldown_minutes: int | None = None
) -> tuple[list[str], list[str]]:
    with exclusive_file_lock(NOTIFICATION_COOLDOWN_FILE):
        return _filter_alerts_by_cooldown_unlocked(alerts, cooldown_minutes=cooldown_minutes)


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
    history_size_bytes = NOTIFICATION_HISTORY_FILE.stat().st_size if NOTIFICATION_HISTORY_FILE.exists() else 0
    history_line_count = (
        len([line for line in NOTIFICATION_HISTORY_FILE.read_text(errors="replace").splitlines() if line.strip()])
        if NOTIFICATION_HISTORY_FILE.exists()
        else 0
    )
    reason_counts: dict[str, int] = {}
    sent_count = 0
    cooldown_skipped = 0
    local_recorded_count = 0
    health_event_count = 0
    health_incident_key_missing_count = 0
    sample_event_count = 0
    last_health_event: dict | None = None
    for row in rows:
        repeat_count = _history_repeat_count(row)
        sample_event_count += repeat_count
        reason = str(row.get("reason") or "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + repeat_count
        if notification_effectively_sent(row):
            sent_count += repeat_count
        if reason == "recorded_local" or (not notification_effectively_sent(row) and not (row.get("channels") or [])):
            local_recorded_count += repeat_count
        try:
            cooldown_skipped += int(row.get("cooldown_skipped") or 0)
        except (TypeError, ValueError):
            pass
        message = str(row.get("message") or "")
        is_health_event = reason == "health_watchdog" or message.startswith("ROXY HEALTH ")
        if is_health_event:
            health_event_count += repeat_count
            last_health_event = row
            if not str(row.get("incident_key") or ""):
                health_incident_key_missing_count += repeat_count
    last = rows[-1] if rows else {}
    last_health_incident_key = str((last_health_event or {}).get("incident_key") or "")
    latest_health_incident_key_missing = bool(last_health_event and not last_health_incident_key)
    last_ts = str(last.get("ts") or "") if last else ""
    last_dt = parse_notification_timestamp(last_ts)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    last_age_minutes = round(max(0.0, (current - last_dt).total_seconds() / 60.0), 1) if last_dt is not None else None
    channels = configured_channels()
    return {
        "sample_size": len(rows),
        "sample_event_count": sample_event_count,
        "line_count": history_line_count,
        "size_bytes": history_size_bytes,
        "max_bytes": NOTIFICATION_HISTORY_MAX_BYTES,
        "max_lines": NOTIFICATION_HISTORY_MAX_LINES,
        "min_lines": NOTIFICATION_HISTORY_MIN_LINES,
        "malformed_recent_lines": malformed_recent_lines,
        "sent_count": sent_count,
        "suppressed_count": sample_event_count - sent_count,
        "local_recorded_count": local_recorded_count,
        "cooldown_skipped": cooldown_skipped,
        "reason_counts": dict(sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))),
        "last_reason": str(last.get("reason") or "-") if last else "-",
        "last_sent": notification_effectively_sent(last) if last else False,
        "last_effective_sent": notification_effectively_sent(last) if last else False,
        "last_ts": last_ts,
        "last_age_minutes": last_age_minutes,
        "last_channels": list(last.get("channels") or []) if last else [],
        "last_incident_key": str(last.get("incident_key") or "") if last else "",
        "health_event_count": health_event_count,
        "health_incident_key_missing_count": health_incident_key_missing_count,
        "latest_health_incident_key_missing": latest_health_incident_key_missing,
        "last_health_incident_key": last_health_incident_key,
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


def send_webhook(msg: str, *, metadata: dict | None = None) -> None:
    if not GENERIC_WEBHOOK:
        logger.debug("Generic webhook not configured; skipping")
        return
    payload = {"message": msg, "source": "roxy_trading", "metadata": dict(metadata or {})}
    _safe_post(GENERIC_WEBHOOK, payload)


def send_pushover(msg: str) -> None:
    if not (PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY):
        logger.debug("Pushover not configured; skipping")
        return
    payload = {
        "token": PUSHOVER_APP_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "title": "Roxy Trading Alert",
        "message": msg[:1024],
    }
    _safe_post("https://api.pushover.net/1/messages.json", payload)


def send_telegram(msg: str) -> None:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        logger.debug("Telegram not configured; skipping")
        return
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg[:3900],
        "disable_web_page_preview": True,
    }
    _safe_post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", payload)


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
    if PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY:
        channels.append("pushover")
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        channels.append("telegram")
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
            "channel": "pushover",
            "configured": bool(PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY),
            "requirements": "PUSHOVER_APP_TOKEN, PUSHOVER_USER_KEY",
            "notes": "Direct push alerts to phone through Pushover.",
        },
        {
            "channel": "telegram",
            "configured": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
            "requirements": "TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID",
            "notes": "Direct phone alerts through Telegram bot messages.",
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
    send_pushover(text)
    send_telegram(text)
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
    metadata: dict | None = None,
) -> dict:
    message = str(message or "").strip()
    extra = dict(metadata or {})
    if not message:
        result = {"sent": False, "reason": "empty", "channels": configured_channels(), "message": "", **extra}
        _append_notification_result(result)
        return result

    channels = configured_channels()
    text = f"{header}\n\n{message}" if header else message
    delivered_channels = list(channels)
    if force_macos and "macos" not in delivered_channels:
        delivered_channels.append("macos")
    if not delivered_channels:
        result = {"sent": False, "reason": "recorded_local", "channels": [], "message": message, **extra}
        _append_notification_result(result)
        return result
    send_slack(text)
    send_discord(text)
    send_pushover(text)
    send_telegram(text)
    send_webhook(text, metadata={"reason": reason, "header": header, **extra})
    send_email(text)
    send_macos_notification(text, force=force_macos)
    result = {"sent": True, "reason": reason, "channels": delivered_channels, "message": message, **extra}
    _append_notification_result(result)
    return result


def send_test_macos_notification() -> dict:
    message = "Roxy test alert. Mac notifications are working."
    send_macos_notification(message, force=True)
    result = {"sent": True, "reason": "test_macos", "channels": ["macos"], "message": message}
    _append_notification_result(result)
    return result
