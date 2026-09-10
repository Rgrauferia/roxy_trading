"""Fail-closed regression checks: only disposable synthetic household files."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from roxy_os import home_private_storage
from roxy_os import home_family, home_commerce
from roxy_os.home_family import HomeFamilyStorageError, HomeFamilyStore
from roxy_os.home_commerce import HomeCommerceStorageError, HomeCommerceStore


@pytest.fixture(params=["family", "commerce"])
def case(tmp_path, request):
    family = request.param == "family"
    cls, error = (HomeFamilyStore, HomeFamilyStorageError) if family else (HomeCommerceStore, HomeCommerceStorageError)
    store = cls(tmp_path / "persistent" / f"{request.param}.json")
    if family:
        seed = {
            "schema_version": 3, "links": {"guest": "house-b"},
            "households": {
                "house-a": {
                    "members": {"person-a": {"sharing_enabled": False, "location": None, "history": [], "profile": {"photo_data_url": "synthetic-photo", "display_name": "Persona A"}}},
                    "directory": {"person-a": {"id": "person-a", "display_name": "Persona A", "role": "OWNER", "avatar": "", "external": False}},
                    "places": {}, "alerts": [], "extension": {"retained": True},
                },
                "house-b": {"external_members": {"guest": {"id": "guest", "display_name": "Invitado"}}, "members": {}},
            },
            "future_field": {"keep": [1, 2, 3]},
        }
        def read(instance):
            return instance.snapshot("house-a", [], "person-a")
        def get_write(instance):
            # Exact store operation invoked by GET /v1/home-family.
            instance.remember_household_members("house-a", [{"id": "person-a", "display_name": "Persona A", "role": "OWNER"}])
    else:
        seed = {
            "schema_version": 2,
            "profiles": {"member:person-a": {"postal_code": "00000", "extension": {"retained": True}}, "member:person-b": {"postal_code": "99999"}},
            "preparations": {"prep": {"id": "prep", "owner_key": "member:person-b", "items": [{"name": "Artículo sintético"}], "providers": ["synthetic"]}},
            "handoffs": {"handoff": {"id": "handoff", "owner_key": "member:person-b", "preparation_id": "prep"}},
            "future_field": {"keep": [1, 2, 3]},
        }
        def read(instance):
            return instance.profile("member:person-a")
        def get_write(instance):
            # Exact store operation invoked by GET commerce recommendations.
            return instance.record_price_recommendations("member:person-a", [])
    return SimpleNamespace(store=store, cls=cls, error=error, seed=seed, read=read, get_write=get_write, family=family)


def seed_file(case, payload=None):
    case.store.path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(case.seed if payload is None else payload, ensure_ascii=False).encode("utf-8")
    case.store.path.write_bytes(raw)
    return raw


def test_new_store_read_does_not_create_state_or_marker(case):
    case.read(case.store)
    assert case.store.storage_status() == "NEW"
    assert not case.store.path.exists()
    assert not home_private_storage.initialized_marker(case.store.path).exists()
    assert not case.store.lock_path.exists()


def test_valid_legacy_read_is_byte_preserving_and_restart_retains_every_namespace(case, tmp_path, monkeypatch):
    raw = seed_file(case)
    case.read(case.store)
    assert case.store.storage_status() == "READY"
    assert case.store.path.read_bytes() == raw
    assert not home_private_storage.initialized_marker(case.store.path).exists()
    case.get_write(case.store)
    state = json.loads(case.store.path.read_text())
    assert state["future_field"] == case.seed["future_field"]
    if case.family:
        assert state == case.seed
    else:
        for key in ("profiles", "preparations", "handoffs"):
            assert state[key] == case.seed[key]
        assert state["schema_version"] == 3
    other_cwd = tmp_path / "new-worker"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)
    restarted = case.cls(case.store.path)
    assert case.read(restarted) == case.read(case.store)
    assert restarted.storage_status() == "READY"
    assert home_private_storage.initialized_marker(case.store.path).read_text() == "1\n"
    assert case.store.path.stat().st_mode & 0o777 == 0o600
    assert case.store.lock_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("raw", [
    b"{broken", b"", b"\xff\xfe", b"null", b"[]", b"{}",
    b'{"households":{},"households":{"discarded":{}},"profiles":{},"preparations":{},"handoffs":{}}',
    b'{"households":{},"profiles":{},"preparations":{},"handoffs":{},"bad":NaN}',
    b'{"schema_version":99,"households":{},"profiles":{},"preparations":{},"handoffs":{}}',
    b'{"schema_version":true,"households":{},"profiles":{},"preparations":{},"handoffs":{}}',
])
def test_corruption_never_becomes_empty_or_overwritten_by_get_operation(case, raw):
    case.store.path.parent.mkdir(parents=True)
    case.store.path.write_bytes(raw)
    for operation in (case.read, case.get_write):
        with pytest.raises(case.error):
            operation(case.store)
        assert case.store.path.read_bytes() == raw
    assert not home_private_storage.initialized_marker(case.store.path).exists()
    assert not list(case.store.path.parent.glob("*.tmp"))


@pytest.mark.parametrize("bad_kind", ["collection", "record", "nested", "id", "consent"])
def test_malformed_nested_data_is_not_silently_discarded(case, bad_kind):
    state = deepcopy(case.seed)
    if case.family:
        house = state["households"]["house-a"]
        if bad_kind == "collection": house["directory"] = None
        elif bad_kind == "record": house["members"]["person-a"] = []
        elif bad_kind == "nested": house["members"]["person-a"]["history"] = [None]
        elif bad_kind == "id": house["directory"]["person-a"]["id"] = "other-person"
        else: house["members"]["person-a"]["sharing_enabled"] = "false"
    else:
        if bad_kind == "collection": state["profiles"] = None
        elif bad_kind == "record": state["preparations"]["prep"] = []
        elif bad_kind == "nested": state["price_history"] = {"member:person-a": [None]}
        elif bad_kind == "id": state["preparations"]["prep"]["id"] = "other-prep"
        else: state["profiles"]["member:person-a"]["location_enabled"] = "false"
    raw = seed_file(case, state)
    for operation in (case.read, case.get_write):
        with pytest.raises(case.error) as caught:
            operation(case.store)
        assert caught.value.code == "invalid_structure"
        assert case.store.path.read_bytes() == raw


def test_initialized_file_disappearance_is_not_a_new_store(case):
    case.get_write(case.store)
    case.store.path.unlink()  # Exact disposable test fixture, never live data.
    restarted = case.cls(case.store.path)
    for operation in (case.read, case.get_write):
        with pytest.raises(case.error) as caught:
            operation(restarted)
        assert caught.value.code == "missing_initialized"
        assert not case.store.path.exists()


def test_unreadable_state_fails_closed_for_read_and_get_mutation(case, monkeypatch):
    original = seed_file(case)
    real_read = Path.read_text
    def denied(path, *args, **kwargs):
        if path == case.store.path:
            raise PermissionError("Synthetic sensitive path must not reach client")
        return real_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", denied)
    for operation in (case.read, case.get_write):
        with pytest.raises(case.error) as caught:
            operation(case.store)
        assert caught.value.code == "unreadable"
        assert "sensitive path" not in str(caught.value)
        assert case.store.path.read_bytes() == original


def test_replace_failure_preserves_original_and_cleans_temporary_file(case, monkeypatch):
    original = seed_file(case)
    real_replace = os.replace
    def denied(source, destination):
        if Path(destination) == case.store.path:
            raise PermissionError("Synthetic read-only volume")
        return real_replace(source, destination)
    monkeypatch.setattr(home_private_storage.os, "replace", denied)
    with pytest.raises(case.error) as caught:
        case.get_write(case.store)
    assert not caught.value.committed
    assert case.store.path.read_bytes() == original
    assert not list(case.store.path.parent.glob("*.tmp"))
    assert case.store.storage_status() == "READY"


def test_first_failed_commit_marks_missing_state_unavailable(case, monkeypatch):
    real_replace = os.replace
    def denied(source, destination):
        if Path(destination) == case.store.path:
            raise OSError("Synthetic full volume")
        return real_replace(source, destination)
    monkeypatch.setattr(home_private_storage.os, "replace", denied)
    with pytest.raises(case.error):
        case.get_write(case.store)
    assert not case.store.path.exists()
    with pytest.raises(case.error) as caught:
        case.read(case.cls(case.store.path))
    assert caught.value.code == "missing_initialized"


def test_unwritable_lock_returns_storage_error_without_overwriting(case, monkeypatch):
    original = seed_file(case)
    real_open = Path.open
    def denied(path, *args, **kwargs):
        if path == case.store.lock_path:
            raise PermissionError("Synthetic lock denial")
        return real_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(case.error) as caught:
        case.get_write(case.store)
    assert caught.value.code == "io_error"
    assert not caught.value.committed
    assert case.store.path.read_bytes() == original


def test_directory_fsync_failure_after_replace_does_not_claim_no_commit(case, monkeypatch):
    seed_file(case)
    real_sync = home_private_storage._sync_directory
    calls = 0
    def fail_last(path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("Synthetic commit acknowledgement failure")
        return real_sync(path)
    monkeypatch.setattr(home_private_storage, "_sync_directory", fail_last)
    with pytest.raises(case.error) as caught:
        case.get_write(case.store)
    assert caught.value.code == "commit_confirmation_failed"
    assert caught.value.committed is True
    assert "puede haberse guardado" in str(caught.value)
    assert case.store.storage_status() == "READY"


def test_invalid_callback_output_cannot_overwrite_valid_state(case):
    original = seed_file(case)
    def corrupt(value):
        value["households" if case.family else "profiles"] = []
    with pytest.raises(case.error):
        (case.store._locked if case.family else case.store._mutate)(corrupt)
    assert case.store.path.read_bytes() == original


def test_lock_release_failure_after_commit_reports_uncertain_acknowledgement(case, monkeypatch):
    module = home_family if case.family else home_commerce
    if module.fcntl is None:
        pytest.skip("fcntl not available on this platform")
    seed_file(case)
    real_flock = module.fcntl.flock
    def denied_unlock(descriptor, operation):
        real_flock(descriptor, operation)
        if operation == module.fcntl.LOCK_UN:
            raise OSError("Synthetic lock release acknowledgement failure")
    monkeypatch.setattr(module.fcntl, "flock", denied_unlock)
    with pytest.raises(case.error) as caught:
        case.get_write(case.store)
    assert caught.value.committed is True
    assert case.store.storage_status() == "READY"


def test_existing_cross_instance_locks_preserve_parallel_namespaces(case):
    module = home_family if case.family else home_commerce
    if module.fcntl is None:
        pytest.skip("fcntl not available on this platform")
    seed_file(case)
    def update(index):
        instance = case.cls(case.store.path)
        owner = f"synthetic-{index}"
        if case.family:
            instance.remember_household_members(owner, [{"id": owner, "display_name": owner}])
        else:
            instance.record_price_recommendations(owner, [])
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(update, range(12)))
    state = json.loads(case.store.path.read_text())
    collection = state["households"] if case.family else state["price_history"]
    assert all(f"synthetic-{index}" in collection for index in range(12))
    assert state["future_field"] == case.seed["future_field"]
