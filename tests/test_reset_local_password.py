from tools import reset_local_password


class _Guard:
    def __init__(self):
        self.cleared = []

    def clear(self, identifier):
        self.cleared.append(identifier)


def test_reset_local_password_rehashes_and_revokes_session(monkeypatch):
    profile = {
        "username": "alice",
        "password_salt": "old-salt",
        "password_hash": "old-hash",
        "session_token_hash": "old-session",
    }
    data = {"users": {"alice": profile}}
    saved = []
    guard = _Guard()
    monkeypatch.setattr(reset_local_password.app, "roxy_load_users", lambda: data)
    monkeypatch.setattr(reset_local_password.app, "roxy_save_users", lambda payload: saved.append(payload))
    monkeypatch.setattr(reset_local_password.app, "roxy_auth_attempt_guard", lambda: guard)

    ok, message = reset_local_password.reset_local_password(
        "Alice",
        "RecoveredPassword3!",
        "RecoveredPassword3!",
    )

    assert ok is True
    assert "revocadas" in message
    assert profile["password_iterations"] == reset_local_password.app.ROXY_PASSWORD_ITERATIONS
    assert "session_token_hash" not in profile
    assert reset_local_password.app.roxy_hash_password(
        "RecoveredPassword3!",
        profile["password_salt"],
        profile["password_iterations"],
    ) == profile["password_hash"]
    assert guard.cleared == ["alice"]
    assert saved


def test_reset_local_password_rejects_unknown_account_without_writing(monkeypatch):
    monkeypatch.setattr(reset_local_password.app, "roxy_load_users", lambda: {"users": {}})
    monkeypatch.setattr(
        reset_local_password.app,
        "roxy_save_users",
        lambda _payload: (_ for _ in ()).throw(AssertionError("unknown account must not be written")),
    )

    ok, message = reset_local_password.reset_local_password(
        "missing",
        "RecoveredPassword3!",
        "RecoveredPassword3!",
    )

    assert ok is False
    assert "no encontrada" in message
