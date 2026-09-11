from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from datetime import date, timedelta
from math import isclose
from typing import Any

from roxy_os.home_pet_restrictions import matching_restrictions
from roxy_os.home_recipe_fallback import local_recipe_catalog


def _identity(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"[^a-z0-9]+", " ", normalized.encode("ascii", "ignore").decode("ascii").lower()).strip()


# Planning estimates, not recipe instructions or a guarantee for every batch size.
# Include the waiting required by the existing recipes (notably oats and pizza).
# Titles, portions and ingredients always come from the current reviewed catalog.
PLAN_RECIPE_MINUTES = {
    "overnight_oats": 370, "eggs_toast": 15, "avocado_toast": 20,
    "pancakes": 25, "installed_avena_con_manzana": 15, "omelet": 15,
    "chicken": 25, "pasta": 25, "rice": 35, "tuna_bowl": 15,
    "chicken_wrap": 15, "soup": 40, "salad": 15, "quesadilla": 20,
    "picadillo": 40, "pizza": 100, "installed_pollo_alfredo": 35,
}


STYLE_SCHEDULES: dict[str, list[tuple[str, str, str]]] = {
    "normal": [
        ("overnight_oats", "chicken", "chicken_wrap"),
        ("installed_avena_con_manzana", "pasta", "soup"),
        ("eggs_toast", "picadillo", "quesadilla"),
        ("omelet", "rice", "tuna_bowl"),
        ("avocado_toast", "tuna_bowl", "chicken"),
        ("pancakes", "pizza", "salad"),
        ("eggs_toast", "installed_pollo_alfredo", "soup"),
    ],
    "fitness": [
        ("eggs_toast", "chicken", "tuna_bowl"),
        ("overnight_oats", "tuna_bowl", "quesadilla"),
        ("installed_avena_con_manzana", "picadillo", "chicken_wrap"),
        ("omelet", "chicken", "soup"),
        ("avocado_toast", "tuna_bowl", "chicken"),
        ("pancakes", "installed_pollo_alfredo", "salad"),
        ("eggs_toast", "rice", "quesadilla"),
    ],
    "quick": [
        ("installed_avena_con_manzana", "tuna_bowl", "chicken_wrap"),
        ("eggs_toast", "quesadilla", "salad"),
        ("avocado_toast", "tuna_bowl", "quesadilla"),
        ("omelet", "chicken_wrap", "salad"),
        ("eggs_toast", "quesadilla", "chicken_wrap"),
        ("installed_avena_con_manzana", "tuna_bowl", "salad"),
        ("avocado_toast", "chicken_wrap", "quesadilla"),
    ],
    "weight_loss": [
        ("omelet", "tuna_bowl", "soup"),
        ("installed_avena_con_manzana", "chicken", "salad"),
        ("overnight_oats", "rice", "chicken_wrap"),
        ("avocado_toast", "tuna_bowl", "soup"),
        ("eggs_toast", "chicken", "salad"),
        ("installed_avena_con_manzana", "picadillo", "quesadilla"),
        ("omelet", "rice", "soup"),
    ],
}


