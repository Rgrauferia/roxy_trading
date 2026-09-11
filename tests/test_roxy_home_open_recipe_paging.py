"""Bounded source navigation; synthetic size fixtures are never real recipes."""
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


@pytest.fixture(autouse=True)
def reset_catalog_caches():
    catalog._catalog.cache_clear()
    catalog._translations.cache_clear()
    yield
    catalog._catalog.cache_clear()
    catalog._translations.cache_clear()


def source_row(number=0, *, language="en"):
    """Complete schema fixture, explicitly not culinary or editorial evidence."""
    original = f"Synthetic testing source {number}; language {language}."
    return {
        "id": f"synthetic-{number:04d}", "title": f"Synthetic source {number:04d}",
        "language": language, "audience": "human", "cuisine": "Test kitchen A",
        "servings": 2, "servings_original": "2", "time_original": "Synthetic time",
        "ingredients_original": [f"2 units synthetic ingredient {number}"],
        "steps_original": [f"Synthetic step {number} a.", f"Synthetic step {number} b."],
        "equipment_original": [], "notes_original": [],
        "source_url": f"https://{language}.wikibooks.org/wiki/Cookbook:Synthetic_{number}",
        "source_revision_url": f"https://{language}.wikibooks.org/w/index.php?oldid={number + 1}",
        "revid": number + 1, "original_wikitext": original,
        "source_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "rights": {"license": "CC BY-SA 4.0", "license_url": catalog.LICENSE_URL,
                   "attribution": "Synthetic attribution for test only", "changes": "Test fixture only",
                   "attribution_required": True, "share_alike_required": True, "commercial_use_permitted": True},
        "audit": {"publishable": True},
    }


def translation(row):
    return {
        "source_id": row["id"], "source_revid": row["revid"], "source_sha256": row["source_sha256"],
        "language": "es", "title": f'Traducción sintética {row["id"]}',
        "ingredients": [f'2 unidades sintéticas {row["id"]}'],
        "steps": [f'Paso sintético {index} de {row["id"]}' for index, _ in enumerate(row["steps_original"])],
        "equipment": [], "notes": [], "editorial_notes": [], "time": "Tiempo sintético",
        "attribution": "Traducción sintética de prueba", "changes": "Sólo prueba de contrato",
        "license": "CC BY-SA 4.0", "license_url": catalog.LICENSE_URL,
    }


@pytest.fixture
def install_sources(tmp_path, monkeypatch):
    source_path, translation_path = tmp_path / "sources.json", tmp_path / "translations.json"
    monkeypatch.setattr(catalog, "CATALOG_PATH", source_path)
    monkeypatch.setattr(catalog, "TRANSLATIONS_PATH", translation_path)

    def install(rows, translations=()):
        source_path.write_text(json.dumps({"recipes": rows}, ensure_ascii=False), encoding="utf-8")
        translation_path.write_text(json.dumps({"schema_version": 1, "translations": list(translations)}, ensure_ascii=False), encoding="utf-8")
        catalog._catalog.cache_clear()
        catalog._translations.cache_clear()
        return source_path, translation_path

    return install


def test_current_seven_sources_remain_readable_without_promoting_candidates():
    legacy = catalog.open_recipe_catalog()
    page = catalog.open_recipe_summaries()
    assert legacy["total"] == page["matched_total"] == page["catalog_total"] == 7
    assert page["count"] == 7 and page["next_cursor"] is None and page["schema_version"] == 2
    assert len(page["catalog_version"]) == 64
    assert {row["id"] for row in page["recipes"]} == {row["id"] for row in legacy["recipes"]}
    assert sum(row["has_source_photo"] for row in page["recipes"]) == 3
    for summary in page["recipes"]:
        assert summary["available_languages"] == ["en", "es"]
        assert summary["title_es"]
        result = catalog.open_recipe_detail(summary["id"], catalog_version=page["catalog_version"])
        detail = result["recipe"]
        assert result["catalog_version"] == page["catalog_version"]
        assert len(detail["steps_original"]) == summary["step_count"]
        assert detail["can_cook_with_roxy"] is False and detail["can_add_to_shopping"] is False
        assert detail["can_read_original"] is True
        for hidden in ("original_wikitext", "audit", "image_original_wikitext", "image_source_evidence", "cook_allowed"):
            assert hidden not in detail and hidden not in summary
        for large in ("steps_original", "ingredients_original", "translation", "rights"):
            assert large not in summary


