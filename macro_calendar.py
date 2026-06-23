from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from roxy_paths import data_dir


LOCAL_TZ = ZoneInfo("America/New_York")
DEFAULT_CALENDAR_PATH = data_dir() / "macro_events.csv"
HIGH_KEYWORDS = (
    "FOMC",
    "FED",
    "POWELL",
    "RATE DECISION",
    "DOT PLOT",
    "MINUTES",
)
MEDIUM_KEYWORDS = (
    "CPI",
    "PCE",
    "NFP",
    "PAYROLL",
    "JOBS",
    "INFLATION",
    "GDP",
    "TREASURY",
    "YIELD",
)


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except Exception:
        pass
    return str(value or "").strip()


def parse_event_time(row: dict[str, Any]) -> datetime | None:
    raw = (
        safe_text(row.get("datetime"))
        or safe_text(row.get("starts_at"))
        or safe_text(row.get("timestamp"))
        or safe_text(row.get("ts"))
    )
    if not raw:
        date = safe_text(row.get("date"))
        time = safe_text(row.get("time")) or "09:30"
        raw = f"{date} {time}".strip()
    if not raw:
        return None
    raw = raw.replace("Z", "+00:00")
    for candidate in (raw, raw.replace("/", "-")):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=LOCAL_TZ)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def infer_severity(row: dict[str, Any]) -> str:
    explicit = safe_text(row.get("severity") or row.get("impact")).upper()
    if explicit in {"HIGH", "MEDIUM", "LOW"}:
        return explicit
    text = " ".join(
        safe_text(row.get(key))
        for key in ("event", "title", "name", "description", "notes", "category")
    ).upper()
    if any(keyword in text for keyword in HIGH_KEYWORDS):
        return "HIGH"
    if any(keyword in text for keyword in MEDIUM_KEYWORDS):
        return "MEDIUM"
    return "LOW"


def event_window_minutes(severity: str) -> tuple[int, int]:
    severity = safe_text(severity).upper()
    if severity == "HIGH":
        return 60, 180
    if severity == "MEDIUM":
        return 30, 90
    return 15, 45


def read_macro_events(path: str | Path | None = None) -> list[dict[str, Any]]:
    calendar_path = Path(path or DEFAULT_CALENDAR_PATH).expanduser()
    if not calendar_path.exists():
        return []
    if calendar_path.suffix.lower() == ".json":
        try:
            payload = json.loads(calendar_path.read_text())
        except Exception:
            return []
        if isinstance(payload, dict):
            payload = payload.get("events") or []
        return [item for item in payload if isinstance(item, dict)]
    try:
        with calendar_path.open(newline="") as handle:
            return list(csv.DictReader(handle))
    except Exception:
        return []


def macro_calendar_status(
    path: str | Path | None = None,
    *,
    now: datetime | None = None,
    upcoming_hours: int = 24,
) -> dict[str, Any]:
    calendar_path = Path(path or DEFAULT_CALENDAR_PATH).expanduser()
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    events = []
    for row in read_macro_events(calendar_path):
        event_time = parse_event_time(row)
        if event_time is None:
            continue
        severity = infer_severity(row)
        before, after = event_window_minutes(severity)
        title = (
            safe_text(row.get("event"))
            or safe_text(row.get("title"))
            or safe_text(row.get("name"))
            or "Evento macro"
        )
        starts = event_time - timedelta(minutes=before)
        ends = event_time + timedelta(minutes=after)
        if now_utc <= event_time + timedelta(hours=upcoming_hours):
            events.append(
                {
                    "title": title,
                    "severity": severity,
                    "event_time": event_time.isoformat(),
                    "active_from": starts.isoformat(),
                    "active_until": ends.isoformat(),
                    "active": starts <= now_utc <= ends,
                    "minutes_to_event": round((event_time - now_utc).total_seconds() / 60.0, 1),
                    "currency": safe_text(row.get("currency")) or "USD",
                    "notes": safe_text(row.get("notes") or row.get("description")),
                }
            )
    events.sort(key=lambda item: item["event_time"])
    active_events = [item for item in events if item["active"] and item["severity"] in {"HIGH", "MEDIUM"}]
    upcoming = [
        item
        for item in events
        if not item["active"] and item["severity"] in {"HIGH", "MEDIUM"} and item["minutes_to_event"] >= 0
    ]
    top = active_events[0] if active_events else (upcoming[0] if upcoming else {})
    active = bool(active_events)
    if active:
        label = "Macro activo"
        detail = f"{top.get('title')} activo hasta {safe_text(top.get('active_until'))}."
    elif upcoming:
        label = "Macro proximo"
        detail = f"{top.get('title')} en {top.get('minutes_to_event')} min."
    elif calendar_path.exists():
        label = "Sin evento macro"
        detail = "Calendario local no tiene eventos macro activos/proximos."
    else:
        label = "Sin calendario macro"
        detail = f"No existe {calendar_path}; Roxy usara solo eventos que vengan en el scan."
    return {
        "path": str(calendar_path),
        "configured": calendar_path.exists(),
        "label": label,
        "detail": detail,
        "active": active,
        "active_events": active_events,
        "upcoming_events": upcoming[:5],
        "top_event": top,
        "alerts_allowed": True,
    }


def apply_macro_context(row: dict[str, Any], context: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(context, dict) or not context.get("active"):
        return dict(row)
    item = dict(row)
    top = context.get("top_event") if isinstance(context.get("top_event"), dict) else {}
    title = safe_text(top.get("title")) or "Evento macro activo"
    item["macro_event"] = True
    item["event_risk"] = True
    item["news_event"] = title
    item["macro_context"] = safe_text(context.get("detail")) or title
    item["macro_event_severity"] = safe_text(top.get("severity")) or "HIGH"
    return item
