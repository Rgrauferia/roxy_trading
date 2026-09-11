"""Weekly plan links and mutations use exact Home recipes; all data is synthetic."""
from copy import deepcopy
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from roxy_os import home_weekly_plans
from roxy_os.home_food import HomeFoodStore
from roxy_os.shopping_list import ShoppingListStore
from tools import roxy_home_service as service


BASE = "/v1/home-food/weekly_test"
SETTINGS = {"style": "normal", "people": 3, "max_minutes": 40, "weekly_budget": 85,
            "cook_days": 2, "meal_scope": "all"}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-weekly-api-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "weekly_test,other_test")
    monkeypatch.setenv("ROXY_HOME_CONVERSATION_PATH", str(tmp_path / "conversation.json"))
    store = HomeFoodStore(tmp_path / "home.json")
    shopping = ShoppingListStore(tmp_path / "shopping.json")
    store.update_profile("weekly_test", allergies=[], dislikes=[], preferences=[], household_size=2)
    monkeypatch.setattr(service, "_home_food_store", lambda: store)
    monkeypatch.setattr(service, "_store", lambda: shopping)
    monkeypatch.setattr(service, "_schedule_account_recipe_photo", lambda *args: "NOT_NEEDED")
    monkeypatch.setattr(service, "_recipe_library_store", lambda: SimpleNamespace(summary=lambda: {}))
    monkeypatch.setattr(service, "_recipe_photo_queue", lambda: SimpleNamespace(public_status=lambda: {}))
    monkeypatch.setattr(service, "_recipe_video_public_status", lambda: {})
    monkeypatch.setattr(service, "_home_voice_config", lambda: SimpleNamespace(public_status=lambda: {}))
    monkeypatch.setattr(service, "_home_recipe_provider_status", lambda auth: {})
    monkeypatch.setattr(service, "_home_ai", lambda: pytest.fail("Local weekly plans must not call AI"))
    monkeypatch.setattr("requests.get", lambda *a, **kw: pytest.fail("No network in weekly tests"))
    monkeypatch.setattr("requests.post", lambda *a, **kw: pytest.fail("No network in weekly tests"))
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: pytest.fail("No network in weekly tests"))
    service._RATE_STATE.clear()
    with TestClient(service.app, headers={"Authorization": "Bearer synthetic-weekly-api-key"}) as client:
        yield client, store, shopping


@pytest.mark.parametrize("reason", ["missing_catalog", "allergies", "time"])
def test_incompatible_generation_returns_422_before_preferences_or_plan_mutation(api, monkeypatch, reason):
    client, store, _ = api
    previous = store.save_weekly_plan("weekly_test", {"title": "Semana previa", "days": []})
    payload = dict(SETTINGS)
    if reason == "missing_catalog":
        monkeypatch.setattr(home_weekly_plans, "local_recipe_catalog", lambda snapshot: [])
    elif reason == "allergies":
        store.update_profile("weekly_test", allergies=["huevo", "leche", "avena"], dislikes=[], preferences=[], household_size=2)
    else:
        payload["max_minutes"] = 5
    before = store.path.read_bytes()
    snapshot = store.snapshot("weekly_test")
    response = client.post(BASE + "/weekly-plans", json=payload)
    assert response.status_code == 422
    assert store.path.read_bytes() == before
    assert store.snapshot("weekly_test") == snapshot
    assert store.get_weekly_plan("weekly_test", previous["id"]) == previous


@pytest.mark.parametrize("scope", ["all", "lunch_dinner", "dinner_only"])
def test_generated_canonical_keys_and_scaled_ingredients_survive_api_reload(api, scope):
    client, store, _ = api
    response = client.post(BASE + "/weekly-plans", json={**SETTINGS, "meal_scope": scope})
    assert response.status_code == 201
    created = response.json()["plan"]
    assert created["recipe_catalog_version"] == 2
    before = store.path.read_bytes()
    fresh_store = HomeFoodStore(store.path)
    assert fresh_store.get_weekly_plan("weekly_test", created["id"]) == created
    read = client.get(BASE)
    assert read.status_code == 200 and read.headers["Cache-Control"] == "private, no-store"
    snapshot = read.json()
    assert snapshot["recipes"] == []  # Catalog links do not silently create saved copies.
    assert snapshot["weekly_plans"][-1] == created
    catalog = {recipe["catalog_key"]: recipe for recipe in snapshot["local_recipes"]}
    for day in created["days"]:
        for meal in day["meals"]:
            recipe = catalog[meal["catalog_key"]]
            assert meal["title"] == recipe["title"]
            assert recipe.get("audience") != "pet" and recipe.get("kind") == "meal"
            assert recipe.get("editorial_status") != "needs_canonical_review" and recipe["steps"]
            assert meal["servings"] == 3 and meal["recipe_servings"] == recipe["servings"]
            assert meal["ingredients"] == [
                {**ingredient, "quantity": round(ingredient["quantity"] * 3 / recipe["servings"], 4)}
                for ingredient in recipe["ingredients"]
            ]
    assert store.path.read_bytes() == before


