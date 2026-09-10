"""Source-yield ranges are lossless reading metadata, never scaling grants."""
from copy import deepcopy
import hashlib
import json

import pytest

from roxy_os import home_open_recipes as catalog
from tools.roxy_home_recipe_import_wikibooks import section, source_lines


POHE_ID = "wikibooks-en-83396"
CANDIDATE_HASH = "746ced612d6ca725084128ad9b4c7e9dca602171d0eb1a3621c883de02ee83c5"


def pohe():
    return deepcopy(next(row for row in json.loads(catalog.CATALOG_PATH.read_text())["recipes"]
                         if row["id"] == POHE_ID))


@pytest.fixture(autouse=True)
def clear_caches():
    catalog._catalog.cache_clear()
    catalog._translations.cache_clear()
    yield
    catalog._catalog.cache_clear()
    catalog._translations.cache_clear()


def test_pohe_preserves_pinned_candidate_without_modifying_the_510_inbox():
    path = catalog.CATALOG_PATH.with_name("home_recipe_candidates_20260910.json")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == CANDIDATE_HASH
    candidates = json.loads(raw)["recipes"]
    assert len(candidates) == 510
    candidate = next(row for row in candidates if row["id"] == POHE_ID)
    source = pohe()
    for field in ("original_wikitext", "source_sha256", "source_revision_url", "source_url",
                  "source_history_url", "source_modified_at", "revid", "pageid", "servings_original",
                  "time_original", "ingredients_original", "steps_original"):
        assert source[field] == candidate[field]
    assert source["revid"] == 4633573
    assert source["servings_original"] == "1–2"
    assert source["servings"] is None and source["servings_range"] == {"min": 1, "max": 2}
    assert source["notes_original"] == source_lines(section(source["original_wikitext"],
                                                            r"^notes, tips, and variations$"), "*", set())
    assert len(source["ingredients_original"]) == 9
    assert len(source["steps_original"]) == 11
    assert len(source["notes_original"]) == 2
    assert source["equipment_original"] == []
    assert source["image_url"] == "https://upload.wikimedia.org/wikipedia/commons/e/ef/Poha_or_Pauva_or_Spicy_Rice_Flakes_WLF15.jpg"
    assert "[[File:Poha or Pauva or Spicy Rice Flakes WLF15.jpg|300px]]" in source["original_wikitext"]
    assert source["image_license"] == "CC BY-SA 4.0"
    assert source["image_author"] == "Nizil Shah"
    assert source["image_sha1"] == candidate["source_media_candidates"][0]["source_file_sha1"]
    assert source["image_source_revision"] == 1149240405
    assert source["photo_scope"] == "Fotografía publicada con la receta original; no verifica cantidades ni resultado"
    assert "fry pay" in source["steps_original"][7]  # The typo is retained in the English original.
    assert all(row["audit"]["publishable"] is False for row in candidates)
    assert path.read_bytes() == raw


def test_pohe_reader_is_bilingual_preserves_range_and_denies_actions(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **kw: pytest.fail("Bundled reader cannot use a provider"))
    result = catalog.open_recipe_catalog("copos", "Indian")
    assert result["count"] == 1 and result["total"] == 7
    row = result["recipes"][0]
    assert row["id"] == POHE_ID and row["servings"] is None
    assert row["servings_range"] == {"min": 1, "max": 2}
    assert row["servings_original"] == "1–2"
    assert row["can_read_original"] is True
    assert row["can_cook_with_roxy"] is False and row["can_add_to_shopping"] is False
    assert row["automatic_scaling_verified"] is False and row["dietary_claims_imported"] is False
    assert row["translation"]["source_sha256"] == row["source_sha256"]
    assert len(row["translation"]["ingredients"]) == 9
    assert len(row["translation"]["steps"]) == 11
    assert len(row["translation"]["notes"]) == 2
    assert "fry pay" in row["translation"]["editorial_notes"][1]
    assert all("cacahuete" not in value for value in row["translation"]["ingredients"])
    assert "cacahuetes" in row["translation"]["notes"][0]
    assert "5 minutos" in row["translation"]["steps"][8]
    assert "1 minuto" in row["translation"]["steps"][9]
    assert "2 minutos" in row["translation"]["steps"][4]
    assert row["translation"]["time"] == "15 minutos"
    assert catalog.open_recipe_catalog("thick pohe")["recipes"][0]["id"] == POHE_ID


@pytest.mark.parametrize("label,bounds", [
    ("1–2", {"min": 1, "max": 2}), ("1-2", {"min": 1, "max": 2}),
    (" 1 — 2 ", {"min": 1, "max": 2}), ("1.5–2.5", {"min": 1.5, "max": 2.5}),
])
def test_explicit_range_is_supported_only_when_label_and_bounds_agree(label, bounds):
    row = pohe()
    row.update(servings_original=label, servings_range=bounds)
    assert catalog._valid_servings(row)


@pytest.mark.parametrize("bounds", [
    None, [], "1–2", {}, {"min": 1}, {"max": 2}, {"min": 1, "max": 2, "default": 1.5},
    {"min": True, "max": 2}, {"min": 1, "max": False},
    {"min": "1", "max": 2}, {"min": 1, "max": "2"},
    {"min": 0, "max": 2}, {"min": -1, "max": 2},
    {"min": 2, "max": 1}, {"min": 1, "max": 1},
    {"min": 1, "max": 3}, {"min": 1.5, "max": 2},
    {"min": float("nan"), "max": 2}, {"min": 1, "max": float("inf")},
    {"min": 1, "max": 10 ** 400},
])
def test_malformed_or_inconsistent_range_fails_closed(bounds):
    row = pohe()
    row["servings_range"] = bounds
    assert not catalog._publishable(row)


@pytest.mark.parametrize("label", [
    None, 12, "", "1", "1–3", "2–1", "1–2 servings", "1 or 2", "1/2–2", "1–2 or 3",
    "1,0–2,0", "<b>1–2</b>", "1–2\nignored", "1" * 65 + "–2",
])
def test_unknown_or_ambiguous_yield_is_not_converted_into_a_range(label):
    row = pohe()
    row["servings_original"] = label
    assert not catalog._publishable(row)


@pytest.mark.parametrize("scalar", [1, 1.5, 2, True, False, "2", 0, float("nan")])
def test_range_never_coexists_with_an_exact_serving_or_midpoint(scalar):
    row = pohe()
    row["servings"] = scalar
    assert not catalog._publishable(row)


def test_missing_range_does_not_turn_unknown_servings_into_one():
    row = pohe()
    row.pop("servings_range")
    assert not catalog._publishable(row)


@pytest.mark.parametrize("value", [None, 0, -1, True, "1", float("inf"), float("nan"), 10 ** 400])
def test_invalid_scalar_servings_still_fail_without_exception(value):
    row = pohe()
    row.pop("servings_range")
    row["servings"] = value
    assert not catalog._publishable(row)


def test_range_support_does_not_override_any_other_source_gate():
    for field, value in (("publishable", False), ("audit", {"publishable": False}),
                         ("source_sha256", "tampered"), ("rights", {})):
        row = pohe()
        row[field] = value
        assert not catalog._publishable(row)


def test_returned_range_does_not_mutate_the_catalog():
    row = catalog.open_recipe_catalog("Pohe")["recipes"][0]
    row["servings_range"]["max"] = 999
    assert catalog.open_recipe_catalog("Pohe")["recipes"][0]["servings_range"] == {"min": 1, "max": 2}
