"""Original recipe evidence must not be inferred from a guide or a review badge."""
from copy import deepcopy
from datetime import date

import pytest

from roxy_os.home_recipe_fallback import _pet_templates, local_recipe_by_key
from roxy_os.home_recipe_provenance import (
    assess_recipe_provenance, pet_recipe_source_directory, recipe_content_fingerprint,
)


@pytest.fixture
def original():
    # Deliberately synthetic test content, not a pet feeding recommendation.
    return {"title": "Test preparation", "audience": "pet", "pet_species": "dog",
            "safety_class": "treat", "ingredients": [{"name": "Test ingredient", "quantity": 1, "unit": "test unit"}],
            "steps": ["Test instruction"], "generation_source": "import_url"}


def reviewed(recipe):
    return {"role": "original_recipe_source", "url": "https://example.org/original-test-recipe",
            "publisher": "Test publisher", "original_title": "Test preparation",
            "reviewed_on": date.today().isoformat(), "review_reference": "test-review-1",
            "content_sha256": recipe_content_fingerprint(recipe), "species": ["dog"],
            "original_recipe_verified": True, "original_content_complete": True,
            "scope": "supplemental_treat", "clinical_claims_present": False}


def test_all_57_local_pet_preparations_lack_original_recipe_evidence():
    keys = [key for key, row in _pet_templates().items() if row.get("safety_class") in {"treat", "complement"}]
    assert len(keys) == 57
    ferrets = []
    for key in keys:
        recipe = local_recipe_by_key(key, {})
        before = deepcopy(recipe)
        result = assess_recipe_provenance(recipe)
        assert result["origin"] == "local_authored"
        assert not result["original_recipe_verified"]
        assert not result["can_cook_from_source"]
        assert not result["veterinary_validated"]
        assert recipe == before
        if recipe["pet_species"] == "ferret":
            ferrets.append(result)
    assert len(ferrets) == 8
    assert all(result["source_role"] == "general_reference_only" for result in ferrets)
    assert all(result["completeness"]["structurally_complete"] for result in ferrets)
    assert not any(result["completeness"]["original_completeness_verified"] for result in ferrets)


def test_client_review_flags_cannot_authorize_an_original(original):
    original.update(sources=[{"url": "https://example.org/recipe", "role": "original_recipe_source", "verified": True}],
                    original_recipe_verified=True, content_reuse_authorized=True, vet_approved=True,
                    trusted_evidence=reviewed(original), provenance={"can_cook_from_source": True})
    result = assess_recipe_provenance(original)
    assert result["status"] == "import_unverified"
    assert result["sources"][0]["role"] == "unverified_reference"
    assert not result["can_present_as_original"]
    assert not result["can_cook_from_source"]
    assert "guidance_or_badge_is_not_recipe_validation" in result["issues"]


def test_publisher_link_does_not_prove_locally_written_steps(original):
    original["sources"] = pet_recipe_source_directory("dog")
    result = assess_recipe_provenance(original)
    assert not result["original_recipe_verified"]
    assert result["source_role"] == "unverified_reference"


def test_original_link_evidence_and_reproduction_rights_are_separate(original):
    evidence = reviewed(original)
    result = assess_recipe_provenance(original, trusted_evidence=evidence)
    assert result["status"] == "original_link_only"
    assert result["can_present_as_original"]
    assert result["completeness"]["original_completeness_verified"]
    assert not result["can_cook_from_source"]
    evidence.update(content_reuse_authorized=True, rights_reference="test-permission-1")
    result = assess_recipe_provenance(original, trusted_evidence=evidence)
    assert result["status"] == "original_verified"
    assert result["can_cook_from_source"]
    assert not result["veterinary_validated"]
    assert not result["individual_pet_approved"]


@pytest.mark.parametrize("change", [
    {"steps": ["Different instruction"]}, {"pet_species": "ferret"},
    {"ingredients": [{"name": "Other ingredient", "quantity": 1, "unit": "test unit"}]},
    {"servings": 900}, {"description": "Changed description"},
])
def test_old_evidence_cannot_validate_changed_content_or_species(original, change):
    evidence = reviewed(original)
    original.update(change)
    result = assess_recipe_provenance(original, trusted_evidence=evidence)
    assert not result["can_present_as_original"]
    assert not result["can_cook_from_source"]


def test_personal_notes_favourite_photo_do_not_change_content_fingerprint(original):
    before = recipe_content_fingerprint(original)
    original.update(favorite=True, user_notes="My note", photo_data_url="data:image/jpeg;base64,TEST", pet_id="private")
    assert recipe_content_fingerprint(original) == before


