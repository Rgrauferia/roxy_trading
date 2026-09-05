from copy import deepcopy

import pytest

from roxy_os.home_food import HomeFoodStore
from roxy_os.home_pet_recipe_safety import check_import_profile, validate_pet_import, pet_import_context
from roxy_os.home_recipe_fallback import personalized_pet_recipe_catalog


def test_import_bound_to_one_pet_and_not_silently_shared(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")
    first = store.upsert_pet("qa", name="Luna", species="ferret", life_stage="adult")
    second = store.upsert_pet("qa", name="Otro ferret", species="ferret", life_stage="adult")
    recipe = deepcopy(personalized_pet_recipe_catalog(first, {})[0])
    recipe["title"] = "Mi preparación importada"
    validated = validate_pet_import(recipe, first)
    store.save_recipe("qa", validated)
    snapshot = store.snapshot("qa")
    assert any(row["title"] == recipe["title"] for row in personalized_pet_recipe_catalog(first, snapshot))
    assert not any(row["title"] == recipe["title"] for row in personalized_pet_recipe_catalog(second, snapshot))


@pytest.mark.parametrize("overrides", [{"species": "fish"}, {"species": "reptile"}, {"species": "bird", "exact_species": "Lori arcoíris"}, {"life_stage": "baby"}, {"life_stage": "unknown"}, {"conditions": ["Insulinoma"]}, {"current_food_kind": "veterinary"}])
def test_import_does_not_replace_specialist_plan(overrides):
    with pytest.raises(ValueError):
        check_import_profile({"species": "ferret", "life_stage": "adult", **overrides})


def test_import_rejects_unreviewed_ingredients_and_care_protocols():
    pet = {"id": "luna", "name": "Luna", "species": "ferret", "life_stage": "adult"}
    recipe = deepcopy(personalized_pet_recipe_catalog(pet, {})[0])
    bad = {**recipe, "ingredients": [{"name": "Chocolate", "quantity": 1, "unit": "gramo"}]}
    with pytest.raises(ValueError):
        validate_pet_import(bad, pet)
    with pytest.raises(ValueError):
        validate_pet_import({**recipe, "safety_class": "feeding_guide"}, pet)


def test_import_context_excludes_documents_photos_and_address():
    assert pet_import_context({"name": "Luna", "photo_data_url": "private-photo", "medical_history": [{"attachment_data_url": "private-report"}], "address": "private-address"})["name"] == "Luna"
    assert "private" not in str(pet_import_context({"name": "Luna", "medical_history": ["private"]}))


@pytest.mark.parametrize("bad", [{"ingredients": ["pollo"]}, {"steps": [None]}, {"steps": "mezclar"}])
def test_malformed_import_is_validation_error_not_server_error(bad):
    pet = {"id": "luna", "name": "Luna", "species": "ferret", "life_stage": "adult"}
    recipe = deepcopy(personalized_pet_recipe_catalog(pet, {})[0])
    with pytest.raises(ValueError):
        validate_pet_import({**recipe, **bad}, pet)


def test_each_ferret_preparation_has_unique_standalone_artwork():
    from pathlib import Path
    rows = personalized_pet_recipe_catalog({"id": "luna", "name": "Luna", "species": "ferret", "life_stage": "adult"}, {})
    assert len(rows) == 8
    assert len({row["photo_asset"] for row in rows}) == len(rows)
    for row in rows:
        assert row["photo_asset_verified"]
        assert Path(row["photo_asset"].lstrip("/")).is_file()
        assert row["ingredients"] and row["steps"]
        assert row["safety_class"] != "feeding_guide"


def test_catalog_does_not_override_medical_diet_or_use_human_allergies():
    pet = {"id": "luna", "name": "Luna", "species": "ferret", "life_stage": "adult"}
    assert not personalized_pet_recipe_catalog({**pet, "conditions": ["Insulinoma"]}, {})
    rows = personalized_pet_recipe_catalog(pet, {"profile": {"allergies": ["private-human-allergy"]}})
    assert rows and "private-human-allergy" not in str(rows)
