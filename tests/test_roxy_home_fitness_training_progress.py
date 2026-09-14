"""Actual manual records stay descriptive, versioned and free of guessed data."""
from copy import deepcopy
from uuid import UUID

import pytest

from roxy_os.fitness.training_content import CONTENT_VERSION, training_catalog, training_detail
from roxy_os.fitness.training_logs import StoredTrainingLog, TrainingLoad
from roxy_os.fitness.training_progress import training_progress


def movement(identity, unit="reps", *, per_side=False):
    return {"id": identity, "name": f"Movimiento {identity}", "phase": "work", "tracking_unit": unit,
            "dose": {"per_side": per_side}, "load_recordable": unit == "reps",
            "source_links": [{"title": "Fuente de la variante", "url": "https://example.org/source"}]}


PROGRAMS = [{"id": "session-a", "title": "Rutina A", "content_version": "test-v1", "exercises": [
    movement("shared-reps", per_side=True), movement("held-pose", "seconds")]},
    {"id": "session-b", "title": "Rutina B", "content_version": "test-v1", "exercises": [
        movement("shared-reps", per_side=True)]}]


def series(reps=None, *, seconds=None, value=None, unit="kg"):
    load = TrainingLoad(value=value, unit=unit) if value is not None else None
    return {"reps": reps, "seconds": seconds, "load": load.model_dump() if load else None,
            "load_kg": load.kilograms() if load else None}


def record(index, day, *, reps=None, seconds=None, skip_reps=False, skip_seconds=False,
           duration=None, version="test-v1", program="session-a"):
    entries = [{"exercise_id": "shared-reps", "skipped": skip_reps,
                "sets": [] if skip_reps else reps if reps is not None else [series(8)]}]
    if program != "session-b":
        entries.append({"exercise_id": "held-pose", "skipped": skip_seconds,
                        "sets": [] if skip_seconds else seconds if seconds is not None else [series(seconds=20)]})
    return StoredTrainingLog.model_validate({
        "session_id": str(UUID(int=index)), "program_id": program, "content_version": version,
        "performed_on": day, "timezone": "America/New_York", "duration_minutes": duration,
        "exercises": entries, "scheduled_date": day, "scheduled_time": "10:00",
        "scheduled_timezone": "America/New_York", "recorded_at": "2020-12-01T12:00:00Z",
        "updated_at": "2020-12-01T12:00:00Z",
    }).model_dump(mode="json")


def snapshot(*records):
    return {"version": 17, "updated_at": "2020-12-01T12:00:00Z", "logs": list(records)}


def project(*records):
    return training_progress(snapshot(*records), programs=PROGRAMS)


def group(result, identity="shared-reps", *, version="test-v1", unit="reps"):
    return next(item for item in result["exercises"] if item["exercise_id"] == identity
                and item["content_version"] == version and item["tracking_unit"] == unit)


def test_empty_snapshot_has_no_invented_duration_or_progress():
    result = training_progress({"version": 0, "updated_at": None, "logs": []}, programs=PROGRAMS)
    assert result["format"] == "roxy-home-training-progress-v1"
    assert result["logs_version"] == 0 and result["updated_at"] is None
    assert result["content_version"] == CONTENT_VERSION
    assert result["self_reported"] is True and result["clinical_approval"] is False
    assert result["workouts"] == result["exercises"] == []
    assert result["summary"] == {
        "recorded_sessions": 0, "active_days": 0, "exercise_entries": 0,
        "performed_exercise_entries": 0, "skipped_exercise_entries": 0, "total_sets": 0,
        "first_performed_on": None, "last_performed_on": None,
        "duration": {"reported_sessions": 0, "unreported_sessions": 0, "total_minutes": None}}


def test_summary_counts_explicit_entries_once_and_does_not_turn_missing_minutes_into_zero():
    result = project(record(1, "2020-01-01", duration=12.5, skip_seconds=True),
                     record(2, "2020-01-03", duration=0.1), record(3, "2020-01-03", program="session-b"))
    summary = result["summary"]
    assert summary["recorded_sessions"] == 3 and summary["active_days"] == 2
    assert summary["exercise_entries"] == 5 and summary["performed_exercise_entries"] == 4
    assert summary["skipped_exercise_entries"] == 1 and summary["total_sets"] == 4
    assert summary["first_performed_on"] == "2020-01-01" and summary["last_performed_on"] == "2020-01-03"
    assert summary["duration"] == {"reported_sessions": 2, "unreported_sessions": 1, "total_minutes": 12.6}
    assert project(record(1, "2020-01-01"))["summary"]["duration"]["total_minutes"] is None


