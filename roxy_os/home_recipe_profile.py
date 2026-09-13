"""Private, explicit culinary preferences; no recipe or allergy-safety claims."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


RECIPE_PROFILE_SCHEMA_VERSION = 1

_CHOICES = {
    "languages": [("es", "Español"), ("en", "English")],
    "cuisine_modes": [
        ("mixed", "Mezclar cocinas"), ("origin", "La cocina de mi país"),
        ("selected", "Elegir mis cocinas"),
    ],
    "cuisines": [
        ("mexican", "Mexicana"), ("peruvian", "Peruana"),
        ("caribbean", "Caribeña"), ("central_american", "Centroamericana"),
        ("south_american", "Sudamericana"), ("spanish", "Española"),
        ("italian", "Italiana"), ("mediterranean", "Mediterránea"),
        ("middle_eastern", "Medio Oriente"), ("indian", "India"),
        ("chinese", "China"), ("japanese", "Japonesa"), ("korean", "Coreana"),
        ("thai", "Tailandesa"), ("american", "Estadounidense"), ("other", "Otra"),
    ],
    "favorite_foods": [
        ("rice", "Arroz"), ("pasta", "Pasta"), ("legumes", "Legumbres"),
        ("vegetables", "Verduras"), ("chicken", "Pollo"), ("meat", "Carne"),
        ("fish", "Pescado"), ("seafood", "Mariscos"), ("eggs", "Huevos"),
        ("soups", "Sopas"), ("salads", "Ensaladas"), ("desserts", "Postres"),
    ],
    "diets": [
        ("omnivore", "Omnívora"), ("vegetarian", "Vegetariana"),
        ("vegan", "Vegana"), ("pescatarian", "Pescetariana"),
        ("undisclosed", "Prefiero no indicarlo"),
    ],
    "allergy_statuses": [
        ("none", "No tengo alergias alimentarias conocidas"),
        ("listed", "Quiero indicar mis alergias"),
        ("undisclosed", "Prefiero no indicarlo"),
    ],
    "allergies": [
        ("milk", "Leche"), ("eggs", "Huevos"), ("fish", "Pescado"),
        ("shellfish", "Mariscos"), ("tree_nuts", "Frutos secos"),
        ("peanuts", "Maní / cacahuate"), ("wheat", "Trigo"), ("soy", "Soja"),
        ("sesame", "Sésamo"), ("other", "Otra"),
    ],
    "skills": [
        ("beginner", "Estoy empezando"), ("intermediate", "Cocino a menudo"),
        ("confident", "Tengo experiencia"), ("undisclosed", "Prefiero no indicarlo"),
    ],
}

_PROFILE_FIELDS = {
    "schema_version", "completed", "consent", "language", "country_of_origin",
    "cuisine_mode", "cuisines", "favorite_foods", "diet", "allergy_status",
    "allergies", "other_allergies", "dislikes", "max_minutes", "skill",
}


class RecipeProfileValidationError(ValueError):
    """A profile was rejected before any account data was changed."""


class RecipeProfileConflictError(ValueError):
    """The member profile changed since the caller loaded it."""


def recipe_profile_options() -> dict[str, list[dict[str, str]]]:
    return {
        name: [{"value": value, "label": label} for value, label in choices]
        for name, choices in _CHOICES.items()
    }


def _text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise RecipeProfileValidationError(f"Revisa {field}: debe ser texto de hasta {maximum} caracteres.")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        raise RecipeProfileValidationError(f"Revisa los caracteres de {field}.")
    return " ".join(value.split())


def _choice(value: Any, field: str, option: str, *, required: bool) -> str | None:
    if value is None and not required:
        return None
    allowed = {row[0] for row in _CHOICES[option]}
    if not isinstance(value, str) or value not in allowed:
        raise RecipeProfileValidationError(f"Elige una opción válida para {field}.")
    return value


def _choices(value: Any, field: str) -> list[str]:
    allowed = {row[0] for row in _CHOICES[field]}
    if not isinstance(value, list) or len(value) > len(allowed):
        raise RecipeProfileValidationError(f"Revisa la selección de {field}.")
    if any(not isinstance(item, str) or item not in allowed for item in value):
        raise RecipeProfileValidationError(f"Revisa la selección de {field}.")
    return list(dict.fromkeys(value))


def normalize_recipe_profile(value: Any) -> dict[str, Any]:
    """Validate a full replacement, preserving explicit omissions and consent.

    A draft may leave enum choices unanswered, but saving it still requires
    consent. Completion requires explicit choices; country never implies cuisine.
    """
    if not isinstance(value, dict) or set(value) - _PROFILE_FIELDS:
        raise RecipeProfileValidationError("El perfil culinario contiene campos no válidos.")
    if type(value.get("schema_version")) is not int or value["schema_version"] != RECIPE_PROFILE_SCHEMA_VERSION:
        raise RecipeProfileValidationError("La versión del perfil culinario no es compatible. Recarga la página.")
    if type(value.get("completed")) is not bool:
        raise RecipeProfileValidationError("Indica si terminaste la configuración culinaria.")
    if value.get("consent") is not True:
        raise RecipeProfileValidationError("Confirma que quieres guardar estas preferencias culinarias en tu perfil privado.")
    completed = value["completed"]
    result = {
        "schema_version": RECIPE_PROFILE_SCHEMA_VERSION,
        "completed": completed,
        "consent": True,
        "language": _choice(value.get("language"), "idioma de recetas", "languages", required=completed),
        "country_of_origin": _text(value.get("country_of_origin", ""), "país de origen", 64),
        "cuisine_mode": _choice(value.get("cuisine_mode"), "cocinas", "cuisine_modes", required=completed),
        "cuisines": _choices(value.get("cuisines", []), "cuisines"),
        "favorite_foods": _choices(value.get("favorite_foods", []), "favorite_foods"),
        "diet": _choice(value.get("diet"), "alimentación", "diets", required=completed),
        "allergy_status": _choice(value.get("allergy_status"), "alergias", "allergy_statuses", required=completed),
        "allergies": _choices(value.get("allergies", []), "allergies"),
        "other_allergies": _text(value.get("other_allergies", ""), "otras alergias", 200),
        "skill": _choice(value.get("skill"), "experiencia al cocinar", "skills", required=completed),
    }
    dislikes = value.get("dislikes", [])
    if not isinstance(dislikes, list) or len(dislikes) > 20:
        raise RecipeProfileValidationError("Puedes indicar hasta 20 alimentos que prefieres evitar.")
    result["dislikes"] = []
    for dislike in dislikes:
        normalized = _text(dislike, "alimentos que prefieres evitar", 60)
        if not normalized:
            raise RecipeProfileValidationError("Revisa los alimentos que prefieres evitar: hay una entrada vacía.")
        if normalized.casefold() not in {item.casefold() for item in result["dislikes"]}:
            result["dislikes"].append(normalized)
    minutes = value.get("max_minutes")
    if minutes is not None and (type(minutes) is not int or not 5 <= minutes <= 240):
        raise RecipeProfileValidationError("El tiempo para cocinar debe estar entre 5 y 240 minutos, o quedar sin indicar.")
    result["max_minutes"] = minutes
    if completed and result["cuisine_mode"] == "origin" and not result["country_of_origin"]:
        raise RecipeProfileValidationError("Indica tu país para elegir su cocina, o elige mezclar cocinas.")
    if completed and result["cuisine_mode"] == "selected" and not result["cuisines"]:
        raise RecipeProfileValidationError("Elige al menos una cocina o selecciona mezclar cocinas.")
    if result["allergy_status"] == "listed":
        if completed and not result["allergies"]:
            raise RecipeProfileValidationError("Indica al menos una alergia o cambia tu respuesta sobre alergias.")
        if "other" in result["allergies"]:
            if completed and not result["other_allergies"]:
                raise RecipeProfileValidationError("Describe la otra alergia que quieres guardar.")
        elif result["other_allergies"]:
            raise RecipeProfileValidationError("Marca otra alergia para guardar su descripción.")
    elif result["allergies"] or result["other_allergies"]:
        raise RecipeProfileValidationError("La respuesta sobre alergias no coincide con las alergias indicadas.")
    return deepcopy(result)


def recipe_onboarding_required(member: dict[str, Any]) -> bool:
    """Legacy members opt in; new members complete a validated private profile."""
    if member.get("recipe_onboarding_required") is not True:
        return False
    try:
        profile = normalize_recipe_profile(member.get("recipe_profile"))
    except RecipeProfileValidationError:
        return True
    return profile["completed"] is not True
