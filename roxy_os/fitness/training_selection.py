"""Scheduling for explicitly selected editorial routines; no diagnosis or load inference."""
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from .domain import FitnessInputError
from .schemas import ConfirmedTrainingRequirements, FitnessProfileInput

TRAINING_IDS = frozenset({"home-bodyweight-foundations", "home-dumbbell-foundations",
                          "gym-dumbbell-foundations", "gentle-mobility",
                          "yoga-gentle-start", "core-foundations"})
STRENGTH_IDS = frozenset({"gentle-strength", "home-bodyweight-foundations",
                         "home-dumbbell-foundations", "gym-dumbbell-foundations", "core-foundations"})
VERSION = "home-training-proposal-213-v1"
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def requirements_for(profile, program, confirmed):
    p = profile if isinstance(profile, FitnessProfileInput) else FitnessProfileInput.model_validate(profile)
    c = confirmed if isinstance(confirmed, ConfirmedTrainingRequirements) else ConfirmedTrainingRequirements.model_validate(confirmed)
    if p.age_band is None:
        raise FitnessInputError("Completa primero tu rango de edad adulto en las preferencias.")
    if p.experience == "prefer_not_to_say":
        raise FitnessInputError("Indica tu experiencia reciente antes de organizar una rutina.")
    if program["level"] == "intermediate" and p.experience != "intermediate":
        raise FitnessInputError("Esta rutina requiere experiencia regular. Elige una de iniciación o revisa tu experiencia.")
    if not set(p.locations).intersection(program["locations"]):
        raise FitnessInputError("Esta rutina usa un espacio distinto de tus preferencias. Confirma dónde puedes entrenar antes de continuar.")
    required = program["requirements"]
    if not set(required["equipment"]).issubset(c.equipment) or not set(required["capabilities"]).issubset(c.capabilities):
        raise FitnessInputError("Confirma el material y los movimientos de esta rutina antes de organizarla.")
    if p.session_minutes is None or p.session_minutes < program["estimated_minutes"]["max"]:
        raise FitnessInputError(f"Esta rutina tiene una estimación de hasta {program['estimated_minutes']['max']} minutos. Elige una opción más corta o ajusta tu disponibilidad.")
    return p, c


