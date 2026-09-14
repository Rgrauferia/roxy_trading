"""Read-only agenda proposals for source guides explicitly chosen by an adult.

This is scheduling, not exercise prescription. Source doses and activation gates
remain unchanged. The caller authenticates the saved profile and consent, and
supplies existing sessions expressed in the profile's timezone.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from .activity_plan import ActivitySession, session_instant
from .domain import FitnessInputError
from .programs import SOURCE_PROGRAMS, program_detail
from .schemas import FitnessProfileInput

VERSION = "fitness-agenda-proposal-212-v1"
_NAMESPACE = UUID("b273f80b-bbb8-4ca3-b44c-207a109615cd")
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
NOTICE_ES = ("La reserva usa los minutos que elegiste e incluye el traslado indicado. "
             "Estas guías no publican una duración total; la reserva no garantiza que quepan completas.")
_RECOVERY_SOURCE = "https://www.niddk.nih.gov/health-information/weight-management/healthy-eating-physical-activity-for-life/health-tips-for-adults"
_MESSAGES = {
    "existing_activity": "Ya tienes una actividad pendiente o realizada ese día; se conserva.",
    "existing_time": "Las horas disponibles coinciden con actividades guardadas; se conservan incluso si las omitiste.",
    "plan_limit": "La agenda alcanzó su límite de actividades guardadas; se conserva completa.",
    "no_availability": "No indicaste disponibilidad para ese día.",
    "strength_recovery": "Dejamos un día entre guías de fuerza; también respetamos tu agenda guardada.",
    "window_too_short": "Ninguna ventana permite reservar tus minutos y el traslado indicado.",
    "past_windows": "Las ventanas que tenían espacio ya pasaron o ya no dejan tiempo suficiente.",
    "dst_unavailable": "No encontramos una hora inequívoca que quepa en tus ventanas durante el cambio de horario.",
}


class _ExistingSession(ActivitySession):
    status: Literal["planned", "completed", "skipped"] = "planned"
    completed_at: str | None = None
    starts_at: str | None = None


def _day(value):
    if not isinstance(value, str):
        raise FitnessInputError("Selecciona una fecha inicial YYYY-MM-DD.")
    try:
        return date.fromisoformat(ActivitySession.valid_date(value))
    except (ValueError, TypeError):
        raise FitnessInputError("Selecciona una fecha inicial válida entre 2000 y 2100.") from None


def _clock(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _minute(clock):
    hour, minute = clock.split(":")
    return int(hour) * 60 + int(minute)


def _slot(day, windows, zone, total_minutes, now, occupied_clocks=()):
    """Find the first valid local minute whose elapsed reservation fits a window.

    DST may change elapsed time within a window. Compute the end from the UTC
    instant, then validate its local representation with the existing planner's
    resolver. Never silently choose either occurrence of an ambiguous clock.
    """
    saw_past = saw_dst = saw_collision = False
    tz = ZoneInfo(zone)
    for window in sorted(windows, key=lambda item: item.start):
        first, last = _minute(window.start), _minute(window.end)
        for minute in range(first, last):
            clock = _clock(minute)
            # Skipped rows remain in the saved plan. Reusing their time can
            # regenerate their UUID and would make a reviewed merge invalid.
            if clock in occupied_clocks:
                saw_collision = True
                continue
            try:
                start = session_instant(day.isoformat(), clock, zone)
            except ValueError:
                saw_dst = True
                continue
            if start < now:
                saw_past = True
                continue
            end = start + timedelta(minutes=total_minutes)
            local_end = end.astimezone(tz)
            if local_end.date() != day or local_end.strftime("%H:%M") > window.end:
                continue
            try:
                resolved_end = session_instant(day.isoformat(), local_end.strftime("%H:%M"), zone)
            except ValueError:
                saw_dst = True
                continue
            if resolved_end != end:
                saw_dst = True
                continue
            return {"time": clock, "starts_at": start.isoformat(), "reserved_until": end.isoformat()}, None
    if saw_dst:
        return None, "dst_unavailable"
    if saw_past:
        return None, "past_windows"
    if saw_collision:
        return None, "existing_time"
    return None, "window_too_short"


def build_proposal(profile, start_date, program_ids, nowUTC, *, existing_sessions=None):
    """Propose seven local days without writing or changing source prescriptions.

    The result contains only new ActivitySession-compatible rows. It must be
    reviewed and merged with the saved agenda before the existing explicit save.
    UUIDs are deterministic for an identical source guide/date/time/timezone.
    """
    if not isinstance(profile, (FitnessProfileInput, dict)):
        raise FitnessInputError("Primero guarda tus preferencias de Ejercicio.")
    parsed = FitnessProfileInput.model_validate(
        profile.model_dump(mode="python") if isinstance(profile, FitnessProfileInput) else profile)
    if parsed.age_band is None:
        raise FitnessInputError("Confirma primero tu rango de edad adulto.")
    if parsed.session_minutes is None:
        raise FitnessInputError("Elige cuántos minutos quieres reservar en tu agenda.")
    if (not isinstance(nowUTC, datetime) or nowUTC.tzinfo is None
            or nowUTC.utcoffset() != timedelta(0)):
        raise FitnessInputError("La hora de referencia necesita una fecha consciente en UTC.")
    now = nowUTC.astimezone(timezone.utc)
    first_day = _day(start_date)
    last_day = first_day + timedelta(days=6)
    if last_day.year > 2100:
        raise FitnessInputError("La semana debe terminar dentro del año 2100.")
    if first_day < now.astimezone(ZoneInfo(parsed.timezone)).date():
        raise FitnessInputError("La fecha inicial no puede estar en el pasado en tu zona horaria.")
    if (not isinstance(program_ids, list) or not 1 <= len(program_ids) <= 3
            or any(not isinstance(item, str) or item not in SOURCE_PROGRAMS for item in program_ids)
            or len(set(program_ids)) != len(program_ids)):
        raise FitnessInputError("Elige entre una y tres guías disponibles, sin repetirlas.")
    # Resolve server-controlled catalog content; never treat an ID as sufficient.
    titles = {item: program_detail(item)["program"]["title_es"] for item in program_ids}
    if existing_sessions is None:
        existing_sessions = []
    if not isinstance(existing_sessions, list) or len(existing_sessions) > 366:
        raise FitnessInputError("La agenda existente no tiene un formato válido.")
    existing = [_ExistingSession.model_validate(item) for item in existing_sessions]
    if len({item.id for item in existing}) != len(existing):
        raise FitnessInputError("La agenda existente contiene identificadores repetidos.")
    occupied, strength_days, existing_clocks = set(), set(), {}
    for item in existing:
        session_instant(item.date, item.time, parsed.timezone)
        existing_clocks.setdefault(item.date, set()).add(item.time)
        if item.status != "skipped":
            occupied.add(date.fromisoformat(item.date))
            if item.program_id == "gentle-strength":
                strength_days.add(date.fromisoformat(item.date))
    availability = {item.day: item.windows for item in parsed.availability}
    total = parsed.session_minutes + parsed.travel_minutes
    sessions, details, excluded, adjustments = [], [], [], []
    next_index = 0
    for offset in range(7):
        day = first_day + timedelta(days=offset)
        reason = None
        windows = availability.get(_DAYS[day.weekday()])
        if day in occupied:
            reason = "existing_activity"
        elif not windows:
            reason = "no_availability"
        elif len(existing) + len(sessions) >= 366:
            reason = "plan_limit"
        if reason:
            excluded.append({"date": day.isoformat(), "reason_code": reason, "message_es": _MESSAGES[reason]})
            continue
        chosen = None
        recovery_blocked = False
        for shift in range(len(program_ids)):
            index = (next_index + shift) % len(program_ids)
            candidate = program_ids[index]
            if candidate == "gentle-strength" and any(abs((day - prior).days) <= 1 for prior in strength_days):
                recovery_blocked = True
                continue
            chosen = candidate
            next_candidate_index = (index + 1) % len(program_ids)
            break
        if chosen is None:
            reason = "strength_recovery"
        else:
            slot, reason = _slot(day, windows, parsed.timezone, total, now,
                                 existing_clocks.get(day.isoformat(), ()))
        if reason:
            excluded.append({"date": day.isoformat(), "reason_code": reason, "message_es": _MESSAGES[reason]})
            continue
        identifier = str(uuid5(_NAMESPACE, "|".join((VERSION, parsed.timezone, day.isoformat(), slot["time"], chosen))))
        sessions.append({"id": identifier, "program_id": chosen, "date": day.isoformat(), "time": slot["time"]})
        details.append({"session_id": identifier, "allocated_minutes": parsed.session_minutes,
                        "travel_minutes": parsed.travel_minutes, "source_duration_minutes": None,
                        "starts_at": slot["starts_at"], "reserved_until": slot["reserved_until"],
                        "reason_es": (f"Elegiste {titles[chosen]}; reservamos {parsed.session_minutes} minutos "
                                      f"y {parsed.travel_minutes} de traslado dentro de tu disponibilidad.")})
        if recovery_blocked:
            adjustments.append({"date": day.isoformat(), "reason_code": "strength_recovery",
                                "message_es": "Usamos otra de las guías que elegiste para dejar un día entre guías de fuerza."})
        next_index = next_candidate_index
        if chosen == "gentle-strength":
            strength_days.add(day)
    return {"version": VERSION, "status": "ready" if sessions else "no_slots", "timezone": parsed.timezone,
            "start_date": first_day.isoformat(), "end_date": last_day.isoformat(),
            "allocated_minutes": parsed.session_minutes, "travel_minutes": parsed.travel_minutes,
            "source_duration_minutes": None, "notice_es": NOTICE_ES, "sessions": sessions,
            "session_details": details, "excluded_days": excluded, "adjustments": adjustments,
            "recovery_source_url": _RECOVERY_SOURCE, "clinical_approval": False, "can_activate_training": False}
