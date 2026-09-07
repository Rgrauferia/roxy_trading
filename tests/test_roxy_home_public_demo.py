from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json

import pytest
from fastapi.testclient import TestClient

from roxy_os.home_accounts import HomeAccountStore, HomeAccountStorageError, HomeTrialLimitError
from roxy_os.home_demo import DEMO_NOTICE_VERSION, registration_config, trial_access_mode, verify_signup_token
from tools import roxy_home_service as service


@pytest.fixture
def demo(tmp_path, monkeypatch):
    for name, filename in {"ROXY_HOME_ACCOUNTS_PATH":"accounts.json", "ROXY_SHOPPING_LIST_PATH":"shopping.json",
                           "ROXY_HOME_MEMORY_PATH":"food.json", "ROXY_HOME_COMMERCE_PATH":"commerce.json",
                           "ROXY_HOME_CONVERSATION_PATH":"conversation.json"}.items():
        monkeypatch.setenv(name, str(tmp_path / filename))
    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-demo-test-only")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "local_user")
    monkeypatch.setenv("ROXY_HOME_PUBLIC_SIGNUP_ENABLED", "1")
    monkeypatch.setenv("ROXY_HOME_TURNSTILE_SITE_KEY", "synthetic-site-key")
    monkeypatch.setenv("ROXY_HOME_TURNSTILE_SECRET_KEY", "synthetic-secret-key")
    monkeypatch.setenv("ROXY_HOME_SIGNUP_HOSTS", "roxy.test")
    monkeypatch.setattr(service, "verify_signup_token", lambda token: token == "verified-test-token")
    service._RATE_STATE.clear()
    service._LOGIN_RATE_STATE.clear()
    return HomeAccountStore(tmp_path / "accounts.json")


def client():
    return TestClient(service.app, base_url="https://roxy.test")


def signup(tester, username="trialone", **overrides):
    payload = {"username":username, "display_name":"Demo", "password":"a-long-test-password",
               "verification_token":"verified-test-token", "acknowledged":True, "notice_version":DEMO_NOTICE_VERSION}
    return tester.post("/v1/home-account/register", json={**payload, **overrides}, headers={"Origin":"https://roxy.test"})


def test_registration_disabled_by_default_and_missing_or_test_keys_fail_closed(monkeypatch):
    for key in ("ROXY_HOME_PUBLIC_SIGNUP_ENABLED", "ROXY_HOME_TURNSTILE_SITE_KEY", "ROXY_HOME_TURNSTILE_SECRET_KEY", "ROXY_HOME_SIGNUP_HOSTS"):
        monkeypatch.delenv(key, raising=False)
    assert registration_config()["enabled"] is False
    monkeypatch.setenv("ROXY_HOME_PUBLIC_SIGNUP_ENABLED", "1")
    assert not registration_config()["enabled"]
    monkeypatch.setenv("ROXY_HOME_TURNSTILE_SITE_KEY", "1x00000000000000000000AA")
    monkeypatch.setenv("ROXY_HOME_TURNSTILE_SECRET_KEY", "1x0000000000000000000000000000000AA")
    monkeypatch.setenv("ROXY_HOME_SIGNUP_HOSTS", "roxy.test")
    assert not registration_config()["enabled"]
    assert signup(client()).status_code == 503


def test_signup_has_no_namespace_override_and_preserves_existing_household(demo):
    owner = demo.bootstrap("local_user", household_name="Original", username="owner", display_name="Original", password="original-password")
    first, second = client(), client()
    assert signup(first, storage_user_id="local_user").status_code == 422
    one, two = signup(first), signup(second, "trialtwo")
    assert one.status_code == two.status_code == 201
    one, two = one.json(), two.json()
    assert len({owner["household_id"], one["household_id"], two["household_id"]}) == 3
    assert one["storage_user_id"].startswith("demo_")
    assert demo.member(owner["id"])["household_name"] == "Original"
    assert demo.member(owner["id"])["trial"] is None
    assert one["trial"]["days"] == 5 and not one["trial"]["auto_charge"]
    assert "password_hash" not in str(one) and "admission_hash" not in str(one)
    assert first.post('/v1/shopping/' + one["storage_user_id"], json={"name":"Manzana privada"}).status_code == 201
    assert first.get('/v1/shopping/' + one["storage_user_id"]).json()["items"]
    assert second.get('/v1/shopping/' + two["storage_user_id"]).json()["items"] == []
    assert second.get('/v1/shopping/' + one["storage_user_id"]).status_code == 403
    assert second.get('/v1/home-food/' + one["storage_user_id"]).status_code == 403
    assert first.get('/v1/shopping/local_user').status_code == 403
    assert client().get('/v1/shopping/' + one["storage_user_id"], headers={"Authorization":"Bearer home-demo-test-only"}).status_code == 403


