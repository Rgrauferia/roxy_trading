"""Editorial source contracts protect exact variants, doses and planning assumptions."""
from copy import deepcopy
import json
import math

import pytest

from roxy_os.fitness import training_content as content


def exercise(program_id, exercise_id):
    return next(e for e in content.training_detail(program_id)["exercises"] if e["id"] == exercise_id)


def test_catalog_has_six_real_readable_sessions_separate_from_clinical_training():
    catalog = content.training_catalog()
    assert catalog["total"] == 6
    assert len(catalog["content_digest"]) == 64
    assert {p["modality"] for p in catalog["programs"]} == {"strength", "mobility", "yoga", "core"}
    assert sum(p["exercise_count"] for p in catalog["programs"]) == 28
    assert catalog["clinical_approval"] is False
    for row in catalog["programs"]:
        assert "exercises" not in row
        detail = content.training_detail(row["id"])
        assert detail["content_version"] == catalog["content_version"]
        assert detail["content_digest"] == catalog["content_digest"]
        assert detail["clinical_approval"] is False
        assert detail["prescribed_load"] is None
        assert detail["auto_progression"] is False
        assert detail["weight_based_selection"] is False
        assert detail["technical_demonstration"] is False
        assert detail["exercises"][0]["phase"] == "warmup"
        assert detail["exercises"][-1]["phase"] == "cooldown"
        assert all(len(e["instructions"]) >= 3 for e in detail["exercises"])
        assert all(e["source_links"] for e in detail["exercises"])
    assert "calories" not in json.dumps(catalog)


def test_each_physical_transition_and_item_is_in_the_required_contract():
    catalog = content.training_catalog()
    for row in catalog["programs"]:
        detail = content.training_detail(row["id"])
        required = detail["requirements"]
        assert required["equipment_complete"] is True
        assert set(required["equipment"]) <= catalog["equipment_labels"].keys()
        assert set(required["capabilities"]) <= catalog["capability_labels"].keys()
        for move in detail["exercises"]:
            assert set(move["equipment"]) <= set(required["equipment"])
            assert set(move["capabilities"]) <= set(required["capabilities"])
    assert set(content.training_detail("home-bodyweight-foundations")["requirements"]["equipment"]) == {"chair", "wall", "bodyweight"}
    assert "bench" not in content.training_detail("home-dumbbell-foundations")["requirements"]["equipment"]
    assert {"bench", "dumbbells"} <= set(content.training_detail("gym-dumbbell-foundations")["requirements"]["equipment"])
    assert "bench_transfer" in content.training_detail("gym-dumbbell-foundations")["requirements"]["capabilities"]
    assert {"standing", "floor_transfer", "kneeling"} <= set(content.training_detail("core-foundations")["requirements"]["capabilities"])
    assert "floor_transfer" not in content.training_detail("yoga-gentle-start")["requirements"]["capabilities"]


def test_bodyweight_doses_keep_real_wall_series_and_unilateral_holds():
    wall = exercise("home-bodyweight-foundations", "wall-pushup")
    assert (wall["dose"]["sets"], wall["dose"]["reps_min"], wall["dose"]["reps_max"]) == (3, 5, 10)
    assert wall["dose"]["basis"] == "source"
    extension = exercise("home-bodyweight-foundations", "chair-hip-extension")
    assert extension["dose"]["per_side"] is True
    assert extension["dose"]["hold_seconds"] == 5
    assert "máximo" in extension["dose"]["note"]
    assert wall["load_recordable"] is False


def test_dumbbell_variants_do_not_silently_change_between_home_and_gym():
    home = exercise("home-dumbbell-foundations", "dumbbell-bent-row")
    gym = exercise("gym-dumbbell-foundations", "dumbbell-bent-row")
    assert home["instructions"] == gym["instructions"]
    assert home["dose"]["per_side"] is gym["dose"]["per_side"] is True
    assert (home["dose"]["sets"], home["dose"]["reps_min"], home["dose"]["reps_max"]) == (1, 12, 15)
    assert (gym["dose"]["sets"], gym["dose"]["reps_min"], gym["dose"]["reps_max"]) == (2, 8, 12)
    assert gym["dose"]["basis"] == "editorial"
    assert any("cdc.gov" in s["url"] for s in gym["source_links"])
    assert home["load"] is gym["load"] is None
    assert home["load_recordable"] is gym["load_recordable"] is True
    press = exercise("gym-dumbbell-foundations", "dumbbell-flat-bench-press")
    assert "por debajo" in " ".join(press["instructions"])
    assert "bench_transfer" in press["capabilities"]


