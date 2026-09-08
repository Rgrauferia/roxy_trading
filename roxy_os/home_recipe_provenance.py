"""Source provenance is independent of formatting, photos and veterinary guidance.

This module performs no network requests or writes. ``trusted_evidence`` must come
from a server-owned review record, never recipe/import/request fields. A publisher
link alone cannot certify that locally written quantities or steps are original.
The result is an additional gate; it never replaces pet/profile/ingredient gates.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import ipaddress
import json
import math
import re
from typing import Any
import unicodedata
from urllib.parse import urlsplit


_SPECIES_REFERENCES = frozenset({
    "https://www.akc.org/dog-breeds/bernese-mountain-dog/",
    "https://www.akc.org/expert-advice/nutrition/can-dogs-eat-watermelon/",
    "https://www.merckvetmanual.com/en-us/veterinary/bird-owners/choosing-and-taking-care-of-a-pet-bird/feeding-a-pet-bird",
    "https://www.merckvetmanual.com/exotic-and-laboratory-animals/rodents/hamsters",
    "https://www.merckvetmanual.com/exotic-and-laboratory-animals/guinea-pigs/housing-and-nutrition-of-guinea-pigs",
    "https://www.merckvetmanual.com/exotic-and-laboratory-animals/rabbits/nutrition-of-rabbits",
    "https://hospital.cvm.ncsu.edu/services/small-animals/nutrition/caring-for-your-pet-ferret/",
    "https://oxbowanimalhealth.com/wp-content/uploads/2023/10/Ferret-Care-Guide-Jul-2022.pdf",
    "https://vcahospitals.com/know-your-pet/feeding-ferrets",
})
_SAFETY_REFERENCES = frozenset({
    "https://www.fda.gov/animal-veterinary/animal-health-literacy/complete-and-balanced-pet-food",
    "https://www.foodsafety.gov/food-safety-charts/safe-minimum-internal-temperatures",
    "https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/meat-fish/jerky",
    "https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/food-safety-basics/leftovers-and-food-safety",
})

_SOURCE_DIRECTORY = {
    "dog": [{
        "title": "Hill's · recetas de premios para perros",
        "url": "https://www.hillspet.com/dog-care/nutrition-feeding/healthy-homemade-dog-treats",
        "publisher": "Hill's Pet Nutrition", "role": "original_recipe_source",
        "note": "Publicación del fabricante con ingredientes y pasos. Pendiente de revisión para incorporarla a Roxy.",
    }],
    "cat": [{
        "title": "Hill's · recetas de premios para gatos",
        "url": "https://www.hillspet.com/cat-care/nutrition-feeding/healthy-homemade-cat-treats",
        "publisher": "Hill's Pet Nutrition", "role": "original_recipe_source",
        "note": "Publicación del fabricante con preparaciones de su alimento. Pendiente de revisión para incorporarla a Roxy.",
    }],
    "ferret": [{
        "title": "VCA · alimentación del Ferret",
        "url": "https://vcahospitals.com/know-your-pet/feeding-ferrets",
        "publisher": "VCA Animal Hospitals", "role": "general_species_reference",
        "note": "Guía alimentaria; no contiene las ocho recetas del catálogo ni valida sus cantidades y pasos.",
    }, {
        "title": "Oxbow · cuidado del Ferret",
        "url": "https://oxbowanimalhealth.com/wp-content/uploads/2023/10/Ferret-Care-Guide-Jul-2022.pdf",
        "publisher": "Oxbow Animal Health", "role": "general_species_reference",
        "note": "Guía de cuidado y alimentación; no equivale a una receta original completa.",
    }],
}


def pet_recipe_source_directory(species: str) -> list[dict[str, Any]]:
    """Return links, not installed recipes or veterinary approval for a pet.

    No inferred species mapping: Oxbow's hay article even appears in search results
    with a ferret query parameter. That URL parameter is not dietary evidence.
    """
    rows = deepcopy(_SOURCE_DIRECTORY.get(str(species or "").strip().lower(), []))
    for row in rows:
        row.update(checked_on="2026-09-08", content_reuse_status="not_authorized",
                   imported_recipe=False, individual_pet_approved=False)
    return rows


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _plain(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()


def _source_url(value: Any) -> str:
    raw = _text(value)
    if not raw or any(ord(char) < 33 for char in raw) or "\\" in raw:
        return ""
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname or ""
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in {None, 443}:
            return ""
        if "." not in host or host.endswith((".local", ".localhost")):
            return ""
        try:
            ipaddress.ip_address(host)
            return ""
        except ValueError:
            pass
    except ValueError:
        return ""
    return raw


def recipe_content_fingerprint(recipe: dict[str, Any]) -> str:
    """Bind an editorial attestation to exactly the reviewed preparation content.

    Personal metadata is excluded so a favourite/photo change does not invalidate
    source review. Changed ingredients, measures, steps, species or claims do.
    """
    fields = (
        "title", "description", "ingredients", "steps", "servings", "yield_text",
        "pet_species", "pet_exact_terms", "pet_life_stages", "safety_class",
        "clinical_claims", "nutrition_claims", "storage_instructions", "veterinary_note",
    )
    try:
        encoded = json.dumps({key: recipe.get(key) for key in fields}, ensure_ascii=False,
                             sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        return ""
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _completeness(recipe: dict[str, Any]) -> dict[str, Any]:
    """Structural presence only. It cannot establish fidelity to an original.

    Accept one-ingredient and short originals; never pad recipes to meet counts.
    An original textual measure is preserved rather than inventing a conversion.
    """
    missing = []
    if not _text(recipe.get("title")):
        missing.append("title")
    ingredients = recipe.get("ingredients")
    if not isinstance(ingredients, list) or not ingredients:
        missing.append("ingredients")
    else:
        for index, row in enumerate(ingredients):
            if not isinstance(row, dict) or not _text(row.get("name")):
                missing.append(f"ingredients.{index}.name")
                continue
            amount = row.get("quantity")
            numeric = (isinstance(amount, (int, float)) and not isinstance(amount, bool)
                       and math.isfinite(amount) and amount > 0 and bool(_text(row.get("unit"))))
            original = bool(_text(row.get("original_measure")))
            if not numeric and not original:
                missing.append(f"ingredients.{index}.measure")
    steps = recipe.get("steps")
    if not isinstance(steps, list) or not steps:
        missing.append("steps")
    else:
        missing.extend(f"steps.{index}" for index, step in enumerate(steps) if not _text(step))
    return {"structurally_complete": not missing, "missing_fields": missing,
            "original_completeness_verified": False}


def _clinical_scope(recipe: dict[str, Any]) -> bool:
    if recipe.get("safety_class") not in {"treat", "complement"}:
        return True
    if recipe.get("clinical_claims") or recipe.get("nutrition_claims"):
        return True
    # Cautionary veterinary notes are deliberately not interpreted as positive
    # claims. They remain part of the fingerprint and need source review.
    text = _plain(" ".join(_text(recipe.get(field)) for field in ("title", "description")))
    return bool(re.search(
        r"\b(terapeutic\w*|therapeutic\w*|cura\w*|curing|cures?|tratar|tratamiento|treatment|"
        r"hipoalergen\w*|hypoallergen\w*|previene|prevents?|"
        r"insulinoma|diabet\w*|hipogluc\w*|hypoglyc\w*|renal|kidney|"
        r"dieta completa|complete diet|nutricionalmente complet\w*|nutritionally complete)\b", text))


def assess_recipe_provenance(recipe: dict[str, Any], *, trusted_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assess source/original completeness without mutating the recipe.

    A trusted record requires role, URL, publisher, original_title, reviewed_on,
    review_reference, content_sha256, species, original_recipe_verified=True and
    original_content_complete=True, scope='supplemental_treat', and
    clinical_claims_present=False (explicitly reviewed). A separate content_reuse_authorized=True plus
    rights_reference is needed to enable reuse/cooking inside Roxy. Review records
    must never be deserialized from a client's recipe or an AI response.
    """
    recipe = recipe if isinstance(recipe, dict) else {}
    evidence = trusted_evidence if isinstance(trusted_evidence, dict) else {}
    completeness = _completeness(recipe)
    fingerprint = recipe_content_fingerprint(recipe)
    issues = []
    sources = []
    raw_sources = recipe.get("sources")
    raw_sources = raw_sources if isinstance(raw_sources, list) else []
    if recipe.get("source_url"):
        raw_sources = [*raw_sources, {"url": recipe["source_url"], "title": recipe.get("source_label")}]
    for row in raw_sources:
        if not isinstance(row, dict):
            continue
        url = _source_url(row.get("url"))
        if not url:
            issues.append("invalid_source_url")
            continue
        role = ("general_species_reference" if url in _SPECIES_REFERENCES else
                "general_safety_reference" if url in _SAFETY_REFERENCES else "unverified_reference")
        sources.append({"title": _text(row.get("title")), "url": url, "role": role})

    source_url = _source_url(evidence.get("url"))
    try:
        reviewed_on = date.fromisoformat(_text(evidence.get("reviewed_on")))
        review_date_valid = reviewed_on <= date.today()
    except ValueError:
        review_date_valid = False
    species = _text(recipe.get("pet_species"))
    reviewed_species = evidence.get("species")
    species_matches = isinstance(reviewed_species, list) and bool(species) and species in reviewed_species
    original_verified = bool(
        fingerprint and evidence.get("content_sha256") == fingerprint
        and evidence.get("role") == "original_recipe_source"
        and source_url and source_url not in _SPECIES_REFERENCES | _SAFETY_REFERENCES
        and evidence.get("original_recipe_verified") is True
        and evidence.get("original_content_complete") is True
        and evidence.get("scope") == "supplemental_treat"
        and evidence.get("clinical_claims_present") is False
        and _text(evidence.get("publisher")) and _text(evidence.get("original_title"))
        and _text(evidence.get("review_reference")) and review_date_valid and species_matches
        and completeness["structurally_complete"]
    )
    completeness["original_completeness_verified"] = original_verified
    if not original_verified:
        issues.append("original_recipe_not_verified")
    if evidence and not original_verified:
        issues.append("source_review_incomplete_or_content_changed")
    rights_verified = bool(original_verified and evidence.get("content_reuse_authorized") is True
                           and _text(evidence.get("rights_reference")))
    if original_verified and not rights_verified:
        issues.append("content_reuse_not_authorized")
    clinical_scope = _clinical_scope(recipe)
    if clinical_scope:
        issues.append("clinical_or_diet_scope_requires_professional_plan")
    if not completeness["structurally_complete"]:
        issues.append("recipe_content_incomplete")
    if recipe.get("editorial_status") == "verified_veterinary_guidance" or recipe.get("vet_approved"):
        issues.append("guidance_or_badge_is_not_recipe_validation")

    generation = _text(recipe.get("generation_source"))
    local = generation == "local_recipe_catalog" or bool(recipe.get("catalog_key"))
    imported = generation.startswith("import_")
    origin = "external_original" if original_verified else "local_authored" if local else "user_import" if imported else "unknown"
    source_role = ("original_recipe_source" if original_verified else
                   "general_reference_only" if sources and all(row["role"].startswith("general_") for row in sources)
                   else "unverified_reference" if sources else "no_source")
    status = ("professional_review_required" if clinical_scope else
              "original_verified" if rights_verified else "original_link_only" if original_verified else
              "local_authored_unverified" if local else "import_unverified" if imported else "source_unverified")
    labels = {
        "professional_review_required": "Requiere un plan profesional",
        "original_verified": "Receta original verificada",
        "original_link_only": "Original localizado · reproducción pendiente",
        "local_authored_unverified": "Preparación local · original sin verificar",
        "import_unverified": "Importación · original sin verificar",
        "source_unverified": "Fuente original sin verificar",
    }
    message = ("Esta preparación requiere revisión profesional antes de ofrecerla a una mascota." if clinical_scope else
               "La receta coincide con la publicación revisada; siguen aplicándose las restricciones de cada mascota." if rights_verified else
               "La publicación original está verificada. Su reproducción en Roxy sigue pendiente." if original_verified else
               "No se ha verificado una publicación original con estos ingredientes, cantidades y pasos. Las guías generales no validan esta receta.")
    return {
        "status": status, "origin": origin, "source_role": source_role,
        "label": labels[status], "message": message, "sources": sources,
        "original_source_url": source_url if original_verified else "",
        "original_recipe_verified": original_verified,
        "can_present_as_original": original_verified and not clinical_scope,
        "content_reuse_authorized": rights_verified,
        "can_cook_from_source": rights_verified and not clinical_scope,
        "veterinary_validated": False, "individual_pet_approved": False,
        "clinical_scope": clinical_scope, "completeness": completeness,
        "issues": list(dict.fromkeys(issues)),
    }
