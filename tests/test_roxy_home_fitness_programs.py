"""Fixed source programme contracts, not clinical or training approvals."""
from copy import deepcopy
import hashlib
import json

import pytest

from roxy_os.fitness import programs


def fixture_row(program_id="gentle-strength"):
    """Synthetic text at an allowed identity; never publish these fixtures."""
    expected = programs.SOURCE_PROGRAMS[program_id]
    row = {"id": program_id, "title_en": expected["title_en"],
           "title_es": "Programa de prueba " + program_id,
           "source_url": expected["source_url"], "source_version": expected["source_version"],
           "checked_on": "2026-09-11", "source_html_sha256": "a" * 64,
           "intro_en": ["Synthetic introductory guidance.", "Preserve this second paragraph."],
           "intro_es": ["Introducción sintética.", "Conserva este segundo párrafo."],
           "frequency_en": "Synthetic frequency, not a prescription.",
           "frequency_es": "Frecuencia sintética, no es prescripción.",
           "exercises": [{"id": f"synthetic-{index}", "name_en": f"Test movement {index}",
                          "name_es": f"Movimiento de prueba {index}",
                          "instructions_en": ["Do not remove this warning.", "Synthetic repeated direction.", "Synthetic repeated direction."],
                          "instructions_es": ["No elimines este aviso.", "Indicación sintética repetida.", "Indicación sintética repetida."]}
                         for index in range(expected["exercise_count"])],
           "notes_es": ["Sólo fixture de pruebas."],
           "attribution_en": "Synthetic original attribution.",
           "attribution_es": "Atribución sintética de prueba.",
           "license_url": programs.LICENSE_URL, "terms_url": programs.TERMS_URL}
    bind_original(row)
    return row


def bind_original(row):
    original = {"title_en": row["title_en"], "intro_en": row["intro_en"],
                "frequency_en": row["frequency_en"],
                "exercises": [{key: exercise[key] for key in ("id", "name_en", "instructions_en")}
                              for exercise in row["exercises"]]}
    row["raw_source"] = json.dumps(original, ensure_ascii=False)
    row["source_sha256"] = hashlib.sha256(row["raw_source"].encode()).hexdigest()


@pytest.fixture
def install(tmp_path, monkeypatch):
    path = tmp_path / "source-programs.json"
    monkeypatch.setattr(programs, "CATALOG_PATH", path)

    def write(rows=None, *, data=None, raw=None):
        value = data if data is not None else {"version": 1, "programs": rows if rows is not None else [fixture_row()]}
        path.write_bytes(raw if isinstance(raw, bytes) else (raw if raw is not None else json.dumps(value, ensure_ascii=False)).encode())
        return path
    return write


def assert_educational(payload):
    assert payload["status"] == "education_only"
    assert payload["active_training"] is False
    assert payload["can_activate_plans"] is False
    assert payload["clinical_approval"] is False
    assert payload["can_persist"] is False


def test_all_source_summaries_are_bounded_exact_and_never_activate(install):
    rows = [fixture_row(key) for key in programs.SOURCE_PROGRAMS]
    path = install(rows); before = path.read_bytes()
    result = programs.program_catalog()
    assert result["total"] == len(result["programs"]) == 3
    assert_educational(result)
    assert len(json.dumps(result).encode()) < 16 * 1024
    assert "raw_source" not in json.dumps(result)
    assert "instructions_en" not in json.dumps(result)
    assert [row["exercise_count"] for row in result["programs"]] == [7, 5, 4]
    for summary, original in zip(result["programs"], rows):
        detail = programs.program_detail(summary["id"])
        assert_educational(detail)
        assert all(detail["program"][key] == value for key, value in summary.items())
        assert detail["program"]["exercises"] == original["exercises"]
        assert detail["program"]["duration_seconds"] is None
        assert "raw_source" not in detail["program"]
        assert "images" not in detail["program"]
    assert path.read_bytes() == before


def test_original_warnings_and_repeated_steps_are_not_rewritten_or_deduplicated(install):
    row = fixture_row(); install([row])
    value = programs.program_detail(row["id"])["program"]
    assert value["intro_en"] == row["intro_en"]
    assert value["exercises"][0]["instructions_en"] == row["exercises"][0]["instructions_en"]
    assert value["frequency_en"] == row["frequency_en"]
    assert value["notes_es"] == row["notes_es"]


def test_responses_cannot_mutate_source_or_expose_unknown_metadata(install):
    row = fixture_row(); row["private_unknown_field"] = "must-not-leak"
    row["exercises"][0]["private_unknown_field"] = "must-not-leak"
    install([row])
    value = programs.program_detail(row["id"])
    assert "must-not-leak" not in json.dumps(value)
    value["program"]["exercises"][0]["instructions_es"][0] = "Wrong mutation"
    value["program"]["intro_en"].clear()
    assert programs.program_detail(row["id"])["program"]["exercises"][0]["instructions_es"] == row["exercises"][0]["instructions_es"]


@pytest.mark.parametrize("value", [None, 1, True, {}, [], "", "../x", "gentle-strength/other", "a" * 1000, "wger-91"])
def test_unknown_id_cannot_fetch_or_resolve_another_programme(install, value):
    path = install(); before = path.read_bytes()
    with pytest.raises(programs.ProgramNotFound):
        programs.program_detail(value)
    assert path.read_bytes() == before


def test_known_but_unselected_id_is_not_found(install):
    install()
    with pytest.raises(programs.ProgramNotFound):
        programs.program_detail("gentle-balance")


