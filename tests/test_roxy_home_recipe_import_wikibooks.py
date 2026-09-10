import hashlib
import json
from pathlib import Path

import pytest

from tools.roxy_home_recipe_import_wikibooks import (
    WikiClient, audit_rows, candidate, editorial_flags, fields, measured, plain, top_split,
)


WIKI = """{{recipesummary|servings=2|time=20 minutes|image=[[File:Oats.jpg|300px]]}}
==Ingredients==
* 1 cup [[Cookbook:Oats|oats]]
* 2 cups water
* Salt to taste
==Procedure==
# Put the oats and water into a pan.
# Simmer for 15 minutes and serve with salt to taste.
[[Category:Breakfast recipes]]
"""


def row(wiki=WIKI, language="en", pageid=123):
    return candidate({"pageid": pageid, "title": "Cookbook:Example", "revisions": [{
        "revid": 456, "timestamp": "2026-09-10T00:00:00Z", "slots": {"main": {"*": wiki}}
    }]}, language, "2026-09-10T01:00:00Z")


def test_complete_original_is_not_an_approved_recipe():
    r = row()
    assert r["audit"]["issues"] == []
    assert r["audit"]["status"] == "source_structure_complete_pending_editorial_review"
    assert not r["audit"]["publishable"]
    assert not r["audit"]["can_cook_with_roxy"]
    assert not r["audit"]["can_add_to_shopping"]
    assert r["audit"]["culinary_review"] == "not_performed"
    assert r["ingredients_original"] == ["1 cup oats", "2 cups water", "Salt to taste"]
    assert r["steps_original"][-1].startswith("Simmer for 15 minutes")
    assert r["source_sha256"] == hashlib.sha256(WIKI.encode()).hexdigest()
    assert "oldid=456" in r["source_revision_url"]


def test_media_never_inherits_recipe_license_or_visual_approval():
    r = row()
    assert r["source_image_names"] == ["Oats.jpg"]
    assert "image_url" not in r
    assert r["image_status"] == "individual_rights_and_visual_review_required"
    assert r["audit"]["visual_review"] == "not_performed"


def test_missing_measure_is_flagged_not_completed():
    r = row(WIKI.replace("2 cups water", "Water"))
    assert r["ingredients_original"][1] == "Water"
    assert r["audit"]["unmeasured_ingredient_indexes"] == [1]
    assert "ingredient_measure_review_required" in r["audit"]["issues"]


@pytest.mark.parametrize("original,expected", [
    ("{{frac|1|2}} cup milk", "1/2 cup milk"),
    ("{{frac|1|1|2}} cups milk", "1 1/2 cups milk"),
    ("{{convert|8|oz|g|abbr=on}} rice", "8 oz rice"),
    ("1 taza de {{ing|arroz}}", "1 taza de arroz"),
    ("{{coc|freír|fríe}} el arroz", "fríe el arroz"),
])
def test_known_markup_keeps_only_original_numbers(original, expected):
    issues = set()
    assert plain(original, issues) == expected
    assert issues == set()


def test_unknown_template_is_preserved_and_blocked():
    issues = set()
    assert "{{mystery|5|cups}}" in plain("{{mystery|5|cups}} flour", issues)
    assert "unresolved_template" in issues


def test_nested_pipes_do_not_break_recipe_fields():
    source = "{{recipesummary|servings=2|image=[[File:X.jpg|300px]]|time={{nowrap|5 minutes}}}}"
    assert fields(source)["time"] == "{{nowrap|5 minutes}}"
    assert len(top_split("a|[[x|y]]|{{z|v}}")) == 3


def test_spanish_original_is_not_translated_or_inferred():
    source = """{{Artes culinarias/Datos de receta
|cantidad para=4 personas
|ingredientes=
* 1 taza de {{ing|arroz}}
* 2 tazas de agua
|procedimiento=
# Calentar el agua.
# Añadir el arroz y cocinar 20 minutos.
}}"""
    r = row(source, "es")
    assert r["servings_original"] == "4 personas"
    assert r["ingredients_original"] == ["1 taza de arroz", "2 tazas de agua"]
    assert r["steps_original"] == ["Calentar el agua.", "Añadir el arroz y cocinar 20 minutos."]
    assert r["audit"]["issues"] == []
    assert r["language"] == "es"


@pytest.mark.parametrize("source,issue", [
    (WIKI.replace("servings=2", "servings="), "missing_original_yield"),
    (WIKI.replace("# Simmer", "Simmer"), "non_list_content_in_recipe_section"),
    (WIKI + "{{cookwork}}", "source_maintenance_or_rights_warning"),
    (WIKI + "Source: another cookbook", "additional_attribution_review_required"),
    (WIKI.replace("Simmer", "For canning, simmer"), "special_food_safety_review_required"),
])
def test_incomplete_or_special_source_requires_review(source, issue):
    assert issue in row(source)["audit"]["issues"]


