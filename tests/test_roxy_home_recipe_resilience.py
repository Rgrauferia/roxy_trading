from fastapi.testclient import TestClient

from roxy_os.home_recipe_fallback import generate_local_recipe


def test_local_recipe_catalog_covers_food_bread_and_drinks():
    snapshot = {"profile": {"allergies": [], "household_size": 2}}

    bread = generate_local_recipe("Enséñame a hacer pan", snapshot)
    pasta = generate_local_recipe("Quiero espaguetis rápidos", snapshot)
    mocktail = generate_local_recipe("Dame una limonada sin alcohol", snapshot)
    cocktail = generate_local_recipe("Prepara un mojito para adultos", snapshot)

    assert bread["kind"] == "bread"
    assert pasta["title"] == "Pasta rápida con tomate y ajo"
    assert mocktail["drink_type"] == "non_alcoholic"
    assert cocktail["drink_type"] == "alcoholic"
    assert all(row["ingredients"] and row["steps"] for row in (bread, pasta, mocktail, cocktail))


def test_recipe_endpoint_uses_real_local_catalog_when_home_openai_is_not_connected(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.delenv("ROXY_HOME_OPENAI_API_KEY", raising=False)
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)

    response = client.post(
        "/v1/home-food/robert/recipes",
        headers={"Authorization": "Bearer home-test-key"},
        json={"prompt": "Quiero una receta de pan", "mode": "routine"},
    )

    assert response.status_code == 201
    assert response.json()["generation_mode"] == "local_recipe_catalog"
    assert response.json()["recipe"]["title"] == "Pan casero sencillo"
    assert client.get("/v1/home-food/robert", headers={"Authorization": "Bearer home-test-key"}).json()["recipes"]


def test_shopping_voice_understands_more_natural_vocabulary():
    from tools.roxy_home_service import _assistant_shopping_intent, _assistant_shopping_requests

    assert _assistant_shopping_intent("échame dos yogures en la lista") == "shopping_add"
    assert _assistant_shopping_intent("retira el champú") == "shopping_remove"
    assert _assistant_shopping_intent("qué tenemos pendiente") == "shopping_query"
    assert _assistant_shopping_requests("anota dos paquetes de pasta en mi lista") == [
        {"name": "pasta", "quantity": 2, "unit": "paquete"}
    ]
