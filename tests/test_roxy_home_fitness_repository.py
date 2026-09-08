"""Synthetic SQL-contract double only: NOT a real PostgreSQL/RLS verification."""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import RLock
from concurrent.futures import ThreadPoolExecutor
import json
import sys
import types

import pytest

from roxy_os.fitness.domain import FitnessInputError
from roxy_os.fitness.repository import FitnessConflict, FitnessConsentRequired, FitnessStorageUnavailable, PostgresFitnessRepository

DSN = "postgresql://synthetic:never-real@example.invalid/home_test"
CONSENT = {"purpose": "fitness_preferences", "text_version": "fitness-preferences-v1", "granted": True}
PROFILE = {"timezone": "America/New_York", "age_band": "30_44", "primary_goal": "fitness_habit"}


def test_real_driver_parameters_cannot_downgrade_tls(monkeypatch):
    """Driver call contract only, not a real certificate or database test."""
    calls = []
    driver = types.ModuleType("psycopg")
    rows = types.ModuleType("psycopg.rows")
    rows.dict_row = object()
    def connect(dsn, **kwargs):
        calls.append(kwargs)
        raise RuntimeError("synthetic stop before network")
    driver.connect = connect
    monkeypatch.setitem(sys.modules, "psycopg", driver)
    monkeypatch.setitem(sys.modules, "psycopg.rows", rows)
    repository = PostgresFitnessRepository(DSN + "?sslmode=disable")
    monkeypatch.setattr(repository, "configuration_status", lambda: {"configured": True})
    with pytest.raises(FitnessStorageUnavailable):
        repository.snapshot("member-a")
    assert calls[0]["sslmode"] == "verify-full"
    assert calls[0]["connect_timeout"] == 5


class SyntheticDB:
    def __init__(self):
        self.states, self.requests, self.calls = {}, {}, []
        self.lock = RLock()
        self.role = {"rolsuper": False, "rolbypassrls": False}
        self.tls = True
        self.schema_version = 1
        self.tables = [{"relname": name, "relrowsecurity": True, "relforcerowsecurity": True, "is_owner": False} for name in ("member_state", "idempotency")]

    def connect(self, _dsn):
        return SyntheticConnection(self)


class SyntheticConnection:
    def __init__(self, db):
        self.db, self.member = db, None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.member = None

    @contextmanager
    def transaction(self):
        with self.db.lock:
            saved = deepcopy((self.db.states, self.db.requests))
            try:
                yield
            except Exception:
                self.db.states, self.db.requests = saved
                raise

    def cursor(self):
        return SyntheticCursor(self)


class SyntheticCursor:
    def __init__(self, conn):
        self.conn, self.result = conn, None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def execute(self, statement, params=()):
        sql = " ".join(statement.split())
        db = self.conn.db
        db.calls.append((sql, params))
        self.result = None
        if "'statement_timeout'" in sql:
            return
        if "FROM pg_catalog.pg_stat_ssl" in sql:
            self.result = {"ssl": db.tls}
        elif "FROM pg_catalog.pg_roles" in sql:
            self.result = deepcopy(db.role)
        elif "FROM pg_catalog.pg_class" in sql:
            self.result = deepcopy(db.tables)
        elif "SELECT version FROM roxy_home_fitness.schema_version" in sql:
            self.result = {"version": db.schema_version}
        elif "set_config('roxy_home.member_id'" in sql:
            self.conn.member = params[0]
        elif "pg_advisory_xact_lock" in sql:
            assert params[0] == "roxy-home-fitness:" + self.conn.member
        elif sql.startswith("INSERT INTO roxy_home_fitness.member_state"):
            assert params[0] == self.conn.member
            db.states.setdefault(params[0], {"version": 0, "profile": None, "consent": None, "updated_at": "2026-09-08T12:00:00Z"})
        elif sql.startswith("SELECT version, profile, consent"):
            assert params[0] == self.conn.member
            self.result = deepcopy(db.states.get(params[0]))
        elif sql.startswith("SELECT request_hash, response_version"):
            assert params[0] == self.conn.member
            self.result = deepcopy(db.requests.get(tuple(params)))
        elif sql.startswith("DELETE FROM roxy_home_fitness.idempotency"):
            assert params[0] == self.conn.member
            db.requests = {key: value for key, value in db.requests.items() if key[0] != params[0]}
        elif sql.startswith("UPDATE roxy_home_fitness.member_state"):
            version, profile, consent, member = params
            assert member == self.conn.member
            db.states[member].update(version=version, profile=json.loads(profile) if profile else None,
                                    consent=json.loads(consent) if consent else None)
        elif sql.startswith("INSERT INTO roxy_home_fitness.idempotency"):
            member, key, digest, version = params
            assert member == self.conn.member
            db.requests[member, key] = {"request_hash": digest, "response_version": version}
        else:
            raise AssertionError("Unexpected SQL in synthetic contract: " + sql)

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result