def test_510_synthetic_sources_paginate_without_missing_or_repeated_ids(install_sources):
    rows = [source_row(number) for number in range(510)]
    # File order is deliberately unrelated to title order.
    install_sources(list(reversed(rows)), [translation(row) for row in rows])
    cursor, seen, page_sizes, versions = "", [], [], set()
    for _ in range(30):
        page = catalog.open_recipe_summaries(cursor=cursor)
        assert page["catalog_total"] == page["matched_total"] == 510
        assert page["status"] == "READY" and not page["live_provider_request"]
        assert page["count"] <= 24
        assert len(json.dumps(page, ensure_ascii=False).encode()) < 64 * 1024
        seen.extend(row["id"] for row in page["recipes"])
        page_sizes.append(page["count"])
        versions.add(page["catalog_version"])
        cursor = page["next_cursor"]
        if cursor is None:
            break
        assert len(cursor) == catalog.MAX_CURSOR_LENGTH
    assert seen == [row["id"] for row in rows]
    assert len(set(seen)) == 510 and page_sizes == [24] * 21 + [6]
    assert len(versions) == 1
    # Legacy consumers still receive only 24 complete records in file order.
    legacy = catalog.open_recipe_catalog(limit=999)
    assert legacy["total"] == 510 and legacy["count"] == 24
    assert legacy["recipes"][0]["id"] == rows[-1]["id"]
    for number in (0, 24, 255, 509):
        detail = catalog.open_recipe_detail(rows[number]["id"])["recipe"]
        assert detail["steps_original"] == rows[number]["steps_original"]
        assert detail["translation"]["steps"] == translation(rows[number])["steps"]


def test_search_beyond_page24_uses_source_translation_and_global_facets(install_sources):
    rows = [source_row(number) for number in range(40)]
    rows[-1]["cuisine"] = "Test kitchen Z"
    translated = translation(rows[-1])
    translated["title"] = "Ñame con limón sintético"
    install_sources(rows, [translated])
    initial = catalog.open_recipe_summaries()
    assert initial["cuisines"] == ["Test kitchen A", "Test kitchen Z"]
    assert rows[-1]["id"] not in {row["id"] for row in initial["recipes"]}
    found = catalog.open_recipe_summaries("name con limon", "test KITCHEN z")
    assert found["matched_total"] == found["count"] == 1 and found["catalog_total"] == 40
    assert found["recipes"][0]["id"] == rows[-1]["id"]
    assert found["cuisines"] == initial["cuisines"]
    assert catalog.open_recipe_summaries("synthetic ingredient 39")["recipes"][0]["id"] == rows[-1]["id"]
    empty = catalog.open_recipe_summaries("no source matches this")
    assert empty["status"] == "READY" and empty["count"] == empty["matched_total"] == 0
    assert empty["catalog_total"] == 40 and empty["next_cursor"] is None


def test_native_spanish_source_is_not_a_fabricated_translation(install_sources):
    en, es = source_row(1), source_row(2, language="es")
    es["title"] = "Fuente sintética española"
    fake_translation = translation(es)
    install_sources([en, es], [translation(en), fake_translation])
    page = catalog.open_recipe_summaries(language="es")
    assert page["count"] == 2 and {row["id"] for row in page["recipes"]} == {en["id"], es["id"]}
    assert page["languages"] == ["en", "es"] and page["catalog_total"] == 2
    summary = next(row for row in page["recipes"] if row["id"] == es["id"])
    assert summary["language"] == "es" and summary["available_languages"] == ["es"]
    assert summary["title_es"] is None and summary["time_es"] is None
    detail = catalog.open_recipe_detail(es["id"])["recipe"]
    assert detail["translation"] is None and detail["steps_original"] == es["steps_original"]
    assert catalog.open_recipe_summaries(language="en")["count"] == 1


@pytest.mark.parametrize("language,host", [("es", "en.wikibooks.org"), ("en", "es.wikibooks.org"), ("es", "example.com")])
def test_source_language_must_match_original_and_revision_domains(install_sources, language, host):
    row = source_row(language=language)
    row["source_revision_url"] = f"https://{host}/w/index.php?oldid=1"
    install_sources([row])
    assert catalog.open_recipe_summaries()["status"] == "UNAVAILABLE"
    with pytest.raises(catalog.OpenRecipeNotFound):
        catalog.open_recipe_detail(row["id"])


