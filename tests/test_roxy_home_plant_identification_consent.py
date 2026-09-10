"""The guided photo upload cannot silently invoke a visual AI provider."""
import base64
from pathlib import Path

from fastapi.testclient import TestClient
import pytest


PHOTO_BYTES = b"\xff\xd8\xffsynthetic-upload-for-consent-check\xff\xd9"
PHOTO = "data:image/jpeg;base64," + base64.b64encode(PHOTO_BYTES).decode("ascii")


@pytest.fixture
def api(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-garden-consent-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "garden-qa")
    monkeypatch.setenv("ROXY_HOME_PLANTS_PATH", str(tmp_path / "plants.json"))
    monkeypatch.setenv("ROXY_HOME_PLANTS_IMAGE_DIR", str(tmp_path / "images"))
    roxy_home_service._RATE_STATE.clear()
    calls = {"factory": 0, "photos": []}

    class SyntheticIdentifier:
        configured = True

        @classmethod
        def from_env(cls):
            calls["factory"] += 1
            return cls()

        def identify(self, photo):
            calls["photos"].append(photo)
            return {"status": "PROPOSED", "species_key": "pothos", "confidence": 0.8, "alternatives": [], "warning": "Propuesta sintética: requiere confirmación."}

    monkeypatch.setattr(roxy_home_service, "HomePlantIdentifier", SyntheticIdentifier)
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    headers = {"Authorization": "Bearer synthetic-garden-consent-key"}
    return client, headers, calls, roxy_home_service


def test_guided_unknown_plant_skips_identifier_entirely_and_preserves_exact_upload(api):
    client, headers, calls, service = api
    response = client.post("/v1/home-plants/garden-qa", headers=headers, json={
        "species_key": "unknown", "display_name": "Mango según el apodo", "photo_data_url": PHOTO,
        "identify_photo": False, "growing_medium": "unknown",
    })
    assert response.status_code == 201, response.text
    data = response.json()
    assert calls == {"factory": 0, "photos": []}
    assert data["identification"] is None
    assert data["plant"]["species_key"] == "unknown"
    assert data["plant"]["identification"]["status"] == "NEEDS_CONFIRMATION"
    assert data["plant"]["display_name"] == "Mango según el apodo"
    stored = service._plant_store().plant("garden-qa", data["plant"]["id"])
    assert Path(stored["photo_path"]).read_bytes() == PHOTO_BYTES
    assert "identify_photo" not in stored
    image = client.get(data["plant"]["photo_url"], headers=headers)
    assert image.status_code == 200 and image.content == PHOTO_BYTES
    assert calls == {"factory": 0, "photos": []}, "Reading the uploaded photo must not send it to an identifier either"


@pytest.mark.parametrize("flag", ["omitted", True])
def test_legacy_or_explicit_opt_in_retains_proposal_route_but_does_not_confirm_it(api, flag):
    client, headers, calls, _service = api
    payload = {"species_key": "unknown", "photo_data_url": PHOTO}
    if flag != "omitted":
        payload["identify_photo"] = flag
    response = client.post("/v1/home-plants/garden-qa", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    assert calls == {"factory": 1, "photos": [PHOTO]}
    plant = response.json()["plant"]
    assert plant["species_key"] == "pothos"
    assert plant["identification"]["status"] == "PROPOSED"
    image = client.get(plant["photo_url"], headers=headers)
    assert image.status_code == 200 and image.content == PHOTO_BYTES


@pytest.mark.parametrize("flag", [False, True])
def test_manually_confirmed_species_never_needs_ai_for_photo_storage(api, flag):
    client, headers, calls, _service = api
    response = client.post("/v1/home-plants/garden-qa", headers=headers, json={"species_key": "mango", "photo_data_url": PHOTO, "identify_photo": flag})
    assert response.status_code == 201, response.text
    plant = response.json()["plant"]
    assert plant["species_key"] == "mango"
    assert plant["identification"]["status"] == "CONFIRMED"
    assert calls == {"factory": 0, "photos": []}
