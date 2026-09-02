import json
from pathlib import Path

from fastapi.testclient import TestClient

from roxy_os.home_food import cooking_step_timer_seconds


def test_cooking_step_timer_detects_wait_time_without_confusing_oven_temperature():
    assert cooking_step_timer_seconds("Deja reposar 30 minutos mientras calientas el horno a 220 °C.") == 1800
    assert cooking_step_timer_seconds("Hornea 1 hora y 15 minutos.") == 4500
    assert cooking_step_timer_seconds("Mezcla hasta formar una masa uniforme.") == 0


def test_local_catalog_includes_species_specific_pet_recipes_with_safety_notes():
    from roxy_os.home_recipe_fallback import local_recipe_catalog

    rows = [row for row in local_recipe_catalog({}) if row.get("audience") == "pet"]
    assert len(rows) == 64
    assert {row["pet_species"] for row in rows} == {
        "dog", "cat", "ferret", "bird", "rabbit", "hamster", "guinea_pig", "fish", "reptile", "amphibian",
        "small_mammal", "invertebrate", "farm_pet", "other",
    }
    assert {species: sum(row["pet_species"] == species for row in rows) for species in ("dog", "cat", "ferret", "fish")} == {"dog": 22, "cat": 9, "ferret": 8, "fish": 4}
    assert {row["safety_class"] for row in rows} == {"treat", "feeding_guide"}
    assert all("no sustituye" in row["veterinary_note"].lower() for row in rows if row["safety_class"] == "treat")
    illustrated = [row for row in rows if row.get("photo_asset")]
    assert len(illustrated) == 24
    assert all(row["photo_asset"].startswith("/assets/roxy_home/recipes/pets/") for row in illustrated)
    assert all(len(row["steps"]) >= 5 for row in rows)
    assert all(Path(row["photo_asset"].removeprefix("/")).is_file() for row in illustrated)
    bernese = [row for row in rows if "bernese mountain" in row.get("pet_exact_terms", [])]
    assert len(bernese) == 12
    assert all(row.get("photo_asset") and row.get("personalization_scope") == "breed_and_life_stage" for row in bernese)
    assert all(row.get("pet_life_stages") == ["baby", "young"] for row in bernese)
    assert {row.get("pet_variety") for row in bernese} >= {
        "Horneado", "Proteína simple", "Congelado fresco", "Horneado crujiente"
    }


def test_catalog_recipe_save_survives_optional_photo_queue_failure(tmp_path, monkeypatch):
    from tools import roxy_home_service

    class BrokenPhotoQueue:
        def schedule(self, recipe):
            raise OSError("artwork storage unavailable")

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home-food.json"))
    monkeypatch.setattr(roxy_home_service, "_recipe_photo_queue", lambda: BrokenPhotoQueue())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    response = client.post(
        "/v1/home-food/robert/recipes",
        headers={"Authorization": "Bearer home-test-key"},
        json={
            "prompt": "Bocaditos de corazón de pollo para hurones",
            "mode": "routine",
            "recipe_type": "general",
            "catalog_key": "ferret_chicken_heart_bites",
        },
    )

    assert response.status_code == 201
    assert response.json()["recipe"]["audience"] == "pet"


class FakeHomeAI:
    def generate_recipe(self, prompt, snapshot, *, deep=False):
        return {
            "title": "Pasta de Roxy",
            "description": prompt,
            "servings": 2,
            "ingredients": [{"name": "Pasta", "quantity": 1, "unit": "paquete"}],
            "steps": ["Cocinar la pasta"],
            "allergen_notes": [],
        }

    def import_recipe(self, source, snapshot, *, source_type, audience="human", pet_species=""):
        return {
            "title": "Premios de calabaza para perros" if audience == "pet" else "Avena de la abuela",
            "description": "Receta importada para revisar.",
            "kind": "other" if audience == "pet" else "meal",
            "servings": 8 if audience == "pet" else 2,
            "ingredients": [{"name": "Calabaza" if audience == "pet" else "Avena", "quantity": 1, "unit": "taza"}],
            "steps": ["Mezcla los ingredientes.", "Cocina hasta que estén listos."],
            "allergen_notes": [], "audience": audience, "pet_species": pet_species,
            "safety_class": "treat" if audience == "pet" else "",
            "veterinary_note": "Premio ocasional; no sustituye una dieta completa." if audience == "pet" else "",
        }


