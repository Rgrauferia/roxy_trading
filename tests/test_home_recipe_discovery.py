from copy import deepcopy
import json

import pytest

from roxy_os.home_recipe_discovery import assess_recipe_fit, discovery_presets, screen_recipe_summaries
from roxy_os.home_recipe_profile import recipe_profile_options


def profile(**changes):
    return {
        "schema_version": 1, "completed": True, "consent": True, "language": "es",
        "country_of_origin": "", "cuisine_mode": "mixed", "cuisines": [],
        "favorite_foods": [], "diet": "omnivore", "allergy_status": "none",
        "allergies": [], "other_allergies": "", "dislikes": [],
        "max_minutes": None, "skill": "undisclosed", **changes,
    }


def test_discovery_uses_only_explicit_choices_and_never_private_free_text():
    private = profile(country_of_origin="PrivateCountry", cuisines=["mexican"], favorite_foods=["pasta", "soups"],
                      allergy_status="listed", allergies=["other"], other_allergies="PrivateAllergy", dislikes=["PrivateDislike"])
    before = deepcopy(private)
    discovery = discovery_presets(private)
    assert [(row["query"], row["category"]) for row in discovery["presets"]] == [("pasta", ""), ("", "Soup")]
    assert "Private" not in json.dumps(discovery)
    assert private == before


@pytest.mark.parametrize("country,query", [
    ("Perú", "Peruvian"), ("Cuba", "Cuban"), ("República Dominicana", "Dominican"),
    ("Colombia", "Colombian"), ("Puerto Rico", "Puerto Rican"), ("Brasil", "Brazilian"),
    ("Costa Rica", "Costa Rican"), ("Venezuela", "Venezuelan"),
])
def test_origin_is_an_explicit_country_query_not_a_region(country, query):
    discovery = discovery_presets(profile(country_of_origin=country, cuisine_mode="origin"))
    assert len(discovery["presets"]) == 1
    assert discovery["presets"][0]["query"] == query
    assert all(row["query"] == "" for row in discovery_presets(profile(country_of_origin=country))["presets"])


def test_unknown_country_or_cuisine_stays_explicit():
    discovery = discovery_presets(profile(country_of_origin="Private unknown country", cuisine_mode="origin"))
    assert [row["category"] for row in discovery["presets"]] == ["Main dish", "Soup", "Salad", "Dessert"]
    assert all(row["query"] == "" for row in discovery["presets"])
    assert "Aún no hay" in discovery["notice"]
    assert "Private" not in discovery["notice"]
    other = discovery_presets(profile(cuisine_mode="selected", cuisines=["other"]))
    assert len(other["presets"]) == 4 and "Otra" in other["notice"]


def test_mixed_without_favorites_gets_fixed_diverse_categories_without_inferred_origin():
    first = discovery_presets(profile(country_of_origin="Perú"))
    second = discovery_presets(profile(country_of_origin="Italia"))
    assert first == second
    assert [row["category"] for row in first["presets"]] == ["Main dish", "Soup", "Salad", "Dessert"]
    assert all(row["query"] == "" and row["reason"] == "Para explorar sabores diferentes" for row in first["presets"])
    selected = discovery_presets(profile(favorite_foods=["pasta"]))
    assert len(selected["presets"]) == 1 and selected["presets"][0]["query"] == "pasta"


def test_explicit_region_selection_and_favorite_queries_are_fixed():
    discovery = discovery_presets(profile(cuisine_mode="selected", cuisines=["caribbean", "italian"], favorite_foods=["rice"]))
    assert [row["query"] for row in discovery["presets"]] == ["Caribbean", "Italian", "rice"]
    assert all(set(row) == {"id", "label", "query", "category", "reason"} for row in discovery["presets"])
    assert "tiempo ni nivel" in discovery["notice"]


def test_every_choice_maps_or_explicitly_reports_missing_support():
    options = recipe_profile_options()
    for row in options["cuisines"]:
        result = discovery_presets(profile(cuisine_mode="selected", cuisines=[row["value"]]))
        assert result["presets"] or "Otra" in result["notice"]
    for row in options["favorite_foods"]:
        result = discovery_presets(profile(favorite_foods=[row["value"]]))
        assert len(result["presets"]) == 1
        assert result["presets"][0]["category"] in {"", "Soup", "Salad", "Dessert"}


