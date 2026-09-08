from copy import deepcopy

import pytest

from roxy_os.home_recipe_core_followup import (
    EGG_KEYS,
    FLOUR_KEYS,
    RECOVERABLE_ORIGINAL_KEYS,
    REVISION,
    STEPS,
    apply_core_followup,
)
from roxy_os.home_recipe_fallback import _templates


def reviewed(key):
    row = deepcopy(_templates()[key])
    assert apply_core_followup(key, row)
    return row


@pytest.mark.parametrize("key", sorted(STEPS))
def test_named_review_preserves_food_quantities_and_user_fields(key):
    row = deepcopy(_templates()[key])
    original_food = [
        (ingredient["name"], ingredient["quantity"], ingredient["unit"])
        for ingredient in row["ingredients"]
    ]
    row.update(id="saved-example", photo_url="/personal-photo.webp", favorite=True,
               user_notes="Mi nota familiar")
    assert apply_core_followup(key, row)
    assert [(i["name"], i["quantity"], i["unit"]) for i in row["ingredients"]] == original_food
    assert row["id"] == "saved-example"
    assert row["photo_url"] == "/personal-photo.webp"
    assert row["favorite"] is True
    assert row["user_notes"] == "Mi nota familiar"
    assert row["editorial_status"] == "reviewed_local"
    assert row["editorial_revision"] == REVISION
    assert "no son autores" in row["source_context"]
    assert "certifican una prueba de cocina" in row["source_context"]
    assert all(source["url"].startswith("https://www.fda.gov/") for source in row["sources"])
    assert row["steps"] == STEPS[key]


@pytest.mark.parametrize("key", ["installed_fl an", "installed_rice", "unseen_recipe", ""])
def test_unknown_and_installed_keys_never_promote_drafts(key):
    row = {"title": "Arroz con vegetales", "editorial_status": "needs_canonical_review", "steps": ["Original"]}
    before = deepcopy(row)
    assert apply_core_followup(key, row) is False
    assert row == before


def test_pet_row_is_untouched_even_with_matching_original_key():
    row = {"title": "Arroz con vegetales", "audience": "pet", "steps": ["Pet instruction"]}
    before = deepcopy(row)
    assert apply_core_followup("rice", row) is False
    assert row == before


@pytest.mark.parametrize("key", sorted(RECOVERABLE_ORIGINAL_KEYS))
def test_recoverable_originals_have_individual_methods_and_exact_categories(key):
    row = reviewed(key)
    assert row["editorial_status"] == "reviewed_local"
    assert row["category"] != "meat"
    assert "proteína" not in " ".join(row["steps"])
    assert row["steps"] != reviewed("flan")["steps"]


@pytest.mark.parametrize("key", ["flan", "cheesecake"])
def test_custards_require_cooked_center_and_prompt_refrigeration(key):
    text = " ".join(reviewed(key)["steps"])
    assert "71.1 °C" in text
    assert "4 °C" in text
    assert "2 horas" in text
    assert "3–4 días" in text
    assert "molde" in text


def test_tres_leches_explains_batter_before_baking_and_chills_after_soaking():
    steps = reviewed("tres_leches")["steps"]
    assert "claras" in steps[1] and "picos firmes" in steps[1]
    assert "yemas" in steps[2]
    assert "harina" in steps[3] and "envolventes" in steps[2]
    assert "Vierte en el molde" in steps[4]
    assert "palillo" in steps[4]
    assert "refrigera de inmediato" in steps[6]


def test_brownies_cool_chocolate_before_eggs_and_specify_pan_and_endpoint():
    steps = reviewed("brownies")["steps"]
    assert "20 cm" in steps[0]
    assert "Deja templar" in steps[1]
    assert "chocolate templado" in steps[2]
    assert "molde preparado" in steps[3]
    assert "no con masa líquida" in steps[4]


def test_apple_pie_uses_all_existing_butter_not_an_unlisted_filling():
    text = " ".join(reviewed("apple_pie")["steps"])
    assert "toda la mantequilla de la lista" in text
    assert "segunda lámina" in text and "ranuras" in text
    assert "manzana esté tierna" in text


def test_bread_explicitly_uses_existing_oil_and_cools_on_rack():
    text = " ".join(reviewed("bread")["steps"])
    assert "el aceite de la lista" in text
    assert "rejilla" in text
    assert "masa cruda" in text


@pytest.mark.parametrize("key", ["whiskey_sour", "old_fashioned", "manhattan", "negroni", "cosmopolitan", "aperol_spritz", "mai_tai"])
def test_cocktails_do_not_require_unlisted_garnish_or_five_step_padding(key):
    row = reviewed(key)
    assert row["drink_type"] == "alcoholic"
    assert len(row["steps"]) == 2
    text = " ".join(row["steps"]).lower()
    assert "decora con" not in text
    assert "sirve con piel" not in text
    assert "sirve con naranja" not in text


def test_soaked_oats_have_refrigeration_not_countertop_overnight():
    row = reviewed("overnight_oats")
    assert len(row["steps"]) == 3
    assert "4 °C" in row["steps"][1] and "6 horas" in row["steps"][1]
    assert any(i["notes"] == "en hojuelas" for i in row["ingredients"])


def test_tuna_bowl_uses_canned_tuna_not_raw_fish():
    row = reviewed("tuna_bowl")
    assert "no usa pescado crudo" in row["steps"][0]
    assert any("en conserva" in i["notes"] for i in row["ingredients"])


def test_references_are_relevant_and_detached_not_shared_mutable_lists():
    for key in EGG_KEYS:
        assert any("egg-safety" in source["url"] for source in reviewed(key)["sources"])
    for key in FLOUR_KEYS:
        assert any("handling-flour" in source["url"] for source in reviewed(key)["sources"])
    row = reviewed("flan")
    row["sources"][0]["title"] = "Modified only here"
    row["steps"][0] = "Modified only here"
    assert reviewed("flan")["sources"][0]["title"] != "Modified only here"
    assert STEPS["flan"][0] != "Modified only here"