def test_home_food_api_requires_confirmation_before_touching_shopping_list(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: FakeHomeAI())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    profile = client.put(
        "/v1/home-food/robert/profile",
        headers=headers,
        json={"preferences": ["Mediterránea"], "allergies": ["Nueces"], "household_size": 2},
    )
    recipe_response = client.post(
        "/v1/home-food/robert/recipes",
        headers=headers,
        json={"prompt": "Una cena rápida", "mode": "routine"},
    )
    recipe_id = recipe_response.json()["recipe"]["id"]
    blocked = client.post(
        f"/v1/home-food/robert/recipes/{recipe_id}/shopping-commit",
        headers=headers,
        json={"confirmed": False},
    )
    before = client.get("/v1/shopping/robert", headers=headers)
    committed = client.post(
        f"/v1/home-food/robert/recipes/{recipe_id}/shopping-commit",
        headers=headers,
        json={"confirmed": True},
    )
    after = client.get("/v1/shopping/robert", headers=headers)
    isolated = client.get("/v1/home-food/alice", headers=headers)

    assert profile.status_code == 200
    assert recipe_response.status_code == 201
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "CONFIRMATION_REQUIRED"
    assert before.json()["items"] == []
    assert committed.json()["status"] == "ADDED"
    assert after.json()["items"][0]["name"] == "Pasta"
    assert isolated.json()["recipes"] == []


def test_recipe_import_is_reviewed_before_save_and_pet_profile_syncs(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: FakeHomeAI())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    pet = client.post("/v1/home-food/robert/pets", headers=headers, json={"name": "Luna", "species": "dog"})
    preview = client.post("/v1/home-food/robert/recipe-imports", headers=headers, json={
        "source_type": "image", "source": "data:image/jpeg;base64,AA==", "audience": "pet", "pet_species": "dog",
    })
    blocked = client.post("/v1/home-food/robert/recipe-imports/commit", headers=headers, json={"confirmed": False, "recipe": preview.json()["recipe"]})
    committed = client.post("/v1/home-food/robert/recipe-imports/commit", headers=headers, json={"confirmed": True, "recipe": preview.json()["recipe"]})
    robert = client.get("/v1/home-food/robert", headers=headers).json()
    alice = client.get("/v1/home-food/alice", headers=headers).json()

    assert pet.status_code == 201
    assert preview.status_code == 200 and preview.json()["status"] == "READY_FOR_REVIEW"
    assert preview.json()["recipe"]["safety_class"] == "treat"
    assert blocked.status_code == 409
    assert committed.status_code == 201
    assert robert["pets"] == [pet.json()["pet"]]
    assert robert["recipes"][0]["pet_species"] == "dog"
    assert alice["pets"] == [] and alice["recipes"] == []


def test_pet_profile_supports_species_specific_private_care_context(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home-food.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}
    response = client.post(
        "/v1/home-food/robert/pets",
        headers=headers,
        json={
            "name": "Azul", "species": "fish", "exact_species": "Betta splendens", "age_years": 1.5,
            "life_stage": "adult", "current_food": "Pellets para betta", "habitat_type": "Acuario de agua dulce",
            "environment_notes": "20 litros, filtrado y ciclado; 26 °C", "routine_notes": "Revisar agua cada semana",
            "allergies": [], "conditions": [], "veterinarian_instructions": "No cambiar el tratamiento sin consultar.",
        },
    )

    assert response.status_code == 201
    pet = response.json()["pet"]
    assert pet["species"] == "fish"
    assert pet["exact_species"] == "Betta splendens"
    assert pet["profile_complete"] is False
    snapshot = client.get("/v1/home-food/robert", headers=headers).json()
    assert snapshot["pets"][0]["habitat_type"] == "Acuario de agua dulce"
    assert snapshot["pet_profile_completions"][pet["id"]]["percent"] < 100
    assert snapshot["pet_profile_completions"][pet["id"]]["next_step"] == 2


