"""Real local PostgreSQL integration for manual migration002 and private agenda."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from roxy_os.fitness.activity_plan import ActivityPlanRepository
from roxy_os.fitness.repository import FitnessConflict, FitnessStorageUnavailable
from test_roxy_home_fitness_postgres_integration import postgres, members, ROOT
from test_roxy_home_fitness_activity_plan import CONSENT, PLAN, SESSION_ID


@pytest.fixture(scope="module")
def planning_pg(postgres):
    with postgres.connect("fitness_owner", autocommit=True) as conn:
        conn.execute((ROOT / "migrations/fitness/002_activity_plan.sql").read_text())
        conn.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON roxy_home_fitness.activity_plan_state, roxy_home_fitness.activity_plan_idempotency TO fitness_runtime")
    return postgres


def setup_plan(pg, member):
    repo = ActivityPlanRepository(pg.repository())
    repo.consent(member, CONSENT, expected_version=0, idempotency_key="consent-plan-0001")
    repo.save(member, PLAN, expected_version=1, idempotency_key="save-plan-0001")
    return repo


def test_real_agenda_commits_progress_export_erasure_and_restart(planning_pg, members):
    a, b = members
    repo = setup_plan(planning_pg, a); setup_plan(planning_pg, b)
    done = repo.set_status(a, SESSION_ID, "completed", expected_version=2, idempotency_key="mark-done-0001")
    assert done["progress"]["completed"] == 1
    planning_pg.stop(); planning_pg.start()
    assert repo.snapshot(a)["plan"]["sessions"][0]["status"] == "completed"
    assert planning_pg.repository().export_data(a)["activity_plan"]["progress"]["completed"] == 1
    planning_pg.repository().delete_data(a, expected_version=0, idempotency_key="delete-all-0001")
    assert repo.snapshot(a)["plan"] is None
    assert repo.snapshot(b)["plan"] is not None
    with pytest.raises(FitnessConflict):
        repo.save(a, PLAN, expected_version=1, idempotency_key="save-plan-0001")


@pytest.mark.parametrize("table", ["activity_plan_state", "activity_plan_idempotency"])
def test_real_agenda_rls_hides_other_member_and_rejects_cross_writes(planning_pg, members, table):
    a, b = members
    setup_plan(planning_pg, a); setup_plan(planning_pg, b)
    with planning_pg.member(a) as conn:
        assert conn.execute(f"SELECT DISTINCT member_id FROM roxy_home_fitness.{table}").fetchall() == [(a,)]
        assert conn.execute(f"DELETE FROM roxy_home_fitness.{table} WHERE member_id = %s", (b,)).rowcount == 0
    with planning_pg.connect() as conn:
        assert conn.execute(f"SELECT COUNT(*) FROM roxy_home_fitness.{table}").fetchone() == (0,)
    with pytest.raises(Exception):
        with planning_pg.member(a) as conn:
            conn.execute(f"UPDATE roxy_home_fitness.{table} SET member_id = %s WHERE member_id = %s", (b, a))


def test_real_concurrent_marks_have_one_winner(planning_pg, members):
    a, _ = members; setup_plan(planning_pg, a); barrier = Barrier(2)
    def write(status):
        repo = ActivityPlanRepository(planning_pg.repository()); barrier.wait()
        try:
            repo.set_status(a, SESSION_ID, status, expected_version=2, idempotency_key="concurrent-" + status)
            return "saved"
        except FitnessConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, ("completed", "skipped"))) == ["conflict", "saved"]
    assert ActivityPlanRepository(planning_pg.repository()).snapshot(a)["version"] == 3


def test_real_revocation_erases_plan_and_preserves_preferences(planning_pg, members):
    a, _ = members; repo = setup_plan(planning_pg, a)
    repo.consent(a, {**CONSENT, "granted": False}, expected_version=2, idempotency_key="revoke-plan-0001")
    assert repo.snapshot(a)["plan"] is None and repo.snapshot(a)["progress"]["total"] == 0
    assert planning_pg.repository().snapshot(a)["version"] == 0


def test_real_rls_regression_fails_before_read(planning_pg, members):
    a, _ = members; repo = setup_plan(planning_pg, a)
    with planning_pg.connect("fitness_owner", autocommit=True) as conn:
        conn.execute("ALTER TABLE roxy_home_fitness.activity_plan_state NO FORCE ROW LEVEL SECURITY")
        try:
            with pytest.raises(FitnessStorageUnavailable):
                repo.snapshot(a)
        finally:
            conn.execute("ALTER TABLE roxy_home_fitness.activity_plan_state FORCE ROW LEVEL SECURITY")


def test_real_global_erasure_invalidates_first_consent_before_any_plan_row(planning_pg, members):
    a, _ = members
    base = planning_pg.repository()
    repo = ActivityPlanRepository(base)
    assert repo.snapshot(a)["version"] == 0
    base.delete_data(a, expected_version=0, idempotency_key="erase-before-first-consent")
    planning_pg.stop(); planning_pg.start()
    assert repo.snapshot(a)["version"] == 1
    with pytest.raises(FitnessConflict):
        repo.consent(a, CONSENT, expected_version=0, idempotency_key="inflight-first-consent")
    assert repo.snapshot(a)["plan"] is repo.snapshot(a)["consent"] is None
