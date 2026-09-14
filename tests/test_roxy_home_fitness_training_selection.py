"""Actual editorial content selection: time, confirmed requirements and preservation."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from roxy_os.fitness import training_selection as selection
from roxy_os.fitness.activity_plan import ActivityPlan
from roxy_os.fitness.domain import FitnessInputError
from roxy_os.fitness.training_content import TrainingContentError, training_detail

NOW = datetime(2026, 9, 14, 11, tzinfo=timezone.utc)
PROGRAM = "home-dumbbell-foundations"


def profile(**changes):
    return {"age_band": "30_44", "timezone": "America/New_York", "experience": "beginner",
            "locations": ["home"], "equipment": ["bodyweight", "dumbbells"],
            "session_minutes": 45, "travel_minutes": 10,
            "availability": [{"day": day, "windows": [{"start": "08:00", "end": "09:00"}]} for day in selection.DAYS], **changes}


def confirmed(program_id=PROGRAM):
    requirements = training_detail(program_id)["requirements"]
    return {key: list(requirements[key]) for key in ("equipment", "capabilities")}


def preview(program_id=PROGRAM, **kwargs):
    return selection.preview_training(kwargs.pop("profile", profile()), program_id, kwargs.pop("confirmed", confirmed(program_id)),
                                      now=kwargs.pop("now", NOW), **kwargs)


def old_row(*, day="2026-09-16", status="planned", program_id="gentle-flexibility", clock="08:00"):
    return {"id": str(uuid4()), "program_id": program_id, "date": day, "time": clock, "status": status}


def test_real_routine_preview_is_reviewable_and_retains_own_content_metadata():
    before_profile, before_confirmed = profile(), confirmed()
    original_profile, original_confirmed = deepcopy(before_profile), deepcopy(before_confirmed)
    result = preview(profile=before_profile, confirmed=before_confirmed)
    assert [s["date"] for s in result["sessions"]] == ["2026-09-14", "2026-09-16", "2026-09-18", "2026-09-20"]
    assert result["clinical_approval"] is False
    assert result["status"] == "ready"
    assert len(result["excluded_days"]) == 3
    for row, detail in zip(result["sessions"], result["session_details"]):
        assert row["time"] == "08:00"
        assert row["program_id"] == PROGRAM
        assert row["content_version"] == training_detail(PROGRAM)["content_version"]
        assert row["confirmed_requirements"] == original_confirmed
        assert row["reserved_minutes"] == 45 and row["travel_minutes"] == 10
        assert "status" not in row and "completed_at" not in row
        assert datetime.fromisoformat(detail["reserved_until"]) - datetime.fromisoformat(detail["starts_at"]) == timedelta(minutes=55)
    ActivityPlan.model_validate({"title": "Borrador sintético", "timezone": result["timezone"], "sessions": result["sessions"]})
    assert before_profile == original_profile and before_confirmed == original_confirmed


@pytest.mark.parametrize("changes", [{"age_band": None}, {"experience": "prefer_not_to_say"}, {"locations": []}, {"locations": ["outdoors"]}, {"session_minutes": None}, {"session_minutes": 33}])
def test_missing_or_incompatible_preferences_do_not_produce_a_plan(changes):
    with pytest.raises(FitnessInputError):
        preview(profile=profile(**changes))


def test_beginner_cannot_obtain_intermediate_gym_from_equipment_alone():
    with pytest.raises(FitnessInputError, match="experiencia"):
        preview("gym-dumbbell-foundations", profile=profile(locations=["gym"]))
    result = preview("gym-dumbbell-foundations", profile=profile(locations=["gym"], experience="intermediate"))
    assert result["sessions"]


@pytest.mark.parametrize("missing", ["wall", "dumbbells", "bodyweight"])
def test_each_required_item_needs_confirmation(missing):
    choice = confirmed()
    choice["equipment"].remove(missing)
    with pytest.raises(FitnessInputError, match="material"):
        preview(confirmed=choice)


@pytest.mark.parametrize("missing", ["standing", "hip_hinge", "free_weights"])
def test_each_required_capability_needs_confirmation(missing):
    choice = confirmed()
    choice["capabilities"].remove(missing)
    with pytest.raises(FitnessInputError, match="movimientos"):
        preview(confirmed=choice)


def test_unknown_equipment_and_duplicate_confirmations_are_invalid():
    choice = confirmed(); choice["equipment"].append("all_gym_machines")
    with pytest.raises(ValidationError):
        preview(confirmed=choice)
    choice = confirmed(); choice["capabilities"].append(choice["capabilities"][0])
    with pytest.raises(ValidationError):
        preview(confirmed=choice)


def test_travel_and_whole_reserved_session_must_fit():
    result = preview(profile=profile(session_minutes=50, travel_minutes=11))
    assert result["status"] == "no_slots" and result["sessions"] == []
    exact = preview(profile=profile(session_minutes=50, travel_minutes=10))
    assert exact["sessions"][0]["time"] == "08:00"
    assert exact["session_details"][0]["reserved_until"].startswith("2026-09-14T13:00")


def test_mobility_is_not_forced_to_follow_strength_recovery_frequency():
    result = preview("gentle-mobility", profile=profile(session_minutes=20, travel_minutes=0))
    assert len(result["sessions"]) == 7


def test_preserves_existing_sessions_statuses_and_strength_recovery_across_week_boundary():
    existing = {"title": "Antes", "timezone": "America/New_York", "sessions": [
        old_row(day="2026-09-13", status="completed", program_id="gentle-strength"),
        old_row(day="2026-09-16"),
    ]}
    before = deepcopy(existing)
    result = preview(existing_plan=existing)
    assert result["sessions"][0]["date"] == "2026-09-15"
    assert "2026-09-16" not in [s["date"] for s in result["sessions"]]
    assert existing == before
    assert all(s["id"] not in {x["id"] for x in existing["sessions"]} for s in result["sessions"])


def test_skipped_activity_remains_stored_and_its_exact_time_is_not_reused():
    existing = {"title": "Antes", "timezone": "America/New_York", "sessions": [old_row(day="2026-09-14", status="skipped")]}
    result = preview(existing_plan=existing)
    assert result["sessions"][0]["time"] == "08:01"
    assert existing["sessions"][0]["status"] == "skipped"


def test_existing_plan_timezone_cannot_silently_change():
    with pytest.raises(FitnessInputError, match="zona"):
        preview(existing_plan={"timezone": "UTC", "sessions": [old_row()]})


def test_plan_limit_preserves_all_rows_without_inserting():
    existing = {"timezone": "America/New_York", "sessions": [old_row(day="2026-09-10", status="skipped") for _ in range(366)]}
    result = preview(existing_plan=existing)
    assert result["status"] == "no_slots"
    assert all("límite" in day["message_es"] for day in result["excluded_days"])
    assert len(existing["sessions"]) == 366


def test_now_uses_local_day_and_never_a_clock_in_the_past():
    now = datetime(2026, 9, 14, 12, 0, 30, tzinfo=timezone.utc)
    result = preview(now=now)
    assert result["sessions"][0]["time"] == "08:01"
    near_midnight = preview(now=datetime(2026, 9, 15, 1, tzinfo=timezone.utc))
    assert near_midnight["start_date"] == "2026-09-14"
    assert all(datetime.fromisoformat(row["starts_at"]) >= now for row in result["session_details"])


@pytest.mark.parametrize("value", ["", "2026-9-14", "2026-02-30", "1999-12-31", "2100-12-28", "2026-09-13"])
def test_invalid_or_past_start_dates_do_not_fall_back_to_today(value):
    with pytest.raises(FitnessInputError):
        preview(start_date=value)


@pytest.mark.parametrize("value", [datetime(2026, 9, 14), "2026-09-14", datetime(2026, 9, 14, tzinfo=timezone(timedelta(hours=1)))])
def test_reference_time_requires_aware_utc(value):
    with pytest.raises(FitnessInputError):
        preview(now=value)


@pytest.mark.parametrize("program_id", ["unknown", "gentle-strength", "../core-foundations"])
def test_only_explicit_editorial_program_ids_are_accepted(program_id):
    with pytest.raises(TrainingContentError):
        preview(program_id, confirmed=confirmed())


@pytest.mark.parametrize("day,window", [("2026-11-01", ("01:00", "02:00")), ("2027-03-14", ("02:00", "03:00"))])
def test_dst_ambiguous_and_nonexistent_windows_never_silently_resolve(day, window):
    p = profile(session_minutes=20, travel_minutes=0, availability=[{"day": "sun", "windows": [{"start": window[0], "end": window[1]}]}])
    result = preview("gentle-mobility", profile=p, start_date=day)
    assert result["status"] == "no_slots"


def test_dst_can_move_to_unambiguous_later_window():
    p = profile(session_minutes=20, travel_minutes=0, availability=[{"day": "sun", "windows": [{"start": "01:00", "end": "02:00"}, {"start": "03:00", "end": "04:00"}]}])
    result = preview("gentle-mobility", profile=p, start_date="2026-11-01")
    assert result["sessions"][0]["time"] == "03:00"
    assert result["session_details"][0]["starts_at"].startswith("2026-11-01T08:00")


def test_new_save_revalidates_version_equipment_time_profile_and_recovery():
    p = profile()
    rows = preview()["sessions"]
    plan = {"timezone": p["timezone"]}
    selection.validate_new_training_session(p, rows[0], plan, rows)
    for field, value in (("content_version", "stale-version"), ("reserved_minutes", 60), ("travel_minutes", 0), ("time", "09:00")):
        with pytest.raises(FitnessInputError):
            selection.validate_new_training_session(p, {**rows[0], field: value}, plan, rows)
    with pytest.raises(FitnessInputError):
        selection.validate_new_training_session(p, rows[0], {"timezone": "UTC"}, rows)
    with pytest.raises(FitnessInputError):
        selection.validate_new_training_session(p, rows[0], plan, [old_row(day="2026-09-15", program_id="gentle-strength")])
    with pytest.raises(FitnessInputError):
        selection.validate_new_training_session(p, rows[0], plan, [old_row(day="2026-09-14")])


def test_save_with_ambiguous_end_is_input_error_not_storage_failure():
    p = profile(session_minutes=60, travel_minutes=0, availability=[{"day": "sun", "windows": [{"start": "00:00", "end": "04:00"}]}])
    row = {"id": str(uuid4()), "program_id": PROGRAM, "date": "2026-11-01", "time": "00:30",
           "content_version": training_detail(PROGRAM)["content_version"], "confirmed_requirements": confirmed(), "reserved_minutes": 60, "travel_minutes": 0}
    with pytest.raises(FitnessInputError, match="ambiguo"):
        selection.validate_new_training_session(p, row, {"timezone": p["timezone"]}, [])
