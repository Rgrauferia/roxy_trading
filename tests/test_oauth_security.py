import json
from urllib.parse import parse_qs, urlsplit

import auth
from tools import oauth_server


def test_oauth_authorization_url_uses_explicit_csrf_state(monkeypatch):
    monkeypatch.setenv("GITHUB_CLIENT_ID", "client-id")
    monkeypatch.setenv("OAUTH_TEST_STATE", "environment-state")

    url = auth.start_oauth_flow(
        "github",
        "http://127.0.0.1:5000/callback",
        state="request-specific-state",
    )

    assert parse_qs(urlsplit(url).query)["state"] == ["request-specific-state"]


def test_oauth_callback_rejects_missing_or_wrong_state_before_exchange(monkeypatch):
    monkeypatch.setenv("OAUTH_TEST_STATE", "expected-state")
    monkeypatch.setattr(
        oauth_server.auth,
        "exchange_code_for_token",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("exchange must not run")),
    )
    client = oauth_server.app.test_client()

    assert client.get("/callback?code=abc").status_code == 400
    assert client.get("/callback?code=abc&state=wrong").status_code == 400


def test_oauth_index_generates_and_includes_state(monkeypatch):
    monkeypatch.setenv("GITHUB_CLIENT_ID", "client-id")
    monkeypatch.delenv("OAUTH_TEST_STATE", raising=False)
    response = oauth_server.app.test_client().get("/")

    assert response.status_code == 200
    assert "state=" in response.get_data(as_text=True)
    assert len(oauth_server.os.environ["OAUTH_TEST_STATE"]) >= 32


def test_oauth_callback_writes_token_result_atomically_and_privately(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OAUTH_TEST_STATE", "expected-state")
    monkeypatch.setattr(oauth_server.auth, "exchange_code_for_token", lambda *_args, **_kwargs: "token-value")
    monkeypatch.setattr(
        oauth_server.auth,
        "fetch_user_info",
        lambda *_args, **_kwargs: {"login": "local-user", "id": 7, "name": "Local User"},
    )

    response = oauth_server.app.test_client().get("/callback?code=abc&state=expected-state")
    callback_path = tmp_path / "run" / "oauth_callback.json"

    assert response.status_code == 200
    assert json.loads(callback_path.read_text())["access_token"] == "token-value"
    assert callback_path.stat().st_mode & 0o777 == 0o600
    assert not list((tmp_path / "run").glob(".oauth_callback.json.*.tmp"))
