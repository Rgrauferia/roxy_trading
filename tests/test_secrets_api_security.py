import sqlite3
import plistlib
from pathlib import Path

from fastapi.testclient import TestClient
from fastapi import HTTPException
from starlette.requests import Request

from system_diagnostics import secrets_api_security_check, voice_api_security_check, voice_remote_access_check
from tools import secrets_service
from tools import voice_service
from tools.voice_service import app


def _isolated_service(tmp_path, monkeypatch):
    path = tmp_path / "roxy.db"
    monkeypatch.setattr(secrets_service, "DB_PATH", str(path))
    secrets_service.ensure_tables()
    return TestClient(app), path


def test_mock_login_and_admin_metadata_fail_closed_by_default(tmp_path, monkeypatch):
    client, path = _isolated_service(tmp_path, monkeypatch)
    monkeypatch.setenv("ROXY_ENV", "production")
    for name in (
        "ROXY_ENABLE_MOCK_LOGIN",
        "ROXY_ALLOW_INSECURE_DEV_ADMIN",
        "ADMIN_TOKEN",
        "ADMIN_USERS",
        "ADMIN_ORGS",
    ):
        monkeypatch.delenv(name, raising=False)

    assert client.post("/api/auth/mock-login", json="anonymous").status_code == 404
    assert client.get("/api/secrets").status_code == 403
    assert client.get("/api/secrets/ANY").status_code == 403
    assert client.get("/api/secrets/ANY/revisions").status_code == 403
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_mock_login_requires_explicit_development_loopback_flag(tmp_path, monkeypatch):
    client, path = _isolated_service(tmp_path, monkeypatch)
    monkeypatch.setenv("ROXY_ENV", "test")
    monkeypatch.setenv("ROXY_ENABLE_MOCK_LOGIN", "1")

    response = client.post("/api/auth/mock-login", json="qa_user")

    assert response.status_code == 200
    payload = response.json()
    assert payload["username"] == "qa_user"
    assert payload["token"]
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE username=? AND provider='mock'", ("qa_user",)
        ).fetchone()[0] == 1


def test_admin_auth_is_dynamic_and_dev_bypass_is_explicit(tmp_path, monkeypatch):
    client, _ = _isolated_service(tmp_path, monkeypatch)
    monkeypatch.setenv("ROXY_ENV", "test")
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("ROXY_ALLOW_INSECURE_DEV_ADMIN", "1")
    assert client.get("/api/secrets").status_code == 200

    monkeypatch.delenv("ROXY_ALLOW_INSECURE_DEV_ADMIN", raising=False)
    monkeypatch.setenv("ADMIN_TOKEN", "dynamic-admin-token")
    assert client.get("/api/secrets").status_code == 403
    assert client.get(
        "/api/secrets", headers={"Authorization": "Bearer dynamic-admin-token"}
    ).status_code == 200


def test_secrets_api_security_diagnostic_reports_bypass_risk_without_values():
    secure = secrets_api_security_check({"ROXY_ENV": "production"})
    assert secure.status == "CONNECTED"
    assert "fail-closed" in secure.detail

    dev = secrets_api_security_check({"ROXY_ENV": "development", "ROXY_ENABLE_MOCK_LOGIN": "1"})
    assert dev.status == "WARNING"
    assert "ROXY_ENABLE_MOCK_LOGIN" in dev.detail

    unsafe = secrets_api_security_check(
        {"ROXY_ENV": "production", "ROXY_ALLOW_INSECURE_DEV_ADMIN": "true", "ADMIN_TOKEN": "secret"}
    )
    assert unsafe.status == "ERROR"
    assert "secret" not in unsafe.detail


def test_fast_diagnostics_surface_includes_secrets_api_security():
    source = Path("streamlit_app.py").read_text(encoding="utf-8")
    diagnostics = source[source.index('elif selected_page == "Diagnostico":') : source.index(
        "def render_focused_live_workspace"
    )]

    assert "secrets_api_security_check," in diagnostics
    assert "runtime_rows.append(secrets_api_security_check().to_dict())" in diagnostics
    assert "runtime_rows.append(voice_api_security_check().to_dict())" in diagnostics
    assert "voice_remote_access_check(launchagent_path=voice_launchagent_path)" in diagnostics
    assert "price_alert_monitor_check," in diagnostics
    assert 'price_alert_monitor_check(project_root / "alerts" / "price_alert_monitor.json")' in diagnostics


def test_voice_api_security_diagnostic_distinguishes_key_and_loopback_fallback():
    local_only = voice_api_security_check({})
    assert local_only.status == "CONNECTED"
    assert "Modo local protegido" in local_only.detail
    assert "loopback" in local_only.detail
    assert "503" in local_only.detail

    secret_like_key = "voice-secret-value"
    configured = voice_api_security_check({"VOICE_API_KEY": secret_like_key})
    assert configured.status == "CONNECTED"
    assert secret_like_key not in configured.detail


def test_voice_remote_access_diagnostic_requires_bind_auth_and_https(tmp_path):
    plist = tmp_path / "voice.plist"
    plist.write_bytes(
        plistlib.dumps(
            {
                "ProgramArguments": [
                    "python",
                    "-m",
                    "uvicorn",
                    "tools.voice_service:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8010",
                ]
            }
        )
    )
    local = voice_remote_access_check(
        {"VOICE_API_KEY": "configured", "ROXY_VOICE_PUBLIC_BASE_URL": "https://roxy.example"},
        launchagent_path=plist,
    )
    assert local.status == "NOT_CONFIGURED"
    assert "solo loopback" in local.detail
    assert "por si sola no cambia el bind" in local.detail

    payload = plistlib.loads(plist.read_bytes())
    payload["ProgramArguments"][5] = "0.0.0.0"
    plist.write_bytes(plistlib.dumps(payload))
    no_tls = voice_remote_access_check(
        {"VOICE_API_KEY": "configured"}, launchagent_path=plist
    )
    ready = voice_remote_access_check(
        {"VOICE_API_KEY": "configured", "ROXY_VOICE_PUBLIC_BASE_URL": "https://roxy.example"},
        launchagent_path=plist,
    )

    assert no_tls.status == "WARNING"
    assert "no hay transporte HTTPS" in no_tls.detail
    assert ready.status == "CONNECTED"


def test_voice_api_without_key_allows_loopback_but_rejects_remote(monkeypatch):
    monkeypatch.delenv("VOICE_API_KEY", raising=False)
    local = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1234)})
    remote = Request({"type": "http", "headers": [], "client": ("192.0.2.25", 1234)})

    assert voice_service.require_api_key(local) == "loopback-local"
    try:
        voice_service.require_api_key(remote)
    except HTTPException as exc:
        assert exc.status_code == 503
    else:
        raise AssertionError("remote voice request unexpectedly bypassed authentication")