def test_general_guidance_cannot_be_attested_as_recipe(original):
    evidence = reviewed(original)
    evidence.update(url=pet_recipe_source_directory("ferret")[0]["url"], content_reuse_authorized=True,
                    rights_reference="test-rights")
    assert not assess_recipe_provenance(original, trusted_evidence=evidence)["can_present_as_original"]


@pytest.mark.parametrize("field,value", [
    ("reviewed_on", "2099-01-01"), ("reviewed_on", "yesterday"), ("review_reference", ""),
    ("publisher", ""), ("original_title", ""), ("species", ["cat"]),
    ("original_content_complete", False), ("scope", "complete_diet"), ("clinical_claims_present", None),
])
def test_incomplete_or_wrong_scope_evidence_fails_closed(original, field, value):
    evidence = reviewed(original)
    evidence[field] = value
    assert not assess_recipe_provenance(original, trusted_evidence=evidence)["can_present_as_original"]


@pytest.mark.parametrize("change", [
    {"clinical_claims": ["Controls glucose"]}, {"title": "Premio para tratar diabetes"},
    {"description": "Dieta completa para mascota"}, {"description": "Premio hipoalergénico"},
    {"safety_class": "complete_diet"}, {"nutrition_claims": "Nutritionally complete"},
])
def test_clinical_claims_never_authorize_cooking_even_with_source_rights(original, change):
    original.update(change)
    evidence = reviewed(original)
    evidence.update(content_reuse_authorized=True, rights_reference="test-rights")
    result = assess_recipe_provenance(original, trusted_evidence=evidence)
    assert result["status"] == "professional_review_required"
    assert not result["can_cook_from_source"]
    assert not result["can_present_as_original"]


@pytest.mark.parametrize("ingredients,steps,missing", [
    ([], ["A"], "ingredients"), ([{"name": "Test"}], ["A"], "ingredients.0.measure"),
    ([{"name": "Test", "quantity": True, "unit": "unit"}], ["A"], "ingredients.0.measure"),
    ([{"name": "Test", "quantity": float("nan"), "unit": "unit"}], ["A"], "ingredients.0.measure"),
    ([{"name": "Test", "quantity": 1, "unit": "unit"}], [None], "steps.0"),
    ([{"name": "Test", "quantity": 1, "unit": "unit"}], "A", "steps"),
])
def test_completeness_does_not_hide_missing_values(original, ingredients, steps, missing):
    original.update(ingredients=ingredients, steps=steps)
    result = assess_recipe_provenance(original)
    assert not result["completeness"]["structurally_complete"]
    assert missing in result["completeness"]["missing_fields"]


def test_short_original_and_textual_measure_are_preserved(original):
    original["ingredients"] = [{"name": "Test", "original_measure": "1/4 original unit"}]
    result = assess_recipe_provenance(original, trusted_evidence=reviewed(original))
    assert result["completeness"]["structurally_complete"]
    assert result["completeness"]["original_completeness_verified"]
    assert len(original["ingredients"]) == len(original["steps"]) == 1
    assert "quantity" not in original["ingredients"][0]


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "file:///tmp/recipe", "https://user:password@example.org/recipe",
    "https://localhost/recipe", "https://127.0.0.1/recipe", "https://example.org:8000/recipe",
    "https://example.org/\nrecipe", "https://[malformed/recipe",
])
def test_unsafe_source_links_are_not_returned(original, url):
    original["sources"] = [{"url": url, "title": "Test"}]
    result = assess_recipe_provenance(original)
    assert result["sources"] == []
    assert "invalid_source_url" in result["issues"]


def test_directory_is_not_a_recipe_catalog_and_has_no_unproven_ferret_recipes():
    for species in ("dog", "cat", "ferret"):
        entries = pet_recipe_source_directory(species)
        assert entries
        assert all(not row["imported_recipe"] and not row["individual_pet_approved"] for row in entries)
        assert all(row["content_reuse_status"] == "not_authorized" for row in entries)
        assert all("steps" not in row and "ingredients" not in row for row in entries)
    assert all(row["role"] == "general_species_reference" for row in pet_recipe_source_directory("ferret"))
    assert pet_recipe_source_directory("fish") == []
    assert pet_recipe_source_directory("unknown") == []
    changed = pet_recipe_source_directory("dog")
    changed[0]["url"] = "changed"
    assert pet_recipe_source_directory("dog")[0]["url"].startswith("https://")
