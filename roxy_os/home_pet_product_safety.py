"""Conservative product gates. Labels cannot certify absence of cross-contact."""
from __future__ import annotations

import hashlib

from roxy_os.home_pet_restrictions import has_medical_restrictions, matching_restrictions, normalized, pet_restrictions


# Facts transcribed from the full manufacturer ingredient panels on 2026-09-06.
# Deliberately retain ambiguous sources (natural flavor, animal blood, gelatin).
# These are screening records, NEVER a declaration that an allergic pet can eat it.
INGREDIENT_REVIEWS = {
    ("mazuri", "ferret diet"): {
        "source_url": "https://mazuri.com/products/mazuri-ferret-diet",
        "ingredients": "chicken meal; rice flour; poultry fat; animal blood cells; chicken; egg; porcine meat and bone meal; fish meal; beet pulp; yeast; phosphoric acid; salt; poultry flavor; fish oil; calcium propionate; taurine; choline chloride; lactose; pyridoxine; thiamine; citric acid; methionine; Lactobacillus acidophilus; rosemary; Lactobacillus casei; tocopherols; Bifidobacterium thermophilum; vitamin A; zinc; lysine; vitamin D3; Enterococcus faecium; magnesium; yucca; vitamin K; folic acid; vitamin B12; ascorbic acid; calcium pantothenate; riboflavin; manganese; calcium carbonate; niacin; iron; copper; cobalt; vitamin E; calcium iodate; sodium selenite; biotin",
        "highlights": "Pollo, huevo, cerdo, pescado y lactosa",
    },
    ("oxbow", "essentials ferret food"): {
        "source_url": "https://oxbowanimalhealth.com/product/essentials-ferret-food/",
        "ingredients": "chicken meal; chicken; chicken fat; egg; gelatin; rice flour; flaxseed; cassava; beet pulp; lysine; chicken liver flavor; fish oil; potassium chloride; taurine; salt; citric acid; vinegar; methionine; choline chloride; yeast; inulin; iron; zinc; rice hulls; carnitine; vitamin E; manganese; tocopherols; yucca; copper; niacin; thiamine; vitamin C; mineral oil; vitamin K; biotin; pyridoxine; sodium selenite; riboflavin; calcium pantothenate; vitamin A; vitamin B12; folic acid; vitamin D3; cobalt carbonate; calcium iodate; rosemary",
        "highlights": "Pollo, huevo, pescado y gelatina de origen no especificado",
    },
    ("wysong", "ferret epigen 90"): {
        "source_url": "https://www.wysong.net/products/ferret-epigen-90",
        "ingredients": "chicken meal; organic chicken; meat protein isolate; chicken fat; tocopherols; gelatin; natural flavor; coconut oil; meat broth; chia; calcium carbonate; taurine; calcium propionate; choline chloride; citric acid; apple fiber; fish oil; yeast extract; inulin; rosemary; yeast culture; potassium chloride; zinc; iron; copper; manganese; sodium selenite; calcium iodate; vitamin C; vitamin E; niacin; calcium pantothenate; vitamin A; thiamine; pyridoxine; riboflavin; vitamin D3; biotin; vitamin B12; folic acid; Aspergillus oryzae; Enterococcus faecium; Lactobacillus casei; Lactobacillus acidophilus; Bacillus subtilis; Lactobacillus plantarum; Lactobacillus lactis",
        "highlights": "Pollo y pescado; también carnes y aromas de origen no especificado",
    },
    ("royal canin", "large puppy dry"): {
        "source_url": "https://www.royalcanin.com/us/dogs/products/retail-products/large-puppy-3006",
        "ingredients": "chicken by product meal; corn; wheat; chicken fat; wheat gluten; rice; natural flavors; rice flour; beet pulp; corn gluten; monocalcium phosphate; sodium aluminosilicate; vegetable oil; salt; calcium carbonate; potassium chloride; psyllium; pea fiber; fish oil; taurine; fructooligosaccharides; choline chloride; yeast; microalgae oil; methionine; vitamin E; vitamin C; biotin; calcium pantothenate; vitamin A; niacin; folic acid; pyridoxine; vitamin B12; thiamine; vitamin D3; riboflavin; zinc; manganese; iron; copper; sodium selenite; calcium iodate; marigold; glucosamine; yucca; chondroitin; carotene; rosemary; tocopherols; citric acid",
        "highlights": "Pollo, maíz, trigo y pescado",
    },
    ("hill s science diet", "puppy large breed chicken brown rice"): {
        "source_url": "https://www.hillspet.com/dog-food/science-diet-puppy-large-breed-dry",
        "ingredients": "chicken; brown rice; oats; chicken meal; barley; chicken fat; pea protein; rice; wheat; soybean meal; corn; chicken liver flavor; pecan shells; lactic acid; pork liver flavor; dicalcium phosphate; flaxseed; beet pulp; fish oil; iodized salt; citrus pulp; potassium chloride; choline chloride; cranberries; calcium carbonate; vitamin E; vitamin C; niacin; thiamine; vitamin A; calcium pantothenate; riboflavin; biotin; vitamin B12; pyridoxine; folic acid; vitamin D3; methionine; threonine; taurine; iron; zinc; copper; manganese; calcium iodate; sodium selenite; tryptophan; tocopherols; natural flavors; carnitine; beta carotene",
        "highlights": "Pollo, avena, trigo, soya, maíz, cerdo y pescado",
    },
}

