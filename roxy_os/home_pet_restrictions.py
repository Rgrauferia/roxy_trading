"""Deterministic ingredient screening, not an allergy diagnosis or clearance."""
from __future__ import annotations

import re
import unicodedata


def normalized(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


ALLERGEN_GROUPS = {
    "pollo": ("pollo", "chicken", "poultry", "avicola"),
    "pavo": ("pavo", "turkey"),
    "res": ("res", "beef", "bovine", "ternera", "vacuno"),
    "cerdo": ("cerdo", "pork", "porcine"),
    "cordero": ("cordero", "lamb"),
    "pato": ("pato", "duck"),
    "pescado": ("pescado", "fish", "salmon", "atun", "tuna", "bacalao", "cod", "herring", "arenque"),
    "mariscos": ("marisco", "mariscos", "shellfish", "shrimp", "camaron", "camarones", "krill"),
    "huevo": ("huevo", "huevos", "egg", "eggs", "albumen"),
    "lacteos": ("lacteo", "lacteos", "leche", "milk", "dairy", "queso", "cheese", "yogur", "yogurt", "whey", "casein", "lactose", "lactosa"),
    "trigo": ("trigo", "wheat"),
    "maiz": ("maiz", "corn", "maize"),
    "soya": ("soya", "soja", "soy", "soybean", "soybeans"),
    "avena": ("avena", "oat", "oats", "oatmeal"),
    "arroz": ("arroz", "rice"),
    "guisantes": ("guisante", "guisantes", "pea", "peas", "arveja", "arvejas"),
}
_NONE = {"ninguna", "ninguna conocida", "ninguno", "none", "no known allergies", "sin alergias conocidas"}
_UNCLEAR = {"otra", "otro", "other", "no se", "no se sabe", "desconocida", "unknown", "ingrediente especifico", "sensibilidad ambiental"}
_NO_CONDITIONS = {"", "ninguna", "ninguno", "ninguna conocida", "none", "no known conditions", "sin condiciones conocidas"}


def has_medical_restrictions(pet: dict) -> bool:
    # Exact negative answers only: "ninguna salvo diabetes" is NOT clearance.
    conditions = pet.get("conditions") or []
    if not isinstance(conditions, list):
        conditions = [conditions]
    return bool(
        pet.get("current_food_kind") == "veterinary"
        or normalized(pet.get("veterinarian_instructions"))
        or any(normalized(value) not in _NO_CONDITIONS for value in conditions)
    )


def contains_term(text: str, term: str) -> bool:
    # "res" must never match "fresa", "Freshwater" or "preserved".
    return bool(term and re.search(r"(?:^| )" + re.escape(term) + r"(?: |$)", text))


def pet_restrictions(pet: dict) -> list[str]:
    return sorted({normalized(value) for value in pet.get("allergies") or []
                   if normalized(value) and normalized(value) not in _NONE})


def unclear_restrictions(pet: dict) -> bool:
    return any(value in _UNCLEAR for value in pet_restrictions(pet))


def matching_restrictions(pet: dict, ingredient_text: object) -> list[str]:
    text = normalized(ingredient_text)
    matches = []
    for restriction in pet_restrictions(pet):
        aliases = {restriction}
        for terms in ALLERGEN_GROUPS.values():
            if any(contains_term(restriction, term) for term in terms):
                aliases.update(terms)
        if any(contains_term(text, term) for term in aliases):
            matches.append(restriction)
    return matches
