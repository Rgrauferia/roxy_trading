from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import re

import pytest

from roxy_os import home_accounts
from roxy_os.home_accounts import HomeAccountStorageError, HomeAccountStore


PASSWORD = "synthetic-original-password"
NEW_PASSWORD = "synthetic-new-password"


@pytest.fixture(autouse=True)
def inexpensive_synthetic_passwords(monkeypatch):
    monkeypatch.setattr(home_accounts, "PASSWORD_ITERATIONS", 100_000)


@pytest.fixture
def account(tmp_path):
    store = HomeAccountStore(tmp_path / "accounts.json")
    owner = store.bootstrap("recovery-fixture", household_name="Synthetic home", username="owner",
                            display_name="Owner", password=PASSWORD)
    partner = store.add_member(owner["id"], username="partner", display_name="Partner", password=PASSWORD)
    return store, owner, partner


def read(store):
    return json.loads(store.path.read_text())


def codes_for(store, member):
    return store.rotate_recovery_codes(member["id"], PASSWORD, expected_session_version=member["session_version"])["recovery_codes"]


def test_legacy_member_version_defaults_to_zero_without_rewriting_accounts(account):
    store, owner, _ = account
    data = read(store)
    del data["members"][owner["id"]]["session_version"]
    store.path.write_text(json.dumps(data))
    before = store.path.read_bytes()
    assert store.member(owner["id"])["session_version"] == 0
    assert store.recovery_status(owner["id"]) == {"enabled": False, "remaining": 0, "generated_at": None}
    assert store.path.read_bytes() == before


def test_bootstrap_keeps_recovery_opt_in_and_trial_issues_codes_atomically(tmp_path, monkeypatch):
    store = HomeAccountStore(tmp_path / "accounts.json")
    member = store.bootstrap("legacy", household_name="Home", username="legacy", display_name="Legacy", password=PASSWORD)
    assert "recovery_codes" not in member
    assert "recovery" not in read(store)["members"][member["id"]]
    writes = []
    original = store._write_unlocked
    def record(payload):
        writes.append(deepcopy(payload))
        original(payload)
    monkeypatch.setattr(store, "_write_unlocked", record)
    trial = store.register_trial(username="trial", display_name="Trial", password=PASSWORD, admission_hash="synthetic-connection")
    assert len(writes) == 1
    private = writes[0]["members"][trial["id"]]
    assert private["recovery"]["hashes"] and private["session_version"] == 0
    assert trial["household_id"] in writes[0]["households"]
    assert len(trial["recovery_codes"]) == 8
    status = store.recovery_status(trial["id"])
    assert status["enabled"] is True and status["remaining"] == 8 and status["generated_at"]


def test_codes_have_128_random_bits_are_unique_and_only_hashes_are_persisted(account, monkeypatch):
    store, owner, _ = account
    requested_bytes = []
    original = home_accounts.secrets.token_hex
    def token_hex(length):
        requested_bytes.append(length)
        return original(length)
    monkeypatch.setattr(home_accounts.secrets, "token_hex", token_hex)
    codes = codes_for(store, owner)
    assert requested_bytes == [16] * 8
    assert len(set(codes)) == 8
    assert all(re.fullmatch(r"[A-F0-9]{8}(?:-[A-F0-9]{8}){3}", code) for code in codes)
    raw = store.path.read_text()
    state = read(store)["members"][owner["id"]]["recovery"]
    assert len(set(state["hashes"])) == 8
    for code, digest in zip(codes, state["hashes"]):
        normalized = code.replace("-", "").lower()
        assert code not in raw and normalized not in raw
        assert digest == hashlib.sha256(("roxy-home-recovery-v1\0" + owner["id"] + "\0" + normalized).encode("ascii")).hexdigest()
    assert (store.path.stat().st_mode & 0o777) == 0o600


def test_public_responses_never_expose_recovery_material_or_status(account):
    store, owner, partner = account
    codes = codes_for(store, owner)
    responses = [store.member(owner["id"]), store.members(partner["id"]), store.authenticate("owner", PASSWORD)]
    text = json.dumps(responses)
    assert '"recovery"' not in text and '"recovery_codes"' not in text
    assert '"generated_at"' not in text and '"remaining"' not in text
    assert "password_hash" not in text
    assert all(code not in text for code in codes)
    assert all(value not in text for value in read(store)["members"][owner["id"]]["recovery"]["hashes"])
    assert all(row["session_version"] == 0 for row in store.members(owner["id"]))