def test_trial_pet_products_are_private_and_expiration_blocks_additions(demo):
    from roxy_os.home_pet_catalog import personalized_pet_products
    tester, outsider = client(), client()
    member = signup(tester).json()
    signup(outsider, "trialtwo")
    namespace = member["storage_user_id"]
    pet = service._home_food_store().upsert_pet(namespace, name="Prueba", species="ferret", life_stage="adult")
    product = next(p for p in personalized_pet_products(pet) if p["brand"] == "Kaytee")
    path = f"/v1/home-food/{namespace}/pets/{pet['id']}/products/{product['id']}/shopping"
    assert outsider.post(path, json={"confirmed": True}).status_code == 403
    assert tester.post(path, json={"confirmed": True}).status_code == 201
    before = service._store().list_items(namespace)
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    demo._mutate(lambda data: data["households"][member["household_id"]]["trial"].update(expires_at=expired))
    assert tester.post(path, json={"confirmed": True}).status_code == 403
    assert service._store().list_items(namespace) == before


def test_signup_requires_verification_acknowledgement_and_durable_admission_caps(demo):
    tester = client()
    assert signup(tester, verification_token="bad-token").status_code == 422
    assert signup(tester, acknowledged=False).status_code == 422
    assert signup(tester, notice_version="old").status_code == 422
    assert not demo.path.exists()
    assert signup(tester).status_code == 201
    assert signup(client(), "second").status_code == 201
    assert signup(client(), "third").status_code == 201
    service._LOGIN_RATE_STATE.clear()
    assert signup(client(), "fourth").status_code == 429
    assert len(json.loads(demo.path.read_text())["households"]) == 3


def test_trial_expiry_is_server_side_read_only_and_login_does_not_reset_it(demo):
    tester = client()
    member = signup(tester).json()
    household_id, namespace = member["household_id"], member["storage_user_id"]
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    demo._mutate(lambda payload: payload["households"][household_id]["trial"].update(expires_at=expired))
    assert tester.get('/v1/home-account/me').json()["trial"]["status"] == "EXPIRED"
    assert tester.get('/v1/shopping/' + namespace).status_code == 200
    assert tester.post('/v1/shopping/' + namespace, json={"name":"Bloqueado"}).status_code == 403
    assert tester.post('/v1/home-account/login', json={"username":"trialone", "password":"a-long-test-password"}).json()["trial"]["expires_at"] == expired
    assert demo.member(member["id"]) is not None


def test_trial_budget_is_atomic_shared_and_survives_new_store_instance(demo):
    member = demo.register_trial(username="one", display_name="One", password="one-test-password", admission_hash="test")
    partner = demo.add_member(member["id"], username="two", display_name="Two", password="two-test-password")
    def reserve(index):
        try:
            HomeAccountStore(demo.path).reserve_trial_request(member["id"] if index % 2 else partner["id"])
            return True
        except HomeTrialLimitError:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(12))) == 5
    assert demo.member(member["id"])["trial"]["ai_remaining_today"] == 0
    with pytest.raises(HomeTrialLimitError):
        demo.reserve_trial_request(partner["id"])