@pytest.mark.parametrize("change", ["original", "translation", "invalid_translation", "duplicate_translation"])
def test_catalog_version_changes_for_source_or_translation_edition(install_sources, change):
    rows = [source_row(number) for number in range(30)]
    translated = translation(rows[0])
    install_sources(rows, [translated])
    page = catalog.open_recipe_summaries()
    replacements = [translated]
    if change == "original":
        rows[0]["time_original"] = "Changed source metadata"
    elif change == "translation":
        translated["title"] = "Título sintético actualizado"
    elif change == "invalid_translation":
        translated["source_sha256"] = "wrong"
    else:
        replacements.append(deepcopy(translated))
    install_sources(rows, replacements)
    with pytest.raises(catalog.OpenRecipeVersionChanged):
        catalog.open_recipe_summaries(cursor=page["next_cursor"])
    with pytest.raises(catalog.OpenRecipeVersionChanged):
        catalog.open_recipe_detail(rows[0]["id"], catalog_version=page["catalog_version"])
    latest = catalog.open_recipe_summaries()
    assert latest["catalog_version"] != page["catalog_version"]
    if change in {"invalid_translation", "duplicate_translation"}:
        assert catalog.open_recipe_detail(rows[0]["id"])["recipe"]["translation"] is None


def test_tampered_or_wrong_filter_or_wrong_page_size_cursor_is_rejected(install_sources):
    install_sources([source_row(number) for number in range(60)])
    cursor = catalog.open_recipe_summaries()["next_cursor"]
    tampered = cursor[:-1] + ("a" if cursor[-1] != "a" else "b")
    with pytest.raises(catalog.OpenRecipeCursorError):
        catalog.open_recipe_summaries(cursor=tampered)
    for filters in ({"query": "source"}, {"cuisine": "Test kitchen A"}, {"language": "en"}, {"limit": 12}):
        with pytest.raises(catalog.OpenRecipeCursorError):
            catalog.open_recipe_summaries(cursor=cursor, **filters)
    assert catalog.open_recipe_summaries(cursor=cursor)["recipes"][0]["id"] == "synthetic-0024"


@pytest.mark.parametrize("kwargs", [
    {"query": None}, {"query": "x" * 101}, {"query": "text\x00"}, {"cuisine": 4},
    {"cuisine": "x" * 101}, {"language": "fr"}, {"language": None}, {"language": []},
    {"limit": True}, {"limit": 0}, {"limit": 25}, {"limit": 2.5}, {"limit": "24"},
])
def test_invalid_filters_fail_explicitly(kwargs):
    with pytest.raises(ValueError):
        catalog.open_recipe_summaries(**kwargs)


@pytest.mark.parametrize("cursor", [None, False, 1, [], "x", "a" * 130, "A" * 64 + "." + "a" * 64, "a" * 64 + "." + "z" * 64])
def test_malformed_cursor_rejected_before_lookup(cursor):
    with pytest.raises(catalog.OpenRecipeCursorError):
        catalog.open_recipe_summaries(cursor=cursor)


@pytest.mark.parametrize("held_duplicate", [False, True])
def test_duplicate_id_fails_closed_even_if_one_copy_is_held(install_sources, held_duplicate):
    first = source_row()
    duplicate = deepcopy(first)
    duplicate["title"] = "Another title with same identity"
    if held_duplicate:
        duplicate["audit"]["publishable"] = False
    install_sources([first, duplicate])
    result = catalog.open_recipe_summaries()
    assert result["status"] == "UNAVAILABLE" and result["catalog_total"] == 0
    with pytest.raises(catalog.OpenRecipeNotFound):
        catalog.open_recipe_detail(first["id"])


