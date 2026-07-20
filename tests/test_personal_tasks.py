import json
from datetime import datetime, timedelta, timezone

import pytest

from roxy_os.personal_tasks import PersonalTaskStore


def test_personal_tasks_are_durable_and_isolated_by_user(tmp_path):
    path = tmp_path / "tasks.json"
    first = PersonalTaskStore(path)
    created = first.create("Robert", "Llamar al cliente", notes="Confirmar contrato", priority="HIGH")
    first.create("Alice", "Tarea privada")

    reopened = PersonalTaskStore(path)
    robert = reopened.list_tasks("robert")
    alice = reopened.list_tasks("alice")

    assert [task["id"] for task in robert] == [created["id"]]
    assert robert[0]["notes"] == "Confirmar contrato"
    assert [task["title"] for task in alice] == ["Tarea privada"]
    assert json.loads(path.read_text())["schema_version"] == 1


def test_personal_task_lifecycle_is_validated_and_recoverable(tmp_path):
    store = PersonalTaskStore(tmp_path / "tasks.json")
    task = store.create("robert", "Preparar reporte")

    started = store.transition("robert", task["id"], "IN_PROGRESS")
    completed = store.transition("robert", task["id"], "DONE")
    archived = store.transition("robert", task["id"], "ARCHIVED")
    restored = store.transition("robert", task["id"], "PENDING")

    assert started["status"] == "IN_PROGRESS"
    assert completed["completed_at"]
    assert archived["status"] == "ARCHIVED"
    assert restored["status"] == "PENDING"
    assert restored["completed_at"] is None


def test_personal_task_store_rejects_cross_user_mutation_and_invalid_input(tmp_path):
    store = PersonalTaskStore(tmp_path / "tasks.json")
    task = store.create("robert", "Revisar alertas")

    with pytest.raises(KeyError):
        store.transition("alice", task["id"], "DONE")
    with pytest.raises(ValueError):
        store.create("robert", "   ")
    with pytest.raises(ValueError):
        store.create("robert", "Tarea", priority="IMPOSSIBLE")
    with pytest.raises(ValueError):
        store.create("robert", "Tarea", due_at="2026-07-20T09:00:00")


def test_personal_task_snapshot_marks_overdue_and_local_only_sync(tmp_path):
    store = PersonalTaskStore(tmp_path / "tasks.json")
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    store.create("robert", "Vencida", due_at=now - timedelta(minutes=1), priority="URGENT")
    store.create("robert", "Futura", due_at=now + timedelta(hours=2))

    rows = store.list_tasks("robert", now=now)
    snapshot = store.snapshot("robert")

    assert rows[0]["title"] == "Vencida"
    assert rows[0]["overdue"] is True
    assert rows[1]["overdue"] is False
    assert snapshot["source"] == "local_durable"
    assert snapshot["sync_state"] == "LOCAL_ONLY"
    assert snapshot["active_count"] == 2


def test_personal_task_archive_is_hidden_by_default(tmp_path):
    store = PersonalTaskStore(tmp_path / "tasks.json")
    task = store.create("robert", "Archivar")
    store.transition("robert", task["id"], "ARCHIVED")

    assert store.list_tasks("robert") == []
    assert store.list_tasks("robert", include_archived=True)[0]["status"] == "ARCHIVED"


def test_personal_tasks_revision_rejects_stale_device_replace(tmp_path):
    store = PersonalTaskStore(tmp_path / "tasks.json")
    store.create("robert", "Primera")
    stale = store.snapshot("robert")
    store.create("robert", "Segunda")

    conflict = store.replace_user_snapshot("robert", stale, expected_revision=stale["revision"])

    assert conflict["conflict"] is True
    assert conflict["current_revision"] == 2
    assert [row["title"] for row in store.list_tasks("robert")] == ["Primera", "Segunda"]


def test_personal_tasks_device_replace_forces_user_namespace(tmp_path):
    store = PersonalTaskStore(tmp_path / "tasks.json")
    result = store.replace_user_snapshot(
        "robert",
        {"tasks": [{"id": "a" * 32, "user_id": "alice", "title": "Sincronizada", "status": "PENDING"}]},
        expected_revision=0,
    )
    assert result["conflict"] is False
    assert store.list_tasks("alice") == []
    assert store.list_tasks("robert")[0]["user_id"] == "robert"
