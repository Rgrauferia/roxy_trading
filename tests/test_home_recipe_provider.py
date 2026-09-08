"""Synthetic contracts only: no live provider calls or catalog downloads."""
from dataclasses import FrozenInstanceError, replace
import json

import pytest

from roxy_os.home_recipe_provider import (
    HomeRecipeProviderConfig,
    MAX_RESPONSE_BYTES,
    RecipeProviderContentError,
    RecipeProviderUnavailable,
    get_provider_recipe,
    recipe_provider_availability,
    search_provider_recipes,
)


def config(**changes):
    return replace(HomeRecipeProviderConfig(enabled=True, commercial_license_confirmed=True,
                                           api_key="synthetic-home-key"), **changes)


def meal(**changes):
    return {
        "idMeal": "52772", "strMeal": "Synthetic omelette", "strCategory": "Breakfast",
        "strArea": "Test", "strInstructions": "Beat the eggs.\r\nCook in the pan until set.",
        "strIngredient1": "Eggs", "strMeasure1": "2", "strIngredient2": "Salt", "strMeasure2": "to taste",
        "strMealThumb": "https://www.themealdb.com/images/media/meals/synthetic.jpg",
        "strSource": None, "strImageSource": None, "strCreativeCommonsConfirmed": "Yes", **changes,
    }


class Response:
    def __init__(self, payload=None, *, body=None, status=200, content_type="application/json"):
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.body = body if body is not None else json.dumps(payload).encode()
        self.closed = False

    def iter_content(self, chunk_size):
        for index in range(0, len(self.body), chunk_size):
            yield self.body[index:index + chunk_size]

    def close(self):
        self.closed = True


def transport_for(payload=None, **kwargs):
    response = Response(payload, **kwargs)
    calls = []

    def transport(url, **options):
        calls.append((url, options))
        return response

    return transport, calls, response


@pytest.mark.parametrize("change", [
    {"enabled": False}, {"commercial_license_confirmed": False}, {"api_key": ""},
    {"api_key": "1"}, {"api_key": "test"}, {"api_key": "YOUR_API_KEY"}, {"api_key": "secret/redirect"},
])
def test_disabled_or_unlicensed_cannot_call_provider(change):
    transport, calls, _ = transport_for({"meals": [meal()]})
    with pytest.raises(RecipeProviderUnavailable):
        search_provider_recipes("eggs", config=config(**change), transport=transport)
    assert not calls


def test_availability_is_read_only_sanitized_and_not_a_live_verification(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: pytest.fail("unexpected network"))
    summary = recipe_provider_availability(config())
    assert summary["available"] and summary["status"] == "configured_not_live_verified"
    assert not summary["live_verified"] and summary["requires_editorial_review"]
    assert "synthetic-home-key" not in json.dumps(summary) + repr(config())
    assert recipe_provider_availability(HomeRecipeProviderConfig())["status"] == "disabled"
    assert recipe_provider_availability(config(api_key=""))["status"] == "awaiting_commercial_key"
    assert recipe_provider_availability(config(commercial_license_confirmed=False))["status"] == "awaiting_license_confirmation"


