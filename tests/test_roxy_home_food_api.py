from fastapi.testclient import TestClient


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
