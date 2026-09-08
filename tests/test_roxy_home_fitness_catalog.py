"""Actual fixed catalogue integrity and trust boundaries, without provider calls."""

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from roxy_os.fitness import catalog
from roxy_os.fitness.domain import ExerciseTiming, FitnessInputError, validate_session_duration


@pytest.fixture
def snapshot():
    return json.loads(catalog.CATALOG_PATH.read_text(encoding="utf-8"))


def replace_snapshot(monkeypatch, tmp_path, snapshot):
    target = tmp_path / "catalogue.json"
    target.write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(catalog, "CATALOG_PATH", target)


def test_real_selection_has_individual_rights_provenance_and_honest_coverage():
    response = catalog.fitness_catalog()
    assert response["status"] == catalog.STATUS
    assert response["count"] == 8
    assert sum(e["language"] == "es" for e in response["entries"]) == 7
    assert sum(e["language"] == "en" for e in response["entries"]) == 1
    assert sum(len(e["images"]) for e in response["entries"]) == 16
    for entry in response["entries"]:
        assert not entry["clinical_approval"] and not entry["can_activate_training"]
        assert entry["attribution"]["authors"]
        assert entry["attribution"]["license"] in catalog.LICENSES
        assert sha256("\n\n".join(entry["instructions"]).encode()).hexdigest() == entry["instructions_sha256"]
        for media in entry["images"]:
            assert media["kind"] == "illustration"
            assert media["author"] == "Everkinetic"
            assert media["source_exercise_id"] == entry["source_exercise_id"]
            assert media["license"] == "CC-BY-SA-3.0"
            assert len(media["sha256"]) == 64


def test_fixed_language_and_variant_never_silently_translated_or_filled():
    butterfly = catalog.fitness_catalog_entry("wger-135")
    assert butterfly["name"] == "Butterfly" and butterfly["language"] == "en"
    assert butterfly["source_translation_id"] == 98
    assert butterfly["instructions"][0].startswith("Sit on the butterfly machine")
    assert butterfly["equipment"] == []
    assert butterfly["equipment_metadata_complete"] is False
    assert catalog.fitness_catalog_entry("wger-365")["source_translation_id"] == 4317
    assert catalog.fitness_catalog_entry("wger-366")["source_translation_id"] == 2637
    assert catalog.fitness_catalog_entry("wger-203") is None  # Disc/dumbbell mismatch was excluded.


def test_catalogue_cannot_be_used_as_approved_training_input():
    response = catalog.fitness_catalog()
    trusted = {entry["id"]: entry for entry in response["entries"]}
    with pytest.raises(FitnessInputError):
        validate_session_duration([ExerciseTiming("wger-91", 1, 30, 0)],
                                  trusted_catalog=trusted, available_seconds=60)


@pytest.mark.parametrize("value", [
    "http://wger.de/media/exercise-images/74/Bicep-curls-1.png",
    "https://wger.de.evil.test/media/exercise-images/74/Bicep-curls-1.png",
    "https://user:password@wger.de/media/exercise-images/74/Bicep-curls-1.png",
    "https://wger.de:443/media/exercise-images/74/Bicep-curls-1.png",
    "https://wger.de/media/exercise-images/74/../../secret.png",
    "https://wger.de/media/exercise-images/74/%2e%2e.png",
    "https://wger.de/media/exercise-images/74/x.svg",
    "https://wger.de/media/exercise-images/74/x.png?tracking=member",
    "https://wger.de/media/exercise-images/74/x.png#fragment",
    "\nhttps://wger.de/media/exercise-images/74/x.png",
    "https://wger.de/media/exercise-images/74/x.png\t",
    "javascript:alert(1)", "data:image/png;base64,AAAA", "https://[", None,
])
def test_remote_media_url_boundary(value):
    assert catalog.safe_catalog_image_url(value) is False


@pytest.mark.parametrize("field,value", [
    ("clinical_approval", True), ("can_activate_training", True),
    ("review_status", "approved"), ("source_exercise_id", 92),
    ("source_api_url", "https://evil.test/"), ("source_url", "javascript:alert(1)"),
    ("instructions", ["<img src=x onerror=alert(1)>"]),
    ("instructions", ["Replaced source prose"]), ("name", "Unsafe\x00name"),
    ("language", "fr"), ("checked_on", "2026-99-99"),
])
def test_invalid_fiche_fails_closed(monkeypatch, tmp_path, snapshot, field, value):
    snapshot["entries"][0][field] = value
    replace_snapshot(monkeypatch, tmp_path, snapshot)
    response = catalog.fitness_catalog()
    assert response["status"] == "catalogue_unavailable"
    assert response["entries"] == [] and response["count"] == 0
    assert not response["can_activate_training"]