def test_original_units_and_each_set_survive_while_comparison_normalizes_loads():
    old = record(1, "2020-01-01", reps=[series(8, value=10, unit="lb"), series(8)])
    new = record(2, "2020-01-03", reps=[series(10, value=5), series(9, value=0)])
    result = project(old, new)
    row = group(result)
    assert row["latest"]["sets"] == new["exercises"][0]["sets"]
    assert row["previous"]["sets"] == old["exercises"][0]["sets"]
    assert row["per_side"] is True
    assert row["latest"]["totals"] == {"sets": 2, "reps": 19, "seconds": None}
    assert row["comparison"]["load_kg_deltas"] == [0.464076, None]
    assert row["comparison"]["reps_delta"] == 3 and row["comparison"]["seconds_delta"] is None
    assert row["comparison"]["interpretation"] == "descriptive_only"
    assert "fuerza ni tu salud" in row["comparison"]["label"]
    assert row["comparison"]["set_count_delta"] == 0
    assert all(item["can_repeat"] for item in result["workouts"])


def test_explicit_zero_load_is_real_and_not_treated_as_omission():
    row = group(project(record(1, "2020-01-01", reps=[series(8, value=0)]),
                        record(2, "2020-01-03", reps=[series(8, value=0)])))
    assert row["comparison"]["load_kg_deltas"] == [0]
    assert row["latest"]["sets"][0]["load"] == {"value": 0, "unit": "kg"}


def test_unmatched_sets_have_no_load_comparison_and_counts_remain_descriptive():
    row = group(project(record(1, "2020-01-01", reps=[series(8, value=1)]),
                        record(2, "2020-01-03", reps=[series(8, value=1), series(8, value=2)])))
    assert row["comparison"]["set_count_delta"] == 1
    assert row["comparison"]["reps_delta"] == 8
    assert row["comparison"]["load_kg_deltas"] == [0, None]


def test_timed_movements_keep_fractional_seconds_and_have_no_fake_repetition_total():
    result = project(record(1, "2020-01-01", seconds=[series(seconds=0.1), series(seconds=0.2)]),
                     record(2, "2020-01-03", seconds=[series(seconds=0.2), series(seconds=0.3)]))
    row = group(result, "held-pose", unit="seconds")
    assert row["previous"]["totals"] == {"sets": 2, "reps": None, "seconds": 0.3}
    assert row["comparison"]["seconds_delta"] == 0.2
    assert row["comparison"]["reps_delta"] is None
    assert row["comparison"]["load_kg_deltas"] == [None, None]


def test_same_movement_in_two_routines_can_compare_exact_variant_and_version():
    result = project(record(1, "2020-01-01"), record(2, "2020-01-03", program="session-b"))
    row = group(result)
    assert row["entry_count"] == 2
    assert row["latest"]["program_title"] == "Rutina B"
    assert row["previous"]["program_title"] == "Rutina A"
    assert row["comparison_reason"] == "compared"


@pytest.mark.parametrize("duplicate_day", ["2020-01-01", "2020-01-03"])
def test_multiple_unordered_entries_on_either_day_disable_comparison(duplicate_day):
    result = project(record(1, "2020-01-01"), record(2, "2020-01-03"),
                     record(3, duplicate_day, program="session-b"))
    row = group(result)
    assert row["previous"]["performed_on"] == "2020-01-01"
    assert row["comparison"] is None and row["comparison_reason"] == "multiple_entries_on_day"
    assert row["latest_day_entry_count"] == (2 if duplicate_day == "2020-01-03" else 1)
    assert row["previous_day_entry_count"] == (2 if duplicate_day == "2020-01-01" else 1)


def test_same_day_is_never_invented_as_previous_workout_even_if_saved_at_different_times():
    first, second = record(1, "2020-01-03"), record(2, "2020-01-03")
    first["updated_at"] = "2020-12-31T12:00:00Z"
    row = group(project(first, second))
    assert row["previous"] is None and row["previous_day_entry_count"] == 0
    assert row["comparison"] is None and row["comparison_reason"] == "multiple_entries_on_day"


def test_backfilled_or_edited_records_sort_by_performed_date_not_write_time():
    early, late = record(1, "2020-01-01"), record(2, "2020-01-03")
    early["updated_at"] = "2020-12-31T12:00:00Z"
    row = group(project(late, early))
    assert row["latest"]["session_id"] == late["session_id"]
    assert row["previous"]["session_id"] == early["session_id"]
    assert row["comparison_reason"] == "compared"


