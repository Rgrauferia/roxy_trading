from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from roxy_os.home_pet_catalog import PRODUCTS, personalized_pet_products
from roxy_os.home_pet_product_safety import product_id, product_safety
from roxy_os.home_pet_restrictions import matching_restrictions, unclear_restrictions
from roxy_os.home_recipe_fallback import personalized_pet_recipe_catalog


@pytest.mark.parametrize("allergy,ingredients,match", [
    ("Res", "fresa fresca y arroz", False),
    ("Res", "Freshwater Master Test Kit", False),
    ("Res", "chicken fat preserved with mixed tocopherols", False),
    ("Res", "beef liver", True),
    ("CHICKEN", "harina de pollo", True),
    ("Huevo", "dried egg product", True),
    ("Soya", "soybean meal", True),
    ("Lácteos", "lactose", True),
    ("Pavo", "turkey", True),
    ("Alergia a pollo y huevo", "egg", True),
    ("Trigo", "harina de avena", False),
    ("Ninguna conocida", "pollo", False),
])
def test_screening_uses_words_and_bilingual_ingredient_aliases(allergy, ingredients, match):
    assert bool(matching_restrictions({"allergies": [allergy]}, ingredients)) is match


@pytest.mark.parametrize("brand,allergy", [
    ("Mazuri", "Pollo"), ("Mazuri", "Lácteos"), ("Mazuri", "Huevo"),
    ("Oxbow", "Huevo"), ("Oxbow", "Pescado"), ("Wysong", "Pollo"),
])
def test_ferret_foods_are_screened_beyond_the_product_name(brand, allergy):
    product = next(p for p in PRODUCTS["ferret"] if p["brand"] == brand and p["category"].startswith("Alimento"))
    assert allergy.lower() not in product["name"].lower()
    pet = {"species": "ferret", "name": "Prueba", "life_stage": "adult", "allergies": [allergy]}
    safety = product_safety(pet, product)
    assert safety["status"] == "ingredient_conflict" and safety["cart_blocked"]
    assert safety["ingredient_review"]["source_url"].startswith("https://")
    assert not any(row["id"] == product_id("ferret", product) for row in personalized_pet_products(pet))


def test_unknown_formula_does_not_become_allergy_safe_and_equipment_remains_available():
    pet = {"species": "ferret", "name": "Prueba", "allergies": ["Otra"]}
    assert unclear_restrictions(pet)
    food = {"brand": "Marca", "name": "Dieta para Ferret", "category": "Alimento completo"}
    assert product_safety(pet, food)["cart_blocked"]
    food["category"] = "Una categoría nueva"
    assert product_safety(pet, food)["cart_blocked"]
    rows = personalized_pet_products(pet)
    assert any(row["safety"]["status"] == "equipment" and not row["safety"]["cart_blocked"] for row in rows)
    assert all(row["safety"]["cart_blocked"] for row in rows if row["category"].startswith("Alimento"))
    assert not personalized_pet_recipe_catalog({**pet, "id": "test", "life_stage": "adult"}, {})


def test_no_ingredient_match_is_not_medical_clearance():
    food = next(p for p in PRODUCTS["ferret"] if p["brand"] == "Oxbow")
    safety = product_safety({"allergies": ["Cilantro"]}, food)
    assert not safety["matched_restrictions"]
    assert safety["cart_blocked"] and safety["status"] == "professional_review_required"
    assert product_safety({"current_food_kind": "veterinary"}, food)["cart_blocked"]
    assert product_safety({"conditions": ["Alergia alimentaria"]}, food)["cart_blocked"]
    assert product_safety({"conditions": ["Enfermedad renal"]}, food)["cart_blocked"]
    assert product_safety({"veterinarian_instructions": "Conservar su dieta"}, food)["cart_blocked"]
    plain = product_safety({"allergies": ["Ninguna conocida"]}, food)
    assert not plain["cart_blocked"] and plain["status"] == "label_review_required"


def test_ids_survive_other_products_being_filtered_and_source_catalog_is_unchanged():
    original = deepcopy(PRODUCTS)
    pet = {"species": "dog", "name": "Prueba", "breed": "Bernese Mountain", "life_stage": "young"}
    before = {p["shopping_name"]: p["id"] for p in personalized_pet_products(pet)}
    after = {p["shopping_name"]: p["id"] for p in personalized_pet_products({**pet, "allergies": ["Pollo"]})}
    shared = before.keys() & after.keys()
    assert shared and all(before[name] == after[name] for name in shared)
    assert all(key not in before.values() for name, key in after.items() if name not in before)
    assert len(set(before.values())) == len(before)
    assert PRODUCTS == original


