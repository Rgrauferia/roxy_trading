import hashlib
import inspect
import json
import stat
from datetime import datetime, timedelta, timezone

import streamlit_app
from roxy_trader.auth_guard import AuthAttemptGuard


class _AllowingAttemptGuard:
    class _Status:
        allowed = True
        retry_after_seconds = 0

    def status(self, _identifier):
        return self._Status()

    def record_failure(self, _identifier):
        return self._Status()

    def clear(self, _identifier):
        return None


def test_unknown_login_cannot_create_or_recover_account_from_client_profile(monkeypatch):
    monkeypatch.setattr(streamlit_app, "roxy_find_user", lambda _identifier: ("", None))
    monkeypatch.setattr(streamlit_app, "roxy_auth_attempt_guard", lambda: _AllowingAttemptGuard())
    monkeypatch.setattr(
        streamlit_app,
        "roxy_save_users",
        lambda _payload: (_ for _ in ()).throw(AssertionError("unknown login must not write a user")),
    )

    ok, message = streamlit_app.roxy_login_user("attacker@example.test", "arbitrary-password")

    assert ok is False
    assert message == "Usuario o contrasena incorrectos."


def test_login_throttle_blocks_unknown_account_without_enumerating_it(monkeypatch, tmp_path):
    guard = AuthAttemptGuard(tmp_path / "attempts.sqlite3", max_failures=2, lock_seconds=120)
    monkeypatch.setattr(streamlit_app, "roxy_find_user", lambda _identifier: ("", None))
    monkeypatch.setattr(streamlit_app, "roxy_auth_attempt_guard", lambda: guard)

    first_ok, first_message = streamlit_app.roxy_login_user("missing@example.test", "wrong-password")
    blocked_ok, blocked_message = streamlit_app.roxy_login_user("missing@example.test", "wrong-password")

    assert first_ok is False
    assert first_message == "Usuario o contrasena incorrectos."
    assert blocked_ok is False
    assert "Demasiados intentos" in blocked_message


def test_legacy_password_hash_is_upgraded_after_successful_login(monkeypatch):
    salt = "legacy-salt"
    profile = {
        "username": "alice",
        "name": "Alice",
        "password_salt": salt,
        "password_hash": streamlit_app.roxy_hash_password("correct-password", salt),
    }
    data = {"users": {"alice": profile}}
    saved = []
    remembered = []
    monkeypatch.setattr(streamlit_app, "roxy_find_user", lambda _identifier: ("alice", profile))
    monkeypatch.setattr(streamlit_app, "roxy_load_users", lambda: data)
    monkeypatch.setattr(streamlit_app, "roxy_save_users", lambda payload: saved.append(payload))
    monkeypatch.setattr(streamlit_app, "roxy_auth_attempt_guard", lambda: _AllowingAttemptGuard())
    monkeypatch.setattr(
        streamlit_app,
        "roxy_remember_authenticated_user",
        lambda username, upgraded: remembered.append((username, upgraded.copy())),
    )

    ok, _message = streamlit_app.roxy_login_user("alice", "correct-password")

    assert ok is True
    assert profile["password_iterations"] == streamlit_app.ROXY_PASSWORD_ITERATIONS
    assert profile["password_salt"] != salt
    assert saved
    assert remembered[0][0] == "alice"


def test_registration_rejects_short_password_before_writing(monkeypatch):
    monkeypatch.setattr(
        streamlit_app,
        "roxy_load_users",
        lambda: (_ for _ in ()).throw(AssertionError("short password must not read or write accounts")),
    )

    ok, message = streamlit_app.roxy_register_user(
        name="Alice Example",
        username="alice",
        email="alice@example.test",
        password="short",
        language="es",
    )

    assert ok is False
    assert str(streamlit_app.ROXY_PASSWORD_MIN_LENGTH) in message


def test_user_backup_is_atomic_and_owner_only(monkeypatch, tmp_path):
    primary = tmp_path / "primary" / "users.json"
    fallback = tmp_path / "fallback" / "users.json"
    monkeypatch.setattr(streamlit_app, "ROXY_USERS_PATH", primary)
    monkeypatch.setattr(streamlit_app, "ROXY_USERS_FALLBACK_PATH", fallback)
    monkeypatch.setattr(streamlit_app, "roxy_save_users_to_db", lambda _data: None)
    payload = {"users": {"alice": {"username": "alice", "password_hash": "hash"}}}

    streamlit_app.roxy_save_users(payload)

    for path in (primary, fallback):
        assert json.loads(path.read_text()) == payload
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert not list(path.parent.glob(f".{path.name}.*.tmp"))


