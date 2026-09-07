import base64
from datetime import date, timedelta
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from roxy_os.home_plants import HomePlantIdentifier, HomePlantStore


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


def test_plant_weather_does_not_turn_missing_temperature_into_freezing_advice():
    script = (Path(__file__).resolve().parents[1] / "assets/roxy_list.js").read_text()
    function = script.split("  function plantWeatherContext(){", 1)[1].split("\n", 1)[0]
    harness = """const assert=require('node:assert/strict');let homeWeather;
""" + "function plantWeatherContext(){" + function + """
for(const data of [{}, {status:'ERROR',current:{temperature:40,code:61}}, {status:'READY',current:{temperature:null,code:null}}]){
  homeWeather=data;const r=plantWeatherContext();assert.equal(Boolean(r.ready),false);assert.equal(Boolean(r.cold),false);assert.equal(Boolean(r.rain),false);
}
homeWeather={status:'READY',current:{temperature:90,code:61}};
assert.equal(plantWeatherContext().hot,true);assert.equal(plantWeatherContext().rain,true);
"""
    result = subprocess.run(["node", "-e", harness], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "makeButton('Editar condiciones'" in script
    assert "$('plantPhoto').required=!plant" in script
    assert "piezas preparadas" not in script
