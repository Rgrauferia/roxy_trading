from time import perf_counter
from pathlib import Path

from fastapi.testclient import TestClient

from roxy_os.home_recipe_fallback import find_local_recipe, generate_local_recipe, local_recipe_catalog_summary


def test_personalized_pet_recipes_use_present_and_identity_appropriate_photos():
    from roxy_os.home_recipe_fallback import personalized_pet_recipe_catalog

    assets = Path(__file__).resolve().parents[1] / "assets"
    pets = [
        {"id": "bella", "name": "Bella", "species": "dog", "breed": "Bernese Mountain", "life_stage": "young"},
        {"id": "luna", "name": "Luna", "species": "ferret", "breed": "Hurón doméstico", "life_stage": "adult"},
        {"id": "mia", "name": "Mia", "species": "cat", "breed": "Siamés", "life_stage": "adult"},
        {"id": "azul", "name": "Azul", "species": "fish", "breed": "Betta", "life_stage": "adult"},
        {"id": "sol", "name": "Sol", "species": "reptile", "breed": "Gecko leopardo", "life_stage": "adult"},
    ]
    rows = [row for pet in pets for row in personalized_pet_recipe_catalog(pet, {})]

    assert rows
    assert all(row.get("photo_asset", "").startswith("/assets/") for row in rows)
    assert all((assets / row["photo_asset"].removeprefix("/assets/")).is_file() for row in rows)
    assert not any(row["pet_id"] in {"azul", "sol"} for row in rows)
    assert not any(row.get("photo_focus") for row in rows)  # Never crop a collage as a recipe.
    assert all(row["photo_asset_verified"] for row in rows if row["pet_id"] == "luna")
    assert not any("collection" in row["photo_asset"] for row in rows if row.get("photo_asset_verified"))


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
    assert summary["total"] >= 500
    assert summary["categories"] == 16
    assert summary["meals"] >= 340
    assert summary["desserts"] >= 35
    assert summary["alcoholic_drinks"] >= 24
    assert summary["non_alcoholic_drinks"] >= 80


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
    assert saved["local_catalog"]["total"] >= 500


def test_installed_catalog_has_requested_categories_and_real_recipe_payloads():
    from roxy_os.home_recipe_fallback import local_recipe_catalog

    rows = local_recipe_catalog({"profile": {"allergies": []}})
    by_title = {row["title"]: row for row in rows}
    expected = {
        "Huevos Benedict": "breakfast",
        "Pollo teriyaki": "chicken",
        "Ropa vieja": "meat",
        "Camarones al ajillo": "seafood",
        "Moros y cristianos": "rice",
        "Pasta carbonara": "pasta",
        "Ajiaco": "soups",
        "Poke bowl": "bowls_salads",
        "Falafel": "vegetarian",
        "Pizza margarita": "baked",
        "Mojo cubano": "sides_sauces",
        "Tres leches": "desserts",
        "Café cubano": "coffee_hot",
        "Agua de jamaica": "juices",
        "Smoothie bowl de açaí": "smoothies",
        "Vaca frita": "meat",
        "Pollo marsala": "chicken",
        "Pizza napolitana": "baked",
        "Crème brûlée": "desserts",
    }
    for title, category in expected.items():
        assert title in by_title
        assert by_title[title]["category"] == category
        assert by_title[title]["ingredients"]
        assert by_title[title]["steps"]


def test_banana_pancakes_are_breakfast_and_steps_match_the_ingredients():
    recipe = find_local_recipe("Pancakes de banana", {"profile": {"allergies": []}})

    assert recipe is not None
    assert recipe["category"] == "breakfast"
    assert recipe["title"] == "Pancakes de banana"
    ingredient_names = " ".join(row["name"].lower() for row in recipe["ingredients"])
    steps = " ".join(recipe["steps"]).lower()
    assert "banana" in ingredient_names
    assert "banana" in steps
    assert "sal" not in steps


def test_every_local_recipe_is_editorially_complete_and_has_no_placeholder_instructions():
    from roxy_os.home_recipe_fallback import local_recipe_catalog

    rows = local_recipe_catalog({"profile": {"allergies": []}})
    forbidden = (
        "método indicado",
        "según corresponda",
        "orden indicado",
        "punto correcto",
        "cocina u hornea",
        "ingrediente principal",
        "según la receta",
        "cuando corresponda",
        "salsa indicada",
        "guarnición indicada",
        "proporción indicada",
    )
    assert len(rows) >= 500
    for recipe in rows:
        steps = recipe["steps"]
        instructions = " ".join(steps).casefold()
        assert len(steps) >= 5, recipe["title"]
        assert all(len(step.strip()) >= 25 for step in steps), recipe["title"]
        assert not any(phrase in instructions for phrase in forbidden), recipe["title"]