_EQUIPMENT_CATEGORIES = {
    "cuidado del doble manto", "cuidado del manto", "cepillado del manto", "comedero interactivo",
    "paseo diario", "arnes para paseo", "paseo", "ejercicio", "transporte", "control del entorno",
    "control del agua", "vigilancia del agua", "descanso y enriquecimiento", "temperatura del agua",
    "pruebas del agua", "monitoreo de habitat", "temperatura", "microclima", "iluminacion uvb",
    "higiene del habitat", "seguimiento de peso", "alimentacion segura", "arnes especifico",
    "comedero resistente", "agua y rutina", "hidratacion",
}
_EQUIPMENT_PRODUCTS = {
    ("kong", "classic"), ("kong", "classic x large"), ("kong", "connects window teaser"),
    ("catit", "senses 2 0 food tree"), ("niteangel", "multi chamber hamster house"),
    ("midwest homes for pets", "ferret nation single unit"),
    ("jolly pets", "push n play ball"), ("pig gear", "snuffle ball"),
}


def product_id(species: str, product: dict) -> str:
    identity = "|".join((species, normalized(product.get("brand")), normalized(product.get("name"))))
    return "pet-product-" + hashlib.sha256(identity.encode()).hexdigest()[:20]


def product_safety(pet: dict, product: dict) -> dict:
    brand, name = normalized(product.get("brand")), normalized(product.get("name"))
    category = normalized(product.get("category"))
    review = INGREDIENT_REVIEWS.get((brand, name))
    equipment = category in _EQUIPMENT_CATEGORIES or (brand, name) in _EQUIPMENT_PRODUCTS
    # Unknown categories, edible enrichment, substrates, water treatments, shampoos
    # and oral products all fail closed for a profile with a restriction.
    if review:
        equipment = False
    restrictions = pet_restrictions(pet)
    matches = matching_restrictions(pet, " ".join((name, (review or {}).get("ingredients", ""))))
    has_diet_restriction = has_medical_restrictions(pet)
    blocked = bool(not equipment and (restrictions or has_diet_restriction))
    if matches:
        status = "ingredient_conflict"
        blocked = True
        message = "No añadir: hay ingredientes o sabores relacionados con una restricción guardada (" + ", ".join(matches) + ")."
    elif blocked:
        status = "professional_review_required"
        message = "No podemos confirmar su compatibilidad con las restricciones de esta mascota. Revisa la fórmula completa y posible contaminación cruzada con su veterinario antes de añadirlo."
    elif equipment:
        status = "equipment"
        message = "Revisa materiales, medidas y uso. Esta selección no certifica ausencia de alérgenos."
    else:
        status = "label_review_required"
        message = "Antes de ofrecerlo, confirma la fórmula, etapa, ración y etiqueta del envase. No tener alergias registradas no equivale a estar libre de alergias."
    return {
        "status": status, "cart_blocked": blocked, "matched_restrictions": matches,
        "message": message,
        "ingredient_review": ({"checked_on": "2026-09-06", "source_url": review["source_url"],
                               "highlights": review["highlights"], "scope": "manufacturer_panel_screening_not_allergy_clearance"}
                              if review else None),
    }
