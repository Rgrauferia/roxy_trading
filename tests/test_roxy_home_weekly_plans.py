from datetime import date
from copy import deepcopy

import pytest

from roxy_os.home_recipe_fallback import local_recipe_catalog
from roxy_os.home_weekly_plans import create_local_weekly_plan, resolve_weekly_meal_recipe, update_weekly_plan_day, update_weekly_plan_meal, validate_weekly_plan_for_shopping, weekly_plan_shopping_items
from tools.roxy_home_service import _weekly_day_index


def test_weekly_styles_generate_complete_real_meals_without_openai():
    snapshot = {"profile": {"allergies": [], "dislikes": []}}
    for style in ("fitness", "normal", "quick", "weight_loss"):
        plan = create_local_weekly_plan(
            snapshot,
            style=style,
            people=2,
            max_minutes=20 if style == "quick" else 40,
            weekly_budget=85,
            start_date=date(2026, 8, 22),
        )
        assert plan["style"] == style
        assert len(plan["days"]) == 7
        assert all(len(day["meals"]) == 3 for day in plan["days"])
        assert all(meal["ingredients"] or meal["key"] == "leftovers" for day in plan["days"] for meal in day["meals"])
        assert all(meal["nutrition_goal"] == plan["balance_note"] for day in plan["days"] for meal in day["meals"])
        assert plan["days"][0]["date"] == "2026-08-22"
        assert plan["days"][0]["day"] == "Sábado"


def test_weekly_styles_apply_distinct_health_rules():
    quick = create_local_weekly_plan({}, style="quick", people=2, max_minutes=45, weekly_budget=85)
    fitness = create_local_weekly_plan({}, style="fitness", people=2, max_minutes=40, weekly_budget=85)
    normal = create_local_weekly_plan({}, style="normal", people=2, max_minutes=40, weekly_budget=85)
    weight_loss = create_local_weekly_plan({}, style="weight_loss", people=2, max_minutes=40, weekly_budget=85)

    assert quick["max_minutes"] == 20
    assert all(meal["minutes"] <= 20 for day in quick["days"] for meal in day["meals"])
    assert "Proteína suficiente" in fitness["balance_note"]
    assert "variedad" in normal["balance_note"]
    assert "saciantes" in weight_loss["balance_note"]
    assert [meal["key"] for meal in fitness["days"][0]["meals"]] != [meal["key"] for meal in weight_loss["days"][0]["meals"]]


def test_spoken_weekly_days_follow_plan_starting_today():
    plan = create_local_weekly_plan(
        {}, style="normal", people=2, max_minutes=40, weekly_budget=85,
        start_date=date(2026, 8, 22),
    )
    assert _weekly_day_index("hoy", plan, current=date(2026, 8, 22)) == 0
    assert _weekly_day_index("mañana", plan, current=date(2026, 8, 22)) == 1
    assert _weekly_day_index("el lunes", plan, current=date(2026, 8, 22)) == 2


def test_weekly_plan_scales_household_and_can_exclude_ready_days():
    one = create_local_weekly_plan({}, style="normal", people=1, max_minutes=40, weekly_budget=80)
    two = create_local_weekly_plan({}, style="normal", people=2, max_minutes=40, weekly_budget=80)
    one_items = weekly_plan_shopping_items(one)
    two_items = weekly_plan_shopping_items(two)
    one_arroz = next(row for row in one_items if row["name"] == "Arroz")
    two_arroz = next(row for row in two_items if row["name"] == "Arroz")
    without_monday = weekly_plan_shopping_items(two, {0})

    assert two_arroz["quantity"] == pytest.approx(one_arroz["quantity"] * 2, abs=0.002)
    assert sum(row["quantity"] for row in without_monday) < sum(row["quantity"] for row in two_items)


def test_weekly_plan_avoids_registered_allergy_when_possible():
    plan = create_local_weekly_plan(
        {"profile": {"allergies": ["huevo"], "dislikes": []}},
        style="normal",
        people=2,
        max_minutes=30,
        weekly_budget=85,
    )
    ingredients = " ".join(
        row["name"].lower()
        for day in plan["days"]
        for meal in day["meals"]
        for row in meal["ingredients"]
    )
    assert "huevo" not in ingredients


