"""Local recipe discovery and limited text checks using private member choices.

Only fixed public search terms leave this layer. A title is not ingredient
evidence, and lack of a text match never establishes allergy compatibility.
"""

from __future__ import annotations

from copy import deepcopy
import math
import re
import unicodedata
from typing import Any

from roxy_os.home_recipe_profile import (
    RecipeProfileValidationError, normalize_recipe_profile, recipe_profile_options,
)


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _contains(text: str, term: str) -> bool:
    return bool(term and re.search(r"(?:^| )" + re.escape(term) + r"(?: |$)", text))


# Fixed source search terms are approximations, not provider cuisine metadata.
_CUISINE_SEARCH = {
    "mexican": "Mexican", "peruvian": "Peruvian", "caribbean": "Caribbean",
    "central_american": "Central American", "south_american": "South American",
    "spanish": "Spanish", "italian": "Italian", "mediterranean": "Mediterranean",
    "middle_eastern": "Middle Eastern", "indian": "Indian", "chinese": "Chinese",
    "japanese": "Japanese", "korean": "Korean", "thai": "Thai", "american": "American",
}
_FOOD_SEARCH = {
    "rice": ("rice", ""), "pasta": ("pasta", ""), "legumes": ("beans", ""),
    "vegetables": ("vegetable", ""), "chicken": ("chicken", ""), "meat": ("beef", ""),
    "fish": ("fish", ""), "seafood": ("shrimp", ""), "eggs": ("egg", ""),
    "soups": ("", "Soup"), "salads": ("", "Salad"), "desserts": ("", "Dessert"),
}
_COUNTRY_SEARCH = {
    alias: (country, label, query)
    for country, aliases, label, query in (
        ("mx", ("mexico",), "Mexicana", "Mexican"),
        ("pe", ("peru",), "Peruana", "Peruvian"),
        ("it", ("italia", "italy"), "Italiana", "Italian"),
        ("es", ("espana", "spain"), "Española", "Spanish"),
        ("in", ("india",), "India", "Indian"),
        ("cn", ("china",), "China", "Chinese"),
        ("jp", ("japon", "japan"), "Japonesa", "Japanese"),
        ("kr", ("corea del sur", "south korea"), "Coreana", "Korean"),
        ("th", ("tailandia", "thailand"), "Tailandesa", "Thai"),
        ("us", ("estados unidos", "united states", "usa"), "Estadounidense", "American"),
        ("cu", ("cuba",), "Cubana", "Cuban"),
        ("do", ("republica dominicana", "dominican republic"), "Dominicana", "Dominican"),
        ("pr", ("puerto rico",), "Puertorriqueña", "Puerto Rican"),
        ("jm", ("jamaica",), "Jamaicana", "Jamaican"),
        ("gt", ("guatemala",), "Guatemalteca", "Guatemalan"),
        ("hn", ("honduras",), "Hondureña", "Honduran"),
        ("sv", ("el salvador",), "Salvadoreña", "Salvadoran"),
        ("ni", ("nicaragua",), "Nicaragüense", "Nicaraguan"),
        ("cr", ("costa rica",), "Costarricense", "Costa Rican"),
        ("pa", ("panama",), "Panameña", "Panamanian"),
        ("co", ("colombia",), "Colombiana", "Colombian"),
        ("ve", ("venezuela",), "Venezolana", "Venezuelan"),
        ("ec", ("ecuador",), "Ecuatoriana", "Ecuadorian"),
        ("bo", ("bolivia",), "Boliviana", "Bolivian"),
        ("cl", ("chile",), "Chilena", "Chilean"),
        ("ar", ("argentina",), "Argentina", "Argentinian"),
        ("uy", ("uruguay",), "Uruguaya", "Uruguayan"),
        ("py", ("paraguay",), "Paraguaya", "Paraguayan"),
        ("br", ("brasil", "brazil"), "Brasileña", "Brazilian"),
    ) for alias in aliases
}
_DISCOVERY_NOTICE = (
    "Son búsquedas por tus elecciones, no una selección verificada por origen, dieta o alergias. "
    "La fuente tiene metadatos limitados y puede no ofrecer coincidencias. "
    "Estas búsquedas no filtran por tiempo ni nivel de experiencia."
)


