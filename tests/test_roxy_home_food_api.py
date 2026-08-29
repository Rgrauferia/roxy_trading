from pathlib import Path

from fastapi.testclient import TestClient

from roxy_os.home_food import cooking_step_timer_seconds


def test_cooking_step_timer_detects_wait_time_without_confusing_oven_temperature():
    assert cooking_step_timer_seconds("Deja reposar 30 minutos mientras calientas el horno a 220 °C.") == 1800
    assert cooking_step_timer_seconds("Hornea 1 hora y 15 minutos.") == 4500
    assert cooking_step_timer_seconds("Mezcla hasta formar una masa uniforme.") == 0


def test_local_catalog_includes_species_specific_pet_recipes_with_safety_notes():
    from roxy_os.home_recipe_fallback import local_recipe_catalog

    rows = [row for row in local_recipe_catalog({}) if row.get("audience") == "pet"]
    assert len(rows) == 12
    assert {row["pet_species"] for row in rows} == {"dog", "cat", "ferret"}
    assert {species: sum(row["pet_species"] == species for row in rows) for species in ("dog", "cat", "ferret")} == {"dog": 4, "cat": 4, "ferret": 4}
    assert all(row["safety_class"] == "treat" for row in rows)
    assert all("no sustituye" in row["veterinary_note"].lower() for row in rows)
    assert all(row["photo_asset"].startswith("/assets/roxy_home/recipes/pets/") for row in rows)
    assert len({row["photo_asset"] for row in rows}) == len(rows)
    assert all(len(row["steps"]) >= 5 for row in rows)
    assert all(Path(row["photo_asset"].removeprefix("/")).is_file() for row in rows)


class FakeHomeAI:
    def generate_recipe(self, prompt, snapshot, *, deep=False):
        return {
            "title": "Pasta de Roxy",
            "description": prompt,
            "servings": 2,
            "ingredients": [{"name": "Pasta", "quantity": 1, "unit": "paquete"}],
            "steps": ["Cocinar la pasta"],
            "allergen_notes": [],
        }

    def import_recipe(self, source, snapshot, *, source_type, audience="human", pet_species=""):
        return {
            "title": "Premios de calabaza para perros" if audience == "pet" else "Avena de la abuela",
            "description": "Receta importada para revisar.",
            "kind": "other" if audience == "pet" else "meal",
            "servings": 8 if audience == "pet" else 2,
            "ingredients": [{"name": "Calabaza" if audience == "pet" else "Avena", "quantity": 1, "unit": "taza"}],
            "steps": ["Mezcla los ingredientes.", "Cocina hasta que estén listos."],
            "allergen_notes": [], "audience": audience, "pet_species": pet_species,
            "safety_class": "treat" if audience == "pet" else "",
            "veterinary_note": "Premio ocasional; no sustituye una dieta completa." if audience == "pet" else "",
        }


def test_home_food_api_requires_confirmation_before_touching_shopping_list(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: FakeHomeAI())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    profile = client.put(
        "/v1/home-food/robert/profile",
        headers=headers,
        json={"preferences": ["Mediterránea"], "allergies": ["Nueces"], "household_size": 2},
    )
    recipe_response = client.post(
        "/v1/home-food/robert/recipes",
        headers=headers,
        json={"prompt": "Una cena rápida", "mode": "routine"},
    )
    recipe_id = recipe_response.json()["recipe"]["id"]
    blocked = client.post(
        f"/v1/home-food/robert/recipes/{recipe_id}/shopping-commit",
        headers=headers,
        json={"confirmed": False},
    )
    before = client.get("/v1/shopping/robert", headers=headers)
    committed = client.post(
        f"/v1/home-food/robert/recipes/{recipe_id}/shopping-commit",
        headers=headers,
        json={"confirmed": True},
    )
    after = client.get("/v1/shopping/robert", headers=headers)
    isolated = client.get("/v1/home-food/alice", headers=headers)

    assert profile.status_code == 200
    assert recipe_response.status_code == 201
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "CONFIRMATION_REQUIRED"
    assert before.json()["items"] == []
    assert committed.json()["status"] == "ADDED"
    assert after.json()["items"][0]["name"] == "Pasta"
    assert isolated.json()["recipes"] == []


