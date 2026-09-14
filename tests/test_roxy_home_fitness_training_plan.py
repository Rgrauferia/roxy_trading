"""Real editorial content through private agenda metadata and version gates."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from roxy_os.fitness.activity_plan import ActivityPlan, ActivityPlanRepository, ActivitySession
from roxy_os.fitness.domain import FitnessInputError
from roxy_os.fitness.repository import PostgresFitnessRepository, FitnessConflict, FitnessConsentRequired
from roxy_os.fitness.schemas import ConfirmedTrainingRequirements
from roxy_os.fitness.training_content import training_detail
from roxy_os.fitness.training_logs import TrainingLogsRepository
from roxy_os.fitness.training_selection import preview_training
from test_roxy_home_fitness_training_logs import LogsSyntheticDB, CONSENT as LOG_CONSENT
from test_roxy_home_fitness_repository import DSN, CONSENT as PROFILE_CONSENT

MEMBER = "member-a"
PROGRAM = "home-dumbbell-foundations"
SESSION = "7b05b497-efb2-4f9f-a9b2-a0d6ca90a910"
LEGACY = "16bbd9f2-913d-4d8a-8a82-c30a817a5d26"
PROFILE = {"age_band": "30_44", "timezone": "UTC", "experience": "beginner", "locations": ["home"],
           "equipment": ["bodyweight", "dumbbells"], "session_minutes": 45, "travel_minutes": 10,
           "availability": [{"day": day, "windows": [{"start": "08:00", "end": "18:00"}]}
                            for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")]}
AGENDA_CONSENT = {"purpose": "fitness_activity_plan", "text_version": "fitness-activity-plan-v1", "granted": True}


def selected(**changes):
    detail = training_detail(PROGRAM)
    return {"id": SESSION, "program_id": PROGRAM, "date": "2020-01-03", "time": "10:00",
            "content_version": detail["content_version"], "reserved_minutes": 45, "travel_minutes": 10,
            "confirmed_requirements": {key: detail["requirements"][key] for key in ("equipment", "capabilities")}, **changes}


def plan(*sessions):
    return {"title": "Training test plan", "timezone": "UTC", "sessions": list(sessions or [selected()])}


def inputs(snapshot):
    return {**snapshot["plan"], "sessions": [{key: value for key, value in row.items()
            if key not in {"status", "completed_at", "starts_at"}} for row in snapshot["plan"]["sessions"]]}


@pytest.fixture
def storage():
    db = LogsSyntheticDB()
    base = PostgresFitnessRepository(DSN, connection_factory=db.connect)
    base.set_consent(MEMBER, PROFILE_CONSENT, expected_version=0, idempotency_key="preferences-consent")
    base.save_profile(MEMBER, PROFILE, expected_version=1, idempotency_key="training-profile")
    repo = ActivityPlanRepository(base)
    repo.consent(MEMBER, AGENDA_CONSENT, expected_version=0, idempotency_key="agenda-consent")
    return repo, base, db


def save(repo, value=None, *, version=1, profile_version=2, key="training-agenda-save"):
    return repo.save(MEMBER, value or plan(), expected_version=version,
                     expected_profile_version=profile_version, idempotency_key=key)


@pytest.mark.parametrize("missing", ["content_version", "confirmed_requirements", "reserved_minutes", "travel_minutes"])
def test_training_sessions_require_all_review_metadata(missing):
    row = selected(); row.pop(missing)
    with pytest.raises(ValidationError):
        ActivitySession.model_validate(row)


@pytest.mark.parametrize("change", [
    {"reserved_minutes": True}, {"reserved_minutes": "45"}, {"reserved_minutes": 4},
    {"travel_minutes": -1}, {"travel_minutes": 181}, {"content_version": ""},
    {"confirmed_requirements": {"equipment": ["unknown"], "capabilities": []}},
    {"confirmed_requirements": {"equipment": ["dumbbells", "dumbbells"], "capabilities": []}},
    {"confirmed_requirements": {"equipment": [], "capabilities": ["medical_clearance"]}},
    {"program_id": "generated-workout"}, {"prescribed_load": 10},
])
def test_invalid_metadata_cannot_enter_saved_agenda(change):
    with pytest.raises(ValidationError):
        ActivitySession.model_validate(selected(**change))


def test_legacy_guides_remain_compatible_without_new_metadata():
    row = {"id": LEGACY, "program_id": "gentle-strength", "date": "2020-01-01", "time": "10:00"}
    assert ActivitySession.model_validate(row).content_version is None
    with pytest.raises(ValidationError):
        ActivitySession.model_validate({**row, "content_version": "home-training-213-v1"})


@pytest.mark.parametrize("version", [None, 0, 1, 3])
def test_new_training_requires_exact_saved_profile_version(storage, version):
    repo, _, _ = storage
    before = repo.snapshot(MEMBER)
    with pytest.raises(FitnessConflict, match="preferencias"):
        save(repo, profile_version=version)
    assert repo.snapshot(MEMBER) == before


def test_new_training_without_saved_preferences_rejects_even_matching_version(storage):
    repo, base, _ = storage
    base.set_consent(MEMBER, {**PROFILE_CONSENT, "granted": False}, expected_version=2, idempotency_key="revoke-profile")
    with pytest.raises(FitnessConsentRequired):
        save(repo, profile_version=3)


@pytest.mark.parametrize("profile_change", [
    {"age_band": None}, {"experience": "prefer_not_to_say"}, {"locations": ["outdoors"]},
    {"session_minutes": 15}, {"availability": []},
])
def test_current_profile_and_actual_content_requirements_are_rechecked(storage, profile_change):
    repo, base, _ = storage
    base.save_profile(MEMBER, {**PROFILE, **profile_change}, expected_version=2, idempotency_key="update-preferences")
    with pytest.raises(FitnessInputError):
        save(repo, profile_version=3)
    assert repo.snapshot(MEMBER)["plan"] is None


@pytest.mark.parametrize("change", [
    {"content_version": "stale-content-v0"}, {"reserved_minutes": 30}, {"travel_minutes": 0},
    {"time": "17:30"}, {"confirmed_requirements": {"equipment": [], "capabilities": []}},
])
def test_schedule_cannot_bypass_review_time_or_equipment(storage, change):
    repo, _, _ = storage
    with pytest.raises(FitnessInputError):
        save(repo, plan(selected(**change)))
    assert repo.snapshot(MEMBER)["plan"] is None


def test_calendar_timezone_must_equal_saved_preferences(storage):
    repo, _, _ = storage
    with pytest.raises(FitnessInputError, match="horarios"):
        save(repo, {**plan(), "timezone": "Europe/Madrid"})


def test_saving_and_replaying_preserves_full_metadata_without_completion(storage):
    repo, _, _ = storage
    result = save(repo)
    row = result["plan"]["sessions"][0]
    assert {key: row[key] for key in selected()} == selected()
    assert row["status"] == "planned" and row["completed_at"] is None
    assert result["progress"] == {"total": 1, "planned": 1, "completed": 0, "skipped": 0}
    assert save(repo)["idempotent_replay"] is True
    with pytest.raises(FitnessConflict):
        save(repo, profile_version=3)


def test_proposal_appends_without_overwriting_completed_legacy_or_training(storage):
    repo, base, _ = storage
    original = {"id": LEGACY, "program_id": "gentle-flexibility", "date": "2019-12-20", "time": "09:00"}
    first = save(repo, plan(original, selected()))
    completed = repo.set_status(MEMBER, LEGACY, "completed", expected_version=2, idempotency_key="complete-original")
    current = base.snapshot(MEMBER)
    detail = training_detail(PROGRAM)
    proposal = preview_training(current["profile"], PROGRAM, selected()["confirmed_requirements"],
        start_date="2026-09-14", existing_plan=completed["plan"], now=datetime(2026, 9, 14, 7, tzinfo=timezone.utc))
    assert proposal["sessions"]
    merged = inputs(completed)
    merged["sessions"].extend(proposal["sessions"])
    result = save(repo, merged, version=3, key="append-proposed-training")
    old = {row["id"]: row for row in completed["plan"]["sessions"]}
    assert all(next(row for row in result["plan"]["sessions"] if row["id"] == key) == value for key, value in old.items())
    assert result["progress"]["completed"] == 1
    assert all(row["content_version"] == detail["content_version"] for row in result["plan"]["sessions"] if row["program_id"] == PROGRAM)


def test_stale_profile_after_proposal_never_overwrites_existing_plan(storage):
    repo, base, _ = storage
    first = save(repo)
    base.save_profile(MEMBER, {**PROFILE, "session_minutes": 60}, expected_version=2, idempotency_key="availability-changed")
    candidate = inputs(first); candidate["sessions"].append(selected(id=str(uuid4()), date="2020-01-06"))
    with pytest.raises(FitnessConflict):
        save(repo, candidate, version=2, key="stale-proposal-save")
    assert repo.snapshot(MEMBER) == first


def test_unchanged_training_history_can_be_read_or_retitled_without_profile(storage):
    repo, base, _ = storage
    first = save(repo)
    base.set_consent(MEMBER, {**PROFILE_CONSENT, "granted": False}, expected_version=2, idempotency_key="withdraw-profile-only")
    update = inputs(first); update["title"] = "My retained history"
    result = save(repo, update, version=2, profile_version=None, key="rename-kept-history")
    assert result["plan"]["sessions"] == first["plan"]["sessions"]
    assert result["plan"]["title"] == "My retained history"


def test_pending_reschedule_preserves_metadata_but_uses_current_preferences(storage):
    repo, base, _ = storage
    first = save(repo)
    update = inputs(first); update["sessions"][0]["date"] = "2020-01-06"
    with pytest.raises(FitnessConflict):
        save(repo, update, version=2, profile_version=None, key="move-without-profile")
    moved = save(repo, update, version=2, key="move-pending-training")
    row = moved["plan"]["sessions"][0]
    for key in ("content_version", "confirmed_requirements", "reserved_minutes", "travel_minutes"):
        assert row[key] == selected()[key]
    assert row["date"] == "2020-01-06" and row["status"] == "planned"
    base.save_profile(MEMBER, {**PROFILE, "session_minutes": 60}, expected_version=2, idempotency_key="changed-after-moving")
    candidate = inputs(moved); candidate["sessions"][0]["date"] = "2020-01-08"
    with pytest.raises(FitnessInputError):
        save(repo, candidate, version=3, profile_version=3, key="old-time-metadata")
    assert repo.snapshot(MEMBER) == moved


def test_completed_training_metadata_cannot_be_changed_silently(storage):
    repo, _, _ = storage
    save(repo)
    completed = repo.set_status(MEMBER, SESSION, "completed", expected_version=2, idempotency_key="complete-training")
    for key, value in (("date", "2020-01-06"), ("reserved_minutes", 60), ("content_version", "other-v1")):
        changed = inputs(completed); changed["sessions"][0][key] = value
        with pytest.raises(FitnessInputError, match="realizada"):
            save(repo, changed, version=3, key="change-history-" + key)
    assert repo.snapshot(MEMBER) == completed


def test_records_block_rescheduling_and_removal_until_explicit_record_erasure(storage):
    repo, base, _ = storage
    saved = save(repo)
    logs = TrainingLogsRepository(base)
    logs.consent(MEMBER, LOG_CONSENT, expected_version=0, idempotency_key="record-consent")
    detail = training_detail(PROGRAM)
    log = {"session_id": SESSION, "program_id": PROGRAM, "content_version": detail["content_version"],
           "performed_on": "2020-01-03", "timezone": "UTC", "duration_minutes": None,
           "exercises": [{"exercise_id": item["id"], "skipped": False, "sets": [{"reps": 6}]}
                         for item in detail["exercises"] if item["phase"] == "work"]}
    logs.save(MEMBER, log, expected_version=1, idempotency_key="record-performed-sets")
    for candidate in (plan(selected(date="2020-01-06")), {**plan(), "sessions": []}):
        with pytest.raises(FitnessInputError, match="registro"):
            save(repo, candidate, version=2, key="change-recorded-plan")
    assert repo.snapshot(MEMBER) == saved
    logs.remove(MEMBER, SESSION, expected_version=2, idempotency_key="explicit-record-delete")
    assert save(repo, plan(selected(date="2020-01-06")), version=2, key="now-move-training")["plan"]["sessions"][0]["date"] == "2020-01-06"


def test_plan_metadata_validation_is_atomic_for_mixed_old_and_new_sessions(storage):
    repo, _, _ = storage
    first = save(repo)
    mixed = inputs(first); mixed["sessions"].append(selected(id=str(uuid4()), date="2020-01-04"))
    with pytest.raises(FitnessInputError, match="día"):
        save(repo, mixed, version=2, key="invalid-adjacent-day")
    assert repo.snapshot(MEMBER) == first