def _catalog_meals(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Use the same installed editions shown in Recetas, with no saved copies."""
    meals = {}
    for recipe in local_recipe_catalog(snapshot):
        key = str(recipe.get("catalog_key") or "")
        if (
            key not in PLAN_RECIPE_MINUTES
            or recipe.get("audience") == "pet"
            or recipe.get("kind") != "meal"
            or recipe.get("editorial_status") == "needs_canonical_review"
            or not recipe.get("steps")
            or not recipe.get("ingredients")
        ):
            continue
        servings = float(recipe.get("servings") or 0)
        if servings <= 0:
            continue
        meals[key] = {
            "key": key,
            "catalog_key": key,
            "title": recipe["title"],
            "recipe_servings": servings,
            "minutes": PLAN_RECIPE_MINUTES[key],
            "minutes_estimated": True,
            "ingredients": deepcopy(recipe["ingredients"]),
            "favorite": False,
        }
    return meals


STYLE_META = {
    "fitness": ("Más proteína y energía", "Preparar proteínas y bases dos veces esta semana"),
    "normal": ("Variado y equilibrado", "Comer variado sin complicarse"),
    "quick": ("Máximo tiempo disponible", "Cocinar solo 2 veces esta semana"),
    "weight_loss": ("Porciones y saciedad", "Priorizar proteína, vegetales y fibra"),
}

STYLE_BALANCE = {
    "fitness": "Proteína suficiente, carbohidratos útiles y energía para entrenar",
    "normal": "Proteína, vegetales, cereales y variedad durante toda la semana",
    "quick": "Platos completos que se preparan en 20 minutos o menos",
    "weight_loss": "Proteína, vegetales y fibra para porciones saciantes",
}

SPANISH_WEEKDAYS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


def _compatible(meal: dict[str, Any], exclusions: set[str]) -> bool:
    haystack = " " + _identity(meal.get("title")) + " " + " ".join(
        _identity(row.get("name")) for row in meal.get("ingredients") or []
    ) + " "
    # Reuse Home's ingredient aliases (egg/huevo, milk/queso, fish/atún).
    # Only the supplied human restrictions enter this shared pure matcher.
    return not matching_restrictions({"allergies": sorted(exclusions)}, haystack)


def resolve_weekly_meal_recipe(meal: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Read one exact full recipe; never interpret an old plan title as a prompt."""
    failure = "Esta comida del plan no tiene una receta disponible. Cambia esa comida o actualiza el plan."
    saved = [recipe for recipe in snapshot.get("recipes") or [] if isinstance(recipe, dict)]
    recipe_id = str(meal.get("recipe_id") or "")
    catalog_key = str(meal.get("catalog_key") or "")
    if recipe_id:
        recipe = next((row for row in saved if str(row.get("id") or "") == recipe_id), None)
    else:
        catalog = local_recipe_catalog(snapshot)
        if catalog_key:
            recipe = next((row for row in catalog if row.get("catalog_key") == catalog_key), None)
        else:
            title = _identity(meal.get("title"))
            if not title:
                raise ValueError(failure)
            # The current catalog wins over an older saved copy of its title.
            # A failed explicit reference above never reaches this legacy path.
            recipe = next((row for row in [*catalog, *reversed(saved)] if _identity(row.get("title")) == title), None)
    if not recipe or recipe.get("audience") == "pet":
        raise ValueError(failure)
    if (
        recipe.get("editorial_status") == "needs_canonical_review"
        or (recipe.get("provenance") or {}).get("can_cook_from_source") is False
    ):
        raise ValueError("La receta de esta comida necesita revisión antes de cocinar. Cambia esa comida o actualiza el plan.")
    try:
        complete = (
            bool(str(recipe.get("title") or "").strip())
            and 0 < float(recipe.get("servings") or 0) <= 100
            and isinstance(recipe.get("ingredients"), list)
            and bool(recipe["ingredients"])
            and all(
                isinstance(row, dict) and str(row.get("name") or "").strip()
                and str(row.get("unit") or "").strip()
                and not isinstance(row.get("quantity"), bool)
                and 0 < float(row.get("quantity") or 0) <= 100000
                for row in recipe["ingredients"]
            )
            and isinstance(recipe.get("steps"), list)
            and bool(recipe["steps"])
            and all(isinstance(step, str) and step.strip() for step in recipe["steps"])
        )
    except (TypeError, ValueError):
        complete = False
    if not complete:
        raise ValueError(failure)
    profile = snapshot.get("profile") or {}
    exclusions = {
        _identity(value)
        for value in [*(profile.get("allergies") or []), *(profile.get("dislikes") or [])]
        if _identity(value)
    }
    if not _compatible(recipe, exclusions):
        raise ValueError("La receta de esta comida no es compatible con tus restricciones actuales. Cambia esa comida o actualiza el plan.")
    return deepcopy(recipe)


def _meal(
    key: str, catalog: dict[str, dict[str, Any]], exclusions: set[str],
    alternatives: list[str], max_minutes: int, *, avoid: set[str] | None = None,
) -> dict[str, Any]:
    candidates = list(dict.fromkeys([key, *alternatives]))
    avoided = avoid or set()
    candidates.sort(key=lambda candidate: candidate in avoided)
    for candidate in candidates:
        meal = catalog.get(candidate)
        if meal and meal["minutes"] <= max_minutes and _compatible(meal, exclusions):
            return deepcopy(meal)
    raise ValueError(
        "No hay una receta disponible para todas las comidas con estas restricciones y tiempo. "
        "Amplía el tiempo o revisa el alcance del plan; tus alergias se conservan."
    )


def create_local_weekly_plan(
    snapshot: dict[str, Any], *, style: str, people: int, max_minutes: int, weekly_budget: float,
    cook_days: int = 2, meal_scope: str = "all", start_date: date | None = None,
) -> dict[str, Any]:
    selected_style = style if style in STYLE_SCHEDULES else "normal"
    effective_max_minutes = min(max_minutes, 20) if selected_style == "quick" else max_minutes
    profile = (snapshot or {}).get("profile") or {}
    exclusions = {_identity(value) for value in [*(profile.get("allergies") or []), *(profile.get("dislikes") or [])] if _identity(value)}
    catalog = _catalog_meals(snapshot)
    alternatives_by_position = [
        list(dict.fromkeys(day[position] for schedule in STYLE_SCHEDULES.values() for day in schedule))
        for position in range(3)
    ]
    cook_days = max(1, min(7, int(cook_days)))
    selected_meal_indexes = {"all": (0, 1, 2), "lunch_dinner": (1, 2), "dinner_only": (2,)}.get(
        meal_scope, (0, 1, 2)
    )
    favorite_keys_by_title = {_identity(meal["title"]): key for key, meal in catalog.items()}
    saved_favorites = [
        key
        for previous in reversed((snapshot or {}).get("weekly_plans") or [])
        for day in previous.get("days") or []
        for meal in day.get("meals") or []
        for key in [meal.get("catalog_key") or favorite_keys_by_title.get(_identity(meal.get("title")))]
        if meal.get("favorite") and key in catalog
    ]
    # "Hoy" begins with the household's actual day, not the next Monday.
    start = start_date or date.today()
    days = []
    for index, keys in enumerate(STYLE_SCHEDULES[selected_style]):
        current = start + timedelta(days=index)
        planned_keys = list(keys)
        for meal_index in selected_meal_indexes:
            favorite = next(
                (
                    key for key in saved_favorites
                    if key in alternatives_by_position[meal_index]
                    and _compatible(catalog[key], exclusions)
                    and catalog[key]["minutes"] <= effective_max_minutes
                ),
                None,
            )
            if favorite and index == meal_index:
                planned_keys[meal_index] = favorite
        meals = []
        for position in selected_meal_indexes:
            alternatives = alternatives_by_position[position]
            # Rotate alternatives instead of repeating one fallback all week.
            offset = index % len(alternatives)
            meal = _meal(
                planned_keys[position], catalog, exclusions,
                alternatives[offset:] + alternatives[:offset], effective_max_minutes,
                avoid={selected["catalog_key"] for selected in meals},
            )
            meal["meal_type"] = ("breakfast", "lunch", "dinner")[position]
            meal["servings"] = people
            meal["nutrition_goal"] = STYLE_BALANCE[selected_style]
            factor = people / meal["recipe_servings"]
            meal["ingredients"] = [
                {**row, "quantity": round(float(row["quantity"]) * factor, 4)}
                for row in meal["ingredients"]
            ]
            meals.append(meal)
        days.append({
            "day": SPANISH_WEEKDAYS[current.weekday()],
            "date": current.isoformat(),
            "meals": meals,
            "ingredients_ready": False,
            "status": "scheduled",
            "reuse_note": "Revisa qué preparaciones puedes reutilizar siguiendo la receta y su conservación." if index and cook_days <= 2 else "",
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
                "Revisar los ingredientes y pasos de las recetas elegidas",
                "Preparar solo las bases que indique cada receta",
                "Organizar las porciones previstas",
                "Seguir las indicaciones de conservación de cada preparación",
            ],
        })
    return {
        "style": selected_style,
        "style_description": description,
        "people": people,
        "max_minutes": effective_max_minutes,
        "weekly_budget": round(weekly_budget, 2),
        "cook_days": cook_days,
        "meal_scope": meal_scope if meal_scope in {"all", "lunch_dinner", "dinner_only"} else "all",
        "focus": focus,
        "balance_note": STYLE_BALANCE[selected_style],
        "days": days,
        "prep_tip": f"Roxy organiza {cook_days} {'sesión' if cook_days == 1 else 'sesiones'} de cocina; revisa qué recetas se pueden preparar con antelación.",
        "prep_sessions": prep_sessions,
        "time_note": "Tiempos orientativos; las tandas y las cantidades pueden cambiarlos. Consulta los pasos de cada receta.",
        "generation_source": "local_weekly_catalog",
        "recipe_catalog_version": 2,
    }


