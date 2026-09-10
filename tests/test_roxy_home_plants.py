import base64
from datetime import date, timedelta
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient
import pytest

from roxy_os.home_plants import HomePlantIdentifier, HomePlantStore, public_plant


PHOTO_BYTES = b"\xff\xd8\xff" + (b"roxy-home-plant" * 2) + b"\xff\xd9"
PHOTO = "data:image/jpeg;base64," + base64.b64encode(PHOTO_BYTES).decode("ascii")
VIDEO_BYTES = b"\x00\x00\x00\x18ftypmp42" + (b"roxy-home-plant-video" * 2)
VIDEO = "data:video/mp4;base64," + base64.b64encode(VIDEO_BYTES).decode("ascii")


def plant_payload(**overrides):
    value = {
        "display_name": "Albahaca de la cocina",
        "species_key": "basil",
        "room": "Cocina",
        "placement": "indoor",
        "pot_type": "terracotta",
        "growing_medium": "soil",
        "drainage": True,
        "light_exposure": "direct_morning",
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

    updated = store.complete_task("hogar-1", plant["id"], first["id"], "Robert", "Tierra seca; regué y dejé drenar", result="WATERED")

    assert updated["care_tasks"][0]["status"] == "DONE"
    assert updated["care_tasks"][0]["completed_by"] == "Robert"
    assert updated["care_tasks"][0]["result"] == "WATERED"
    next_checks = [row for row in updated["care_tasks"] if row["status"] == "PENDING" and row["action"] == "CHECK_SOIL"]
    assert len(next_checks) == 1
    assert {row["action"] for row in updated["care_tasks"] if row["status"] == "PENDING"} >= {"CHECK_SOIL", "ROTATE", "FERTILIZE"}


def test_plant_snapshot_includes_preventive_health_upcoming_care_and_video_followup(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    plant = store.create("hogar-1", "robert", plant_payload(species_key="monstera"))
    entry = store.add_journal("hogar-1", plant["id"], "robert", "Nueva hoja visible", VIDEO)
    snapshot = store.snapshot("hogar-1", "robert")

    assert {row["action"] for row in snapshot["upcoming_care"]} == {"CHECK_SOIL", "ROTATE", "FERTILIZE"}
    assert snapshot["health_summary"]["total"] == 1
    assert snapshot["environment"]["sensor_status"] == "not_connected"
    assert entry["photo_media_type"] == "video/mp4"
    assert snapshot["plants"][0]["journal"][0]["media_type"] == "video/mp4"
    assert snapshot["plants"][0]["plant_type"] == "Trepadora tropical"
    assert snapshot["plants"][0]["light_exposure"] == "direct_morning"


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
    assert completed.json()["plant"]["care_tasks"][0]["result"] == "CHECKED"
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


def test_plant_concerns_reach_summary_and_edit_preserves_photo_and_history(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    plant = store.create("qa", "qa", plant_payload(species_key="pothos", light_exposure="direct_afternoon", drainage=False))
    store.add_journal("qa", plant["id"], "qa", "Observación de prueba", PHOTO)
    before = store.plant("qa", plant["id"])
    snapshot = store.snapshot("qa", "qa")
    assert snapshot["health_summary"] == {"total": 1, "good": 0, "watch": 1, "needs_identification": 0}
    assert len(snapshot["plants"][0]["condition_concerns"]) == 2
    updated = store.update("qa", plant["id"], {"light_exposure": "bright_indirect", "drainage": True, "room": "Nueva ubicación"})
    assert updated["photo_path"] == before["photo_path"]
    assert updated["journal"] == before["journal"]
    assert updated["care_tasks"] == before["care_tasks"]
    assert updated["id"] == before["id"]
    assert Path(updated["photo_path"]).read_bytes() == PHOTO_BYTES
    after = store.snapshot("qa", "qa")
    assert after["health_summary"] == {"total": 1, "good": 1, "watch": 0, "needs_identification": 0}
    assert after["plants"][0]["condition_concerns"] == []


def test_plant_summary_never_counts_an_unidentified_plant_twice(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    plant = store.create("qa", "qa", plant_payload(species_key="unknown", drainage=False))
    def make_due(value):
        value["households"]["qa"]["plants"][plant["id"]]["care_tasks"][0]["due_date"] = (date.today() - timedelta(days=1)).isoformat()
    store._locked(make_due)
    snapshot = store.snapshot("qa", "qa")
    assert snapshot["due_today"]
    assert snapshot["health_summary"] == {"total": 1, "good": 0, "watch": 0, "needs_identification": 1}


def test_plant_completion_is_idempotent_and_never_guesses_watering(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    plant = store.create("qa", "qa", plant_payload())
    task = plant["care_tasks"][0]
    completed = store.complete_task("qa", plant["id"], task["id"], "qa", "No regué; tierra húmeda")
    assert completed["care_tasks"][0]["result"] == "CHECKED"
    repeated = store.complete_task("qa", plant["id"], task["id"], "qa", "Segundo clic", result="WATERED")
    assert repeated == completed
    assert len([row for row in repeated["care_tasks"] if row["action"] == "CHECK_SOIL" and row["status"] == "PENDING"]) == 1


@pytest.mark.parametrize("drainage", [None, False, True])
def test_soil_drainage_unknown_is_not_an_observed_problem(tmp_path, drainage):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    store.create("qa", "qa", plant_payload(drainage=drainage))
    snapshot = store.snapshot("qa", "qa")
    plant = snapshot["plants"][0]

    assert plant["drainage"] is drainage
    assert bool(plant["condition_concerns"]) is (drainage is False)
    assert bool(plant["setup_questions"]) is (drainage is None)
    assert snapshot["health_summary"]["watch"] == int(drainage is False)


def test_plant_omitted_drainage_stays_unknown_and_can_be_cleared(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    payload = plant_payload()
    payload.pop("drainage")
    created = store.create("qa", "qa", payload)
    assert created["drainage"] is None
    store.update("qa", created["id"], {"drainage": True})
    cleared = store.update("qa", created["id"], {"drainage": None, "room": None})
    assert cleared["drainage"] is None
    assert cleared["room"] == created["room"]
    assert cleared["care_tasks"] == created["care_tasks"]
    assert cleared["photo_path"] == created["photo_path"]


def test_legacy_glass_pot_does_not_identify_medium_or_diagnose_drainage(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    created = store.create("qa", "qa", plant_payload(species_key="pothos", pot_type="glass", drainage=False))
    def legacy_record(value):
        value["households"]["qa"]["plants"][created["id"]].pop("growing_medium")
    store._locked(legacy_record)
    before = store.path.read_bytes()
    plant = store.snapshot("qa", "qa")["plants"][0]

    assert plant["growing_medium"] == "unknown"
    assert plant["drainage"] is False  # Original fact is preserved, without guessing a medium.
    assert plant["condition_concerns"] == []
    assert plant["setup_questions"]
    assert plant["product_queries"] == []
    assert "confirma" in plant["soil_rule"].lower()
    assert plant["care_tasks"][0]["title"] == "Confirmar si está en tierra o en agua"
    assert store.path.read_bytes() == before


def test_water_pothos_guidance_does_not_use_soil_watering_or_products(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    created = store.create("qa", "qa", plant_payload(species_key="pothos", growing_medium="water", pot_type="glass", drainage=False))
    plant = public_plant(created, "qa")

    assert plant["condition_concerns"] == []
    assert plant["product_queries"] == []
    assert "turbia" in plant["soil_rule"]
    assert "5 cm" not in plant["soil_rule"]
    assert "esqueje" in plant["fertilizer"]
    assert plant["care_tasks"][0]["title"] == "Revisar agua, raíces y hojas"
    assert any("2025-02-21" in source["url"] for source in plant["sources"])
    assert "5 cm" in created["soil_rule"]  # Keep the soil profile for a later confirmed move.


@pytest.mark.parametrize("species_key,identification", [("aloe", None), ("unknown", {"species_key": "pothos", "status": "PROPOSED"})])
def test_water_profile_does_not_claim_pothos_guide_for_other_or_unconfirmed_species(tmp_path, species_key, identification):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    created = store.create("qa", "qa", plant_payload(species_key=species_key, growing_medium="water"), identification)
    plant = public_plant(created, "qa")
    assert "Confirma una guía" in plant["soil_rule"]
    assert "Pothos" not in plant["soil_rule"]
    assert plant["product_queries"] == []


def test_changing_medium_adapts_pending_care_and_preserves_history_links_and_photo(tmp_path):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    created = store.create("qa", "qa", plant_payload(species_key="pothos"))
    completed = store.complete_task("qa", created["id"], created["care_tasks"][0]["id"], "qa", "Tierra húmeda; no regué")
    next_check = next(task for task in completed["care_tasks"] if task["action"] == "CHECK_SOIL" and task["status"] == "PENDING")
    store.link_task_calendar("qa", created["id"], next_check["id"], "existing-event")
    before = store.plant("qa", created["id"])

    water = store.update("qa", created["id"], {"growing_medium": "water", "drainage": None})
    assert water["care_tasks"][0] == before["care_tasks"][0]
    assert water["photo_path"] == before["photo_path"]
    for original, updated in zip(before["care_tasks"], water["care_tasks"]):
        assert {key: value for key, value in original.items() if key != "title"} == {key: value for key, value in updated.items() if key != "title"}
    assert public_plant(water, "qa")["product_queries"] == []

    soil = store.update("qa", created["id"], {"growing_medium": "soil", "drainage": True})
    assert soil["care_tasks"] == before["care_tasks"]
    assert public_plant(soil, "qa")["soil_rule"] == created["soil_rule"]


def test_plant_api_persists_medium_and_distinguishes_omitted_from_cleared_drainage(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "plants-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_PLANTS_PATH", str(tmp_path / "plants.json"))
    monkeypatch.setenv("ROXY_HOME_PLANTS_IMAGE_DIR", str(tmp_path / "images"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    headers = {"Authorization": "Bearer plants-test-key"}
    payload = plant_payload(species_key="pothos", growing_medium="water")
    payload.pop("drainage")
    response = client.post("/v1/home-plants/robert", headers=headers, json=payload)
    assert response.status_code == 201
    plant = response.json()["plant"]
    assert plant["growing_medium"] == "water"
    assert plant["drainage"] is None
    url = f"/v1/home-plants/robert/{plant['id']}"
    response = client.patch(url, headers=headers, json={"growing_medium": "soil", "drainage": False})
    assert response.status_code == 200
    assert response.json()["plant"]["condition_concerns"]
    response = client.patch(url, headers=headers, json={"room": "Salón"})
    assert response.json()["plant"]["drainage"] is False
    response = client.patch(url, headers=headers, json={"drainage": None})
    assert response.status_code == 200
    updated = response.json()["plant"]
    assert updated["drainage"] is None
    assert updated["room"] == "Salón"
    assert updated["growing_medium"] == "soil"
    assert updated["condition_concerns"] == []
    assert updated["setup_questions"]
    assert updated["photo_url"] == plant["photo_url"]
    assert client.patch(url, headers=headers, json={"growing_medium": "guessed-from-photo"}).status_code == 422


def test_plant_water_reminder_uses_same_care_text_as_public_plant(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "plants-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_PLANTS_PATH", str(tmp_path / "plants.json"))
    monkeypatch.setenv("ROXY_HOME_PLANTS_IMAGE_DIR", str(tmp_path / "images"))
    monkeypatch.setenv("ROXY_HOME_CALENDAR_PATH", str(tmp_path / "calendar.json"))
    monkeypatch.setattr(roxy_home_service, "_sync_calendar_event", lambda *_: {"synced": False})
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    headers = {"Authorization": "Bearer plants-test-key"}
    response = client.post("/v1/home-plants/robert", headers=headers, json=plant_payload(species_key="pothos", growing_medium="water"))
    assert response.status_code == 201
    plant = response.json()["plant"]
    task = plant["care_tasks"][0]
    response = client.post(f"/v1/home-plants/robert/{plant['id']}/reminders", headers=headers, json={"task_id": task["id"]})
    assert response.status_code == 201
    event = response.json()["event"]
    assert "Revisar agua, raíces y hojas" in event["title"]
    assert plant["soil_rule"] in event["notes"]
    assert "5 cm" not in event["notes"]
    refreshed = client.get("/v1/home-plants/robert", headers=headers).json()["plants"][0]
    assert refreshed["care_tasks"][0]["calendar_event_id"] == event["id"]


def test_plant_weather_does_not_turn_missing_temperature_into_freezing_advice():
    script = (Path(__file__).resolve().parents[1] / "assets/roxy_list.js").read_text()
    function = script.split("  function plantWeatherContext(){", 1)[1].split("\n", 1)[0]
    atmosphere = script[script.index("  function familyWeatherMode()"):script.index("  let familyWeatherRefreshTimer=")]
    harness = """const assert=require('node:assert/strict');let homeWeather;
""" + atmosphere + "function plantWeatherContext(){" + function + """
for(const data of [{}, {status:'ERROR',current:{temperature:40,code:61}}, {status:'READY',current:{temperature:null,code:null}}]){
  homeWeather=data;const r=plantWeatherContext();assert.equal(Boolean(r.ready),false);assert.equal(Boolean(r.cold),false);assert.equal(Boolean(r.rain),false);
}
homeWeather={status:'READY',updated_at:new Date().toISOString(),current:{temperature:90,code:61,valid_at:new Date().toISOString()}};
assert.equal(plantWeatherContext().hot,true);assert.equal(plantWeatherContext().rain,true);
homeWeather.current.valid_at='2020-01-01T00:00:00Z';
assert.equal(plantWeatherContext().ready,false,'stale weather must not change garden guidance');
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "makeButton('Editar condiciones'" in script
    assert "$('plantPhoto').required=!plant" in script
    assert "piezas preparadas" not in script