@pytest.mark.parametrize("raw", [None, {}, "bad", {"completed": True}, profile(completed=False)])
def test_unusable_profile_is_not_personalized(raw):
    assert discovery_presets(raw)["presets"] == []
    assert assess_recipe_fit(raw, ["rice"])["status"] == "needs_review"


@pytest.mark.parametrize("ingredients", [None, [], "rice", [""], [None], [{"name": "rice"}], ["x" * 4001], ["rice"] * 201])
def test_insufficient_ingredient_evidence_never_returns_unrestricted(ingredients):
    result = assess_recipe_fit(profile(), ingredients, title="Safe vegan allergy-free dish")
    assert result["status"] == "needs_review"
    assert "ingredientes suficiente" in result["caution"]


@pytest.mark.parametrize("allergen,ingredient", [
    ("milk", "1 cup milk"), ("milk", "100 g queso"), ("eggs", "2 huevos"),
    ("fish", "tuna in water"), ("shellfish", "1 cup shrimp"), ("tree_nuts", "almendras"),
    ("peanuts", "peanut butter"), ("wheat", "whole wheat flour"),
    ("soy", "2 cucharadas de soja"), ("sesame", "tahini"),
])
def test_declared_allergen_terms_raise_possible_conflict(allergen, ingredient):
    result = assess_recipe_fit(profile(allergy_status="listed", allergies=[allergen]), [ingredient])
    assert result["status"] == "conflict"
    assert any("alergia indicada" in item for item in result["conflicts"])
    assert "no certifica" in result["caution"]


def test_peanuts_do_not_implicitly_mean_tree_nuts():
    result = assess_recipe_fit(profile(allergy_status="listed", allergies=["tree_nuts"]), ["peanuts", "coconut", "nutmeg"])
    assert result["conflicts"] == []
    assert result["status"] == "needs_review"


def test_plant_milk_and_nut_butter_are_not_definite_dairy_conflicts():
    result = assess_recipe_fit(profile(allergy_status="listed", allergies=["milk"]), ["almond milk", "peanut butter"])
    assert result["status"] == "needs_review"
    assert result["conflicts"] == []
    assert assess_recipe_fit(profile(allergy_status="listed", allergies=["tree_nuts"]), ["almond milk"])["status"] == "conflict"


def test_no_lexicon_match_never_clears_declared_allergies():
    result = assess_recipe_fit(profile(allergy_status="listed", allergies=["wheat"]), ["1 cup flour", "sauce"])
    assert result["status"] == "needs_review"
    assert result["conflicts"] == []
    assert "etiquetas" in result["caution"]


def test_custom_allergy_only_matches_whole_text_and_remains_uncertain_otherwise():
    selected = profile(allergy_status="listed", allergies=["other"], other_allergies="Kiwi")
    assert assess_recipe_fit(selected, ["1 kiwi"])["status"] == "conflict"
    assert assess_recipe_fit(selected, ["kiwifruit flavor"])["status"] == "needs_review"


@pytest.mark.parametrize("diet,ingredient", [
    ("vegetarian", "chicken broth"), ("vegetarian", "salmon"),
    ("vegan", "miel"), ("vegan", "huevos"), ("vegan", "queso"),
    ("pescatarian", "bacon"),
])
def test_diet_conflicts_are_evidence_not_recipe_certification(diet, ingredient):
    result = assess_recipe_fit(profile(diet=diet), [ingredient])
    assert result["status"] == "conflict"
    assert "alimentación" in result["conflicts"][0]
    assert assess_recipe_fit(profile(diet=diet), ["rice"])["status"] == "needs_review"


def test_fish_is_not_a_pescatarian_conflict():
    result = assess_recipe_fit(profile(diet="pescatarian"), ["fish", "rice"])
    assert result["status"] == "needs_review" and result["conflicts"] == []


def test_title_is_not_ingredient_evidence():
    result = assess_recipe_fit(profile(allergy_status="listed", allergies=["eggs"]), ["rice"], title="No eggs")
    assert result["status"] == "needs_review" and result["conflicts"] == []


def test_disliked_food_matches_word_boundaries_and_accents():
    selected = profile(dislikes=["piña", "res"])
    assert assess_recipe_fit(selected, ["piña en cubos"])["status"] == "conflict"
    result = assess_recipe_fit(selected, ["fresa", "fresh vegetables"])
    assert result["conflicts"] == [] and result["status"] == "needs_review"


