"""Synthetic preference/timing contracts; these do not approve clinical protocols."""
import math

import pytest
from pydantic import ValidationError

from roxy_os.fitness.domain import ExerciseTiming, FitnessInputError, preview_readiness, validate_session_duration
from roxy_os.fitness.schemas import FitnessConsentInput, FitnessDeleteRequest, FitnessProfileInput


def profile(**overrides):
    value = {"age_band": "30_44", "timezone": "America/New_York", "primary_goal": "fitness_habit",
             "session_minutes": 20, "locations": ["home"], "equipment": ["bodyweight"],
             "availability": [{"day": "mon", "windows": [{"start": "08:00", "end": "08:20"}]}]}
    return FitnessProfileInput.model_validate({**value, **overrides})


def approved_catalog():
    # Pure fixtures, not actual professional/content approval.
    return {"synthetic-1": {"review_status": "approved", "rights_valid": True, "active": True}}


def test_minimal_profile_is_optional_preferences_not_fake_health():
    parsed = FitnessProfileInput(timezone="UTC")
    assert parsed.age_band is None
    assert parsed.without_weight_or_calories is True
    assert parsed.primary_goal is None
    assert "weight" not in parsed.model_dump()
    result = preview_readiness(parsed, consent_active=True)
    assert result["status"] == "needs_more_information"
    assert "age_band" in result["missing_fields"]


@pytest.mark.parametrize("field,value", [
    ("age_band", "17"), ("age_band", 30), ("language", "xx"), ("weight_unit", "lbs"),
    ("length_unit", "in"), ("timezone", "Orlando"), ("timezone", "../../etc/passwd"),
    ("session_minutes", "20"), ("session_minutes", True), ("session_minutes", 0),
    ("session_minutes", 181), ("travel_minutes", -1), ("without_weight_or_calories", "false"),
    ("experience", "expert"), ("locations", ["home", "home"]), ("equipment", ["unknown_machine"]),
    ("member_id", "someone_else"), ("household_id", "household-1"), ("diagnosis", "anything"),
    ("medication", "anything"), ("weight", 200), ("calories", 1000), ("approved", True),
])
def test_invalid_or_sensitive_profile_fields_rejected(field, value):
    with pytest.raises(ValidationError):
        profile(**{field: value})


@pytest.mark.parametrize("windows", [
    [{"start": "08:60", "end": "09:00"}], [{"start": "24:00", "end": "25:00"}],
    [{"start": "8:00", "end": "09:00"}], [{"start": "09:00", "end": "08:00"}],
    [{"start": "09:00", "end": "09:00"}],
    [{"start": "08:00", "end": "09:00"}, {"start": "08:59", "end": "10:00"}],
])
def test_time_windows_do_not_rollover_or_overlap(windows):
    with pytest.raises(ValidationError):
        profile(availability=[{"day": "mon", "windows": windows}])


def test_adjacent_windows_valid_but_duplicate_days_rejected():
    entry = {"day": "mon", "windows": [{"start": "08:00", "end": "09:00"}, {"start": "09:00", "end": "10:00"}]}
    assert profile(availability=[entry]).availability[0].day == "mon"
    with pytest.raises(ValidationError):
        profile(availability=[entry, entry])


@pytest.mark.parametrize("primary,secondary", [("fat_loss", "healthy_weight_gain"), ("strength", "strength"), (None, "strength")])
def test_contradictory_goals_rejected(primary, secondary):
    with pytest.raises(ValidationError):
        profile(primary_goal=primary, secondary_goal=secondary)


def test_compatible_goals_and_imperial_preferences_not_converted_to_metrics():
    parsed = profile(primary_goal="muscle_gain", secondary_goal="strength", weight_unit="lb", length_unit="ft_in")
    assert parsed.weight_unit == "lb"
    assert "weight" not in parsed.model_dump()


