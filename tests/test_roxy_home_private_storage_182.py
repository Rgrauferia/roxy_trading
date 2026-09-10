"""Restart/failure checks use disposable synthetic files, never customer data."""
import base64
import json
import os
from pathlib import Path

import pytest

from roxy_os import home_private_storage
from roxy_os.home_design import HomeDesignStorageError, HomeDesignStore
from roxy_os.home_plants import HomePlantStorageError, HomePlantStore


PNG = b"\x89PNG\r\n\x1a\nsynthetic-private-photo"
PHOTO = "data:image/png;base64," + base64.b64encode(PNG).decode("ascii")


@pytest.fixture(params=["plants", "design"])
def case(tmp_path, request):
    cls, error = (HomePlantStore, HomePlantStorageError) if request.param == "plants" else (HomeDesignStore, HomeDesignStorageError)
    store = cls(tmp_path / "persistent" / f"{request.param}.json", tmp_path / "persistent" / "images")
    values = {"photo_data_url": PHOTO, "species_key": "pothos", "display_name": "Planta sintética", "room_type": "living_room", "style": "warm_modern", "budget": 0}
    def rows(instance=None, owner="synthetic"):
        instance = instance or store
        return instance.snapshot(owner, owner)["plants"] if request.param == "plants" else instance.projects(owner)
    return store, cls, error, values, rows


def test_missing_never_initialized_is_new_and_read_does_not_create_files(case):
    store, _, _, _, rows = case
    assert rows() == []
    assert store.storage_status() == "NEW"
    assert not store.path.exists()
    assert not home_private_storage.initialized_marker(store.path).exists()


def test_restart_retains_namespace_original_photo_and_ready_state(case, tmp_path, monkeypatch):
    store, cls, _, values, rows = case
    created = store.create("synthetic", "synthetic", values)
    original = store.path.read_bytes()
    # Equivalent to a new worker in another working directory using the same disk.
    other_cwd = tmp_path / "new-container"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)
    restarted = cls(store.path, store.image_root)
    assert rows(restarted)[0]["id"] == created["id"]
    assert restarted.storage_status() == "READY"
    assert rows(restarted, "another-household") == []
    assert Path(created["photo_path"]).read_bytes() == PNG
    assert store.path.read_bytes() == original
    assert home_private_storage.initialized_marker(store.path).read_text() == "1\n"
    assert store.path.stat().st_mode & 0o777 == 0o600
    assert Path(created["photo_path"]).stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("raw", [b"{not json", b"", b"\xff\xfe", b"null", b"[]", b"{}", b'{"schema_version":2,"households":{},"projects":{}}', b'{"households":{},"households":{"lost":{}},"projects":{}}', b'{"households":{},"projects":{},"bad":NaN}'])
def test_corrupt_or_unknown_structure_fails_closed_without_overwrite_or_media(case, raw):
    store, _, error, values, rows = case
    store.path.parent.mkdir(parents=True)
    store.path.write_bytes(raw)
    for operation in (rows, lambda: store.create("synthetic", "synthetic", values)):
        with pytest.raises(error):
            operation()
        assert store.path.read_bytes() == raw
    assert not store.image_root.exists()


@pytest.mark.parametrize("mutation", ["nested_null", "bad_id", "bad_row"])
def test_malformed_nested_records_are_not_silently_dropped(case, mutation):
    store, _, error, values, rows = case
    created = store.create("synthetic", "synthetic", values)
    state = json.loads(store.path.read_text())
    collection = state["households"]["synthetic"]["plants"] if isinstance(store, HomePlantStore) else state["projects"]["synthetic"]
    if mutation == "bad_id":
        collection[created["id"]]["id"] = "different-id"
    elif mutation == "bad_row":
        collection[created["id"]] = []
    elif isinstance(store, HomePlantStore):
        state["households"]["synthetic"]["plants"] = None
    else:
        state["projects"]["synthetic"] = None
    raw = json.dumps(state).encode()
    store.path.write_bytes(raw)
    with pytest.raises(error):
        rows()
    with pytest.raises(error):
        store.create("synthetic", "synthetic", values)
    assert store.path.read_bytes() == raw
    assert Path(created["photo_path"]).read_bytes() == PNG


