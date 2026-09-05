"""Conservative import gates in addition to AI review, never veterinary certification."""
from __future__ import annotations

from roxy_os.home_pet_habitats import identity, bird_diet_group


def resolve_pet(snapshot: dict, pet_id: str) -> dict:
    pet = next((row for row in snapshot.get("pets", []) if row.get("id") == pet_id), None)
    if not pet:
        raise ValueError("Selecciona una mascota guardada de este hogar antes de importar.")
    return pet


def pet_import_context(pet: dict) -> dict:
    # No household profile, addresses, photos, documents, or other pets.
    return {key: pet.get(key) for key in (
        "name", "species", "exact_species", "breed", "life_stage", "age_years", "weight_kg",
        "allergies", "conditions", "current_food", "current_food_kind", "veterinarian_instructions",
    )}


def check_import_profile(pet: dict) -> None:
    species = pet.get("species")
    if species not in {"dog", "cat", "ferret", "rabbit", "guinea_pig", "hamster", "bird"}:
        raise ValueError("Para esta especie, revisa Alimentación y cuidados en Información. Roxy no convierte un protocolo de cuidado en una receta casera.")
    if pet.get("life_stage") in {None, "unknown", "baby"}:
        raise ValueError("Confirma su etapa de vida. No importamos preparaciones para crías sin un plan profesional.")
    if species == "bird" and (bird_diet_group(pet) not in {"parrot", "canary"} or ((pet.get("habitat_observations") or {}).get("values") or {}).get("weaned") == "No"):
        raise ValueError("Esta ave necesita un plan específico revisado por un veterinario aviar; no se aplicará una receta de otra especie.")
    if any(not identity(value).startswith("ninguna") for value in pet.get("conditions") or []) or pet.get("current_food_kind") == "veterinary" or pet.get("veterinarian_instructions"):
        raise ValueError("Hay una condición o indicación veterinaria guardada. Conserva la publicación como referencia y consulta antes de cambiar su alimentación; Roxy no reemplazará ese plan.")


def validate_pet_import(recipe: dict, pet: dict) -> dict:
    check_import_profile(pet)
    if recipe.get("safety_class") not in {"treat", "complement"}:
        raise ValueError("Solo se pueden importar premios o complementos, no dietas completas, tratamientos ni guías de cuidados.")
    # Only ingredients already covered by the curated species shelf are accepted.
    # Similar names do not count as evidence of equivalent safety.
    from roxy_os.home_recipe_fallback import personalized_pet_recipe_catalog
    allowed = {identity(item["name"]) for row in personalized_pet_recipe_catalog(pet, {})
               for item in row.get("ingredients", [])}
    ingredients = recipe.get("ingredients") or []
    if not isinstance(ingredients, list) or not ingredients or not isinstance(recipe.get("steps"), list) or not recipe["steps"]:
        raise ValueError("Faltan ingredientes o pasos completos. Añade la receta escrita o una captura legible.")
    if any(not isinstance(step, str) or not step.strip() for step in recipe["steps"]):
        raise ValueError("Cada paso debe contener una instrucción escrita.")
    for ingredient in ingredients:
        if not isinstance(ingredient, dict):
            raise ValueError("Cada ingrediente debe indicar nombre y cantidad.")
        name = identity(ingredient.get("name"))
        if name not in allowed:
            raise ValueError("Un ingrediente no tiene una equivalencia revisada para esta mascota. Roxy no lo añadirá por semejanza: pide a su veterinario confirmar la receta.")
    result = dict(recipe)
    result.update(audience="pet", pet_id=pet["id"], pet_species=pet["species"], pet_name=pet["name"],
                  editorial_status="user_reviewed_import", content_kind="recipe")
    result["veterinary_note"] = "Premio o complemento ocasional; no sustituye su alimento completo. Importación revisada por el usuario, no certificada por un veterinario. Confirma la cantidad individual y cualquier cambio de salud antes de ofrecerla."
    return result