def test_env_config_is_home_only_defaults_off_and_bounds_invalid_numbers(monkeypatch):
    for name in list(__import__("os").environ):
        if name.startswith(("ROXY_HOME_RECIPE_PROVIDER_", "ROXY_HOME_THEMEALDB_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("SPOONACULAR_API_KEY", "other-product-do-not-use")
    assert HomeRecipeProviderConfig.from_env() == HomeRecipeProviderConfig()
    monkeypatch.setenv("ROXY_HOME_RECIPE_PROVIDER_TIMEOUT_SECONDS", "NaN")
    monkeypatch.setenv("ROXY_HOME_RECIPE_PROVIDER_MAX_RESULTS", "9999")
    monkeypatch.setenv("ROXY_HOME_THEMEALDB_LICENSED_RECIPE_IDS", "52772, invalid,52772, 10")
    actual = HomeRecipeProviderConfig.from_env()
    assert actual.timeout_seconds == 5 and actual.max_results == 20
    assert actual.licensed_recipe_ids == ("10", "52772")


def test_original_is_immutable_and_no_translation_quantity_or_servings_invented():
    transport, calls, response = transport_for({"meals": [meal()]})
    recipe = get_provider_recipe("52772", config=config(), transport=transport)
    assert recipe is not None
    view = recipe.to_dict()
    assert view["provider_original"]["instructions"] == meal()["strInstructions"]
    assert view["steps"] == ["Beat the eggs.", "Cook in the pan until set."]
    assert view["servings"] is None and view["language"] == "en"
    assert view["ingredients"][0] == {"name": "Eggs", "measure": "2", "quantity": None, "unit": None}
    assert view["ingredients"][1]["measure"] == "to taste"
    assert not view["can_cook"] and not view["can_add_to_shopping"] and not view["photo_verified"]
    assert view["editorial_status"] == "provider_content_needs_review"
    assert view["sources"][0]["url"] == "https://www.themealdb.com/"
    view["provider_original"]["ingredients"][0]["name"] = "Mutation"
    assert recipe.to_dict()["provider_original"]["ingredients"][0]["name"] == "Eggs"
    with pytest.raises(FrozenInstanceError):
        recipe.original_json = "{}"
    assert response.closed and len(calls) == 1
    assert calls[0][1] == {"params": {"i": "52772"}, "timeout": (3.0, 5.0), "allow_redirects": False, "stream": True}


@pytest.mark.parametrize("audience", ["pet", "ferret", "fish", "dog", "Human", ""])
def test_human_provider_never_feeds_pets(audience):
    transport, calls, _ = transport_for({"meals": [meal()]})
    with pytest.raises(RecipeProviderUnavailable, match="human_recipes_only"):
        get_provider_recipe("52772", audience=audience, config=config(), transport=transport)
    assert not calls


@pytest.mark.parametrize("change", [
    {"strInstructions": ""}, {"strMeal": None}, {"strIngredient1": ""},
    {"strMeasure1": ""}, {"strMealThumb": ""}, {"strCreativeCommonsConfirmed": None},
    {"strSource": "https://third-party.example/recipe"},
    {"strImageSource": "https://third-party.example/image"},
    {"strSource": "javascript:alert(1)"}, {"strSource": "https://user:password@example.com/"},
    {"strSource": "https://[invalid"},
    {"strMealThumb": "https://www.themealdb.com.evil.example/images/media/meals/x.jpg"},
    {"strMealThumb": "https://www.themealdb.com/api/json/v1/key/search.php"},
])
def test_missing_content_or_unconfirmed_rights_fail_closed(change):
    transport, _, response = transport_for({"meals": [meal(**change)]})
    with pytest.raises(RecipeProviderContentError):
        get_provider_recipe("52772", config=config(), transport=transport)
    assert response.closed


def test_third_party_requires_separate_operator_rights_for_exact_id():
    raw = meal(strSource="https://publisher.example/synthetic-recipe", strCreativeCommonsConfirmed=None)
    transport, _, _ = transport_for({"meals": [raw]})
    record = get_provider_recipe("52772", config=config(licensed_recipe_ids=("52772",)), transport=transport)
    assert record.to_dict()["provider_original"]["source_url"] == raw["strSource"]
    assert record.rights_basis == "operator_documented_recipe_and_image_license"
    transport, _, _ = transport_for({"meals": [raw]})
    with pytest.raises(RecipeProviderContentError):
        get_provider_recipe("52772", config=config(licensed_recipe_ids=("12345",)), transport=transport)


def test_search_limits_deduplicates_and_excludes_rejected_rows():
    rows = [meal(strMeasure1=""), meal(), meal()]
    rows += [meal(idMeal=str(100 + i)) for i in range(25)]
    transport, calls, _ = transport_for({"meals": rows})
    results = search_provider_recipes(" egg ", limit=999, config=config(max_results=2), transport=transport)
    assert len(results) == 2 and len({row.provider_id for row in results}) == 2
    assert len(calls) == 1 and calls[0][1]["params"] == {"s": "egg"}


@pytest.mark.parametrize("payload", [{}, {"meals": {}}, {"meals": [meal()] * 101}, []])
def test_malformed_or_excessive_payload_does_not_become_catalog(payload):
    transport, _, response = transport_for(payload)
    with pytest.raises(RecipeProviderUnavailable):
        search_provider_recipes("egg", config=config(), transport=transport)
    assert response.closed


@pytest.mark.parametrize("options", [
    {"status": 302}, {"status": 429}, {"status": 500}, {"content_type": "text/html"},
    {"body": b"{"}, {"body": b"x" * (MAX_RESPONSE_BYTES + 1)},
])
def test_provider_failure_never_leaks_key_or_response_body(options):
    transport, _, response = transport_for({"secret": "do-not-expose"}, **options)
    with pytest.raises(RecipeProviderUnavailable) as exc:
        search_provider_recipes("egg", config=config(), transport=transport)
    assert "synthetic-home-key" not in str(exc.value) and "do-not-expose" not in str(exc.value)
    assert response.closed


def test_transport_error_is_sanitized_and_not_chained():
    def broken(*args, **kwargs):
        raise RuntimeError("https://www.themealdb.com/api/json/v1/synthetic-home-key/lookup.php")
    with pytest.raises(RecipeProviderUnavailable) as exc:
        get_provider_recipe("52772", config=config(), transport=broken)
    assert str(exc.value) == "recipe_provider_request_failed" and exc.value.__suppress_context__


def test_slow_stream_is_stopped_at_deadline(monkeypatch):
    times = iter([0, 11])
    monkeypatch.setattr("roxy_os.home_recipe_provider.time.monotonic", lambda: next(times))
    transport, _, response = transport_for({"meals": [meal()]})
    with pytest.raises(RecipeProviderUnavailable, match="deadline_exceeded"):
        get_provider_recipe("52772", config=config(), transport=transport)
    assert response.closed


def test_no_result_is_distinct_from_bad_recipe_and_id_substitution():
    transport, _, _ = transport_for({"meals": None})
    assert get_provider_recipe("52772", config=config(), transport=transport) is None
    transport, _, _ = transport_for({"meals": [meal(idMeal="999")]})
    with pytest.raises(RecipeProviderContentError, match="provider_id_mismatch"):
        get_provider_recipe("52772", config=config(), transport=transport)


@pytest.mark.parametrize("query", ["", "e", "e" * 101, "egg\n", None])
def test_invalid_queries_never_make_requests(query):
    transport, calls, _ = transport_for({"meals": []})
    with pytest.raises(ValueError):
        search_provider_recipes(query, config=config(), transport=transport)
    assert not calls


@pytest.fixture
def provider_client(monkeypatch):
    from fastapi.testclient import TestClient
    from tools import roxy_home_service as service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-api-access")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_RECIPE_PROVIDER_ENABLED", "0")
    monkeypatch.setenv("ROXY_HOME_THEMEALDB_API_KEY", "")
    monkeypatch.setenv("ROXY_HOME_THEMEALDB_COMMERCIAL_LICENSE_CONFIRMED", "0")
    monkeypatch.setenv("ROXY_HOME_THEMEALDB_LICENSED_RECIPE_IDS", "")
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: pytest.fail("unexpected provider request"))
    # These GET-only routes must not read/mutate private data or schedule media.
    for name in ("_home_food_store", "_recipe_library_store", "_recipe_photo_queue", "_home_ai"):
        monkeypatch.setattr(service, name, lambda: pytest.fail("unexpected private store/AI access"))
    service._RATE_STATE.clear()
    with TestClient(service.app) as client:
        yield client, service, {"Authorization": "Bearer synthetic-api-access"}


