from roxy_os.home_food import HomeFoodStore, HomePermissionPolicy
from roxy_os.shopping_list import ShoppingListStore


def sample_recipe():
    return {
        "title": "Arroz con tomate",
        "description": "Cena sencilla",
        "servings": 2,
        "ingredients": [
            {"name": "Arroz", "quantity": 2, "unit": "taza"},
            {"name": "Tomate", "quantity": 4, "unit": "unidad"},
        ],
        "steps": ["Cocinar", "Servir"],
        "allergen_notes": [],
    }


def test_home_food_isolates_profiles_pantry_and_recipes_by_user(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")
    store.update_profile(
        "robert",
        preferences=["Mediterránea"],
        allergies=["Nueces"],
        dislikes=[],
        household_size=2,
    )
    store.replace_pantry("robert", [{"name": "Arroz", "quantity": 1, "unit": "taza"}])
    recipe = store.save_recipe("robert", sample_recipe())

    assert store.snapshot("robert")["profile"]["allergies"] == ["Nueces"]
    assert store.snapshot("alice")["profile"]["allergies"] == []
    assert store.snapshot("alice")["pantry"] == []
    try:
        store.get_recipe("alice", recipe["id"])
    except KeyError:
        pass
    else:  # pragma: no cover
        raise AssertionError("Una receta privada fue visible para otro usuario")


def test_shared_artwork_inventory_deduplicates_saved_recipe_titles(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")
    first = sample_recipe()
    second = {**sample_recipe(), "title": "Pizza cubana clásica"}
    store.save_recipe("robert", first)
    store.save_recipe("roxy", first)
    store.save_recipe("roxy", second)

    assert [row["title"] for row in store.all_saved_recipes()] == [
        "Arroz con tomate",
        "Pizza cubana clásica",
    ]
    assert store.find_saved_recipe_by_title("  PIZZA CUBANA CLÁSICA ")["title"] == "Pizza cubana clásica"
    assert store.find_saved_recipe_by_title("No existe") is None


def test_scaling_pantry_subtraction_and_confirmed_shopping_conversion(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")
    shopping = ShoppingListStore(tmp_path / "shopping.json")
    store.replace_pantry("robert", [{"name": "Arroz", "quantity": 1, "unit": "taza"}])
    recipe = store.save_recipe("robert", sample_recipe())

    scaled = store.scale_recipe("robert", recipe["id"], 4)
    preview = store.shopping_preview("robert", recipe["id"], servings=4)
    blocked = store.commit_recipe_to_shopping(
        "robert", recipe["id"], shopping, confirmed=False, servings=4
    )

    assert scaled["ingredients"][0]["quantity"] == 4
    assert preview["items"][0]["name"] == "Arroz"
    assert preview["items"][0]["quantity"] == 3
    assert blocked["status"] == "CONFIRMATION_REQUIRED"
    assert shopping.list_items("robert") == []

    committed = store.commit_recipe_to_shopping(
        "robert", recipe["id"], shopping, confirmed=True, servings=4
    )
    rows = shopping.list_items("robert")
    assert committed["status"] == "ADDED"
    assert [(row["name"], row["quantity"]) for row in rows] == [("Arroz", 3), ("Tomate", 8)]
    assert all(row["source"] == "roxy_home_recipe" for row in rows)


def test_home_permission_policy_denies_purchase_and_device_control():
    assert HomePermissionPolicy.decision("recipe") == "ALLOW"
    assert HomePermissionPolicy.decision("recipe_to_shopping") == "CONFIRMATION_REQUIRED"
    assert HomePermissionPolicy.decision("recipe_to_shopping", confirmed=True) == "ALLOW"
    assert HomePermissionPolicy.decision("purchase", confirmed=True) == "DENY"
    assert HomePermissionPolicy.decision("device_control", confirmed=True) == "DENY"


def test_saved_recipe_can_resume_a_persistent_guided_cooking_session(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")
    recipe = store.save_recipe("robert", sample_recipe())

    session = store.start_cooking_session("robert", recipe["id"])
    first = store.cooking_session_detail("robert", session["id"])
    store.update_cooking_session("robert", session["id"], "next")
    second = store.cooking_session_detail("robert", session["id"])
    store.update_cooking_session("robert", session["id"], "next")
    completed = store.cooking_session_detail("robert", session["id"])

    assert first["current_step"] == "Cocinar"
    assert first["step_number"] == 1
    assert second["current_step"] == "Servir"
    assert second["session"]["step_index"] == 1
    assert completed["session"]["status"] == "COMPLETED"
    assert store.snapshot("alice")["cooking_sessions"] == []


def test_recipe_personalization_and_cooking_timers_stay_private(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")
    recipe = store.save_recipe("robert", sample_recipe())
    personalized = store.personalize_recipe(
        "robert",
        recipe["id"],
        favorite=True,
        user_notes="Duplicar el tomate",
        photo_data_url="data:image/webp;base64,aGVsbG8=",
    )
    session = store.start_cooking_session("robert", recipe["id"])
    timer = store.add_cooking_timer(
        "robert", session["id"], duration_seconds=120, label="Arroz"
    )
    detail = store.cooking_session_detail("robert", session["id"])
    cancelled = store.cancel_cooking_timer("robert", session["id"], timer["id"])

    assert personalized["favorite"] is True
    assert personalized["user_notes"] == "Duplicar el tomate"
    assert personalized["photo_data_url"].startswith("data:image/webp;base64,")
    assert 0 < detail["session"]["timers"][0]["remaining_seconds"] <= 120
    assert cancelled["status"] == "CANCELLED"
    assert store.snapshot("alice")["recipes"] == []
    assert store.snapshot("alice")["cooking_sessions"] == []


def test_drinks_are_classified_with_and_without_alcohol(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")
    alcoholic = store.save_recipe(
        "robert",
        {
            **sample_recipe(),
            "title": "Cóctel de piña",
            "kind": "drink",
            "drink_type": "alcoholic",
        },
    )
    normal = store.save_recipe(
        "robert",
        {
            **sample_recipe(),
            "title": "Limonada",
            "kind": "drink",
            "drink_type": "non_alcoholic",
        },
    )

    assert alcoholic["drink_type"] == "alcoholic"
    assert normal["drink_type"] == "non_alcoholic"

    # Recipes saved before drink_type existed are classified when read.
    legacy = store.save_recipe(
        "robert",
        {
            **sample_recipe(),
            "title": "Café frío",
            "kind": "drink",
        },
    )
    payload = store._read_unlocked()
    payload["users"]["robert"]["recipes"][-1].pop("drink_type")
    store._write_unlocked(payload)
    migrated = store.get_recipe("robert", legacy["id"])
    assert migrated["drink_type"] == "non_alcoholic"
