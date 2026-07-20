import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from cryptography.fernet import Fernet

from tools import secrets_service


def oauth_db(path, *, expires_at, redirect_uri="http://127.0.0.1:5000/callback"):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE oauth_states (id INTEGER PRIMARY KEY, state TEXT UNIQUE, expires_at TEXT, redirect_uri TEXT)"
    )
    conn.execute(
        "INSERT INTO oauth_states (state, expires_at, redirect_uri) VALUES (?, ?, ?)",
        ("state-1", expires_at, redirect_uri),
    )
    conn.commit()
    conn.close()


def test_oauth_callback_rejects_expired_state_before_token_exchange(tmp_path, monkeypatch):
    path = tmp_path / "oauth.db"
    oauth_db(
        path,
        expires_at=(datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)).isoformat(),
    )
    monkeypatch.setattr(secrets_service, "_conn", lambda: sqlite3.connect(path))
    monkeypatch.setattr(
        __import__("auth"),
        "exchange_code_for_token",
        lambda *_args: (_ for _ in ()).throw(AssertionError("exchange must not run")),
    )

    with pytest.raises(HTTPException) as exc:
        secrets_service.auth_oauth_callback("code", "state-1", "https://attacker.example/callback")

    assert exc.value.status_code == 400


def test_oauth_callback_rejects_unknown_state_as_client_error(tmp_path, monkeypatch):
    path = tmp_path / "oauth.db"
    oauth_db(
        path,
        expires_at=(datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5)).isoformat(),
    )
    monkeypatch.setattr(secrets_service, "_conn", lambda: sqlite3.connect(path))

    with pytest.raises(HTTPException) as exc:
        secrets_service.auth_oauth_callback("code", "unknown", None)

    assert exc.value.status_code == 400


def test_oauth_callback_stores_one_time_session_result_encrypted(tmp_path, monkeypatch):
    path = tmp_path / "oauth-encrypted.db"
    monkeypatch.setattr(secrets_service, "DB_PATH", str(path))
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    secrets_service.ensure_tables()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO oauth_states (state, redirect_uri, expires_at) VALUES (?, ?, ?)",
            (
                "encrypted-state",
                "http://127.0.0.1:5000/callback",
                (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5)).isoformat(),
            ),
        )

    auth_module = __import__("auth")
    monkeypatch.setattr(auth_module, "exchange_code_for_token", lambda *_args: "provider-token")
    monkeypatch.setattr(auth_module, "fetch_user_info", lambda *_args: {"login": "oauth-user"})

    callback = secrets_service.auth_oauth_callback("code", "encrypted-state", None)
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT session_token, encrypted_session_token FROM oauth_results WHERE state=?",
            ("encrypted-state",),
        ).fetchone()
    assert row[0] in {"", None}
    assert row[1]

    result = secrets_service.auth_check_state(
        "encrypted-state", secrets_service._sign_state("encrypted-state")
    )
    assert result["username"] == "oauth-user"
    assert result["session_token"] == callback["session_token"]
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM oauth_results").fetchone()[0] == 0