def test_initialized_state_disappearance_is_not_a_fresh_empty_store(case):
    store, cls, error, values, rows = case
    created = store.create("synthetic", "synthetic", values)
    store.path.unlink()  # Only this test's disposable synthetic JSON.
    restarted = cls(store.path, store.image_root)
    with pytest.raises(error) as caught:
        rows(restarted)
    assert caught.value.code == "missing_initialized"
    with pytest.raises(error):
        restarted.create("synthetic", "synthetic", values)
    assert not store.path.exists()
    assert Path(created["photo_path"]).read_bytes() == PNG


def test_read_permission_failure_never_returns_empty_or_writes_photos(case, monkeypatch):
    store, _, error, values, rows = case
    created = store.create("synthetic", "synthetic", values)
    original = store.path.read_bytes()
    before = set(store.image_root.rglob("*"))
    actual = Path.read_text
    def denied(path, *args, **kwargs):
        if path == store.path:
            raise PermissionError("Synthetic permission denial")
        return actual(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", denied)
    with pytest.raises(error) as caught:
        rows()
    assert caught.value.code == "unreadable"
    with pytest.raises(error):
        store.create("synthetic", "synthetic", values)
    assert store.path.read_bytes() == original
    assert set(store.image_root.rglob("*")) == before
    assert Path(created["photo_path"]).read_bytes() == PNG


def test_write_protected_state_does_not_replace_json_or_keep_uncommitted_photo(case, monkeypatch):
    store, _, error, values, rows = case
    created = store.create("synthetic", "synthetic", values)
    original = store.path.read_bytes()
    original_files = {p for p in store.image_root.rglob("*") if p.is_file()}
    actual = os.replace
    def denied(source, destination):
        if Path(destination) == store.path:
            raise PermissionError("Synthetic read-only volume")
        return actual(source, destination)
    monkeypatch.setattr(home_private_storage.os, "replace", denied)
    with pytest.raises(error):
        store.create("synthetic", "synthetic", values)
    assert store.path.read_bytes() == original
    assert len(rows()) == 1
    assert {p for p in store.image_root.rglob("*") if p.is_file()} == original_files
    assert Path(created["photo_path"]).read_bytes() == PNG
    assert list(store.path.parent.glob("*.tmp")) == []


def test_unwritable_media_does_not_acknowledge_or_mutate_state(case, monkeypatch):
    store, _, error, values, rows = case
    created = store.create("synthetic", "synthetic", values)
    original = store.path.read_bytes()
    actual = os.open
    def denied(path, *args, **kwargs):
        if str(path).startswith(str(store.image_root)) and str(path).endswith("original.png"):
            raise PermissionError("Synthetic media directory denial")
        return actual(path, *args, **kwargs)
    monkeypatch.setattr(home_private_storage.os, "open", denied)
    with pytest.raises(error):
        store.create("synthetic", "synthetic", values)
    assert store.path.read_bytes() == original
    assert len(rows()) == 1
    assert Path(created["photo_path"]).read_bytes() == PNG


def test_failure_after_atomic_replace_keeps_committed_media(case, monkeypatch):
    store, cls, error, values, rows = case
    actual = home_private_storage._sync_directory
    calls = 0
    def fail_last(path):
        nonlocal calls
        if path == store.path.parent:
            calls += 1
            if calls == 2:
                raise OSError("Synthetic post-commit fsync failure")
        return actual(path)
    monkeypatch.setattr(home_private_storage, "_sync_directory", fail_last)
    with pytest.raises(error) as caught:
        store.create("synthetic", "synthetic", values)
    assert caught.value.committed is True
    assert caught.value.code == "commit_confirmation_failed"
    restarted = cls(store.path, store.image_root)
    persisted = rows(restarted)
    assert len(persisted) == 1
    private = restarted.plant("synthetic", persisted[0]["id"]) if isinstance(restarted, HomePlantStore) else persisted[0]
    assert Path(private["photo_path"]).read_bytes() == PNG


def test_marker_survives_first_commit_failure_and_blocks_silent_reinitialization(case, monkeypatch):
    store, cls, error, values, rows = case
    actual = os.replace
    def denied(source, destination):
        if Path(destination) == store.path:
            raise PermissionError("Synthetic first commit failure")
        return actual(source, destination)
    monkeypatch.setattr(home_private_storage.os, "replace", denied)
    with pytest.raises(error):
        store.create("synthetic", "synthetic", values)
    assert not store.path.exists()
    assert home_private_storage.initialized_marker(store.path).exists()
    with pytest.raises(error) as caught:
        rows(cls(store.path, store.image_root))
    assert caught.value.code == "missing_initialized"


def test_unreadable_initialization_marker_does_not_look_like_new_store(case, monkeypatch):
    store, _, error, _, rows = case
    actual = Path.lstat
    def denied(path, *args, **kwargs):
        if path == home_private_storage.initialized_marker(store.path):
            raise PermissionError("Synthetic marker permission denial")
        return actual(path, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", denied)
    with pytest.raises(error):
        rows()
    assert not store.path.exists()


def test_broken_state_symlink_is_not_treated_as_an_unused_store(case):
    store, _, error, _, rows = case
    store.path.parent.mkdir(parents=True)
    store.path.symlink_to(store.path.parent / "missing-synthetic-target.json")
    with pytest.raises(error):
        rows()
    assert store.path.is_symlink()


def test_lock_permission_failure_blocks_mutation_and_preserves_json(case, monkeypatch):
    store, _, error, values, _ = case
    store.create("synthetic", "synthetic", values)
    before = store.path.read_bytes()
    actual = Path.open
    def denied(path, *args, **kwargs):
        if path == store.lock_path:
            raise PermissionError("Synthetic lock denial")
        return actual(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", denied)
    with pytest.raises(error):
        store.create("synthetic", "synthetic", values)
    assert store.path.read_bytes() == before


def test_failed_plant_journal_commit_preserves_original_and_prior_notes(tmp_path, monkeypatch):
    store = HomePlantStore(tmp_path / "plants.json", tmp_path / "images")
    plant = store.create("synthetic", "synthetic", {"photo_data_url": PHOTO, "species_key": "pothos"})
    first = store.add_journal("synthetic", plant["id"], "synthetic", "Nota anterior", PHOTO)
    original = store.path.read_bytes()
    actual = os.replace
    def denied(source, destination):
        if Path(destination) == store.path:
            raise PermissionError("Synthetic journal commit denial")
        return actual(source, destination)
    monkeypatch.setattr(home_private_storage.os, "replace", denied)
    with pytest.raises(HomePlantStorageError):
        store.add_journal("synthetic", plant["id"], "synthetic", "Nota nueva", PHOTO)
    assert store.path.read_bytes() == original
    assert Path(plant["photo_path"]).read_bytes() == PNG
    assert Path(first["photo_path"]).read_bytes() == PNG
    assert len(list((Path(plant["photo_path"]).parent / "journal").iterdir())) == 1


def test_design_rejected_proposal_commit_preserves_previous_image(tmp_path, monkeypatch):
    store = HomeDesignStore(tmp_path / "design.json", tmp_path / "images")
    project = store.create("synthetic", "synthetic", {"photo_data_url": PHOTO, "room_type": "living_room", "style": "warm_modern"})
    first = store.save_proposal("synthetic", project["id"], base64.b64encode(PNG).decode())
    before = store.path.read_bytes()
    original_proposal = Path(first["proposal_path"])
    actual = os.replace
    def denied(source, destination):
        if Path(destination) == store.path:
            raise PermissionError("Synthetic JSON write denial")
        return actual(source, destination)
    monkeypatch.setattr(home_private_storage.os, "replace", denied)
    with pytest.raises(HomeDesignStorageError):
        store.save_proposal("synthetic", project["id"], base64.b64encode(PNG + b"second").decode())
    assert store.path.read_bytes() == before
    assert original_proposal.read_bytes() == PNG
    assert list(original_proposal.parent.glob("proposal-*.png")) == [original_proposal]


def test_container_defaults_and_blueprint_keep_private_state_and_media_on_disk():
    root = Path(__file__).resolve().parents[1]
    docker = (root / "Dockerfile.roxy-home").read_text()
    blueprint = (root / "render.yaml").read_text().split("name: roxy-home\n", 1)[1].split("  - type: web", 1)[0]
    expected = {"ROXY_HOME_PLANTS_PATH": "/var/data/roxy_home/plants.json", "ROXY_HOME_PLANTS_IMAGE_DIR": "/var/data/roxy_home/plants", "ROXY_HOME_DESIGN_PATH": "/var/data/roxy_home/design.json", "ROXY_HOME_DESIGN_IMAGE_DIR": "/var/data/roxy_home/design"}
    for key, path in expected.items():
        assert f"{key}={path}" in docker
        assert f"- key: {key}\n        value: {path}" in blueprint
    assert "mountPath: /var/data" in blueprint
