"""Provider HTTP boundary: synthetic data, no paid requests or production state."""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_recipe_provider import ProviderRecipe
from tools import roxy_home_service as service


BASE = "/v1/home-food/local_user/providers/recipes"


@pytest.fixture
def tester(tmp_path, monkeypatch):
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-provider-home-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "local_user,other_home")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "food.json"))
    monkeypatch.setenv("ROXY_HOME_RECIPE_LIBRARY_PATH", str(tmp_path / "library.sqlite"))
    monkeypatch.setenv("ROXY_HOME_RECIPE_PROVIDER_ENABLED", "0")
    monkeypatch.delenv("ROXY_HOME_THEMEALDB_API_KEY", raising=False)
    monkeypatch.delenv("ROXY_HOME_THEMEALDB_COMMERCIAL_LICENSE_CONFIRMED", raising=False)
    monkeypatch.setattr(service.recipe_provider.requests, "get", lambda *a, **k: pytest.fail("Unexpected external request"))
    service._RATE_STATE.clear()
    client = TestClient(service.app, base_url="https://roxy.test")
    client.cookies.set(service.SESSION_COOKIE, service._session_cookie("local_user"))
    return client


def synthetic_recipe():
    return ProviderRecipe("52772", json.dumps({
        "provider": "themealdb", "provider_id": "52772", "title": "Synthetic omelette",
        "language": "en", "instructions": "Beat the eggs.\r\nCook until set.",
        "ingredients": [{"name": "Eggs", "measure": "2", "quantity": None, "unit": None}],
        "image_url": "https://www.themealdb.com/images/media/meals/synthetic.jpg",
        "source_url": "https://www.themealdb.com/",
    }), "synthetic_test_rights")


@pytest.mark.parametrize("suffix", ["/status", "/search?q=eggs&requested=true", "/52772?requested=true"])
def test_provider_requires_auth_and_matching_household(tester, suffix):
    assert tester.get(BASE.replace("local_user", "other_home") + suffix).status_code == 403
    tester.cookies.clear()
    assert tester.get(BASE + suffix).status_code == 401
    assert tester.get(BASE + suffix, headers={"Authorization": "Bearer wrong"}).status_code == 403


def test_status_reads_configuration_only_and_never_exposes_key(tester, monkeypatch):
    monkeypatch.setenv("ROXY_HOME_RECIPE_PROVIDER_ENABLED", "1")
    monkeypatch.setenv("ROXY_HOME_THEMEALDB_API_KEY", "synthetic-private-provider-key")
    monkeypatch.setenv("ROXY_HOME_THEMEALDB_COMMERCIAL_LICENSE_CONFIRMED", "1")
    monkeypatch.setattr(service, "_home_food_store", lambda: pytest.fail("Status must not access household data"))
    response = tester.get(BASE + "/status")
    assert response.status_code == 200
    status = response.json()
    assert status["available"] and status["access_allowed"]
    assert status["status"] == "configured_not_live_verified"
    assert not status["live_verified"] and status["explicit_request_required"]
    assert "synthetic-private-provider-key" not in response.text
    assert "no-store" in response.headers["Cache-Control"]


@pytest.mark.parametrize("suffix", ["/search?q=eggs", "/52772"])
def test_provider_requires_deliberate_request_and_does_not_auto_fallback(tester, suffix):
    url = BASE + suffix
    separator = "&" if "?" in suffix else "?"
    assert tester.get(url).status_code == 409
    assert tester.get(url + separator + "requested=false").status_code == 409
    assert tester.get(url + separator + "requested=true").status_code == 503


@pytest.mark.parametrize("query", ["q=e", "q=" + "a" * 101, "q=eggs&limit=0", "q=eggs&limit=21",
                                   "q=eggs&audience=pet", "q=eggs&audience=ferret", "q=eggs&requested=perhaps"])
def test_search_rejects_invalid_input_before_provider(tester, query, monkeypatch):
    monkeypatch.setattr(service.recipe_provider, "search_provider_recipes", lambda *a, **k: pytest.fail("Invalid request reached adapter"))
    assert tester.get(BASE + "/search?" + query).status_code == 422


def test_search_preserves_original_and_never_reads_or_mutates_home(tester, monkeypatch):
    calls = []
    monkeypatch.setattr(service, "_home_food_store", lambda: pytest.fail("Search must not access household data"))
    monkeypatch.setattr(service, "_recipe_library_store", lambda: pytest.fail("No persistence without review"))
    def search(q, **kwargs):
        calls.append((q, kwargs))
        return (synthetic_recipe(),)
    monkeypatch.setattr(service.recipe_provider, "search_provider_recipes", search)
    response = tester.get(BASE + "/search?q=eggs&limit=3&requested=true")
    assert response.status_code == 200
    payload = response.json()
    assert calls == [("eggs", {"audience": "human", "limit": 3})]
    assert payload["status"] == "RESULTS_NEED_REVIEW" and payload["count"] == 1
    assert payload["review_required"] and not payload["imported"]
    recipe = payload["recipes"][0]
    assert recipe["servings"] is None and recipe["ingredients"][0]["quantity"] is None
    assert recipe["provider_original"]["instructions"] == "Beat the eggs.\r\nCook until set."
    assert recipe["editorial_status"] == "provider_content_needs_review"
    assert not recipe["can_cook"] and not recipe["can_add_to_shopping"]
    assert "no-store" in response.headers["Cache-Control"]