def enable_api_provider(monkeypatch, payload):
    monkeypatch.setenv("ROXY_HOME_RECIPE_PROVIDER_ENABLED", "1")
    monkeypatch.setenv("ROXY_HOME_THEMEALDB_API_KEY", "synthetic-provider-key")
    monkeypatch.setenv("ROXY_HOME_THEMEALDB_COMMERCIAL_LICENSE_CONFIRMED", "1")
    transport, calls, response = transport_for(payload)
    monkeypatch.setattr("requests.get", transport)
    return calls, response


def test_provider_routes_require_auth_and_match_household(provider_client):
    client, service, headers = provider_client
    paths = ["status", "search?q=egg&requested=true", "52772?requested=true"]
    for path in paths:
        response = client.get(f"/v1/home-food/robert/providers/recipes/{path}")
        assert response.status_code == 401
        response = client.get(f"/v1/home-food/mallory/providers/recipes/{path}", headers=headers)
        assert response.status_code == 403
    client.cookies.set(service.SESSION_COOKIE, service._session_cookie("robert"))
    for path in paths:
        assert client.get(f"/v1/home-food/alice/providers/recipes/{path}").status_code == 403


def test_provider_status_is_safe_no_network_no_private_store(provider_client):
    client, _, headers = provider_client
    response = client.get("/v1/home-food/robert/providers/recipes/status", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert response.json()["live_verified"] is False
    assert "synthetic" not in response.text


@pytest.mark.parametrize("path", ["search?q=egg", "52772"])
def test_provider_routes_require_deliberate_request_and_config(provider_client, path):
    client, _, headers = provider_client
    url = f"/v1/home-food/robert/providers/recipes/{path}"
    assert client.get(url, headers=headers).status_code == 409
    separator = "&" if "?" in url else "?"
    assert client.get(url + separator + "requested=true", headers=headers).status_code == 503
    assert client.post(url, headers=headers).status_code == 405


@pytest.mark.parametrize("params", [
    {"q": ""}, {"q": "x" * 101}, {"q": "egg", "limit": 0}, {"q": "egg", "limit": 21},
    {"q": "egg", "audience": "pet"}, {"q": "egg", "audience": "ferret"},
])
def test_provider_route_query_bounds_before_any_external_call(provider_client, params):
    client, _, headers = provider_client
    response = client.get("/v1/home-food/robert/providers/recipes/search", headers=headers,
                          params={"requested": "true", **params})
    assert response.status_code == 422


def test_search_route_sends_only_query_preserves_original_and_never_saves(provider_client, monkeypatch):
    client, _, headers = provider_client
    calls, response = enable_api_provider(monkeypatch, {"meals": [meal()]})
    actual = client.get("/v1/home-food/robert/providers/recipes/search", headers=headers,
                        params={"q": "egg", "requested": "true", "limit": 2})
    assert actual.status_code == 200
    body = actual.json()
    assert body["count"] == 1 and body["status"] == "RESULTS_NEED_REVIEW"
    assert body["imported"] is False and body["review_required"] is True
    assert body["recipes"][0]["provider_original"]["instructions"] == meal()["strInstructions"]
    assert body["recipes"][0]["servings"] is None and body["recipes"][0]["language"] == "en"
    assert len(calls) == 1 and calls[0][1]["params"] == {"s": "egg"}
    assert "robert" not in str(calls) and "synthetic-provider-key" not in actual.text
    assert response.closed


def test_detail_route_preserves_original_and_missing_vs_rejected_distinction(provider_client, monkeypatch):
    client, _, headers = provider_client
    url = "/v1/home-food/robert/providers/recipes/52772?requested=true"
    calls, _ = enable_api_provider(monkeypatch, {"meals": [meal()]})
    result = client.get(url, headers=headers)
    assert result.status_code == 200 and result.json()["imported"] is False
    assert result.json()["recipe"]["provider_id"] == "52772"
    assert calls[0][1]["params"] == {"i": "52772"}
    enable_api_provider(monkeypatch, {"meals": None})
    assert client.get(url, headers=headers).status_code == 404
    enable_api_provider(monkeypatch, {"meals": [meal(strInstructions="")]})
    assert client.get(url, headers=headers).status_code == 422


def test_network_error_response_does_not_expose_provider_details(provider_client, monkeypatch):
    client, _, headers = provider_client
    enable_api_provider(monkeypatch, {"meals": []})
    def failed(*args, **kwargs):
        raise RuntimeError("secret provider key and private URL")
    monkeypatch.setattr("requests.get", failed)
    result = client.get("/v1/home-food/robert/providers/recipes/search?q=egg&requested=true", headers=headers)
    assert result.status_code == 503
    assert "secret" not in result.text and "synthetic-provider-key" not in result.text


@pytest.mark.parametrize("trial_status", ["ACTIVE", "EXPIRED"])
def test_trial_cannot_spend_unapproved_external_recipe_budget(provider_client, monkeypatch, trial_status):
    client, service, _ = provider_client
    monkeypatch.setattr(service, "_cookie_auth", lambda _: service.AuthContext(
        "member", "demo-house", "member-one", {"status": trial_status}))
    for path in ("search?q=egg&requested=true", "52772?requested=true"):
        result = client.get(f"/v1/home-food/demo-house/providers/recipes/{path}")
        assert result.status_code == 403
    assert client.get("/v1/home-food/demo-house/providers/recipes/status").status_code == 200