def test_holds_licenses_hashes_and_translation_grants_cannot_escalate_access(install_sources):
    good, held, invalid_rights, bad_hash = [source_row(number) for number in range(4)]
    good.update(can_cook_with_roxy=True, can_add_to_shopping=True, automatic_scaling_verified=True,
                arbitrary_private_key="Do not project this", image_original_wikitext="internal evidence")
    good["rights"]["arbitrary_private_key"] = "Do not project nested field"
    held["audit"]["publishable"] = False
    invalid_rights["rights"]["commercial_use_permitted"] = False
    bad_hash["source_sha256"] = "bad hash"
    translated = translation(good)
    translated.update(can_cook_with_roxy=True, can_add_to_shopping=True, instructions="invented instruction")
    install_sources([good, held, invalid_rights, bad_hash], [translated, translation(held)])
    page = catalog.open_recipe_summaries()
    assert page["catalog_total"] == 1
    for row in (page["recipes"][0], catalog.open_recipe_detail(good["id"])["recipe"]):
        assert row["can_cook_with_roxy"] is False and row["can_add_to_shopping"] is False
        assert "arbitrary_private_key" not in json.dumps(row)
    detail = catalog.open_recipe_detail(good["id"])["recipe"]
    assert detail["automatic_scaling_verified"] is False
    assert "instructions" not in detail["translation"]
    for invalid in (held, invalid_rights, bad_hash):
        with pytest.raises(catalog.OpenRecipeNotFound):
            catalog.open_recipe_detail(invalid["id"])


def test_summary_and_detail_mutations_never_modify_cached_content(install_sources):
    row = source_row()
    row.update(servings=None, servings_original="1–2", servings_range={"min": 1, "max": 2})
    paths = install_sources([row], [translation(row)])
    before = [path.read_bytes() for path in paths]
    summary = catalog.open_recipe_summaries()
    pristine_summary = deepcopy(summary)
    detail = catalog.open_recipe_detail(row["id"])
    pristine_detail = deepcopy(detail)
    summary["recipes"][0]["servings_range"]["min"] = 400
    summary["cuisines"].clear()
    summary["languages"].clear()
    detail["recipe"]["steps_original"].clear()
    detail["recipe"]["translation"]["steps"].clear()
    detail["recipe"]["rights"]["attribution"] = "Removed"
    assert catalog.open_recipe_summaries() == pristine_summary
    assert catalog.open_recipe_detail(row["id"]) == pristine_detail
    assert [path.read_bytes() for path in paths] == before


def test_stable_title_order_uses_identity_to_break_ties(install_sources):
    rows = [source_row(number) for number in range(30)]
    for row in rows:
        row["title"] = "Título idéntico"
    install_sources(list(reversed(rows)))
    first = catalog.open_recipe_summaries()
    second = catalog.open_recipe_summaries(cursor=first["next_cursor"])
    assert [row["id"] for row in first["recipes"] + second["recipes"]] == [row["id"] for row in rows]


def test_1000_row_limit_and_oversized_row_do_not_silently_truncate_a_recipe(install_sources):
    rows = [source_row(number) for number in range(1001)]
    install_sources(rows)
    assert catalog.open_recipe_summaries()["status"] == "UNAVAILABLE"
    rows = rows[:2]
    rows[1]["steps_original"] = ["x" * (catalog.MAX_LINE_CHARS + 1)]
    install_sources(rows)
    assert catalog.open_recipe_summaries()["catalog_total"] == 1
    with pytest.raises(catalog.OpenRecipeNotFound):
        catalog.open_recipe_detail(rows[1]["id"])
    rows[1]["steps_original"] = ["valid step"] * (catalog.MAX_LIST_ITEMS + 1)
    install_sources(rows)
    assert catalog.open_recipe_summaries()["catalog_total"] == 1
    rows[1] = source_row(1)
    rows[1]["oversized_internal_blob"] = "x" * catalog.MAX_ROW_BYTES
    install_sources(rows)
    assert catalog.open_recipe_summaries()["catalog_total"] == 1


def test_valid_catalog_and_translations_above_old_byte_limits_are_supported(install_sources):
    rows = [source_row(number) for number in range(510)]
    for row in rows:
        # Source evidence belongs on the server, not in a giant browser response.
        row["original_wikitext"] += " x" * 2000
        row["source_sha256"] = hashlib.sha256(row["original_wikitext"].encode()).hexdigest()
    paths = install_sources(rows, [translation(row) for row in rows])
    assert paths[0].stat().st_size > 1_000_000 and paths[1].stat().st_size > 250_000
    assert catalog.open_recipe_summaries()["catalog_total"] == 510
    assert catalog.open_recipe_detail(rows[-1]["id"])["recipe"]["translation"]
    assert len(json.dumps(catalog.open_recipe_summaries()).encode()) < 64 * 1024


