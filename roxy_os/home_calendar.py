from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


CALENDAR_STORE_VERSION = 1
CALENDAR_CATEGORIES = {"PERSONAL", "WORK", "FAMILY", "SCHOOL", "APPOINTMENTS", "HOME"}
RECURRENCE_TYPES = {"NONE", "DAILY", "WEEKLY", "WEEKDAYS"}
DEFAULT_TIMEZONE = "America/New_York"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _timezone(value: Any) -> ZoneInfo:
    try:
        return ZoneInfo(str(value or DEFAULT_TIMEZONE))
    except (KeyError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def _aware(value: Any, timezone_name: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value or ""))
    zone = _timezone(timezone_name)
    if result.tzinfo is None:
        result = result.replace(tzinfo=zone)
    return result.astimezone(zone)


def _ics_escape(value: Any) -> str:
    return str(value or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def _ics_stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class HomeCalendarStore:
    """Private, durable calendar and confirmation drafts for each Home member."""

    def __init__(self, path: str | Path = "data/roxy_home_calendar.json") -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"schema_version": CALENDAR_STORE_VERSION, "events": [], "drafts": {}, "updated_at": _now_iso()}

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            return self._empty()
        if not isinstance(payload, dict):
            return self._empty()
        payload["schema_version"] = CALENDAR_STORE_VERSION
        payload["events"] = [row for row in payload.get("events", []) if isinstance(row, dict)]
        payload["drafts"] = payload.get("drafts") if isinstance(payload.get("drafts"), dict) else {}
        return payload

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload["schema_version"] = CALENDAR_STORE_VERSION
        payload["updated_at"] = _now_iso()
        handle, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, self.path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def _mutate(self, callback: Callable[[dict[str, Any]], Any]) -> Any:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            try:
                self.lock_path.chmod(0o600)
            except OSError:
                pass
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._read_unlocked()
                result = callback(payload)
                self._write_unlocked(payload)
                return result
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _validate(raw: dict[str, Any]) -> dict[str, Any]:
        title = _clean(raw.get("title"), 160)
        if not title:
            raise ValueError("El evento necesita un título.")
        timezone_name = str(raw.get("timezone") or DEFAULT_TIMEZONE)
        starts_at = _aware(raw.get("starts_at"), timezone_name)
        ends_at = _aware(raw.get("ends_at") or (starts_at + timedelta(hours=1)), timezone_name)
        if ends_at <= starts_at:
            raise ValueError("La hora de finalización debe ser posterior al comienzo.")
        if ends_at - starts_at > timedelta(days=14):
            raise ValueError("El evento es demasiado largo.")
        category = str(raw.get("category") or "PERSONAL").upper()
        if category not in CALENDAR_CATEGORIES:
            raise ValueError("La categoría del calendario no es válida.")
        recurrence = str(raw.get("recurrence") or "NONE").upper()
        if recurrence not in RECURRENCE_TYPES:
            raise ValueError("La repetición del evento no es válida.")
        recurrence_until = raw.get("recurrence_until") or None
        if recurrence != "NONE" and not recurrence_until:
            raise ValueError("Indica cuándo termina la repetición.")
        if recurrence_until:
            recurrence_until = date.fromisoformat(str(recurrence_until)).isoformat()
            if date.fromisoformat(recurrence_until) < starts_at.date():
                raise ValueError("La repetición no puede terminar antes de comenzar.")
        reminder_minutes = int(raw.get("reminder_minutes") if raw.get("reminder_minutes") is not None else 60)
        if reminder_minutes < 0 or reminder_minutes > 43_200:
            raise ValueError("El recordatorio debe estar entre 0 minutos y 30 días.")
        participants = [_clean(value, 160) for value in raw.get("participants") or []]
        participants = [value for value in participants if value][:50]
        return {
            "title": title,
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "timezone": timezone_name,
            "category": category,
            "reminder_minutes": reminder_minutes,
            "location": _clean(raw.get("location"), 240),
            "notes": _clean(raw.get("notes"), 2000),
            "participants": participants,
            "recurrence": recurrence,
            "recurrence_until": recurrence_until,
            "all_day": bool(raw.get("all_day", False)),
        }

    def save_draft(self, owner_id: str, raw: dict[str, Any]) -> dict[str, Any]:
        owner = str(owner_id)
        draft = self._validate(raw)
        draft.update({"id": uuid4().hex, "owner_id": owner, "status": "PENDING", "created_at": _now_iso()})

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            payload["drafts"][owner] = draft
            return deepcopy(draft)

        return self._mutate(apply)

    def pending_draft(self, owner_id: str) -> dict[str, Any] | None:
        row = self._read_unlocked().get("drafts", {}).get(str(owner_id))
        return deepcopy(row) if isinstance(row, dict) else None

    def discard_draft(self, owner_id: str) -> None:
        self._mutate(lambda payload: payload["drafts"].pop(str(owner_id), None))

    def save_delete_draft(self, owner_id: str, event_id: str) -> dict[str, Any]:
        event = self.get(owner_id, event_id)
        draft = {
            "id": uuid4().hex,
            "owner_id": str(owner_id),
            "status": "PENDING",
            "action": "DELETE",
            "event_id": event["id"],
            "event": event,
            "created_at": _now_iso(),
        }
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            payload["drafts"][str(owner_id)] = draft
            return deepcopy(draft)

        return self._mutate(apply)

    def create(self, owner_id: str, raw: dict[str, Any], *, source: str = "ui") -> dict[str, Any]:
        owner = str(owner_id)
        event = self._validate(raw)
        now = _now_iso()
        event.update({"id": uuid4().hex, "owner_id": owner, "source": _clean(source, 40) or "ui", "created_at": now, "updated_at": now})

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            payload["events"].append(event)
            payload["drafts"].pop(owner, None)
            return deepcopy(event)

        return self._mutate(apply)

    def confirm_draft(self, owner_id: str, draft_id: str | None = None, *, source: str = "voice") -> dict[str, Any]:
        draft = self.pending_draft(owner_id)
        if draft is None or (draft_id and draft.get("id") != draft_id):
            raise KeyError("draft")
        if draft.get("action") == "DELETE":
            deleted = self.delete(owner_id, str(draft.get("event_id") or ""))
            self.discard_draft(owner_id)
            return {**deleted, "deleted": True}
        return self.create(owner_id, draft, source=source)

    def get(self, owner_id: str, event_id: str) -> dict[str, Any]:
        row = next((row for row in self._read_unlocked()["events"] if row.get("owner_id") == str(owner_id) and row.get("id") == str(event_id)), None)
        if row is None:
            raise KeyError(event_id)
        return deepcopy(row)

    def update(self, owner_id: str, event_id: str, raw: dict[str, Any]) -> dict[str, Any]:
        owner = str(owner_id)

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            for index, current in enumerate(payload["events"]):
                if current.get("owner_id") != owner or current.get("id") != str(event_id):
                    continue
                event = self._validate({**current, **raw})
                event.update({key: current.get(key) for key in ("id", "owner_id", "source", "created_at")})
                event["updated_at"] = _now_iso()
                payload["events"][index] = event
                return deepcopy(event)
            raise KeyError(event_id)

        return self._mutate(apply)

    def delete(self, owner_id: str, event_id: str) -> dict[str, Any]:
        owner = str(owner_id)

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            for index, current in enumerate(payload["events"]):
                if current.get("owner_id") == owner and current.get("id") == str(event_id):
                    return deepcopy(payload["events"].pop(index))
            raise KeyError(event_id)

        return self._mutate(apply)

    @staticmethod
    def _occurrences(event: dict[str, Any], start: datetime, end: datetime) -> list[dict[str, Any]]:
        timezone_name = str(event.get("timezone") or DEFAULT_TIMEZONE)
        original_start = _aware(event["starts_at"], timezone_name)
        original_end = _aware(event["ends_at"], timezone_name)
        duration = original_end - original_start
        recurrence = str(event.get("recurrence") or "NONE")
        until = date.fromisoformat(str(event.get("recurrence_until"))) if event.get("recurrence_until") else original_start.date()
        results: list[dict[str, Any]] = []
        current = original_start
        while current.date() <= until:
            if current + duration > start and current < end:
                row = deepcopy(event)
                row["starts_at"] = current.isoformat()
                row["ends_at"] = (current + duration).isoformat()
                row["occurrence_date"] = current.date().isoformat()
                row["occurrence_id"] = f"{event['id']}:{current.date().isoformat()}"
                results.append(row)
            if recurrence == "NONE":
                break
            if recurrence == "DAILY":
                current += timedelta(days=1)
            elif recurrence == "WEEKLY":
                current += timedelta(days=7)
            else:
                current += timedelta(days=1)
                while current.weekday() >= 5:
                    current += timedelta(days=1)
        return results

    def list_events(self, owner_id: str, *, start: Any, end: Any, timezone_name: str = DEFAULT_TIMEZONE) -> list[dict[str, Any]]:
        range_start = _aware(start, timezone_name)
        range_end = _aware(end, timezone_name)
        if range_end <= range_start or range_end - range_start > timedelta(days=370):
            raise ValueError("El rango del calendario no es válido.")
        rows: list[dict[str, Any]] = []
        for event in self._read_unlocked()["events"]:
            if event.get("owner_id") == str(owner_id):
                rows.extend(self._occurrences(event, range_start, range_end))
        return sorted(rows, key=lambda row: (row["starts_at"], row["title"].casefold()))

    def conflicts(self, owner_id: str, raw: dict[str, Any], *, exclude_id: str | None = None) -> list[dict[str, Any]]:
        event = self._validate(raw)
        start = _aware(event["starts_at"], event["timezone"])
        end = _aware(event["ends_at"], event["timezone"])
        rows = self.list_events(owner_id, start=start - timedelta(days=1), end=end + timedelta(days=1), timezone_name=event["timezone"])
        return [row for row in rows if row.get("id") != exclude_id and _aware(row["starts_at"], row["timezone"]) < end and _aware(row["ends_at"], row["timezone"]) > start]

    def export_ics(self, owner_id: str, event_id: str) -> str:
        event = self.get(owner_id, event_id)
        start = _aware(event["starts_at"], event["timezone"])
        end = _aware(event["ends_at"], event["timezone"])
        lines = [
            "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Roxy Home//Calendario//ES", "CALSCALE:GREGORIAN",
            "BEGIN:VEVENT", f"UID:{event['id']}@roxy-home", f"DTSTAMP:{_ics_stamp(datetime.now(timezone.utc))}",
            f"DTSTART:{_ics_stamp(start)}", f"DTEND:{_ics_stamp(end)}", f"SUMMARY:{_ics_escape(event['title'])}",
        ]
        if event.get("location"):
            lines.append(f"LOCATION:{_ics_escape(event['location'])}")
        if event.get("notes"):
            lines.append(f"DESCRIPTION:{_ics_escape(event['notes'])}")
        reminder = int(event.get("reminder_minutes") or 0)
        if reminder:
            lines.extend(["BEGIN:VALARM", f"TRIGGER:-PT{reminder}M", "ACTION:DISPLAY", f"DESCRIPTION:{_ics_escape(event['title'])}", "END:VALARM"])
        recurrence = str(event.get("recurrence") or "NONE")
        until = event.get("recurrence_until")
        if recurrence != "NONE" and until:
            until_stamp = datetime.combine(date.fromisoformat(str(until)) + timedelta(days=1), time.min, tzinfo=_timezone(event["timezone"]))
            frequency = "DAILY" if recurrence in {"DAILY", "WEEKDAYS"} else "WEEKLY"
            rule = f"RRULE:FREQ={frequency};UNTIL={_ics_stamp(until_stamp)}"
            if recurrence == "WEEKDAYS":
                rule += ";BYDAY=MO,TU,WE,TH,FR"
            lines.append(rule)
        lines.extend(["END:VEVENT", "END:VCALENDAR", ""])
        return "\r\n".join(lines)