@pytest.mark.parametrize("field,value", [
    ("id", "other"), ("title_en", "Altered source title"), ("title_es", ""),
    ("source_url", "https://www.nhs.uk.evil.test/live-well/exercise/strength-exercises/"),
    ("source_url", "https://www.nhs.uk/live-well/exercise/strength-exercises/?tracking=1"),
    ("source_version", "2025-01-01"), ("source_sha256", "0" * 64),
    ("source_html_sha256", "wrong"), ("raw_source", "not JSON"),
    ("checked_on", "2023-01-01"), ("checked_on", "2026-02-30"),
    ("intro_en", []), ("intro_es", ["Incomplete"]), ("frequency_en", ""),
    ("frequency_es", True), ("attribution_en", ""), ("attribution_es", ""),
    ("license_url", "http://wrong.test"), ("terms_url", programs.TERMS_URL + "extra"),
    ("notes_es", ["bad\x00text"]), ("notes_es", "not list"),
    ("active_training", True), ("can_activate_plans", "false"), ("clinical_approval", 1),
    ("can_activate_training", True), ("can_persist", True),
    ("duration_seconds", 1800), ("rest_seconds", 60), ("progression", "weekly"),
])
def test_invalid_row_fails_whole_catalogue_without_partial_success(install, field, value):
    valid, broken = fixture_row("gentle-balance"), fixture_row()
    broken[field] = value
    path = install([valid, broken]); before = path.read_bytes()
    with pytest.raises(programs.ProgramCatalogUnavailable, match="fitness_program_catalog_unavailable"):
        programs.program_catalog()
    assert path.read_bytes() == before


@pytest.mark.parametrize("change", [
    lambda r: r["exercises"].pop(),
    lambda r: r["exercises"].append(deepcopy(r["exercises"][0])),
    lambda r: r["exercises"][1].update(id=r["exercises"][0]["id"]),
    lambda r: r["exercises"][0].update(instructions_en=["Different source text"]),
    lambda r: r["exercises"][0].update(instructions_es=["Incomplete translation"]),
    lambda r: r["exercises"][0].update(name_es="<img src=x onerror=alert(1)>"),
    lambda r: r["exercises"][0].update(instructions_es=["x"] * 41),
    lambda r: r["exercises"][0].update(instructions_es=["x" * 6001] * 3),
    lambda r: r["exercises"][0].update(sets=3),
    lambda r: r["exercises"][0].update(reps=10),
    lambda r: r["exercises"][0].update(rest_seconds=60),
    lambda r: r["exercises"][0].update(duration_seconds=30),
    lambda r: r["exercises"][0].update(weight_kg=5),
    lambda r: r["exercises"][0].update(weight_lb=5),
])
def test_incomplete_changed_or_unpublished_structured_doses_rejected(install, change):
    row = fixture_row(); change(row); install([row])
    with pytest.raises(programs.ProgramCatalogUnavailable):
        programs.program_catalog()


@pytest.mark.parametrize("field", ["id", "title_es", "source_url"])
def test_duplicate_selection_rejected(install, field):
    first, second = fixture_row(), fixture_row("gentle-balance")
    second[field] = first[field]
    install([first, second])
    with pytest.raises(programs.ProgramCatalogUnavailable):
        programs.program_catalog()


@pytest.mark.parametrize("data", [None, [], True, {}, {"version": True}, {"version": 2},
    {"version": 1, "programs": []}, {"version": 1, "programs": [fixture_row()] * 4}])
def test_invalid_container_is_unavailable_not_an_empty_guide(install, data):
    install(raw=json.dumps(data))
    with pytest.raises(programs.ProgramCatalogUnavailable):
        programs.program_catalog()


@pytest.mark.parametrize("raw", [b"\xff", b'{"version":1,"version":1}', b'{"version":NaN}',
    b'{"version":1e309}', b"[" * 1500 + b"]" * 1500, b" " * (programs.MAX_BYTES + 1)])
def test_corrupted_recursive_duplicate_or_large_files_fail_closed(install, raw):
    install(raw=raw)
    with pytest.raises(programs.ProgramCatalogUnavailable):
        programs.program_catalog()


def test_missing_or_changed_file_does_not_return_stale_cached_success(install):
    path = install()
    assert programs.program_catalog()["total"] == 1
    path.write_text("broken", encoding="utf-8")
    with pytest.raises(programs.ProgramCatalogUnavailable):
        programs.program_catalog()
    path.unlink()
    with pytest.raises(programs.ProgramCatalogUnavailable):
        programs.program_catalog()
    assert not path.exists()


def test_raw_source_recomputed_hash_still_requires_exact_extracted_instructions(install):
    row = fixture_row()
    original = json.loads(row["raw_source"])
    original["exercises"][0]["instructions_en"][0] = "Changed warning"
    row["raw_source"] = json.dumps(original)
    row["source_sha256"] = hashlib.sha256(row["raw_source"].encode()).hexdigest()
    install([row])
    with pytest.raises(programs.ProgramCatalogUnavailable):
        programs.program_catalog()


def test_real_release_if_present_is_exact_complete_and_read_only():
    if not programs.CATALOG_PATH.exists():
        pytest.skip("Source programme selection not delivered yet; synthetic contracts only")
    before = programs.CATALOG_PATH.read_bytes()
    catalog = programs.program_catalog()
    assert catalog["total"] == 3
    assert_educational(catalog)
    assert sum(row["exercise_count"] for row in catalog["programs"]) == 16
    for row in catalog["programs"]:
        detail = programs.program_detail(row["id"])
        assert_educational(detail)
        assert detail["program"]["source_sha256"] == row["source_sha256"]
        assert len(detail["program"]["exercises"]) == row["exercise_count"]
    assert programs.CATALOG_PATH.read_bytes() == before