def test_rotation_invalidates_previous_batch_without_changing_password_or_session_version(account):
    store, owner, _ = account
    old = codes_for(store, owner)
    previous_password_hash = read(store)["members"][owner["id"]]["password_hash"]
    result = store.rotate_recovery_codes(owner["id"], PASSWORD, expected_session_version=0)
    assert set(old).isdisjoint(result["recovery_codes"])
    before = store.path.read_bytes()
    assert store.reset_password_with_recovery("owner", old[0], NEW_PASSWORD) is False
    assert store.path.read_bytes() == before
    member = read(store)["members"][owner["id"]]
    assert member["password_hash"] == previous_password_hash and member["session_version"] == 0
    assert store.authenticate("owner", PASSWORD)


@pytest.mark.parametrize("current_password", ["wrong-password", "", None, False, [PASSWORD]])
def test_rotation_rejects_wrong_password_without_any_account_mutation(account, current_password):
    store, owner, _ = account
    codes_for(store, owner)
    before = store.path.read_bytes()
    with pytest.raises(PermissionError):
        store.rotate_recovery_codes(owner["id"], current_password, expected_session_version=0)
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("expected_version", [True, "0", -1, 1])
def test_rotation_rejects_malformed_or_stale_session_version(account, expected_version):
    store, owner, _ = account
    before = store.path.read_bytes()
    with pytest.raises(PermissionError):
        store.rotate_recovery_codes(owner["id"], PASSWORD, expected_session_version=expected_version)
    assert store.path.read_bytes() == before


def test_reset_preserves_household_other_members_and_private_profiles(account):
    store, owner, partner = account
    codes = codes_for(store, owner)
    data = read(store)
    data["members"][owner["id"]]["recipe_profile"] = {"future": "private preferences kept"}
    data["members"][owner["id"]]["photo"] = "synthetic-photo-reference"
    data["members"][owner["id"]]["unknown_future_field"] = {"keep": True}
    data["households"][owner["household_id"]]["other_metadata"] = {"keep": "household data"}
    store.path.write_text(json.dumps(data))
    assert store.reset_password_with_recovery("OWNER", codes[3], NEW_PASSWORD) is True
    after = read(store)
    assert after["households"] == data["households"]
    assert after["members"][partner["id"]] == data["members"][partner["id"]]
    for key, value in data["members"][owner["id"]].items():
        if key not in {"password_hash", "session_version", "recovery"}:
            assert after["members"][owner["id"]][key] == value
    assert after["members"][owner["id"]]["session_version"] == 1
    assert after["members"][owner["id"]]["password_hash"] != data["members"][owner["id"]]["password_hash"]
    assert after["members"][owner["id"]]["password_changed_at"]
    assert store.authenticate("owner", PASSWORD) is None
    assert store.authenticate("owner", NEW_PASSWORD)["session_version"] == 1
    assert store.recovery_status(owner["id"])["remaining"] == 0
    assert store.recovery_status(owner["id"])["enabled"] is False
    assert NEW_PASSWORD not in store.path.read_text()
    before = store.path.read_bytes()
    for code in codes:
        assert store.reset_password_with_recovery("owner", code, "synthetic-next-password") is False
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("formatting", ["uppercase", "lowercase", "compact", "spaces", "pasted_whitespace"])
def test_normalization_preserves_all_code_bits(account, formatting):
    store, owner, _ = account
    code = codes_for(store, owner)[0]
    variations = {
        "uppercase": code.upper(), "lowercase": code.lower(), "compact": code.replace("-", ""),
        "spaces": code.replace("-", " "), "pasted_whitespace": "\t " + code + "\r\n",
    }
    assert store.reset_password_with_recovery("owner", variations[formatting], NEW_PASSWORD) is True