def test_trial_api_enforces_request_budget_and_foreign_origin(demo):
    tester = client()
    assert tester.post('/v1/home-account/register', json={"username":"trial", "display_name":"Test", "password":"a-long-test-password", "verification_token":"verified-test-token", "acknowledged":True, "notice_version":DEMO_NOTICE_VERSION}, headers={"Origin":"https://elsewhere.test"}).status_code == 403
    member = signup(tester).json()
    for _ in range(5):
        result = tester.post('/v1/assistant/command/' + member['storage_user_id'], json={"text":"qué hay en mi lista de compras"})
        assert result.status_code == 200
    assert tester.post('/v1/assistant/command/' + member['storage_user_id'], json={"text":"qué hay en mi lista de compras"}).status_code == 429
    assert tester.get('/v1/home-account/me').json()['trial']['ai_remaining_today'] == 0


def test_trial_api_cannot_start_paid_media_even_with_configured_provider(demo, monkeypatch):
    tester = client()
    namespace = signup(tester).json()["storage_user_id"]
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "test-agent")
    assert tester.get('/v1/assistant/session/' + namespace).status_code == 403
    assert tester.post(f'/v1/home-design/{namespace}/projects/project/proposal', json={}).status_code == 403
    assert tester.post(f'/v1/home-food/{namespace}/recipes/recipe/video', json={}).status_code == 403
    assert tester.post(f'/v1/home-food/{namespace}/cooking-sessions/session/speech', json={}).status_code == 403
    assert trial_access_mode("POST", "/v1/new-expensive-provider/demo") == "unavailable"
    monkeypatch.setattr(service, "_schedule_recipe_photo", lambda recipe: pytest.fail("Trial GET scheduled paid artwork"))
    food = tester.get('/v1/home-food/' + namespace)
    assert food.status_code == 200 and food.json()["pets"] == []


@pytest.mark.parametrize("raw", ['{invalid', '[]', '{"households":{},"members":[]}', '{"households":{},"members":{"bad":null}}'])
def test_corrupt_accounts_are_preserved_not_replaced(tmp_path, raw):
    path = tmp_path / 'accounts.json'
    path.write_text(raw)
    store = HomeAccountStore(path)
    with pytest.raises(HomeAccountStorageError):
        store.register_trial(username="one", display_name="One", password="one-test-password", admission_hash="test")
    assert path.read_text() == raw


def test_turnstile_verifies_hostname_action_age_and_fails_closed(demo, monkeypatch):
    from roxy_os import home_demo
    result = {"success":True, "hostname":"roxy.test", "action":"home_signup", "challenge_ts":datetime.now(timezone.utc).isoformat()}
    class Response:
        def raise_for_status(self): pass
        def json(self): return dict(result)
    def post(url, **kwargs):
        assert url == "https://challenges.cloudflare.com/turnstile/v0/siteverify"
        assert kwargs["timeout"] == 10 and kwargs["json"]["response"] == "valid-token"
        return Response()
    monkeypatch.setattr(home_demo.requests, "post", post)
    assert verify_signup_token("valid-token")
    for field, bad_value in [("hostname","other.test"), ("action","login"), ("success",False), ("challenge_ts", "invalid")]:
        old = result[field]; result[field] = bad_value
        assert not verify_signup_token("valid-token")
        result[field] = old
    result["challenge_ts"] = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
    assert not verify_signup_token("valid-token")


def test_public_image_request_cannot_generate_or_search_private_recipes(demo, monkeypatch):
    monkeypatch.setattr(service, "_schedule_recipe_photo", lambda recipe: pytest.fail("Anonymous image request spent credits"))
    class Missing:
        def resolve(self, title): return None
    monkeypatch.setattr(service, "_recipe_photo_store", lambda: Missing())
    assert client().get('/v1/home-food/recipe-photo', params={"title":"Café americano"}).status_code == 404
    assert client().get('/v1/home-food/recipe-photo', params={"title":"Mi secreto privado"}).status_code == 404


def test_private_api_responses_are_never_shared_cacheable(demo):
    response = signup(client())
    assert response.headers['cache-control'] == 'private, no-store'
    assert 'HttpOnly' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
    assert response.headers['vary'] == 'Cookie, Authorization'
