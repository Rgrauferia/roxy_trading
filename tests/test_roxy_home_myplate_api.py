"""MyPlate browsing authorization contracts; no live provider requests or recipes."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_demo import trial_access_mode
from tools import roxy_home_service as service


BASE = "/v1/home-food/myplate_test/myplate-recipes"
SUMMARY = {"slug": "synthetic-dish", "title": "Synthetic dish for tests",
           "description": "Test fixture only", "category": "Main dish", "language": "en",
           "image_url": "https://storage.googleapis.com/peppermint-cdn/myplate.food-recipe-images/synthetic-dish.jpg",
           "source_url": "https://myplate.food/recipes/synthetic-dish", "translation_urls": {}}
DETAIL = {**SUMMARY, "ingredients": [{"text": "1/2 cup synthetic food", "note": "Test only"}],
          "directions": "Synthetic test instructions. Preserve the exact text, including 1.5 and 1/2.",
          "yield": "2 synthetic servings", "serving_size": "1/2 synthetic portion", "notes": "Not a recipe",
          "contributor": "Synthetic test contributor", "source": "Synthetic fixture",
          "can_cook": False, "can_add_to_shopping": False}


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-myplate-api-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "myplate_test,other_home")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setattr("requests.get", lambda *a, **kw: pytest.fail("No provider network in API tests"))
    monkeypatch.setattr("requests.post", lambda *a, **kw: pytest.fail("No POST in source browser"))
    for name in ("_home_food_store", "_recipe_library_store", "_recipe_photo_queue", "_home_ai"):
        monkeypatch.setattr(service, name, lambda: pytest.fail("Source browsing touched private data or AI"))
    calls = []

    def search_recipes(**kwargs):
        calls.append(("search", deepcopy(kwargs)))
        limit, offset = kwargs.get("limit", 24), kwargs.get("offset", 0)
        return {"recipes": [deepcopy(SUMMARY)], "total": 1072, "offset": offset, "limit": limit,
                "next_offset": offset + limit, "category_options": list(service.myplate_recipes.CATEGORY_OPTIONS),
                "source": "Synthetic source", "provider": "MyPlate.food", "live": True, "audience": "human"}

    def get_recipe(slug):
        calls.append(("detail", slug))
        return {"recipe": deepcopy(DETAIL)}

    monkeypatch.setattr(service.myplate_recipes, "search_recipes", search_recipes)
    monkeypatch.setattr(service.myplate_recipes, "get_recipe", get_recipe)
    service._RATE_STATE.clear()
    with TestClient(service.app, base_url="https://myplate-home.test") as client:
        client.cookies.set(service.SESSION_COOKIE, service._session_cookie("myplate_test"))
        yield client, calls


@pytest.mark.parametrize("suffix", ["", "/synthetic-dish"])
def test_source_requires_authenticated_matching_household(api_client, suffix):
    client, calls = api_client
    for path, expected in ((BASE.replace("myplate_test", "other_home") + suffix, 403),):
        response = client.get(path, params={"requested": "true"})
        assert response.status_code == expected
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.headers["Vary"] == "Cookie, Authorization"
    assert calls == []
    client.cookies.clear()
    assert client.get(BASE + suffix, params={"requested": "true"}).status_code == 401
    assert client.get(BASE + suffix, params={"requested": "true"}, headers={"Authorization": "Bearer wrong"}).status_code == 403
    assert calls == []


@pytest.mark.parametrize("suffix", ["", "/synthetic-dish"])
@pytest.mark.parametrize("params", [{}, {"requested": "false"}])
def test_source_needs_explicit_request_without_spending_or_loading_on_open(api_client, suffix, params):
    client, calls = api_client
    response = client.get(BASE + suffix, params=params)
    assert response.status_code == 400
    assert response.headers["Cache-Control"] == "private, no-store"
    assert not calls


@pytest.mark.parametrize("params", [
    {"q": "x" * 101}, {"category": "x" * 41}, {"offset": "-1"}, {"offset": "2001"}, {"offset": "1.5"},
    {"limit": "0"}, {"limit": "25"}, {"limit": "true"}, {"requested": "not-a-boolean"},
])
def test_invalid_source_queries_fail_422_before_provider(api_client, params):
    client, calls = api_client
    result = client.get(BASE, params={"requested": "true", **params})
    assert result.status_code == 422
    assert result.headers["Cache-Control"] == "private, no-store"
    assert not calls


def test_source_paging_passes_only_explicit_filters_not_identity_or_secrets(api_client):
    client, calls = api_client
    result = client.get(BASE, params={"requested": "true", "q": "pasta", "category": "Main dish", "offset": 24, "limit": 24})
    assert result.status_code == 200
    assert result.headers["Cache-Control"] == "private, no-store"
    assert calls == [("search", {"q": "pasta", "category": "Main dish", "offset": 24, "limit": 24})]
    assert "myplate_test" not in str(calls) and "synthetic-myplate-api-key" not in result.text
    assert result.json()["recipes"][0]["slug"] == "synthetic-dish"
    assert result.json()["total"] == 1072 and result.json()["offset"] == 24


def test_source_detail_is_original_readonly_and_never_stored(api_client):
    client, calls = api_client
    result = client.get(BASE + "/synthetic-dish", params={"requested": "true"})
    assert result.status_code == 200
    assert result.headers["Cache-Control"] == "private, no-store"
    assert result.json()["recipe"] == DETAIL
    assert calls == [("detail", "synthetic-dish")]
    assert client.post(BASE + "/synthetic-dish", params={"requested": "true"}).status_code == 405
    assert client.post(BASE, params={"requested": "true"}).status_code == 405
    assert len(calls) == 1


@pytest.mark.parametrize("category", ["Breakfast", "Bread", "Side dish"])
def test_native_category_browse_keeps_explicit_readonly_contract(api_client, category):
    client, calls = api_client
    result = client.get(BASE, params={"requested": "true", "category": category})
    assert result.status_code == 200
    assert result.headers["Cache-Control"] == "private, no-store"
    assert calls == [("search", {"q": "", "category": category, "offset": 0, "limit": 24})]
    assert result.json()["category_options"] == list(service.myplate_recipes.CATEGORY_OPTIONS)
    assert "Snack" not in result.json()["category_options"]


@pytest.mark.parametrize("suffix", ["", "/synthetic-dish"])
def test_source_home_rate_limit_precedes_provider(api_client, monkeypatch, suffix):
    client, calls = api_client
    monkeypatch.setattr(service, "RATE_LIMIT_MAX", 1)
    assert client.get(BASE + suffix, params={"requested": "true"}).status_code == 200
    response = client.get(BASE + suffix, params={"requested": "true"})
    assert response.status_code == 429
    assert response.headers["Cache-Control"] == "private, no-store"
    assert len(calls) == 1


@pytest.mark.parametrize("expired", [False, True])
def test_trial_can_read_free_source_without_ai_quota_or_account_mutation(api_client, tmp_path, expired):
    client, calls = api_client
    accounts = HomeAccountStore(tmp_path / "accounts.json")
    member = accounts.register_trial(username="source-reader", display_name="Synthetic Reader",
                                     password="synthetic-long-test-password", admission_hash="test")
    if expired:
        accounts._mutate(lambda data: data["households"][member["household_id"]]["trial"].update(
            expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()))
    client.cookies.set(service.SESSION_COOKIE, service._member_session_cookie(member))
    before = accounts.path.read_bytes()
    for suffix in ("", "/synthetic-dish"):
        path = BASE.replace("myplate_test", member["storage_user_id"]) + suffix
        assert trial_access_mode("GET", path) == "local"
        assert trial_access_mode("POST", path) == "unavailable"
        assert client.get(path, params={"requested": "true"}).status_code == 200
        assert client.get(BASE + suffix, params={"requested": "true"}).status_code == 403
    assert len(calls) == 2
    assert accounts.path.read_bytes() == before


@pytest.mark.parametrize("suffix", ["", "/synthetic-dish"])
def test_unexpected_provider_error_is_redacted(api_client, monkeypatch, suffix):
    client, calls = api_client

    def fail(*args, **kwargs):
        raise RuntimeError("upstream-private-marker key=do-not-leak url=https://private.invalid/")

    monkeypatch.setattr(service.myplate_recipes, "search_recipes", fail)
    monkeypatch.setattr(service.myplate_recipes, "get_recipe", fail)
    result = client.get(BASE + suffix, params={"requested": "true"})
    assert result.status_code == 503
    assert result.headers["Cache-Control"] == "private, no-store"
    assert "upstream-private-marker" not in result.text
    assert "private.invalid" not in result.text and "do-not-leak" not in result.text
    assert not calls


@pytest.mark.parametrize("suffix", ["", "/synthetic-dish"])
def test_provider_rate_limit_preserves_bounded_retry_after_and_redacts_message(api_client, monkeypatch, suffix):
    client, _ = api_client

    def fail(*args, **kwargs):
        raise service.myplate_recipes.MyPlateRecipeError("rate_limited", "upstream-private-marker", 429, 60)

    monkeypatch.setattr(service.myplate_recipes, "search_recipes", fail)
    monkeypatch.setattr(service.myplate_recipes, "get_recipe", fail)
    result = client.get(BASE + suffix, params={"requested": "true"})
    assert result.status_code == 429
    assert result.headers["Retry-After"] == "60"
    assert result.headers["Cache-Control"] == "private, no-store"
    assert "upstream-private-marker" not in result.text


@pytest.mark.parametrize("upstream,expected", [(400, 400), (404, 404), (422, 422), (503, 503), (418, 503), (200, 503)])
def test_provider_error_status_allowlist_never_exposes_messages(api_client, monkeypatch, upstream, expected):
    client, _ = api_client

    def fail(*args, **kwargs):
        raise service.myplate_recipes.MyPlateRecipeError("synthetic_code", "private-upstream-detail", upstream)

    monkeypatch.setattr(service.myplate_recipes, "get_recipe", fail)
    response = client.get(BASE + "/synthetic-dish", params={"requested": "true"})
    assert response.status_code == expected
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "private-upstream-detail" not in response.text and "synthetic_code" not in response.text


@pytest.mark.parametrize("retry,expected", [(-7, "1"), (999999999, "86400"), ("invalid", "60"), (float("inf"), "60")])
def test_provider_retry_header_is_bounded_even_when_adapter_value_is_invalid(api_client, monkeypatch, retry, expected):
    client, _ = api_client

    def fail(*args, **kwargs):
        raise service.myplate_recipes.MyPlateRecipeError("rate_limited", "private-marker", 429, retry)

    monkeypatch.setattr(service.myplate_recipes, "get_recipe", fail)
    response = client.get(BASE + "/synthetic-dish", params={"requested": "true"})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == expected
    assert "private-marker" not in response.text