def test_pet_profile_completion_is_species_aware_and_explainable():
    from roxy_os.home_pet_catalog import pet_profile_completion

    dog = pet_profile_completion({
        "species": "dog", "breed": "Golden Retriever", "life_stage": "adult", "weight_kg": 28,
        "allergies": ["Ninguna conocida"], "conditions": ["Ninguna diagnosticada"],
        "current_food": "Alimento completo adulto", "current_food_kind": "complete",
        "feeding_frequency": 2, "feeding_times": ["07:30", "18:30"],
        "feeding_amount_source": "label", "feeding_amount": 280, "feeding_unit": "g",
        "routine_notes": "Paseo por la mañana y por la tarde",
    })
    fish = pet_profile_completion({
        "species": "fish", "exact_species": "Betta splendens", "life_stage": "adult",
        "allergies": ["Ninguna conocida"], "conditions": ["Ninguna observada"],
        "current_food": "Pellets para betta", "current_food_kind": "complete",
        "feeding_frequency": 2, "feeding_times": ["09:00", "18:00"],
        "feeding_amount_source": "specialist", "habitat_type": "Acuario de agua dulce",
        "environment_notes": "20 litros, filtrado y ciclado; 26 °C", "routine_notes": "Revisión semanal del agua",
    })
    unidentified = pet_profile_completion({"species": "other", "exact_species": "Especie exótica con permiso"})

    assert dog["status"] == "complete" and dog["percent"] == 100
    assert fish["status"] == "complete" and fish["percent"] == 100
    assert unidentified["missing"][0]["field"] == "exact_species"
    assert all({"field", "label", "step", "reason"} <= item.keys() for item in unidentified["missing"])


def test_pet_profile_exposes_breeds_products_and_private_medical_history(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home-food.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}
    created = client.post(
        "/v1/home-food/robert/pets",
        headers=headers,
        json={
            "name": "Luna", "species": "dog", "breed": "Golden Retriever", "life_stage": "adult",
            "sex": "female", "sterilized": "yes", "size_class": "large", "activity_level": "moderate",
            "body_condition": "ideal", "goals": ["Piel y pelaje"], "conditions": ["Piel sensible"],
            "allergies": ["Pollo"], "current_food": "Alimento seco actual", "current_food_kind": "complete",
            "feeding_amount": 280, "feeding_unit": "g", "feeding_frequency": 2,
            "feeding_times": ["07:30", "18:30"], "feeding_amount_source": "veterinarian",
            "feeding_notes": "Transición completada.",
        },
    )
    pet_id = created.json()["pet"]["id"]
    medical = client.post(
        f"/v1/home-food/robert/pets/{pet_id}/medical-history",
        headers=headers,
        json={
            "occurred_on": "2026-08-20", "record_type": "checkup", "title": "Revisión anual",
            "provider": "Clínica Central", "notes": "Peso estable.", "medications": ["Ninguno"],
            "next_due_on": "2026-09-20", "weight_kg": 28.4,
            "attachment_name": "resultado.pdf", "attachment_type": "application/pdf",
            "attachment_data_url": "data:application/pdf;base64,JVBERi0xLjQK",
        },
    )
    completed = client.post(
        f"/v1/home-food/robert/pets/{pet_id}/care-log",
        headers=headers,
        json={"routine_id": "morning_meal", "title": "Alimentación de la mañana"},
    )
    feeding = client.post(
        f"/v1/home-food/robert/pets/{pet_id}/care-log",
        headers=headers,
        json={"routine_id": "feeding_observation", "title": "Registro de alimentación", "outcome": "partial"},
    )
    snapshot = client.get("/v1/home-food/robert", headers=headers).json()

    assert created.status_code == 201 and medical.status_code == 201 and completed.status_code == 201 and feeding.status_code == 201
    assert "Golden Retriever" in snapshot["pet_options"]["breeds"]["dog"]
    assert "Betta splendens" in snapshot["pet_options"]["exact_species"]["fish"]
    assert len(snapshot["pet_options"]["breeds"]["dog"]) >= 80
    assert len(snapshot["pet_recommendations"][pet_id]) >= 3
    assert all(row["name"] != "Adult Perfect Weight" for row in snapshot["pet_recommendations"][pet_id])
    assert any(row["brand"] == "Royal Canin" and row["select_before_cart"] for row in snapshot["pet_recommendations"][pet_id])
    assert snapshot["pets"][0]["medical_history"][0]["title"] == "Revisión anual"
    assert snapshot["pets"][0]["medical_history"][0]["next_due_on"] == "2026-09-20"
    assert snapshot["pets"][0]["medical_history"][0]["weight_kg"] == 28.4
    assert snapshot["pets"][0]["medical_history"][0]["attachment_name"] == "resultado.pdf"
    assert snapshot["pets"][0]["medical_history"][0]["attachment_data_url"].startswith("data:application/pdf;base64,")
    assert snapshot["pets"][0]["care_log"][0]["routine_id"] == "morning_meal"
    assert snapshot["pet_care_plans"][pet_id]["routines"][0]["completed_today"] is True
    assert snapshot["pet_care_plans"][pet_id]["information"]["life_expectancy"] == "10–15 años"
    assert "comidas al día" in snapshot["pet_care_plans"][pet_id]["information"]["feeding"]
    assert snapshot["pet_nutrition_plans"][pet_id]["amount"] == 280
    assert snapshot["pet_nutrition_plans"][pet_id]["frequency"] == 2
    assert snapshot["pet_nutrition_plans"][pet_id]["last_feeding"]["outcome"] == "partial"
    assert snapshot["pets"][0]["goals"] == ["Piel y pelaje"]