def test_recipe_import_is_reviewed_before_save_and_pet_profile_syncs(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: FakeHomeAI())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    pet = client.post("/v1/home-food/robert/pets", headers=headers, json={"name": "Luna", "species": "dog"})
    preview = client.post("/v1/home-food/robert/recipe-imports", headers=headers, json={
        "source_type": "image", "source": "data:image/jpeg;base64,AA==", "audience": "pet", "pet_species": "dog",
    })
    blocked = client.post("/v1/home-food/robert/recipe-imports/commit", headers=headers, json={"confirmed": False, "recipe": preview.json()["recipe"]})
    committed = client.post("/v1/home-food/robert/recipe-imports/commit", headers=headers, json={"confirmed": True, "recipe": preview.json()["recipe"]})
    robert = client.get("/v1/home-food/robert", headers=headers).json()
    alice = client.get("/v1/home-food/alice", headers=headers).json()

    assert pet.status_code == 201
    assert preview.status_code == 200 and preview.json()["status"] == "READY_FOR_REVIEW"
    assert preview.json()["recipe"]["safety_class"] == "treat"
    assert blocked.status_code == 409
    assert committed.status_code == 201
    assert robert["pets"] == [pet.json()["pet"]]
    assert robert["recipes"][0]["pet_species"] == "dog"
    assert alice["pets"] == [] and alice["recipes"] == []


def test_weekly_plan_is_local_persistent_and_requires_confirmation_for_shopping(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    created = client.post(
        "/v1/home-food/robert/weekly-plans",
        headers=headers,
        json={"style": "quick", "people": 2, "max_minutes": 20, "weekly_budget": 85, "cook_days": 2, "meal_scope": "lunch_dinner"},
    )
    assert created.status_code == 201
    plan = created.json()["plan"]
    assert plan["generation_source"] == "local_weekly_catalog"
    assert len(plan["days"]) == 7
    assert all(len(day["meals"]) == 2 for day in plan["days"])
    assert all([meal["meal_type"] for meal in day["meals"]] == ["lunch", "dinner"] for day in plan["days"])
    assert len(plan["prep_sessions"]) == 2
    assert max(meal["minutes"] for day in plan["days"] for meal in day["meals"]) <= 20

    original_title = plan["days"][0]["meals"][0]["title"]
    swapped = client.patch(
        f"/v1/home-food/robert/weekly-plans/{plan['id']}/meal",
        headers=headers,
        json={"day_index": 0, "meal_index": 0, "action": "swap"},
    )
    assert swapped.status_code == 200
    assert swapped.json()["plan"]["days"][0]["meals"][0]["title"] != original_title
    favorite = client.patch(
        f"/v1/home-food/robert/weekly-plans/{plan['id']}/meal",
        headers=headers,
        json={"day_index": 0, "meal_index": 0, "action": "favorite"},
    )
    assert favorite.status_code == 200
    assert favorite.json()["plan"]["days"][0]["meals"][0]["favorite"] is True

    lived = client.patch(
        f"/v1/home-food/robert/weekly-plans/{plan['id']}/day",
        headers=headers,
        json={"day_index": 1, "action": "leftovers"},
    )
    assert lived.status_code == 200
    assert lived.json()["plan"]["days"][1]["status"] == "leftovers"
    assert lived.json()["shopping_preview"]

    blocked = client.post(
        f"/v1/home-food/robert/weekly-plans/{plan['id']}/shopping-commit",
        headers=headers,
        json={"confirmed": False, "excluded_days": []},
    )
    committed = client.post(
        f"/v1/home-food/robert/weekly-plans/{plan['id']}/shopping-commit",
        headers=headers,
        json={"confirmed": True, "excluded_days": [0]},
    )
    robert = client.get("/v1/home-food/robert", headers=headers).json()
    alice = client.get("/v1/home-food/alice", headers=headers).json()

    assert blocked.status_code == 409
    assert committed.status_code == 200
    assert committed.json()["items"]
    assert robert["weekly_plans"][-1]["id"] == plan["id"]
    assert robert["weekly_plans"][-1]["days"][1]["status"] == "leftovers"
    assert robert["meal_planning"]["cook_days"] == 2
    assert robert["meal_planning"]["meal_scope"] == "lunch_dinner"
    assert alice["weekly_plans"] == []


def test_roxy_conversation_controls_days_and_reuses_available_recipes(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    created = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, organiza nuestro plan de comidas de la semana"},
    )
    assert created.status_code == 200
    assert created.json()["intent"] == "weekly_create"
    assert created.json()["agent"] == "home_food"

    monday = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, ¿qué comemos el lunes?"},
    )
    assert monday.status_code == 200
    assert monday.json()["intent"] == "weekly_query"
    assert "Para Lunes" in monday.json()["speech"]

    skipped = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, el martes no voy a cocinar"},
    )
    assert skipped.status_code == 200
    skipped_plan = skipped.json()["data"]["weekly_plan"]
    assert skipped_plan["days"][roxy_home_service._weekly_day_index("martes", skipped_plan)]["status"] == "skipped"

    leftovers = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, el miércoles comeremos las sobras"},
    )
    assert leftovers.status_code == 200
    leftovers_plan = leftovers.json()["data"]["weekly_plan"]
    assert leftovers_plan["days"][roxy_home_service._weekly_day_index("miércoles", leftovers_plan)]["status"] == "leftovers"

    recipe = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, dame la receta de la cena del jueves"},
    )
    assert recipe.status_code == 200
    assert recipe.json()["intent"] == "weekly_recipe"
    assert recipe.json()["data"]["recipe"]["steps"]
    assert recipe.json()["data"]["generation_mode"] == "local_recipe_catalog"

    adapted = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, hoy no cociné, tengo pollo y arroz"},
    )
    assert adapted.status_code == 200
    assert adapted.json()["intent"] == "weekly_from_pantry"
    assert adapted.json()["data"]["recipe"]["generation_source"] == "local_recipe_catalog"
    assert "No añadí nada a compras" in adapted.json()["speech"]
    adapted_plan = adapted.json()["data"]["weekly_plan"]
    assert any(
        meal.get("recipe_id") == adapted.json()["data"]["recipe"]["id"]
        for meal in adapted_plan["days"][roxy_home_service._weekly_day_index("hoy", adapted_plan)]["meals"]
    )

    cookbook = client.get("/v1/home-food/robert", headers=headers).json()
    assert cookbook["local_catalog"]["total"] == len(cookbook["local_recipes"])
    assert cookbook["local_catalog"]["total"] >= 70
    assert {"Avena nocturna con frutas", "Quesadilla de pollo y vegetales"}.issubset(
        {row["title"] for row in cookbook["local_recipes"]}
    )