@pytest.mark.parametrize("resource", ["attribution", "base_attribution", "images"])
@pytest.mark.parametrize("mutation", ["missing_author", "unknown_license", "incorrect_license_id"])
def test_missing_or_unknown_rights_never_go_active(monkeypatch, tmp_path, snapshot, resource, mutation):
    entry = snapshot["entries"][0]
    target = entry[resource][0] if resource == "images" else entry[resource]
    if mutation == "missing_author":
        target["authors" if resource == "attribution" else "author"] = [] if resource == "attribution" else ""
    elif mutation == "unknown_license":
        target["license"] = "all-rights-reserved"
    else:
        target["source_license_id"] = 999
    replace_snapshot(monkeypatch, tmp_path, snapshot)
    assert catalog.fitness_catalog()["entries"] == []


@pytest.mark.parametrize("field,value", [
    ("source_exercise_id", 999), ("url", "https://foreign.test/photo.png"),
    ("kind", "photo"), ("is_ai_generated", True), ("visual_review", "pending"),
    ("source_url", "https://wger.de/api/v2/exerciseimage/999/"), ("sha256", "missing"),
])
def test_visual_association_and_review_are_mandatory(monkeypatch, tmp_path, snapshot, field, value):
    snapshot["entries"][0]["images"][0][field] = value
    replace_snapshot(monkeypatch, tmp_path, snapshot)
    assert catalog.fitness_catalog()["entries"] == []


def test_duplicate_identifiers_and_invalid_catalogue_notice_fail_closed(monkeypatch, tmp_path, snapshot):
    snapshot["entries"].append(deepcopy(snapshot["entries"][0]))
    replace_snapshot(monkeypatch, tmp_path, snapshot)
    assert catalog.fitness_catalog()["count"] == 0
    snapshot["entries"].pop()
    snapshot["data_license_notice"] = "<script>bad()</script>"
    replace_snapshot(monkeypatch, tmp_path, snapshot)
    assert catalog.fitness_catalog()["count"] == 0


def test_provider_extensions_do_not_enter_response(monkeypatch, tmp_path, snapshot):
    entry = snapshot["entries"][0]
    entry["raw_html"] = "<script>bad()</script>"
    entry["active"] = True
    entry["attribution"]["author_url"] = "javascript:alert(1)"
    entry["images"][0]["html"] = "<img onerror=bad()>"
    entry["equipment"][0]["html"] = "<img onerror=bad()>"
    replace_snapshot(monkeypatch, tmp_path, snapshot)
    result = catalog.fitness_catalog()["entries"][0]
    assert "raw_html" not in result and "active" not in result
    assert "author_url" not in result["attribution"]
    assert "html" not in result["images"][0]
    assert "html" not in result["equipment"][0]


def test_original_html_becomes_prose_without_active_markup():
    result = catalog.plain_instruction_paragraphs(
        '<p>Primero <strong>texto original</strong>.</p><script>alert(1)</script>'
        '<p>Segundo &amp; completo.</p><iframe>ignore</iframe><p>Último.</p>')
    assert result == ["Primero texto original.", "Segundo & completo.", "Último."]
    with pytest.raises(catalog.CatalogValidationError):
        catalog.plain_instruction_paragraphs("<p>&lt;script&gt;bad&lt;/script&gt;</p>")


def test_missing_file_and_unknown_id_are_honest(monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, "CATALOG_PATH", tmp_path / "not-present.json")
    assert catalog.fitness_catalog()["status"] == "catalogue_unavailable"
    assert catalog.fitness_catalog_entry("wger-91") is None
    for value in ("../../etc/passwd", "91", "wger-0", 91, None):
        assert catalog.fitness_catalog_entry(value) is None


def test_readers_cannot_mutate_subsequent_catalogue_responses():
    entry = catalog.fitness_catalog_entry("wger-91")
    entry["instructions"][0] = "changed"
    entry["images"][0]["author"] = "changed"
    fresh = catalog.fitness_catalog_entry("wger-91")
    assert fresh["instructions"][0] != "changed"
    assert fresh["images"][0]["author"] == "Everkinetic"