def test_pollo_alfredo_explains_the_complete_recipe_instead_of_a_generic_method():
    from roxy_os.home_recipe_fallback import exact_local_recipe

    recipe = exact_local_recipe("Pollo Alfredo")
    assert recipe is not None
    ingredient_names = {row["name"] for row in recipe["ingredients"]}
    assert {"Fettuccine", "Crema de leche", "Queso parmesano rallado", "Pollo"} <= ingredient_names
    assert len(recipe["steps"]) == 6
    instructions = " ".join(recipe["steps"])
    assert "al dente" in instructions
    assert "74 °C" in instructions
    assert "2 minutos" in instructions
    assert "método indicado" not in instructions


def test_avena_con_manzana_matches_the_atomic_step_by_step_standard():
    from roxy_os.home_recipe_fallback import exact_local_recipe

    recipe = exact_local_recipe("Avena con manzana")
    assert recipe is not None
    assert [(row["name"], row["quantity"], row["unit"]) for row in recipe["ingredients"]] == [
        ("Avena en hojuelas", 0.5, "taza"),
        ("Leche o agua", 1, "taza"),
        ("Manzana", 0.5, "unidad"),
        ("Canela molida", 0.5, "cucharadita"),
        ("Miel o azúcar", 1, "cucharadita"),
    ]
    assert len(recipe["steps"]) == 8
    assert "5 a 7 minutos" in " ".join(recipe["steps"])
    assert "textura cremosa" not in " ".join(recipe["steps"])
    assert "esté cremosa" in " ".join(recipe["steps"])


def test_cafe_cubano_is_a_verified_moka_recipe_with_espumita_and_no_other_drinks():
    from roxy_os.home_recipe_editorial import recipe_quality_issues
    from roxy_os.home_recipe_fallback import exact_local_recipe

    recipe = exact_local_recipe("Café cubano")
    assert recipe is not None
    assert recipe["servings"] == 4
    assert recipe["editorial_status"] == "verified"
    assert recipe["sources"][0]["url"] == "https://www.cafebustelo.com/coffee/recipes/hot-coffee/cafecito"
    assert {row["name"] for row in recipe["ingredients"]} == {
        "Agua", "Café espresso molido de tueste oscuro", "Azúcar blanca",
    }
    instructions = " ".join(recipe["steps"])
    assert "cafetera moka" in instructions
    assert "espumita" in instructions
    assert "1 a 2 minutos" in instructions
    assert all(word not in instructions.casefold() for word in ("matcha", "cacao", "espuma de leche"))
    assert recipe_quality_issues(recipe, "Café cubano") == []


def test_saved_old_catalog_recipe_is_upgraded_without_losing_user_metadata(tmp_path):
    from roxy_os.home_food import HomeFoodStore

    store = HomeFoodStore(tmp_path / "home.json")
    saved = store.save_recipe(
        "robert",
        {
            "title": "Avena con manzana",
            "kind": "meal",
            "servings": 2,
            "ingredients": [{"name": "Avena", "quantity": 1, "unit": "taza"}],
            "steps": ["Prepara todo.", "Cocina según corresponda.", "Sirve."],
        },
    )

    upgraded = store.get_recipe("robert", saved["id"])

    assert upgraded["id"] == saved["id"]
    assert upgraded["favorite"] is False
    assert upgraded["user_notes"] == ""
    assert upgraded["editorial_version"] == 3
    assert len(upgraded["steps"]) == 8
    assert upgraded["ingredients"][0]["quantity"] == 0.5


def test_shopping_voice_understands_more_natural_vocabulary():
    from tools.roxy_home_service import _assistant_pantry_requests, _assistant_shopping_intent, _assistant_shopping_requests
    assert _assistant_shopping_intent("échame dos yogures en la lista") == "shopping_add"
    assert _assistant_shopping_intent("retira el champú") == "shopping_remove"
    assert _assistant_shopping_intent("qué tenemos pendiente") == "shopping_query"
    assert _assistant_shopping_requests("anota dos paquetes de pasta en mi lista") == [{"name": "pasta", "quantity": 2, "unit": "paquete"}]
    assert _assistant_shopping_intent("Compré dos litros de leche") == "pantry_add"
    assert _assistant_shopping_intent("¿Qué hay en la despensa?") == "pantry_query"
    assert _assistant_shopping_intent("Se acabó la leche") == "pantry_remove"
    assert _assistant_pantry_requests("Compré dos litros de leche") == [{"name": "leche", "quantity": 2, "unit": "litro"}]


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
