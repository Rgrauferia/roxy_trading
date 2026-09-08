"""Display capabilities derived from the actual pet and its reviewed shelf.

Never infer that every species eats homemade treats. Canonical IDs and saved
profiles remain unchanged; Ferret is a presentation preference, not a new taxon.
"""
from __future__ import annotations

import re
from typing import Any

from roxy_os.home_pet_recipe_safety import check_import_profile
from roxy_os.home_pet_habitats import bird_diet_group


def pet_recipe_section_supported(pet: dict[str, Any]) -> bool:
    """Navigation is not permission to cook: profile restrictions are separate.

    A missing age or a medical restriction should explain why the shelf is
    paused, not make an existing ferret's entire recipe section disappear.
    Specialist species still have feeding information instead of a recipe tab.
    """
    species = pet.get("species")
    return species in {"dog", "cat", "ferret", "rabbit", "guinea_pig", "hamster"} or (
        species == "bird" and bird_diet_group(pet) in {"parrot", "canary"}
    )


def ferret_display_text(value: str) -> str:
    return re.sub(r"\bhur[oó]n(?:es)?\b", lambda match: "ferrets" if match[0].lower().endswith("es") else "Ferret", value, flags=re.IGNORECASE)


def pet_display_copy(pet: dict, value: Any) -> Any:
    """Normalize derived copy only, never persisted identity, artwork keys or URLs."""
    if pet.get("species") != "ferret":
        return value
    copy_fields = {"text", "intro", "source_label", "display_name", "characteristics", "common_health",
                   "feeding", "frequency", "fun_fact", "reason", "profile_label", "veterinary_note", "personalization_reason"}
    if isinstance(value, list):
        return [pet_display_copy(pet, item) for item in value]
    if isinstance(value, dict):
        return {key: ferret_display_text(item) if key in copy_fields and isinstance(item, str)
                else pet_display_copy(pet, item) if isinstance(item, (dict, list)) else item
                for key, item in value.items()}
    return value


def pet_capabilities(pet: dict[str, Any], recipes: list[dict[str, Any]]) -> dict[str, Any]:
    section_supported = pet_recipe_section_supported(pet)
    try:
        check_import_profile(pet)
        eligible, reason = True, ""
    except ValueError as exc:
        eligible, reason = False, str(exc)
    preparations = [row for row in recipes if row.get("safety_class") in {"treat", "complement"}
                    and row.get("pet_species") == pet.get("species")
                    and str(row.get("pet_id")) == str(pet.get("id"))]
    available = eligible and bool(preparations)
    title = "Premios y complementos ocasionales" if available else "Revisa su perfil antes de preparar"
    if eligible and not available:
        reason = "No hay preparaciones revisadas compatibles con los datos de este perfil. Conserva su alimentación habitual; los cuidados están en Información."
        title = "No hay preparaciones compatibles por ahora"
    if available and pet.get("species") == "ferret":
        reason = "Para un Ferret, estas preparaciones son premios ocasionales, no una dieta completa. Mantén su alimento habitual y confirma la cantidad individual con su veterinario."
    return {
        "recipes": available,
        "recipe_tab": section_supported,
        "recipe_import": available,
        "recipe_count": len(preparations) if available else 0,
        "recipe_notice": reason,
        "recipe_notice_title": title,
        "recipe_status": "available" if available else "unsupported" if not section_supported else "profile_review_required" if not eligible else "no_matches",
        "recipe_source": {"label": "NC State Veterinary Hospital · alimentación del Ferret", "url": "https://hospital.cvm.ncsu.edu/services/small-animals/nutrition/caring-for-your-pet-ferret/"} if pet.get("species") == "ferret" else None,
        "display_species": "Ferret" if pet.get("species") == "ferret" else "",
        "tabs": ["care", "medical"] + (["recipes"] if section_supported else []) + ["products"],
    }