def discovery_presets(profile: Any) -> dict[str, Any]:
    """Return optional public searches, never free-text dietary or country data."""
    try:
        selected = normalize_recipe_profile(profile)
    except RecipeProfileValidationError:
        return {"presets": [], "notice": "Configura tus preferencias para explorar recetas a partir de tus elecciones."}
    if not selected["completed"]:
        return {"presets": [], "notice": "Completa tus preferencias para usarlas al explorar recetas."}
    options = recipe_profile_options()
    labels = {key: {row["value"]: row["label"] for row in options[key]} for key in ("cuisines", "favorite_foods")}
    presets = []
    notice = _DISCOVERY_NOTICE
    cuisines = selected["cuisines"] if selected["cuisine_mode"] == "selected" else []
    if selected["cuisine_mode"] == "origin":
        origin = _COUNTRY_SEARCH.get(_normalized(selected["country_of_origin"]))
        if origin:
            country, label, query = origin
            presets.append({"id": "origin-" + country, "label": label, "query": query, "category": "",
                            "reason": "Por la cocina de origen que elegiste"})
        else:
            notice = "Aún no hay una búsqueda por país preparada para tu elección. Puedes elegir cocinas en Ajustes. " + notice
    for cuisine in cuisines:
        if cuisine not in _CUISINE_SEARCH:
            notice = "La opción Otra no tiene una búsqueda específica preparada. " + notice
            continue
        presets.append({
            "id": "cuisine-" + cuisine, "label": labels["cuisines"][cuisine],
            "query": _CUISINE_SEARCH[cuisine], "category": "",
            "reason": "Por una cocina que elegiste",
        })
    for food in selected["favorite_foods"]:
        query, category = _FOOD_SEARCH[food]
        presets.append({
            "id": "food-" + food, "label": labels["favorite_foods"][food],
            "query": query, "category": category, "reason": "Por un alimento que elegiste",
        })
    if not presets:
        presets = [
            {"id": "explore-" + key, "label": label, "query": "", "category": category,
             "reason": "Para explorar sabores diferentes"}
            for key, label, category in (
                ("main-dish", "Platos principales", "Main dish"),
                ("soup", "Sopas", "Soup"),
                ("salad", "Ensaladas", "Salad"),
                ("dessert", "Postres", "Dessert"),
            )
        ]
    return {"presets": presets, "notice": notice}


# These terms detect potential conflicts only. They are deliberately neither
# exhaustive nor an ingredient ontology. Generic "nut" never means tree nuts.
_ALLERGEN_TERMS = {
    "milk": ("milk", "dairy", "cream", "butter", "cheese", "yogurt", "yoghurt", "whey", "casein",
             "leche", "lacteos", "nata", "crema", "mantequilla", "queso", "yogur", "caseina"),
    "eggs": ("egg", "eggs", "albumen", "huevo", "huevos", "clara", "claras", "yema", "yemas"),
    "fish": ("fish", "salmon", "tuna", "cod", "anchovy", "anchovies", "sardine", "sardines", "trout",
             "pescado", "atun", "bacalao", "anchoa", "anchoas", "sardina", "sardinas", "trucha"),
    "shellfish": ("shellfish", "shrimp", "prawn", "prawns", "crab", "lobster", "clam", "clams",
                  "mussel", "mussels", "oyster", "oysters", "scallop", "scallops", "marisco", "mariscos",
                  "camaron", "camarones", "gamba", "gambas", "cangrejo", "langosta", "mejillon", "mejillones", "almeja", "almejas"),
    "tree_nuts": ("almond", "almonds", "walnut", "walnuts", "pecan", "pecans", "cashew", "cashews",
                  "hazelnut", "hazelnuts", "pistachio", "pistachios", "macadamia", "brazil nuts",
                  "almendra", "almendras", "nuez", "nueces", "anacardo", "anacardos", "avellana", "avellanas", "pistacho", "pistachos"),
    "peanuts": ("peanut", "peanuts", "groundnut", "groundnuts", "mani", "cacahuate", "cacahuates", "cacahuete", "cacahuetes"),
    "wheat": ("wheat", "semolina", "bulgur", "couscous", "spelt", "trigo", "semola", "cuscus", "espelta"),
    "soy": ("soy", "soya", "soybean", "soybeans", "tofu", "tempeh", "edamame", "soja"),
    "sesame": ("sesame", "tahini", "tahin", "sesamo", "ajonjoli"),
}
_MEAT_TERMS = ("meat", "chicken", "beef", "steak", "steaks", "pork", "bacon", "ham", "turkey", "lamb", "duck", "sausage", "gelatin",
               "carne", "pollo", "res", "ternera", "bistec", "bistecs", "cerdo", "tocino", "bacon", "jamon", "pavo", "cordero", "pato", "salchicha", "gelatina")