def test_voice_can_create_recipe_add_ingredients_and_remove_naturally(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: FakeHomeAI())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    recipe = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, dame una receta de pasta de verdad"},
    )
    add = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "agrega todos los ingredientes de esta receta a mi lista"},
    )
    remove = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "saca las pastas de mi lista de compras"},
    )
    final_list = client.get("/v1/shopping/robert", headers=headers)

    assert recipe.status_code == 200
    assert recipe.json()["intent"] == "recipe_generate"
    assert recipe.json()["data"]["recipe"]["title"] == "Pasta rápida con tomate y ajo"
    assert recipe.json()["data"]["generation_mode"] == "voice_local_recipe_catalog"
    assert add.json()["intent"] == "recipe_to_shopping"
    assert add.json()["data"]["items"][0]["name"] == "Pasta"
    assert remove.json()["intent"] == "shopping_remove"
    assert "Pasta" in remove.json()["message"]
    assert all(row["name"] != "Pasta" for row in final_list.json()["items"])
    assert len(final_list.json()["items"]) == 4


def test_recipe_can_be_deleted_without_touching_another_users_library(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: FakeHomeAI())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}
    robert = client.post(
        "/v1/home-food/robert/recipes",
        headers=headers,
        json={"prompt": "Pasta para Robert", "mode": "routine"},
    ).json()["recipe"]
    alice = client.post(
        "/v1/home-food/alice/recipes",
        headers=headers,
        json={"prompt": "Pasta para Alice", "mode": "routine"},
    ).json()["recipe"]
    session = client.post(
        f"/v1/home-food/robert/recipes/{robert['id']}/cooking-sessions",
        headers=headers,
        json={},
    )
    deleted = client.delete(
        f"/v1/home-food/robert/recipes/{robert['id']}", headers=headers
    )
    robert_snapshot = client.get("/v1/home-food/robert", headers=headers).json()
    alice_snapshot = client.get("/v1/home-food/alice", headers=headers).json()
    missing = client.delete(
        f"/v1/home-food/robert/recipes/{robert['id']}", headers=headers
    )

    assert session.status_code == 201
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "DELETED"
    assert robert_snapshot["recipes"] == []
    assert robert_snapshot["cooking_sessions"] == []
    assert alice_snapshot["recipes"][0]["id"] == alice["id"]
    assert missing.status_code == 404