def test_database_persistence_never_invents_a_plaintext_session_placeholder(monkeypatch, tmp_path):
    import sqlite3

    database = tmp_path / "roxy.db"
    monkeypatch.setattr(streamlit_app, "roxy_auth_db_path", lambda: str(database))
    monkeypatch.setattr(streamlit_app.storage, "init_db", lambda: None)
    payload = {"users": {"alice": {"username": "alice", "session_token_hash": "a" * 64}}}

    streamlit_app.roxy_save_users_to_db(payload)

    with sqlite3.connect(database) as connection:
        stored_token = connection.execute(
            "SELECT session_token FROM roxy_auth_users WHERE username='alice'"
        ).fetchone()[0]
        tables = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert stored_token == ""
    assert "roxy_auth_attempts" in tables


def test_authenticated_password_change_rotates_hash_and_revokes_old_session(monkeypatch):
    salt = "current-salt"
    profile = {
        "username": "alice",
        "password_salt": salt,
        "password_hash": streamlit_app.roxy_hash_password(
            "CurrentPassword1!",
            salt,
            streamlit_app.ROXY_PASSWORD_ITERATIONS,
        ),
        "password_iterations": streamlit_app.ROXY_PASSWORD_ITERATIONS,
        "session_token_hash": "old-session-hash",
    }
    data = {"users": {"alice": profile}}
    saved = []
    monkeypatch.setattr(streamlit_app, "roxy_load_users", lambda: data)
    monkeypatch.setattr(streamlit_app, "roxy_save_users", lambda payload: saved.append(payload))
    monkeypatch.setattr(streamlit_app, "roxy_auth_attempt_guard", lambda: _AllowingAttemptGuard())
    monkeypatch.setattr(streamlit_app, "roxy_issue_session_token", lambda _username: "")

    ok, message = streamlit_app.roxy_change_password(
        "alice",
        "CurrentPassword1!",
        "NewPassword2!",
        "NewPassword2!",
    )

    assert ok is True
    assert "otras sesiones" in message
    assert profile["password_salt"] != salt
    assert profile["password_iterations"] == streamlit_app.ROXY_PASSWORD_ITERATIONS
    assert "session_token_hash" not in profile
    assert secrets_compare_password(profile, "NewPassword2!")
    assert saved


def secrets_compare_password(profile, password):
    return streamlit_app.roxy_hash_password(
        password,
        profile["password_salt"],
        profile["password_iterations"],
    ) == profile["password_hash"]


