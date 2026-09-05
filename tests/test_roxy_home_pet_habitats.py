from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from roxy_os.home_food import HomeFoodStore
from roxy_os.home_pet_habitats import habitat_plan, validate_observations, bird_diet_group
from roxy_os.home_pet_catalog import EXACT_SPECIES, personalized_pet_products
from roxy_os.home_recipe_fallback import personalized_pet_recipe_catalog


@pytest.mark.parametrize("species", ["dog", "cat", "ferret", "rabbit", "guinea_pig", "hamster", "small_mammal", "bird", "fish", "reptile", "amphibian", "invertebrate", "farm_pet", "other"])
def test_all_groups_have_observations_without_fake_measurements(species):
    plan = habitat_plan({"species": species})
    assert plan["values"] == {} and plan["recorded_at"] == ""
    assert plan["coverage"] == "group_guidance"
    assert len({field["key"] for field in plan["questions"]}) == len(plan["questions"])
    assert "sensores" in plan["disclosure"]


@pytest.mark.parametrize("species,required,absent", [
    ("fish", "ammonia", "flight_hours"), ("reptile", "uvb", "ph"),
    ("bird", "flight_hours", "nitrite"), ("amphibian", "ph", "bar_spacing_cm"),
])
def test_questions_change_by_species(species, required, absent):
    keys = {row["key"] for row in habitat_plan({"species": species})["questions"]}
    assert required in keys and absent not in keys


@pytest.mark.parametrize("name,group", [("Lori arcoíris", "nectar"), ("Mina", "softbill"), ("Canario", "canary"), ("Periquito australiano", "parrot"), ("Ave desconocida", "unverified")])
def test_bird_diets_do_not_cross_species(name, group):
    pet = {"id": "bird", "name": "Pío", "species": "bird", "exact_species": name, "life_stage": "adult"}
    assert bird_diet_group(pet) == group
    if group not in {"parrot", "canary"}:
        assert personalized_pet_recipe_catalog(pet, {}) == []
        assert all(row["category"] == "Transporte" for row in personalized_pet_products(pet))
    else:
        assert personalized_pet_recipe_catalog(pet, {})
    pet["habitat_observations"] = {"values": {"weaned": "No"}}
    assert personalized_pet_recipe_catalog(pet, {}) == []


def test_betta_water_alerts_and_unknown_stocking_are_not_marked_safe():
    pet = {"species": "fish", "exact_species": "Betta splendens", "habitat_observations": {"values": {"volume_l": 8, "ammonia": 0.2, "nitrite": 0, "residents": 2}}}
    plan = habitat_plan(pet)
    assert plan["coverage"] == "exact_species"
    assert any("Amoniaco detectable" in text for text in plan["alerts"])
    assert not any("Nitrito detectable" in text for text in plan["alerts"])
    assert any("20 L" in text for text in plan["alerts"])
    assert any("Convivencia" in text for text in plan["alerts"])
    assert any("no aplica una regla universal" in row["text"] for row in plan["sections"])


def test_marine_fish_do_not_get_a_freshwater_test():
    pet = {"species": "fish", "exact_species": "Pez marino", "habitat_observations": {"values": {"water_type": "Marina"}}}
    assert not any("Freshwater" in row["name"] for row in personalized_pet_products(pet))


@pytest.mark.parametrize("values", [{"ph": 15}, {"volume_l": "NaN"}, {"volume_l": "Infinity"}, {"residents": 1.5}, {"residents": True}, {"cycled": "inventado"}, {"flight_hours": 2}])
def test_invalid_observations_rejected(values):
    with pytest.raises(ValueError):
        validate_observations({"species": "fish"}, values)


def test_zero_is_a_reading_not_a_missing_value():
    assert validate_observations({"species": "fish"}, {"ammonia": 0, "nitrite": "0", "ph": ""}) == {"ammonia": 0.0, "nitrite": 0.0, "ph": None}


def test_habitat_updates_preserve_photo_history_identity_and_other_pets(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")
    first = store.upsert_pet("qa", name="Azul", species="fish", exact_species="Betta splendens", photo_data_url="data:image/jpeg;base64,AA==")
    other = store.upsert_pet("qa", name="Luna", species="ferret")
    store.add_pet_medical_record("qa", first["id"], title="Revisión")
    before = store.snapshot("qa")["pets"][0]
    store.record_pet_habitat("qa", first["id"], {"volume_l": 25, "ammonia": 0})
    store.record_pet_habitat("qa", first["id"], {"ph": 7})
    after = store.snapshot("qa")["pets"]
    assert after[0]["photo_data_url"] == before["photo_data_url"]
    assert after[0]["medical_history"] == before["medical_history"]
    assert after[1] == other
    assert after[0]["habitat_observations"]["values"] == {"volume_l": 25, "ammonia": 0, "ph": 7}
    assert len(after[0]["habitat_history"]) == 2
    assert store.snapshot("someone_else")["pets"] == []
    store.upsert_pet("qa", pet_id=first["id"], name="Azul", species="fish")
    assert store.snapshot("qa")["pets"][0]["habitat_history"] == after[0]["habitat_history"]


def test_medical_history_keeps_more_than_one_hundred_records(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")
    pet = store.upsert_pet("qa", name="Pío", species="bird")
    for number in range(105):
        store.add_pet_medical_record("qa", pet["id"], title=f"Observación {number}")
    history = store.snapshot("qa")["pets"][0]["medical_history"]
    assert len(history) == 105 and history[0]["title"] == "Observación 0"


def test_habitat_api_separates_care_from_recipes_and_limits_owner(tmp_path, monkeypatch):
    from tools import roxy_home_service as service
    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "qa,other")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    service._RATE_STATE.clear()
    client = TestClient(service.app)
    headers = {"Authorization": "Bearer home-test-key"}
    pet = client.post("/v1/home-food/qa/pets", headers=headers, json={"name": "Pío", "species": "bird", "exact_species": "Periquito australiano"}).json()["pet"]
    path = f"/v1/home-food/qa/pets/{pet['id']}/habitat"
    assert client.put(path, json={"values": {}}).status_code == 401
    assert client.put(path.replace("/qa/", "/other/"), headers=headers, json={"values": {}}).status_code == 404
    assert client.put(path, headers=headers, json={"values": {"flight_hours": 4}}).status_code == 200
    assert client.put(path, headers=headers, json={"values": {"ph": 7}}).status_code == 422
    data = client.get("/v1/home-food/qa", headers=headers).json()
    assert data["pet_habitat_plans"][pet["id"]]["values"]["flight_hours"] == 4
    assert all(row["safety_class"] != "feeding_guide" for row in data["pet_recipe_recommendations"][pet["id"]])
    assert all(row["safety_class"] == "feeding_guide" and "photo_asset" not in row for row in data["pet_care_guides"][pet["id"]])