def test_weekly_plan_can_focus_on_two_meals_and_build_batch_sessions():
    plan = create_local_weekly_plan(
        {},
        style="quick",
        people=2,
        max_minutes=20,
        weekly_budget=85,
        cook_days=2,
        meal_scope="lunch_dinner",
    )

    assert all([meal["meal_type"] for meal in day["meals"]] == ["lunch", "dinner"] for day in plan["days"])
    assert len(plan["prep_sessions"]) == 2
    assert all(session["tasks"] for session in plan["prep_sessions"])
    assert plan["days"][1]["reuse_note"]


def test_live_week_reschedules_skipped_day_and_excludes_covered_days_from_shopping():
    plan = create_local_weekly_plan({}, style="normal", people=2, max_minutes=40, weekly_budget=85)
    monday_titles = [meal["title"] for meal in plan["days"][0]["meals"]]
    tuesday_titles = [meal["title"] for meal in plan["days"][1]["meals"]]
    full_items = weekly_plan_shopping_items(plan)

    update_weekly_plan_day(plan, day_index=0, action="skip")
    assert plan["days"][0]["status"] == "skipped"
    assert [meal["title"] for meal in plan["days"][1]["meals"]] == monday_titles
    assert [meal["title"] for meal in plan["days"][0]["meals"]] == tuesday_titles
    assert len(weekly_plan_shopping_items(plan)) <= len(full_items)

    update_weekly_plan_day(plan, day_index=0, action="reset")
    assert plan["days"][0]["status"] == "scheduled"
    assert [meal["title"] for meal in plan["days"][0]["meals"]] == monday_titles

    update_weekly_plan_day(plan, day_index=1, action="leftovers")
    assert plan["days"][1]["status"] == "leftovers"
    assert sum(row["quantity"] for row in weekly_plan_shopping_items(plan)) < sum(row["quantity"] for row in full_items)


@pytest.mark.parametrize("style", ["normal", "quick", "fitness", "weight_loss"])
def test_every_planned_meal_opens_exact_current_recipe_and_uses_its_portions(style):
    catalog = {recipe["catalog_key"]: recipe for recipe in local_recipe_catalog({})}
    plan = create_local_weekly_plan({}, style=style, people=3, max_minutes=40, weekly_budget=85)
    for day in plan["days"]:
        for meal in day["meals"]:
            recipe = catalog[meal["catalog_key"]]
            assert meal["title"] == recipe["title"]
            assert recipe.get("audience") != "pet"
            assert recipe.get("editorial_status") != "needs_canonical_review"
            assert recipe["steps"]
            assert meal["recipe_servings"] == recipe["servings"]
            assert meal["ingredients"] == [
                {**row, "quantity": round(row["quantity"] * 3 / recipe["servings"], 4)}
                for row in recipe["ingredients"]
            ]
            assert meal["minutes_estimated"] is True
    assert plan["recipe_catalog_version"] == 2


def test_time_limit_includes_long_waits_from_actual_recipe():
    quick = create_local_weekly_plan({}, style="quick", people=2, max_minutes=20, weekly_budget=85)
    assert not {"overnight_oats", "pizza"} & {
        meal["catalog_key"] for day in quick["days"] for meal in day["meals"]
    }
    normal = create_local_weekly_plan({}, style="normal", people=2, max_minutes=400, weekly_budget=85)
    oats = next(meal for day in normal["days"] for meal in day["meals"] if meal["catalog_key"] == "overnight_oats")
    assert oats["minutes"] >= 360


def test_plan_cannot_reintroduce_a_recipe_that_now_requires_review(monkeypatch):
    from roxy_os import home_weekly_plans

    catalog = local_recipe_catalog({})
    for recipe in catalog:
        if recipe["catalog_key"] == "tuna_bowl":
            recipe["editorial_status"] = "needs_canonical_review"
    monkeypatch.setattr(home_weekly_plans, "local_recipe_catalog", lambda snapshot: catalog)
    plan = create_local_weekly_plan({}, style="quick", people=2, max_minutes=20, weekly_budget=85)
    assert all(meal["catalog_key"] != "tuna_bowl" for day in plan["days"] for meal in day["meals"])


def test_no_available_recipes_is_explicit_and_preserves_the_previous_plan(monkeypatch):
    from roxy_os import home_weekly_plans

    previous = {"id": "saved-week", "days": [{"meals": [{"title": "Mi receta anterior"}]}]}
    snapshot = {"weekly_plans": [previous]}
    before = deepcopy(snapshot)
    monkeypatch.setattr(home_weekly_plans, "local_recipe_catalog", lambda snapshot: [])
    with pytest.raises(ValueError, match="No hay una receta disponible"):
        create_local_weekly_plan(snapshot, style="normal", people=2, max_minutes=40, weekly_budget=85)
    assert snapshot == before


