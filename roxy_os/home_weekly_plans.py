from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from typing import Any


def _identity(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"[^a-z0-9]+", " ", normalized.encode("ascii", "ignore").decode("ascii").lower()).strip()


def _item(name: str, quantity: float, unit: str) -> dict[str, Any]:
    return {"name": name, "quantity": quantity, "unit": unit}


MEALS: dict[str, dict[str, Any]] = {
    "overnight_oats": {"title": "Avena nocturna con frutas", "minutes": 5, "ingredients": [_item("Avena", .5, "taza"), _item("Leche", .75, "taza"), _item("Frutos rojos", .5, "taza")]},
    "eggs_toast": {"title": "Huevos con tostada integral", "minutes": 10, "ingredients": [_item("Huevo", 2, "unidad"), _item("Pan integral", 2, "rebanada")]},
    "yogurt_fruit": {"title": "Yogur con fruta y avena", "minutes": 5, "ingredients": [_item("Yogur natural", 1, "taza"), _item("Fruta", 1, "unidad"), _item("Avena", .25, "taza")]},
    "avocado_toast": {"title": "Tostada de aguacate y huevo", "minutes": 12, "ingredients": [_item("Pan integral", 2, "rebanada"), _item("Aguacate", .5, "unidad"), _item("Huevo", 1, "unidad")]},
    "banana_smoothie": {"title": "Batido de plátano y avena", "minutes": 5, "ingredients": [_item("Plátano", 1, "unidad"), _item("Leche", 1, "taza"), _item("Avena", .25, "taza")]},
    "pancakes": {"title": "Panqueques de avena", "minutes": 15, "ingredients": [_item("Avena", .75, "taza"), _item("Huevo", 1, "unidad"), _item("Plátano", 1, "unidad")]},
    "chicken_rice": {"title": "Pollo al ajo con arroz", "minutes": 25, "ingredients": [_item("Pechuga de pollo", 1, "unidad"), _item("Arroz", .5, "taza"), _item("Ajo", 1, "diente"), _item("Vegetales verdes", 1, "taza")]},
    "chicken_bowl": {"title": "Bowl de pollo y vegetales", "minutes": 12, "ingredients": [_item("Pechuga de pollo cocida", 1, "unidad"), _item("Vegetales mixtos", 1.5, "taza"), _item("Arroz cocido", .5, "taza")]},
    "spaghetti": {"title": "Espaguetis con salsa casera", "minutes": 25, "ingredients": [_item("Espaguetis", 100, "gramo"), _item("Tomate triturado", 1, "taza"), _item("Carne molida", 120, "gramo")]},
    "salmon": {"title": "Salmón al horno con vegetales", "minutes": 25, "ingredients": [_item("Salmón", 1, "filete"), _item("Vegetales mixtos", 1.5, "taza"), _item("Limón", .5, "unidad")]},
    "turkey_bowl": {"title": "Bowl de pavo, quinoa y aguacate", "minutes": 20, "ingredients": [_item("Pavo molido", 120, "gramo"), _item("Quinoa", .5, "taza"), _item("Aguacate", .5, "unidad")]},
    "lentils": {"title": "Lentejas guisadas ligeras", "minutes": 30, "ingredients": [_item("Lentejas", .75, "taza"), _item("Zanahoria", 1, "unidad"), _item("Cebolla", .5, "unidad")]},
    "tacos": {"title": "Tacos de pollo en casa", "minutes": 20, "ingredients": [_item("Pollo cocido", 120, "gramo"), _item("Tortilla", 3, "unidad"), _item("Tomate", 1, "unidad"), _item("Aguacate", .5, "unidad")]},
    "rice_chicken": {"title": "Arroz con pollo familiar", "minutes": 35, "ingredients": [_item("Pollo", 150, "gramo"), _item("Arroz", .5, "taza"), _item("Vegetales mixtos", 1, "taza")]},
    "tuna_bowl": {"title": "Bowl de atún y garbanzos", "minutes": 10, "ingredients": [_item("Atún", 1, "lata"), _item("Garbanzos", .75, "taza"), _item("Pepino", .5, "unidad"), _item("Tomate", 1, "unidad")]},
    "chicken_wrap": {"title": "Wrap de pollo y aguacate", "minutes": 10, "ingredients": [_item("Pollo cocido", 120, "gramo"), _item("Tortilla integral", 1, "unidad"), _item("Aguacate", .5, "unidad")]},
    "vegetable_soup": {"title": "Sopa rápida de vegetales", "minutes": 20, "ingredients": [_item("Caldo", 2, "taza"), _item("Vegetales mixtos", 1.5, "taza"), _item("Papa", 1, "unidad")]},
    "omelet": {"title": "Tortilla de vegetales", "minutes": 12, "ingredients": [_item("Huevo", 2, "unidad"), _item("Vegetales mixtos", 1, "taza")]},
    "fish_sweet_potato": {"title": "Pescado con batata y ensalada", "minutes": 25, "ingredients": [_item("Pescado", 1, "filete"), _item("Batata", 1, "unidad"), _item("Ensalada verde", 2, "taza")]},
    "chickpea_salad": {"title": "Ensalada de garbanzos", "minutes": 10, "ingredients": [_item("Garbanzos", 1, "taza"), _item("Pepino", .5, "unidad"), _item("Tomate", 1, "unidad"), _item("Limón", .5, "unidad")]},
    "quesadilla": {"title": "Quesadilla de pollo y vegetales", "minutes": 12, "ingredients": [_item("Tortilla", 2, "unidad"), _item("Pollo cocido", 100, "gramo"), _item("Queso", .5, "taza"), _item("Vegetales mixtos", .5, "taza")]},
    "ropa_vieja": {"title": "Ropa vieja con arroz", "minutes": 35, "ingredients": [_item("Carne de res", 150, "gramo"), _item("Pimiento", .5, "unidad"), _item("Tomate triturado", .75, "taza"), _item("Arroz", .5, "taza")]},
    "pizza": {"title": "Pizza casera para compartir", "minutes": 35, "ingredients": [_item("Masa para pizza", 1, "unidad"), _item("Tomate triturado", .75, "taza"), _item("Queso", 1, "taza")]},
    "leftovers": {"title": "Cena de preparaciones de la semana", "minutes": 8, "ingredients": []},
}


