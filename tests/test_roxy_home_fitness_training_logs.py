"""Private manual training records: strict input and atomic synthetic storage."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from roxy_os.fitness import training_logs as module
from roxy_os.fitness.activity_plan import ActivityPlanRepository, TABLES as PLAN_TABLES
from roxy_os.fitness.domain import FitnessInputError
from roxy_os.fitness.training_logs import (TrainingLog, TrainingSet, TrainingLogWrite,
    TrainingLogConsent, TrainingLogConsentWrite, TrainingLogDeleteWrite, TrainingLogsRepository)
from roxy_os.fitness.repository import (PostgresFitnessRepository, FitnessConflict,
    FitnessConsentRequired, FitnessStorageUnavailable)
from test_roxy_home_fitness_repository import DSN, SyntheticDB, SyntheticConnection, SyntheticCursor
from test_roxy_home_fitness_measurements import adult

CONSENT = {"purpose": "fitness_training_logs", "text_version": "fitness-training-logs-v1", "granted": True}
PLAN_CONSENT = {"purpose": "fitness_activity_plan", "text_version": "fitness-activity-plan-v1", "granted": True}
SESSION_ID = "fc636e4e-3f74-43db-9fdf-0bd2b25c4d67"
PLAN = {"title": "Synthetic training", "timezone": "UTC", "sessions": [
    {"id": SESSION_ID, "program_id": "gentle-strength", "date": "2020-01-01", "time": "10:00"}]}
LOG = {"session_id": SESSION_ID, "program_id": "gentle-strength", "content_version": "test-v1",
       "performed_on": "2020-01-01", "timezone": "UTC", "duration_minutes": 20,
       "exercises": [{"exercise_id": "test-reps", "skipped": False,
                      "sets": [{"reps": 8, "seconds": None, "load": {"value": 10, "unit": "lb"}}]},
                     {"exercise_id": "test-seconds", "skipped": True, "sets": []}]}
DETAIL = {"content_version": "test-v1", "exercises": [
    {"id": "test-reps", "phase": "work", "tracking_unit": "reps", "load_recordable": True},
    {"id": "test-seconds", "phase": "work", "tracking_unit": "seconds", "load_recordable": False},
    {"id": "test-warmup", "phase": "warmup", "tracking_unit": "seconds"}]}


class LogsSyntheticDB(SyntheticDB):
    def __init__(self):
        super().__init__()
        self.log_states, self.log_requests = {}, {}
        self.tables.extend({"relname": name, "relrowsecurity": True, "relforcerowsecurity": True,
                            "is_owner": False} for name in module.TABLES | PLAN_TABLES)

    def connect(self, _dsn):
        return LogsSyntheticConnection(self)


class LogsSyntheticConnection(SyntheticConnection):
    @contextmanager
    def transaction(self):
        with self.db.lock:
            saved = deepcopy((self.db.log_states, self.db.log_requests))
            try:
                with super().transaction():
                    yield
            except Exception:
                self.db.log_states, self.db.log_requests = saved
                raise

    def cursor(self):
        return LogsSyntheticCursor(self)


class LogsSyntheticCursor(SyntheticCursor):
    def execute(self, statement, params=()):
        sql = " ".join(statement.split())
        if "pg_advisory_xact_lock" in sql and params == ("roxy-home-training-logs:" + self.conn.member,):
            self.conn.db.calls.append((sql, params))
            return
        if "roxy_home_fitness.training_logs_" not in sql:
            return super().execute(statement, params)
        db = self.conn.db
        db.calls.append((sql, params)); self.result = None
        if sql.startswith("INSERT INTO roxy_home_fitness.training_logs_state"):
            assert params[0] == self.conn.member
            db.log_states.setdefault(params[0], {"version": 0, "logs": [], "consent": None,
                                                 "updated_at": "2020-01-01T00:00:00Z"})
        elif sql.startswith("SELECT version, logs, consent"):
            assert params[0] == self.conn.member
            self.result = deepcopy(db.log_states.get(params[0]))
        elif sql.startswith("UPDATE roxy_home_fitness.training_logs_state SET version = version + 1"):
            assert params[0] == self.conn.member
            state = db.log_states[params[0]]
            state.update(version=state["version"] + 1, logs=[], consent=None)
        elif sql.startswith("UPDATE roxy_home_fitness.training_logs_state"):
            version, records, consent, member = params
            assert member == self.conn.member
            db.log_states[member].update(version=version, logs=json.loads(records),
                                         consent=json.loads(consent) if consent else None)
        elif sql.startswith("SELECT request_hash, response_version"):
            assert params[0] == self.conn.member
            self.result = deepcopy(db.log_requests.get(tuple(params)))
        elif sql.startswith("DELETE FROM roxy_home_fitness.training_logs_idempotency"):
            assert params[0] == self.conn.member
            db.log_requests = {key: value for key, value in db.log_requests.items() if key[0] != params[0]}
        elif sql.startswith("INSERT INTO roxy_home_fitness.training_logs_idempotency"):
            member, key, digest, version = params
            assert member == self.conn.member
            db.log_requests[member, key] = {"request_hash": digest, "response_version": version}
        else:
            raise AssertionError("Unexpected synthetic training SQL: " + sql)


@pytest.fixture
def content(monkeypatch):
    def detail(program):
        if program != LOG["program_id"]:
            raise FitnessInputError("Unknown synthetic program")
        return deepcopy(DETAIL)
    monkeypatch.setattr(module, "_content_detail", detail)
    return detail


@pytest.fixture
def storage(content):
    db = LogsSyntheticDB()
    base = PostgresFitnessRepository(DSN, connection_factory=db.connect)
    return TrainingLogsRepository(base), base, db


def prepare(base, member="member-a"):
    adult(base, member)
    planner = ActivityPlanRepository(base)
    planner.consent(member, PLAN_CONSENT, expected_version=0, idempotency_key="plan-consent")
    planner.save(member, PLAN, expected_version=1, idempotency_key="plan-save")
    return planner


def grant(repo, member="member-a", version=0):
    return repo.consent(member, CONSENT, expected_version=version, idempotency_key=f"training-consent-{version}")


def save(repo, member="member-a", payload=None, version=1, key=None):
    return repo.save(member, payload or LOG, expected_version=version, idempotency_key=key or f"training-save-{version}")


@pytest.mark.parametrize("change", [
    {"session_id": "bad"}, {"session_id": SESSION_ID.upper()}, {"performed_on": "2020-1-1"},
    {"performed_on": "2020-02-30"}, {"performed_on": "2099-01-01"}, {"timezone": "Bad/Zone"},
    {"program_id": "../unsafe"}, {"content_version": ""}, {"member_id": "other"}, {"calories": 50},
    {"duration_minutes": True}, {"duration_minutes": "20"}, {"duration_minutes": 0},
    {"duration_minutes": float("nan")}, {"duration_minutes": float("inf")},
    {"duration_minutes": 1441}, {"duration_minutes": 10**1000}, {"exercises": []},
    {"exercises": [LOG["exercises"][0]] * 2},
    {"exercises": [{"exercise_id": "test-reps", "skipped": False, "sets": []}]},
    {"exercises": [{"exercise_id": "test-reps", "skipped": True, "sets": [{"reps": 1}]}]},
    {"exercises": [{"exercise_id": "test-reps", "skipped": True, "sets": []}]},
])
def test_invalid_or_inferred_log_fields_rejected(change):
    with pytest.raises(ValidationError):
        TrainingLog.model_validate({**LOG, **change})


@pytest.mark.parametrize("series", [
    {}, {"reps": 1, "seconds": 5}, {"reps": True}, {"reps": "8"}, {"reps": 8.5},
    {"reps": 0}, {"reps": -1}, {"reps": 10001}, {"seconds": True}, {"seconds": "10"},
    {"seconds": 0}, {"seconds": float("nan")}, {"seconds": float("inf")}, {"seconds": 86401},
    {"reps": 8, "load": {"value": True, "unit": "kg"}},
    {"reps": 8, "load": {"value": "10", "unit": "kg"}},
    {"reps": 8, "load": {"value": -1, "unit": "kg"}},
    {"reps": 8, "load": {"value": float("nan"), "unit": "kg"}},
    {"reps": 8, "load": {"value": 2501, "unit": "kg"}},
    {"reps": 8, "load": {"value": 20, "unit": "stone"}},
    {"reps": 8, "load_kg": 10}, {"reps": 8, "calories": 100},
])
def test_strict_series_without_zero_or_dual_axes(series):
    with pytest.raises(ValidationError):
        TrainingSet.model_validate(series)


@pytest.mark.parametrize("model,payload", [
    (TrainingLogConsent, {**CONSENT, "purpose": "fitness_preferences"}),
    (TrainingLogConsent, {**CONSENT, "text_version": "fitness-preferences-v1"}),
    (TrainingLogConsent, {**CONSENT, "granted": 1}),
    (TrainingLogWrite, {"expected_version": True, "log": LOG}),
    (TrainingLogConsentWrite, {"expected_version": "0", "consent": CONSENT}),
    (TrainingLogDeleteWrite, {"expected_version": 0, "confirm_delete": 1}),
    (TrainingLogDeleteWrite, {"expected_version": 0, "confirm_delete": False}),
])
def test_write_and_consent_envelopes_are_strict(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_optional_fields_stay_absent_and_load_units_preserved():
    raw = deepcopy(LOG)
    raw["duration_minutes"] = None
    raw["exercises"][0]["sets"] = [{"reps": 1, "load": None}, {"reps": 2, "load": {"value": 0, "unit": "kg"}}]
    result = TrainingLog.model_validate(raw).model_dump(mode="json")
    assert result["duration_minutes"] is None
    assert result["exercises"][0]["sets"][0]["load"] is None
    assert result["exercises"][0]["sets"][1]["load"]["value"] == 0


def test_read_requires_no_records_or_consent_and_creates_nothing(storage):
    repo, base, db = storage
    result = repo.snapshot("member-a")
    assert result["logs"] == [] and result["eligible"] is False and result["version"] == 0
    assert not db.log_states
    adult(base)
    assert repo.snapshot("member-a")["eligible"] is True and not db.log_states


@pytest.mark.parametrize("age", [None, "18_29", "30_44", "45_64", "65_plus"])
def test_saved_adult_profile_gate(storage, age):
    repo, base, db = storage
    adult(base, age=age)
    if age is None:
        with pytest.raises(FitnessInputError, match="18 años"):
            grant(repo)
        assert not db.log_states
    else:
        assert grant(repo)["eligible"] is True


def test_consent_is_required_and_saving_does_not_complete_agenda(storage):
    repo, base, db = storage
    planner = prepare(base)
    with pytest.raises(FitnessConsentRequired):
        save(repo, version=0)
    grant(repo)
    before = planner.snapshot("member-a")
    result = save(repo)
    assert result["version"] == 2 and len(result["logs"]) == 1
    assert planner.snapshot("member-a") == before
    row = result["logs"][0]
    assert row["exercises"][0]["sets"][0]["load_kg"] == 4.535924
    assert row["exercises"][0]["sets"][0]["load"] == LOG["exercises"][0]["sets"][0]["load"]
    assert row["exercises"][1] == LOG["exercises"][1]
    assert row["scheduled_date"] == "2020-01-01"
    assert repo.snapshot("member-b")["logs"] == []


def test_cannot_register_unknown_other_member_or_future_session(storage):
    repo, base, _ = storage
    prepare(base); grant(repo)
    for change in ({"session_id": str(uuid4())}, {"program_id": "another"}, {"timezone": "Europe/Madrid"}, {"performed_on": "2019-12-31"}):
        with pytest.raises(FitnessInputError):
            save(repo, payload={**LOG, **change})
    adult(base, "member-b"); grant(repo, "member-b")
    with pytest.raises(FitnessInputError, match="no existe"):
        save(repo, "member-b")
    planner = ActivityPlanRepository(base)
    future = {**PLAN, "sessions": [{**PLAN["sessions"][0], "date": (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()}]}
    planner.save("member-a", future, expected_version=2, idempotency_key="future-plan")
    with pytest.raises(FitnessInputError):
        save(repo)


def test_content_version_exact_axes_and_all_work_exercises_required(storage):
    repo, base, _ = storage
    prepare(base); grant(repo)
    with pytest.raises(FitnessConflict, match="cambiaron"):
        save(repo, payload={**LOG, "content_version": "stale-v0"})
    with pytest.raises(FitnessInputError, match="incluir"):
        save(repo, payload={**LOG, "exercises": [LOG["exercises"][0]]})
    raw = deepcopy(LOG)
    raw["exercises"][0]["sets"] = [{"seconds": 8}]
    with pytest.raises(FitnessInputError, match="unidades"):
        save(repo, payload=raw)
    raw = deepcopy(LOG)
    raw["exercises"][1] = {"exercise_id": "test-seconds", "skipped": False, "sets": [{"seconds": 15}]}
    assert save(repo, payload=raw)["logs"][0]["exercises"][1]["sets"][0]["seconds"] == 15


def test_idempotency_latest_only_and_edit_preserves_creation(storage):
    repo, base, db = storage
    prepare(base); grant(repo)
    row = save(repo)["logs"][0]
    assert save(repo)["idempotent_replay"] is True
    with pytest.raises(FitnessConflict):
        save(repo, payload={**LOG, "duration_minutes": 22})
    edited = save(repo, payload={**LOG, "duration_minutes": None}, version=2)
    assert len(edited["logs"]) == 1 and edited["logs"][0]["recorded_at"] == row["recorded_at"]
    assert edited["logs"][0]["duration_minutes"] is None
    assert set(next(iter(db.log_requests.values()))) == {"request_hash", "response_version"}
    with pytest.raises(FitnessConflict):
        save(repo)


def test_omitting_more_than_twenty_sets_is_rejected():
    raw = deepcopy(LOG)
    raw["exercises"][0]["sets"] = [{"reps": 1}] * 21
    with pytest.raises(ValidationError):
        TrainingLog.model_validate(raw)


def test_profile_withdrawal_blocks_new_logs_but_export_and_delete_work(storage):
    from test_roxy_home_fitness_measurements import PREFERENCES_CONSENT
    repo, base, _ = storage
    prepare(base); grant(repo); save(repo)
    base.set_consent("member-a", {**PREFERENCES_CONSENT, "granted": False}, expected_version=2, idempotency_key="withdraw-profile")
    assert repo.snapshot("member-a")["eligible"] is False
    with pytest.raises(FitnessInputError, match="18 años"):
        save(repo, version=2)
    assert repo.export_data("member-a")["data"]["logs"]
    assert repo.remove("member-a", SESSION_ID, expected_version=2, idempotency_key="delete-one-log")["logs"] == []


def test_revoke_and_delete_clear_records_and_stale_replays(storage):
    repo, base, _ = storage
    prepare(base); grant(repo); save(repo)
    revoked = repo.consent("member-a", {**CONSENT, "granted": False}, expected_version=2, idempotency_key="withdraw-training")
    assert revoked["logs"] == [] and revoked["consent"]["granted"] is False
    with pytest.raises(FitnessConflict):
        save(repo)
    assert repo.delete_data("member-a", expected_version=3, idempotency_key="delete-training")["consent"] is None
    assert ActivityPlanRepository(base).snapshot("member-a")["plan"]


def test_same_transaction_erase_tombstone_and_rollback(storage):
    repo, base, _ = storage
    prepare(base)
    with base._transaction("member-a") as cursor:
        TrainingLogsRepository.erase_for_member(cursor, "member-a")
    assert repo.snapshot("member-a")["version"] == 1
    with pytest.raises(FitnessConflict):
        grant(repo)
    grant(repo, version=1); save(repo, version=2)
    before = repo.snapshot("member-a")
    with pytest.raises(RuntimeError):
        with base._transaction("member-a") as cursor:
            TrainingLogsRepository.erase_for_member(cursor, "member-a")
            raise RuntimeError("synthetic rollback")
    assert repo.snapshot("member-a") == before


def test_plan_guard_protects_registered_session_but_allows_unrelated_changes(storage):
    repo, base, _ = storage
    prepare(base); grant(repo); save(repo)
    with base._transaction("member-a") as cursor:
        TrainingLogsRepository.guard_plan_change(cursor, "member-a", {**PLAN, "title": "New title"})
    for change in ({"sessions": []}, {"timezone": "Europe/Madrid"},
                   {"sessions": [{**PLAN["sessions"][0], "time": "11:00"}]},
                   {"sessions": [{**PLAN["sessions"][0], "program_id": "gentle-balance"}]}):
        with base._transaction("member-a") as cursor:
            with pytest.raises(FitnessInputError, match="registro"):
                TrainingLogsRepository.guard_plan_change(cursor, "member-a", {**PLAN, **change})
    repo.remove("member-a", SESSION_ID, expected_version=2, idempotency_key="delete-to-reschedule")
    with base._transaction("member-a") as cursor:
        TrainingLogsRepository.guard_plan_change(cursor, "member-a", {**PLAN, "sessions": []})


@pytest.mark.parametrize("flag", ["relrowsecurity", "relforcerowsecurity", "is_owner"])
def test_rls_or_role_regression_fails_closed(storage, flag):
    repo, _, db = storage
    row = next(item for item in db.tables if item["relname"] == "training_logs_state")
    row[flag] = flag == "is_owner"
    with pytest.raises(FitnessStorageUnavailable):
        repo.snapshot("member-a")


def test_optional_migration_absent_and_partial_fail_closed(storage):
    repo, base, db = storage
    db.tables = [item for item in db.tables if item["relname"] not in module.TABLES]
    with base._transaction("member-a") as cursor:
        assert TrainingLogsRepository.available(cursor, required=False) is False
    with pytest.raises(FitnessStorageUnavailable):
        repo.snapshot("member-a")
    db.tables.append({"relname": "training_logs_state", "relrowsecurity": True, "relforcerowsecurity": True, "is_owner": False})
    with base._transaction("member-a") as cursor:
        with pytest.raises(FitnessStorageUnavailable):
            TrainingLogsRepository.available(cursor, required=False)


@pytest.mark.parametrize("field,value", [("version", True), ("version", -1), ("version", 2**53),
    ("consent", None), ("logs", None), ("updated_at", "2020-01-01")])
def test_corruption_fails_closed(storage, field, value):
    repo, base, db = storage
    prepare(base); grant(repo); save(repo)
    db.log_states["member-a"][field] = value
    with pytest.raises(FitnessStorageUnavailable):
        repo.snapshot("member-a")


def test_normalized_load_tampering_fails_closed(storage):
    repo, base, db = storage
    prepare(base); grant(repo); save(repo)
    db.log_states["member-a"]["logs"][0]["exercises"][0]["sets"][0]["load_kg"] = 999
    with pytest.raises(FitnessStorageUnavailable):
        repo.snapshot("member-a")


def test_locks_follow_foundation_agenda_then_training(storage):
    repo, base, db = storage
    adult(base); db.calls.clear()
    grant(repo)
    locks = [params[0] for sql, params in db.calls if "pg_advisory_xact_lock" in sql]
    assert locks == ["roxy-home-fitness:member-a", "roxy-home-activity-plan:member-a", "roxy-home-training-logs:member-a"]
