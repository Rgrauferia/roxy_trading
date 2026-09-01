from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from roxy_os.home_pet_catalog import personalized_pet_routines


_MEAL_LABELS = {"breakfast": "Desayuno", "lunch": "Comida", "dinner": "Cena"}


def _as_datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _today_meals(food: dict[str, Any], today: date) -> list[dict[str, Any]]:
    plans = food.get("weekly_plans") or []
    if not plans:
        return []
    days = plans[-1].get("days") or []
    row = next((item for item in days if str(item.get("date") or "") == today.isoformat()), None)
    if row is None:
        return []
    return [
        {
            "meal_type": str(meal.get("meal_type") or "meal"),
            "label": _MEAL_LABELS.get(str(meal.get("meal_type") or ""), "Comida"),
            "title": str(meal.get("title") or "").strip(),
            "minutes": int(meal.get("minutes") or 0),
        }
        for meal in row.get("meals") or []
        if str(meal.get("title") or "").strip()
    ]


def build_home_daily_brief(
    *,
    display_name: str,
    shopping: dict[str, Any],
    food: dict[str, Any],
    calendar: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a deterministic, private daily brief from existing Home data."""

    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    today = moment.date()
    pending = [row for row in shopping.get("items") or [] if row.get("status") == "PENDING"]
    pantry = [row for row in food.get("pantry") or [] if isinstance(row, dict)]
    meals = _today_meals(food, today)
    events = []
    for row in calendar.get("events") or []:
        starts_at = _as_datetime(row.get("starts_at"))
        ends_at = _as_datetime(row.get("ends_at"))
        if starts_at and (ends_at or starts_at) >= moment:
            events.append((starts_at, row))
    events.sort(key=lambda item: item[0])
    upcoming = events[0][1] if events else None
    cards: list[dict[str, Any]] = []
    pet_tasks: list[dict[str, Any]] = []
    pet_followups: list[dict[str, Any]] = []
    for pet in food.get("pets") or []:
        if not isinstance(pet, dict) or not pet.get("id"):
            continue
        routines = personalized_pet_routines(pet)
        for routine in routines:
            completed_at = _as_datetime(routine.get("last_completed_at"))
            completed_local = completed_at.astimezone(moment.tzinfo) if completed_at else None
            if routine.get("cadence") == "weekly":
                done = bool(completed_local and 0 <= (moment - completed_local).total_seconds() < 7 * 86400)
            else:
                done = bool(completed_local and completed_local.date() == today)
            if not done:
                pet_tasks.append({"pet": pet, "routine": routine})
        for record in pet.get("medical_history") or []:
            due_text = str(record.get("next_due_on") or "")
            try:
                due = date.fromisoformat(due_text)
            except ValueError:
                continue
            if due <= today + timedelta(days=14):
                pet_followups.append({"pet": pet, "record": record, "due": due})

    if upcoming:
        starts_at = events[0][0]
        cards.append(
            {
                "id": "next-event",
                "kind": "calendar",
                "icon": "event_upcoming",
                "title": str(upcoming.get("title") or "Próximo evento"),
                "detail": starts_at.isoformat(),
                "action": {"panel": "calendar", "label": "Ver calendario"},
                "priority": 100,
            }
        )
    if meals:
        next_meal = meals[0]
        cards.append(
            {
                "id": "today-meal",
                "kind": "meal",
                "icon": "restaurant",
                "title": next_meal["title"],
                "detail": f"{next_meal['label']} de hoy" + (f" · {next_meal['minutes']} min" if next_meal["minutes"] else ""),
                "action": {"panel": "today", "label": "Ver plan"},
                "priority": 90,
            }
        )
    if pet_followups:
        followup = sorted(pet_followups, key=lambda row: row["due"])[0]
        pet = followup["pet"]
        cards.append(
            {
                "id": "pet-followup",
                "kind": "pet",
                "icon": "medical_services",
                "title": f"Seguimiento de {pet.get('name') or 'tu mascota'}",
                "detail": f"{followup['record'].get('title') or 'Control pendiente'} · {followup['due'].isoformat()}",
                "action": {"panel": "recipes", "audience": "pet", "pet_id": str(pet.get("id")), "tab": "medical"},
                "priority": 98,
            }
        )
    if pet_tasks:
        task = pet_tasks[0]
        pet, routine = task["pet"], task["routine"]
        cards.append(
            {
                "id": "pet-care",
                "kind": "pet",
                "icon": str(routine.get("icon") or "pets"),
                "title": f"{pet.get('name') or 'Tu mascota'} · {routine.get('title') or 'Cuidado pendiente'}",
                "detail": str(routine.get("detail") or "Abre su ficha para registrarlo."),
                "action": {"panel": "recipes", "audience": "pet", "pet_id": str(pet.get("id")), "tab": "care"},
                "priority": 95,
            }
        )
    if pending:
        cards.append(
            {
                "id": "pending-shopping",
                "kind": "shopping",
                "icon": "shopping_cart",
                "title": f"{len(pending)} productos por comprar",
                "detail": ", ".join(str(row.get("name") or "") for row in pending[:3]),
                "action": {"panel": "shopping", "label": "Abrir lista"},
                "priority": 80,
            }
        )
    low_pantry = [row for row in pantry if float(row.get("quantity") or 0) <= 1]
    if low_pantry:
        cards.append(
            {
                "id": "low-pantry",
                "kind": "pantry",
                "icon": "inventory_2",
                "title": "Productos por revisar",
                "detail": "Queda poco de " + ", ".join(str(row.get("name") or "") for row in low_pantry[:3]),
                "action": {"panel": "pantry", "label": "Ver despensa"},
                "priority": 70,
            }
        )
    if not cards:
        cards.append(
            {
                "id": "all-clear",
                "kind": "ready",
                "icon": "check_circle",
                "title": "Todo está tranquilo en casa",
                "detail": "Puedes pedirme que organice la semana o revise la despensa.",
                "action": {"panel": "today", "label": "Hablar con Roxy"},
                "priority": 10,
            }
        )

    cards.sort(key=lambda row: int(row.get("priority") or 0), reverse=True)
    name = " ".join(str(display_name or "").strip().split())
    headline = cards[0]["title"]
    summary = f"{name}, {headline[0].lower() + headline[1:]}." if name else f"{headline}."
    return {
        "generated_at": moment.isoformat(),
        "headline": headline,
        "summary": summary,
        "cards": cards[:4],
        "today_meals": meals,
        "counts": {
            "shopping_pending": len(pending),
            "pantry": len(pantry),
            "events_upcoming": len(events),
            "meals_today": len(meals),
            "pet_tasks": len(pet_tasks),
            "pet_followups": len(pet_followups),
        },
        "suggested_phrases": [
            "¿Qué tengo hoy?",
            "¿Qué podemos cocinar con lo que hay?",
            "¿Qué falta comprar?",
            "¿Qué necesitan mis mascotas hoy?",
        ],
    }
