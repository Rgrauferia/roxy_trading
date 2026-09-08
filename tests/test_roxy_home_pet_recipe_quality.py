from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from roxy_os.home_food import HomeFoodStore, RecipeReviewRequired
from roxy_os.home_recipe_fallback import local_recipe_by_key, personalized_pet_recipe_catalog
from roxy_os.home_pet_recipe_safety import check_import_profile
from roxy_os.home_pet_product_safety import product_safety


@pytest.mark.parametrize("species,exact_species", [
    ("rabbit", "Conejo doméstico"), ("guinea_pig", "Cobaya"),
    ("hamster", "Hámster sirio"), ("bird", "Periquito australiano"), ("bird", "Canario"),
])
def test_small_pet_preparations_have_individual_photos_and_current_profile(species, exact_species):
    pet = {"id": "photo-qa", "name": "Prueba", "species": species, "exact_species": exact_species, "life_stage": "adult"}
    rows = personalized_pet_recipe_catalog(pet, {})
    root = Path(__file__).resolve().parents[1]
    assert len(rows) == 3
    assert len({row["photo_asset"] for row in rows}) == 3
    assert all(row["photo_asset_verified"] and row["pet_id"] == pet["id"] for row in rows)
    assert all((root / row["photo_asset"].lstrip("/")).is_file() for row in rows)
    assert all(row["content_kind"] == "recipe" and len(row["steps"]) >= 5 and row["ingredients"] for row in rows)
    assert not personalized_pet_recipe_catalog({**pet, "life_stage": "baby"}, {})
    ingredients = [item["name"] for row in rows for item in row["ingredients"]]
    assert not personalized_pet_recipe_catalog({**pet, "allergies": ingredients}, {})


@pytest.mark.parametrize("conditions,blocked", [
    (["Ninguna"], False), (["none"], False), (["Sin condiciones conocidas"], False),
    (["No known conditions"], False), (["Ninguna salvo diabetes"], True),
    (["Ninguna", "Renal"], True), (["Unknown"], True), ("ninguna salvo diabetes", True),
])
def test_recipe_and_product_medical_gate_share_exact_negative_answers(conditions, blocked):
    pet = {"id": "qa", "name": "Prueba", "species": "cat", "life_stage": "adult", "conditions": conditions}
    product = {"brand": "Prueba", "name": "Alimento", "category": "Alimento completo"}
    assert product_safety(pet, product)["cart_blocked"] is blocked
    if blocked:
        with pytest.raises(ValueError, match="veterinaria"):
            check_import_profile(pet)
        assert personalized_pet_recipe_catalog(pet, {}) == []
    else:
        check_import_profile(pet)
        assert len(personalized_pet_recipe_catalog(pet, {})) == 12


@pytest.mark.parametrize("species,exact_species", [
    ("bird", "Lori arcoíris"), ("bird", ""), ("reptile", "Pitón bola"),
    ("fish", "Betta"), ("amphibian", "Ajolote"), ("invertebrate", "Tarántula"),
])
def test_more_photos_never_enable_recipes_for_specialist_species(species, exact_species):
    pet = {"id": "qa", "name": "Prueba", "species": species, "exact_species": exact_species, "life_stage": "adult"}
    assert personalized_pet_recipe_catalog(pet, {}) == []


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


@pytest.mark.parametrize("breed", ["Domestic Shorthair", "Siamese", "Maine Coon"])
def test_cat_catalog_has_distinct_photos_and_preserves_profile_filters(breed):
    pet = {"id": "cat-qa", "name": "Prueba", "species": "cat", "breed": breed, "life_stage": "adult"}
    rows = personalized_pet_recipe_catalog(pet, {})
    root = Path(__file__).resolve().parents[1]
    assert len(rows) == 12
    assert len({r["photo_asset"] for r in rows}) == 12
    assert all(r["photo_asset_verified"] and r["pet_id"] == pet["id"] for r in rows)
    assert all((root / r["photo_asset"].lstrip("/")).is_file() for r in rows)
    assert not any("collection" in r["photo_asset"] or "variety" in r["photo_asset"] for r in rows)
    filtered = personalized_pet_recipe_catalog({**pet, "allergies": ["chicken", "egg", "fish", "shellfish"]}, {})
    assert filtered and len(filtered) < len(rows)
    assert all(r["photo_asset_verified"] for r in filtered)
    assert {r["catalog_key"] for r in filtered}.isdisjoint({"cat_egg_chicken_bites", "cat_plain_shrimp", "cat_dehydrated_chicken", "cat_dehydrated_whitefish", "cat_hard_boiled_egg"})


def test_shopping_footer_counts_product_lines_not_mixed_quantities():
    script = (Path(__file__).resolve().parents[1] / "assets/roxy_list.js").read_text()
    function = script.split("  function renderShopping() {", 1)[1].split("  function renderCommerceSummary", 1)[0]
    harness = """
const assert = require('node:assert/strict');
const nodes = {pendingTotal:{},pendingLabel:{},completeButton:{}};
const $ = id => nodes[id];
const renderFilters=()=>{},renderStaples=()=>{},renderList=()=>{},renderHistory=()=>{},renderCommerceSummary=()=>{};
let items=[]; const activeItems=()=>items;
""" + "function renderShopping(){" + function + """
for (const [rows, count, label, disabled] of [
  [[], '0', 'productos pendientes', true],
  [[{quantity:250,unit:'gramo'}], '1', 'producto pendiente', false],
  [[{quantity:250,unit:'gramo'},{quantity:60,unit:'gramo'},{quantity:1,unit:'unidad'}], '3', 'productos pendientes', false],
  [[{quantity:0.5,unit:'litro'},{quantity:12,unit:'unidad'}], '2', 'productos pendientes', false]
]) {
  items=rows; renderShopping();
  assert.equal(nodes.pendingTotal.textContent,count);
  assert.equal(nodes.pendingLabel.textContent,label);
  assert.equal(nodes.completeButton.disabled,disabled);
}
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("key,expected", [
    ("dog_apple_carrot_oat", ["manzana", "zanahoria", "avena"]),
    ("dog_turkey_pumpkin", ["pavo", "calabaza"]),
    ("dog_beef_green_bean", ["res", "judías"]),
    ("dog_frozen_banana_pumpkin", ["plátano", "calabaza"]),
])
def test_batch_ingredients_are_preserved_but_unverified_sources_cannot_reach_shopping(tmp_path, key, expected):
    store = HomeFoodStore(tmp_path / "food.json")
    pet = store.upsert_pet("qa", name="Prueba", species="dog", life_stage="adult")
    canonical = local_recipe_by_key(key, {})
    recipe = store.save_recipe("qa", {**canonical, "pet_id": pet["id"]})
    names = " ".join(r["name"].lower() for r in recipe["ingredients"])
    assert all(ingredient in names for ingredient in expected)
    assert len(recipe["ingredients"]) == len(expected)
    before = deepcopy(store.snapshot("qa"))
    with pytest.raises(RecipeReviewRequired, match="original"):
        store.shopping_preview("qa", recipe["id"])
    with pytest.raises(RecipeReviewRequired, match="original"):
        store.start_cooking_session("qa", recipe["id"])
    assert store.snapshot("qa") == before
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
