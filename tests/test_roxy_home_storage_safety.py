import errno
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from roxy_os import atomic_json
from roxy_os.home_food import HomeFoodStorageError, HomeFoodStore


@pytest.mark.parametrize("broken", ["", "{", "[]", '{"users": []}'])
def test_corruption_never_becomes_an_empty_household(tmp_path, broken):
    path = tmp_path / "home.json"
    path.write_text(broken)
    store = HomeFoodStore(path)
    with pytest.raises(HomeFoodStorageError):
        store.upsert_pet("robert", name="Luna", species="ferret")
    assert path.read_text() == broken
    assert not store.backup_path.exists()


def test_atomic_failure_after_writing_temporary_file_preserves_original(tmp_path, monkeypatch):
    path = tmp_path / "home.json"
    atomic_json.write_compact_json(path, {"pets": ["Bella", "Luna"]})
    original = path.read_bytes()

    def no_space(*_args):
        raise OSError(errno.ENOSPC, "simulated full disk")

    monkeypatch.setattr(atomic_json.os, "replace", no_space)
    with pytest.raises(OSError):
        atomic_json.write_compact_json(path, {"pets": []})
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


def test_backup_and_partial_edit_keep_identity_photo_and_medical_history(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")
    photo = "data:image/png;base64,cGhvdG8="
    luna = store.upsert_pet("robert", name="Luna", species="ferret", photo_data_url=photo, weight_kg=1.2)
    store.add_pet_medical_record("robert", luna["id"], title="Vacuna", record_type="vaccine")
    before = store.path.read_bytes()
    renamed = store.upsert_pet("robert", pet_id=luna["id"], name="Luna querida", species="ferret")
    assert renamed["id"] == luna["id"]
    assert renamed["photo_data_url"] == photo
    assert renamed["weight_kg"] == 1.2
    assert len(renamed["medical_history"]) == 1
    assert len(HomeFoodStore(store.path).snapshot("robert")["pets"]) == 1
    assert json.loads(store.backup_path.read_text()) == json.loads(before)


def test_missing_live_file_with_backup_does_not_create_empty_household(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")
    store.backup_path.write_text('{"users":{"robert":{"pets":[]}}}')
    with pytest.raises(HomeFoodStorageError):
        store.upsert_pet("robert", name="Luna", species="ferret")
    assert not store.path.exists()


def test_twenty_first_pet_never_evicts_saved_pets(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")
    for index in range(20):
        store.upsert_pet("robert", name=f"Mascota {index}", species="ferret")
    original = store.path.read_bytes()
    with pytest.raises(ValueError, match="No se eliminó"):
        store.upsert_pet("robert", name="Otra mascota", species="dog")
    assert store.path.read_bytes() == original
    assert len(store.snapshot("robert")["pets"]) == 20


def test_concurrent_saves_across_store_instances_keep_every_pet(tmp_path):
    path = tmp_path / "home.json"
    def add(index):
        return HomeFoodStore(path).upsert_pet("robert", name=f"Mascota {index}", species="ferret")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(add, range(12)))
    assert len(HomeFoodStore(path).snapshot("robert")["pets"]) == 12


def test_api_returns_recoverable_storage_error_not_empty_success(tmp_path, monkeypatch):
    from tools import roxy_home_service as service
    path = tmp_path / "home.json"
    path.write_text("{")
    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(path))
    service._RATE_STATE.clear()
    client = TestClient(service.app)
    result = client.get("/v1/home-food/robert", headers={"Authorization": "Bearer home-test-key"})
    assert result.status_code == 503
    assert "No se han reemplazado" in result.json()["detail"]
    assert "pets" not in result.json()
    assert path.read_text() == "{"


def test_api_partial_edit_keeps_fields_and_photo(tmp_path, monkeypatch):
    from tools import roxy_home_service as service
    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "home.json"))
    service._RATE_STATE.clear()
    client = TestClient(service.app)
    headers = {"Authorization": "Bearer home-test-key"}
    url = "/v1/home-food/robert/pets"
    photo = "data:image/png;base64,cGhvdG8="
    first = client.post(url, headers=headers, json={"name": "Luna", "species": "ferret", "photo_data_url": photo, "allergies": ["Pollo"]})
    pet = first.json()["pet"]
    updated = client.post(url, headers=headers, json={"pet_id": pet["id"], "name": "Luna", "species": "ferret", "weight_kg": 1.2})
    assert updated.status_code == 201
    assert updated.json()["pet"]["photo_data_url"] == photo
    assert updated.json()["pet"]["allergies"] == ["Pollo"]
    assert updated.json()["pet"]["id"] == pet["id"]
