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
