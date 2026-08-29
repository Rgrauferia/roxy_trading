import base64

from fastapi.testclient import TestClient

from roxy_os.home_plants import HomePlantIdentifier, HomePlantStore


PHOTO_BYTES = b"\xff\xd8\xff" + (b"roxy-home-plant" * 2) + b"\xff\xd9"
PHOTO = "data:image/jpeg;base64," + base64.b64encode(PHOTO_BYTES).decode("ascii")


def plant_payload(**overrides):
    value = {
        "display_name": "Albahaca de la cocina",
        "species_key": "basil",
        "room": "Cocina",
        "placement": "indoor",
        "pot_type": "terracotta",
        "drainage": True,
        "notes": "Cerca de la ventana, sin sol fuerte de tarde.",
        "photo_data_url": PHOTO,
    }
    value.update(overrides)
    return value


def test_plant_store_persists_household_care_and_requires_real_confirmation(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    proposed = store.create(
        "hogar-1",
        "robert",
        plant_payload(species_key="unknown"),
        {"status": "PROPOSED", "species_key": "basil", "confidence": 0.81, "warning": "Confirma la especie."},
    )

    assert proposed["species_key"] == "basil"
    assert proposed["identification"]["status"] == "PROPOSED"
    assert store.snapshot("hogar-1", "roxy")["plants"][0]["display_name"] == "Albahaca de la cocina"
    assert store.snapshot("otro-hogar", "alice")["plants"] == []

    confirmed = store.update("hogar-1", proposed["id"], {"species_key": "basil"})
    assert confirmed["identification"]["status"] == "CONFIRMED"


def test_plant_care_records_observation_and_schedules_next_check(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    plant = store.create("hogar-1", "robert", plant_payload())
    first = plant["care_tasks"][0]

    updated = store.complete_task("hogar-1", plant["id"], first["id"], "Robert", "Tierra seca; regué y dejé drenar")

    assert updated["care_tasks"][0]["status"] == "DONE"
    assert updated["care_tasks"][0]["completed_by"] == "Robert"
    assert updated["care_tasks"][0]["result"] == "WATERED"
    assert updated["care_tasks"][1]["status"] == "PENDING"
    assert updated["care_tasks"][1]["action"] == "CHECK_SOIL"


def test_plant_identifier_has_safe_manual_fallback_without_home_key():
    proposal = HomePlantIdentifier(None).identify(PHOTO)

    assert proposal["status"] == "UNAVAILABLE"
    assert proposal["species_key"] == "unknown"
    assert "manualmente" in proposal["warning"]


def test_home_plants_api_is_private_persistent_and_serves_the_uploaded_photo(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "plants-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_PLANTS_PATH", str(tmp_path / "plants.json"))
    monkeypatch.setenv("ROXY_HOME_PLANTS_IMAGE_DIR", str(tmp_path / "images"))
    monkeypatch.setenv("ROXY_HOME_CALENDAR_PATH", str(tmp_path / "calendar.json"))
    monkeypatch.delenv("ROXY_HOME_OPENAI_API_KEY", raising=False)
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    headers = {"Authorization": "Bearer plants-test-key"}

    created = client.post("/v1/home-plants/robert", headers=headers, json=plant_payload())
    plant = created.json()["plant"]
    listed = client.get("/v1/home-plants/robert", headers=headers)
    image = client.get(plant["photo_url"], headers=headers)
    forbidden = client.get("/v1/home-plants/alice", headers=headers)
    task = plant["care_tasks"][0]
    completed = client.post(
        f"/v1/home-plants/robert/{plant['id']}/tasks/{task['id']}/complete",
        headers=headers,
        json={"observation": "La tierra sigue húmeda; no regué."},
    )
    journal = client.post(
        f"/v1/home-plants/robert/{plant['id']}/journal",
        headers=headers,
        json={"notes": "Hoja nueva", "photo_data_url": PHOTO},
    )
    refreshed = client.get("/v1/home-plants/robert", headers=headers).json()
    entry = refreshed["plants"][0]["journal"][0]
    journal_image = client.get(entry["photo_url"], headers=headers)

    assert created.status_code == 201
    assert listed.status_code == 200
    assert listed.json()["plants"][0]["common_name"] == "Albahaca"
    assert image.status_code == 200 and image.content == PHOTO_BYTES
    assert forbidden.status_code == 403
    assert completed.status_code == 200
    assert completed.json()["plant"]["care_tasks"][0]["status"] == "DONE"
    assert journal.status_code == 201
    assert entry["notes"] == "Hoja nueva"
    assert journal_image.status_code == 200 and journal_image.content == PHOTO_BYTES


def test_plant_photo_validation_rejects_non_image_content(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    bad = "data:image/jpeg;base64," + base64.b64encode(b"not-a-jpeg-at-all-but-long-enough").decode("ascii")

    try:
        store.create("hogar-1", "robert", plant_payload(photo_data_url=bad))
    except ValueError as exc:
        assert "no es válida" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Una foto falsa no debe guardarse")
