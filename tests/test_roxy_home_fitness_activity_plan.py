"""Private agenda contracts with synthetic SQL; real PG evidence is separate."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from roxy_os.fitness.activity_plan import (
    ActivityPlan, ActivityConsent, ActivityPlanRepository, session_instant,
)
from roxy_os.fitness.repository import PostgresFitnessRepository, FitnessStorageUnavailable, FitnessConsentRequired, FitnessConflict
from roxy_os.fitness.domain import FitnessInputError
from test_roxy_home_fitness_repository import SyntheticDB, DSN

CONSENT = {"purpose": "fitness_activity_plan", "text_version": "fitness-activity-plan-v1", "granted": True}
SESSION_ID = "4c9c7b50-614c-4350-b2e1-454f324e037b"
PLAN = {"title": "Mi semana", "timezone": "America/New_York", "sessions": [
    {"id": SESSION_ID, "program_id": "gentle-strength", "date": "2026-09-01", "time": "09:00"}]}


@pytest.fixture
def storage():
    db = SyntheticDB()
    db.tables.extend({"relname": name, "relrowsecurity": True, "relforcerowsecurity": True, "is_owner": False} for name in ("activity_plan_state", "activity_plan_idempotency"))
    base = PostgresFitnessRepository(DSN, connection_factory=db.connect)
    return ActivityPlanRepository(base), base, db


def grant(repo, member="member-a", version=0):
    return repo.consent(member, CONSENT, expected_version=version, idempotency_key=f"consent-{version:04}")


def save(repo, member="member-a", plan=None, version=1):
    return repo.save(member, plan or PLAN, expected_version=version, idempotency_key=f"save-plan-{version:04}")


@pytest.mark.parametrize("change", [
    {"title": " "}, {"title": "x" * 101}, {"timezone": "not-a-zone"},
    {"sessions": [{**PLAN["sessions"][0], "program_id": "custom-doctor-plan"}]},
    {"sessions": [{**PLAN["sessions"][0], "status": "completed"}]},
    {"sessions": [{**PLAN["sessions"][0], "id": "arbitrary"}]},
    {"sessions": [{**PLAN["sessions"][0], "time": "25:01"}]},
    {"sessions": [{**PLAN["sessions"][0], "date": "2026-02-30"}]},
    {"sessions": PLAN["sessions"] * 2},
    {"member_id": "member-b"},
])
def test_contract_rejects_untrusted_or_invalid_values(change):
    with pytest.raises(ValidationError):
        ActivityPlan.model_validate({**PLAN, **change})


@pytest.mark.parametrize("day,clock", [("2026-03-08", "02:30"), ("2026-11-01", "01:30")])
def test_nonexistent_and_ambiguous_dst_hours_require_new_choice(day, clock):
    with pytest.raises(ValidationError, match="cambio de horario"):
        ActivityPlan.model_validate({**PLAN, "sessions": [{**PLAN["sessions"][0], "date": day, "time": clock}]})


def test_exact_instant_preserves_chosen_local_time():
    assert session_instant("2026-09-01", "09:00", "America/New_York").isoformat() == "2026-09-01T13:00:00+00:00"
    assert session_instant("2026-01-01", "09:00", "America/New_York").isoformat() == "2026-01-01T14:00:00+00:00"


def test_consent_is_separate_from_preferences():
    with pytest.raises(ValidationError):
        ActivityConsent.model_validate({"purpose": "fitness_preferences", "text_version": "fitness-preferences-v1", "granted": True})


def test_missing_migration_or_rls_never_saves(storage):
    repo, base, db = storage
    db.tables = [row for row in db.tables if not row["relname"].startswith("activity_plan")]
    with pytest.raises(FitnessStorageUnavailable):
        repo.snapshot("member-a")
    assert "activity_plan" not in base.export_data("member-a")
    assert not db.plan_states


@pytest.mark.parametrize("field,value", [("relrowsecurity", False), ("relforcerowsecurity", False), ("is_owner", True)])
def test_agenda_tables_must_remain_private(storage, field, value):
    repo, _, db = storage
    db.tables[-1][field] = value
    with pytest.raises(FitnessStorageUnavailable):
        grant(repo)
    assert not db.plan_states


def test_new_plan_requires_consent_and_real_program(storage):
    repo, _, db = storage
    with pytest.raises(FitnessConsentRequired):
        save(repo, version=0)
    assert not db.plan_states
    grant(repo)
    saved = save(repo)
    assert saved["version"] == 2
    assert saved["progress"] == {"total": 1, "planned": 1, "completed": 0, "skipped": 0}
    assert saved["plan"]["sessions"][0]["starts_at"] == "2026-09-01T13:00:00+00:00"
    assert repo.snapshot("member-b")["plan"] is None


def test_progress_comes_only_from_explicit_marks_and_can_be_undone(storage):
    repo, _, _ = storage
    grant(repo); save(repo)
    done = repo.set_status("member-a", SESSION_ID, "completed", expected_version=2, idempotency_key="mark-done-0001")
    assert done["progress"]["completed"] == 1
    assert datetime.fromisoformat(done["plan"]["sessions"][0]["completed_at"]).tzinfo is not None
    replay = repo.set_status("member-a", SESSION_ID, "completed", expected_version=2, idempotency_key="mark-done-0001")
    assert replay["version"] == done["version"] and replay["idempotent_replay"]
    skipped = repo.set_status("member-a", SESSION_ID, "skipped", expected_version=3, idempotency_key="mark-skip-0001")
    assert skipped["progress"]["skipped"] == 1 and skipped["progress"]["completed"] == 0
    assert skipped["plan"]["sessions"][0]["completed_at"] is None
    undone = repo.set_status("member-a", SESSION_ID, "planned", expected_version=4, idempotency_key="undo-status-0001")
    assert undone["progress"]["planned"] == 1


def test_cannot_mark_future_activity_completed(storage):
    repo, _, _ = storage
    grant(repo)
    save(repo, plan={**PLAN, "sessions": [{**PLAN["sessions"][0], "date": "2100-01-01"}]})
    with pytest.raises(FitnessInputError, match="futura"):
        repo.set_status("member-a", SESSION_ID, "completed", expected_version=2, idempotency_key="future-mark-0001")
    assert repo.snapshot("member-a")["version"] == 2


def test_editing_plan_preserves_done_only_for_unchanged_activity(storage):
    repo, _, _ = storage
    grant(repo); save(repo)
    repo.set_status("member-a", SESSION_ID, "completed", expected_version=2, idempotency_key="mark-done-0001")
    same = save(repo, version=3)
    assert same["progress"]["completed"] == 1
    with pytest.raises(FitnessInputError, match="mover ni quitar"):
        save(repo, version=4, plan={**PLAN, "sessions": [{**PLAN["sessions"][0], "time": "10:00"}]})
    assert repo.snapshot("member-a")["version"] == 4
    assert repo.snapshot("member-a")["progress"]["completed"] == 1
    repo.set_status("member-a", SESSION_ID, "planned", expected_version=4, idempotency_key="explicit-undo-0001")
    moved = save(repo, version=5, plan={**PLAN, "sessions": [{**PLAN["sessions"][0], "time": "10:00"}]})
    assert moved["progress"]["planned"] == 1 and moved["progress"]["completed"] == 0


def test_stale_writes_and_cross_member_marks_cannot_change_records(storage):
    repo, _, _ = storage
    grant(repo); save(repo); grant(repo, "member-b")
    with pytest.raises(FitnessConflict):
        repo.save("member-a", PLAN, expected_version=1, idempotency_key="different-stale-request")
    with pytest.raises(FitnessInputError):
        repo.set_status("member-b", SESSION_ID, "completed", expected_version=1, idempotency_key="cross-mark-0001")
    assert repo.snapshot("member-a")["progress"]["planned"] == 1


def test_revoke_erases_agenda_and_blocks_old_requests(storage):
    repo, _, _ = storage
    grant(repo); save(repo)
    revoked = repo.consent("member-a", {**CONSENT, "granted": False}, expected_version=2, idempotency_key="revoke-plan-0001")
    assert revoked["plan"] is None and revoked["progress"]["total"] == 0
    with pytest.raises(FitnessConflict):
        save(repo)
    with pytest.raises(FitnessConsentRequired):
        save(repo, version=3)


def test_independent_export_delete_and_global_export_delete_are_complete(storage):
    repo, base, _ = storage
    grant(repo); save(repo); grant(repo, "member-b"); save(repo, "member-b")
    assert repo.export_data("member-a")["data"]["plan"]
    exported = base.export_data("member-a")
    assert exported["activity_plan"]["plan"]
    base.delete_data("member-a", expected_version=0, idempotency_key="global-delete-0001")
    assert repo.snapshot("member-a")["plan"] is None
    assert repo.snapshot("member-a")["consent"] is None
    assert repo.snapshot("member-b")["plan"]
    with pytest.raises(FitnessConflict):
        save(repo)
    result = repo.delete_data("member-b", expected_version=2, idempotency_key="plan-delete-0001")
    assert result["plan"] is result["consent"] is None


def test_corrupt_state_never_becomes_empty_success(storage):
    repo, _, db = storage
    grant(repo); save(repo)
    db.plan_states["member-a"]["plan"]["sessions"][0]["status"] = "guessed"
    with pytest.raises(FitnessStorageUnavailable):
        repo.snapshot("member-a")


@pytest.mark.parametrize("status", ["completed", "skipped"])
@pytest.mark.parametrize("edit", ["timezone", "remove", "program", "date", "time"])
def test_saving_draft_cannot_silently_rewrite_history(storage, status, edit):
    repo, _, _ = storage
    grant(repo); save(repo)
    repo.set_status("member-a", SESSION_ID, status, expected_version=2, idempotency_key="record-status-0001")
    before = repo.snapshot("member-a")
    changed = deepcopy(PLAN)
    if edit == "timezone":
        changed["timezone"] = "Europe/Madrid"
    elif edit == "remove":
        changed["sessions"] = []
    else:
        changed["sessions"][0][edit if edit != "program" else "program_id"] = {
            "program": "gentle-balance", "date": "2026-09-02", "time": "10:00"}[edit]
    with pytest.raises(FitnessInputError):
        save(repo, version=3, plan=changed)
    assert repo.snapshot("member-a") == before


def test_append_keeps_history_and_pending_can_be_rescheduled(storage):
    repo, _, _ = storage
    grant(repo); save(repo)
    repo.set_status("member-a", SESSION_ID, "completed", expected_version=2, idempotency_key="record-status-0001")
    historical = repo.snapshot("member-a")["plan"]["sessions"][0]
    new = {**PLAN["sessions"][0], "id": str(uuid4()), "date": "2026-09-20"}
    appended = save(repo, version=3, plan={**PLAN, "sessions": [*PLAN["sessions"], new]})
    assert appended["plan"]["sessions"][0] == historical
    pending_moved = {**new, "time": "11:00"}
    rescheduled = save(repo, version=4, plan={**PLAN, "sessions": [*PLAN["sessions"], pending_moved]})
    assert rescheduled["plan"]["sessions"][0] == historical
    assert rescheduled["plan"]["sessions"][1]["time"] == "11:00"
    assert rescheduled["progress"] == {"total": 2, "completed": 1, "planned": 1, "skipped": 0}


def test_global_erasure_before_first_agenda_rejects_inflight_initial_consent(storage):
    repo, base, _ = storage
    assert repo.snapshot("member-a")["version"] == 0
    base.delete_data("member-a", expected_version=0, idempotency_key="erase-before-first-consent")
    erased = repo.snapshot("member-a")
    assert erased["version"] == 1 and erased["plan"] is erased["consent"] is None
    with pytest.raises(FitnessConflict):
        grant(repo, version=0)
    assert repo.snapshot("member-a") == erased
    # A new decision after refreshing remains possible.
    assert grant(repo, version=1)["consent"]["granted"] is True
