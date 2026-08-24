import base64
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from roxy_os.home_design import HomeDesignGenerator, HomeDesignStore


PNG = b"\x89PNG\r\n\x1a\n" + b"roxy-home-test"
PHOTO = "data:image/png;base64," + base64.b64encode(PNG).decode("ascii")


def _values(**overrides):
    values = {
        "name": "Nuestra sala",
        "room_type": "living_room",
        "style": "warm_modern",
        "budget": 800,
        "measurements": "12 x 14 pies",
        "keep_items": ["sofá gris"],
        "priorities": ["más luz"],
        "notes": "Tenemos un perro",
        "photo_data_url": PHOTO,
    }
    values.update(overrides)
    return values


def test_design_store_isolates_projects_and_private_images(tmp_path):
    store = HomeDesignStore(tmp_path / "design.json", tmp_path / "images")
    project = store.create("member:robert", "home", _values())

    assert store.projects("member:robert")[0]["id"] == project["id"]
    assert store.projects("member:roxy") == []
    assert Path(project["photo_path"]).read_bytes() == PNG
    assert project["products"][0]["name"].endswith("estilo moderno cálido")
    assert sum(row["budget_target"] for row in project["products"]) == 800


def test_design_generation_uses_responses_api_image_edit_and_never_stores_request(tmp_path):
    store = HomeDesignStore(tmp_path / "design.json", tmp_path / "images")
    project = store.create("member:robert", "home", _values())
    captured = {}

    class Responses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output=[SimpleNamespace(type="image_generation_call", result=base64.b64encode(PNG).decode("ascii"))])

    client = SimpleNamespace(responses=Responses())
    result = HomeDesignGenerator("home-only-key", "gpt-5.6-terra", client=client).generate(project)

    assert base64.b64decode(result) == PNG
    assert captured["model"] == "gpt-5.6-terra"
    assert captured["store"] is False
    assert captured["tools"][0]["type"] == "image_generation"
    content = captured["input"][0]["content"]
    assert any(row["type"] == "input_image" and row["image_url"].startswith("data:image/png;base64,") for row in content)
    assert "sofá gris" in content[0]["text"]
    assert "exact architecture" in content[0]["text"]


def test_design_api_creates_private_project_and_prepares_real_store_searches(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_DESIGN_PATH", str(tmp_path / "design.json"))
    monkeypatch.setenv("ROXY_HOME_DESIGN_IMAGE_DIR", str(tmp_path / "images"))
    monkeypatch.setenv("ROXY_HOME_COMMERCE_PATH", str(tmp_path / "commerce.json"))
    monkeypatch.setenv("ROXY_HOME_AMAZON_ASSOCIATE_TAG", "roxyhome-20")
    monkeypatch.setenv("ROXY_HOME_OPENAI_API_KEY", "")
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    created = client.post("/v1/home-design/robert/projects", headers=headers, json=_values())
    project = created.json()["project"]
    snapshot = client.get("/v1/home-design/robert", headers=headers)
    prepared = client.post(
        f"/v1/home-design/robert/projects/{project['id']}/commerce",
        headers=headers,
        json={"product_ids": [project["products"][0]["id"]], "provider_ids": ["amazon"]},
    )
    blocked_generation = client.post(
        f"/v1/home-design/robert/projects/{project['id']}/proposal", headers=headers, json={}
    )

    assert created.status_code == 201
    assert snapshot.status_code == 200
    assert snapshot.json()["projects"][0]["photo_url"].endswith("/image/original")
    assert prepared.status_code == 201
    assert prepared.json()["preparation"]["source"] == "design"
    assert prepared.json()["preparation"]["items"][0]["category"] == "HOUSEHOLD"
    assert blocked_generation.status_code == 503