def test_pet_care_repairs_legacy_null_log_instead_of_returning_http_500(tmp_path, monkeypatch):
    from tools import roxy_home_service

    memory_path = tmp_path / "home-food.json"
    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(memory_path))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}
    created = client.post(
        "/v1/home-food/robert/pets",
        headers=headers,
        json={"name": "Bella", "species": "dog", "life_stage": "young"},
    )
    pet_id = created.json()["pet"]["id"]
    legacy = json.loads(memory_path.read_text(encoding="utf-8"))
    legacy["users"]["robert"]["revision"] = "legacy"
    legacy["users"]["robert"]["recipes"] = None
    legacy["users"]["robert"]["pantry"] = None
    legacy["users"]["robert"]["pets"][0]["care_log"] = None
    legacy["users"]["robert"]["pets"].append(None)
    memory_path.write_text(json.dumps(legacy), encoding="utf-8")

    completed = client.post(
        f"/v1/home-food/robert/pets/{pet_id}/care-log",
        headers=headers,
        json={"routine_id": "morning_meal", "title": "Alimentación de la mañana"},
    )

    assert completed.status_code == 201
    snapshot = client.get("/v1/home-food/robert", headers=headers).json()
    assert snapshot["pets"][0]["care_log"][0]["routine_id"] == "morning_meal"