@pytest.fixture
def product_client(tmp_path, monkeypatch):
    from tools import roxy_home_service as service
    monkeypatch.setenv("ROXY_HOME_API_KEY", "test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "qa,other")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "food.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setenv("ROXY_HOME_RECIPE_IMAGE_GENERATION_ENABLED", "0")
    service._RATE_STATE.clear()
    client = TestClient(service.app)
    client.headers["Authorization"] = "Bearer test-key"
    pet = service._home_food_store().upsert_pet("qa", name="Prueba", species="ferret", exact_species="Ferret", life_stage="adult")
    return client, service, pet


def test_cart_revalidates_current_profile_and_preserves_both_stores_on_rejection(product_client):
    client, service, pet = product_client
    food = next(p for p in personalized_pet_products(pet) if p["brand"] == "Mazuri")
    path = f"/v1/home-food/qa/pets/{pet['id']}/products/{food['id']}/shopping"
    assert client.post(path, json={}).status_code == 409
    service._home_food_store().upsert_pet("qa", pet_id=pet["id"], name=pet["name"], species=pet["species"], allergies=["Pollo"])
    before_food = service._home_food_store().snapshot("qa")
    before_cart = service._store().snapshot("qa")
    response = client.post(path, json={"confirmed": True, "name": "forged harmless item"})
    assert response.status_code == 409
    assert service._home_food_store().snapshot("qa") == before_food
    after_cart = service._store().snapshot("qa")
    assert {k: v for k, v in after_cart.items() if k != "updated_at"} == {k: v for k, v in before_cart.items() if k != "updated_at"}


def test_product_endpoint_keeps_pet_context_and_never_purchases(product_client):
    client, service, pet = product_client
    carrier = next(p for p in personalized_pet_products(pet) if p["brand"] == "Kaytee")
    path = f"/v1/home-food/qa/pets/{pet['id']}/products/{carrier['id']}/shopping"
    response = client.post(path, json={"confirmed": True})
    assert response.status_code == 201, response.text
    item = response.json()["item"]
    assert item["category"] == "PETS" and item["status"] == "PENDING"
    assert item["source"] == "pet_recommendation"
    assert "Prueba" in item["notes"] and "medidas" in item["notes"]
    assert service._home_food_store().snapshot("qa")["pets"][0]["id"] == pet["id"]
    assert client.post(path.replace("/qa/", "/other/"), json={"confirmed": True}).status_code == 404
    assert client.post(path.replace(pet["id"], "unknown"), json={"confirmed": True}).status_code == 404
    assert client.post(path, headers={"Authorization": "Bearer wrong"}, json={"confirmed": True}).status_code == 403


def test_unknown_ingredient_restriction_blocks_add_even_with_forged_client_clearance(product_client):
    client, service, pet = product_client
    service._home_food_store().upsert_pet("qa", pet_id=pet["id"], name=pet["name"], species=pet["species"], allergies=["Cilantro"])
    food = next(p for p in personalized_pet_products(pet) if p["brand"] == "Mazuri")
    response = client.post(f"/v1/home-food/qa/pets/{pet['id']}/products/{food['id']}/shopping",
                           json={"confirmed": True, "safety": {"cart_blocked": False}})
    assert response.status_code == 409
    assert "compatibilidad" in response.json()["detail"]
    assert not service._store().snapshot("qa")["items"]


def test_pet_catalog_recipe_save_is_bound_to_a_current_matching_profile(product_client):
    client, service, ferret = product_client
    path = "/v1/home-food/qa/recipes"
    payload = {"prompt": "Huevo hervido", "catalog_key": "dog_hard_boiled_egg"}
    assert client.post(path, json=payload).status_code == 422
    assert client.post(path, json={**payload, "pet_id": ferret["id"]}).status_code == 422
    dog = service._home_food_store().upsert_pet("qa", name="Perro de prueba", species="dog", life_stage="adult")
    response = client.post(path, json={**payload, "pet_id": dog["id"]})
    assert response.status_code == 201, response.text
    recipe = response.json()["recipe"]
    assert recipe["pet_id"] == dog["id"] and recipe["pet_name"] == dog["name"]
    assert recipe["photo_asset_verified"] is True
    assert recipe["photo_asset"].endswith("dog-hard-boiled-egg-v2.jpg")
    service._home_food_store().upsert_pet("qa", pet_id=dog["id"], name=dog["name"], species="dog", allergies=["Huevo"])
    assert client.post(path, json={**payload, "pet_id": dog["id"]}).status_code == 422
    assert len(service._home_food_store().snapshot("qa")["recipes"]) == 1
    assert not service._store().snapshot("qa")["items"]