@pytest.mark.parametrize("mutation", ["prefix", "suffix", "punctuation", "unicode_hex", "missing_digit", "extra_digit", "null", "list"])
def test_invalid_code_format_never_discards_data_to_match(account, mutation):
    store, owner, _ = account
    code = codes_for(store, owner)[0]
    invalid = {"prefix": "X" + code, "suffix": code + "!", "punctuation": code.replace("-", "."),
               "unicode_hex": "Ａ" + code[1:], "missing_digit": code[1:], "extra_digit": code + "0",
               "null": None, "list": [code]}[mutation]
    before = store.path.read_bytes()
    assert store.reset_password_with_recovery("owner", invalid, NEW_PASSWORD) is False
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("password", ["short", "x" * 11, "x" * 129, None, 123456789012, True])
def test_new_password_is_strictly_12_to_128_characters(account, password):
    store, owner, _ = account
    code = codes_for(store, owner)[0]
    before = store.path.read_bytes()
    with pytest.raises(ValueError):
        store.reset_password_with_recovery("owner", code, password)
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("password", ["x" * 12, "x" * 128, "  synthetic-password  "])
def test_valid_new_password_boundaries_and_whitespace_are_preserved(account, password):
    store, owner, _ = account
    assert store.reset_password_with_recovery("owner", codes_for(store, owner)[0], password) is True
    assert store.authenticate("owner", password)


def test_unknown_inactive_absent_and_wrong_code_use_same_failure_shape_and_hash_cost(account, monkeypatch):
    store, owner, partner = account
    code = codes_for(store, owner)[0]
    data = read(store)
    data["members"][owner["id"]]["active"] = False
    store.path.write_text(json.dumps(data))
    before = store.path.read_bytes()
    calls = []
    original = home_accounts.hash_password
    def tracked(password):
        calls.append(password)
        return original(password)
    monkeypatch.setattr(home_accounts, "hash_password", tracked)
    for username, attempted_code in [("unknown", code), ("owner", code), ("partner", code), ("partner", "invented")]:
        assert store.reset_password_with_recovery(username, attempted_code, NEW_PASSWORD) is False
    assert len(calls) == 4 and store.path.read_bytes() == before
    with pytest.raises(PermissionError):
        store.recovery_status(owner["id"])
    with pytest.raises(PermissionError):
        store.rotate_recovery_codes(owner["id"], PASSWORD)
    assert store.path.read_bytes() == before


def test_unknown_user_on_virgin_store_does_not_create_account_file(tmp_path):
    store = HomeAccountStore(tmp_path / "accounts.json")
    assert store.reset_password_with_recovery("unknown", "0" * 32, NEW_PASSWORD) is False
    assert not store.path.exists()
    assert not store.path.with_name("accounts.json.initialized").exists()


def test_codes_are_bound_to_the_member(account):
    store, owner, partner = account
    code = codes_for(store, owner)[0]
    codes_for(store, partner)
    before = store.path.read_bytes()
    assert store.reset_password_with_recovery("partner", code, NEW_PASSWORD) is False
    assert store.path.read_bytes() == before


def test_copying_hashes_to_another_member_does_not_copy_recovery_authority(account):
    store, owner, partner = account
    code = codes_for(store, owner)[0]
    data = read(store)
    data["members"][partner["id"]]["recovery"] = deepcopy(data["members"][owner["id"]]["recovery"])
    store.path.write_text(json.dumps(data))
    before = store.path.read_bytes()
    assert store.reset_password_with_recovery("partner", code, NEW_PASSWORD) is False
    assert store.path.read_bytes() == before


def test_recovery_password_is_checked_inside_exclusive_mutation(account, monkeypatch):
    store, owner, _ = account
    original = home_accounts.verify_password
    checked = []
    def check(password, encoded):
        # A separately opened lock descriptor must be excluded during validation.
        with store.lock_path.open("a+") as competing:
            with pytest.raises(BlockingIOError):
                home_accounts.fcntl.flock(competing.fileno(), home_accounts.fcntl.LOCK_EX | home_accounts.fcntl.LOCK_NB)
        checked.append(True)
        return original(password, encoded)
    monkeypatch.setattr(home_accounts, "verify_password", check)
    store.rotate_recovery_codes(owner["id"], PASSWORD, expected_session_version=0)
    assert checked == [True]


def test_legacy_version_is_incremented_by_first_successful_recovery(account):
    store, owner, _ = account
    code = codes_for(store, owner)[0]
    data = read(store)
    del data["members"][owner["id"]]["session_version"]
    store.path.write_text(json.dumps(data))
    assert store.reset_password_with_recovery("owner", code, NEW_PASSWORD) is True
    assert store.member(owner["id"])["session_version"] == 1


