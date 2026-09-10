"""Calendar persistence checks use temporary synthetic records exclusively."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from roxy_os import home_calendar, home_private_storage
from roxy_os.home_calendar import HomeCalendarStorageError, HomeCalendarStore


def event_values(**overrides):
    values = {
        "title": "Evento sintético", "starts_at": "2026-09-14T08:30:00-04:00",
        "ends_at": "2026-09-14T09:15:00-04:00", "timezone": "America/New_York",
        "category": "HOME", "reminder_minutes": 15, "location": "Casa de prueba",
        "notes": "Primera línea\nSegunda línea; sin normalizar al leer.",
        "participants": ["Persona sintética"], "recurrence": "WEEKLY",
        "recurrence_until": "2026-10-14", "all_day": False,
    }
    return {**values, **overrides}


@pytest.fixture
def store(tmp_path):
    return HomeCalendarStore(tmp_path / "persistent" / "calendar.json")


@pytest.fixture
def seed(store):
    events = [
        {**event_values(), "id": f"event-{owner}", "owner_id": owner,
         "source": "legacy-source", "created_at": "2026-08-01T01:02:03-04:00",
         "updated_at": "2026-08-02T02:03:04-04:00", "future_field": {"preserve": [1, None, "dos"]}}
        for owner in ("member:a", "member:b", "legacy:household")
    ]
    state = {
        "schema_version": 1, "events": events,
        "drafts": {
            "member:b": {**deepcopy(events[1]), "id": "draft-b", "status": "PENDING"},
            "member:a": {"id": "delete-a", "owner_id": "member:a", "status": "PENDING", "action": "DELETE",
                         "event_id": events[0]["id"], "event": deepcopy(events[0]), "created_at": "2026-09-01T12:00:00Z", "future_draft_field": "keep"},
        },
        "updated_at": "2026-09-01T12:00:00Z", "future_root_field": {"keep": True},
    }
    store.path.parent.mkdir(parents=True)
    store.path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return state


def listed(store, owner="member:a"):
    return store.list_events(owner, start="2026-09-14T00:00:00-04:00", end="2026-09-15T00:00:00-04:00")


def mutation_operations(store):
    return (
        lambda: store.create("member:new", event_values()),
        lambda: store.save_draft("member:new", event_values()),
        lambda: store.discard_draft("member:b"),
        lambda: store.update("member:a", "event-member:a", {"title": "Cambio sintético"}),
        lambda: store.delete("member:a", "event-member:a"),
    )


def test_never_initialized_read_is_new_without_creating_files(store):
    assert store.owned_events("member:a") == []
    assert listed(store) == []
    assert store.pending_draft("member:a") is None
    assert store.storage_status() == "NEW"
    assert not store.path.parent.exists()


@pytest.mark.parametrize("versioned", [True, False])
def test_legacy_records_and_extensions_survive_restart_without_read_normalization(store, seed, tmp_path, monkeypatch, versioned):
    if not versioned:
        seed.pop("schema_version")
        store.path.write_text(json.dumps(seed, ensure_ascii=False), encoding="utf-8")
    original = store.path.read_bytes()
    for event in seed["events"]:
        assert store.get(event["owner_id"], event["id"]) == event
    assert store.pending_draft("member:a") == seed["drafts"]["member:a"]
    assert store.owned_events("member:unknown") == []
    assert len(listed(store)) == 1
    assert store.storage_status() == "READY"
    assert store.path.read_bytes() == original
    assert not home_private_storage.initialized_marker(store.path).exists()
    # A different owner writes; existing event dates, reminders and drafts do not change.
    created = store.create("member:new", event_values(recurrence="NONE", recurrence_until=None))
    changed = json.loads(store.path.read_text())
    assert changed["events"][:-1] == seed["events"]
    assert changed["drafts"] == seed["drafts"]
    assert changed["future_root_field"] == seed["future_root_field"]
    assert changed["schema_version"] == 1
    other_cwd = tmp_path / "restarted-worker"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)
    reopened = HomeCalendarStore(store.path)
    assert reopened.get("member:new", created["id"]) == created
    assert reopened.owned_events("member:a") == [seed["events"][0]]
    assert reopened.pending_draft("member:b") == seed["drafts"]["member:b"]
    assert home_private_storage.initialized_marker(store.path).read_text() == "1\n"
    assert reopened.storage_status() == "READY"
    assert store.path.stat().st_mode & 0o777 == 0o600
    assert store.lock_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("raw", [
    b"", b"{broken", b"\xff\xfe", b"null", b"[]", b"{}",
    b'{"events":null,"drafts":{}}', b'{"events":[],"drafts":null}',
    b'{"events":[],"events":[{"discarded":true}],"drafts":{}}',
    b'{"events":[],"drafts":{},"bad":NaN}',
    b'{"events":[],"drafts":{},"schema_version":2}',
    b'{"events":[],"drafts":{},"schema_version":true}',
    b'{"events":[],"drafts":{},"schema_version":"1"}',
])
def test_corruption_never_becomes_empty_or_overwritten(store, raw):
    store.path.parent.mkdir(parents=True)
    store.path.write_bytes(raw)
    reads = (lambda: listed(store), lambda: store.pending_draft("member:a"), lambda: store.owned_events("member:b"))
    for operation in (*reads, *mutation_operations(store)):
        with pytest.raises(HomeCalendarStorageError):
            operation()
        assert store.path.read_bytes() == raw
    assert not home_private_storage.initialized_marker(store.path).exists()
    assert not list(store.path.parent.glob("*.tmp"))


@pytest.mark.parametrize("kind", ["event_row", "event_id", "owner", "date_type", "participants", "reminder", "duplicate_event", "draft_row", "draft_owner", "delete_event", "delete_reference"])
def test_malformed_records_are_rejected_not_filtered(store, seed, kind):
    event = seed["events"][0]
    if kind == "event_row": seed["events"].append(None)
    elif kind == "event_id": event.pop("id")
    elif kind == "owner": event["owner_id"] = None
    elif kind == "date_type": event["starts_at"] = {"invalid": "shape"}
    elif kind == "participants": event["participants"] = "Not a list"
    elif kind == "reminder": event["reminder_minutes"] = True
    elif kind == "duplicate_event": seed["events"].append(deepcopy(event))
    elif kind == "draft_row": seed["drafts"]["member:b"] = []
    elif kind == "draft_owner": seed["drafts"]["member:b"]["owner_id"] = "member:a"
    elif kind == "delete_event": seed["drafts"]["member:a"]["event"] = None
    elif kind == "delete_reference": seed["drafts"]["member:a"]["event_id"] = "event-member:b"
    raw = json.dumps(seed).encode()
    store.path.write_bytes(raw)
    for operation in (lambda: listed(store), *mutation_operations(store)):
        with pytest.raises(HomeCalendarStorageError) as caught:
            operation()
        assert caught.value.code == "invalid_structure"
        assert store.path.read_bytes() == raw


def test_initialized_file_disappearance_blocks_reads_and_mutations(store):
    store.create("member:a", event_values())
    store.path.unlink()  # Exact temporary synthetic fixture, never customer data.
    reopened = HomeCalendarStore(store.path)
    for operation in (lambda: listed(reopened), *mutation_operations(reopened)):
        with pytest.raises(HomeCalendarStorageError) as caught:
            operation()
        assert caught.value.code == "missing_initialized"
        assert not store.path.exists()


def test_read_permission_failure_retains_all_bytes(store, seed, monkeypatch):
    original = store.path.read_bytes()
    real_read = Path.read_text
    def denied(path, *args, **kwargs):
        if path == store.path:
            raise PermissionError("Synthetic internal path must remain private")
        return real_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", denied)
    for operation in (lambda: listed(store), *mutation_operations(store)):
        with pytest.raises(HomeCalendarStorageError) as caught:
            operation()
        assert caught.value.code == "unreadable"
        assert "internal path" not in str(caught.value)
        assert store.path.read_bytes() == original


def test_replace_failure_preserves_original_and_removes_temp(store, seed, monkeypatch):
    original = store.path.read_bytes()
    real_replace = os.replace
    def denied(source, destination):
        if Path(destination) == store.path:
            raise OSError("Synthetic full disk")
        return real_replace(source, destination)
    monkeypatch.setattr(home_private_storage.os, "replace", denied)
    with pytest.raises(HomeCalendarStorageError) as caught:
        store.create("member:new", event_values())
    assert not caught.value.committed
    assert store.path.read_bytes() == original
    assert store.owned_events("member:new") == []
    assert not list(store.path.parent.glob("*.tmp"))


def test_failed_first_commit_does_not_subsequently_look_new(store, monkeypatch):
    real_replace = os.replace
    def denied(source, destination):
        if Path(destination) == store.path:
            raise PermissionError("Synthetic read-only volume")
        return real_replace(source, destination)
    monkeypatch.setattr(home_private_storage.os, "replace", denied)
    with pytest.raises(HomeCalendarStorageError):
        store.create("member:a", event_values())
    assert not store.path.exists()
    with pytest.raises(HomeCalendarStorageError) as caught:
        HomeCalendarStore(store.path).owned_events("member:a")
    assert caught.value.code == "missing_initialized"


def test_unwritable_lock_blocks_before_mutation(store, seed, monkeypatch):
    original = store.path.read_bytes()
    real_open = Path.open
    def denied(path, *args, **kwargs):
        if path == store.lock_path:
            raise PermissionError("Synthetic lock denial")
        return real_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(HomeCalendarStorageError) as caught:
        store.create("member:new", event_values())
    assert caught.value.code == "io_error"
    assert not caught.value.committed
    assert store.path.read_bytes() == original


def test_error_after_atomic_replace_reports_possible_commit(store, seed, monkeypatch):
    real_sync = home_private_storage._sync_directory
    calls = 0
    def fail_second(path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("Synthetic fsync acknowledgement failure")
        return real_sync(path)
    monkeypatch.setattr(home_private_storage, "_sync_directory", fail_second)
    with pytest.raises(HomeCalendarStorageError) as caught:
        store.create("member:new", event_values())
    assert caught.value.code == "commit_confirmation_failed"
    assert caught.value.committed is True
    assert len(store.owned_events("member:new")) == 1


def test_lock_release_error_does_not_deny_completed_commit(store, seed, monkeypatch):
    if home_calendar.fcntl is None:
        pytest.skip("fcntl unavailable")
    real_flock = home_calendar.fcntl.flock
    def deny_unlock(descriptor, operation):
        real_flock(descriptor, operation)
        if operation == home_calendar.fcntl.LOCK_UN:
            raise OSError("Synthetic unlock acknowledgement failure")
    monkeypatch.setattr(home_calendar.fcntl, "flock", deny_unlock)
    with pytest.raises(HomeCalendarStorageError) as caught:
        store.create("member:new", event_values())
    assert caught.value.committed is True
    assert len(store.owned_events("member:new")) == 1


def test_invalid_mutation_cannot_drop_previous_events(store, seed):
    original = store.path.read_bytes()
    with pytest.raises(HomeCalendarStorageError):
        store._mutate(lambda value: value["events"].append(None))
    assert store.path.read_bytes() == original


def test_parallel_instances_preserve_all_owners(store, seed):
    if home_calendar.fcntl is None:
        pytest.skip("fcntl unavailable")
    def save(index):
        return HomeCalendarStore(store.path).create(f"member:parallel-{index}", event_values())
    with ThreadPoolExecutor(max_workers=4) as executor:
        created = list(executor.map(save, range(12)))
    for event in created:
        assert store.get(event["owner_id"], event["id"]) == event
    assert store.pending_draft("member:b") == seed["drafts"]["member:b"]
    assert len(json.loads(store.path.read_text())["events"]) == 15


def test_confirmation_and_delete_drafts_retain_existing_semantics(store):
    draft = store.save_draft("member:a", event_values())
    assert listed(store) == []
    assert HomeCalendarStore(store.path).pending_draft("member:a") == draft
    created = store.confirm_draft("member:a", draft["id"])
    assert created["reminder_minutes"] == 15
    assert created["starts_at"] == event_values()["starts_at"]
    assert "TRIGGER:-PT15M" in store.export_ics("member:a", created["id"])
    assert store.pending_draft("member:a") is None
    deletion = store.save_delete_draft("member:a", created["id"])
    assert len(listed(store)) == 1
    assert HomeCalendarStore(store.path).pending_draft("member:a") == deletion
    assert store.confirm_draft("member:a", deletion["id"])["deleted"] is True
    assert listed(store) == []
    assert store.pending_draft("member:a") is None


def test_editing_minimal_legacy_event_preserves_optional_absence_and_unknown_metadata(store):
    original = {
        "id": "legacy-minimal", "owner_id": "member:a", "title": "Título antiguo",
        "starts_at": "2026-09-14T08:30:00-04:00", "ends_at": "2026-09-14T09:15:00-04:00",
        "future_metadata": {"must_keep": ["original", None, {"nested": True}]},
    }
    state = {"events": [original], "drafts": {}, "extra_root": "retain"}
    store.path.parent.mkdir(parents=True)
    store.path.write_text(json.dumps(state), encoding="utf-8")
    assert store.get("member:a", original["id"]) == original
    updated = store.update("member:a", original["id"], {
        "title": "Título nuevo", "id": "cannot-change-id", "owner_id": "member:other",
        "source": "cannot-inject-source", "created_at": "cannot-inject-date", "future_metadata": "cannot-replace",
    })
    assert updated["title"] == "Título nuevo"
    assert updated["id"] == original["id"] and updated["owner_id"] == "member:a"
    assert "source" not in updated and "created_at" not in updated
    assert updated["future_metadata"] == original["future_metadata"]
    assert updated["starts_at"] == original["starts_at"] and updated["ends_at"] == original["ends_at"]
    assert HomeCalendarStore(store.path).get("member:a", original["id"]) == updated
    assert json.loads(store.path.read_text())["extra_root"] == "retain"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-calendar-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "calendarqa")
    for key, filename in {
        "ROXY_HOME_CALENDAR_PATH": "calendar.json", "ROXY_HOME_CALENDAR_SYNC_PATH": "sync.json",
        "ROXY_HOME_ACCOUNTS_PATH": "accounts.json", "ROXY_SHOPPING_LIST_PATH": "shopping.json",
        "ROXY_HOME_MEMORY_PATH": "food.json",
    }.items():
        monkeypatch.setenv(key, str(tmp_path / filename))
    from tools import roxy_home_service as service
    service._RATE_STATE.clear()
    client = TestClient(service.app, base_url="https://roxy.test", headers={"Authorization": "Bearer synthetic-calendar-key"})
    return client, service, tmp_path / "calendar.json"


@pytest.mark.parametrize("raw", [b"{broken", b"\xff", b'{"events":[null],"drafts":{}}'])
def test_existing_http_handler_returns_503_not_empty_calendar(api, raw):
    client, _, path = api
    path.write_bytes(raw)
    response = client.get("/v1/home-calendar/calendarqa", params={"start": "2026-09-14T00:00:00-04:00", "end": "2026-09-15T00:00:00-04:00"})
    assert response.status_code == 503
    assert response.json()["code"] == "HOME_STORAGE_UNAVAILABLE"
    assert str(path) not in response.text
    assert "events" not in response.json()
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["retry-after"] == "30"
    assert path.read_bytes() == raw
    mutation = client.post("/v1/home-calendar/calendarqa/drafts", json=event_values())
    assert mutation.status_code == 503
    assert path.read_bytes() == raw


def test_http_storage_error_does_not_bypass_authentication(api):
    _, service, path = api
    path.write_bytes(b"{broken")
    response = TestClient(service.app, base_url="https://roxy.test").get("/v1/home-calendar/calendarqa", params={"start": "2026-09-14T00:00:00Z", "end": "2026-09-15T00:00:00Z"})
    assert response.status_code == 401