def test_catalog_and_translation_file_limits_are_enforced(install_sources):
    row = source_row()
    source_path, translation_path = install_sources([row], [translation(row)])
    source_path.write_bytes(b" " * (catalog.MAX_CATALOG_BYTES + 1))
    catalog._catalog.cache_clear()
    assert catalog.open_recipe_summaries()["status"] == "UNAVAILABLE"
    install_sources([row], [translation(row)])
    translation_path.write_bytes(b" " * (catalog.MAX_TRANSLATION_BYTES + 1))
    catalog._translations.cache_clear()
    assert catalog.open_recipe_summaries()["catalog_total"] == 1
    assert catalog.open_recipe_detail(row["id"])["recipe"]["translation"] is None


def test_nonfinite_json_fails_closed(install_sources):
    source_path, _ = install_sources([source_row()])
    source_path.write_text('{"recipes": [], "not_allowed": NaN}')
    catalog._catalog.cache_clear()
    assert catalog.open_recipe_summaries()["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("identity", [None, True, [], "", "x" * 129, "../secret", "synthetic-does-not-exist"])
def test_unknown_or_malformed_identity_is_not_found(identity):
    with pytest.raises(catalog.OpenRecipeNotFound):
        catalog.open_recipe_detail(identity)


@pytest.mark.parametrize("version", [None, True, [], "x", "x" * 1000])
def test_invalid_detail_version_is_validation_error(version):
    with pytest.raises(ValueError):
        catalog.open_recipe_detail("synthetic-0000", catalog_version=version)


def test_index_reused_without_revalidating_all_translations_per_request(install_sources, monkeypatch):
    rows = [source_row(number) for number in range(510)]
    install_sources(rows, [translation(row) for row in rows])
    original_translation = catalog._translation
    validations = []

    def counted(row, **kwargs):
        validations.append(row["id"])
        return original_translation(row, **kwargs)

    monkeypatch.setattr(catalog, "_translation", counted)
    page = catalog.open_recipe_summaries()
    assert len(validations) == 510
    for _ in range(4):
        catalog.open_recipe_summaries(cursor=page["next_cursor"])
        catalog.open_recipe_detail(rows[-1]["id"])
        catalog.open_recipe_catalog(query="Synthetic")
    assert len(validations) == 510


@pytest.mark.parametrize("field,value", [
    ("language", []), ("source_revision_url", "https://en.wikibooks.org/w/index.php?oldid=999"),
    ("source_revision_url", "https://en.wikibooks.org/w/index.php?oldid=1&oldid=2"),
    ("source_revision_url", "https://en.wikibooks.org/wiki/Not_a_revision?oldid=1"),
])
def test_malformed_source_is_skipped_without_hiding_other_valid_rows(install_sources, field, value):
    bad, good = source_row(), source_row(1)
    bad[field] = value
    install_sources([bad, good])
    assert [row["id"] for row in catalog.open_recipe_summaries()["recipes"]] == [good["id"]]


def test_range_requires_explicit_null_scalar_in_summary_schema(install_sources):
    row = source_row()
    row.update(servings_original="1–2", servings_range={"min": 1, "max": 2})
    row.pop("servings")
    install_sources([row])
    assert catalog.open_recipe_summaries()["catalog_total"] == 0


@pytest.mark.parametrize("bad", [b"not JSON", b"[]", b"null", b'{"recipes":null}', b'\xff', b'{"recipes":[]',
                                 b'{"recipes":[],"recipes":[]}'])
def test_malformed_source_files_fail_closed_without_changing_bytes(install_sources, bad):
    path, _ = install_sources([source_row()])
    path.write_bytes(bad)
    catalog._catalog.cache_clear()
    assert catalog.open_recipe_summaries()["status"] == "UNAVAILABLE"
    assert path.read_bytes() == bad


def test_missing_source_file_and_corrupt_translation_preserve_original_reading(install_sources):
    row = source_row()
    source_path, translation_path = install_sources([row], [translation(row)])
    translation_path.write_bytes(b"broken")
    catalog._translations.cache_clear()
    assert catalog.open_recipe_detail(row["id"])["recipe"]["translation"] is None
    assert catalog.open_recipe_summaries(language="es")["count"] == 0
    source_path.unlink()
    catalog._catalog.cache_clear()
    assert catalog.open_recipe_summaries()["status"] == "UNAVAILABLE"


def test_unencodable_translation_cannot_break_catalog_version_or_original_reader(install_sources):
    row = source_row()
    _, path = install_sources([row], [translation(row)])
    path.write_bytes(b'{"schema_version":1,"translations":[{"source_id":"synthetic-0000","title":"\\ud800"}]}')
    catalog._translations.cache_clear()
    assert catalog.open_recipe_summaries()["count"] == 1
    assert catalog.open_recipe_detail(row["id"])["recipe"]["translation"] is None


def test_nested_metadata_is_whitelisted_and_photographic_rights_are_independent(install_sources):
    row = source_row()
    row.update(image_status="source_linked_individual_license_checked", image_commercial_use_permitted=True,
               image_mime="image/jpeg", image_author="Synthetic test author", image_license="CC BY-SA 4.0",
               image_license_url=catalog.LICENSE_URL, image_dimensions={"width": 100, "height": 100},
               image_url="https://upload.wikimedia.org/wikipedia/commons/a/ab/Synthetic.jpg",
               image_source_url="https://commons.wikimedia.org/wiki/File:Synthetic.jpg")
    row["image_dimensions"]["private_key"] = "private marker"
    row["pageid"] = {"private_key": "private marker"}
    install_sources([row])
    assert catalog.open_recipe_summaries()["recipes"][0]["has_source_photo"] is True
    assert "private marker" not in json.dumps(catalog.open_recipe_detail(row["id"]))
    for key, value in (("image_commercial_use_permitted", False), ("image_url", "https://example.com/image.jpg"),
                       ("image_license", "All rights reserved"), ("image_license_url", "javascript:alert(1)")):
        invalid = deepcopy(row)
        invalid[key] = value
        install_sources([invalid])
        assert catalog.open_recipe_summaries()["recipes"][0]["has_source_photo"] is False
        detail = catalog.open_recipe_detail(row["id"])["recipe"]
        assert detail["image_url"] == "" and detail["image_commercial_use_permitted"] is False


BASE = "/v1/home-food/source_test/open-recipes"


@pytest.fixture
def tester(tmp_path, monkeypatch):
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-open-api-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "source_test,other_home")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setattr("requests.get", lambda *a, **kw: pytest.fail("Source paging must not call network"))
    for name in ("_home_food_store", "_recipe_library_store", "_recipe_photo_queue", "_home_ai"):
        monkeypatch.setattr(service, name, lambda: pytest.fail("Source paging must not touch household data or AI"))
    service._RATE_STATE.clear()
    with TestClient(service.app, base_url="https://sources.test") as client:
        client.cookies.set(service.SESSION_COOKIE, service._session_cookie("source_test"))
        yield client