def test_pet_care_compacts_in_place_when_persistent_disk_cannot_allocate_temp_file(tmp_path, monkeypatch):
    import errno

    from roxy_os import atomic_json
    from roxy_os.home_food import HomeFoodStore

    memory_path = tmp_path / "home-food.json"
    store = HomeFoodStore(memory_path)
    pet = store.upsert_pet("local_user", name="Bella", species="dog")

    def disk_full(*_args, **_kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(atomic_json.tempfile, "mkstemp", disk_full)
    entry = store.complete_pet_care_routine(
        "local_user", pet["id"], routine_id="morning_meal", title="Alimentación de la mañana"
    )

    saved = json.loads(memory_path.read_text(encoding="utf-8"))
    assert entry["routine_id"] == "morning_meal"
    assert saved["users"]["local_user"]["pets"][0]["care_log"][0]["routine_id"] == "morning_meal"
    assert "\n" not in memory_path.read_text(encoding="utf-8")


def test_pet_information_uses_exact_breed_profile_instead_of_generic_dog_copy(tmp_path):
    from roxy_os.home_food import HomeFoodStore
    from roxy_os.home_pet_catalog import personalized_pet_care_plan

    store = HomeFoodStore(tmp_path / "home-food.json")
    bella = store.upsert_pet(
        "local_user", name="Bella", species="dog", breed="Bernese Mountain", life_stage="young"
    )
    plan = personalized_pet_care_plan(bella)

    assert plan["information"]["scope"] == "breed"
    assert plan["information"]["display_name"] == "Bernese Mountain Dog"
    assert plan["information"]["life_expectancy"] == "7–10 años"
    assert "Bella" in plan["information"]["characteristics"]
    assert "sarcoma histiocítico" in plan["information"]["common_health"]
    assert plan["information"]["frequency"].startswith("Joven:")
    assert plan["source_label"] == "AKC y BMDCA · Bernese Mountain Dog"


def test_bella_products_are_concrete_illustrated_and_never_use_adult_food():
    from roxy_os.home_pet_catalog import personalized_pet_products

    rows = personalized_pet_products({
        "name": "Bella", "species": "dog", "breed": "Bernese Mountain", "life_stage": "young"
    })
    specific = [row for row in rows if row.get("identity_specific")]

    assert len(specific) == 10
    assert all(row.get("image_url", "").startswith("/assets/roxy_home/products/pets/") for row in specific)
    assert all(Path(row["image_url"].removeprefix("/")).is_file() for row in specific)
    assert all("Bella" in row["reason"] for row in specific)
    assert {row["category"] for row in specific} >= {
        "Alimento para crecimiento", "Higiene dental", "Paseo diario", "Comedero interactivo",
        "Cepillado del manto",
    }
    assert any(row["name"] == "Front Range Harness" and row["requires_measurement"] for row in specific)
    assert not any("Adult Chicken" in row["name"] for row in rows)


def test_products_keep_each_supported_pet_identity_and_do_not_require_a_goal_for_safe_essentials():
    from roxy_os.home_pet_catalog import personalized_pet_products

    profiles = [
        ("dog", "Bernese Mountain"), ("cat", "Maine Coon"), ("ferret", "Hurón doméstico"),
        ("rabbit", "Holland Lop"), ("guinea_pig", "American"), ("hamster", "Sirio"),
        ("bird", "Periquito australiano"), ("fish", "Betta splendens"),
        ("reptile", "Gecko leopardo"), ("amphibian", "Ajolote"),
        ("small_mammal", "Chinchilla"), ("invertebrate", "Tarántula"),
        ("farm_pet", "Cerdo miniatura"),
    ]
    for index, (species, identity) in enumerate(profiles, start=1):
        pet = {
            "name": f"Mascota {index}", "species": species, "life_stage": "adult", "goals": [],
            "breed": identity if species in {"dog", "cat"} else "",
            "exact_species": identity if species not in {"dog", "cat"} else "",
        }
        rows = personalized_pet_products(pet)
        assert rows, (species, identity)
        assert all(row["profile_label"].startswith(f"Para Mascota {index} · {identity}") for row in rows)
        assert all(f"Mascota {index}" in row["reason"] for row in rows)
        assert not any(row["name"] == "Adult Perfect Weight" for row in rows)

    weight_rows = personalized_pet_products({
        "name": "Max", "species": "dog", "breed": "Labrador Retriever", "life_stage": "adult",
        "goals": ["Bajar peso"],
    })
    assert any(row["name"] == "Adult Perfect Weight" for row in weight_rows)


def test_pet_care_supports_companion_animals_beyond_dogs_and_cats(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home-food.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}
    animals = [
        ("ferret", "Hurón doméstico"), ("rabbit", "Holland Lop"),
        ("guinea_pig", "American"), ("hamster", "Sirio"),
        ("small_mammal", "Chinchilla"), ("bird", "Ninfa / cockatiel"),
        ("fish", "Betta splendens"), ("reptile", "Gecko leopardo"),
        ("amphibian", "Ajolote"), ("invertebrate", "Tarántula"),
        ("farm_pet", "Cerdo miniatura"), ("other", "Otra especie doméstica"),
    ]
    for index, (species, exact_species) in enumerate(animals):
        response = client.post(
            "/v1/home-food/robert/pets",
            headers=headers,
            json={"name": f"Mascota {index}", "species": species, "exact_species": exact_species},
        )
        assert response.status_code == 201

    snapshot = client.get("/v1/home-food/robert", headers=headers).json()
    assert len(snapshot["pets"]) == len(animals)
    assert len(snapshot["pet_care_plans"]) == len(animals)
    assert all(len(plan["sections"]) >= 5 for plan in snapshot["pet_care_plans"].values())
    assert all(len(plan["routines"]) >= 3 for plan in snapshot["pet_care_plans"].values())
    assert "Chinchilla" in snapshot["pet_options"]["exact_species"]["small_mammal"]
    assert "Tarántula" in snapshot["pet_options"]["exact_species"]["invertebrate"]
    assert "Cerdo miniatura" in snapshot["pet_options"]["exact_species"]["farm_pet"]
    assert any(
        row["brand"] == "Mazuri"
        for pet in snapshot["pets"] if pet["species"] == "ferret"
        for row in snapshot["pet_recommendations"][pet["id"]]
    )
    ferret = next(pet for pet in snapshot["pets"] if pet["species"] == "ferret")
    assert {row["brand"] for row in snapshot["pet_recommendations"][ferret["id"]]} >= {"Mazuri", "Oxbow", "Wysong"}
    assert all(row.get("image_url", "").startswith("https://") for row in snapshot["pet_recommendations"][ferret["id"]])
    assert snapshot["pet_care_plans"][ferret["id"]]["information"]["life_expectancy"] == "5–10 años"
    assert snapshot["pet_care_plans"][ferret["id"]]["information"]["frequency"] == "Varias comidas pequeñas al día"
    assert "Insulinoma o hipoglucemia" in snapshot["pet_options"]["conditions"]["ferret"]
    assert "Vitamina C" in snapshot["pet_options"]["goals"]["guinea_pig"]


def test_weekly_plan_is_local_persistent_and_requires_confirmation_for_shopping(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    created = client.post(
        "/v1/home-food/robert/weekly-plans",
        headers=headers,
        json={"style": "quick", "people": 2, "max_minutes": 20, "weekly_budget": 85, "cook_days": 2, "meal_scope": "lunch_dinner"},
    )
    assert created.status_code == 201
    plan = created.json()["plan"]
    assert plan["generation_source"] == "local_weekly_catalog"
    assert len(plan["days"]) == 7
    assert all(len(day["meals"]) == 2 for day in plan["days"])
    assert all([meal["meal_type"] for meal in day["meals"]] == ["lunch", "dinner"] for day in plan["days"])
    assert len(plan["prep_sessions"]) == 2
    assert max(meal["minutes"] for day in plan["days"] for meal in day["meals"]) <= 20

    original_title = plan["days"][0]["meals"][0]["title"]
    swapped = client.patch(
        f"/v1/home-food/robert/weekly-plans/{plan['id']}/meal",
        headers=headers,
        json={"day_index": 0, "meal_index": 0, "action": "swap"},
    )
    assert swapped.status_code == 200
    assert swapped.json()["plan"]["days"][0]["meals"][0]["title"] != original_title
    favorite = client.patch(
        f"/v1/home-food/robert/weekly-plans/{plan['id']}/meal",
        headers=headers,
        json={"day_index": 0, "meal_index": 0, "action": "favorite"},
    )
    assert favorite.status_code == 200
    assert favorite.json()["plan"]["days"][0]["meals"][0]["favorite"] is True

    lived = client.patch(
        f"/v1/home-food/robert/weekly-plans/{plan['id']}/day",
        headers=headers,
        json={"day_index": 1, "action": "leftovers"},
    )
    assert lived.status_code == 200
    assert lived.json()["plan"]["days"][1]["status"] == "leftovers"
    assert lived.json()["shopping_preview"]

    blocked = client.post(
        f"/v1/home-food/robert/weekly-plans/{plan['id']}/shopping-commit",
        headers=headers,
        json={"confirmed": False, "excluded_days": []},
    )
    committed = client.post(
        f"/v1/home-food/robert/weekly-plans/{plan['id']}/shopping-commit",
        headers=headers,
        json={"confirmed": True, "excluded_days": [0]},
    )
    robert = client.get("/v1/home-food/robert", headers=headers).json()
    alice = client.get("/v1/home-food/alice", headers=headers).json()

    assert blocked.status_code == 409
    assert committed.status_code == 200
    assert committed.json()["items"]
    assert robert["weekly_plans"][-1]["id"] == plan["id"]
    assert robert["weekly_plans"][-1]["days"][1]["status"] == "leftovers"
    assert robert["meal_planning"]["cook_days"] == 2
    assert robert["meal_planning"]["meal_scope"] == "lunch_dinner"
    assert alice["weekly_plans"] == []


def test_roxy_conversation_controls_days_and_reuses_available_recipes(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    created = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, organiza nuestro plan de comidas de la semana"},
    )
    assert created.status_code == 200
    assert created.json()["intent"] == "weekly_create"
    assert created.json()["agent"] == "home_food"

    monday = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, ¿qué comemos el lunes?"},
    )
    assert monday.status_code == 200
    assert monday.json()["intent"] == "weekly_query"
    assert "Para Lunes" in monday.json()["speech"]

    skipped = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, el martes no voy a cocinar"},
    )
    assert skipped.status_code == 200
    skipped_plan = skipped.json()["data"]["weekly_plan"]
    assert skipped_plan["days"][roxy_home_service._weekly_day_index("martes", skipped_plan)]["status"] == "skipped"

    leftovers = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, el miércoles comeremos las sobras"},
    )
    assert leftovers.status_code == 200
    leftovers_plan = leftovers.json()["data"]["weekly_plan"]
    assert leftovers_plan["days"][roxy_home_service._weekly_day_index("miércoles", leftovers_plan)]["status"] == "leftovers"

    recipe = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, dame la receta de la cena del jueves"},
    )
    assert recipe.status_code == 200
    assert recipe.json()["intent"] == "weekly_recipe"
    assert recipe.json()["data"]["recipe"]["steps"]
    assert recipe.json()["data"]["generation_mode"] == "local_recipe_catalog"

    adapted = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, hoy no cociné, tengo pollo y arroz"},
    )
    assert adapted.status_code == 200
    assert adapted.json()["intent"] == "weekly_from_pantry"
    assert adapted.json()["data"]["recipe"]["generation_source"] == "local_recipe_catalog"
    assert "No añadí nada a compras" in adapted.json()["speech"]
    adapted_plan = adapted.json()["data"]["weekly_plan"]
    assert any(
        meal.get("recipe_id") == adapted.json()["data"]["recipe"]["id"]
        for meal in adapted_plan["days"][roxy_home_service._weekly_day_index("hoy", adapted_plan)]["meals"]
    )

    cookbook = client.get("/v1/home-food/robert", headers=headers).json()
    assert cookbook["local_catalog"]["total"] == len(cookbook["local_recipes"])
    assert cookbook["local_catalog"]["total"] >= 70
    assert {"Avena nocturna con frutas", "Quesadilla de pollo y vegetales"}.issubset(
        {row["title"] for row in cookbook["local_recipes"]}
    )