def test_swapping_an_old_unresolvable_title_changes_only_the_requested_meal():
    old = {
        "people": 2, "max_minutes": 40,
        "days": [{"meals": [
            {"key": "spaghetti", "title": "Espaguetis con salsa casera", "meal_type": "lunch"},
            {"key": "salmon", "title": "Salmón al horno con vegetales", "meal_type": "dinner"},
        ]}],
    }
    untouched = deepcopy(old["days"][0]["meals"][1])
    changed = update_weekly_plan_meal(old, {}, day_index=0, meal_index=0, action="swap")
    meal = changed["days"][0]["meals"][0]
    recipe = next(recipe for recipe in local_recipe_catalog({}) if recipe["catalog_key"] == meal["catalog_key"])
    assert recipe["title"] == meal["title"]
    assert recipe.get("editorial_status") != "needs_canonical_review"
    assert changed["days"][0]["meals"][1] == untouched


def test_swap_rechecks_allergy_and_never_restores_an_incompatible_current_recipe():
    plan = create_local_weekly_plan({}, style="quick", people=2, max_minutes=20, weekly_budget=85)
    old = deepcopy(plan)
    with pytest.raises(ValueError, match="No hay una receta disponible"):
        update_weekly_plan_meal(
            plan, {"profile": {"allergies": ["huevo", "leche", "avena"]}},
            day_index=0, meal_index=0, action="swap",
        )
    assert plan == old


def test_default_week_avoids_duplicate_meals_in_a_day_when_alternatives_exist():
    plan = create_local_weekly_plan({}, style="normal", people=2, max_minutes=25, weekly_budget=85)
    assert all(len({meal["catalog_key"] for meal in day["meals"]}) == 3 for day in plan["days"])


@pytest.mark.parametrize("restriction", ["huevos", "eggs", "milk", "lácteos", "pescado"])
def test_planning_uses_existing_ingredient_aliases(restriction):
    from roxy_os.home_pet_restrictions import matching_restrictions

    plan = create_local_weekly_plan(
        {"profile": {"allergies": [restriction]}},
        style="normal", people=2, max_minutes=40, weekly_budget=85,
    )
    for day in plan["days"]:
        for meal in day["meals"]:
            assert not matching_restrictions({"allergies": [restriction]}, " ".join(row["name"] for row in meal["ingredients"]))


def test_shopping_validates_every_included_recipe_before_returning():
    plan = create_local_weekly_plan({}, style="normal", people=3, max_minutes=40, weekly_budget=85)
    assert validate_weekly_plan_for_shopping(plan, {}) is None
    damaged = deepcopy(plan)
    damaged["days"][-1]["meals"][-1]["ingredients"][0]["quantity"] += 1
    with pytest.raises(ValueError, match="Actualiza el plan"):
        validate_weekly_plan_for_shopping(damaged, {})
    assert validate_weekly_plan_for_shopping(damaged, {}, {6}) is None


def test_legacy_shopping_requires_exact_title_and_canonical_ingredients():
    plan = create_local_weekly_plan({}, style="normal", people=2, max_minutes=40, weekly_budget=85)
    for day in plan["days"]:
        for meal in day["meals"]:
            meal.pop("catalog_key")
    assert validate_weekly_plan_for_shopping(plan, {}) is None
    plan["days"][0]["meals"][0]["title"] = "Espaguetis con salsa casera"
    with pytest.raises(ValueError, match="Actualiza el plan"):
        validate_weekly_plan_for_shopping(plan, {})


def test_shopping_rechecks_the_current_profile_and_explicit_unknown_key():
    plan = create_local_weekly_plan({}, style="quick", people=2, max_minutes=20, weekly_budget=85)
    with pytest.raises(ValueError, match="restricciones actuales"):
        validate_weekly_plan_for_shopping(plan, {"profile": {"allergies": ["huevo"]}})
    plan["days"][0]["meals"][0]["catalog_key"] = "missing-source"
    with pytest.raises(ValueError, match="Actualiza el plan"):
        validate_weekly_plan_for_shopping(plan, {})


