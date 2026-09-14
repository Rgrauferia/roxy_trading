"""Measurement integration against a newly created synthetic, TLS-only cluster.

No product DSN is read and no existing preview or server is migrated by these tests.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from roxy_os.fitness.measurements import MeasurementsRepository
from roxy_os.fitness.repository import FitnessConflict, FitnessStorageUnavailable
from test_roxy_home_fitness_postgres_integration import postgres, members, ROOT
from test_roxy_home_fitness_measurements import CONSENT, MEASUREMENT, RECORD_ID, adult


@pytest.fixture(scope="module")
def measurements_pg(postgres):
    with postgres.connect("fitness_owner", autocommit=True) as connection:
        connection.execute((ROOT / "migrations/fitness/003_measurements.sql").read_text())
        connection.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON roxy_home_fitness.measurements_state, roxy_home_fitness.measurements_idempotency TO fitness_runtime")
    return postgres


def setup_measurement(pg, member, *, save=True):
    base = pg.repository()
    adult(base, member)
    repo = MeasurementsRepository(base)
    repo.consent(member, CONSENT, expected_version=0, idempotency_key="measurements-consent")
    if save:
        repo.save(member, MEASUREMENT, expected_version=1, idempotency_key="measurements-save")
    return repo


def test_real_measurement_persists_through_restart_with_units_and_private_export(measurements_pg, members):
    a, b = members
    repo = setup_measurement(measurements_pg, a)
    setup_measurement(measurements_pg, b)
    before = repo.snapshot(a)
    assert before["measurements"][0]["weight_kg"] == 72.574779
    assert before["measurements"][0]["height_cm"] == 173.99
    measurements_pg.stop(); measurements_pg.start()
    assert repo.snapshot(a) == before
    exported = repo.export_data(a)
    assert exported["scope"] == "authenticated_member_only"
    assert exported["data"] == before
    assert exported["data"]["measurements"][0]["weight"] == MEASUREMENT["weight"]
    assert measurements_pg.repository().export_data(a)["measurements"] == before
    removed = repo.remove(a, RECORD_ID, expected_version=2, idempotency_key="remove-one-measurement")
    assert removed["measurements"] == [] and removed["consent"]["granted"] is True
    assert repo.snapshot(b)["measurements"]


@pytest.mark.parametrize("table", ["measurements_state", "measurements_idempotency"])
def test_real_rls_hides_other_member_and_rejects_cross_member_writes(measurements_pg, members, table):
    a, b = members
    setup_measurement(measurements_pg, a); setup_measurement(measurements_pg, b)
    with measurements_pg.member(a) as connection:
        assert connection.execute(f"SELECT DISTINCT member_id FROM roxy_home_fitness.{table}").fetchall() == [(a,)]
        assert connection.execute(f"DELETE FROM roxy_home_fitness.{table} WHERE member_id = %s", (b,)).rowcount == 0
    with measurements_pg.connect() as connection:
        assert connection.execute(f"SELECT count(*) FROM roxy_home_fitness.{table}").fetchone() == (0,)
    with pytest.raises(measurements_pg.driver.errors.InsufficientPrivilege):
        with measurements_pg.member(a) as connection:
            connection.execute(f"UPDATE roxy_home_fitness.{table} SET member_id = %s WHERE member_id = %s", (b, a))


def test_real_concurrent_writes_have_one_winner_and_no_duplicate_record(measurements_pg, members):
    a, _ = members
    repo = setup_measurement(measurements_pg, a, save=False)
    barrier = Barrier(2)
    def write(day):
        writer = MeasurementsRepository(measurements_pg.repository())
        barrier.wait()
        try:
            writer.save(a, {**MEASUREMENT, "date": day, "id": str(uuid4())},
                        expected_version=1, idempotency_key="concurrent-" + day)
            return "saved"
        except FitnessConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, ("2020-01-01", "2020-01-02"))) == ["conflict", "saved"]
    assert repo.snapshot(a)["version"] == 2 and len(repo.snapshot(a)["measurements"]) == 1


def test_real_retry_is_idempotent_and_withdrawal_cannot_replay_measurements(measurements_pg, members):
    a, _ = members
    repo = setup_measurement(measurements_pg, a)
    replay = repo.save(a, MEASUREMENT, expected_version=1, idempotency_key="measurements-save")
    assert replay["version"] == 2 and replay["idempotent_replay"] is True
    with measurements_pg.member(a) as connection:
        columns = connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'roxy_home_fitness' AND table_name = 'measurements_idempotency'").fetchall()
        assert {row[0] for row in columns} == {"member_id", "request_key", "request_hash", "response_version"}
    revoked = repo.consent(a, {**CONSENT, "granted": False}, expected_version=2, idempotency_key="withdraw-measurements")
    assert revoked["measurements"] == [] and revoked["consent"]["granted"] is False
    with pytest.raises(FitnessConflict):
        repo.save(a, MEASUREMENT, expected_version=1, idempotency_key="measurements-save")
    assert measurements_pg.repository().snapshot(a)["profile"]


def test_real_global_erasure_clears_measurements_without_touching_other_member(measurements_pg, members):
    a, b = members
    repo = setup_measurement(measurements_pg, a)
    setup_measurement(measurements_pg, b)
    base = measurements_pg.repository()
    base.delete_data(a, expected_version=2, idempotency_key="erase-all-fitness")
    assert repo.snapshot(a)["measurements"] == []
    assert repo.snapshot(a)["consent"] is None and repo.snapshot(a)["eligible"] is False
    assert repo.snapshot(a)["version"] == 3
    assert repo.snapshot(b)["measurements"]
    with pytest.raises(FitnessConflict):
        repo.save(a, MEASUREMENT, expected_version=1, idempotency_key="measurements-save")


def test_real_global_erasure_before_first_consent_keeps_tombstone(measurements_pg, members):
    a, _ = members
    base = measurements_pg.repository()
    adult(base, a)
    repo = MeasurementsRepository(base)
    assert repo.snapshot(a)["version"] == 0
    base.delete_data(a, expected_version=2, idempotency_key="erase-before-measurements")
    measurements_pg.stop(); measurements_pg.start()
    assert repo.snapshot(a)["version"] == 1
    with pytest.raises(FitnessConflict):
        repo.consent(a, CONSENT, expected_version=0, idempotency_key="inflight-first-consent")
    assert repo.snapshot(a)["measurements"] == []


def test_real_concurrent_global_erasure_and_first_consent_cannot_restore_data(measurements_pg, members):
    a, _ = members
    adult(measurements_pg.repository(), a)
    barrier = Barrier(2)
    def grant():
        barrier.wait()
        try:
            MeasurementsRepository(measurements_pg.repository()).consent(a, CONSENT, expected_version=0, idempotency_key="concurrent-first-consent")
            return "granted_before_erasure"
        except FitnessConflict:
            return "conflict_after_erasure"
    def erase():
        barrier.wait()
        measurements_pg.repository().delete_data(a, expected_version=2, idempotency_key="concurrent-global-erasure")
        return "erased"
    with ThreadPoolExecutor(max_workers=2) as pool:
        granting = pool.submit(grant)
        erasing = pool.submit(erase)
        assert granting.result() in {"granted_before_erasure", "conflict_after_erasure"}
        assert erasing.result() == "erased"
    after = MeasurementsRepository(measurements_pg.repository()).snapshot(a)
    assert after["consent"] is None and after["measurements"] == [] and after["eligible"] is False


def test_real_global_helper_rollback_restores_measurements(measurements_pg, members):
    a, _ = members
    repo = setup_measurement(measurements_pg, a)
    before = repo.snapshot(a)
    with pytest.raises(FitnessStorageUnavailable):
        with measurements_pg.repository()._transaction(a) as cursor:
            MeasurementsRepository.erase_for_member(cursor, a)
            raise RuntimeError("synthetic downstream erase failure")
    assert repo.snapshot(a) == before


@pytest.mark.parametrize("table", ["measurements_state", "measurements_idempotency"])
def test_real_rls_regression_fails_before_returning_measurements(measurements_pg, members, table):
    a, _ = members
    repo = setup_measurement(measurements_pg, a)
    with measurements_pg.connect("fitness_owner", autocommit=True) as connection:
        connection.execute(f"ALTER TABLE roxy_home_fitness.{table} NO FORCE ROW LEVEL SECURITY")
        try:
            with pytest.raises(FitnessStorageUnavailable):
                repo.snapshot(a)
        finally:
            connection.execute(f"ALTER TABLE roxy_home_fitness.{table} FORCE ROW LEVEL SECURITY")


def test_real_measurements_inherit_tls_and_nonowner_requirements(measurements_pg, members):
    a, _ = members
    setup_measurement(measurements_pg, a)
    with pytest.raises(FitnessStorageUnavailable):
        MeasurementsRepository(measurements_pg.repository(host="wrong-host.invalid", sslmode="disable")).snapshot(a)
    with pytest.raises(FitnessStorageUnavailable):
        MeasurementsRepository(measurements_pg.repository(role="fitness_owner")).snapshot(a)


def test_real_database_rejects_more_than_500_records(measurements_pg, members):
    a, _ = members
    setup_measurement(measurements_pg, a)
    with pytest.raises(measurements_pg.driver.errors.CheckViolation):
        with measurements_pg.member(a) as connection:
            connection.execute("UPDATE roxy_home_fitness.measurements_state SET measurements = (SELECT jsonb_agg('{}'::jsonb) FROM generate_series(1, 501)) WHERE member_id = %s", (a,))
    assert len(MeasurementsRepository(measurements_pg.repository()).snapshot(a)["measurements"]) == 1