def preview_training(profile, program_id, confirmed, *, start_date=None, existing_plan=None, now=None, training_targets=None):
    from .training_content import training_detail
    from .training_targets import validate_training_targets
    from copy import deepcopy
    from .proposals import _slot, _day
    program = training_detail(program_id)
    targets = validate_training_targets(program_id, program["content_version"], training_targets)
    p, c = requirements_for(profile, program, confirmed)
    now = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise FitnessInputError("La hora de referencia necesita una fecha consciente en UTC.")
    today = now.astimezone(ZoneInfo(p.timezone)).date()
    first = _day(start_date) if start_date is not None else today
    if first < today or (first + timedelta(days=6)).year > 2100:
        raise FitnessInputError("Elige una semana actual o futura dentro del calendario permitido.")
    existing = (existing_plan or {}).get("sessions", [])
    if existing and existing_plan["timezone"] != p.timezone:
        raise FitnessInputError("La zona de tus preferencias y tu plan debe coincidir antes de organizar nuevas fechas.")
    occupied = {s["date"] for s in existing if s["status"] != "skipped"}
    strength = {date.fromisoformat(s["date"]) for s in existing if s["status"] != "skipped" and s["program_id"] in STRENGTH_IDS}
    slots = {s["day"]: s["windows"] for s in p.model_dump()["availability"]}
    sessions, details, excluded = [], [], []
    for offset in range(7):
        day = first + timedelta(days=offset)
        reason = None
        if len(existing) + len(sessions) >= 366:
            reason = "Tu plan alcanzó el límite de actividades; las conservamos."
        elif day.isoformat() in occupied:
            reason = "Ya tienes una actividad ese día; la conservamos."
        elif DAYS[day.weekday()] not in slots:
            reason = "Ese día no tiene disponibilidad indicada."
        elif program_id in STRENGTH_IDS and any(abs((day - other).days) <= 1 for other in strength):
            reason = "Dejamos un día entre rutinas de fuerza que pueden trabajar los mismos grupos."
        if reason is None:
            windows = next(row.windows for row in p.availability if row.day == DAYS[day.weekday()])
            slot, _reason = _slot(day, windows, p.timezone, p.session_minutes + p.travel_minutes, now,
                                  {s["time"] for s in existing if s["date"] == day.isoformat()})
            if slot is None:
                reason = "No queda una hora inequívoca que permita tus minutos y traslado dentro de la ventana."
        if reason:
            excluded.append({"date": day.isoformat(), "message_es": reason})
            continue
        session_id = str(uuid4())
        sessions.append({"id": session_id, "program_id": program_id, "date": day.isoformat(), "time": slot["time"],
                         "content_version": program["content_version"], "confirmed_requirements": c.model_dump(),
                         "reserved_minutes": p.session_minutes, "travel_minutes": p.travel_minutes})
        if targets is not None:
            sessions[-1]["training_targets"] = deepcopy(targets)
        details.append({"session_id": session_id, "starts_at": slot["starts_at"], "reserved_until": slot["reserved_until"]})
        if program_id in STRENGTH_IDS:
            strength.add(day)
    return {"version": VERSION, "status": "ready" if sessions else "no_slots", "timezone": p.timezone,
            "program_id": program_id, "title": program["title"], "content_version": program["content_version"],
            "start_date": first.isoformat(), "end_date": (first + timedelta(days=6)).isoformat(),
            "sessions": sessions, "session_details": details, "excluded_days": excluded,
            "estimated_minutes": program["estimated_minutes"], "reserved_minutes": p.session_minutes,
            "travel_minutes": p.travel_minutes,
            "notice_es": "Las fechas usan tu disponibilidad y las confirmaciones de esta rutina. La duración de ejecución es una estimación; descansa y avanza a tu ritmo.",
            "clinical_approval": False,
            "targets_notice_es": "Los objetivos son una elección tuya para consultar durante la sesión. No son resultados realizados ni una indicación de aumentar el esfuerzo. Los tiempos estimados corresponden a la guía original; los objetivos que elijas pueden requerir otro tiempo." if targets else None}


def validate_new_training_session(profile, session, plan, others):
    from .activity_plan import session_instant
    from .training_content import training_detail
    program = training_detail(session["program_id"])
    p, _confirmed = requirements_for(profile, program, session["confirmed_requirements"])
    if session["content_version"] != program["content_version"]:
        raise FitnessInputError("La rutina cambió. Vuelve a revisarla antes de guardar una nueva fecha.")
    if plan["timezone"] != p.timezone or session["reserved_minutes"] != p.session_minutes or session["travel_minutes"] != p.travel_minutes:
        raise FitnessInputError("Tus horarios o minutos cambiaron. Vuelve a revisar esta rutina con tus preferencias actuales.")
    day = date.fromisoformat(session["date"])
    start = session_instant(session["date"], session["time"], p.timezone)
    end = start + timedelta(minutes=session["reserved_minutes"] + session["travel_minutes"])
    local_end = end.astimezone(ZoneInfo(p.timezone))
    if local_end.date() != day or not any(row.day == DAYS[day.weekday()] and any(
            window.start <= session["time"] and local_end.strftime("%H:%M") <= window.end
            for window in row.windows) for row in p.availability):
        raise FitnessInputError("La fecha y hora deben caber en una ventana de tu disponibilidad, incluido el traslado.")
    try:
        resolved_end = session_instant(session["date"], local_end.strftime("%H:%M"), p.timezone)
    except ValueError:
        raise FitnessInputError("El final de la reserva coincide con un cambio de horario ambiguo.") from None
    if resolved_end != end:
        raise FitnessInputError("El final de la reserva coincide con un cambio de horario ambiguo.")
    for other in others:
        if other["id"] == session["id"] or other.get("status") == "skipped":
            continue
        other_day = date.fromisoformat(other["date"])
        if other_day == day:
            raise FitnessInputError("Ya hay otra actividad ese día. Elige otra fecha para esta rutina.")
        if session["program_id"] in STRENGTH_IDS and other["program_id"] in STRENGTH_IDS and abs((day - other_day).days) <= 1:
            raise FitnessInputError("Deja un día entre estas rutinas de fuerza antes de guardar.")