def test_exact_legacy_favorite_survives_without_reusing_ambiguous_old_keys():
    snapshot = {"weekly_plans": [{"days": [{"meals": [{
        "key": "pancakes", "title": "Panqueques de avena", "favorite": True,
    }]}]}]}
    before = deepcopy(snapshot)
    plan = create_local_weekly_plan(snapshot, style="normal", people=2, max_minutes=400, weekly_budget=85)
    assert plan["days"][0]["meals"][0]["catalog_key"] == "pancakes"
    assert snapshot == before
    snapshot["weekly_plans"][0]["days"][0]["meals"][0].update(key="omelet", title="Tortilla de vegetales")
    plan = create_local_weekly_plan(snapshot, style="normal", people=2, max_minutes=400, weekly_budget=85)
    assert plan["days"][0]["meals"][0]["catalog_key"] == "overnight_oats"


def test_weekly_recipe_resolver_returns_full_exact_catalog_and_does_not_mutate():
    catalog = {recipe["catalog_key"]: recipe for recipe in local_recipe_catalog({})}
    plan = create_local_weekly_plan({}, style="normal", people=2, max_minutes=40, weekly_budget=85)
    before = deepcopy(plan)
    for day in plan["days"]:
        for meal in day["meals"]:
            recipe = resolve_weekly_meal_recipe(meal, {})
            assert recipe == catalog[meal["catalog_key"]]
    assert plan == before
    recipe["steps"].clear()
    assert catalog[meal["catalog_key"]]["steps"]


@pytest.mark.parametrize("reference", [{"recipe_id": "missing"}, {"catalog_key": "missing"}])
def test_weekly_recipe_missing_explicit_reference_never_falls_back_by_title(reference):
    meal = {"title": "Huevos con tostada integral", **reference}
    with pytest.raises(ValueError, match="no tiene una receta disponible"):
        resolve_weekly_meal_recipe(meal, {})


def test_weekly_recipe_legacy_lookup_is_exact_and_prefers_canonical_edition():
    canonical = next(recipe for recipe in local_recipe_catalog({}) if recipe["catalog_key"] == "eggs_toast")
    saved = {**deepcopy(canonical), "id": "saved", "steps": ["Paso distinto guardado"]}
    snapshot = {"recipes": [saved]}
    assert resolve_weekly_meal_recipe({"title": "  HUEVOS con tostada integral! "}, snapshot) == canonical
    assert resolve_weekly_meal_recipe({"recipe_id": "saved", "catalog_key": "eggs_toast"}, snapshot) == saved
    with pytest.raises(ValueError, match="no tiene una receta disponible"):
        resolve_weekly_meal_recipe({"title": "Huevos con tostada integral y tomate"}, snapshot)
    with pytest.raises(ValueError, match="no tiene una receta disponible"):
        resolve_weekly_meal_recipe({"key": "omelet", "title": "Tortilla de vegetales"}, {})


def test_weekly_recipe_resolver_rechecks_allergy_and_catalog_review():
    with pytest.raises(ValueError, match="restricciones actuales"):
        resolve_weekly_meal_recipe({"catalog_key": "omelet"}, {"profile": {"allergies": ["milk"]}})
    with pytest.raises(ValueError, match="necesita revisión"):
        resolve_weekly_meal_recipe({"catalog_key": "installed_salmon_al_horno"}, {})


@pytest.mark.parametrize("mutation", [
    {"audience": "pet"}, {"steps": []}, {"ingredients": []},
    {"editorial_status": "needs_canonical_review"},
    {"provenance": {"can_cook_from_source": False}},
])
def test_weekly_recipe_resolver_keeps_saved_recipe_gates(mutation):
    recipe = next(recipe for recipe in local_recipe_catalog({}) if recipe["catalog_key"] == "eggs_toast")
    recipe.update(id="saved", **mutation)
    snapshot = {"recipes": [recipe]}
    before = deepcopy(snapshot)
    with pytest.raises(ValueError):
        resolve_weekly_meal_recipe({"recipe_id": "saved"}, snapshot)
    assert snapshot == before


def test_weekly_recipe_legacy_saved_title_is_read_only_and_never_crosses_households():
    recipe = next(recipe for recipe in local_recipe_catalog({}) if recipe["catalog_key"] == "eggs_toast")
    recipe.update(id="private", title="Mi desayuno guardado")
    assert resolve_weekly_meal_recipe({"title": "Mi desayuno guardado"}, {"recipes": [recipe]}) == recipe
    with pytest.raises(ValueError):
        resolve_weekly_meal_recipe({"title": "Mi desayuno guardado"}, {"recipes": []})
