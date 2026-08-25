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
    assert [row["id"] for row in project["budget_tiers"]] == ["economy", "balanced", "complete"]
    assert [row["budget"] for row in project["budget_tiers"]] == [520, 800, 1080]
    assert [row["priority"] for row in project["products"]] == ["essential", "essential", "optional", "optional"]
    assert project["analysis_status"] == "READY_LOCAL"


def test_design_store_changes_budget_tier_and_remembers_conversational_revisions(tmp_path):
    store = HomeDesignStore(tmp_path / "design.json", tmp_path / "images")
    project = store.create("member:robert", "home", _values())

    economy = store.select_tier("member:robert", project["id"], "economy")
    revised = store.request_revision(
        "member:robert", project["id"], "Conserva el sofá y usa paredes beige", "economy"
    )
    analyzed = store.save_analysis("member:robert", project["id"], {
        "summary": "La distribución funciona, pero puede ganar luz.",
        "strengths": ["Buena circulación"],
        "opportunities": ["Añadir luz de pie"],
        "questions": ["¿Cuánto mide la pared?"],
    })

    assert economy["selected_tier"] == "economy"
    assert sum(row["budget_target"] for row in economy["products"]) == 520
    assert revised["revision_notes"][-1]["instruction"] == "Conserva el sofá y usa paredes beige"
    assert analyzed["analysis_status"] == "READY_AI"
    assert analyzed["analysis"]["questions"] == ["¿Cuánto mide la pared?"]


def test_design_analysis_reclassifies_room_and_turns_specific_furniture_advice_into_products(tmp_path):
    store = HomeDesignStore(tmp_path / "design.json", tmp_path / "images")
    project = store.create("member:robert", "home", _values(name="Cuarto", room_type="living_room"))

    analyzed = store.save_analysis("member:robert", project["id"], {
        "summary": "La foto muestra un dormitorio.",
        "strengths": ["Buena luz"],
        "opportunities": ["Mejorar almacenamiento"],
        "questions": [],
        "detected_room_type": "bedroom",
        "detected_room_confidence": 0.96,
        "furniture_recommendations": [
            {"name": "cama plataforma de roble", "role": "descanso", "placement": "pared principal", "style_details": "roble claro y líneas bajas", "priority": "essential"},
            {"name": "mesita de noche flotante", "role": "apoyo", "placement": "junto a la cama", "style_details": "madera clara", "priority": "optional"},
        ],
    })

    assert analyzed["room_type"] == "bedroom"
    assert analyzed["room_label"] == "dormitorio"
    assert analyzed["products"][0]["name"].startswith("cama plataforma de roble")
    assert analyzed["analysis"]["furniture_recommendations"][1]["placement"] == "junto a la cama"


def test_design_store_keeps_physical_constraints_separate_and_requires_complete_measurements(tmp_path):
    from roxy_os.home_design import public_project

    store = HomeDesignStore(tmp_path / "design.json", tmp_path / "images")
    project = store.create("member:robert", "home", _values())
    incomplete = store.update_fit_constraints("member:robert", project["id"], {"wall_width": 120, "passage_width": 0, "max_depth": 24})
    complete = store.update_fit_constraints("member:robert", project["id"], {"wall_width": 120, "passage_width": 36, "max_depth": 24})

    assert public_project(incomplete, "robert")["fit_assessment"]["status"] == "NEEDS_MEASUREMENTS"
    assert public_project(complete, "robert")["fit_assessment"]["status"] == "READY_TO_COMPARE"
    assert complete["fit_constraints"]["passage_width"] == 36


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
    assert "transformation unmistakable" in content[0]["text"]
    assert "Preserve only these movable items" in content[0]["text"]
    assert "Physical limits in inches" in content[0]["text"]


def test_design_visual_analysis_uses_private_photo_and_structured_responses_output(tmp_path):
    store = HomeDesignStore(tmp_path / "design.json", tmp_path / "images")
    project = store.create("member:robert", "home", _values())
    captured = {}

    class Responses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_text='{"summary":"Buena base","strengths":["Luz natural"],"opportunities":["Ordenar cables"],"questions":["¿Cuánto mide la pared?"]}')

    result = HomeDesignGenerator("home-only-key", "gpt-5.6-terra", client=SimpleNamespace(responses=Responses())).analyze(project)

    assert result["summary"] == "Buena base"
    assert captured["store"] is False
    assert captured["text"]["format"]["type"] == "json_schema"
    assert captured["input"][0]["content"][1]["image_url"].startswith("data:image/png;base64,")
    assert "furniture_recommendations" in captured["text"]["format"]["schema"]["required"]


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
    assert prepared.json()["preparation"]["source_title"] == "Opción Equilibrada para Nuestra sala"
    assert prepared.json()["preparation"]["items"][0]["budget_target"] == 304
    assert "precio real" in prepared.json()["preparation"]["items"][0]["reason"]
    assert {"ikea", "wayfair", "west_elm", "article"}.issubset({row["id"] for row in prepared.json()["providers"]})
    assert blocked_generation.status_code == 503


def test_design_api_analyzes_revises_and_generates_only_the_selected_budget_option(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_DESIGN_PATH", str(tmp_path / "design.json"))
    monkeypatch.setenv("ROXY_HOME_DESIGN_IMAGE_DIR", str(tmp_path / "images"))
    roxy_home_service._RATE_STATE.clear()

    class Generator:
        configured = True

        def analyze(self, _project):
            return {"summary": "Buena base", "strengths": ["Luz natural"], "opportunities": ["Más orden"], "questions": []}

        def generate(self, project):
            assert project["selected_tier"] in {"economy", "complete"}
            return base64.b64encode(PNG).decode("ascii")

    monkeypatch.setattr(roxy_home_service.HomeDesignGenerator, "from_env", staticmethod(lambda: Generator()))
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}
    project = client.post("/v1/home-design/robert/projects", headers=headers, json=_values()).json()["project"]

    measured = client.put(
        f"/v1/home-design/robert/projects/{project['id']}/measurements",
        headers=headers,
        json={"wall_width": 120, "passage_width": 36, "max_depth": 24},
    )
    analyzed = client.post(f"/v1/home-design/robert/projects/{project['id']}/analysis", headers=headers, json={})
    generated = client.post(f"/v1/home-design/robert/projects/{project['id']}/proposal", headers=headers, json={"tier": "economy"})
    revised = client.post(
        f"/v1/home-design/robert/projects/{project['id']}/revision",
        headers=headers,
        json={"tier": "complete", "instruction": "Conserva el sofá y usa tonos beige"},
    )
    snapshot = client.get("/v1/home-design/robert", headers=headers).json()["projects"][0]

    assert measured.status_code == 200
    assert measured.json()["project"]["fit_assessment"]["status"] == "READY_TO_COMPARE"
    assert analyzed.status_code == 200
    assert analyzed.json()["project"]["analysis_status"] == "READY_AI"
    assert generated.status_code == 202
    assert revised.status_code == 202
    assert snapshot["selected_tier"] == "complete"
    assert snapshot["proposal_tier"] == "complete"
    assert snapshot["revision_notes"][-1]["instruction"] == "Conserva el sofá y usa tonos beige"