SPANISH_WEEKDAYS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
SPANISH_MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}


def _plain(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"\s+", " ", normalized.encode("ascii", "ignore").decode("ascii").lower()).strip()


def parse_calendar_command(text: str, *, current: datetime | None = None, timezone_name: str = DEFAULT_TIMEZONE) -> dict[str, Any]:
    """Parse common Spanish scheduling commands without sending private calendar data to AI."""
    zone = _timezone(timezone_name)
    now = (current or datetime.now(zone)).astimezone(zone)
    clean = _plain(text)
    target = now.date()
    if re.search(r"\bpasado manana\b", clean):
        target += timedelta(days=2)
    elif re.search(r"\bmanana\b", clean):
        target += timedelta(days=1)
    weekday_match = next(((name, index) for name, index in SPANISH_WEEKDAYS.items() if re.search(rf"\b{name}\b", clean)), None)
    day_match = re.search(r"\b(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)?\s*(\d{1,2})(?:\s+de\s+([a-z]+))?(?:\s+de\s+(\d{4}))?\b", clean)
    if day_match and (weekday_match or day_match.group(2)):
        day = int(day_match.group(1))
        month = SPANISH_MONTHS.get(day_match.group(2) or "", now.month)
        year = int(day_match.group(3) or now.year)
        try:
            candidate = date(year, month, day)
            if not day_match.group(2) and candidate < now.date():
                candidate = date(year + 1, month, day)
            target = candidate
        except ValueError as exc:
            raise ValueError("La fecha indicada no es válida.") from exc
    elif weekday_match:
        target += timedelta(days=(weekday_match[1] - target.weekday()) % 7 or 7)
    time_match = re.search(r"\b(?:a\s+las?|a\s+la)\s+(\d{1,2})(?::([0-5]\d))?\s*(a\.?\s*m\.?|p\.?\s*m\.?)?", clean)
    if not time_match:
        time_match = re.search(r"\b(\d{1,2}):([0-5]\d)\s*(a\.?\s*m\.?|p\.?\s*m\.?)?", clean)
    if not time_match:
        raise ValueError("Indica la hora del evento.")
    hour = int(time_match.group(1))
    minute = int(time_match.group(2) or 0)
    meridiem = re.sub(r"[^apm]", "", time_match.group(3) or "")
    if meridiem.startswith("p") and hour < 12:
        hour += 12
    if meridiem.startswith("a") and hour == 12:
        hour = 0
    if hour > 23:
        raise ValueError("La hora indicada no es válida.")
    starts_at = datetime.combine(target, time(hour, minute), tzinfo=zone)
    reminder = 60
    reminder_match = re.search(r"(?:recuerdame|avisame|recordatorio)(?:\s+de)?\s+(\d+)\s*(minutos?|horas?|dias?)\s+antes", clean)
    if reminder_match:
        amount = int(reminder_match.group(1))
        reminder = amount * (1440 if reminder_match.group(2).startswith("dia") else 60 if reminder_match.group(2).startswith("hora") else 1)
    recurrence = "WEEKDAYS" if re.search(r"de lunes a viernes|lunes a viernes", clean) else "NONE"
    until_match = re.search(r"hasta\s+(?:el\s+)?(\d{1,2})(?:\s+de\s+([a-z]+))?(?:\s+de\s+(\d{4}))?", clean)
    recurrence_until = None
    if recurrence != "NONE" and until_match:
        month = SPANISH_MONTHS.get(until_match.group(2) or "", target.month)
        recurrence_until = date(int(until_match.group(3) or target.year), month, int(until_match.group(1))).isoformat()
    title = re.sub(r"^(?:roxy[, ]+)?(?:agrega|anade|añade|programa|crea|pon|agenda)\s+", "", clean).strip()
    title = re.sub(r"^(?:un|una|el|la)\s+", "", title).strip()
    title = re.split(r"\b(?:el|para)\s+(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo|hoy|manana)\b|\b(?:a\s+las?|a\s+la)\s+\d|\bde lunes a viernes\b", title, maxsplit=1)[0].strip(" ,.-")
    title = title or "Nuevo evento"
    return {
        "title": title[:160].capitalize(), "starts_at": starts_at.isoformat(), "ends_at": (starts_at + timedelta(hours=1)).isoformat(),
        "timezone": timezone_name, "category": "SCHOOL" if "escuela" in clean else "WORK" if "trabajo" in clean else "APPOINTMENTS" if re.search(r"dentista|medico|cita", clean) else "FAMILY" if re.search(r"familia|ninos|niños", text.lower()) else "PERSONAL",
        "reminder_minutes": reminder, "location": "", "notes": "", "participants": [], "recurrence": recurrence, "recurrence_until": recurrence_until,
        "needs_clarification": recurrence != "NONE" and not recurrence_until,
    }