@pytest.mark.parametrize("suffix", ["/summaries", "/detail/wikibooks-150880"])
def test_paging_api_requires_auth_and_matching_namespace_with_private_cache(tester, suffix):
    assert tester.get(BASE + suffix).status_code == 200
    for path, code in ((BASE.replace("source_test", "other_home") + suffix, 403),):
        response = tester.get(path)
        assert response.status_code == code
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.headers["Vary"] == "Cookie, Authorization"
    tester.cookies.clear()
    assert tester.get(BASE + suffix).status_code == 401
    assert tester.get(BASE + suffix, headers={"Authorization": "Bearer wrong"}).status_code == 403


def test_api_pages_510_without_duplicates_and_loads_detail_beyond_first_page(tester, install_sources):
    rows = [source_row(number) for number in range(510)]
    paths = install_sources(rows, [translation(rows[-1])])
    before = [path.read_bytes() for path in paths]
    cursor, seen = "", []
    for _ in range(22):
        response = tester.get(BASE + "/summaries", params={"cursor": cursor})
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "private, no-store"
        payload = response.json()
        assert payload["catalog_total"] == payload["matched_total"] == 510
        assert len(response.content) < 64 * 1024
        seen.extend(row["id"] for row in payload["recipes"])
        cursor = payload["next_cursor"]
        if cursor is None:
            break
    assert seen == [row["id"] for row in rows]
    response = tester.get(BASE + "/detail/" + rows[-1]["id"], params={"catalog_version": payload["catalog_version"]})
    assert response.status_code == 200 and response.json()["recipe"]["steps_original"] == rows[-1]["steps_original"]
    search = tester.get(BASE + "/summaries", params={"q": "Traducción sintética synthetic-0509", "language": "es"})
    assert search.status_code == 200 and search.json()["count"] == 1
    assert tester.get(BASE).json()["count"] == 24
    assert [path.read_bytes() for path in paths] == before


