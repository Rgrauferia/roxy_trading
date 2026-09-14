"""Chosen future goals round-trip separately from private performed results."""
from copy import deepcopy

import pytest

from roxy_os.fitness.domain import FitnessInputError
from roxy_os.fitness.training_content import training_detail
from roxy_os.fitness.training_logs import TrainingLogsRepository
from test_roxy_home_fitness_training_plan import (storage, save, selected, plan, inputs,
    MEMBER, PROGRAM, SESSION, LOG_CONSENT)


def targets():
    work = [e for e in training_detail(PROGRAM)["exercises"] if e["phase"] == "work"]
    return [{"exercise_id": work[0]["id"], "sets": [{"reps": 8, "seconds": None,
             "load": {"value": 10, "unit": "lb"}}]}]


def record(base):
    detail = training_detail(PROGRAM)
    logs = TrainingLogsRepository(base)
    logs.consent(MEMBER, LOG_CONSENT, expected_version=0, idempotency_key="target-log-consent")
    result = logs.save(MEMBER, {"session_id": SESSION, "program_id": PROGRAM,
        "content_version": detail["content_version"], "performed_on": "2020-01-03", "timezone": "UTC",
        "duration_minutes": 20, "exercises": [{"exercise_id": ex["id"], "skipped": False,
            "sets": [{"reps": 5}]} for ex in detail["exercises"] if ex["phase"] == "work"]},
        expected_version=1, idempotency_key="target-actual-record")
    return logs, result


def test_chosen_targets_round_trip_without_becoming_actual_results(storage):
    repo, base, _ = storage
    chosen = targets()
    saved = save(repo, plan(selected(training_targets=chosen)))
    assert saved["plan"]["sessions"][0]["training_targets"] == chosen
    assert repo.snapshot(MEMBER) == saved
    exported = repo.export_data(MEMBER)
    assert exported["data"] == saved
    assert exported["training_logs"]["logs"] == []
    assert save(repo, plan(selected(training_targets=chosen)))["idempotent_replay"] is True
    assert TrainingLogsRepository(base).snapshot(MEMBER)["logs"] == []
    moved = inputs(saved); moved["sessions"][0]["date"] = "2020-01-06"
    updated = save(repo, moved, version=2, key="move-goals-with-date")
    assert updated["plan"]["sessions"][0]["training_targets"] == chosen
    assert chosen == targets()


@pytest.mark.parametrize("with_targets", [False, True])
def test_logged_sessions_cannot_retroactively_change_chosen_targets(storage, with_targets):
    repo, base, _ = storage
    saved = save(repo, plan(selected(**({"training_targets": targets()} if with_targets else {}))))
    logs, actual = record(base)
    modified = inputs(saved)
    modified["sessions"][0]["training_targets"] = targets()
    modified["sessions"][0]["training_targets"][0]["sets"][0]["reps"] = 9
    with pytest.raises(FitnessInputError, match="objetivos"):
        save(repo, modified, version=2, key="must-not-rewrite-objectives")
    assert repo.snapshot(MEMBER) == saved
    assert logs.snapshot(MEMBER) == actual
    assert actual["logs"][0]["exercises"][0]["sets"][0]["reps"] == 5


def test_logged_targets_are_preserved_when_retitling_plan(storage):
    repo, base, _ = storage
    saved = save(repo, plan(selected(training_targets=targets())))
    logs, actual = record(base)
    renamed = inputs(saved); renamed["title"] = "Mi historial y mis objetivos"
    changed = save(repo, renamed, version=2, key="rename-target-history")
    assert changed["plan"]["sessions"] == saved["plan"]["sessions"]
    assert logs.snapshot(MEMBER) == actual


def test_new_target_validation_is_atomic_and_does_not_touch_existing_agenda(storage):
    repo, base, _ = storage
    saved = save(repo)
    bad = inputs(saved); bad["sessions"][0]["training_targets"] = [{"exercise_id": "not-in-program", "sets": [{"reps": 5}]}]
    with pytest.raises(FitnessInputError):
        save(repo, bad, version=2, key="invalid-target-change")
    assert repo.snapshot(MEMBER) == saved
    assert TrainingLogsRepository(base).snapshot(MEMBER)["logs"] == []
