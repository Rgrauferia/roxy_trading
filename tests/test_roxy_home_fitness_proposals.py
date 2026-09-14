"""Scheduling rules for a read-only agenda; no workout prescription claims."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from roxy_os.fitness.activity_plan import ActivityPlan, session_instant
from roxy_os.fitness.domain import FitnessInputError
from roxy_os.fitness.proposals import build_proposal
from roxy_os.fitness.schemas import FitnessProfileInput


NOW = datetime(2026, 9, 14, 7, 0, tzinfo=timezone.utc)  # Monday


def profile(**updates):
    data = {
        "age_band": "30_44", "timezone": "UTC", "session_minutes": 20,
        "availability": [{"day": day, "windows": [{"start": "08:00", "end": "09:00"}]}
                         for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")],
    }
    return {**data, **updates}


def existing(day="2026-09-14", clock="08:00", *, program="gentle-balance", status="planned", identifier=None):
    return {"id": identifier or str(uuid4()), "program_id": program, "date": day, "time": clock,
            "status": status, "completed_at": "2026-09-14T08:30:00+00:00" if status == "completed" else None,
            "starts_at": day + "T" + clock + ":00+00:00"}


def propose(p=None, programs=None, **kwargs):
    return build_proposal(p or profile(), kwargs.pop("start_date", "2026-09-14"),
                          programs or ["gentle-balance"], kwargs.pop("now", NOW), **kwargs)


def test_seven_day_proposal_is_deterministic_read_only_and_activity_plan_compatible():
    p = profile()
    before = deepcopy(p)
    result = propose(p, ["gentle-balance", "gentle-flexibility"])
    assert result == propose(p, ["gentle-balance", "gentle-flexibility"])
    assert p == before
    assert len(result["sessions"]) == 7
    assert [row["program_id"] for row in result["sessions"]] == [
        "gentle-balance", "gentle-flexibility", "gentle-balance", "gentle-flexibility",
        "gentle-balance", "gentle-flexibility", "gentle-balance"]
    ActivityPlan.model_validate({"title": "Revisar", "timezone": "UTC", "sessions": result["sessions"]})
    assert result["clinical_approval"] is False
    assert result["can_activate_training"] is False
    assert result["source_duration_minutes"] is None
    assert all(detail["source_duration_minutes"] is None for detail in result["session_details"])
    assert "no garantiza" in result["notice_es"]


@pytest.mark.parametrize("end,travel,count", [("08:20", 0, 1), ("08:19", 0, 0), ("08:30", 10, 1), ("08:29", 10, 0)])
def test_window_exact_fit_and_travel_are_elapsed_reservation(end, travel, count):
    p = profile(travel_minutes=travel, availability=[{"day": "mon", "windows": [{"start": "08:00", "end": end}]}])
    result = propose(p)
    assert len(result["sessions"]) == count
    if count:
        detail = result["session_details"][0]
        assert datetime.fromisoformat(detail["reserved_until"]) - datetime.fromisoformat(detail["starts_at"]) == timedelta(minutes=20 + travel)
    else:
        assert result["excluded_days"][0]["reason_code"] == "window_too_short"


def test_first_fitting_window_is_chosen_in_chronological_order():
    p = profile(availability=[{"day": "mon", "windows": [
        {"start": "12:00", "end": "13:00"}, {"start": "07:30", "end": "07:40"},
        {"start": "09:00", "end": "09:30"}]}])
    assert propose(p)["sessions"][0]["time"] == "09:00"


def test_only_future_minutes_are_proposed_without_rounding_backwards():
    result = propose(now=datetime(2026, 9, 14, 8, 10, 30, tzinfo=timezone.utc))
    assert result["sessions"][0]["time"] == "08:11"
    assert all(datetime.fromisoformat(item["starts_at"]) >= datetime(2026, 9, 14, 8, 10, 30, tzinfo=timezone.utc)
               for item in result["session_details"])


def test_elapsed_day_does_not_produce_backdated_rows():
    result = propose(now=datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc))
    assert result["excluded_days"][0]["reason_code"] == "past_windows"
    assert all(row["date"] != "2026-09-14" for row in result["sessions"])


def test_start_date_is_compared_in_members_timezone():
    p = profile(timezone="America/New_York")
    result = propose(p, now=datetime(2026, 9, 15, 0, 30, tzinfo=timezone.utc))
    assert result["start_date"] == "2026-09-14"  # Still Sep 14 in New York.
    with pytest.raises(FitnessInputError, match="pasado"):
        propose(p, now=datetime(2026, 9, 15, 5, 0, tzinfo=timezone.utc))


@pytest.mark.parametrize("status", ["planned", "completed"])
def test_existing_pending_or_completed_day_is_preserved_and_not_proposed(status):
    rows = [existing(status=status)]
    before = deepcopy(rows)
    result = propose(existing_sessions=rows)
    assert rows == before
    assert len(result["sessions"]) == 6
    assert result["excluded_days"][0]["reason_code"] == "existing_activity"
    assert rows[0]["id"] not in {item["id"] for item in result["sessions"]}


@pytest.mark.parametrize("saved_day,blocked_day", [("2026-09-13", "2026-09-14"), ("2026-09-15", "2026-09-14"),
                                                  ("2026-09-21", "2026-09-20")])
def test_strength_recovery_respects_existing_sessions_before_and_after_week(saved_day, blocked_day):
    result = propose(programs=["gentle-strength"], existing_sessions=[existing(saved_day, program="gentle-strength")])
    assert blocked_day not in {item["date"] for item in result["sessions"]}
    assert any(item["date"] == blocked_day and item["reason_code"] == "strength_recovery" for item in result["excluded_days"])


def test_new_strength_sessions_have_rest_days_and_selected_alternative_can_fill():
    only = propose(programs=["gentle-strength"])
    assert [row["date"] for row in only["sessions"]] == ["2026-09-14", "2026-09-16", "2026-09-18", "2026-09-20"]
    mixed = propose(programs=["gentle-strength", "gentle-balance"],
                    existing_sessions=[existing("2026-09-13", program="gentle-strength")])
    assert mixed["sessions"][0]["program_id"] == "gentle-balance"
    assert mixed["adjustments"][0]["reason_code"] == "strength_recovery"


def test_skipped_strength_does_not_block_next_day_but_its_same_day_clock_is_never_reused():
    initial = propose(programs=["gentle-strength"])["sessions"][0]
    rows = [existing(program="gentle-strength", status="skipped", identifier=initial["id"]),
            existing("2026-09-13", program="gentle-strength", status="skipped")]
    result = propose(programs=["gentle-strength"], existing_sessions=rows)
    first = result["sessions"][0]
    assert first["date"] == "2026-09-14"
    assert first["time"] == "08:01"
    assert first["id"] != initial["id"]
    clean_existing = [{key: row[key] for key in ("id", "program_id", "date", "time")} for row in rows]
    ActivityPlan.model_validate({"title": "Conservado", "timezone": "UTC", "sessions": clean_existing + result["sessions"]})


def test_all_skipped_clocks_are_avoided_even_with_different_guides():
    rows = [existing(clock="08:00", status="skipped"), existing(clock="08:01", program="gentle-flexibility", status="skipped")]
    assert propose(existing_sessions=rows)["sessions"][0]["time"] == "08:02"


def test_skipped_collision_with_exact_fit_does_not_create_unmergeable_proposal():
    p = profile(availability=[{"day": "mon", "windows": [{"start": "08:00", "end": "08:20"}]}])
    result = propose(p, existing_sessions=[existing(status="skipped")])
    assert result["status"] == "no_slots"
    assert result["sessions"] == []
    assert result["excluded_days"][0]["reason_code"] == "existing_time"


@pytest.mark.parametrize("saved_count,new_count", [(365, 1), (366, 0)])
def test_proposal_preserves_room_for_every_existing_row_at_plan_capacity(saved_count, new_count):
    rows = [existing("2026-08-01", clock=f"{minute // 60:02d}:{minute % 60:02d}", status="skipped")
            for minute in range(saved_count)]
    before = deepcopy(rows)
    result = propose(existing_sessions=rows)
    assert rows == before
    assert len(result["sessions"]) == new_count
    assert len(result["sessions"]) + len(rows) == 366
    assert any(item["reason_code"] == "plan_limit" for item in result["excluded_days"])
    clean_existing = [{key: row[key] for key in ("id", "program_id", "date", "time")} for row in rows]
    ActivityPlan.model_validate({"title": "Conservado", "timezone": "UTC", "sessions": clean_existing + result["sessions"]})


@pytest.mark.parametrize("day,start,end,expected", [
    ("2026-03-08", "02:00", "03:30", "03:00"),  # Spring gap skipped.
    ("2026-11-01", "01:00", "02:30", "02:00"),  # Both repeated clocks rejected.
])
def test_dst_resolves_only_unambiguous_clock(day, start, end, expected):
    p = profile(timezone="America/New_York", availability=[{"day": "sun", "windows": [{"start": start, "end": end}]}])
    result = propose(p, start_date=day, now=datetime.fromisoformat(day + "T00:00:00+00:00"))
    assert result["sessions"][0]["time"] == expected
    detail = result["session_details"][0]
    assert datetime.fromisoformat(detail["reserved_until"]) - datetime.fromisoformat(detail["starts_at"]) == timedelta(minutes=20)
    assert datetime.fromisoformat(detail["starts_at"]) == session_instant(day, expected, p["timezone"])


def test_dst_gap_can_shorten_wall_clock_span_but_not_elapsed_reservation():
    p = profile(timezone="America/New_York", session_minutes=30,
                availability=[{"day": "sun", "windows": [{"start": "01:45", "end": "03:15"}]}])
    result = propose(p, start_date="2026-03-08", now=datetime(2026, 3, 8, tzinfo=timezone.utc))
    assert result["sessions"][0]["time"] == "01:45"
    assert result["session_details"][0]["reserved_until"] == "2026-03-08T07:15:00+00:00"


@pytest.mark.parametrize("day,start,end", [("2026-03-08", "02:00", "02:30"), ("2026-11-01", "01:00", "01:30")])
def test_dst_only_ambiguous_or_nonexistent_windows_are_excluded(day, start, end):
    p = profile(timezone="America/New_York", availability=[{"day": "sun", "windows": [{"start": start, "end": end}]}])
    result = propose(p, start_date=day, now=datetime.fromisoformat(day + "T00:00:00+00:00"))
    assert result["status"] == "no_slots"
    assert result["excluded_days"][0]["reason_code"] == "dst_unavailable"


@pytest.mark.parametrize("updates", [{"age_band": None}, {"session_minutes": None}])
def test_required_saved_preferences_are_not_inferred(updates):
    with pytest.raises(FitnessInputError):
        propose(profile(**updates))


def test_typed_saved_profile_is_supported():
    assert propose(FitnessProfileInput.model_validate(profile())) == propose(profile())


@pytest.mark.parametrize("bad", [[], {}, "gentle-balance", ["unknown"], ["gentle-balance", "gentle-balance"], [True]])
def test_rejects_invalid_guide_selection(bad):
    with pytest.raises(FitnessInputError):
        build_proposal(profile(), "2026-09-14", bad, NOW)


@pytest.mark.parametrize("bad", [None, "2026-9-14", "2026-09-31", "1999-12-31", "2100-12-26", "2026-09-13"])
def test_rejects_invalid_or_past_week(bad):
    with pytest.raises(FitnessInputError):
        propose(start_date=bad)


@pytest.mark.parametrize("bad", [None, "2026-09-14T07:00:00Z", datetime(2026, 9, 14),
                                 datetime(2026, 9, 14, tzinfo=timezone(timedelta(hours=2)))])
def test_requires_explicit_utc_reference(bad):
    with pytest.raises(FitnessInputError):
        propose(now=bad)


@pytest.mark.parametrize("updates", [{"session_minutes": True}, {"travel_minutes": -1}, {"weight_kg": 70},
                                      {"timezone": "not-a-zone"}, {"age_band": "under_18"},
                                      {"availability": [{"day": "mon", "windows": [{"start": "09:00", "end": "08:00"}]}]}])
def test_malformed_profile_schema_is_rejected(updates):
    with pytest.raises(ValidationError):
        propose(profile(**updates))


def test_malformed_existing_sessions_and_duplicate_ids_are_rejected():
    row = existing()
    for bad in ("not-a-list", [row] * 367, [row, deepcopy(row)]):
        with pytest.raises(FitnessInputError):
            propose(existing_sessions=bad)
    for bad in ({**row, "status": "unknown"}, {**row, "time": "25:00"}, {**row, "extra": "forbidden"}):
        with pytest.raises(ValidationError):
            propose(existing_sessions=[bad])
