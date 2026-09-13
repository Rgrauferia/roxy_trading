import json

import pytest

from roxy_os.home_accounts import HomeAccountStorageError, HomeAccountStore
from roxy_os.home_private_storage import initialized_marker


def bootstrap(store):
    return store.bootstrap("storage-test", household_name="Casa", username="owner", display_name="Owner", password="test-password")


@pytest.fixture(autouse=True)
def faster_test_passwords(monkeypatch):
    monkeypatch.setattr("roxy_os.home_accounts.PASSWORD_ITERATIONS", 100_000)


def test_virgin_path_can_be_created_and_is_marked_before_use(tmp_path):
    store = HomeAccountStore(tmp_path / "accounts.json")
    assert store.household_configured("storage-test") is False
    assert not initialized_marker(store.path).exists()
    bootstrap(store)
    assert initialized_marker(store.path).read_text() == "1\n"
    assert (initialized_marker(store.path).stat().st_mode & 0o777) == 0o600


def test_missing_initialized_file_does_not_reset_accounts_or_trial_admission(tmp_path):
    store = HomeAccountStore(tmp_path / "accounts.json")
    owner = bootstrap(store)
    saved = store.path.read_bytes()
    backup = tmp_path / "accounts.saved.json"
    store.path.rename(backup)
    reloaded = HomeAccountStore(store.path)
    operations = [
        lambda: reloaded.member(owner["id"]),
        lambda: reloaded.authenticate("owner", "test-password"),
        lambda: reloaded.household_configured("storage-test"),
        lambda: bootstrap(reloaded),
        lambda: reloaded.register_trial(username="new-trial", display_name="New", password="test-password", admission_hash="same-admission"),
    ]
    for operation in operations:
        with pytest.raises(HomeAccountStorageError):
            operation()
    assert not store.path.exists()
    assert backup.read_bytes() == saved


def test_legacy_first_read_creates_only_marker_and_preserves_bytes(tmp_path):
    source = HomeAccountStore(tmp_path / "source.json")
    owner = bootstrap(source)
    path = tmp_path / "legacy.json"
    prior = source.path.read_bytes()
    path.write_bytes(prior)
    store = HomeAccountStore(path)
    assert not initialized_marker(path).exists()
    assert store.member(owner["id"])["display_name"] == "Owner"
    assert path.read_bytes() == prior
    assert initialized_marker(path).exists()
    backup = tmp_path / "legacy.saved.json"
    path.rename(backup)
    with pytest.raises(HomeAccountStorageError):
        store.register_trial(username="trial", display_name="Trial", password="test-password", admission_hash="test")
    assert backup.read_bytes() == prior and not path.exists()


def test_interruption_after_marker_before_identity_commit_fails_closed(tmp_path, monkeypatch):
    store = HomeAccountStore(tmp_path / "accounts.json")
    def fail_replace(source, target):
        assert initialized_marker(store.path).exists()
        raise OSError("synthetic interrupted commit")
    monkeypatch.setattr("roxy_os.home_private_storage.os.replace", fail_replace)
    with pytest.raises(HomeAccountStorageError):
        bootstrap(store)
    assert initialized_marker(store.path).exists()
    assert not store.path.exists()
    with pytest.raises(HomeAccountStorageError):
        bootstrap(HomeAccountStore(store.path))


def test_existing_accounts_survive_failed_atomic_replacement(tmp_path, monkeypatch):
    store = HomeAccountStore(tmp_path / "accounts.json")
    owner = bootstrap(store)
    prior = store.path.read_bytes()
    def fail_replace(*_):
        raise OSError("synthetic full disk")
    monkeypatch.setattr("roxy_os.home_private_storage.os.replace", fail_replace)
    with pytest.raises(HomeAccountStorageError):
        store.update_personalization(owner["id"], display_name="Changed", preferences={})
    assert store.path.read_bytes() == prior


@pytest.mark.parametrize("raw", [b"not-json", b"\xff", b'{"households": {}, "members": {}, "members": {}}', b'{"households": {}, "members": {}, "unknown": NaN}'])
def test_corrupt_accounts_are_not_replaced_or_marked_as_valid(tmp_path, raw):
    path = tmp_path / "legacy.json"
    path.write_bytes(raw)
    store = HomeAccountStore(path)
    with pytest.raises(HomeAccountStorageError):
        bootstrap(store)
    assert path.read_bytes() == raw
    assert not initialized_marker(path).exists()


def test_confirmed_trial_admission_count_survives_storage_failure(tmp_path):
    store = HomeAccountStore(tmp_path / "accounts.json")
    store.register_trial(username="trial", display_name="Trial", password="test-password", admission_hash="connection")
    saved = json.loads(store.path.read_text())
    backup = tmp_path / "accounts.saved.json"
    store.path.rename(backup)
    with pytest.raises(HomeAccountStorageError):
        store.register_trial(username="trial-next", display_name="Trial", password="test-password", admission_hash="connection")
    assert json.loads(backup.read_text()) == saved
    assert len(saved["households"]) == 1