def validate_weekly_plan_for_shopping(
    plan: dict[str, Any], snapshot: dict[str, Any], excluded_days: set[int] | None = None,
) -> None:
    """Fail before shopping writes when an old plan no longer matches a recipe."""
    catalog = _catalog_meals(snapshot)
    by_title = {_identity(meal["title"]): meal for meal in catalog.values()}
    profile = snapshot.get("profile") or {}
    exclusions = {
        _identity(value)
        for value in [*(profile.get("allergies") or []), *(profile.get("dislikes") or [])]
        if _identity(value)
    }
    excluded = excluded_days or set()
    failure = "Este plan contiene comidas que no coinciden con una receta disponible. Actualiza el plan antes de añadir sus ingredientes a Compra."
    try:
        people = float(plan.get("people") or 0)
        if not 0 < people <= 100:
            raise ValueError(failure)
        for day_index, day in enumerate(plan.get("days") or []):
            if day_index in excluded or day.get("status") in {"cooked", "leftovers", "skipped"}:
                continue
            for meal in day.get("meals") or []:
                # Explicit references never fall back to a different title.
                key = str(meal.get("catalog_key") or "")
                recipe = catalog.get(key) if key else by_title.get(_identity(meal.get("title")))
                if not recipe or _identity(meal.get("title")) != _identity(recipe["title"]):
                    raise ValueError(failure)
                if not _compatible(recipe, exclusions):
                    raise ValueError("Una comida del plan no es compatible con tus restricciones actuales. Actualiza el plan antes de añadirla a Compra.")
                factor = people / recipe["recipe_servings"]
                expected = recipe["ingredients"]
                actual = meal.get("ingredients") or []
                if len(actual) != len(expected):
                    raise ValueError(failure)
                for row, original in zip(actual, expected):
                    if (
                        _identity(row.get("name")) != _identity(original["name"])
                        or _identity(row.get("unit")) != _identity(original["unit"])
                        or isinstance(row.get("quantity"), bool)
                        or not isclose(float(row.get("quantity") or 0), round(float(original["quantity"]) * factor, 4), rel_tol=0, abs_tol=0.00005)
                    ):
                        raise ValueError(failure)
    except (TypeError, KeyError, AttributeError) as exc:
        raise ValueError(failure) from exc


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
    if schedule_position not in (0, 1, 2):
        raise ValueError("El tipo de comida indicado no existe.")
    catalog = _catalog_meals(snapshot)
    candidates = list(dict.fromkeys(
        day[schedule_position] for schedule in STYLE_SCHEDULES.values() for day in schedule
    ))
    # An old plan's generic key must not identify a different recipe edition.
    current_key = str(current.get("catalog_key") or "")
    start = candidates.index(current_key) + 1 if current_key in candidates else 0
    ordered = candidates[start:] + candidates[:start]
    alternatives = [
        key for key in ordered
        if key != current_key
        and key in catalog
        and _identity(catalog[key]["title"]) != _identity(current.get("title"))
    ]
    if not alternatives:
        raise ValueError("No hay otra receta disponible para esta comida.")
    meal = _meal(
        alternatives[0], catalog, exclusions, alternatives[1:], max_minutes,
        avoid={row.get("catalog_key", "") for index, row in enumerate(days[day_index]["meals"]) if index != meal_index},
    )
    people = int(plan.get("people") or 1)
    meal["meal_type"] = current.get("meal_type") or ("breakfast", "lunch", "dinner")[schedule_position]
    meal["servings"] = people
    meal["nutrition_goal"] = plan.get("balance_note") or ""
    factor = people / meal["recipe_servings"]
    meal["ingredients"] = [
        {**row, "quantity": round(float(row["quantity"]) * factor, 4)}
        for row in meal["ingredients"]
    ]
    days[day_index]["meals"][meal_index] = meal
    return plan