def test_future_plan_portions_do_not_rewrite_an_existing_week(api):
    client, store, _ = api
    first = client.post(BASE + "/weekly-plans", json={**SETTINGS, "people": 1}).json()["plan"]
    second = client.post(BASE + "/weekly-plans", json={**SETTINGS, "people": 4}).json()["plan"]
    assert first["id"] != second["id"]
    assert store.get_weekly_plan("weekly_test", first["id"]) == first
    assert first["days"][0]["meals"][0]["catalog_key"] == second["days"][0]["meals"][0]["catalog_key"]
    assert all(meal["servings"] == 1 for day in first["days"] for meal in day["meals"])
    assert all(meal["servings"] == 4 for day in second["days"] for meal in day["meals"])


def test_swap_rechecks_current_allergies_and_preserves_previous_plan_on_failure(api):
    client, store, _ = api
    plan = client.post(BASE + "/weekly-plans", json=SETTINGS).json()["plan"]
    store.update_profile("weekly_test", allergies=["huevo", "leche", "avena"], dislikes=[], preferences=[], household_size=2)
    before = store.path.read_bytes()
    response = client.patch(BASE + f'/weekly-plans/{plan["id"]}/meal',
                            json={"day_index": 0, "meal_index": 0, "action": "swap"})
    assert response.status_code == 422
    assert store.path.read_bytes() == before
    assert store.get_weekly_plan("weekly_test", plan["id"]) == plan


def test_swap_resolves_one_legacy_meal_and_keeps_the_rest_of_week(api):
    client, store, _ = api
    old = store.save_weekly_plan("weekly_test", {
        "title": "Semana antigua", "people": 3, "max_minutes": 40, "days": [{"meals": [
            {"key": "spaghetti", "title": "Espaguetis con salsa casera", "meal_type": "lunch"},
            {"key": "salmon", "title": "Salmón al horno con vegetales", "meal_type": "dinner"},
        ]}],
    })
    response = client.patch(BASE + f'/weekly-plans/{old["id"]}/meal',
                            json={"day_index": 0, "meal_index": 0, "action": "swap"})
    assert response.status_code == 200
    updated = response.json()["plan"]
    assert updated["days"][0]["meals"][1] == old["days"][0]["meals"][1]
    assert updated["days"][0]["meals"][0]["catalog_key"]
    assert store.get_weekly_plan("weekly_test", old["id"]) == updated


def test_shopping_rejects_unresolved_legacy_meal_without_partial_additions(api):
    client, store, shopping = api
    plan = client.post(BASE + "/weekly-plans", json=SETTINGS).json()["plan"]
    invalid = deepcopy(plan)
    invalid["days"][-1]["meals"][-1] = {
        "key": "salmon", "title": "Salmón al horno con vegetales", "meal_type": "dinner",
        "ingredients": [{"name": "Pescado supuesto", "quantity": 2, "unit": "filete"}],
    }
    store.replace_weekly_plan("weekly_test", plan["id"], invalid)
    prior_item = shopping.add("weekly_test", "Producto previo", quantity=1, unit="unidad")
    before = store.path.read_bytes()
    response = client.post(BASE + f'/weekly-plans/{plan["id"]}/shopping-commit', json={"confirmed": True})
    assert response.status_code == 422
    assert shopping.list_items("weekly_test") == [prior_item]
    assert store.path.read_bytes() == before


def test_shopping_rechecks_allergies_added_after_plan_creation(api):
    client, store, shopping = api
    plan = client.post(BASE + "/weekly-plans", json=SETTINGS).json()["plan"]
    ingredient = plan["days"][0]["meals"][0]["ingredients"][0]["name"]
    store.update_profile("weekly_test", allergies=[ingredient], dislikes=[], preferences=[], household_size=2)
    before = store.path.read_bytes()
    response = client.post(BASE + f'/weekly-plans/{plan["id"]}/shopping-commit', json={"confirmed": True})
    assert response.status_code == 422
    assert shopping.list_items("weekly_test") == []
    assert store.path.read_bytes() == before


def test_current_plan_shopping_requires_confirmation_and_uses_scaled_source_quantities(api):
    client, store, shopping = api
    plan = client.post(BASE + "/weekly-plans", json=SETTINGS).json()["plan"]
    path = BASE + f'/weekly-plans/{plan["id"]}/shopping-commit'
    assert client.post(path, json={"confirmed": False}).status_code == 409
    assert shopping.list_items("weekly_test") == []
    before = store.path.read_bytes()
    response = client.post(path, json={"confirmed": True})
    assert response.status_code == 200
    expected = home_weekly_plans.weekly_plan_shopping_items(plan)
    assert len(response.json()["items"]) == len(expected)
    assert all(item["source"] == "roxy_home_weekly_plan" for item in response.json()["items"])
    for actual, ingredient in zip(response.json()["items"], expected):
        assert actual["name"] == ingredient["name"]
        assert actual["quantity"] == ingredient["quantity"]
        assert actual["unit"] == ingredient["unit"]
    assert store.path.read_bytes() == before


