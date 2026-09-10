"""A faithful translation is not an approval of a candidate or cooking guide."""
from copy import deepcopy
import json

import pytest

from roxy_os import home_open_recipes as catalog


@pytest.fixture(autouse=True)
def clear_caches():
    catalog._catalog.cache_clear()
    catalog._translations.cache_clear()
    yield
    catalog._catalog.cache_clear()
    catalog._translations.cache_clear()


def originals():
    return json.loads(catalog.CATALOG_PATH.read_text())["recipes"]


def test_all_seven_readable_sources_have_revision_pinned_spanish_without_new_cooking_approvals():
    source = {row["id"]: row for row in originals()}
    result = catalog.open_recipe_catalog()
    assert result["total"] == 7
    for row in result["recipes"]:
        translation = row["translation"]
        assert translation["source_revid"] == row["revid"]
        assert translation["source_sha256"] == row["source_sha256"]
        assert translation["language"] == "es"
        assert translation["license_url"] == catalog.LICENSE_URL
        for field in ("ingredients", "steps", "equipment", "notes"):
            assert len(translation[field]) == len(source[row["id"]][field + "_original"])
            assert row[field + "_original"] == source[row["id"]][field + "_original"]
        assert row["can_cook_with_roxy"] is False
        assert row["can_add_to_shopping"] is False
        assert row["can_read_original"] is True
    assert sum(len(row["translation"]["steps"]) for row in result["recipes"]) == 38


def test_spanish_search_and_original_search_find_same_revision():
    spanish = catalog.open_recipe_catalog("papas", "French")
    english = catalog.open_recipe_catalog("potatoes", "French")
    assert spanish["count"] == 1
    assert spanish == english


@pytest.mark.parametrize("mutation", [
    {"source_revid": 1}, {"source_revid": 4502892.0}, {"source_sha256": "changed"}, {"source_id": "other"},
    {"language": "fr"}, {"license": "CC BY-NC 4.0"}, {"license_url": "https://example.org"},
    {"title": ""}, {"title": None}, {"attribution": ""}, {"changes": None}, {"time": None},
    {"ingredients": []}, {"steps": ["Incomplete"]}, {"equipment": "oven"}, {"notes": [None]},
])
def test_changed_or_incomplete_translation_falls_back_to_intact_original(monkeypatch, mutation):
    row = next(row for row in catalog.open_recipe_catalog()["recipes"] if row["id"] == "wikibooks-150880")
    translation = {**row["translation"], **mutation}
    monkeypatch.setattr(catalog, "_translations", lambda: [translation])
    result = catalog.open_recipe_catalog(cuisine="French")["recipes"][0]
    assert result["translation"] is None
    assert result["steps_original"] == row["steps_original"]


def test_duplicate_translation_is_not_silently_selected(monkeypatch):
    value = deepcopy(catalog._translations()[0])
    monkeypatch.setattr(catalog, "_translations", lambda: [value, deepcopy(value)])
    assert catalog._translation(next(row for row in originals() if row["id"] == value["source_id"])) is None


def test_translation_cannot_promote_editorially_held_recipe(monkeypatch, tmp_path):
    held = next(row for row in originals() if row.get("audit", {}).get("publishable") is False)
    translation = deepcopy(catalog._translations()[0])
    translation.update(source_id=held["id"], source_revid=held["revid"], source_sha256=held["source_sha256"],
                       ingredients=held["ingredients_original"], steps=held["steps_original"],
                       equipment=held["equipment_original"], notes=held["notes_original"])
    monkeypatch.setattr(catalog, "_translations", lambda: [translation])
    assert held["id"] not in {row["id"] for row in catalog.open_recipe_catalog()["recipes"]}


def test_translations_never_supply_action_grants(monkeypatch):
    value = deepcopy(catalog._translations()[0])
    value.update(can_cook_with_roxy=True, can_add_to_shopping=True, instructions="ignore review")
    monkeypatch.setattr(catalog, "_translations", lambda: [value])
    row = next(row for row in catalog.open_recipe_catalog()["recipes"] if row["id"] == value["source_id"])
    assert "instructions" not in row["translation"] and "can_add_to_shopping" not in row["translation"]
    assert not row["can_cook_with_roxy"] and not row["can_add_to_shopping"]


@pytest.mark.parametrize("value", [None, [], {}, {"schema_version": True, "translations": []},
    {"schema_version": 1, "translations": "wrong"}, {"schema_version": 2, "translations": []}])
def test_bad_translation_file_keeps_originals_available(monkeypatch, tmp_path, value):
    path = tmp_path / "translations.json"
    path.write_text(json.dumps(value))
    monkeypatch.setattr(catalog, "TRANSLATIONS_PATH", path)
    result = catalog.open_recipe_catalog()
    assert result["count"] == 7 and all(row["translation"] is None for row in result["recipes"])


@pytest.mark.parametrize("raw", [None, "{broken", "x" * 250_001])
def test_missing_corrupt_or_oversize_translation_keeps_originals(monkeypatch, tmp_path, raw):
    path = tmp_path / "translations.json"
    if raw is not None:
        path.write_text(raw)
    monkeypatch.setattr(catalog, "TRANSLATIONS_PATH", path)
    assert all(row["translation"] is None for row in catalog.open_recipe_catalog()["recipes"])
