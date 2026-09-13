"""Account security regression tests use isolated, synthetic Home identities."""
import base64
import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from roxy_os.home_accounts import HomeAccountStore
from tools import roxy_home_service as service

BASE = "https://roxy.test"
PASSWORD = "synthetic-original-password"
NEW_PASSWORD = "synthetic-replacement-password"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-recovery-key")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "local_user")
    monkeypatch.setenv("ROXY_HOME_PUBLIC_SIGNUP_ENABLED", "0")
    monkeypatch.setattr("roxy_os.home_accounts.PASSWORD_ITERATIONS", 100_000)
    service._RATE_STATE.clear()
    service._LOGIN_RATE_STATE.clear()
    service._RECOVERY_RATE_STATE.clear()
    store = HomeAccountStore(tmp_path / "accounts.json")
    owner = store.bootstrap("local_user", household_name="Synthetic", username="owner",
                            display_name="Synthetic", password=PASSWORD, _issue_recovery=True)
    return store, owner


def signed_in(username="owner"):
    client = TestClient(service.app, base_url=BASE)
    assert client.post("/v1/home-account/login", json={"username": username, "password": PASSWORD}).status_code == 200
    return client


def headers(member):
    return {"Origin": BASE, "X-Roxy-Member-Id": member["id"]}


def reset(client, code, username="owner", password=NEW_PASSWORD, origin=BASE):
    return client.post("/v1/home-account/recovery/reset", headers={"Origin": origin},
                       json={"username": username, "recovery_code": code, "new_password": password})


