"""Bundled original recipe content and the authenticated, non-billable API."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import html
import json
import re

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
    "wikibooks-105063": ("Pancakes (North American)", "North American", 3, 6, 6, 4585403),
    "wikibooks-17844": ("Oat Porridge", "", 1, 3, 5, 4606890),
    "wikibooks-9014": ("Red Lentil Soup", "", 4, 7, 4, 4518501),
    "wikibooks-50089": ("Lentil Rice Loaf", "", 4, 8, 6, 4515107),
    "wikibooks-8542": ("Chili (Vegan)", "Tex-Mex", 8, 17, 7, 4599150),
    "wikibooks-4034": ("Tomato Pasta", "", 3, 8, 4, 4516489),
    "wikibooks-85651": ("Chicken Cacciatore", "Italian", 4, 14, 5, 4540895),
    "wikibooks-252225": ("Baked Lemon Thyme Halibut", "Native American", 5, 6, 3, 4511873),
    "wikibooks-en-83396": ("Pohe (Spiced Flattened Rice)", "Indian", None, 9, 11, 4633573),
}
READABLE_IDS = {
    "wikibooks-150880", "wikibooks-128617", "wikibooks-219286", "wikibooks-167989",
    "wikibooks-9014", "wikibooks-4034", "wikibooks-en-83396",
}
HELD_IDS = set(EXPECTED) - READABLE_IDS


@pytest.fixture(autouse=True)
def clean_catalog_cache():
    catalog._catalog.cache_clear()
    yield
    catalog._catalog.cache_clear()


def source_rows():
    return json.loads(catalog.CATALOG_PATH.read_text(encoding="utf-8"))["recipes"]


def valid_source_row():
    return deepcopy(next(row for row in source_rows() if row["id"] == "wikibooks-150880"))


def test_fifteen_fixed_originals_preserve_english_measures_steps_and_attribution(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **k: pytest.fail("Bundled catalog cannot call a provider"))
    original = {row["id"]: row for row in source_rows()}
    result = catalog.open_recipe_catalog()
    assert result["status"] == "READY" and result["count"] == result["total"] == 7
    assert result["cost"] == "free_local_catalog" and not result["live_provider_request"]
    assert result["language"] == "en" and result["license"] == "CC BY-SA 4.0"
    assert set(EXPECTED) == set(original)
    assert READABLE_IDS == {row["id"] for row in result["recipes"]}
    for source in original.values():
        title, cuisine, servings, ingredients, steps, revision = EXPECTED[source["id"]]
        assert (source["title"], source["cuisine"], source["servings"], len(source["ingredients_original"]),
                len(source["steps_original"]), source["revid"]) == (title, cuisine, servings, ingredients, steps, revision)
        assert source["source_sha256"] == hashlib.sha256(source["original_wikitext"].encode()).hexdigest()
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
    assert sum(bool(row["image_url"]) for row in original.values()) == 6
    assert sum(len(row["ingredients_original"]) for row in original.values()) == 109
    assert sum(len(row["steps_original"]) for row in original.values()) == 87


def test_editorial_holds_preserve_original_evidence_but_never_appear_in_readable_results():
    rows = {row["id"]: row for row in source_rows()}
    held = {row["id"] for row in rows.values() if row.get("audit", {}).get("publishable") is False}
    assert held == HELD_IDS
    for recipe_id in HELD_IDS:
        row = rows[recipe_id]
        assert row["cook_allowed"] is False
        assert row["audit"]["source_fidelity_checked"] is True
        assert row["audit"]["source_revision_reviewed"] == row["revid"]
        assert row["audit"]["reason_codes"] and row["audit"]["reason"]
        assert row["audit"]["report"] == "reports/home_recipe_14_publication_audit_20260910.md"
        assert not catalog._publishable(row)
        assert not catalog.open_recipe_catalog(query=row["title"])["recipes"]


def test_original_qualitative_measure_and_approximate_conversion_are_not_rewritten():
    japanese = catalog.open_recipe_catalog(cuisine="Japanese")["recipes"][0]
    assert japanese["ingredients_original"][0] == "1 pound (½ kg) Japanese sweet potatoes"
    assert japanese["time_original"] == ""
    assert "1 tsp soy sauce" in japanese["ingredients_original"]
    assert not japanese["dietary_claims_imported"]
    french = catalog.open_recipe_catalog(cuisine="French")["recipes"][0]
    assert french["ingredients_original"] == ["4 potatoes, optionally peeled", "100 g butter"]
    assert french["steps_original"][0] == "Preheat the oven to 250 °C."


def test_expanded_originals_keep_every_source_ingredient_step_and_note_in_order():
    expanded_ids = {"wikibooks-105063", "wikibooks-17844", "wikibooks-9014", "wikibooks-50089",
                    "wikibooks-8542", "wikibooks-4034", "wikibooks-85651", "wikibooks-252225"}
    for row in source_rows():
        if row["id"] not in expanded_ids:
            continue
        sections, current = {}, None
        for line in row["original_wikitext"].splitlines():
            heading = re.fullmatch(r"==([^=]+)==\s*", line)
            if heading:
                current = heading[1].strip().lower()
                sections[current] = []
            elif current and re.match(r"^[*#](?![*#])", line):
                text = re.sub(r"^[*#]\s*", "", line)
                text = re.sub(r"\[\[(?:File|Image):.*?\]\]", "", text, flags=re.I)
                text = re.sub(r"\[\[[^|\]]+\|([^\]]+)\]\]", r"\1", text)
                text = re.sub(r"\[\[(?:[^:\]]+:)?([^\]]+)\]\]", r"\1", text)
                sections[current].append(html.unescape(text.replace("'''", "").replace("''", "")).strip())
        assert row["ingredients_original"] == sections["ingredients"]
        assert row["steps_original"] == sections["procedure"]
        assert row["notes_original"] == sections.get("notes, tips, and variations", [])
    # The embedded soup photograph has a caption, not an additional cooking step.
    soup = next(row for row in source_rows() if row["id"] == "wikibooks-9014")
    assert soup["steps_original"][0] == "Pick over the lentils to remove any debris if needed. Rinse well."
    assert soup["image_url"] == "" and soup["image_status"] == "not_included_source_image_has_unlisted_variation"


def test_all_fifteen_originals_preserve_every_source_section_after_display_markup_removal():
    from tools.roxy_home_recipe_import_wikibooks import section, source_lines
    headings = {
        "ingredients_original": (r"^ingredients$", "*"),
        "steps_original": (r"^procedure$", "#"),
        "notes_original": (r"^notes, tips, and variations$", "*"),
        "equipment_original": (r"^equipment$", "*"),
    }
    normalized = lambda values: [re.sub(r"\s+", " ", value).strip() for value in values]
    for row in source_rows():
        for field, (heading, marker) in headings.items():
            extracted = source_lines(section(row["original_wikitext"], heading), marker, set())
            assert normalized(row[field]) == normalized(extracted), (row["id"], field)


def test_expansion_keeps_source_servings_cuisine_and_individual_image_licenses():
    rows = {row["id"]: row for row in source_rows()}
    assert rows["wikibooks-252225"]["servings_original"] == "16 ounces (5 servings)"
    assert rows["wikibooks-252225"]["servings"] == 5
    for recipe_id in ("wikibooks-17844", "wikibooks-9014", "wikibooks-50089", "wikibooks-4034"):
        assert rows[recipe_id]["cuisine"] == ""  # A source title/category is not an invented country.
    for recipe_id, filename, license_name, revision in (
        ("wikibooks-105063", "Banana on pancake.jpg", "CC BY-SA 2.0", 1131890279),
        ("wikibooks-17844", "Oatmealraisins2.jpg", "CC BY-SA 3.0", 1228249094),
    ):
        row = rows[recipe_id]
        assert filename in row["original_wikitext"]
        assert row["image_source_revision"] == revision
        assert row["image_license"] == license_name
        assert row["image_original_wikitext"] and row["image_author"]
        assert row["image_commercial_use_permitted"] and "opcional" in row["photo_scope"]
        assert len(row["image_sha1"]) == 40
        assert "?" not in row["image_url"]  # No image API campaign/tracking parameters.


@pytest.mark.parametrize("query,cuisine,expected", [
    ("", "french", ["wikibooks-150880"]), ("", "Frénch", ["wikibooks-150880"]),
    ("soy sauce", "Japanese", ["wikibooks-128617"]), ("SAGANAKI", "", ["wikibooks-219286"]),
    ("soy sauce", "French", []), ("", "No cuisine", []), ("nonexistent recipe", "", []),
])
def test_filters_use_exact_cuisine_and_source_title_or_ingredients(query, cuisine, expected):
    result = catalog.open_recipe_catalog(query, cuisine)
    assert [row["id"] for row in result["recipes"]] == expected
    assert result["count"] == len(expected)
    assert result["total"] == 7 and result["status"] == "READY"
    assert result["cuisines"] == ["French", "Greek", "Indian", "Japanese"]


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
    assert catalog.open_recipe_catalog(limit=999)["count"] == 7


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
    row = valid_source_row()
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
    row = valid_source_row()
    row["rights"][field] = value
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"recipes": [row]}))
    monkeypatch.setattr(catalog, "CATALOG_PATH", path)
    assert catalog.open_recipe_catalog()["count"] == 0


@pytest.mark.parametrize("scope", ["row", "audit"])
@pytest.mark.parametrize("flag", ["publishable", "cook_allowed"])
@pytest.mark.parametrize("value", [False, None, 0, 1, "false", "true", [], {}])
def test_explicit_non_true_editorial_flag_cannot_promote_source_complete_candidate(scope, flag, value):
    row = valid_source_row()
    target = row if scope == "row" else row.setdefault("audit", {})
    target[flag] = value
    assert not catalog._publishable(row)


@pytest.mark.parametrize("audit", [None, False, [], "approved"])
def test_malformed_audit_cannot_bypass_publication_hold(audit):
    row = valid_source_row()
    row["audit"] = audit
    assert not catalog._publishable(row)


def test_editorial_true_is_not_an_override_for_license_or_source_integrity():
    row = valid_source_row()
    row.update(publishable=True, cook_allowed=True, audit={"publishable": True, "cook_allowed": True})
    assert catalog._publishable(row)
    row["source_sha256"] = "tampered"
    assert not catalog._publishable(row)
    row = valid_source_row()
    row["audit"] = {"publishable": True}
    row["rights"]["commercial_use_permitted"] = False
    assert not catalog._publishable(row)


def test_a_nested_hold_wins_over_top_level_approval_and_shopping_remains_independent():
    row = valid_source_row()
    row.update(publishable=True, cook_allowed=True, audit={"publishable": False})
    assert not catalog._publishable(row)
    row = valid_source_row()
    row["can_add_to_shopping"] = False
    assert catalog._publishable(row)


def test_runtime_omits_held_candidate_even_when_every_source_and_license_field_is_valid(tmp_path, monkeypatch):
    approved = valid_source_row()
    candidate = valid_source_row()
    candidate["id"] = "candidate-must-not-be-promoted"
    candidate["audit"] = {"publishable": False, "cook_allowed": False, "source_structure_complete": True}
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"recipes": [approved, candidate]}))
    monkeypatch.setattr(catalog, "CATALOG_PATH", path)
    result = catalog.open_recipe_catalog()
    assert result["count"] == result["total"] == 1
    assert [row["id"] for row in result["recipes"]] == [approved["id"]]


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
    assert response.status_code == 200 and response.json()["count"] == 7
    assert accounts.path.read_bytes() == before
    assert tester.get(BASE).status_code == 403
    assert trial_access_mode("GET", path) == "local"
    assert trial_access_mode("POST", path) == "unavailable"
