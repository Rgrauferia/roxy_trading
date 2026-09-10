import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ROXY_HOME_API_KEY", "storage-qa-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "storageqa")
    for kind in ("PLANTS", "DESIGN"):
        monkeypatch.setenv(f"ROXY_HOME_{kind}_PATH", str(tmp_path / f"{kind.lower()}.json"))
        monkeypatch.setenv(f"ROXY_HOME_{kind}_IMAGE_DIR", str(tmp_path / f"{kind.lower()}-images"))
    from tools import roxy_home_service as service
    service._RATE_STATE.clear()
    monkeypatch.setattr(service, "public_pinterest_design_trends", lambda: {"status": "not_connected"})
    return TestClient(service.app, base_url="https://roxy.test", headers={"Authorization": "Bearer storage-qa-key"})


@pytest.mark.parametrize("kind", ["plants", "design"])
def test_legacy_client_cannot_overwrite_its_cache_with_missing_storage(client, kind):
    response = client.get(f"/v1/home-{kind}/storageqa")
    assert response.status_code == 503
    assert "Conserva la copia" in response.json()["detail"]
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("kind,field", [("plants", "plants"), ("design", "projects")])
def test_new_client_can_initialize_an_empty_collection_after_preserving_its_copy(client, kind, field):
    response = client.get(f"/v1/home-{kind}/storageqa", headers={"X-Roxy-Snapshot-Version": "2"})
    assert response.status_code == 200
    assert response.json()["storage_status"] == "NEW"
    assert response.json()[field] == []


@pytest.mark.parametrize("kind", ["plants", "design"])
def test_corruption_returns_503_for_every_client_without_replacing_file(client, kind, tmp_path):
    path = tmp_path / f"{kind}.json"
    path.write_text('{"broken":', encoding="utf-8")
    for headers in ({}, {"X-Roxy-Snapshot-Version": "2"}):
        response = client.get(f"/v1/home-{kind}/storageqa", headers=headers)
        assert response.status_code == 503
        assert response.json()["code"] == "HOME_STORAGE_UNAVAILABLE"
        assert str(tmp_path) not in response.text
    assert path.read_text() == '{"broken":'


@pytest.mark.parametrize("kind", ["plants", "design"])
def test_snapshot_protocol_does_not_bypass_authorization(client, kind):
    response = client.get(f"/v1/home-{kind}/other-home", headers={"X-Roxy-Snapshot-Version": "2"})
    assert response.status_code == 403


@pytest.mark.parametrize("kind,raw", [
    ("plants", '{"schema_version":1,"households":{"other-home":{"plants":{}}}}'),
    ("design", '{"schema_version":1,"projects":{"member:other-person":{}}}'),
])
def test_legacy_empty_protection_survives_initialization_by_another_household(client, kind, raw, tmp_path):
    (tmp_path / f"{kind}.json").write_text(raw)
    assert client.get(f"/v1/home-{kind}/storageqa").status_code == 503
    current = client.get(f"/v1/home-{kind}/storageqa", headers={"X-Roxy-Snapshot-Version": "2"})
    assert current.status_code == 200
    assert current.json()["storage_status"] == "READY"