@pytest.mark.parametrize("duration", [None, True, "30", float("nan"), float("inf"), -1, 0])
def test_missing_or_malformed_source_duration_remains_unknown(duration):
    result = assess_recipe_fit(profile(max_minutes=30), ["rice"], duration_minutes=duration)
    assert result["status"] == "needs_review"
    assert "No se conoce el tiempo" in result["caution"]


def test_valid_source_duration_is_compared_without_estimating():
    assert assess_recipe_fit(profile(max_minutes=30), ["rice"], duration_minutes=45)["status"] == "conflict"
    assert assess_recipe_fit(profile(max_minutes=30), ["rice"], duration_minutes=30)["status"] == "unrestricted"


def test_undisclosed_answers_and_no_declared_restrictions_are_different():
    assert assess_recipe_fit(profile(allergy_status="undisclosed"), ["rice"])["status"] == "needs_review"
    assert assess_recipe_fit(profile(diet="undisclosed"), ["rice"])["status"] == "needs_review"
    result = assess_recipe_fit(profile(), ["rice"])
    assert result["status"] == "unrestricted"
    assert "no certifica" in result["caution"]


def test_summary_screen_hides_observed_steak_and_creamy_dressing_conflicts():
    selected = profile(diet="vegetarian", allergy_status="listed", allergies=["milk"])
    rows = [
        {"slug": "steak", "title": "Steak salad", "description": "Italian style"},
        {"slug": "dressing", "title": "Creamy Italian Dressing", "description": "For salads"},
        {"slug": "pasta", "title": "Pasta salad", "description": "Ingredients not in this summary", "can_cook": False},
    ]
    before = deepcopy(rows)
    result = screen_recipe_summaries(selected, rows)
    assert result["rows"] == [rows[2]] and result["hidden_in_page"] == 2
    assert rows == before
    assert "necesitan revisión" in result["notice"]
    assert "no están certificadas" in result["notice"]
    assert "status" not in result["rows"][0] and result["rows"][0]["can_cook"] is False


@pytest.mark.parametrize("selected,row", [
    (profile(diet="vegetarian"), {"title": "Bistec con ensalada"}),
    (profile(diet="vegetarian"), {"title": "Arroz", "description": "Con pollo y verduras"}),
    (profile(diet="vegan"), {"title": "Pan con miel"}),
    (profile(diet="vegan"), {"title": "Ensalada", "description": "Huevos y queso"}),
    (profile(diet="pescatarian"), {"title": "Pasta with bacon"}),
    (profile(allergy_status="listed", allergies=["peanuts"]), {"title": "Peanut sauce"}),
    (profile(allergy_status="listed", allergies=["sesame"]), {"description": "Tahini dressing"}),
    (profile(allergy_status="listed", allergies=["other"], other_allergies="kiwi"), {"title": "Kiwi juice"}),
    (profile(dislikes=["piña"]), {"title": "Arroz con piña"}),
])
def test_summary_screen_uses_explicit_diet_allergy_and_dislike_clues(selected, row):
    result = screen_recipe_summaries(selected, [row])
    assert result["rows"] == [] and result["hidden_in_page"] == 1


@pytest.mark.parametrize("row", [
    {"title": "No milk muffins"}, {"title": "Milk-free bread"},
    {"title": "Sin leche", "description": "Pan de avena"},
    {"title": "Almond milk drink"}, {"title": "Peanut butter cookies"},
])
def test_summary_absence_or_plant_alternative_is_not_positive_dairy_evidence(row):
    result = screen_recipe_summaries(profile(allergy_status="listed", allergies=["milk"]), [row])
    assert result["rows"] == [row] and result["hidden_in_page"] == 0
    assert "no están certificadas" in result["notice"]


def test_summary_alternative_does_not_hide_other_conflicting_text():
    selected = profile(diet="vegetarian", allergy_status="listed", allergies=["milk"])
    rows = [
        {"title": "Cauliflower steak", "description": "With vegetables"},
        {"title": "Cauliflower steak", "description": "With bacon"},
        {"title": "No milk bread", "description": "Made with butter"},
    ]
    result = screen_recipe_summaries(selected, rows)
    assert result["rows"] == [rows[0]] and result["hidden_in_page"] == 2


def test_summary_words_do_not_produce_substring_allergen_or_meat_claims():
    selected = profile(diet="vegetarian", allergy_status="listed", allergies=["tree_nuts"])
    rows = [{"title": "Peanut and coconut salad", "description": "Fresh strawberries and nutmeg"}]
    assert screen_recipe_summaries(selected, rows)["rows"] == rows


