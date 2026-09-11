"""Bilingual drinks: release integrity and read-only API, not kitchen validation."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from roxy_os import home_drinks as catalog
from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_demo import trial_access_mode
from tools import roxy_home_service as service


BASE = "/v1/home-food/drinks_test/drinks"


def source_metadata():
    return {"name": "Open Drinks", "revision": catalog.REVISION, "license": "MIT",
            "license_url": catalog.SOURCE_BASE + "LICENSE"}


def source_row(number=1, category="juice"):
    """Synthetic fixture only; never publish as a recipe or culinary evidence."""
    slug = f"synthetic-drink-{number}"
    original = {"name": f"Synthetic test drink {number}", "description": "Only a test fixture",
                "github": f"test-contributor-{number}", "image": slug + ".jpg",
                "ingredients": [{"quantity": "1/2", "measure": "cup", "ingredient": "synthetic A"},
                                {"quantity": 1.5, "measure": "tablespoons", "ingredient": "synthetic B"}],
                "directions": [f"Synthetic direction {number}. Preserve 1/2 and 1.5.", "Synthetic final direction."],
                "keywords": ["synthetic"]}
    raw = json.dumps(original, ensure_ascii=False)
    return {"id": slug, "title": original["name"], "original_name": original["name"],
            "title_es": f"Bebida sintética de prueba {number}", "category": category,
            "alcoholic": category == "cocktail", "contributor": original["github"],
            "image_credit": "Synthetic credit, not a real photograph",
            "ingredients": ["1/2 cup synthetic A", "1.5 tablespoons synthetic B"],
            "steps": original["directions"].copy(),
            "ingredients_es": ["1/2 taza de A sintético", "1.5 cucharadas de B sintético"],
            "steps_es": [f"Indicación sintética {number}. Conserva 1/2 y 1.5.", "Última indicación sintética."],
            "notes_es": ["Sólo datos sintéticos; no es una receta."],
            "raw_source": raw, "source_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "source_url": catalog.SOURCE_BASE + f"src/recipes/{slug}.json",
            "image_url": catalog.IMAGE_BASE + original["image"]}


def bind_original(row, change):
    original = json.loads(row["raw_source"])
    change(original)
    row["raw_source"] = json.dumps(original, ensure_ascii=False)
    row["source_sha256"] = hashlib.sha256(row["raw_source"].encode()).hexdigest()


@pytest.fixture(autouse=True)
def clear_caches():
    catalog._catalog.cache_clear()
    yield
    catalog._catalog.cache_clear()


@pytest.fixture
def install(tmp_path, monkeypatch):
    path = tmp_path / "drinks.json"
    monkeypatch.setattr(catalog, "CATALOG_PATH", path)

    def write(rows=None, *, data=None, raw=None):
        payload = data if data is not None else {"version": 1, "source": source_metadata(), "drinks": rows if rows is not None else [source_row()]}
        path.write_bytes(raw if isinstance(raw, bytes) else (raw if raw is not None else json.dumps(payload, ensure_ascii=False)).encode())
        catalog._catalog.cache_clear()
        return path

    return write


def test_real_selection_counts_provenance_and_small_public_payload():
    payload = catalog.drink_catalog()
    assert 1 <= payload["total"] <= catalog.MAX_ROWS
    assert payload["total"] == len(payload["drinks"]) == sum(payload["counts"].values())
    assert payload["counts"] == {name: Counter(row["category"] for row in payload["drinks"])[name] for name in catalog.CATEGORIES}
    assert len(json.dumps(payload, ensure_ascii=False).encode()) < 150 * 1024
    assert payload["audience"] == "human" and payload["can_scale"] is False and payload["can_add_to_shopping"] is False
    assert payload["source"] == {"name": "Open Drinks", "revision": catalog.REVISION, "license": "MIT",
                                  "license_url": "/assets/open-drinks-license.txt"}
    assert "raw_source" not in json.dumps(payload)
    for row in payload["drinks"]:
        assert row["image_url"].startswith(catalog.IMAGE_BASE)
        assert len(row["source_sha256"]) == 64
        assert not {"ingredients", "ingredients_es", "steps", "steps_es", "raw_source"}.intersection(row)
        detail = catalog.drink_detail(row["id"])["drink"]
        assert detail["source_url"].startswith(catalog.SOURCE_BASE)
        assert detail["source_sha256"] == row["source_sha256"]
        assert len(detail["ingredients"]) == len(detail["ingredients_es"]) == row["ingredient_count"] > 0
        assert len(detail["steps"]) == len(detail["steps_es"]) == row["step_count"] > 0


def test_source_original_lines_and_translation_are_retained_verbatim_and_never_mutable_by_response(install):
    rows = [source_row(index, category) for index, category in enumerate(catalog.CATEGORIES)]
    rows[0]["private_unknown_metadata"] = "must-not-leak"
    install(rows)
    payload = catalog.drink_catalog()
    assert payload["total"] == 5 and payload["counts"] == dict.fromkeys(catalog.CATEGORIES, 1)
    assert "must-not-leak" not in json.dumps(payload) and "raw_source" not in json.dumps(payload)
    for summary, original in zip(payload["drinks"], rows):
        actual = catalog.drink_detail(summary["id"])["drink"]
        assert "must-not-leak" not in json.dumps(actual) and "raw_source" not in actual
        for field in ("ingredients", "steps", "ingredients_es", "steps_es", "notes_es", "source_sha256"):
            assert actual[field] == original[field]
    detail = catalog.drink_detail(rows[0]["id"])
    detail["drink"]["ingredients"][0] = "bad mutation"
    detail["drink"]["steps_es"].append("wrong step")
    assert catalog.drink_detail(rows[0]["id"])["drink"]["ingredients"] == rows[0]["ingredients"]
    assert catalog.drink_detail(rows[0]["id"])["drink"]["steps_es"] == rows[0]["steps_es"]
    payload["drinks"][0]["title"] = "bad mutation"
    assert catalog.drink_catalog()["drinks"][0]["title"] == rows[0]["title"]


def test_two_hundred_summaries_stay_lightweight_without_prefetching_details(install):
    rows = [source_row(index) for index in range(200)]
    install(rows)
    payload = catalog.drink_catalog()
    assert payload["total"] == 200
    assert len(json.dumps(payload, ensure_ascii=False).encode()) < 150 * 1024
    assert "Synthetic direction" not in json.dumps(payload)
    assert catalog.drink_detail(rows[-1]["id"])["drink"]["steps"] == rows[-1]["steps"]


@pytest.mark.parametrize("names,expected", [
    (["dry Gin", "ginger ale"], ["gin"]),
    (["Blueberry Vodka", "Light rum"], ["vodka", "rum"]),
    (["blanco tequila", "mezcal"], ["agave"]),
    (["Scotch whiskey", "bourbon", "rye whiskey"], ["whisky"]),
    (["dry Gin", "Champagne", "dry vermouth"], ["gin", "wine"]),
    (["White dry Port", "Peppermint"], ["wine"]),
    (["Cognac", "brandy", "Cachaça", "Shochu"], ["other"]),
    (["Ginger Liqueur", "pineapple juice"], ["other"]),
    (["rum extract", "bourbon vanilla", "non-alcoholic gin", "alcohol-free wine"], ["other"]),
    (["Vanilla vodka", "bourbon-vanilla"], ["vodka"]),
    (["bourbon vanilla vodka"], ["vodka"]),
    (["bourbon vanilla whiskey", "Vanilla bourbon whiskey"], ["whisky"]),
    (["red wine vinegar", "Champagne vinegar", "Gin"], ["gin"]),
    (["Crémant de Loire"], ["wine"]),
])
def test_bases_are_literal_ingredient_labels_not_titles_or_strength(names, expected):
    row = source_row(category="cocktail")
    bind_original(row, lambda data: data.update(ingredients=[{"ingredient": name} for name in names]))
    row["title"] = "Gin Vodka Rum Tequila Whisky Wine"
    row["ingredients_es"] = ["Texto que no debe determinar bases"]
    assert catalog._spirit_bases(row) == expected
    row["alcoholic"] = False
    assert catalog._spirit_bases(row) == []


def test_base_metadata_is_opt_in_and_consistent_for_all_real_details():
    previous = catalog.drink_catalog()
    enriched = catalog.drink_catalog(include_spirit_bases=True)
    assert "spirit_bases" not in json.dumps(previous)
    assert "spirit_bases" not in json.dumps(catalog.drink_catalog_legacy())
    assert previous["total"] == enriched["total"]
    for original, summary in zip(previous["drinks"], enriched["drinks"]):
        bases = summary["spirit_bases"]
        assert len(bases) == len(set(bases)) and set(bases) <= set(catalog.SPIRIT_BASES)
        assert bool(bases) is summary["alcoholic"]
        assert {key: value for key, value in summary.items() if key != "spirit_bases"} == original
        detail = catalog.drink_detail(summary["id"], include_spirit_bases=True)["drink"]
        assert detail["spirit_bases"] == bases
        assert "spirit_bases" not in catalog.drink_detail(summary["id"])["drink"]
        assert "raw_source" not in detail


def test_legacy_open_tabs_receive_a_compatible_bounded_selection(install):
    rows = [source_row(index) for index in range(200)]
    install(rows)
    old = catalog.drink_catalog_legacy()
    assert old["total"] == len(old["drinks"]) == sum(old["counts"].values()) == 60
    assert old["available_total"] == 200
    assert old["drinks"][0]["steps_es"] == rows[0]["steps_es"]
    assert "raw_source" not in json.dumps(old)
    assert catalog.drink_catalog()["total"] == 200


@pytest.mark.parametrize("drink_id", [None, 1, "", "../unsafe", "a/b", "A", "a" * 101, "unknown-drink"])
def test_unknown_or_invalid_detail_never_substitutes_a_recipe(install, drink_id):
    path = install(); before = path.read_bytes()
    with pytest.raises(catalog.DrinkNotFound, match="drink_not_found"):
        catalog.drink_detail(drink_id)
    assert path.read_bytes() == before


@pytest.mark.parametrize("field,value", [
    ("id", "../unsafe"), ("id", 1), ("id", ""), ("id", "x" * 101),
    ("category", "pet"), ("alcoholic", "false"), ("alcoholic", 0), ("alcoholic", True),
    ("title", "Changed title"), ("original_name", "Changed name"), ("title_es", ""),
    ("contributor", "Wrong contributor"), ("image_credit", ""), ("source_sha256", "0" * 64),
    ("raw_source", "not JSON"), ("raw_source", ""), ("notes_es", "not a list"), ("notes_es", [None]),
    ("ingredients", []), ("ingredients", "wrong type"), ("ingredients", [True]),
    ("ingredients_es", []), ("ingredients_es", [None, "x"]), ("ingredients_es", ["only one"]),
    ("steps", []), ("steps_es", ["missing second"]), ("steps_es", ["", "nonempty"]),
    ("steps_es", ["x"] * 49), ("ingredients_es", ["x" * 4097, "valid"]),
    ("title_es", "invalid\x00text"), ("notes_es", ["bad\x01control"]),
])
def test_invalid_release_row_rejected_without_partial_catalog(install, field, value):
    valid, broken = source_row(1), source_row(2)
    broken[field] = value
    install([valid, broken])
    with pytest.raises(catalog.DrinkCatalogUnavailable, match="drink_catalog_unavailable"):
        catalog.drink_catalog()


@pytest.mark.parametrize("field,value", [
    ("source_url", "https://github.com/alfg/opendrinks/blob/master/src/recipes/synthetic-drink-1.json"),
    ("source_url", catalog.SOURCE_BASE + "src/recipes/wrong-id.json"),
    ("source_url", catalog.SOURCE_BASE.replace("github.com", "github.com.evil.test") + "src/recipes/synthetic-drink-1.json"),
    ("image_url", catalog.IMAGE_BASE.replace(catalog.REVISION, "master") + "synthetic-drink-1.jpg"),
    ("image_url", catalog.IMAGE_BASE + "wrong.jpg"),
    ("image_url", catalog.IMAGE_BASE + "synthetic-drink-1.jpg?tracking=1"),
    ("image_url", "javascript:alert(1)"),
])
def test_pinned_urls_must_exactly_match_original_and_release_revision(install, field, value):
    row = source_row(); row[field] = value; install([row])
    with pytest.raises(catalog.DrinkCatalogUnavailable):
        catalog.drink_catalog()


@pytest.mark.parametrize("change", [
    lambda data: data.update(name="Changed source name"),
    lambda data: data.update(github="changed-user"),
    lambda data: data.update(directions=["Changed original direction", "Other"]),
    lambda data: data.update(image="../wrong.jpg"),
    lambda data: data.update(source="https://third-party.invalid/recipe"),
    lambda data: data.update(description="Visit www.thirdparty.invalid for the rest"),
    lambda data: data.update(description="Read https://thirdparty.invalid/ for original"),
    lambda data: data["ingredients"][0].update(quantity="2/3"),
    lambda data: data["ingredients"][0].update(quantity=True),
    lambda data: data["ingredients"][0].update(measure={"bad": "object"}),
    lambda data: data["ingredients"].append("wrong ingredient type"),
])
def test_recomputed_hash_cannot_mask_mismatch_or_unlicensed_source(install, change):
    row = source_row(); bind_original(row, change); install([row])
    with pytest.raises(catalog.DrinkCatalogUnavailable):
        catalog.drink_catalog()


def test_numeric_overflow_in_raw_source_is_rejected_even_if_extracted_lines_match(install):
    row = source_row()
    row["raw_source"] = row["raw_source"].replace('"quantity": 1.5', '"quantity": 1e309')
    row["source_sha256"] = hashlib.sha256(row["raw_source"].encode()).hexdigest()
    row["ingredients"][1] = "inf tablespoons synthetic B"
    install([row])
    with pytest.raises(catalog.DrinkCatalogUnavailable):
        catalog.drink_catalog()


@pytest.mark.parametrize("field", ["id", "title_es", "image_url", "source_sha256"])
def test_duplicate_selection_fields_rejected(install, field):
    first, second = source_row(1), source_row(2)
    if field == "title_es":
        second[field] = first[field].upper()
    elif field == "id":
        second = deepcopy(first)
    elif field == "image_url":
        bind_original(second, lambda value: value.update(image="synthetic-drink-1.jpg"))
        second["image_url"] = first["image_url"]
    else:
        second = deepcopy(first); second["id"] = "other-id"; second["source_url"] = catalog.SOURCE_BASE + "src/recipes/other-id.json"
    install([first, second])
    with pytest.raises(catalog.DrinkCatalogUnavailable):
        catalog.drink_catalog()


@pytest.mark.parametrize("data", [None, [], True, {}, {"version": True, "drinks": []},
    {"version": 2, "drinks": []}, {"version": 1, "drinks": None}, {"version": 1, "drinks": []},
    {"version": 1, "source": source_metadata(), "drinks": [source_row(i) for i in range(catalog.MAX_ROWS + 1)]}])
def test_invalid_container_never_becomes_empty_success(install, data):
    install(raw=json.dumps(data))
    with pytest.raises(catalog.DrinkCatalogUnavailable):
        catalog.drink_catalog()


@pytest.mark.parametrize("field,value", [("name", "Other source"), ("revision", "master"), ("license", "MIT-like"),
    ("license_url", "https://example.invalid/license")])
def test_manifest_source_rights_are_pinned(install, field, value):
    source = source_metadata(); source[field] = value
    install(data={"version": 1, "source": source, "drinks": [source_row()]})
    with pytest.raises(catalog.DrinkCatalogUnavailable):
        catalog.drink_catalog()


@pytest.mark.parametrize("raw", [b"\xff", b'{"version":1,"version":1,"drinks":[]}',
    b'{"version":NaN}', b'{"version":Infinity}', b'{"version":-Infinity}',
    b"[" * 1500 + b"]" * 1500, b" " * (catalog.MAX_BYTES + 1)])
def test_corrupted_duplicate_nonfinite_recursive_or_oversized_json_fails_closed(install, raw):
    install(raw=raw)
    with pytest.raises(catalog.DrinkCatalogUnavailable):
        catalog.drink_catalog()


def test_missing_release_file_fails_without_creating_data(install):
    path = install(); path.unlink()
    with pytest.raises(catalog.DrinkCatalogUnavailable):
        catalog.drink_catalog()
    assert not path.exists()


@pytest.fixture
def api_client(tmp_path, monkeypatch, install):
    path = install([source_row(1), source_row(2, "cocktail")])
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-drinks-api-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "drinks_test,other_home")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setattr("requests.get", lambda *a, **kw: pytest.fail("Drinks must not call a live source"))
    monkeypatch.setattr("requests.post", lambda *a, **kw: pytest.fail("Drinks cannot call AI or mutate remotely"))
    for name in ("_home_food_store", "_recipe_library_store", "_recipe_photo_queue", "_home_ai"):
        monkeypatch.setattr(service, name, lambda: pytest.fail("Drinks cannot access private profile or mutation helpers"))
    service._RATE_STATE.clear()
    with TestClient(service.app, base_url="https://drinks-home.test") as client:
        client.cookies.set(service.SESSION_COOKIE, service._session_cookie("drinks_test"))
        yield client, path


@pytest.mark.parametrize("suffix", ["", "/summaries", "/synthetic-drink-1", "/summaries?include_spirit_bases=true", "/synthetic-drink-1?include_spirit_bases=true"])
def test_api_is_private_authenticated_same_household_and_get_only(api_client, suffix):
    client, path = api_client; before = path.read_bytes()
    url = BASE + suffix
    response = client.get(url)
    assert response.status_code == 200
    if suffix.startswith("/synthetic-drink-1"):
        assert response.json()["drink"]["id"] == "synthetic-drink-1"
    else:
        assert response.json()["total"] == 2
        if suffix.startswith("/summaries"):
            assert "steps" not in response.text and "ingredients" not in response.text
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Vary"] == "Cookie, Authorization"
    assert "raw_source" not in response.text and "synthetic-drinks-api-key" not in response.text
    assert response.json()["can_add_to_shopping"] is False
    assert client.get(url.replace("drinks_test", "other_home")).status_code == 403
    for method in ("post", "patch", "put", "delete"):
        assert getattr(client, method)(url).status_code == 405
    client.cookies.clear()
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"Authorization": "Bearer wrong"}).status_code == 403
    assert path.read_bytes() == before


def test_api_flag_adds_only_base_labels_and_preserves_190_payload(api_client):
    client, path = api_client; before = path.read_bytes()
    old = client.get(BASE + "/summaries").json()
    enriched = client.get(BASE + "/summaries?include_spirit_bases=true").json()
    assert "spirit_bases" not in json.dumps(old)
    assert enriched["drinks"][0]["spirit_bases"] == []
    assert enriched["drinks"][1]["spirit_bases"] == ["other"]
    assert client.get(BASE + "/synthetic-drink-2?include_spirit_bases=true").json()["drink"]["spirit_bases"] == ["other"]
    assert client.get(BASE + "/summaries?include_spirit_bases=false").json() == old
    assert client.get(BASE + "/summaries?include_spirit_bases=invalid").status_code == 422
    assert path.read_bytes() == before


@pytest.mark.parametrize("suffix", ["", "/summaries", "/synthetic-drink-1"])
def test_damaged_release_api503_is_redacted_not_empty_or_generated(api_client, suffix):
    client, path = api_client
    path.write_text('{"private-secret":"do-not-leak"', encoding="utf-8")
    catalog._catalog.cache_clear(); before = path.read_bytes()
    response = client.get(BASE + suffix)
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "do-not-leak" not in response.text and str(path) not in response.text
    assert "drinks" not in response.json() and path.read_bytes() == before


@pytest.mark.parametrize("suffix", ["", "/summaries", "/synthetic-drink-1"])
def test_api_keeps_home_rate_limit(api_client, monkeypatch, suffix):
    client, _ = api_client; monkeypatch.setattr(service, "RATE_LIMIT_MAX", 1)
    assert client.get(BASE + suffix).status_code == 200
    response = client.get(BASE + suffix)
    assert response.status_code == 429 and response.headers["Cache-Control"] == "private, no-store"


def test_detail_not_found_is_private_and_not_synthesized(api_client):
    client, path = api_client; before = path.read_bytes()
    response = client.get(BASE + "/not-in-selection")
    assert response.status_code == 404
    assert response.headers["Cache-Control"] == "private, no-store"
    assert "drink" not in response.json() and path.read_bytes() == before


@pytest.mark.parametrize("expired", [False, True])
@pytest.mark.parametrize("suffix", ["", "/summaries", "/synthetic-drink-1"])
def test_active_or_expired_trial_can_read_bundled_drinks_without_modifying_account(api_client, tmp_path, expired, suffix):
    client, path = api_client
    accounts = HomeAccountStore(tmp_path / "accounts.json")
    member = accounts.register_trial(username="drink-reader", display_name="Synthetic Reader",
                                     password="synthetic-long-test-password", admission_hash="test")
    if expired:
        accounts._mutate(lambda data: data["households"][member["household_id"]]["trial"].update(
            expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()))
    client.cookies.set(service.SESSION_COOKIE, service._member_session_cookie(member))
    before, source_before = accounts.path.read_bytes(), path.read_bytes()
    url = BASE.replace("drinks_test", member["storage_user_id"]) + suffix
    assert trial_access_mode("GET", url) == "local" and trial_access_mode("POST", url) == "unavailable"
    assert client.get(url).status_code == 200 and client.get(BASE).status_code == 403
    assert accounts.path.read_bytes() == before and path.read_bytes() == source_before