STYLE_SCHEDULES: dict[str, list[tuple[str, str, str]]] = {
    "normal": [
        ("overnight_oats", "chicken_rice", "chicken_bowl"), ("yogurt_fruit", "spaghetti", "vegetable_soup"),
        ("eggs_toast", "ropa_vieja", "chicken_wrap"), ("banana_smoothie", "salmon", "omelet"),
        ("avocado_toast", "tuna_bowl", "tacos"), ("pancakes", "pizza", "chickpea_salad"),
        ("eggs_toast", "rice_chicken", "leftovers"),
    ],
    "fitness": [
        ("overnight_oats", "chicken_rice", "salmon"), ("eggs_toast", "turkey_bowl", "chickpea_salad"),
        ("yogurt_fruit", "fish_sweet_potato", "chicken_wrap"), ("banana_smoothie", "chicken_bowl", "omelet"),
        ("avocado_toast", "tuna_bowl", "lentils"), ("pancakes", "turkey_bowl", "chickpea_salad"),
        ("eggs_toast", "rice_chicken", "vegetable_soup"),
    ],
    "quick": [
        ("overnight_oats", "chicken_rice", "chicken_wrap"), ("yogurt_fruit", "spaghetti", "chickpea_salad"),
        ("avocado_toast", "tuna_bowl", "vegetable_soup"), ("banana_smoothie", "chicken_bowl", "quesadilla"),
        ("eggs_toast", "turkey_bowl", "chicken_wrap"), ("pancakes", "tacos", "leftovers"),
        ("yogurt_fruit", "rice_chicken", "leftovers"),
    ],
    "weight_loss": [
        ("eggs_toast", "chicken_bowl", "vegetable_soup"), ("yogurt_fruit", "salmon", "omelet"),
        ("overnight_oats", "lentils", "chickpea_salad"), ("avocado_toast", "turkey_bowl", "vegetable_soup"),
        ("banana_smoothie", "fish_sweet_potato", "chickpea_salad"), ("eggs_toast", "tuna_bowl", "omelet"),
        ("overnight_oats", "rice_chicken", "vegetable_soup"),
    ],
}


STYLE_META = {
    "fitness": ("Más proteína y energía", "Preparar proteínas y bases dos veces esta semana"),
    "normal": ("Variado y equilibrado", "Comer variado sin complicarse"),
    "quick": ("Máximo tiempo disponible", "Cocinar solo 2 veces esta semana"),
    "weight_loss": ("Porciones y saciedad", "Priorizar proteína, vegetales y fibra"),
}

SPANISH_WEEKDAYS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


def _next_monday(today: date | None = None) -> date:
    current = today or date.today()
    return current + timedelta(days=(7 - current.weekday()) % 7)


def _compatible(meal: dict[str, Any], exclusions: set[str]) -> bool:
    haystack = _identity(meal.get("title")) + " " + " ".join(_identity(row.get("name")) for row in meal.get("ingredients") or [])
    return not any(exclusion and exclusion in haystack for exclusion in exclusions)