def test_session_tokens_are_rotated_and_only_hash_is_persisted(monkeypatch):
    data = {"users": {"alice": {"username": "alice", "session_token": "legacy-secret-token-value-1234"}}}
    saved = []
    monkeypatch.setattr(streamlit_app, "roxy_load_users", lambda: data)
    monkeypatch.setattr(streamlit_app, "roxy_save_users", lambda payload: saved.append(payload))

    token = streamlit_app.roxy_issue_session_token("alice")
    profile = data["users"]["alice"]

    assert len(token) >= 24
    assert "session_token" not in profile
    assert profile["session_token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert saved


def test_legacy_plain_session_token_is_migrated_after_valid_restore(monkeypatch):
    token = "legacy-session-token-value-123456789"
    data = {"users": {"alice": {"username": "alice", "session_token": token}}}
    saved = []
    monkeypatch.setattr(streamlit_app, "roxy_load_users", lambda: data)
    monkeypatch.setattr(streamlit_app, "roxy_save_users", lambda payload: saved.append(payload))

    username, profile = streamlit_app.roxy_find_user_by_session_token(token)

    assert username == "alice"
    assert "session_token" not in profile
    assert profile["session_token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert saved


def test_loading_users_migrates_all_plaintext_session_tokens_at_rest(monkeypatch):
    token = "legacy-session-token-value-123456789"
    file_data = {
        "users": {
            "alice": {"username": "alice", "session_token": token},
            "bob": {"username": "bob", "session_token": ""},
        }
    }
    saved = []
    monkeypatch.setattr(streamlit_app, "roxy_load_users_from_db", lambda: {"users": {}})
    monkeypatch.setattr(streamlit_app, "roxy_load_users_from_file", lambda _path: file_data)
    monkeypatch.setattr(streamlit_app, "ROXY_USERS_PATH", streamlit_app.ROXY_USERS_FALLBACK_PATH)
    monkeypatch.setattr(streamlit_app, "roxy_save_users", lambda payload: saved.append(payload))

    loaded = streamlit_app.roxy_load_users()

    assert loaded["users"]["alice"]["session_token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert "session_token" not in loaded["users"]["alice"]
    assert "session_token" not in loaded["users"]["bob"]
    assert loaded["users"]["alice"]["session_updated_at"]
    assert saved == [loaded]


def test_expired_session_is_revoked_server_side(monkeypatch):
    token = "expired-session-token-value-123456789"
    issued_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    data = {
        "users": {
            "alice": {
                "username": "alice",
                "session_token_hash": hashlib.sha256(token.encode()).hexdigest(),
                "session_updated_at": issued_at.isoformat(),
            }
        }
    }
    saved = []
    monkeypatch.setattr(streamlit_app, "roxy_load_users", lambda: data)
    monkeypatch.setattr(streamlit_app, "roxy_save_users", lambda payload: saved.append(payload))

    username, profile = streamlit_app.roxy_find_user_by_session_token(
        token,
        now=issued_at + timedelta(days=31),
    )

    assert username == ""
    assert profile is None
    assert "session_token_hash" not in data["users"]["alice"]
    assert saved


def test_unexpired_session_remains_valid(monkeypatch):
    token = "current-session-token-value-123456789"
    issued_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    profile = {
        "username": "alice",
        "session_token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "session_updated_at": issued_at.isoformat(),
    }
    monkeypatch.setattr(streamlit_app, "roxy_load_users", lambda: {"users": {"alice": profile}})

    username, restored = streamlit_app.roxy_find_user_by_session_token(
        token,
        now=issued_at + timedelta(days=29),
    )

    assert username == "alice"
    assert restored is profile


def test_public_profile_and_internal_links_never_carry_session_token():
    profile = streamlit_app.roxy_public_profile_payload(
        "alice", {"name": "Alice", "email": "alice@example.test", "language": "es"}, "secret-token"
    )
    bridge = inspect.getsource(streamlit_app.render_roxy_browser_session_bridge)

    assert "session_token" not in profile
    assert "patchLinks" not in bridge
    assert "MutationObserver" not in bridge
    assert "currentUrl.searchParams.set" not in bridge
    assert "url.searchParams.delete" in bridge


def test_restore_bridge_uses_only_short_lived_token_query_and_supports_logout_clear():
    source = inspect.getsource(streamlit_app.render_roxy_session_restore_bridge)

    assert "profileStorageKey" not in source
    assert "url.searchParams.set" in source
    assert "localStorage.removeItem" in source
    assert "ROXY_LOGOUT_PARAM" in source


def test_login_recovery_control_reports_configuration_state_instead_of_being_dead_text():
    source = inspect.getsource(streamlit_app.render_roxy_auth_gate)

    assert 'st.form_submit_button("Recuperar acceso")' in source
    assert "recuperacion por correo no esta configurada" in source
    assert "roxy-auth-forgot" not in source


def test_password_change_uses_post_rerun_confirmation_message():
    source = inspect.getsource(streamlit_app.show_focused_sidebar)

    assert 'st.session_state["roxy_account_security_message"] = message' in source
    assert 'st.session_state.pop("roxy_account_security_message", "")' in source


def test_authentication_clears_register_mode_and_logout_targets_login():
    authenticated_source = inspect.getsource(streamlit_app.roxy_set_authenticated_user)
    logout_source = inspect.getsource(streamlit_app.roxy_logout_user)

    assert 'del st.query_params["auth"]' in authenticated_source
    assert 'st.query_params["auth"] = "login"' in logout_source


def test_passkey_skip_is_persisted_but_manual_management_remains_available():
    panel_source = inspect.getsource(streamlit_app.render_roxy_passkey_setup_panel)
    remember_source = inspect.getsource(streamlit_app.roxy_remember_authenticated_user)

    assert 'stored_profile["passkey_offer_dismissed"] = True' in panel_source
    assert "if not manage_visible and bool(profile.get(\"passkey_offer_dismissed\"))" in panel_source
    assert "if not manage_visible and not st.session_state.get" in panel_source
    assert 'not bool(profile.get("passkey_offer_dismissed"))' in remember_source
