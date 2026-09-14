"""Discovery must expose real sources without inventing eligibility or media rights."""
from copy import deepcopy
import json

import pytest

from roxy_os.fitness import classes
from roxy_os.fitness.catalog import fitness_catalog
from roxy_os.fitness.programs import program_catalog
from tools import roxy_home_service as service
from test_roxy_home_fitness_api import api, private_cache


def test_directory_distinguishes_full_classes_and_bodyweight_demonstrations():
    result = classes.class_catalog()
    assert result["count"] == 18
    assert result["class_count"] == 15
    assert result["technique_count"] == 3
    by_id = {row["id"]: row for row in result["classes"]}
    assert by_id["nhs-yoga-vinyasa"]["duration_minutes"] == 50
    assert by_id["nhs-pilates-chair"]["duration_minutes"] == 30
    assert "aproximada" in by_id["nhs-pilates-chair"]["duration_note_es"]
    assert "sentados" in " ".join(by_id["nhs-pilates-chair"]["source_notes_es"])
    for identifier in ("mayo-squat", "mayo-modified-pushup", "mayo-step-up"):
        assert by_id[identifier]["modality"] == "calisthenics"
        assert by_id[identifier]["format"] == "technique"
        assert by_id[identifier]["duration_minutes"] is None
    assert fitness_catalog()["count"] == 25
    assert sum(row["exercise_count"] for row in program_catalog()["programs"]) == 16


def test_missing_or_conflicting_metadata_is_not_assumed_beginner_or_no_equipment():
    by_id = {row["id"]: row for row in classes.class_catalog()["classes"]}
    assert by_id["nhs-warm-up"]["duration_minutes"] is None
    assert "5 minutos" in by_id["nhs-warm-up"]["duration_note_es"]
    assert "10" in by_id["nhs-warm-up"]["duration_note_es"]
    assert by_id["nhs-pilates-pyjama"]["level"] == "basic_experience"
    assert by_id["nhs-strength-abs"]["level"] == "basic_fitness"
    assert by_id["nhs-yoga-vinyasa"]["level"] is None
    assert by_id["mayo-squat"]["equipment"] == []
    assert by_id["mayo-squat"]["equipment_complete"] is False
    assert all(row["equipment_complete"] is False for row in by_id.values())


def test_directory_grants_no_media_reuse_or_personal_training_capability():
    result = classes.class_catalog()
    assert result["clinical_approval"] is False
    assert result["can_activate_plans"] is False
    assert "en inglés" in result["media_notice_es"]
    for row in result["classes"]:
        assert row["embed_url"] is None
        assert row["media_mode"] == "external_link"
        assert row["language"] == "en"
        assert row["can_activate_plans"] is row["clinical_approval"] is False
        assert "weight_kg" not in row and "age_min" not in row and "calories" not in row
        assert row["source_url"] == classes.SOURCE_URLS[row["id"]]


@pytest.mark.parametrize("change", [
    {"source_url": "https://www.nhs.uk.evil.invalid/video"},
    {"source_url": "javascript:alert(1)"},
    {"embed_url": "https://www.youtube.com/embed/unlicensed"},
    {"clinical_approval": True},
    {"can_activate_plans": True},
    {"duration_minutes": 3},
    {"equipment_complete": True},
    {"level": "beginner"},
    {"unexpected_html": "<script>alert(1)</script>"},
])
def test_edited_source_facts_fail_closed(tmp_path, monkeypatch, change):
    data = json.loads(classes.CATALOG_PATH.read_text())
    data["classes"][0].update(change)
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(classes, "CATALOG_PATH", path)
    with pytest.raises(classes.ClassCatalogUnavailable):
        classes.class_catalog()


@pytest.mark.parametrize("contents", [b"{", b"null", b"{\"version\":1,\"version\":1}", b"{\"a\":NaN}", b"x" * (classes.MAX_BYTES + 1)])
def test_invalid_or_oversized_catalogue_never_returns_empty_success(tmp_path, monkeypatch, contents):
    path = tmp_path / "bad.json"
    path.write_bytes(contents)
    monkeypatch.setattr(classes, "CATALOG_PATH", path)
    with pytest.raises(classes.ClassCatalogUnavailable):
        classes.class_catalog()


def test_formatting_does_not_change_source_facts_and_results_are_detached(tmp_path, monkeypatch):
    data = json.loads(classes.CATALOG_PATH.read_text())
    path = tmp_path / "formatted.json"
    path.write_text(json.dumps(data, sort_keys=True, ensure_ascii=True))
    monkeypatch.setattr(classes, "CATALOG_PATH", path)
    first = classes.class_catalog()
    first["classes"][0]["equipment"].clear()
    first["classes"][0]["title_es"] = "edited by caller"
    second = classes.class_catalog()
    assert second["classes"][0] == data["classes"][0]


@pytest.mark.parametrize("mode", ["member", "legacy", "bearer"])
def test_discovery_endpoint_uses_existing_auth_without_personal_storage(api, monkeypatch, mode):
    api.identity = service.AuthContext(mode, "shared-household", "member-a" if mode == "member" else None)
    from roxy_os.fitness import router
    monkeypatch.setattr(router, "repository", lambda: pytest.fail("Discovery accessed private storage"))
    response = api.client.get("/api/fitness/v1/classes")
    assert response.status_code == 200
    assert response.json()["count"] == 18
    private_cache(response)
    assert api.db.calls == []


def test_unauthenticated_discovery_is_not_cached(api, monkeypatch):
    monkeypatch.delitem(service.app.dependency_overrides, service._authenticate)
    response = api.client.get("/api/fitness/v1/classes")
    assert response.status_code == 401
    private_cache(response)
    assert api.db.calls == []


def test_source_failure_is_explicit_and_preserves_other_catalogues(api, monkeypatch, tmp_path):
    monkeypatch.setattr(classes, "CATALOG_PATH", tmp_path / "missing.json")
    response = api.client.get("/api/fitness/v1/classes")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "class_catalog_unavailable"
    private_cache(response)
    assert api.client.get("/api/fitness/v1/exercises").json()["count"] == 25
    assert api.client.get("/api/fitness/v1/programs").json()["total"] == 3
    assert api.db.calls == []