def test_voice_can_create_recipe_add_ingredients_and_remove_naturally(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: FakeHomeAI())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    recipe = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Roxy, dame una receta de pasta de verdad"},
    )
    add = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "agrega todos los ingredientes de esta receta a mi lista"},
    )
    remove = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "saca las pastas de mi lista de compras"},
    )
    final_list = client.get("/v1/shopping/robert", headers=headers)

    assert recipe.status_code == 200
    assert recipe.json()["intent"] == "recipe_generate"
    assert recipe.json()["data"]["recipe"]["title"] == "Pasta rápida con tomate y ajo"
    assert recipe.json()["data"]["generation_mode"] == "voice_local_recipe_catalog"
    assert add.json()["intent"] == "recipe_to_shopping"
    assert add.json()["data"]["items"][0]["name"] == "Pasta"
    assert remove.json()["intent"] == "shopping_remove"
    assert "Pasta" in remove.json()["message"]
    assert all(row["name"] != "Pasta" for row in final_list.json()["items"])
    assert len(final_list.json()["items"]) == 4


def test_recipe_can_be_deleted_without_touching_another_users_library(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: FakeHomeAI())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}
    robert = client.post(
        "/v1/home-food/robert/recipes",
        headers=headers,
        json={"prompt": "Pasta para Robert", "mode": "routine"},
    ).json()["recipe"]
    alice = client.post(
        "/v1/home-food/alice/recipes",
        headers=headers,
        json={"prompt": "Pasta para Alice", "mode": "routine"},
    ).json()["recipe"]
    session = client.post(
        f"/v1/home-food/robert/recipes/{robert['id']}/cooking-sessions",
        headers=headers,
        json={},
    )
    deleted = client.delete(
        f"/v1/home-food/robert/recipes/{robert['id']}", headers=headers
    )
    robert_snapshot = client.get("/v1/home-food/robert", headers=headers).json()
    alice_snapshot = client.get("/v1/home-food/alice", headers=headers).json()
    missing = client.delete(
        f"/v1/home-food/robert/recipes/{robert['id']}", headers=headers
    )

    assert session.status_code == 201
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "DELETED"
    assert robert_snapshot["recipes"] == []
    assert robert_snapshot["cooking_sessions"] == []
    assert alice_snapshot["recipes"][0]["id"] == alice["id"]
    assert missing.status_code == 404