@pytest.mark.parametrize("params", [
    {"q": "x" * 101}, {"q": "bad\x00"}, {"cuisine": "x" * 101}, {"language": "fr"},
    {"limit": "0"}, {"limit": "25"}, {"limit": "2.5"}, {"limit": "true"},
    {"limit": "9" * 5000}, {"cursor": "invalid"}, {"cursor": "a" * 130},
])
def test_paging_api_bad_filters_are_sanitized_400(tester, params):
    response = tester.get(BASE + "/summaries", params=params)
    assert response.status_code == 400
    assert response.json() == {"detail": "No se pudo validar la búsqueda o la página del recetario."}
    assert response.headers["Cache-Control"] == "private, no-store"


def test_paging_api_stale_tampered_and_filter_mismatch_bookmarks(tester, install_sources):
    rows = [source_row(number) for number in range(30)]
    install_sources(rows)
    page = tester.get(BASE + "/summaries").json()
    assert tester.get(BASE + "/summaries", params={"cursor": page["next_cursor"], "limit": "12"}).status_code == 400
    invalid = page["next_cursor"][:-1] + ("a" if page["next_cursor"][-1] != "a" else "b")
    assert tester.get(BASE + "/summaries", params={"cursor": invalid}).status_code == 400
    assert tester.get(BASE + "/detail/" + rows[0]["id"], params={"catalog_version": "invalid"}).status_code == 400
    rows[0]["title"] = "Updated edition"
    install_sources(rows)
    for response in (tester.get(BASE + "/summaries", params={"cursor": page["next_cursor"]}),
                     tester.get(BASE + "/detail/" + rows[0]["id"], params={"catalog_version": page["catalog_version"]})):
        assert response.status_code == 409
        assert response.json() == {"detail": "El recetario cambió. Vuelve a cargar la lista."}
        assert response.headers["Cache-Control"] == "private, no-store"


def test_api_unknown_and_held_details_are_same_404(tester):
    responses = [tester.get(BASE + "/detail/" + identity) for identity in ("unknown", "wikibooks-385022", "x" * 129)]
    assert all(response.status_code == 404 for response in responses)
    assert all(response.json() == {"detail": "La receta no está disponible."} for response in responses)


@pytest.mark.parametrize("expired", [False, True])
def test_trial_members_read_both_new_routes_without_spend_or_mutation(tester, tmp_path, expired):
    accounts = HomeAccountStore(tmp_path / "accounts.json")
    member = accounts.register_trial(username="reader", display_name="Reader", password="long-synthetic-password", admission_hash="test")
    if expired:
        accounts._mutate(lambda data: data["households"][member["household_id"]]["trial"].update(
            expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()))
    tester.cookies.set(service.SESSION_COOKIE, service._member_session_cookie(member))
    before = accounts.path.read_bytes()
    for suffix in ("/summaries", "/detail/wikibooks-150880"):
        path = BASE.replace("source_test", member["storage_user_id"]) + suffix
        assert tester.get(path).status_code == 200
        assert trial_access_mode("GET", path) == "local"
        assert trial_access_mode("POST", path) == "unavailable"
        assert tester.get(BASE + suffix).status_code == 403
    assert accounts.path.read_bytes() == before


@pytest.mark.parametrize("suffix", ["/summaries", "/detail/wikibooks-150880"])
def test_new_routes_keep_existing_rate_limit(tester, monkeypatch, suffix):
    monkeypatch.setattr(service, "RATE_LIMIT_MAX", 1)
    assert tester.get(BASE + suffix).status_code == 200
    response = tester.get(BASE + suffix)
    assert response.status_code == 429 and response.headers["Cache-Control"] == "private, no-store"
