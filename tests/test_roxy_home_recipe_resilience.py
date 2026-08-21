from time import perf_counter

from fastapi.testclient import TestClient

from roxy_os.home_recipe_fallback import find_local_recipe, generate_local_recipe, local_recipe_catalog_summary


def test_local_recipe_catalog_covers_food_bread_and_drinks():
    snapshot = {"profile": {"allergies": [], "household_size": 2}}
    bread = generate_local_recipe("Enséñame a hacer pan", snapshot)
    pasta = generate_local_recipe("Quiero espaguetis rápidos", snapshot)
    mocktail = generate_local_recipe("Dame una limonada sin alcohol", snapshot)
    cocktail = generate_local_recipe("Prepara un mojito para adultos", snapshot)
    pina_colada = generate_local_recipe("Hazme una piña colada sin alcohol", snapshot)
    hot_chocolate = generate_local_recipe("Dame un chocolate caliente", snapshot)
    assert bread["kind"] == "bread"
    assert pasta["title"] == "Pasta rápida con tomate y ajo"
    assert mocktail["drink_type"] == "non_alcoholic"
    assert cocktail["drink_type"] == "alcoholic"
    assert pina_colada["title"] == "Piña colada sin alcohol"
    assert hot_chocolate["kind"] == "drink"
    assert all(row["ingredients"] and row["steps"] for row in (bread, pasta, mocktail, cocktail, pina_colada, hot_chocolate))


def test_expanded_catalog_covers_common_drinks_meals_and_desserts_before_openai():
    snapshot = {"profile": {"allergies": []}}
    expected = {
        "whisky sour": ("drink", "alcoholic"),
        "gin tonic": ("drink", "alcoholic"),
        "Aperol spritz": ("drink", "alcoholic"),
        "espresso martini": ("drink", "alcoholic"),
        "mojito sin alcohol": ("drink", "non_alcoholic"),
        "daiquiri sin alcohol": ("drink", "non_alcoholic"),
        "limonada con vodka": ("drink", "alcoholic"),
        "ropa vieja": ("meal", ""),
        "arroz con pollo": ("meal", ""),
        "lasaña": ("meal", ""),
        "flan": ("dessert", ""),
        "pastel de tres leches": ("dessert", ""),
        "brownies": ("dessert", ""),
    }
    for prompt, (kind, drink_type) in expected.items():
        recipe = find_local_recipe(f"Dame una receta de {prompt}", snapshot)
        assert recipe is not None, prompt
        assert recipe["kind"] == kind
        assert recipe.get("drink_type", "") == drink_type
    assert find_local_recipe("Quiero preparar injera etíope tradicional", snapshot) is None

    summary = local_recipe_catalog_summary()
    assert summary == {
        "total": 62,
        "meals": 18,
        "desserts": 11,
        "drinks": 33,
        "alcoholic_drinks": 24,
        "non_alcoholic_drinks": 9,
    }


def test_common_recipe_bypasses_openai_but_uncommon_recipe_uses_it(monkeypatch, tmp_path):
    from tools import roxy_home_service

    class TrackingAI:
        calls = 0

        def generate_recipe(self, prompt, snapshot, *, deep=False):
            self.calls += 1
            return {
                "title": "Injera etíope",
                "description": "Receta especializada",
                "kind": "meal",
                "servings": 4,
                "ingredients": [{"name": "Harina de teff", "quantity": 2, "unit": "taza"}],
                "steps": ["Fermenta la masa", "Cocina cada injera"],
            }

    ai = TrackingAI()
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: ai)
    monkeypatch.setenv("ROXY_HOME_RECIPE_LIBRARY_PATH", str(tmp_path / "recipe-library.sqlite"))
    snapshot = {"profile": {"allergies": []}}

    common, common_mode = roxy_home_service._recipe_with_resilience("Dame un whisky sour", snapshot, deep=False)
    uncommon, uncommon_mode = roxy_home_service._recipe_with_resilience("Quiero preparar injera etíope", snapshot, deep=False)

    assert common["title"] == "Whisky sour"
    assert common_mode == "local_recipe_catalog"
    assert uncommon["title"] == "Injera etíope"
    assert uncommon_mode == "openai"
    assert ai.calls == 1


def test_recipe_endpoint_uses_real_local_catalog_when_home_openai_is_not_connected(tmp_path, monkeypatch):
    from tools import roxy_home_service
    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.delenv("ROXY_HOME_OPENAI_API_KEY", raising=False)
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    response = client.post("/v1/home-food/robert/recipes", headers={"Authorization": "Bearer home-test-key"}, json={"prompt": "Quiero una receta de pan", "mode": "routine"})
    assert response.status_code == 201
    assert response.json()["generation_mode"] == "local_recipe_catalog"
    assert response.json()["recipe"]["title"] == "Pan casero sencillo"
    saved = client.get("/v1/home-food/robert", headers={"Authorization": "Bearer home-test-key"}).json()
    assert saved["recipes"]
    assert saved["local_catalog"]["total"] == 62


def test_shopping_voice_understands_more_natural_vocabulary():
    from tools.roxy_home_service import _assistant_shopping_intent, _assistant_shopping_requests
    assert _assistant_shopping_intent("échame dos yogures en la lista") == "shopping_add"
    assert _assistant_shopping_intent("retira el champú") == "shopping_remove"
    assert _assistant_shopping_intent("qué tenemos pendiente") == "shopping_query"
    assert _assistant_shopping_requests("anota dos paquetes de pasta en mi lista") == [{"name": "pasta", "quantity": 2, "unit": "paquete"}]


def test_voice_recognizes_natural_drink_and_dessert_requests_without_recipe_word():
    from tools.roxy_home_service import _assistant_shopping_intent

    assert _assistant_shopping_intent("Dame una limonada") == "recipe_generate"
    assert _assistant_shopping_intent("Hazme un mojito") == "recipe_generate"
    assert _assistant_shopping_intent("Dame un whisky sour") == "recipe_generate"
    assert _assistant_shopping_intent("Hazme ropa vieja") == "recipe_generate"
    assert _assistant_shopping_intent("Enséñame un pastel de tres leches") == "recipe_generate"
    assert _assistant_shopping_intent("Prepárame un flan") == "recipe_generate"
    assert _assistant_shopping_intent("Agrega jugo de naranja") == "shopping_add"


def test_voice_recipe_returns_inside_client_tool_deadline_without_waiting_for_openai(tmp_path, monkeypatch):
    from tools import roxy_home_service

    class ForbiddenRemoteAI:
        def generate_recipe(self, *args, **kwargs):
            raise AssertionError("voice recipe must not wait for the remote provider")

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: ForbiddenRemoteAI())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    started = perf_counter()
    response = client.post(
        "/v1/assistant/command/robert",
        headers={"Authorization": "Bearer home-test-key"},
        json={"text": "Dame una receta para hacer pan"},
    )
    elapsed = perf_counter() - started
    assert response.status_code == 200
    assert elapsed < 0.5
    assert response.json()["data"]["generation_mode"] == "voice_local_recipe_catalog"
    assert "Pan casero sencillo" in response.json()["speech"]
