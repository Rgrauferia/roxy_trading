"""Real isolated TLS/RLS and race checks; no existing product database is used."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from copy import deepcopy

import pytest

from roxy_os.fitness.training_logs import TrainingLogsRepository
from roxy_os.fitness.activity_plan import ActivityPlanRepository
from roxy_os.fitness.repository import FitnessConflict, FitnessStorageUnavailable
from roxy_os.fitness.domain import FitnessInputError
from test_roxy_home_fitness_postgres_integration import postgres, members, ROOT
from test_roxy_home_fitness_training_logs import CONSENT, LOG, PLAN, SESSION_ID, prepare, content


@pytest.fixture(scope="module")
def logs_pg(postgres):
    with postgres.connect("fitness_owner", autocommit=True) as connection:
        connection.execute((ROOT / "migrations/fitness/002_activity_plan.sql").read_text())
        connection.execute((ROOT / "migrations/fitness/004_training_logs.sql").read_text())
        connection.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON roxy_home_fitness.activity_plan_state, roxy_home_fitness.activity_plan_idempotency, roxy_home_fitness.training_logs_state, roxy_home_fitness.training_logs_idempotency TO fitness_runtime")
    return postgres


def setup_log(pg, member, *, save=True):
    base = pg.repository()
    prepare(base, member)
    repo = TrainingLogsRepository(base)
    repo.consent(member, CONSENT, expected_version=0, idempotency_key="training-consent")
    if save:
        repo.save(member, LOG, expected_version=1, idempotency_key="training-save")
    return repo


def test_real_private_records_persist_after_restart_and_preserve_units(logs_pg, members, content):
    a, b = members
    repo = setup_log(logs_pg, a); setup_log(logs_pg, b)
    before = repo.snapshot(a)
    assert before["logs"][0]["exercises"][0]["sets"][0]["load_kg"] == 4.535924
    logs_pg.stop(); logs_pg.start()
    assert repo.snapshot(a) == before
    assert repo.export_data(a)["data"] == before
    assert ActivityPlanRepository(logs_pg.repository()).snapshot(a)["progress"]["completed"] == 0
    assert repo.remove(a, SESSION_ID, expected_version=2, idempotency_key="remove-one-log")["logs"] == []
    assert repo.snapshot(b)["logs"]


@pytest.mark.parametrize("table", ["training_logs_state", "training_logs_idempotency"])
def test_real_rls_hides_others_without_context_and_rejects_cross_member_writes(logs_pg, members, content, table):
    a, b = members
    setup_log(logs_pg, a); setup_log(logs_pg, b)
    with logs_pg.member(a) as connection:
        assert connection.execute(f"SELECT DISTINCT member_id FROM roxy_home_fitness.{table}").fetchall() == [(a,)]
        assert connection.execute(f"DELETE FROM roxy_home_fitness.{table} WHERE member_id = %s", (b,)).rowcount == 0
    with logs_pg.connect() as connection:
        assert connection.execute(f"SELECT count(*) FROM roxy_home_fitness.{table}").fetchone() == (0,)
    with pytest.raises(logs_pg.driver.errors.InsufficientPrivilege):
        with logs_pg.member(a) as connection:
            connection.execute(f"UPDATE roxy_home_fitness.{table} SET member_id = %s WHERE member_id = %s", (b, a))


def test_real_two_concurrent_writes_have_one_winner(logs_pg, members, content):
    a, _ = members
    repo = setup_log(logs_pg, a, save=False)
    barrier = Barrier(2)
    def write(duration):
        writer = TrainingLogsRepository(logs_pg.repository())
        barrier.wait()
        try:
            writer.save(a, {**LOG, "duration_minutes": duration}, expected_version=1, idempotency_key=f"concurrent-log-{duration}")
            return "saved"
        except FitnessConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, (20, 25))) == ["conflict", "saved"]
    assert repo.snapshot(a)["version"] == 2 and len(repo.snapshot(a)["logs"]) == 1


def test_real_idempotency_stores_no_record_payload_and_revocation_blocks_replay(logs_pg, members, content):
    a, _ = members
    repo = setup_log(logs_pg, a)
    assert repo.save(a, LOG, expected_version=1, idempotency_key="training-save")["idempotent_replay"] is True
    with logs_pg.member(a) as connection:
        columns = connection.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'roxy_home_fitness' AND table_name = 'training_logs_idempotency'").fetchall()
        assert {row[0] for row in columns} == {"member_id", "request_key", "request_hash", "response_version"}
    repo.consent(a, {**CONSENT, "granted": False}, expected_version=2, idempotency_key="revoke-training")
    with pytest.raises(FitnessConflict):
        repo.save(a, LOG, expected_version=1, idempotency_key="training-save")
    assert repo.snapshot(a)["logs"] == []


def test_real_erase_helper_is_atomic_and_tombstone_survives_restart(logs_pg, members, content):
    a, _ = members
    base = logs_pg.repository()
    prepare(base, a)
    repo = TrainingLogsRepository(base)
    with base._transaction(a) as cursor:
        TrainingLogsRepository.erase_for_member(cursor, a)
    logs_pg.stop(); logs_pg.start()
    assert repo.snapshot(a)["version"] == 1
    with pytest.raises(FitnessConflict):
        repo.consent(a, CONSENT, expected_version=0, idempotency_key="old-first-consent")
    repo.consent(a, CONSENT, expected_version=1, idempotency_key="new-consent")
    repo.save(a, LOG, expected_version=2, idempotency_key="new-log-001")
    before = repo.snapshot(a)
    with pytest.raises(FitnessStorageUnavailable):
        with base._transaction(a) as cursor:
            TrainingLogsRepository.erase_for_member(cursor, a)
            raise RuntimeError("synthetic erase failure")
    assert repo.snapshot(a) == before


def test_real_guard_prevents_session_change_until_log_explicitly_deleted(logs_pg, members, content):
    a, _ = members
    repo = setup_log(logs_pg, a)
    changed = deepcopy(PLAN); changed["sessions"][0]["time"] = "11:00"
    with logs_pg.repository()._transaction(a) as cursor:
        with pytest.raises(FitnessInputError, match="registro"):
            TrainingLogsRepository.guard_plan_change(cursor, a, changed)
    repo.remove(a, SESSION_ID, expected_version=2, idempotency_key="delete-before-change")
    with logs_pg.repository()._transaction(a) as cursor:
        TrainingLogsRepository.guard_plan_change(cursor, a, changed)


@pytest.mark.parametrize("table", ["training_logs_state", "training_logs_idempotency"])
def test_real_disabled_force_rls_fails_before_returning_values(logs_pg, members, content, table):
    a, _ = members
    repo = setup_log(logs_pg, a)
    with logs_pg.connect("fitness_owner", autocommit=True) as connection:
        connection.execute(f"ALTER TABLE roxy_home_fitness.{table} NO FORCE ROW LEVEL SECURITY")
        try:
            with pytest.raises(FitnessStorageUnavailable):
                repo.snapshot(a)
        finally:
            connection.execute(f"ALTER TABLE roxy_home_fitness.{table} FORCE ROW LEVEL SECURITY")


def test_real_tls_hostname_and_runtime_nonowner_still_required(logs_pg, members, content):
    a, _ = members
    setup_log(logs_pg, a)
    with pytest.raises(FitnessStorageUnavailable):
        TrainingLogsRepository(logs_pg.repository(host="wrong-host.invalid", sslmode="disable")).snapshot(a)
    with pytest.raises(FitnessStorageUnavailable):
        TrainingLogsRepository(logs_pg.repository(role="fitness_owner")).snapshot(a)


def test_real_sql_bound_rejects_more_than_366_logs(logs_pg, members, content):
    a, _ = members
    repo = setup_log(logs_pg, a)
    with pytest.raises(logs_pg.driver.errors.CheckViolation):
        with logs_pg.member(a) as connection:
            connection.execute("UPDATE roxy_home_fitness.training_logs_state SET logs = (SELECT jsonb_agg('{}'::jsonb) FROM generate_series(1, 367)) WHERE member_id = %s", (a,))
    assert len(repo.snapshot(a)["logs"]) == 1


def test_real_global_export_and_delete_cascade(logs_pg, members, content):
    a, b = members
    repo = setup_log(logs_pg, a); setup_log(logs_pg, b)
    base = logs_pg.repository()
    assert base.export_data(a)["training_logs"]["logs"][0]["session_id"] == SESSION_ID
    base.delete_data(a, expected_version=2, idempotency_key="delete-all-fitness")
    assert repo.snapshot(a)["logs"] == [] and repo.snapshot(a)["consent"] is None
    assert repo.snapshot(b)["logs"]
    with pytest.raises(FitnessConflict):
        repo.save(a, LOG, expected_version=1, idempotency_key="training-save")


def test_real_agenda_deletion_erases_logs_without_removing_preferences(logs_pg, members, content):
    a, _ = members
    repo = setup_log(logs_pg, a)
    base = logs_pg.repository()
    ActivityPlanRepository(base).delete_data(a, expected_version=2, idempotency_key="delete-agenda")
    assert repo.snapshot(a)["logs"] == [] and repo.snapshot(a)["consent"] is None
    assert base.snapshot(a)["profile"]


def test_real_concurrent_agenda_deletion_cannot_leave_orphan_log(logs_pg, members, content):
    a, _ = members
    repo = setup_log(logs_pg, a, save=False)
    barrier = Barrier(2)
    def record():
        barrier.wait()
        try:
            TrainingLogsRepository(logs_pg.repository()).save(a, LOG, expected_version=1, idempotency_key="race-record")
            return "saved_before_deletion"
        except (FitnessConflict, FitnessInputError):
            return "rejected_after_deletion"
    def erase():
        barrier.wait()
        ActivityPlanRepository(logs_pg.repository()).delete_data(a, expected_version=2, idempotency_key="race-delete-agenda")
    with ThreadPoolExecutor(max_workers=2) as pool:
        writing = pool.submit(record); deleting = pool.submit(erase)
        assert writing.result() in {"saved_before_deletion", "rejected_after_deletion"}
        deleting.result()
    assert repo.snapshot(a)["logs"] == [] and repo.snapshot(a)["consent"] is None


def test_real_concurrent_global_erasure_and_first_consent_cannot_restore_logs(logs_pg, members, content):
    a, _ = members
    base = logs_pg.repository(); prepare(base, a)
    barrier = Barrier(2)
    def grant():
        barrier.wait()
        try:
            TrainingLogsRepository(logs_pg.repository()).consent(a, CONSENT, expected_version=0, idempotency_key="race-first-consent")
            return "granted_before_erasure"
        except (FitnessConflict, FitnessInputError):
            return "rejected_after_erasure"
    def erase():
        barrier.wait()
        logs_pg.repository().delete_data(a, expected_version=2, idempotency_key="race-global-erase")
    with ThreadPoolExecutor(max_workers=2) as pool:
        granting = pool.submit(grant); erasing = pool.submit(erase)
        assert granting.result() in {"granted_before_erasure", "rejected_after_erasure"}
        erasing.result()
    after = TrainingLogsRepository(base).snapshot(a)
    assert after["logs"] == [] and after["consent"] is None and after["eligible"] is False


def test_real_catalog_routine_logs_each_work_exercise_with_exact_version(logs_pg, members):
    """End-to-end catalogue, preferences, selected agenda, manual record: no content mock."""
    from roxy_os.fitness.training_content import training_detail
    a, _ = members
    base = logs_pg.repository()
    planner = prepare(base, a)
    profile = base.snapshot(a)["profile"]
    profile.update(timezone="UTC", locations=["home"], equipment=["bodyweight", "dumbbells"],
                   experience="beginner", session_minutes=45, travel_minutes=0,
                   availability=[{"day": "wed", "windows": [{"start": "09:00", "end": "12:00"}]}])
    base.save_profile(a, profile, expected_version=2, idempotency_key="real-training-profile")
    detail = training_detail("home-dumbbell-foundations")
    session = {**PLAN["sessions"][0], "program_id": detail["id"], "content_version": detail["content_version"],
               "confirmed_requirements": {key: detail["requirements"][key] for key in ("equipment", "capabilities")},
               "reserved_minutes": 45, "travel_minutes": 0}
    planned = planner.save(a, {**PLAN, "sessions": [session]}, expected_version=2,
                           expected_profile_version=3, idempotency_key="real-training-plan")
    repo = TrainingLogsRepository(base)
    repo.consent(a, CONSENT, expected_version=0, idempotency_key="real-training-consent")
    payload = {**LOG, "program_id": detail["id"], "content_version": detail["content_version"],
               "exercises": [{"exercise_id": item["id"], "skipped": False,
                  "sets": [{"reps": 8, "seconds": None,
                            "load": {"value": 5, "unit": "kg"} if item["load_recordable"] else None}]}
                  for item in detail["exercises"] if item["phase"] == "work"]}
    result = repo.save(a, payload, expected_version=1, idempotency_key="real-training-results")
    assert len(result["logs"][0]["exercises"]) == detail["exercise_count"] == 5
    assert planner.snapshot(a) == planned
    altered = deepcopy(payload)
    wall = next(item for item in altered["exercises"] if item["exercise_id"] == "wall-pushup")
    wall["sets"][0]["load"] = {"value": 5, "unit": "kg"}
    with pytest.raises(FitnessInputError, match="sin carga"):
        repo.save(a, altered, expected_version=2, idempotency_key="invalid-weighted-wall")
    with pytest.raises(FitnessConflict, match="versión"):
        repo.save(a, {**payload, "content_version": "stale-v0"}, expected_version=2, idempotency_key="invalid-log-version")
    assert repo.snapshot(a)["version"] == 2


def test_real_skipped_logs_stay_readable_but_only_active_or_completed_sessions_can_correct(logs_pg, members, content):
    a, _ = members
    repo = setup_log(logs_pg, a)
    planner = ActivityPlanRepository(logs_pg.repository())
    before = repo.snapshot(a)
    planner.set_status(a, SESSION_ID, "skipped", expected_version=2, idempotency_key="skip-recorded-session")
    with pytest.raises(FitnessInputError, match="omitida"):
        repo.save(a, {**LOG, "duration_minutes": 30}, expected_version=2, idempotency_key="reject-skipped-correction")
    assert repo.snapshot(a) == before
    assert repo.export_data(a)["data"] == before
    planner.set_status(a, SESSION_ID, "completed", expected_version=3, idempotency_key="confirm-actually-completed")
    corrected = repo.save(a, {**LOG, "duration_minutes": 30}, expected_version=2, idempotency_key="correct-completed-session")
    assert corrected["logs"][0]["duration_minutes"] == 30
    planner.set_status(a, SESSION_ID, "skipped", expected_version=4, idempotency_key="skip-corrected-session")
    assert repo.remove(a, SESSION_ID, expected_version=3, idempotency_key="remove-skipped-record")["logs"] == []