def _meal(key: str, exclusions: set[str], alternatives: list[str], max_minutes: int) -> dict[str, Any]:
    chosen = key
    if not _compatible(MEALS[chosen], exclusions) or int(MEALS[chosen].get("minutes") or 0) > max_minutes:
        chosen = next((candidate for candidate in alternatives if _compatible(MEALS[candidate], exclusions)), "leftovers")
    return {"key": chosen, **MEALS[chosen], "favorite": False}


def create_local_weekly_plan(
    snapshot: dict[str, Any], *, style: str, people: int, max_minutes: int, weekly_budget: float,
    cook_days: int = 2, meal_scope: str = "all"
) -> dict[str, Any]:
    selected_style = style if style in STYLE_SCHEDULES else "normal"
    profile = (snapshot or {}).get("profile") or {}
    exclusions = {_identity(value) for value in [*(profile.get("allergies") or []), *(profile.get("dislikes") or [])] if _identity(value)}
    alternatives_by_position = [
        [
            key
            for schedule in STYLE_SCHEDULES.values()
            for day in schedule
            for key in [day[position]]
            if int(MEALS[key].get("minutes") or 0) <= max_minutes or key == "leftovers"
        ]
        for position in range(3)
    ]
    cook_days = max(1, min(7, int(cook_days)))
    selected_meal_indexes = {"all": (0, 1, 2), "lunch_dinner": (1, 2), "dinner_only": (2,)}.get(
        meal_scope, (0, 1, 2)
    )
    saved_favorites = [
        meal.get("key")
        for previous in reversed((snapshot or {}).get("weekly_plans") or [])
        for day in previous.get("days") or []
        for meal in day.get("meals") or []
        if meal.get("favorite") and meal.get("key") in MEALS
    ]
    start = _next_monday()
    days = []
    for index, keys in enumerate(STYLE_SCHEDULES[selected_style]):
        current = start + timedelta(days=index)
        planned_keys = list(keys)
        for meal_index in selected_meal_indexes:
            favorite = next(
                (
                    key
                    for key in saved_favorites
                    if key in alternatives_by_position[meal_index]
                    and _compatible(MEALS[key], exclusions)
                    and int(MEALS[key].get("minutes") or 0) <= max_minutes
                ),
                None,
            )
            if favorite and index == meal_index:
                planned_keys[meal_index] = favorite
        meals = [
            _meal(key, exclusions, alternatives_by_position[position], max_minutes)
            for position, key in enumerate(planned_keys)
            if position in selected_meal_indexes
        ]
        for position, meal in zip(selected_meal_indexes, meals):
            meal["meal_type"] = ("breakfast", "lunch", "dinner")[position]
            meal["servings"] = people
            meal["ingredients"] = [{**row, "quantity": round(float(row["quantity"]) * people, 3)} for row in meal["ingredients"]]
        days.append({
            "day": SPANISH_WEEKDAYS[index],
            "date": current.isoformat(),
            "meals": meals,
            "ingredients_ready": False,
            "status": "scheduled",
            "reuse_note": "Roxy reutiliza una base ya preparada para ahorrar tiempo." if index and cook_days <= 2 else "",
        })
    description, focus = STYLE_META[selected_style]
    prep_indexes = sorted({round(index * 6 / max(cook_days - 1, 1)) for index in range(cook_days)})
    if cook_days == 1:
        prep_indexes = [0]
    prep_sessions = []
    for session_index, day_index in enumerate(prep_indexes):
        prep_date = start + timedelta(days=day_index)
        prep_sessions.append({
            "title": "Preparación principal" if session_index == 0 else "Refuerzo de mitad de semana",
            "date": prep_date.isoformat(),
            "minutes": 75 if cook_days == 1 else 45,
            "tasks": [
                "Cocinar las bases de cereales de los próximos días",
                "Preparar y porcionar las proteínas",
                "Lavar y cortar los vegetales",
                "Etiquetar y refrigerar cada preparación",
            ],
        })
    return {
        "style": selected_style,
        "style_description": description,
        "people": people,
        "max_minutes": max_minutes,
        "weekly_budget": round(weekly_budget, 2),
        "cook_days": cook_days,
        "meal_scope": meal_scope if meal_scope in {"all", "lunch_dinner", "dinner_only"} else "all",
        "focus": focus,
        "days": days,
        "prep_tip": f"Roxy organiza {cook_days} {'sesión' if cook_days == 1 else 'sesiones'} de cocina y reutiliza bases durante la semana.",
        "prep_sessions": prep_sessions,
        "generation_source": "local_weekly_catalog",
    }


