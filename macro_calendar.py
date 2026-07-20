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
SOURCE_FRESH_AFTER_HOURS = 48.0
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
    "PERSONAL INCOME",
    "PERSONAL CONSUMPTION",
    "INTERNATIONAL TRADE",
    "GOODS AND SERVICES",
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


def human_event_distance(minutes: Any) -> str:
    try:
        value = max(0.0, float(minutes))
    except (TypeError, ValueError):
        return "tiempo no disponible"
    if value < 120:
        return f"{value:.0f} min"
    hours = value / 60.0
    if hours < 72:
        return f"{hours:.1f} h"
    return f"{hours / 24.0:.1f} dias"


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
    raw_events = read_macro_events(calendar_path)
    events = []
    valid_event_times: list[datetime] = []
    fetched_times: list[datetime] = []
    source_names: set[str] = set()
    source_urls: set[str] = set()
    for row in raw_events:
        event_time = parse_event_time(row)
        if event_time is None:
            continue
        valid_event_times.append(event_time)
        source_name = safe_text(row.get("source"))
        source_url = safe_text(row.get("source_url"))
        if source_name:
            source_names.add(source_name)
        if source_url:
            source_urls.add(source_url)
        fetched_raw = safe_text(row.get("fetched_at"))
        if fetched_raw:
            try:
                fetched_at = datetime.fromisoformat(fetched_raw.replace("Z", "+00:00"))
                if fetched_at.tzinfo is None:
                    fetched_at = fetched_at.replace(tzinfo=timezone.utc)
                fetched_times.append(fetched_at.astimezone(timezone.utc))
            except ValueError:
                pass
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
        if event_time + timedelta(minutes=after) >= now_utc and event_time <= now_utc + timedelta(hours=upcoming_hours):
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
                    "source": safe_text(row.get("source")) or "Archivo configurado",
                    "source_url": safe_text(row.get("source_url")),
                    "fetched_at": fetched_raw,
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
    file_exists = calendar_path.exists()
    valid_event_count = len(valid_event_times)
    latest_event_time = max(valid_event_times).isoformat() if valid_event_times else ""
    future_event_times = [event_time for event_time in valid_event_times if event_time >= now_utc]
    next_event_time = min(future_event_times).isoformat() if future_event_times else ""
    source_fetched_at = max(fetched_times) if fetched_times else None
    source_age_hours = (
        max(0.0, (now_utc - source_fetched_at).total_seconds() / 3600.0)
        if source_fetched_at is not None
        else None
    )
    source_current = source_age_hours is not None and source_age_hours <= SOURCE_FRESH_AFTER_HOURS
    if not file_exists:
        data_status = "NOT_CONFIGURED"
        coverage = "UNKNOWN"
    elif valid_event_count == 0:
        data_status = "NO_DATA"
        coverage = "UNKNOWN"
    elif source_current or (source_fetched_at is None and (active_events or upcoming)):
        data_status = "CONNECTED"
        coverage = "ACTIVE_OR_UPCOMING" if active_events or upcoming else "LOADED_NO_EVENT_IN_WINDOW"
    else:
        data_status = "DELAYED"
        coverage = "STALE_SOURCE_CACHE"

    if active:
        label = "Macro activo"
        detail = f"{top.get('title')} activo hasta {safe_text(top.get('active_until'))}."
    elif upcoming:
        label = "Macro proximo"
        detail = f"{top.get('title')} en {human_event_distance(top.get('minutes_to_event'))}."
    elif file_exists and valid_event_count:
        if data_status == "CONNECTED":
            label = "Calendario conectado"
            detail = (
                f"Fuente vigente con {valid_event_count} evento(s); ninguno cae en la ventana de "
                f"{upcoming_hours}h. Proximo evento almacenado: {next_event_time or 'ninguno'} ."
            )
        else:
            label = "Calendario retrasado"
            age_label = f"{source_age_hours:.1f}h" if source_age_hours is not None else "desconocida"
            detail = (
                f"El cache contiene {valid_event_count} evento(s), pero su frescura es {age_label}; "
                "se conserva como dato retrasado hasta la proxima sincronizacion."
            )
    elif file_exists:
        label = "Calendario sin datos"
        detail = "El archivo existe, pero no contiene eventos macro validos; no se presenta como conectado."
    else:
        label = "Sin calendario macro"
        detail = f"No existe {calendar_path}; Roxy usara solo eventos que vengan en el scan."
    return {
        "path": str(calendar_path),
        "configured": file_exists,
        "data_status": data_status,
        "coverage": coverage,
        "raw_event_count": len(raw_events),
        "valid_event_count": valid_event_count,
        "latest_event_time": latest_event_time,
        "next_event_time": next_event_time,
        "source_fetched_at": source_fetched_at.isoformat() if source_fetched_at else "",
        "source_age_hours": round(source_age_hours, 2) if source_age_hours is not None else None,
        "source_current": source_current,
        "sources": sorted(source_names),
        "source_urls": sorted(source_urls),
        "source_count": len(source_names),
        "label": label,
        "detail": detail,
        "active": active,
        "active_events": active_events,
        "upcoming_events": upcoming[:5],
        "scheduled_events": events[:100],
        "top_event": top,
        # This flag controls calendar-event notifications only. It must never
        # be interpreted as permission to emit a market/trading signal.
        "alerts_allowed": bool(valid_event_count and data_status in {"CONNECTED", "DELAYED"}),
        "alert_scope": "CALENDAR_EVENTS_ONLY",
        "market_signal_gate": "CONTEXT_ONLY",
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