@pytest.mark.parametrize("skipped_day", ["2020-01-02", "2020-01-03"])
def test_skipped_entry_stays_visible_and_cannot_be_skipped_over_for_a_better_comparison(skipped_day):
    result = project(record(1, "2020-01-01"),
                     record(2, "2020-01-02", skip_reps=skipped_day == "2020-01-02"),
                     record(3, "2020-01-03", skip_reps=skipped_day == "2020-01-03"))
    row = group(result)
    assert row["previous"]["performed_on"] == "2020-01-02"
    assert row["comparison"] is None and row["comparison_reason"] == "skipped_entry"
    assert row["performed_count"] == 2 and row["skipped_count"] == 1
    skipped = next(item for item in row["history"] if item["skipped"])
    assert skipped["totals"] == {"sets": 0, "reps": None, "seconds": None}
    assert skipped["sets"] == []


def test_distinct_content_versions_never_share_comparison_and_retired_workouts_cannot_repeat():
    result = project(record(1, "2020-01-01", version="old-v1"), record(2, "2020-01-03"))
    old = group(result, version="old-v1")
    current = group(result)
    assert old["current_content_available"] is False and old["source_links"] == []
    assert old["per_side"] is None and old["name"].startswith("Ejercicio guardado")
    assert old["comparison"] is current["comparison"] is None
    assert {row["can_repeat"] for row in result["workouts"] if row["content_version"] == "old-v1"} == {False}


def test_retired_skipped_entry_joins_history_only_when_the_recorded_unit_is_unambiguous():
    result = project(record(1, "2020-01-01", version="old-v1"),
                     record(2, "2020-01-03", version="old-v1", skip_reps=True))
    row = group(result, version="old-v1")
    assert row["entry_count"] == 2 and row["latest"]["skipped"] is True
    assert row["comparison_reason"] == "skipped_entry"


def test_historical_units_do_not_merge_and_ambiguous_skipped_entries_stay_separate():
    first = record(1, "2020-01-01", version="old-v1")
    second = record(2, "2020-01-03", version="old-v1", reps=[series(seconds=5)])
    third = record(3, "2020-01-04", version="old-v1", skip_reps=True)
    rows = [item for item in project(first, second, third)["exercises"] if item["exercise_id"] == "shared-reps"]
    assert {row["tracking_unit"] for row in rows} == {"reps", "seconds", None}
    assert all(row["comparison"] is None and row["entry_count"] == 1 for row in rows)


@pytest.mark.parametrize("change", ["unknown_program", "extra_exercise", "missing_exercise", "wrong_axis", "unreviewed_load"])
def test_repeat_requires_exact_current_program_and_valid_work_exercise_ids(change):
    row = record(1, "2020-01-01")
    if change == "unknown_program":
        row["program_id"] = "retired-routine"
    elif change == "extra_exercise":
        row["exercises"].append({"exercise_id": "unreviewed", "skipped": False, "sets": [series(8)]})
    elif change == "missing_exercise":
        row["exercises"].pop()
    elif change == "wrong_axis":
        row["exercises"][0]["sets"] = [series(seconds=5)]
    else:
        row["exercises"][1]["sets"] = [series(seconds=5, value=1)]
    row = StoredTrainingLog.model_validate(row).model_dump(mode="json")
    result = project(row)
    assert result["workouts"][0]["can_repeat"] is False
    assert result["summary"]["recorded_sessions"] == 1


def test_projection_is_pure_and_returns_independent_copies_of_sensitive_records():
    original = snapshot(record(1, "2020-01-01", reps=[series(8, value=1)]))
    saved, content = deepcopy(original), deepcopy(PROGRAMS)
    result = training_progress(original, programs=PROGRAMS)
    result["exercises"][0]["source_links"][0]["title"] = "Changed"
    row = group(result)
    row["latest"]["sets"][0]["load"]["value"] = 90
    assert row["history"][0]["sets"][0]["load"]["value"] == 1
    row["history"][0]["sets"][0]["load"]["value"] = 80
    assert original == saved and PROGRAMS == content


def test_current_real_catalog_is_used_without_external_calls_or_profile_inputs():
    detail = training_detail(training_catalog()["programs"][0]["id"])
    raw = record(1, "2020-01-01")
    raw.update(program_id=detail["id"], content_version=detail["content_version"], exercises=[
        {"exercise_id": item["id"], "skipped": False,
         "sets": [series(1) if item["tracking_unit"] == "reps" else series(seconds=1)]}
        for item in detail["exercises"] if item["phase"] == "work"])
    saved = StoredTrainingLog.model_validate(raw).model_dump(mode="json")
    result = training_progress(snapshot(saved))
    assert result["workouts"][0]["can_repeat"] is True
    assert result["workouts"][0]["program_title"] == detail["title"]
    assert all(item["current_content_available"] for item in result["exercises"])
    assert {item["exercise_id"] for item in result["exercises"]} == {item["id"] for item in detail["exercises"] if item["phase"] == "work"}