def weekly_plan_shopping_items(plan: dict[str, Any], excluded_days: set[int] | None = None) -> list[dict[str, Any]]:
    excluded = excluded_days or set()
    totals: dict[tuple[str, str], dict[str, Any]] = {}
    for day_index, day in enumerate(plan.get("days") or []):
        if day_index in excluded or day.get("status") in {"cooked", "leftovers", "skipped"}:
            continue
        for meal in day.get("meals") or []:
            for ingredient in meal.get("ingredients") or []:
                key = (_identity(ingredient.get("name")), str(ingredient.get("unit") or "unidad").casefold())
                if not key[0]:
                    continue
                row = totals.setdefault(key, {"name": ingredient.get("name"), "quantity": 0.0, "unit": ingredient.get("unit") or "unidad"})
                row["quantity"] += float(ingredient.get("quantity") or 0)
    return [{**row, "quantity": round(row["quantity"], 3)} for row in totals.values() if row["quantity"] > 0]


def update_weekly_plan_day(plan: dict[str, Any], *, day_index: int, action: str) -> dict[str, Any]:
    days = plan.get("days") or []
    if not 0 <= day_index < len(days):
        raise ValueError("El día indicado no existe.")
    day = days[day_index]
    if action == "reset":
        swap_index = day.pop("reschedule_swap_with", None)
        if isinstance(swap_index, int) and 0 <= swap_index < len(days):
            day["meals"], days[swap_index]["meals"] = days[swap_index]["meals"], day["meals"]
            days[swap_index].pop("rescheduled_from", None)
        day["status"] = "scheduled"
        day.pop("status_note", None)
        return plan
    if action == "cooked":
        day["status"] = "cooked"
        day["status_note"] = "Ya está preparado; Roxy no volverá a incluir sus ingredientes."
        return plan
    if action == "leftovers":
        day["status"] = "leftovers"
        day["status_note"] = "Este día queda cubierto con sobras y no necesita compras nuevas."
        return plan
    if action == "skip":
        if day.get("status") == "skipped":
            return plan
        next_index = next(
            (
                index
                for index in range(day_index + 1, len(days))
                if days[index].get("status", "scheduled") == "scheduled"
            ),
            None,
        )
        if next_index is not None:
            day["meals"], days[next_index]["meals"] = days[next_index]["meals"], day["meals"]
            day["reschedule_swap_with"] = next_index
            days[next_index]["rescheduled_from"] = day.get("date")
            day["status_note"] = "Roxy movió estas comidas al próximo día disponible."
        else:
            day["status_note"] = "No quedan días disponibles; estas comidas pasan a la próxima semana."
        day["status"] = "skipped"
        return plan
    raise ValueError("La acción del día no es válida.")


def update_weekly_plan_meal(
    plan: dict[str, Any], snapshot: dict[str, Any], *, day_index: int, meal_index: int, action: str
) -> dict[str, Any]:
    days = plan.get("days") or []
    if not 0 <= day_index < len(days) or not 0 <= meal_index < len(days[day_index].get("meals") or []):
        raise ValueError("La comida indicada no existe.")
    current = days[day_index]["meals"][meal_index]
    if action == "favorite":
        current["favorite"] = not bool(current.get("favorite"))
        return plan
    if action != "swap":
        raise ValueError("La acción del plan no es válida.")
    profile = (snapshot or {}).get("profile") or {}
    exclusions = {
        _identity(value)
        for value in [*(profile.get("allergies") or []), *(profile.get("dislikes") or [])]
        if _identity(value)
    }
    max_minutes = int(plan.get("max_minutes") or 180)
    schedule_position = {"breakfast": 0, "lunch": 1, "dinner": 2}.get(str(current.get("meal_type")), meal_index)
    candidates = []
    for schedule in STYLE_SCHEDULES.values():
        for day in schedule:
            key = day[schedule_position]
            if key not in candidates:
                candidates.append(key)
    current_key = str(current.get("key") or "")
    start = candidates.index(current_key) + 1 if current_key in candidates else 0
    ordered = candidates[start:] + candidates[:start]
    replacement = next(
        (
            key
            for key in ordered
            if key != current_key
            and int(MEALS[key].get("minutes") or 0) <= max_minutes
            and _compatible(MEALS[key], exclusions)
        ),
        current_key,
    )
    people = int(plan.get("people") or 1)
    meal = {"key": replacement, **MEALS[replacement], "favorite": False, "meal_type": current.get("meal_type")}
    meal["servings"] = people
    meal["ingredients"] = [
        {**row, "quantity": round(float(row["quantity"]) * people, 3)} for row in meal["ingredients"]
    ]
    days[day_index]["meals"][meal_index] = meal
    return plan