@pytest.mark.parametrize("different_code", [False, True])
def test_concurrent_resets_only_one_consumes_the_whole_batch(account, different_code):
    store, owner, _ = account
    codes = codes_for(store, owner)
    def reset(index):
        code = codes[index] if different_code else codes[0]
        return HomeAccountStore(store.path).reset_password_with_recovery("owner", code, NEW_PASSWORD + str(index))
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(reset, [0, 1]))
    assert sorted(outcomes) == [False, True]
    assert store.member(owner["id"])["session_version"] == 1
    assert store.recovery_status(owner["id"])["remaining"] == 0
    assert store.authenticate("owner", NEW_PASSWORD + str(outcomes.index(True)))


def test_revoked_session_cannot_rotate_even_if_reset_reused_current_password(account):
    store, owner, _ = account
    code = codes_for(store, owner)[0]
    assert store.reset_password_with_recovery("owner", code, PASSWORD) is True
    before = store.path.read_bytes()
    with pytest.raises(PermissionError):
        store.rotate_recovery_codes(owner["id"], PASSWORD, expected_session_version=0)
    assert store.path.read_bytes() == before
    assert len(store.rotate_recovery_codes(owner["id"], PASSWORD, expected_session_version=1)["recovery_codes"]) == 8


@pytest.mark.parametrize("mutation", [
    {"recovery": None}, {"recovery": {"schema_version": 1, "hashes": [], "generated_at": None}},
    {"recovery": {"schema_version": True, "hashes": [], "generated_at": "2026-09-13T12:00:00+00:00"}},
    {"recovery": {"schema_version": 1, "hashes": "bad", "generated_at": "2026-09-13T12:00:00+00:00"}},
    {"recovery": {"schema_version": 1, "hashes": ["not-a-hash"], "generated_at": "2026-09-13T12:00:00+00:00"}},
    {"recovery": {"schema_version": 1, "hashes": ["a" * 64] * 2, "generated_at": "2026-09-13T12:00:00+00:00"}},
    {"recovery": {"schema_version": 1, "hashes": [], "generated_at": "2026-09-13T12:00:00"}},
    {"recovery": {"schema_version": 1, "hashes": [], "generated_at": "bad"}},
    {"recovery": {"schema_version": 1, "hashes": [], "generated_at": "2026-09-13T12:00:00+00:00", "recovery_codes": ["plaintext"]}},
    {"session_version": True}, {"session_version": "0"}, {"session_version": -1},
])
def test_corrupt_recovery_or_session_version_fails_closed(account, mutation):
    store, owner, _ = account
    codes_for(store, owner)
    data = read(store)
    data["members"][owner["id"]].update(deepcopy(mutation))
    store.path.write_text(json.dumps(data))
    before = store.path.read_bytes()
    operations = [lambda: store.member(owner["id"]), lambda: store.recovery_status(owner["id"]),
                  lambda: store.rotate_recovery_codes(owner["id"], PASSWORD),
                  lambda: store.reset_password_with_recovery("owner", "0" * 32, NEW_PASSWORD)]
    for operation in operations:
        with pytest.raises(HomeAccountStorageError):
            operation()
    assert store.path.read_bytes() == before


def test_recovery_code_generation_failure_preserves_previous_batch(account, monkeypatch):
    store, owner, _ = account
    codes_for(store, owner)
    before = store.path.read_bytes()
    monkeypatch.setattr(home_accounts.secrets, "token_hex", lambda count: "0" * (count * 2))
    with pytest.raises(HomeAccountStorageError):
        store.rotate_recovery_codes(owner["id"], PASSWORD)
    assert store.path.read_bytes() == before


def test_failed_reset_commit_preserves_password_codes_and_session_version(account, monkeypatch):
    store, owner, _ = account
    code = codes_for(store, owner)[0]
    before = store.path.read_bytes()
    def reject(*_):
        raise OSError("synthetic write failure")
    monkeypatch.setattr("roxy_os.home_private_storage.os.replace", reject)
    with pytest.raises(HomeAccountStorageError):
        store.reset_password_with_recovery("owner", code, NEW_PASSWORD)
    assert store.path.read_bytes() == before
    assert store.authenticate("owner", PASSWORD)["session_version"] == 0


def test_missing_initialized_account_file_rejects_recovery_without_recreation(account, tmp_path):
    store, owner, _ = account
    code = codes_for(store, owner)[0]
    before = store.path.read_bytes()
    backup = tmp_path / "preserved-accounts.json"
    store.path.rename(backup)
    with pytest.raises(HomeAccountStorageError):
        HomeAccountStore(store.path).reset_password_with_recovery("owner", code, NEW_PASSWORD)
    assert not store.path.exists() and backup.read_bytes() == before