def test_excluded_unresolved_day_does_not_block_confirmed_remaining_recipes(api):
    client, store, _ = api
    plan = client.post(BASE + "/weekly-plans", json=SETTINGS).json()["plan"]
    plan["days"][-1]["meals"][-1] = {"title": "Comida sin receta", "ingredients": []}
    store.replace_weekly_plan("weekly_test", plan["id"], plan)
    response = client.post(BASE + f'/weekly-plans/{plan["id"]}/shopping-commit',
                           json={"confirmed": True, "excluded_days": [6]})
    assert response.status_code == 200
    assert len(response.json()["items"]) == len(home_weekly_plans.weekly_plan_shopping_items(plan, {6}))


def test_existing_plan_keeps_adjustment_summary_questionnaire_and_submit_reachable():
    assets = Path(__file__).resolve().parents[1] / "assets"
    css = (assets / "roxy_list.css").read_text()
    html = (assets / "roxy_list.html").read_text()
    # Regression: these three selectors used to hide every route to updating an
    # existing week, including after its recovery notice opened the details.
    protected = {".meal-plan-setup.has-plan > summary", ".meal-plan-setup.has-plan .meal-plan-questionnaire",
                 ".meal-plan-setup.has-plan #mealPlanCreate"}
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        selected = {re.sub(r"\s+", " ", selector.strip()) for selector in selectors.split(",")}
        if selected & protected:
            assert not re.search(r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)\b", body)
    for pattern in (r'<details\b[^>]*\bid="mealPlanSetup"[^>]*>',
                    r'<details\b[^>]*\bclass="meal-plan-questionnaire"[^>]*>',
                    r'<button\b[^>]*\bid="mealPlanCreate"[^>]*>'):
        tag = re.search(pattern, html)
        assert tag and not re.search(r"\b(?:hidden|disabled)(?:\s|=|>)", tag[0])


def test_conversational_legacy_recipe_request_returns_422_without_saving_or_model_calls(api, monkeypatch):
    client, store, _ = api
    store.save_weekly_plan("weekly_test", {
        "people": 3, "days": [{"meals": [
            {"key": "chicken_rice", "title": "Pollo al ajo con arroz", "meal_type": "dinner",
             "ingredients": [{"name": "Pollo supuesto", "quantity": 3, "unit": "unidad"}]},
        ]}],
    })
    monkeypatch.setattr(service, "_recipe_with_resilience", lambda *a, **kw: pytest.fail("Exact planned recipes must not use aliases or models"))
    before = store.path.read_bytes()
    response = client.post("/v1/assistant/command/weekly_test", json={"text": "dame la receta de la cena de hoy"})
    assert response.status_code == 422
    assert store.path.read_bytes() == before
    assert store.snapshot("weekly_test")["recipes"] == []


def test_conversational_canonical_recipe_request_saves_exact_source_title_and_steps(api, monkeypatch):
    client, store, _ = api
    plan = client.post(BASE + "/weekly-plans", json=SETTINGS).json()["plan"]
    meal = next(row for row in plan["days"][0]["meals"] if row["meal_type"] == "dinner")
    original = next(recipe for recipe in home_weekly_plans.local_recipe_catalog(store.snapshot("weekly_test"))
                    if recipe["catalog_key"] == meal["catalog_key"])
    monkeypatch.setattr(service, "_recipe_with_resilience", lambda *a, **kw: pytest.fail("Exact planned recipes must not use aliases or models"))
    response = client.post("/v1/assistant/command/weekly_test", json={"text": "dame la receta de la cena de hoy"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "weekly_recipe"
    assert payload["data"]["generation_mode"] == "weekly_exact_recipe"
    recipe = payload["data"]["recipe"]
    assert recipe["title"] == meal["title"] == original["title"]
    assert recipe["steps"] == original["steps"]
    saved = store.snapshot("weekly_test")["recipes"][0]
    for field in ("id", "title", "steps", "ingredients", "servings"):
        assert saved[field] == recipe[field]
    assert store.get_weekly_plan("weekly_test", plan["id"]) == plan


def test_conversational_plan_generation_incompatibility_is_422_without_writes(api, monkeypatch):
    client, store, _ = api
    monkeypatch.setattr(home_weekly_plans, "local_recipe_catalog", lambda snapshot: [])
    before = store.path.read_bytes()
    response = client.post("/v1/assistant/command/weekly_test", json={"text": "Roxy, organiza nuestro plan de comidas de la semana"})
    assert response.status_code == 422
    assert store.path.read_bytes() == before