def test_summary_fish_can_remain_for_pescatarian_and_time_skill_are_not_inferred():
    selected = profile(diet="pescatarian", max_minutes=10, skill="beginner")
    rows = [{"title": "Fish stew", "description": "Traditional slow recipe"}]
    assert screen_recipe_summaries(selected, rows)["rows"] == rows


@pytest.mark.parametrize("selected", [None, profile(completed=False), profile(diet="undisclosed", allergy_status="undisclosed")])
def test_summary_screen_does_not_invent_undisclosed_restrictions(selected):
    rows = [{"title": "Steak with cheese", "description": "Source summary"}]
    result = screen_recipe_summaries(selected, rows)
    assert result["rows"] == rows and result["hidden_in_page"] == 0


def test_summary_screen_preserves_source_order_unknown_metadata_and_input():
    rows = [
        {"slug": "first", "title": "Rice", "source": {"id": 5}},
        {"slug": "middle", "title": "Chicken"},
        {"slug": "last", "title": "Unknown", "description": None},
    ]
    result = screen_recipe_summaries(profile(diet="vegetarian"), rows)
    assert [row["slug"] for row in result["rows"]] == ["first", "last"]
    result["rows"][0]["source"]["id"] = 10
    assert rows[0]["source"]["id"] == 5
    assert "total" not in result and "offset" not in result
    assert screen_recipe_summaries(profile(), []) == {"rows": [], "hidden_in_page": 0, "notice": result["notice"]}


@pytest.mark.parametrize("rows", [None, "bad", [None], ["row"]])
def test_summary_screen_rejects_malformed_source_container(rows):
    with pytest.raises(ValueError):
        screen_recipe_summaries(profile(), rows)


@pytest.mark.parametrize("title", [
    "Baked Meatballs", "Meatball sandwich", "Albóndiga al horno", "Albóndigas en salsa",
    "Sausage Pasta", "Sausages with beans", "Salchichas al horno", "Steaks and salad",
    "Burger", "Burgers", "Hamburger", "Hamburgers", "Hamburguesa", "Hamburguesas",
])
def test_summary_common_meat_dishes_and_plurals_are_excluded(title):
    row = {"title": title, "description": "Source summary"}
    result = screen_recipe_summaries(profile(diet="vegetarian"), [row])
    assert result["rows"] == [] and result["hidden_in_page"] == 1


@pytest.mark.parametrize("title", [
    "Baked veggie meatballs", "Vegetarian meatball sandwich", "Vegan meatballs",
    "Plant-based burgers", "Black bean burger", "Lentil meatballs", "Chickpea burgers",
    "Mushroom burger", "Vegan sausages", "Vegetarian sausage casserole",
    "Albóndigas vegetarianas", "Albóndigas de lentejas", "Hamburguesas de garbanzos",
    "Hamburguesa vegana", "Salchichas vegetales", "Cauliflower steaks",
])
def test_summary_clear_plant_dish_descriptor_remains_visible_for_review(title):
    row = {"title": title, "description": "Source summary"}
    result = screen_recipe_summaries(profile(diet="vegetarian"), [row])
    assert result["rows"] == [row] and result["hidden_in_page"] == 0
    assert "no están certificadas" in result["notice"]


def test_plant_meatball_phrase_does_not_erase_separate_conflict():
    rows = [
        {"title": "Veggie meatballs", "description": "Served with bacon"},
        {"title": "Black bean burgers", "description": "With cheese"},
        {"title": "Albóndigas de lentejas", "description": "Con pollo"},
    ]
    result = screen_recipe_summaries(profile(diet="vegetarian", allergy_status="listed", allergies=["milk"]), rows)
    assert result["rows"] == [] and result["hidden_in_page"] == 3


def test_summary_screen_does_not_read_recipe_instructions_as_ingredients():
    row = {"title": "Rice and vegetables", "description": "Source summary",
           "instructions": "Shape it like meatballs; use a meatloaf-like pan.",
           "source_steps": ["Shape like burgers or steaks."]}
    assert screen_recipe_summaries(profile(diet="vegetarian"), [row])["rows"] == [row]
    fit = assess_recipe_fit(profile(diet="vegetarian"), ["rice", "vegetables"], title="Baked Meatballs")
    assert fit["status"] == "needs_review" and fit["conflicts"] == []