def test_yoga_breaths_and_core_holds_are_never_presented_as_measured_seconds():
    tree = exercise("yoga-gentle-start", "yoga-supported-tree-toes")
    assert tree["dose"]["seconds"] is None
    assert (tree["dose"]["breaths_min"], tree["dose"]["breaths_max"]) == (3, 5)
    assert tree["dose"]["per_side"] is True
    assert tree["tracking_unit"] == "seconds"  # Optional actual elapsed time entered by the member.
    bridge = exercise("core-foundations", "floor-glute-bridge")
    assert bridge["dose"]["seconds"] is None
    assert bridge["dose"]["hold_breaths"] == 3
    assert bridge["tracking_unit"] == "reps"
    assert bridge["dose"]["basis"] == "editorial"
    assert "no una clase de Pilates" in content.training_detail("core-foundations")["scope"]


def test_duration_estimates_account_for_pauses_sides_and_reading():
    for row in content.training_catalog()["programs"]:
        estimate = row["estimated_minutes"]
        assert estimate["source_duration_seconds"] is None
        assert estimate["kind"] == "editorial_estimate"
        components = estimate["components_seconds"]
        assert estimate["min"] == math.ceil(sum(x[0] for x in components.values()) / 60)
        assert estimate["max"] == math.ceil(sum(x[1] for x in components.values()) / 60)
        assert components["warmup"][0] > 0
        assert components["cooldown"][0] > 0
        assert components["between_exercises"][1] > 0
        assert components["reading_and_transitions"][1] > 0
        assert estimate["max"] > estimate["min"]
        assert all(e["rest"]["suggested_seconds"] is None for e in content.training_detail(row["id"])["exercises"])
    gym = content.training_detail("gym-dumbbell-foundations")["estimated_minutes"]
    assert gym["components_seconds"]["between_sets"] == [300, 600]
    assert gym["max"] == 45
    changed = deepcopy(content.training_detail("home-dumbbell-foundations")["exercises"])
    next(e for e in changed if e["id"] == "dumbbell-bent-row")["dose"]["per_side"] = False
    assert content._estimate(changed)["components_seconds"]["work"][1] < content.training_detail("home-dumbbell-foundations")["estimated_minutes"]["components_seconds"]["work"][1]


def test_licensed_adaptations_keep_attribution_and_media_exclusions():
    for program_id in ("home-bodyweight-foundations", "home-dumbbell-foundations", "gentle-mobility"):
        detail = content.training_detail(program_id)
        assert detail["attribution"]["text"] == content.OGL_ATTRIBUTION
        assert detail["attribution"]["url"] == content.OGL_URL
        assert detail["attribution"]["adapted"] is True
        assert all(e["media"] is None for e in detail["exercises"])
    for row in content.training_catalog()["programs"]:
        assert all(link["url"].startswith("https://") for link in row["source_links"])


def test_callers_cannot_mutate_the_reviewed_content_or_a_second_response():
    original = content.training_detail("home-bodyweight-foundations")
    modified = content.training_detail(original["id"])
    modified["exercises"][1]["dose"]["sets"] = 99
    modified["requirements"]["equipment"].clear()
    catalog = content.training_catalog()
    catalog["programs"][0]["title"] = "Injected"
    catalog["equipment_labels"].clear()
    assert content.training_detail(original["id"]) == original
    assert content.training_catalog()["programs"][0]["title"] != "Injected"
    assert content.training_catalog()["equipment_labels"]


@pytest.mark.parametrize("bad_id", [None, 1, True, [], {}, "", "gentle-strength", "../home-bodyweight-foundations", "HOME-BODYWEIGHT-FOUNDATIONS", " home-bodyweight-foundations"])
def test_unknown_ids_do_not_fall_back_to_a_routine(bad_id):
    with pytest.raises(content.TrainingContentError):
        content.training_detail(bad_id)


@pytest.mark.parametrize("field,value", [("equipment_complete", False), ("equipment", []), ("capabilities", [])])
def test_missing_requirements_fail_closed(monkeypatch, field, value):
    damaged = deepcopy(content._PROGRAMS)
    damaged[0]["requirements"][field] = value
    monkeypatch.setattr(content, "_PROGRAMS", damaged)
    with pytest.raises(content.TrainingContentError):
        content.training_catalog()


def test_editing_dose_without_updating_duration_is_rejected(monkeypatch):
    damaged = deepcopy(content._PROGRAMS)
    damaged[0]["exercises"][1]["dose"]["sets"] = 10
    monkeypatch.setattr(content, "_PROGRAMS", damaged)
    with pytest.raises(content.TrainingContentError):
        content.training_detail("home-bodyweight-foundations")


def test_unreviewed_instruction_edit_cannot_keep_earlier_source_audit(monkeypatch):
    damaged = deepcopy(content._PROGRAMS)
    damaged[0]["exercises"][1]["instructions"][0] = "Unreviewed replacement."
    monkeypatch.setattr(content, "_PROGRAMS", damaged)
    with pytest.raises(content.TrainingContentError):
        content.training_catalog()