@pytest.fixture
def repository():
    db = SyntheticDB()
    return PostgresFitnessRepository(DSN, connection_factory=db.connect), db


def test_missing_configuration_never_creates_fallback_or_claims_ready(monkeypatch, tmp_path):
    monkeypatch.delenv("ROXY_HOME_FITNESS_DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    repo = PostgresFitnessRepository.from_env()
    assert repo.configuration_status()["status"] == "storage_not_configured"
    assert not repo.configuration_status()["personal_data_fallback"]
    with pytest.raises(FitnessStorageUnavailable):
        repo.snapshot("member-a")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("dsn", ["sqlite:///private.db", "https://example.org", "postgresql:///", "not a DSN"])
def test_not_postgres_dsn_fails_closed(dsn):
    assert PostgresFitnessRepository(dsn).configuration_status()["status"] == "invalid_storage_configuration"


def test_driver_missing_is_explicit_and_no_secret_exposed(monkeypatch):
    monkeypatch.setattr("roxy_os.fitness.repository.importlib.util.find_spec", lambda _: None)
    repo = PostgresFitnessRepository(DSN)
    assert repo.configuration_status()["status"] == "postgres_driver_unavailable"
    assert "never-real" not in json.dumps(repo.configuration_status())


def test_configuration_is_not_connection_verification(repository):
    repo, db = repository
    assert repo.configuration_status()["status"] == "storage_configured_not_verified"
    assert repo.configuration_status()["verified"] is False
    assert db.calls == []


def test_explicit_consent_then_own_profile_snapshot_export(repository):
    repo, db = repository
    assert repo.snapshot("member-a")["version"] == 0
    assert not db.states  # read does not create a record
    with pytest.raises(FitnessConsentRequired):
        repo.save_profile("member-a", PROFILE, expected_version=0, idempotency_key="save-no-consent")
    assert not db.states  # failed transaction rolled back first insert
    assert repo.set_consent("member-a", CONSENT, expected_version=0, idempotency_key="consent-0001")["version"] == 1
    saved = repo.save_profile("member-a", PROFILE, expected_version=1, idempotency_key="profile-0001")
    assert saved["version"] == 2 and saved["profile"]["primary_goal"] == "fitness_habit"
    assert repo.snapshot("member-b")["profile"] is None
    exported = repo.export_data("member-a")
    assert exported["data"] == saved and exported["contains_clinical_records"] is False
    assert "member-b" not in json.dumps(exported)
    assert any("set_config('roxy_home.member_id'" in sql and params == ("member-a",) for sql, params in db.calls)


def test_identical_retry_no_duplicate_different_payload_or_version_conflicts(repository):
    repo, _ = repository
    first = repo.set_consent("member-a", CONSENT, expected_version=0, idempotency_key="consent-0001")
    retry = repo.set_consent("member-a", CONSENT, expected_version=0, idempotency_key="consent-0001")
    assert first["version"] == retry["version"] == 1 and retry["idempotent_replay"] is True
    with pytest.raises(FitnessConflict):
        repo.set_consent("member-a", {**CONSENT, "granted": False}, expected_version=0, idempotency_key="consent-0001")
    with pytest.raises(FitnessConflict):
        repo.save_profile("member-a", PROFILE, expected_version=0, idempotency_key="profile-stale")


def test_revoke_erases_profile_blocks_stale_save_and_old_response(repository):
    repo, db = repository
    repo.set_consent("member-a", CONSENT, expected_version=0, idempotency_key="consent-0001")
    repo.save_profile("member-a", PROFILE, expected_version=1, idempotency_key="profile-0001")
    revoked = repo.set_consent("member-a", {**CONSENT, "granted": False}, expected_version=2, idempotency_key="revoke-00001")
    assert revoked["profile"] is None and revoked["consent"]["granted"] is False
    with pytest.raises(FitnessConflict):
        repo.save_profile("member-a", PROFILE, expected_version=1, idempotency_key="profile-0001")
    with pytest.raises(FitnessConsentRequired):
        repo.save_profile("member-a", PROFILE, expected_version=3, idempotency_key="profile-0002")
    assert len(db.requests) == 1
    assert all(set(v) == {"request_hash", "response_version"} for v in db.requests.values())


def test_delete_clears_only_own_preferences_retains_version_tombstone(repository):
    repo, db = repository
    for member in ("member-a", "member-b"):
        repo.set_consent(member, CONSENT, expected_version=0, idempotency_key="consent-0001")
        repo.save_profile(member, PROFILE, expected_version=1, idempotency_key="profile-0001")
    deleted = repo.delete_data("member-a", expected_version=2, idempotency_key="delete-00001")
    assert deleted["profile"] is deleted["consent"] is None and deleted["version"] == 3
    assert repo.snapshot("member-b")["profile"] is not None
    with pytest.raises(FitnessConflict):
        repo.set_consent("member-a", CONSENT, expected_version=0, idempotency_key="old-create-0001")


def test_concurrent_saves_only_one_current_version_wins_synthetic_lock(repository):
    repo, _ = repository
    repo.set_consent("member-a", CONSENT, expected_version=0, idempotency_key="consent-0001")
    def save(index):
        try:
            return repo.save_profile("member-a", PROFILE, expected_version=1, idempotency_key=f"concurrent-{index}")["version"]
        except FitnessConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, [1, 2]))
    assert sorted(str(item) for item in results) == ["2", "conflict"]


