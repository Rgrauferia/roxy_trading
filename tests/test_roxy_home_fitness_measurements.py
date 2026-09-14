"""Measurements contracts and synthetic transactions; real RLS tests are separate."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from roxy_os.fitness import measurements as module
from roxy_os.fitness.domain import FitnessInputError
from roxy_os.fitness.measurements import (Measurement, MeasurementConsent, MeasurementWrite,
    MeasurementConsentWrite, MeasurementDeleteWrite, MeasurementsRepository, _snapshot)
from roxy_os.fitness.repository import (PostgresFitnessRepository, FitnessConflict,
    FitnessConsentRequired, FitnessStorageUnavailable)
from test_roxy_home_fitness_repository import (DSN, SyntheticDB, SyntheticConnection,
    SyntheticCursor, CONSENT as PREFERENCES_CONSENT, PROFILE)

CONSENT = {"purpose": "fitness_measurements", "text_version": "fitness-measurements-v1", "granted": True}
RECORD_ID = "f83d9b44-eec5-4330-af30-1fa854efb338"
MEASUREMENT = {"id": RECORD_ID, "date": "2020-01-01", "timezone": "America/New_York",
               "weight": {"value": 160, "unit": "lb"}, "height": {"feet": 5, "inches": 8.5, "unit": "ft_in"}}


class MeasurementsSyntheticDB(SyntheticDB):
    def __init__(self):
        super().__init__()
        self.measurements_states, self.measurements_requests = {}, {}
        self.tables.extend({"relname": name, "relrowsecurity": True, "relforcerowsecurity": True,
                            "is_owner": False} for name in module.TABLES)

    def connect(self, _dsn):
        return MeasurementsSyntheticConnection(self)


class MeasurementsSyntheticConnection(SyntheticConnection):
    @contextmanager
    def transaction(self):
        with self.db.lock:
            saved = deepcopy((self.db.measurements_states, self.db.measurements_requests))
            try:
                with super().transaction():
                    yield
            except Exception:
                self.db.measurements_states, self.db.measurements_requests = saved
                raise

    def cursor(self):
        return MeasurementsSyntheticCursor(self)


class MeasurementsSyntheticCursor(SyntheticCursor):
    def execute(self, statement, params=()):
        sql = " ".join(statement.split())
        if "pg_advisory_xact_lock" in sql and params == ("roxy-home-measurements:" + self.conn.member,):
            self.conn.db.calls.append((sql, params))
            return
        if "roxy_home_fitness.measurements_" not in sql:
            return super().execute(statement, params)
        db = self.conn.db
        db.calls.append((sql, params))
        self.result = None
        if sql.startswith("INSERT INTO roxy_home_fitness.measurements_state"):
            assert params[0] == self.conn.member
            db.measurements_states.setdefault(params[0], {"version": 0, "measurements": [], "consent": None,
                                                         "updated_at": "2020-01-01T00:00:00Z"})
        elif sql.startswith("SELECT version, measurements, consent"):
            assert params[0] == self.conn.member
            self.result = deepcopy(db.measurements_states.get(params[0]))
        elif sql.startswith("UPDATE roxy_home_fitness.measurements_state SET version = version + 1"):
            assert params[0] == self.conn.member
            state = db.measurements_states[params[0]]
            state.update(version=state["version"] + 1, measurements=[], consent=None)
        elif sql.startswith("UPDATE roxy_home_fitness.measurements_state"):
            version, records, consent, member = params
            assert member == self.conn.member
            db.measurements_states[member].update(version=version, measurements=json.loads(records),
                                                 consent=json.loads(consent) if consent else None)
        elif sql.startswith("SELECT request_hash, response_version"):
            assert params[0] == self.conn.member
            self.result = deepcopy(db.measurements_requests.get(tuple(params)))
        elif sql.startswith("DELETE FROM roxy_home_fitness.measurements_idempotency"):
            assert params[0] == self.conn.member
            db.measurements_requests = {key: value for key, value in db.measurements_requests.items() if key[0] != params[0]}
        elif sql.startswith("INSERT INTO roxy_home_fitness.measurements_idempotency"):
            member, key, digest, version = params
            assert member == self.conn.member
            db.measurements_requests[member, key] = {"request_hash": digest, "response_version": version}
        else:
            raise AssertionError("Unexpected synthetic measurements SQL: " + sql)


@pytest.fixture
def storage():
    db = MeasurementsSyntheticDB()
    base = PostgresFitnessRepository(DSN, connection_factory=db.connect)
    return MeasurementsRepository(base), base, db


def adult(base, member="member-a", age="30_44"):
    base.set_consent(member, PREFERENCES_CONSENT, expected_version=0, idempotency_key="preference-consent-0001")
    return base.save_profile(member, {**PROFILE, "age_band": age}, expected_version=1, idempotency_key="adult-profile-0001")


def grant(repo, member="member-a", version=0):
    return repo.consent(member, CONSENT, expected_version=version, idempotency_key=f"measure-consent-{version}")


def save(repo, member="member-a", record=None, version=1, key=None):
    return repo.save(member, record or MEASUREMENT, expected_version=version, idempotency_key=key or f"measure-save-{version}")


@pytest.mark.parametrize("change", [
    {"id": "not-a-uuid"}, {"id": RECORD_ID.upper()}, {"date": "2020-1-01"}, {"date": "2020-02-30"},
    {"date": "2099-01-01"}, {"timezone": "Unknown/Zone"}, {"date": True},
    {"weight": None, "height": None}, {"weight": {"value": True, "unit": "kg"}},
    {"weight": {"value": "60", "unit": "kg"}}, {"weight": {"value": float("nan"), "unit": "kg"}},
    {"weight": {"value": float("inf"), "unit": "kg"}}, {"weight": {"value": -1, "unit": "kg"}},
    {"weight": {"value": 1000.1, "unit": "kg"}}, {"weight": {"value": 10**1000, "unit": "kg"}},
    {"weight": {"value": 100, "unit": "stone"}}, {"height": {"value": False, "unit": "cm"}},
    {"height": {"value": "175", "unit": "cm"}}, {"height": {"value": float("inf"), "unit": "cm"}},
    {"height": {"value": 29.9, "unit": "cm"}}, {"height": {"value": 300.1, "unit": "cm"}},
    {"height": {"feet": True, "inches": 0, "unit": "ft_in"}},
    {"height": {"feet": 5.5, "inches": 0, "unit": "ft_in"}},
    {"height": {"feet": 5, "inches": 12, "unit": "ft_in"}},
    {"height": {"feet": 5, "inches": "6", "unit": "ft_in"}},
    {"height": {"feet": 5, "inches": float("nan"), "unit": "ft_in"}},
    {"height": {"feet": 10, "inches": 0, "unit": "ft_in"}},
    {"height": {"feet": 0, "inches": 1, "unit": "ft_in"}},
    {"member_id": "member-b"}, {"bmi": 24}, {"calories": 2000}, {"note": "diagnosis"},
    {"weight_kg": 70}, {"recorded_at": "2020-01-01T00:00:00Z"},
])
def test_rejects_invalid_values_and_untrusted_derived_or_clinical_fields(change):
    with pytest.raises(ValidationError):
        Measurement.model_validate({**MEASUREMENT, **change})


def test_conversion_preserves_entered_units_and_optional_values():
    parsed = Measurement.model_validate(MEASUREMENT)
    assert parsed.canonical() == {"weight_kg": 72.574779, "height_cm": 173.99}
    assert parsed.model_dump()["weight"] == MEASUREMENT["weight"]
    assert parsed.model_dump()["height"] == MEASUREMENT["height"]
    height_only = Measurement.model_validate({**MEASUREMENT, "weight": None, "height": {"value": 175.125, "unit": "cm"}})
    assert height_only.canonical() == {"weight_kg": None, "height_cm": 175.125}
    weight_only = Measurement.model_validate({**MEASUREMENT, "height": None, "weight": {"value": 60.1234567, "unit": "kg"}})
    assert weight_only.canonical() == {"weight_kg": 60.123457, "height_cm": None}
    assert weight_only.weight.value == 60.1234567


@pytest.mark.parametrize("weight,height", [(1, 30), (1000, 300)])
def test_technical_bounds_are_inclusive_without_interpreting_measurements(weight, height):
    result = Measurement.model_validate({**MEASUREMENT, "weight": {"value": weight, "unit": "kg"},
                                        "height": {"value": height, "unit": "cm"}}).canonical()
    assert set(result) == {"weight_kg", "height_cm"}


def test_today_uses_declared_timezone_not_the_servers_calendar(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 15, 0, 30, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(module, "datetime", Clock)
    with pytest.raises(ValidationError, match="fecha anterior"):
        Measurement.model_validate({**MEASUREMENT, "date": "2026-09-15", "timezone": "America/New_York"})
    assert Measurement.model_validate({**MEASUREMENT, "date": "2026-09-15", "timezone": "Pacific/Kiritimati"})


@pytest.mark.parametrize("model,payload", [
    (MeasurementConsent, {**CONSENT, "text_version": "fitness-preferences-v1"}),
    (MeasurementConsent, {**CONSENT, "purpose": "fitness_preferences"}),
    (MeasurementConsent, {**CONSENT, "granted": 1}),
    (MeasurementWrite, {"expected_version": True, "measurement": MEASUREMENT}),
    (MeasurementConsentWrite, {"expected_version": "0", "consent": CONSENT}),
    (MeasurementDeleteWrite, {"expected_version": 0, "confirm_delete": 1}),
    (MeasurementDeleteWrite, {"expected_version": 0, "confirm_delete": False}),
])
def test_consent_and_write_envelopes_are_strict_and_separate(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_no_measurement_is_required_and_read_does_not_create_private_state(storage):
    repo, base, db = storage
    assert repo.snapshot("member-a") == {"version": 0, "measurements": [], "consent": None, "updated_at": None,
                                          "eligible": False, "eligibility_reason": "adult_profile_required"}
    assert not db.measurements_states
    adult(base)
    assert repo.snapshot("member-a")["eligible"] is True
    assert not db.measurements_states


@pytest.mark.parametrize("age", [None, "18_29", "30_44", "45_64", "65_plus"])
def test_adult_gate_uses_saved_preferences_in_the_same_transaction(storage, age):
    repo, base, db = storage
    adult(base, age=age)
    if age is None:
        with pytest.raises(FitnessInputError, match="18 años"):
            grant(repo)
        assert not db.measurements_states
    else:
        assert grant(repo)["eligible"] is True
        assert save(repo)["measurements"]


def test_unknown_profile_rejects_grant_and_save_but_can_delete_or_revoke(storage):
    repo, _, db = storage
    for action in (lambda: grant(repo), lambda: save(repo, version=0)):
        with pytest.raises(FitnessInputError, match="preferencias"):
            action()
    assert not db.measurements_states
    revoked = repo.consent("member-a", {**CONSENT, "granted": False}, expected_version=0, idempotency_key="withdraw-no-profile")
    assert revoked["consent"]["granted"] is False
    assert repo.delete_data("member-a", expected_version=1, idempotency_key="delete-no-profile")["measurements"] == []


def test_specific_consent_required_and_record_is_member_private(storage):
    repo, base, db = storage
    adult(base)
    with pytest.raises(FitnessConsentRequired):
        save(repo, version=0)
    assert not db.measurements_states
    grant(repo)
    saved = save(repo)
    assert saved["version"] == 2
    assert saved["measurements"][0]["height_cm"] == 173.99
    assert repo.snapshot("member-b")["measurements"] == []
    assert base.snapshot("member-a")["profile"]["without_weight_or_calories"] is True


def test_idempotency_replays_only_latest_unchanged_request(storage):
    repo, base, db = storage
    adult(base); grant(repo)
    saved = save(repo)
    replay = save(repo)
    assert replay["version"] == saved["version"] and replay["idempotent_replay"] is True
    assert len(replay["measurements"]) == 1
    with pytest.raises(FitnessConflict):
        save(repo, record={**MEASUREMENT, "weight": {"value": 165, "unit": "lb"}})
    assert set(next(iter(db.measurements_requests.values()))) == {"request_hash", "response_version"}


def test_edit_preserves_record_identity_and_creation_timestamp(storage):
    repo, base, _ = storage
    adult(base); grant(repo)
    original = save(repo)["measurements"][0]
    edited = save(repo, version=2, record={**MEASUREMENT, "date": "2020-01-02", "weight": None})
    row = edited["measurements"][0]
    assert len(edited["measurements"]) == 1 and row["id"] == RECORD_ID
    assert row["recorded_at"] == original["recorded_at"]
    assert datetime.fromisoformat(row["updated_at"]) >= datetime.fromisoformat(original["updated_at"])
    assert row["weight"] is row["weight_kg"] is None and row["date"] == "2020-01-02"


def test_different_uuid_same_date_is_not_a_duplicate_record(storage):
    repo, base, _ = storage
    adult(base); grant(repo); save(repo)
    with pytest.raises(FitnessInputError, match="esa fecha"):
        save(repo, version=2, record={**MEASUREMENT, "id": str(uuid4())})
    assert repo.snapshot("member-a")["version"] == 2
    second = save(repo, version=2, record={**MEASUREMENT, "id": str(uuid4()), "date": "2020-01-02"})
    assert [row["date"] for row in second["measurements"]] == ["2020-01-02", "2020-01-01"]


def test_record_limit_allows_edit_and_removal_then_new_measurement(storage):
    repo, base, db = storage
    adult(base); grant(repo); save(repo)
    stored = db.measurements_states["member-a"]
    first = stored["measurements"][0]
    stored["measurements"] = [{**first, "id": str(uuid4()), "date": (date(2020, 1, 1) + timedelta(days=index)).isoformat()} for index in range(500)]
    with pytest.raises(FitnessInputError, match="500"):
        save(repo, version=2, record={**MEASUREMENT, "id": str(uuid4()), "date": "2023-01-01"})
    edit = {key: stored["measurements"][0][key] for key in MEASUREMENT}
    assert len(save(repo, version=2, record={**edit, "weight": None})["measurements"]) == 500
    assert len(repo.remove("member-a", edit["id"], expected_version=3, idempotency_key="remove-for-space")["measurements"]) == 499
    assert len(save(repo, version=4, record={**MEASUREMENT, "id": str(uuid4()), "date": "2023-01-01"})["measurements"]) == 500


def test_withdrawal_and_delete_erase_values_and_invalidate_previous_requests(storage):
    repo, base, db = storage
    adult(base); grant(repo); save(repo)
    revoked = repo.consent("member-a", {**CONSENT, "granted": False}, expected_version=2, idempotency_key="revoke-measurements")
    assert revoked["measurements"] == [] and revoked["consent"]["granted"] is False
    assert len(db.measurements_requests) == 1
    with pytest.raises(FitnessConflict):
        save(repo)
    with pytest.raises(FitnessConsentRequired):
        save(repo, version=3)
    assert repo.delete_data("member-a", expected_version=3, idempotency_key="delete-measurements")["consent"] is None
    assert base.snapshot("member-a")["profile"]


def test_profile_revocation_blocks_new_measures_but_retains_export_and_delete(storage):
    repo, base, _ = storage
    adult(base); grant(repo); save(repo)
    base.set_consent("member-a", {**PREFERENCES_CONSENT, "granted": False}, expected_version=2, idempotency_key="withdraw-preferences")
    assert repo.snapshot("member-a")["eligible"] is False
    with pytest.raises(FitnessInputError, match="18 años"):
        save(repo, version=2)
    exported = repo.export_data("member-a")
    assert exported["data"]["measurements"][0]["weight_kg"] == 72.574779
    assert repo.remove("member-a", RECORD_ID, expected_version=2, idempotency_key="remove-without-profile")["measurements"] == []


def test_global_erasure_helper_is_atomic_and_invalidates_first_consent(storage):
    repo, base, _ = storage
    adult(base)
    with base._transaction("member-a") as cursor:
        MeasurementsRepository.erase_for_member(cursor, "member-a")
    assert repo.snapshot("member-a")["version"] == 1
    with pytest.raises(FitnessConflict):
        grant(repo)
    grant(repo, version=1); save(repo, version=2)
    before = repo.snapshot("member-a")
    with pytest.raises(RuntimeError):
        with base._transaction("member-a") as cursor:
            MeasurementsRepository.erase_for_member(cursor, "member-a")
            raise RuntimeError("synthetic downstream erase failure")
    assert repo.snapshot("member-a") == before


@pytest.mark.parametrize("flag,value", [("relrowsecurity", False), ("relforcerowsecurity", False), ("is_owner", True)])
def test_invalid_private_storage_configuration_fails_closed(storage, flag, value):
    repo, _, db = storage
    db.tables[-1][flag] = value
    with pytest.raises(FitnessStorageUnavailable):
        repo.snapshot("member-a")
    assert not db.measurements_states


def test_absent_migration_optional_discovery_and_partial_migration_fail_closed(storage):
    repo, base, db = storage
    db.tables = [row for row in db.tables if row["relname"] not in module.TABLES]
    with base._transaction("member-a") as cursor:
        assert MeasurementsRepository.available(cursor, required=False) is False
        MeasurementsRepository.erase_for_member(cursor, "member-a")
    with pytest.raises(FitnessStorageUnavailable):
        repo.snapshot("member-a")
    db.tables.append({"relname": "measurements_state", "relrowsecurity": True, "relforcerowsecurity": True, "is_owner": False})
    with base._transaction("member-a") as cursor:
        with pytest.raises(FitnessStorageUnavailable):
            MeasurementsRepository.available(cursor, required=False)


@pytest.mark.parametrize("change", [
    {"version": True}, {"version": -1}, {"version": 2**53}, {"measurements": None},
    {"consent": None}, {"consent": {**CONSENT, "granted": False, "recorded_at": "2020-01-01T00:00:00Z"}},
    {"updated_at": "2020-01-01"},
])
def test_corruption_does_not_become_empty_success(storage, change):
    repo, base, db = storage
    adult(base); grant(repo); save(repo)
    db.measurements_states["member-a"].update(change)
    with pytest.raises(FitnessStorageUnavailable):
        repo.snapshot("member-a")


@pytest.mark.parametrize("field,value", [("weight_kg", 2), ("height_cm", float("nan")),
    ("recorded_at", "2020-01-01"), ("updated_at", "1900-01-01T00:00:00Z")])
def test_corrupt_normalization_or_timestamps_are_rejected(storage, field, value):
    repo, base, db = storage
    adult(base); grant(repo); save(repo)
    db.measurements_states["member-a"]["measurements"][0][field] = value
    with pytest.raises(FitnessStorageUnavailable):
        repo.snapshot("member-a")


def test_remove_unknown_or_other_member_id_never_modifies_data(storage):
    repo, base, _ = storage
    adult(base); grant(repo); save(repo)
    with pytest.raises(FitnessInputError):
        repo.remove("member-b", RECORD_ID, expected_version=0, idempotency_key="cross-member-remove")
    with pytest.raises(FitnessInputError):
        repo.remove("member-a", "not-a-uuid", expected_version=2, idempotency_key="invalid-id-remove")
    assert repo.snapshot("member-a")["version"] == 2


def test_global_foundation_export_and_erasure_include_measurements_when_integrated(storage):
    repo, base, _ = storage
    adult(base); grant(repo); save(repo)
    exported = base.export_data("member-a")
    # Root integrates these hooks in repository.py in the same release.
    assert exported["measurements"]["measurements"][0]["id"] == RECORD_ID
    base.delete_data("member-a", expected_version=2, idempotency_key="delete-all-fitness")
    assert repo.snapshot("member-a")["measurements"] == []
    assert repo.snapshot("member-a")["consent"] is None


def test_mutations_share_foundation_then_measurements_lock_order(storage):
    repo, base, db = storage
    adult(base)
    db.calls.clear()
    grant(repo)
    locks = [params[0] for sql, params in db.calls if "pg_advisory_xact_lock" in sql]
    assert locks == ["roxy-home-fitness:member-a", "roxy-home-measurements:member-a"]
