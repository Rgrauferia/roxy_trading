from copy import deepcopy
import json
from pathlib import Path

import pytest

from roxy_os.home_food import HomeFoodStore, RecipeReviewRequired
from roxy_os.home_recipe_fallback import local_recipe_by_key, personalized_pet_recipe_catalog


def test_breed_view_has_distinct_preparations_not_relabelled_duplicates():
    pet = {"id": "bella", "name": "Bella", "species": "dog", "breed": "Bernese Mountain Dog", "life_stage": "young"}
    rows = personalized_pet_recipe_catalog(pet, {})
    signatures = [json.dumps([r["ingredients"], r["steps"]], sort_keys=True) for r in rows]
    assert len(signatures) == len(set(signatures)) == 15
    verified = [row for row in rows if row.get("photo_asset_verified")]
    assert len(verified) == 15
    assert len({r["photo_asset"] for r in verified}) == len(verified)
    root = Path(__file__).resolve().parents[1]
    assert all((root / row["photo_asset"].lstrip("/")).is_file() for row in verified)
    assert all(row["pet_id"] == pet["id"] for row in rows)


@pytest.mark.parametrize("key,expected", [
    ("dog_apple_carrot_oat", ["manzana", "zanahoria", "avena"]),
    ("dog_turkey_pumpkin", ["pavo", "calabaza"]),
    ("dog_beef_green_bean", ["res", "judías"]),
    ("dog_frozen_banana_pumpkin", ["plátano", "calabaza"]),
])
def test_every_batch_ingredient_reaches_shopping_and_allergy_screening(tmp_path, key, expected):
    store = HomeFoodStore(tmp_path / "food.json")
    pet = store.upsert_pet("qa", name="Prueba", species="dog", life_stage="adult")
    canonical = local_recipe_by_key(key, {})
    recipe = store.save_recipe("qa", {**canonical, "pet_id": pet["id"]})
    preview = store.shopping_preview("qa", recipe["id"])
    names = " ".join(r["name"].lower() for r in preview["items"])
    assert all(ingredient in names for ingredient in expected)
    assert len(preview["items"]) == len(expected)
    store.upsert_pet("qa", pet_id=pet["id"], name=pet["name"], species="dog", allergies=[expected[-1]])
    assert not any(r["catalog_key"] == key for r in personalized_pet_recipe_catalog(store.snapshot("qa")["pets"][0], {}))
    with pytest.raises(RecipeReviewRequired):
        store.shopping_preview("qa", recipe["id"])
    with pytest.raises(RecipeReviewRequired):
        store.start_cooking_session("qa", recipe["id"])


def test_old_catalog_copy_is_updated_without_losing_personal_metadata():
    old = local_recipe_by_key("dog_apple_carrot_oat", {})
    old.update(id="unchanged", pet_id="pet", favorite=True, user_notes="Mi anotación", photo_data_url="data:image/jpeg;base64,USERPHOTO")
    old["ingredients"] = old["ingredients"][:1]
    HomeFoodStore._upgrade_installed_recipe(old)
    assert len(old["ingredients"]) == 3
    assert old["content_revision"] == "complete-ingredients-2026-09-06"
    assert old["photo_asset_verified"] is True
    assert (old["id"], old["pet_id"], old["favorite"], old["user_notes"], old["photo_data_url"]) == ("unchanged", "pet", True, "Mi anotación", "data:image/jpeg;base64,USERPHOTO")


def test_import_with_catalog_title_is_not_overwritten_even_when_short():
    imported = local_recipe_by_key("dog_apple_carrot_oat", {})
    imported.update(generation_source="import_text", editorial_status="user_reviewed_import", steps=["Un paso escrito por mí"], photo_data_url="data:image/jpeg;base64,MINE")
    original = deepcopy(imported)
    HomeFoodStore._upgrade_installed_recipe(imported)
    assert imported == original


def test_saving_a_catalog_recipe_preserves_notes_without_duplicating_cards(tmp_path):
    store = HomeFoodStore(tmp_path / "food.json")
    pet = store.upsert_pet("qa", name="Prueba", species="dog", breed="Bernese Mountain", life_stage="young")
    recipe = store.save_recipe("qa", {**local_recipe_by_key("dog_apple_carrot_oat", {}), "pet_id": pet["id"]})
    snapshot = store.snapshot("qa")
    snapshot["recipes"][0].update(favorite=True, user_notes="Mi detalle", photo_data_url="data:image/jpeg;base64,MINE")
    original = deepcopy(snapshot)
    rows = personalized_pet_recipe_catalog(pet, snapshot)
    assert len(rows) == 15
    saved = [r for r in rows if r.get("id") == recipe["id"]]
    assert len(saved) == 1
    assert saved[0]["favorite"] and saved[0]["user_notes"] == "Mi detalle"
    assert saved[0]["photo_data_url"].endswith("MINE")
    assert snapshot == original


@pytest.mark.parametrize("key,temperature", [
    ("dog_dehydrated_chicken", "74 °C"), ("dog_dehydrated_turkey", "74 °C"),
    ("cat_dehydrated_chicken", "74 °C"), ("cat_dehydrated_whitefish", "63 °C"),
])
def test_dehydrated_recipes_cook_before_drying_and_are_not_shelf_stable(key, temperature):
    recipe = local_recipe_by_key(key, {})
    steps = recipe["steps"]
    assert "Antes de deshidratar" in steps[2] and temperature in steps[2]
    assert "termómetro" in steps[2] and "60 °C" in steps[3]
    assert "refrigera" in steps[-1] and "dos días" in steps[-1]
    assert any("foodsafety.gov" in source["url"] for source in recipe["sources"])


def test_frozen_recipe_storage_matches_its_preparation():
    recipe = local_recipe_by_key("dog_frozen_banana_pumpkin", {})
    assert "congelado" in recipe["steps"][-1]
    assert "ablande" in recipe["steps"][-2]
    assert "refrigera" not in recipe["steps"][-1]


def test_pet_recipe_client_uses_profile_bound_server_rechecks():
    script = (Path(__file__).resolve().parents[1] / "assets/roxy_list.js").read_text()
    assert "pet_id:recipe.audience==='pet'" in script
    assert "return !blockedIngredients.some(item=>ingredients.includes(item))" not in script
    assert "Ingredientes y restricciones" in script
    assert "safety.cart_blocked" in script
    assert "aria-pressed" in script