@pytest.mark.parametrize("unsafe", ["superuser", "bypass", "owner", "rls_disabled", "force_disabled", "missing_table", "wrong_version", "no_tls"])
def test_insecure_database_or_unmigrated_schema_never_reads_preferences(repository, unsafe):
    repo, db = repository
    if unsafe == "superuser": db.role["rolsuper"] = True
    elif unsafe == "bypass": db.role["rolbypassrls"] = True
    elif unsafe == "owner": db.tables[0]["is_owner"] = True
    elif unsafe == "rls_disabled": db.tables[0]["relrowsecurity"] = False
    elif unsafe == "force_disabled": db.tables[0]["relforcerowsecurity"] = False
    elif unsafe == "missing_table": db.tables.pop()
    elif unsafe == "wrong_version": db.schema_version = 999
    elif unsafe == "no_tls": db.tls = False
    with pytest.raises(FitnessStorageUnavailable):
        repo.snapshot("member-a")
    assert not any("SELECT version, profile" in sql for sql, _ in db.calls)


def test_database_exception_redacted():
    def fail(_):
        raise RuntimeError("postgresql://sensitive:secret@host/private-db member-a medical details")
    with pytest.raises(FitnessStorageUnavailable) as error:
        PostgresFitnessRepository(DSN, connection_factory=fail).snapshot("member-a")
    assert all(word not in str(error.value) for word in ("sensitive", "secret", "medical", "private-db"))


def test_corrupt_profile_without_consent_is_not_exposed_or_overwritten(repository):
    repo, db = repository
    db.states["member-a"] = {"version": 5, "profile": PROFILE, "consent": None, "updated_at": None}
    with pytest.raises(FitnessStorageUnavailable):
        repo.snapshot("member-a")
    with pytest.raises(FitnessStorageUnavailable):
        repo.set_consent("member-a", CONSENT, expected_version=5, idempotency_key="consent-repair")
    assert db.states["member-a"]["version"] == 5


@pytest.mark.parametrize("member", ["", "a' OR TRUE --", "a/b", "a" * 129, None])
def test_identity_requires_trusted_member_format(repository, member):
    with pytest.raises(FitnessInputError):
        repository[0].snapshot(member)


@pytest.mark.parametrize("version,key", [(True, "valid-key"), (-1, "valid-key"), (1, "short"), (0, "bad key with space"), (0, "k" * 129)])
def test_mutation_requires_version_and_valid_idempotency(repository, version, key):
    with pytest.raises(FitnessInputError):
        repository[0].set_consent("member-a", CONSENT, expected_version=version, idempotency_key=key)


def test_manual_migration_has_force_rls_using_and_write_checks_without_role_creation():
    sql = (Path(__file__).resolve().parents[1] / "migrations/fitness/001_foundation.sql").read_text()
    assert sql.count("FORCE ROW LEVEL SECURITY") == 2
    assert sql.count("WITH CHECK (member_id = NULLIF(current_setting('roxy_home.member_id', TRUE), ''))") == 2
    assert "REVOKE ALL ON ALL TABLES" in sql
    assert "CREATE ROLE" not in sql and "CREATE USER" not in sql