_PLANT_DAIRY_PHRASES = (
    "almond milk", "soy milk", "soya milk", "oat milk", "rice milk", "coconut milk", "coconut cream",
    "peanut butter", "almond butter", "cocoa butter", "leche de almendras", "leche de soja", "leche de soya",
    "leche de avena", "leche de arroz", "leche de coco", "crema de coco", "mantequilla de mani", "mantequilla de cacahuate",
)
_CAUTION = (
    "Cotejo limitado del texto de ingredientes. No verifica etiquetas, sustituciones ni contaminación cruzada "
    "y no certifica que la receta sea apta para alergias. Revisa la fuente y los productos concretos."
)
_SUMMARY_NOTICE = (
    "Se omiten posibles conflictos visibles en títulos y descripciones. "
    "Los resúmenes no verifican los ingredientes: las recetas restantes necesitan revisión y no están certificadas para alergias."
)
_SUMMARY_DAIRY_CLUES = ("creamy", "cheesy", "cremoso", "cremosa", "cremosos", "cremosas")
_SUMMARY_MEAT_CLUES = (
    "meatball", "meatballs", "albondiga", "albondigas", "sausages", "salchichas",
    "burger", "burgers", "hamburger", "hamburgers", "hamburguesa", "hamburguesas",
)
_SUMMARY_PLANT_MEAT_PHRASES = (
    "cauliflower steak", "cauliflower steaks", "mushroom steak", "mushroom steaks",
    "tofu steak", "tofu steaks", "eggplant steak", "eggplant steaks", "bistec de coliflor",
)
# Adjacent plant descriptors suppress only that dish phrase. A separate mention
# of bacon, beef, milk, etc. still excludes the summary for the relevant choice.
_SUMMARY_PLANT_MEAT_PHRASES += tuple(
    f"{qualifier} {dish}"
    for qualifier in ("veggie", "vegetable", "vegetarian", "vegan", "plant based",
                      "lentil", "chickpea", "black bean", "bean", "mushroom", "tofu")
    for dish in ("meatball", "meatballs", "burger", "burgers", "hamburger", "hamburgers", "sausage", "sausages")
)
_SUMMARY_PLANT_MEAT_PHRASES += tuple(
    f"{dish} {qualifier}"
    for dish in ("albondiga", "albondigas", "hamburguesa", "hamburguesas", "salchicha", "salchichas")
    for qualifier in ("vegetariana", "vegetarianas", "vegana", "veganas", "vegetal", "vegetales",
                      "de lentejas", "de garbanzo", "de garbanzos", "de frijoles", "de tofu")
)


def _summary_has_term(text: str, term: str) -> bool:
    """A stated absence is not positive evidence for excluding a summary."""
    if not term:
        return False
    for match in re.finditer(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text):
        before = text[:match.start()].split()
        after = text[match.end():].split()
        if before and before[-1] in {"no", "without", "sin"}:
            continue
        if after and after[0] in {"free", "libre"}:
            continue
        return True
    return False