def test_content_duplicate_is_not_counted_twice_as_complete():
    a, b = row(), row(pageid=124)
    summary = audit_rows([a, b])
    assert summary["source_structure_complete"] == 1
    assert summary["culinary_approved"] == 0
    assert summary["publishable"] == 0
    assert b["audit"]["duplicate_of"] == a["id"]


def test_redirect_is_not_a_new_recipe():
    assert row("#REDIRECT [[Cookbook:Example]]") is None


def test_no_network_from_constructor_and_no_arbitrary_source(tmp_path):
    client = WikiClient("es", tmp_path)
    assert client.url == "https://es.wikibooks.org/w/api.php"
    with pytest.raises(ValueError): WikiClient("http://127.0.0.1", tmp_path)


@pytest.mark.parametrize("line", ["Salt", "Milk", "Flour", "Agua", "1/4 de pasas", "1/2 de piñones"])
def test_bare_ingredients_are_not_assigned_default_measures(line):
    assert not measured(line)


def test_safety_triage_never_repairs_source_or_claims_safety():
    flags = editorial_flags(["3 huevos", "250g de queso"], ["Mezclar las yemas con queso.", "Refrigerar."], "")
    assert "egg_cooking_or_pasteurization_review" in flags
    assert editorial_flags(["2 cups water", "1 cup rice"], ["Cook rice"], "") == []
    # The no-flag source still cannot cook: triage is deliberately not clearance.
    assert row()["audit"]["can_cook_with_roxy"] is False


def test_unlisted_poultry_and_missing_note_are_flagged_without_substituting():
    flags = editorial_flags(["1 cup pork broth"], ["Bring chicken broth to boil (see Note)."], "")
    assert "possible_unlisted_ingredient:chicken" in flags
    assert "referenced_notes_missing_from_extraction" in flags


def test_dehydration_and_inline_instructions_require_review():
    flags = editorial_flags(["1 taza de trigo"], ["Para germinar y deshidratar #Opcionalmente añadir pasas"], "")
    assert "sprouting_or_dehydration_review" in flags
    assert "inline_instruction_marker" in flags


def test_notes_are_preserved_separately_in_source_markup():
    r = row(WIKI + "\n==Notes==\n* Important source detail.\n")
    assert "Important source detail" in r["notes_source_wikitext"]
    assert r["audit"]["publishable"] is False


def test_source_duplicate_warning_excludes_count_padding():
    r = row(WIKI + "\n[[Category:Duplicate recipes]]")
    assert "source_marked_possible_duplicate" in r["audit"]["issues"]


def test_actual_corpus_integrity_and_zero_automatic_approvals():
    path = Path(__file__).resolve().parents[1] / "data/home_recipe_candidates_20260910.json"
    data = json.loads(path.read_text())
    assert data["kind"] == "editorial_candidates_not_runtime_catalogue"
    assert data["public_enabled"] is False
    assert len(data["recipes"]) >= 500
    assert len({r["id"] for r in data["recipes"]}) == len(data["recipes"])
    assert len({r["content_fingerprint"] for r in data["recipes"]}) == len(data["recipes"])
    for r in data["recipes"]:
        assert hashlib.sha256(r["original_wikitext"].encode()).hexdigest() == r["source_sha256"]
        assert r["audit"]["issues"] == []
        assert not r["audit"]["publishable"]
        assert not r["audit"]["can_cook_with_roxy"]
        assert not r["audit"]["can_add_to_shopping"]
        assert r["rights"]["share_alike_required"]
        assert r["rights"]["attribution_url"] == r["source_url"]
        assert all(not m["display_enabled"] for m in r.get("source_media_candidates", []))
    from roxy_os.home_open_recipes import CATALOG_PATH
    assert path != CATALOG_PATH


def test_spanish_unit_omission_and_source_duplicates_remain_outside_retained_candidates():
    path = Path(__file__).resolve().parents[1] / "data/home_recipe_candidates_20260910.json"
    data = json.loads(path.read_text())
    rejected = {r["id"]: r for r in data["rejected_index"]}
    assert "ingredient_measure_review_required" in rejected["wikibooks-es-39453"]["issues"]
    assert "source_marked_possible_duplicate" in rejected["wikibooks-en-479550"]["issues"]


def test_repeated_source_photo_is_not_called_specific_or_enabled():
    path = Path(__file__).resolve().parents[1] / "data/home_recipe_candidates_20260910.json"
    data = json.loads(path.read_text())
    shared = [r for r in data["recipes"] if r["title"] in {"Iced Tea", "Hawthorn Tea"}]
    assert len(shared) == 2
    for r in shared:
        assert "same_source_image_used_for_multiple_recipes" in r["audit"]["editorial_triage_flags"]
        assert all(not m["display_enabled"] for m in r["source_media_candidates"])