def test_no_matches_do_not_return_a_random_recipe(tester, monkeypatch):
    monkeypatch.setattr(service.recipe_provider, "search_provider_recipes", lambda *a, **k: ())
    result = tester.get(BASE + "/search?q=eggs&requested=true").json()
    assert result["recipes"] == [] and result["count"] == 0
    assert result["status"] == "NO_PUBLISHABLE_MATCHES"


def test_detail_returns_review_record_and_unknown_id_404(tester, monkeypatch):
    calls = []
    def lookup(provider_id, **kwargs):
        calls.append((provider_id, kwargs))
        return synthetic_recipe() if provider_id == "52772" else None
    monkeypatch.setattr(service.recipe_provider, "get_provider_recipe", lookup)
    result = tester.get(BASE + "/52772?requested=true")
    assert result.status_code == 200 and not result.json()["imported"]
    assert result.json()["recipe"]["servings"] is None
    assert tester.get(BASE + "/99999?requested=true").status_code == 404
    assert calls == [("52772", {"audience": "human"}), ("99999", {"audience": "human"})]
    assert tester.get(BASE + "/52772?requested=true&audience=pet").status_code == 422


@pytest.mark.parametrize("error,status", [(service.recipe_provider.RecipeProviderUnavailable, 503),
                                         (service.recipe_provider.RecipeProviderContentError, 422), (ValueError, 422)])
@pytest.mark.parametrize("suffix,name", [("/search?q=eggs&requested=true", "search_provider_recipes"),
                                        ("/52772?requested=true", "get_provider_recipe")])
def test_provider_errors_are_sanitized(tester, monkeypatch, error, status, suffix, name):
    def fail(*args, **kwargs):
        raise error("secret-key-in-provider-url")
    monkeypatch.setattr(service.recipe_provider, name, fail)
    result = tester.get(BASE + suffix)
    assert result.status_code == status
    assert "secret-key-in-provider-url" not in result.text


@pytest.mark.parametrize("expired", [False, True])
def test_trial_can_read_status_but_not_spend_on_external_recipes(tester, tmp_path, monkeypatch, expired):
    store = HomeAccountStore(tmp_path / "accounts.json")
    member = store.register_trial(username="trial", display_name="Trial", password="long-synthetic-password", admission_hash="synthetic")
    if expired:
        store._mutate(lambda data: data["households"][member["household_id"]]["trial"].update(
            expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()))
    tester.cookies.set(service.SESSION_COOKIE, service._member_session_cookie(member))
    base = BASE.replace("local_user", member["storage_user_id"])
    monkeypatch.setenv("ROXY_HOME_RECIPE_PROVIDER_ENABLED", "1")
    monkeypatch.setenv("ROXY_HOME_THEMEALDB_API_KEY", "synthetic-provider-key")
    monkeypatch.setenv("ROXY_HOME_THEMEALDB_COMMERCIAL_LICENSE_CONFIRMED", "1")
    status = tester.get(base + "/status")
    assert status.status_code == 200
    assert status.json()["available"] and not status.json()["access_allowed"]
    assert status.json()["access_status"] == "not_included_in_demo"
    before = store.path.read_bytes()
    assert tester.get(base + "/search?q=eggs&requested=true").status_code == 403
    assert tester.get(base + "/52772?requested=true").status_code == 403
    assert store.path.read_bytes() == before
    assert tester.get(BASE + "/status").status_code == 403


def test_home_food_includes_read_only_provider_availability(tester, monkeypatch):
    monkeypatch.setattr(service, "_schedule_account_recipe_photo", lambda *a, **k: None)
    monkeypatch.setattr(service, "_recipe_photo_queue", lambda: SimpleNamespace(public_status=lambda: {}))
    monkeypatch.setattr(service, "_recipe_video_public_status", lambda: {})
    monkeypatch.setattr(service, "_home_voice_config", lambda: SimpleNamespace(public_status=lambda: {}))
    response = tester.get("/v1/home-food/local_user")
    assert response.status_code == 200
    assert response.json()["recipe_provider_service"]["status"] == "disabled"
    assert not response.json()["recipe_provider_service"]["access_allowed"]