def legacy_personal_cookie(member):
    raw = f"member|{member['id']}|{member['storage_user_id']}|{int(time.time()) + 3600}"
    encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    signature = hmac.new(b"synthetic-recovery-key", encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def test_reset_revokes_all_personal_sessions_preserves_other_member_and_data(setup):
    store, owner = setup
    other = store.add_member(owner["id"], username="partner", display_name="Other", password=PASSWORD)
    one, two, partner = signed_in(), signed_in(), signed_in("partner")
    legacy = TestClient(service.app, base_url=BASE)
    legacy.cookies.set(service.SESSION_COOKIE, legacy_personal_cookie(owner), domain="roxy.test", path="/")
    assert legacy.get("/v1/home-account/me").status_code == 200
    previous = json.loads(store.path.read_text())
    response = reset(TestClient(service.app, base_url=BASE), owner["recovery_codes"][0])
    assert response.status_code == 200 and response.json()["status"] == "RESET"
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert response.headers["cache-control"] == "private, no-store"
    for client in (one, two, legacy):
        assert client.get("/v1/home-account/me").status_code == 401
    assert partner.get("/v1/home-account/me").json()["id"] == other["id"]
    assert store.authenticate("owner", PASSWORD) is None
    assert store.authenticate("owner", NEW_PASSWORD)["session_version"] == 1
    assert store.recovery_status(owner["id"])["remaining"] == 0
    current = json.loads(store.path.read_text())
    assert current["households"] == previous["households"]
    assert current["members"][other["id"]] == previous["members"][other["id"]]
    assert reset(TestClient(service.app, base_url=BASE), owner["recovery_codes"][1]).status_code == 401


def test_recovery_status_is_member_bound_and_never_exposes_codes(setup):
    store, owner = setup
    client = signed_in()
    result = client.get("/v1/home-account/recovery", headers=headers(owner))
    assert result.status_code == 200 and result.json()["remaining"] == 8
    assert "hashes" not in result.text and "recovery_codes" not in result.text
    assert all(code not in result.text for code in owner["recovery_codes"])
    assert client.get("/v1/home-account/recovery").status_code == 409
    assert client.get("/v1/home-account/recovery", headers={"X-Roxy-Member-Id": "other"}).status_code == 409
    bearer = TestClient(service.app, base_url=BASE)
    assert bearer.get("/v1/home-account/recovery", headers={**headers(owner), "Authorization": "Bearer synthetic-recovery-key"}).status_code == 403
    bearer.cookies.set(service.SESSION_COOKIE, service._session_cookie("local_user"), domain="roxy.test", path="/")
    assert bearer.get("/v1/home-account/recovery", headers=headers(owner)).status_code == 403


def test_rotation_requires_same_origin_password_and_current_member(setup):
    store, owner = setup
    client = signed_in()
    prior = store.path.read_bytes()
    payload = {"current_password": PASSWORD}
    assert client.post("/v1/home-account/recovery/codes", headers={"X-Roxy-Member-Id": owner["id"]}, json=payload).status_code == 403
    assert client.post("/v1/home-account/recovery/codes", headers={**headers(owner), "Origin": "https://evil.test"}, json=payload).status_code == 403
    assert client.post("/v1/home-account/recovery/codes", headers=headers(owner), json={"current_password": "incorrect-password"}).status_code == 401
    assert store.path.read_bytes() == prior
    response = client.post("/v1/home-account/recovery/codes", headers=headers(owner), json=payload)
    assert response.status_code == 200 and len(response.json()["recovery_codes"]) == 8
    assert response.headers["cache-control"] == "private, no-store"
    assert PASSWORD not in response.text
    assert reset(client, owner["recovery_codes"][0]).status_code == 401
    assert reset(client, response.json()["recovery_codes"][0]).status_code == 200


def test_invalid_reset_does_not_enumerate_modify_or_echo_secrets(setup):
    store, owner = setup
    client = TestClient(service.app, base_url=BASE)
    before = store.path.read_bytes()
    one = reset(client, "not-a-code", "owner")
    missing = reset(client, "not-a-code", "missing-owner")
    assert one.status_code == missing.status_code == 401
    assert one.json() == missing.json()
    assert store.path.read_bytes() == before
    bad = reset(client, owner["recovery_codes"][0], password="secret")
    assert bad.status_code == 422
    assert "secret" not in bad.text and owner["recovery_codes"][0] not in bad.text
    assert store.path.read_bytes() == before
    assert reset(client, owner["recovery_codes"][0], origin="null").status_code == 403


def test_auth_validation_does_not_echo_passwords_or_extra_secret_fields(setup):
    client = TestClient(service.app, base_url=BASE)
    for route, body in [
        ("login", {"username": "owner", "password": "s3cret"}),
        ("recovery/codes", {"current_password": "short"}),
        ("recovery/reset", {"username": "owner", "recovery_code": "synthetic-secret-code", "new_password": "s3cret"}),
        ("register", {"password": "synthetic-secret-password", "unexpected": "synthetic-secret-extra"}),
    ]:
        if route == "recovery/codes":
            continue  # Unauthenticated dependency rejects before body validation.
        response = client.post("/v1/home-account/" + route, json=body, headers={"Origin": BASE})
        assert response.status_code == 422
        assert "s3cret" not in response.text and "synthetic-secret" not in response.text


def test_security_is_available_after_trial_expiry_without_extending_trial(setup):
    store, _ = setup
    trial = store.register_trial(username="trialperson", display_name="Trial", password=PASSWORD, admission_hash="synthetic")
    def expire(payload):
        payload["households"][trial["household_id"]]["trial"]["expires_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    store._mutate(expire)
    before = json.loads(store.path.read_text())["households"]
    client = signed_in("trialperson")
    assert client.get("/v1/home-account/recovery", headers=headers(trial)).status_code == 200
    response = client.post("/v1/home-account/recovery/codes", headers=headers(trial), json={"current_password": PASSWORD})
    assert response.status_code == 200
    assert reset(client, response.json()["recovery_codes"][0], username="trialperson").status_code == 200
    assert json.loads(store.path.read_text())["households"] == before


def test_revoked_authenticated_context_cannot_rotate_even_if_password_reused(setup, monkeypatch):
    store, owner = setup
    client = signed_in()
    original = HomeAccountStore.rotate_recovery_codes
    def raced(self, member_id, password, **kwargs):
        assert store.reset_password_with_recovery("owner", owner["recovery_codes"][0], PASSWORD)
        return original(self, member_id, password, **kwargs)
    monkeypatch.setattr(HomeAccountStore, "rotate_recovery_codes", raced)
    response = client.post("/v1/home-account/recovery/codes", headers=headers(owner), json={"current_password": PASSWORD})
    assert response.status_code == 401
    assert store.recovery_status(owner["id"])["remaining"] == 0


def test_cookie_issuance_uses_authenticated_version_not_newer_reset_version(setup):
    store, owner = setup
    authenticated = store.authenticate("owner", PASSWORD)
    assert store.reset_password_with_recovery("owner", owner["recovery_codes"][0], NEW_PASSWORD)
    assert service._cookie_auth(service._member_session_cookie(authenticated)) is None
    assert service._cookie_auth(service._member_session_cookie(store.authenticate("owner", NEW_PASSWORD))).session_version == 1


def test_legacy_signed_cookie_cannot_select_private_demo_namespace(setup):
    store, _ = setup
    trial = store.register_trial(username="private", display_name="Private", password=PASSWORD, admission_hash="synthetic")
    assert service._cookie_auth(service._session_cookie(trial["storage_user_id"])) is None
    assert service._cookie_auth(service._session_cookie("local_user")).mode == "legacy"


def request(ip="192.0.2.1"):
    return Request({"type": "http", "client": (ip, 123), "headers": [], "method": "POST", "path": "/"})


def test_login_limit_normalizes_username_and_is_thread_safe(setup):
    def attempt(index):
        try:
            service._login_rate_limit(request(), "owner" + "!" * index)
            return True
        except HTTPException as exc:
            assert exc.status_code == 429
            return False
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(attempt, range(15)))
    assert sum(results) == service.LOGIN_RATE_LIMIT_MAX


def test_recovery_limits_cross_ip_same_account_without_blocking_login(setup):
    for index in range(10):
        service._recovery_rate_limit(request(f"192.0.2.{index}"), "owner" + "!" * index)
    with pytest.raises(HTTPException) as exc:
        service._recovery_rate_limit(request("192.0.2.99"), "owner")
    assert exc.value.status_code == 429 and "Retry-After" in exc.value.headers
    service._login_rate_limit(request(), "owner")
    assert all("owner" not in key and "192.0.2" not in key for key in service._RECOVERY_RATE_STATE)


def test_corrupt_store_never_becomes_new_accounts_through_recovery(setup):
    store, owner = setup
    store.path.write_text("{broken")
    response = reset(TestClient(service.app, base_url=BASE), owner["recovery_codes"][0])
    assert response.status_code == 503 and store.path.read_text() == "{broken"
    assert owner["recovery_codes"][0] not in response.text


def test_trusted_render_origin_works_behind_internal_http_without_trusting_client_forwarded_headers(setup, monkeypatch):
    _, owner = setup
    monkeypatch.setenv("RENDER_EXTERNAL_URL", BASE)
    client = TestClient(service.app, base_url="http://roxy.test")
    assert reset(client, "not-a-code").status_code == 401  # Reached verifier, not CSRF denial.
    malicious = client.post("/v1/home-account/recovery/reset",
                            headers={"Origin": "https://evil.test", "X-Forwarded-Proto": "https", "X-Forwarded-Host": "evil.test"},
                            json={"username": "owner", "recovery_code": owner["recovery_codes"][0], "new_password": NEW_PASSWORD})
    assert malicious.status_code == 403
    assert reset(client, owner["recovery_codes"][0]).status_code == 200


@pytest.mark.parametrize("configured", ["https://other.test", "http://roxy.test", "https://roxy.test/path", "https://user@roxy.test", "https://roxy.test?x=1", "https://roxy.test:bad"])
def test_invalid_deployment_origin_fails_closed(setup, monkeypatch, configured):
    _, owner = setup
    monkeypatch.setenv("ROXY_HOME_PUBLIC_ORIGIN", configured)
    assert reset(TestClient(service.app, base_url=BASE), owner["recovery_codes"][0]).status_code == 403
