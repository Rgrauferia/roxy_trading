"""Synthetic ingress tests. Public edge-header replacement is verified separately."""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_demo import DEMO_NOTICE_VERSION
from tools import roxy_home_service as service


@pytest.fixture
def ingress(tmp_path, monkeypatch):
    monkeypatch.setenv("ROXY_HOME_CLIENT_IP_SOURCE", "render_cf")
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_SERVICE_ID", "srv-synthetic-home")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://home.test")
    monkeypatch.delenv("ROXY_HOME_PUBLIC_ORIGIN", raising=False)
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-home-only")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setenv("ROXY_HOME_PUBLIC_SIGNUP_ENABLED", "1")
    monkeypatch.setenv("ROXY_HOME_TURNSTILE_SITE_KEY", "synthetic-site")
    monkeypatch.setenv("ROXY_HOME_TURNSTILE_SECRET_KEY", "synthetic-secret")
    monkeypatch.setenv("ROXY_HOME_SIGNUP_HOSTS", "home.test")
    monkeypatch.setattr(service, "verify_signup_token", lambda token: token == "synthetic-verified-token")
    service._RATE_STATE.clear()
    service._LOGIN_RATE_STATE.clear()
    service._RECOVERY_RATE_STATE.clear()
    yield HomeAccountStore(tmp_path / "accounts.json")
    service._RATE_STATE.clear()
    service._LOGIN_RATE_STATE.clear()
    service._RECOVERY_RATE_STATE.clear()


def edge(ip="8.8.8.8", **extra):
    return {"Origin": "https://home.test", "CF-Connecting-IP": ip, **extra}


def register(client, username, headers):
    return client.post("/v1/home-account/register", headers=headers, json={
        "username": username, "display_name": "Synthetic QA", "password": "synthetic-password-only",
        "verification_token": "synthetic-verified-token", "acknowledged": True,
        "notice_version": DEMO_NOTICE_VERSION,
    })


def test_client_ip_separates_login_buckets_and_ignores_xff(ingress):
    client = TestClient(service.app, base_url="https://home.test")
    payload = {"username": "nonexistent-synthetic", "password": "synthetic-invalid-password"}
    for _ in range(10):
        assert client.post("/v1/home-account/login", headers=edge(), json=payload).status_code == 401
    response = client.post("/v1/home-account/login", headers=edge(**{"X-Forwarded-For": "1.1.1.1"}), json=payload)
    assert response.status_code == 429
    assert client.post("/v1/home-account/login", headers=edge("1.1.1.1"), json=payload).status_code == 401
    assert not ingress.path.exists()


@pytest.mark.parametrize("headers", [
    {"Origin": "https://home.test"}, edge("not-an-ip"), edge("8.8.8.8,1.1.1.1"), edge("127.0.0.1"),
])
def test_bad_ingress_never_mutates_or_attempts_provider(ingress, monkeypatch, headers):
    monkeypatch.setattr(service, "verify_signup_token", lambda _: pytest.fail("Called provider with unverified ingress"))
    client = TestClient(service.app, base_url="https://home.test")
    response = register(client, "synthetic-nomutation", headers)
    assert response.status_code == 503
    assert response.headers["cache-control"] == "private, no-store"
    assert "not-an-ip" not in response.text
    assert not ingress.path.exists()


def test_durable_admission_hash_uses_edge_not_shared_socket(ingress):
    client = TestClient(service.app, base_url="https://home.test")
    for number in range(3):
        assert register(client, f"synthetic-a{number}", edge()).status_code == 201
    assert register(client, "synthetic-too-many", edge(**{"X-Forwarded-For": "1.1.1.1"})).status_code == 429
    assert register(client, "synthetic-b", edge("1.1.1.1")).status_code == 201
    households = list(json.loads(ingress.path.read_text())["households"].values())
    expected = hmac.new(b"synthetic-home-only", b"8.8.8.8", hashlib.sha256).hexdigest()
    assert sum(row["trial"]["admission_hash"] == expected for row in households) == 3
    assert len({row["trial"]["admission_hash"] for row in households}) == 2
    assert "8.8.8.8" not in ingress.path.read_text()


def test_recovery_uses_same_verified_identity_without_locking_login(ingress):
    client = TestClient(service.app, base_url="https://home.test")
    response = client.post("/v1/home-account/recovery/reset", headers={"Origin": "https://home.test"}, json={
        "username": "synthetic-absent", "recovery_code": "invalid-code", "new_password": "synthetic-new-password",
    })
    assert response.status_code == 503
    assert not service._RECOVERY_RATE_STATE
    assert not service._LOGIN_RATE_STATE


def test_ingress_misconfiguration_preserves_health_and_hides_details(ingress, monkeypatch):
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://unexpected-private-host.test")
    client = TestClient(service.app, base_url="https://home.test")
    assert client.get("/health").status_code == 200
    # Login's earlier Origin check is independently covered; exercise the
    # transport configuration guard even when no Origin header is supplied.
    response = client.post("/v1/home-account/login", headers={"CF-Connecting-IP": "8.8.8.8"}, json={
        "username": "synthetic-absent", "password": "synthetic-invalid-password",
    })
    assert response.status_code == 503
    assert "unexpected-private-host" not in response.text
    assert "RENDER" not in response.text
    assert not ingress.path.exists()