def test_consent_requires_exact_version_and_explicit_bool():
    good = {"purpose": "fitness_preferences", "text_version": "fitness-preferences-v1", "granted": True}
    assert FitnessConsentInput.model_validate(good).granted
    for changes in ({"purpose": "marketing"}, {"text_version": "old"}, {"granted": "true"}, {"member_id": "other"}):
        with pytest.raises(ValidationError):
            FitnessConsentInput.model_validate({**good, **changes})
    for value in (False, 1, "true"):
        with pytest.raises(ValidationError):
            FitnessDeleteRequest(expected_version=1, confirm_delete=value)


def test_complete_preferences_never_produce_workout_or_safety_clearance():
    result = preview_readiness(profile(), consent_active=True, clinical_approval=True,
                               trusted_catalog=approved_catalog(), safety_status="eligible_general_wellness")
    assert result["status"] == "needs_professional_review"
    assert result["reason_code"] == "content_review_required"
    assert not result["medical_clearance"] and not result["can_activate"]
    assert result["sessions"] == result["prescriptions"] == []
    assert preview_readiness(profile(), consent_active=False)["reason_code"] == "consent_required"


def test_one_set_has_no_mandatory_rest_after_last_set():
    assert ExerciseTiming("synthetic-1", 1, 30, 60).total_seconds() == 30
    assert ExerciseTiming("synthetic-1", 3, 30, 60).total_seconds() == 210


def test_unilateral_counts_both_sides_and_side_transition_not_extra_last_rest():
    movement = ExerciseTiming("synthetic-1", 3, 30, 60, True, 5, 20)
    assert movement.total_seconds() == 335  # 180 work + 120 rest + 15 side + 20 setup


def test_session_budget_and_separate_travel():
    result = validate_session_duration([ExerciseTiming("synthetic-1", 3, 30, 60)], trusted_catalog=approved_catalog(),
                                      available_seconds=300, warmup_seconds=60, cooldown_seconds=30, travel_seconds=600)
    assert result["valid_duration"] is True
    assert result["training_seconds"] == 300
    assert result["calendar_seconds"] == 900
    assert result["clinical_approval"] is False
    result = validate_session_duration([ExerciseTiming("synthetic-1", 3, 30, 60)], trusted_catalog=approved_catalog(), available_seconds=200)
    assert result["valid_duration"] is False and result["overrun_seconds"] == 10


def test_transitions_are_only_between_movements():
    result = validate_session_duration([ExerciseTiming("synthetic-1", 1, 30, 60)] * 2,
                                      trusted_catalog=approved_catalog(), available_seconds=90, transition_seconds=20)
    assert result["training_seconds"] == 80


@pytest.mark.parametrize("field,value", [("sets", True), ("sets", 0), ("sets", 2.5), ("sets", 101),
                                        ("work_seconds_per_set_per_side", 0), ("work_seconds_per_set_per_side", math.inf),
                                        ("rest_seconds_between_sets", -1), ("rest_seconds_between_sets", "30"),
                                        ("unilateral", "yes"), ("side_transition_seconds", 5)])
def test_timing_rejects_invalid_missing_or_misleading_values(field, value):
    args = {"exercise_id": "synthetic-1", "sets": 2, "work_seconds_per_set_per_side": 30, "rest_seconds_between_sets": 60}
    with pytest.raises(FitnessInputError):
        ExerciseTiming(**{**args, field: value}).total_seconds()


@pytest.mark.parametrize("catalog", [None, {}, {"synthetic-1": {}}, {"synthetic-1": {"review_status": "proposed", "rights_valid": True, "active": True}},
                                      {"synthetic-1": {"review_status": "approved", "rights_valid": False, "active": True}}])
def test_unreviewed_unknown_or_unlicensed_catalog_cannot_validate(catalog):
    with pytest.raises(FitnessInputError):
        validate_session_duration([ExerciseTiming("synthetic-1", 1, 30, 0)], available_seconds=100, trusted_catalog=catalog)
