"""Cuisine discovery and bounded detail hydration use only synthetic transport."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_demo import trial_access_mode
from roxy_os import home_recipe_provider as provider
from tools import roxy_home_service as service


BASE = "/v1/home-food/countries_test/providers/recipes"


def config(**changes):
    return replace(provider.HomeRecipeProviderConfig(enabled=True, commercial_license_confirmed=True,
                                                      api_key="synthetic-cuisine-provider-key"), **changes)


def meal(identifier="100", **changes):
    return {"idMeal": identifier, "strMeal": "Synthetic source dish", "strCategory": "Test category",
            "strArea": "Italian", "strInstructions": "Original step one.\r\nOriginal step two.",
            "strIngredient1": "Test flour", "strMeasure1": "½ original cup",
            "strIngredient2": "Test seasoning", "strMeasure2": "to taste",
            "strMealThumb": "https://www.themealdb.com/images/media/meals/test.jpg",
            "strSource": None, "strImageSource": None, "strCreativeCommonsConfirmed": "Yes", **changes}


class Response:
    def __init__(self, payload):
        self.status_code = 200
        self.headers = {"Content-Type": "application/json"}
        self.body = json.dumps(payload).encode()
        self.closed = False

    def iter_content(self, chunk_size):
        yield self.body

    def close(self):
        self.closed = True


def transport_for(payloads):
    calls, responses = [], []

    def transport(url, **options):
        endpoint = urlsplit(url).path.rsplit("/", 1)[-1]
        params = options["params"]
        calls.append((endpoint, dict(params), options))
        key = (endpoint, params.get("i") or params.get("a"))
        if key not in payloads:
            pytest.fail(f"Unexpected provider request: {endpoint} {params}")
        response = Response(payloads[key])
        responses.append(response)
        return response

    return transport, calls, responses


@pytest.mark.parametrize("changes", [
    {"enabled": False}, {"commercial_license_confirmed": False}, {"api_key": ""},
    {"api_key": "1"}, {"api_key": "demo"}, {"api_key": "other/endpoint"},
])
@pytest.mark.parametrize("function,args", [(provider.provider_recipe_areas, ()), (provider.browse_provider_recipes, ("Italian",))])
def test_countries_and_browse_require_enabled_home_key_and_commercial_license(changes, function, args):
    calls = []
    def transport(*args, **kwargs):
        calls.append(args)
        pytest.fail("Unavailable provider made a network request")
    with pytest.raises(provider.RecipeProviderUnavailable):
        function(*args, config=config(**changes), transport=transport)
    assert not calls


def test_areas_are_sorted_deduplicated_names_from_exact_provider_response():
    payload = {"meals": [{"strArea": "Italian"}, {"strArea": "French"}, {"strArea": "Italian"},
                         {"strArea": "Saudi Arabian"}, {"strArea": "x"}, {"strArea": "<script>"},
                         {"strArea": "French\n"}, {"strArea": None}, {}, None]}
    transport, calls, responses = transport_for({("list.php", "list"): payload})
    assert provider.provider_recipe_areas(config=config(), transport=transport) == ("French", "Italian", "Saudi Arabian")
    assert len(calls) == 1 and calls[0][:2] == ("list.php", {"a": "list"})
    assert calls[0][2]["allow_redirects"] is False and calls[0][2]["stream"] is True
    assert all(response.closed for response in responses)


@pytest.mark.parametrize("area", ["", "I", "Italian\n", "../Italian", "<Italian>", "Italia1", None, "A" * 61])
def test_invalid_country_never_reaches_filter(area):
    transport, calls, _ = transport_for({})
    with pytest.raises(ValueError, match="invalid_recipe_area"):
        provider.browse_provider_recipes(area, config=config(), transport=transport)
    assert calls == []


def test_country_filter_summaries_are_hydrated_once_with_maximum_four_details():
    summaries = [{"idMeal": str(identifier), "strMeal": "Summary only"} for identifier in range(100, 108)]
    summaries.insert(1, {"idMeal": "100"})
    summaries.insert(0, {"idMeal": "invalid"})
    summaries.insert(0, None)
    payloads = {("filter.php", "Italian"): {"meals": summaries}}
    payloads.update({("lookup.php", str(identifier)): {"meals": [meal(str(identifier))]} for identifier in range(100, 104)})
    transport, calls, responses = transport_for(payloads)
    results = provider.browse_provider_recipes("Italian", limit=999, config=config(), transport=transport)
    assert [row.provider_id for row in results] == ["100", "101", "102", "103"]
    assert [call[:2] for call in calls] == [("filter.php", {"a": "Italian"}),
        *[("lookup.php", {"i": str(identifier)}) for identifier in range(100, 104)]]
    assert len(calls) == 5 and all(response.closed for response in responses)
    for record in results:
        row = record.to_dict()
        assert row["title"] == "Synthetic source dish" and row["area"] == "Italian"
        assert row["language"] == "en" and row["audience"] == "human"
        assert row["provider_original"]["instructions"] == "Original step one.\r\nOriginal step two."
        assert [item["measure"] for item in row["ingredients"]] == ["½ original cup", "to taste"]
        assert all(item["quantity"] is None and item["unit"] is None for item in row["ingredients"])
        assert row["servings"] is None and not row["can_cook"] and not row["can_add_to_shopping"]
        assert row["rights"]["attribution_required"] and row["rights"]["terms_url"]


def test_rejected_or_wrong_country_details_are_excluded_without_expanding_lookup_budget():
    payloads = {("filter.php", "Italian"): {"meals": [{"idMeal": str(i)} for i in range(100, 108)]},
                ("lookup.php", "100"): {"meals": [meal("100", strInstructions="")]},
                ("lookup.php", "101"): {"meals": [meal("101", strArea="French")]},
                ("lookup.php", "102"): {"meals": [meal("102", strCreativeCommonsConfirmed=None)]},
                ("lookup.php", "103"): {"meals": [meal("103")]}}
    transport, calls, _ = transport_for(payloads)
    assert [row.provider_id for row in provider.browse_provider_recipes("Italian", config=config(), transport=transport)] == ["103"]
    assert len(calls) == 5


def test_small_limit_restricts_calls_and_absent_detail_is_not_fabricated():
    payloads = {("filter.php", "Italian"): {"meals": [{"idMeal": "100"}, {"idMeal": "101"}]},
                ("lookup.php", "100"): {"meals": None}}
    transport, calls, _ = transport_for(payloads)
    assert provider.browse_provider_recipes("Italian", limit=1, config=config(), transport=transport) == ()
    assert len(calls) == 2


@pytest.mark.parametrize("function,args,endpoint,parameter", [
    (provider.provider_recipe_areas, (), "list.php", "list"),
    (provider.browse_provider_recipes, ("Italian",), "filter.php", "Italian"),
])
@pytest.mark.parametrize("payload", [{}, {"meals": {}}, {"meals": [None] * 101}])
def test_invalid_provider_lists_fail_closed(function, args, endpoint, parameter, payload):
    transport, _, responses = transport_for({(endpoint, parameter): payload})
    with pytest.raises(provider.RecipeProviderUnavailable):
        function(*args, config=config(), transport=transport)
    assert all(response.closed for response in responses)


@pytest.fixture
def tester(tmp_path, monkeypatch):
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-country-api-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "countries_test,other_home")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "food.json"))
    monkeypatch.setenv("ROXY_HOME_RECIPE_PROVIDER_ENABLED", "0")
    monkeypatch.delenv("ROXY_HOME_THEMEALDB_API_KEY", raising=False)
    monkeypatch.delenv("ROXY_HOME_THEMEALDB_COMMERCIAL_LICENSE_CONFIRMED", raising=False)
    monkeypatch.setattr("requests.get", lambda *a, **k: pytest.fail("Unexpected external provider request"))
    for name in ("_home_food_store", "_recipe_library_store", "_recipe_photo_queue", "_home_ai"):
        monkeypatch.setattr(service, name, lambda: pytest.fail("Country routes must not read/mutate home or AI"))
    service._RATE_STATE.clear()
    client = TestClient(service.app, base_url="https://countries.test")
    client.cookies.set(service.SESSION_COOKIE, service._session_cookie("countries_test"))
    yield client
    client.close()


@pytest.mark.parametrize("suffix", ["/areas?requested=true", "/browse?area=Italian&requested=true"])
def test_country_endpoints_require_matching_authenticated_household(tester, suffix):
    assert tester.get(BASE.replace("countries_test", "other_home") + suffix).status_code == 403
    tester.cookies.clear()
    assert tester.get(BASE + suffix).status_code == 401
    assert tester.get(BASE + suffix, headers={"Authorization": "Bearer wrong"}).status_code == 403


@pytest.mark.parametrize("suffix", ["/areas", "/browse?area=Italian"])
def test_country_routes_require_explicit_request_then_configuration(tester, suffix):
    separator = "&" if "?" in suffix else "?"
    assert tester.get(BASE + suffix).status_code == 409
    assert tester.get(BASE + suffix + separator + "requested=false").status_code == 409
    assert tester.get(BASE + suffix + separator + "requested=true").status_code == 503


def test_areas_and_browse_routes_return_source_records_without_home_access(tester, monkeypatch):
    calls = []
    def areas():
        calls.append("areas")
        return ("French", "Italian")
    def browse(area):
        calls.append(("browse", area))
        return (provider._normalize_record(meal(), config()),)
    monkeypatch.setattr(provider, "provider_recipe_areas", areas)
    monkeypatch.setattr(provider, "browse_provider_recipes", browse)
    result = tester.get(BASE + "/areas?requested=true")
    assert result.status_code == 200 and result.json()["areas"] == ["French", "Italian"]
    response = tester.get(BASE + "/browse?area=Italian&requested=true")
    assert response.status_code == 200
    payload = response.json()
    assert calls == ["areas", ("browse", "Italian")]
    assert payload["count"] == 1 and payload["review_required"] and not payload["imported"]
    assert payload["recipes"][0]["provider_original"]["ingredients"][0]["measure"] == "½ original cup"
    assert "no-store" in response.headers["Cache-Control"]


@pytest.mark.parametrize("query", ["area=I", "area=", "area=Italian1", "area=" + "A" * 61, "area=Italian&requested=perhaps"])
def test_browse_endpoint_validates_input_before_adapter(tester, monkeypatch, query):
    monkeypatch.setattr(provider, "browse_provider_recipes", lambda *a, **k: pytest.fail("Invalid request reached adapter"))
    assert tester.get(BASE + "/browse?" + query).status_code == 422


@pytest.mark.parametrize("suffix,name,error,status", [
    ("/areas?requested=true", "provider_recipe_areas", provider.RecipeProviderUnavailable, 503),
    ("/browse?area=Italian&requested=true", "browse_provider_recipes", provider.RecipeProviderUnavailable, 503),
    ("/browse?area=Italian&requested=true", "browse_provider_recipes", provider.RecipeProviderContentError, 422),
    ("/browse?area=Italian&requested=true", "browse_provider_recipes", ValueError, 422),
])
def test_country_api_errors_never_expose_provider_key(tester, monkeypatch, suffix, name, error, status):
    def fail(*args, **kwargs):
        raise error("secret-country-provider-url")
    monkeypatch.setattr(provider, name, fail)
    response = tester.get(BASE + suffix)
    assert response.status_code == status
    assert "secret-country-provider-url" not in response.text


@pytest.mark.parametrize("expired", [False, True])
def test_trials_cannot_spend_on_country_or_detail_requests(tester, tmp_path, monkeypatch, expired):
    accounts = HomeAccountStore(tmp_path / "accounts.json")
    member = accounts.register_trial(username="trialcountry", display_name="Trial", password="long-synthetic-password", admission_hash="test")
    if expired:
        accounts._mutate(lambda data: data["households"][member["household_id"]]["trial"].update(
            expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()))
    tester.cookies.set(service.SESSION_COOKIE, service._member_session_cookie(member))
    for name in ("provider_recipe_areas", "browse_provider_recipes"):
        monkeypatch.setattr(provider, name, lambda *a, **k: pytest.fail("Trial reached external adapter"))
    base = BASE.replace("countries_test", member["storage_user_id"])
    before = accounts.path.read_bytes()
    for suffix in ("/areas?requested=true", "/browse?area=Italian&requested=true"):
        assert tester.get(base + suffix).status_code == 403
        assert trial_access_mode("GET", (base + suffix).split("?")[0]) == "unavailable"
    assert accounts.path.read_bytes() == before
