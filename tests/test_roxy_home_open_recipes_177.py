"""Bundled original recipe content and the authenticated, non-billable API."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from roxy_os import home_open_recipes as catalog
from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_demo import trial_access_mode
from tools import roxy_home_service as service


BASE = "/v1/home-food/source_test/open-recipes"
EXPECTED = {
    "wikibooks-385022": ("Spanish Potato Omelette", "Spanish", 4, 5, 8, 4500599),
    "wikibooks-150880": ("Potatoes Anna", "French", 4, 2, 5, 4502892),
    "wikibooks-128617": ("Daigakuimo (Japanese Candied Sweet Potato)", "Japanese", 4, 6, 5, 4494175),
    "wikibooks-219286": ("Pan-Fried White Brined Cheese (Saganaki)", "Greek", 1, 5, 6, 4613881),
    "wikibooks-167989": ("Indian Chai", "Indian", 1, 5, 3, 4522385),
    "wikibooks-108144": ("Risotto II", "Italian", 6, 8, 9, 4525538),
}


@pytest.fixture(autouse=True)
def clean_catalog_cache():
    catalog._catalog.cache_clear()
    yield
    catalog._catalog.cache_clear()


def source_rows():
    return json.loads(catalog.CATALOG_PATH.read_text(encoding="utf-8"))["recipes"]


def test_six_fixed_originals_preserve_english_measures_steps_and_attribution(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: pytest.fail("Bundled catalog cannot call a provider"))
    original = {row["id"]: row for row in source_rows()}
    result = catalog.open_recipe_catalog()
    assert result["status"] == "READY" and result["count"] == result["total"] == 6
    assert result["cost"] == "free_local_catalog" and not result["live_provider_request"]
    assert result["language"] == "en" and result["license"] == "CC BY-SA 4.0"
    assert set(EXPECTED) == set(original) == {row["id"] for row in result["recipes"]}
    for row in result["recipes"]:
        title, cuisine, servings, ingredients, steps, revision = EXPECTED[row["id"]]
        assert (row["title"], row["cuisine"], row["servings"], len(row["ingredients_original"]),
                len(row["steps_original"]), row["revid"]) == (title, cuisine, servings, ingredients, steps, revision)
        source = original[row["id"]]
        assert row["language"] == "en" and row["audience"] == "human"
        for field in ("ingredients_original", "steps_original", "servings_original", "time_original", "notes_original", "equipment_original", "rights"):
            assert row[field] == source[field]
        assert row["source_sha256"] == hashlib.sha256(source["original_wikitext"].encode()).hexdigest()
        assert f"oldid={revision}" in row["source_revision_url"]
        assert row["attribution"] == row["rights"]["attribution"]
        assert row["license_url"] == row["rights"]["license_url"] == catalog.LICENSE_URL
        assert row["rights"]["commercial_use_permitted"] and row["rights"]["share_alike_required"]
        assert row["rights"]["attribution_required"] and row["rights"]["changes"]
        assert not row["can_add_to_shopping"] and row["can_read_original"]
        assert "ingredients" not in row and "steps" not in row and "original_wikitext" not in row
        assert not row["dietary_claims_imported"] and not row["automatic_scaling_verified"]
        assert row["image_url"] == source["image_url"]
        if row["image_url"]:
            assert row["image_url"].startswith("https://upload.wikimedia.org/wikipedia/commons/")
            assert row["image_source_url"].startswith("https://commons.wikimedia.org/wiki/File:")
            assert row["image_commercial_use_permitted"]
            assert row["image_author"] and row["image_license"].startswith("CC BY-SA ")
    assert sum(bool(row["image_url"]) for row in result["recipes"]) == 3
    assert sum(len(row["ingredients_original"]) for row in result["recipes"]) == 31
    assert sum(len(row["steps_original"]) for row in result["recipes"]) == 36


def test_original_qualitative_measure_and_approximate_conversion_are_not_rewritten():
    japanese = catalog.open_recipe_catalog(cuisine="Japanese")["recipes"][0]
    assert japanese["ingredients_original"][0] == "1 pound (½ kg) Japanese sweet potatoes"
    assert japanese["time_original"] == ""
    assert "1 tsp soy sauce" in japanese["ingredients_original"]
    assert not japanese["dietary_claims_imported"]
    french = catalog.open_recipe_catalog(cuisine="French")["recipes"][0]
    assert french["ingredients_original"] == ["4 potatoes, optionally peeled", "100 g butter"]
    assert french["steps_original"][0] == "Preheat the oven to 250 °C."


@pytest.mark.parametrize("query,cuisine,expected", [
    ("", "french", ["wikibooks-150880"]), ("", "Frénch", ["wikibooks-150880"]),
    ("soy sauce", "Japanese", ["wikibooks-128617"]), ("SAGANAKI", "", ["wikibooks-219286"]),
    ("soy sauce", "French", []), ("", "No cuisine", []), ("nonexistent recipe", "", []),
])
def test_filters_use_exact_cuisine_and_source_title_or_ingredients(query, cuisine, expected):
    result = catalog.open_recipe_catalog(query, cuisine)
    assert [row["id"] for row in result["recipes"]] == expected
    assert result["count"] == len(expected)
    assert result["total"] == 6 and result["status"] == "READY"
    assert result["cuisines"] == ["French", "Greek", "Indian", "Italian", "Japanese", "Spanish"]


def test_reading_and_modifying_returned_catalog_never_changes_original_file_or_cache():
    before = catalog.CATALOG_PATH.read_bytes()
    original = catalog.open_recipe_catalog()
    changed = catalog.open_recipe_catalog()
    changed["recipes"][0]["ingredients_original"].append("Invented ingredient")
    changed["recipes"][0]["rights"]["attribution"] = "Removed author"
    changed["recipes"].clear()
    assert catalog.open_recipe_catalog() == original
    assert catalog.CATALOG_PATH.read_bytes() == before
    assert catalog.open_recipe_catalog(limit=2)["count"] == 2
    assert catalog.open_recipe_catalog(limit=999)["count"] == 6


@pytest.mark.parametrize("bad", [None, 2, "bad", [], {"title": "Incomplete"}])
def test_malformed_rows_are_not_labeled_ready_or_raise_500(tmp_path, monkeypatch, bad):
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"recipes": [bad]}))
    monkeypatch.setattr(catalog, "CATALOG_PATH", path)
    assert catalog.open_recipe_catalog()["status"] == "UNAVAILABLE"
    assert catalog.open_recipe_catalog()["recipes"] == []


@pytest.mark.parametrize("field,value", [
    ("rights", None), ("rights", {"attribution": "Insufficient credit"}),
    ("language", "es"), ("audience", "pet"), ("steps_original", "not a list"),
    ("ingredients_original", [None]), ("source_sha256", "changed"), ("servings", 0),
])
def test_invalid_source_or_rights_metadata_is_not_republished(tmp_path, monkeypatch, field, value):
    row = deepcopy(source_rows()[0])
    row[field] = value
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"recipes": [row]}))
    monkeypatch.setattr(catalog, "CATALOG_PATH", path)
    result = catalog.open_recipe_catalog()
    assert result["status"] == "UNAVAILABLE" and result["count"] == 0


@pytest.mark.parametrize("field,value", [
    ("license", "All rights reserved"), ("license_url", "https://example.org/unknown"),
    ("commercial_use_permitted", False), ("attribution_required", False), ("share_alike_required", False),
])
def test_incompatible_rights_never_gain_automatic_cc_license(tmp_path, monkeypatch, field, value):
    row = deepcopy(source_rows()[0])
    row["rights"][field] = value
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"recipes": [row]}))
    monkeypatch.setattr(catalog, "CATALOG_PATH", path)
    assert catalog.open_recipe_catalog()["count"] == 0


@pytest.fixture
def tester(tmp_path, monkeypatch):
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-open-api-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "source_test,other_home")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "food.json"))
    monkeypatch.setenv("ROXY_HOME_RECIPE_LIBRARY_PATH", str(tmp_path / "library.sqlite"))
    monkeypatch.setattr("requests.get", lambda *a, **k: pytest.fail("Original catalog API must not call network"))
    for name in ("_home_food_store", "_recipe_library_store", "_recipe_photo_queue", "_home_ai"):
        monkeypatch.setattr(service, name, lambda: pytest.fail("Original catalog must not read/mutate household or AI"))
    service._RATE_STATE.clear()
    client = TestClient(service.app, base_url="https://sources.test")
    client.cookies.set(service.SESSION_COOKIE, service._session_cookie("source_test"))
    yield client
    client.close()


def test_open_api_requires_auth_and_household_match(tester):
    assert tester.get(BASE.replace("source_test", "other_home")).status_code == 403
    tester.cookies.clear()
    assert tester.get(BASE).status_code == 401
    assert tester.get(BASE, headers={"Authorization": "Bearer wrong"}).status_code == 403


def test_open_api_filters_and_does_not_require_paid_provider(tester):
    response = tester.get(BASE + "?q=soy%20sauce&cuisine=Japanese")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1 and payload["recipes"][0]["id"] == "wikibooks-128617"
    assert not payload["live_provider_request"]
    assert "no-store" in response.headers["Cache-Control"]
    assert "synthetic-open-api-key" not in response.text
    assert tester.get(BASE + "?q=" + "a" * 101).status_code == 422
    assert tester.get(BASE + "?cuisine=" + "a" * 101).status_code == 422


@pytest.mark.parametrize("expired", [False, True])
def test_trial_may_read_local_originals_without_quota_or_household_mutation(tester, tmp_path, expired):
    accounts = HomeAccountStore(tmp_path / "accounts.json")
    member = accounts.register_trial(username="reader", display_name="Reader", password="long-synthetic-password", admission_hash="test")
    if expired:
        accounts._mutate(lambda data: data["households"][member["household_id"]]["trial"].update(
            expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()))
    tester.cookies.set(service.SESSION_COOKIE, service._member_session_cookie(member))
    path = BASE.replace("source_test", member["storage_user_id"])
    before = accounts.path.read_bytes()
    response = tester.get(path)
    assert response.status_code == 200 and response.json()["count"] == 6
    assert accounts.path.read_bytes() == before
    assert tester.get(BASE).status_code == 403
    assert trial_access_mode("GET", path) == "local"
    assert trial_access_mode("POST", path) == "unavailable"