def _without_phrases(text: str, phrases: tuple[str, ...]) -> str:
    for phrase in phrases:
        text = re.sub(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", " ", text)
    return " ".join(text.split())


def screen_recipe_summaries(profile: Any, rows: Any) -> dict[str, Any]:
    """Only exclude summary clues; never approve or relabel remaining recipes.

    The caller retains the provider's total, offsets and next page. No details
    are fetched here, and no ingredients or origin claims are invented.
    """
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("La fuente no devolvió una lista válida de resúmenes.")
    copied = deepcopy(rows)
    try:
        selected = normalize_recipe_profile(profile)
    except RecipeProfileValidationError:
        return {"rows": copied, "hidden_in_page": 0, "notice": "No hay preferencias completas para filtrar estos resúmenes. " + _SUMMARY_NOTICE}
    if not selected["completed"]:
        return {"rows": copied, "hidden_in_page": 0, "notice": "Completa tus preferencias para filtrar estos resúmenes. " + _SUMMARY_NOTICE}
    diet = selected["diet"]
    groups = []
    for allergen in selected["allergies"]:
        terms = (_normalized(selected["other_allergies"]),) if allergen == "other" else _ALLERGEN_TERMS[allergen]
        groups.append(("dairy" if allergen == "milk" else "general", terms))
        if allergen == "milk":
            groups.append(("dairy", _SUMMARY_DAIRY_CLUES))
    if diet in {"vegetarian", "vegan", "pescatarian"}:
        groups.append(("meat", _MEAT_TERMS + _SUMMARY_MEAT_CLUES))
    if diet in {"vegetarian", "vegan"}:
        groups.append(("general", _ALLERGEN_TERMS["fish"] + _ALLERGEN_TERMS["shellfish"]))
    if diet == "vegan":
        groups.extend((
            ("dairy", _ALLERGEN_TERMS["milk"] + _SUMMARY_DAIRY_CLUES),
            ("general", _ALLERGEN_TERMS["eggs"] + ("honey", "miel")),
        ))
    if selected["dislikes"]:
        groups.append(("general", tuple(_normalized(value) for value in selected["dislikes"])))
    kept = []
    for row in copied:
        # Validate only text used for this negative screen. Missing summaries
        # remain visible with the same universal review notice.
        text = _normalized(" ".join(row.get(key, "") for key in ("title", "description") if isinstance(row.get(key), str)))
        haystacks = {
            "general": text,
            "dairy": _without_phrases(text, _PLANT_DAIRY_PHRASES),
            "meat": _without_phrases(text, _SUMMARY_PLANT_MEAT_PHRASES),
        }
        if not any(_summary_has_term(haystacks[kind], term) for kind, terms in groups for term in terms):
            kept.append(row)
    return {"rows": kept, "hidden_in_page": len(copied) - len(kept), "notice": _SUMMARY_NOTICE}


def assess_recipe_fit(
    profile: Any, ingredient_lines: Any, title: str = "", duration_minutes: Any = None,
) -> dict[str, Any]:
    """Flag evidence of a conflict, keep unknowns explicit, never return 'safe'."""
    try:
        selected = normalize_recipe_profile(profile)
    except RecipeProfileValidationError:
        return {"status": "needs_review", "conflicts": [], "caution": "No hay preferencias completas para este cotejo. " + _CAUTION}
    if not selected["completed"]:
        return {"status": "needs_review", "conflicts": [], "caution": "Las preferencias aún están incompletas. " + _CAUTION}
    # The title is intentionally not evidence of an ingredient's presence/absence.
    usable = isinstance(ingredient_lines, list) and bool(ingredient_lines) and all(
        isinstance(line, str) and 0 < len(line.strip()) <= 4000 for line in ingredient_lines
    ) and len(ingredient_lines) <= 200
    if not usable:
        return {"status": "needs_review", "conflicts": [], "caution": "No hay una lista de ingredientes suficiente para cotejar. " + _CAUTION}
    lines = [_normalized(line) for line in ingredient_lines]
    dairy_lines = list(lines)
    for index, line in enumerate(dairy_lines):
        for phrase in _PLANT_DAIRY_PHRASES:
            line = re.sub(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", " ", line)
        dairy_lines[index] = " ".join(line.split())
    conflicts = []
    labels = {row["value"]: row["label"] for row in recipe_profile_options()["allergies"]}
    for allergen in selected["allergies"]:
        terms = (_normalized(selected["other_allergies"]),) if allergen == "other" else _ALLERGEN_TERMS[allergen]
        haystacks = dairy_lines if allergen == "milk" else lines
        if any(_contains(line, term) for line in haystacks for term in terms):
            label = selected["other_allergies"] if allergen == "other" else labels[allergen]
            conflicts.append("Posible coincidencia con la alergia indicada: " + label + ".")
    diet = selected["diet"]
    excluded_groups = []
    if diet in {"vegetarian", "vegan", "pescatarian"}:
        excluded_groups.append(("carne", _MEAT_TERMS, lines))
    if diet in {"vegetarian", "vegan"}:
        excluded_groups.extend((
            ("pescado", _ALLERGEN_TERMS["fish"], lines),
            ("mariscos", _ALLERGEN_TERMS["shellfish"], lines),
        ))
    if diet == "vegan":
        excluded_groups.extend((
            ("lácteos", _ALLERGEN_TERMS["milk"], dairy_lines),
            ("huevos", _ALLERGEN_TERMS["eggs"], lines),
            ("miel", ("honey", "miel"), lines),
        ))
    for label, terms, haystacks in excluded_groups:
        if any(_contains(line, term) for line in haystacks for term in terms):
            conflicts.append("Posible conflicto con tu alimentación: " + label + ".")
    for dislike in selected["dislikes"]:
        if any(_contains(line, _normalized(dislike)) for line in lines):
            conflicts.append("Incluye un alimento que prefieres evitar: " + dislike + ".")
    maximum = selected["max_minutes"]
    known_duration = type(duration_minutes) in (int, float) and math.isfinite(duration_minutes) and 0 < duration_minutes <= 1440
    if maximum is not None and known_duration and duration_minutes > maximum:
        conflicts.append("El tiempo indicado en la fuente supera los minutos que elegiste.")
    if conflicts:
        status = "conflict"
    elif (selected["allergy_status"] != "none" or diet != "omnivore" or selected["dislikes"]
          or (maximum is not None and not known_duration)):
        status = "needs_review"
    else:
        status = "unrestricted"
    caution = _CAUTION
    if selected["allergy_status"] == "undisclosed":
        caution = "No has indicado información sobre alergias. " + caution
    if maximum is not None and not known_duration:
        caution = "No se conoce el tiempo total de esta receta. " + caution
    return {"status": status, "conflicts": conflicts, "caution": caution}
