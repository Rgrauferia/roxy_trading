import json
import sqlite3

from fastapi.testclient import TestClient

from roxy_os.home_recipe_library import (
    HomeRecipeLibraryStore,
    canonical_recipe_query,
    requested_servings,
)


def recipe():
    return {
        "title": "Injera etíope",
        "description": "Pan plano fermentado.",
        "kind": "bread",
        "servings": 4,
        "ingredients": [
            {"name": "Harina de teff", "quantity": 400, "unit": "gramo", "notes": ""},
            {"name": "Agua", "quantity": 600, "unit": "mililitro", "notes": ""},
        ],
        "steps": ["Mezcla y fermenta.", "Cocina en una sartén."],
        "allergen_notes": [],
        "favorite": True,
        "user_notes": "Esta nota es privada",
        "photo_data_url": "data:image/png;base64,cHJpdmFkbw==",
    }


def empty_snapshot(**profile):
    return {"profile": {"allergies": [], "dislikes": [], **profile}, "pantry": []}


def test_equivalent_recipe_requests_share_one_private_hash():
    first = canonical_recipe_query("Dame una receta de injera etíope")
    second = canonical_recipe_query("Quiero hacer injera etíope para 8 personas")

    assert first == second
    assert "injera" not in first
    assert requested_servings("Injera para 8 personas") == 8


def test_recipe_is_published_once_and_reused_scaled_for_another_user(tmp_path):
    store = HomeRecipeLibraryStore(tmp_path / "library.sqlite")
    published = store.publish("Dame injera etíope", recipe(), source="openai")
    reused = store.find("Quiero preparar injera etíope para 8 personas", empty_snapshot())

    assert reused["shared_recipe_id"] == published["id"]
    assert reused["generation_source"] == "shared_recipe_library"
    assert reused["servings"] == 8
    assert reused["ingredients"][0]["quantity"] == 800
    assert store.summary() == {"recipes": 1, "reuses": 1}

    with sqlite3.connect(tmp_path / "library.sqlite") as connection:
        stored = json.loads(connection.execute("SELECT recipe_json FROM recipes").fetchone()[0])
    assert "favorite" not in stored
    assert "user_notes" not in stored
    assert "photo_data_url" not in stored


def test_library_does_not_reuse_a_recipe_that_conflicts_with_household_allergy(tmp_path):
    store = HomeRecipeLibraryStore(tmp_path / "library.sqlite")
    store.publish("Dame injera etíope", recipe(), source="openai")

    blocked = store.find(
        "Quiero hacer injera etíope",
        empty_snapshot(allergies=["Teff"]),
    )

    assert blocked is None
    assert store.summary() == {"recipes": 1, "reuses": 0}


def test_irrelevant_provider_result_cannot_poison_shared_query(tmp_path):
    store = HomeRecipeLibraryStore(tmp_path / "library.sqlite")
    result = store.publish("Dame injera etíope", {**recipe(), "title": "Pan casero", "description": "Pan común", "ingredients": [{"name": "Harina", "quantity": 2, "unit": "taza"}]}, source="openai")

    assert result["published"] is False
    assert store.find("Dame injera etíope", empty_snapshot()) is None
    assert store.summary() == {"recipes": 0, "reuses": 0}


def test_home_api_calls_openai_once_then_reuses_recipe_for_another_user(tmp_path, monkeypatch):
    from tools import roxy_home_service

    calls = []

    class FakeHomeAI:
        def generate_recipe(self, prompt, snapshot, *, deep=False):
            calls.append((prompt, snapshot, deep))
            return recipe()

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "food.json"))
    monkeypatch.setenv("ROXY_HOME_RECIPE_LIBRARY_PATH", str(tmp_path / "library.sqlite"))
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: FakeHomeAI())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    first = client.post(
        "/v1/home-food/robert/recipes",
        headers=headers,
        json={"prompt": "Dame una receta de injera etíope", "mode": "routine"},
    )
    second = client.post(
        "/v1/home-food/alice/recipes",
        headers=headers,
        json={"prompt": "Quiero hacer injera etíope para 8 personas", "mode": "routine"},
    )

    assert first.status_code == 201
    assert first.json()["generation_mode"] == "openai"
    assert second.status_code == 201
    assert second.json()["generation_mode"] == "shared_recipe_library"
    assert second.json()["recipe"]["servings"] == 8
    assert second.json()["recipe"]["shared_recipe_id"] == first.json()["recipe"]["shared_recipe_id"]
    assert len(calls) == 1
    assert calls[0][1] == {"profile": {}, "pantry": []}
