from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any


ACTION_LIBRARY_VERSION = 1


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.encode("ascii", "ignore").decode("ascii").lower()).split())


@dataclass(frozen=True)
class RoxyActionClip:
    key: str
    label: str
    family: str
    direction: str


def _clip(key: str, label: str, family: str, direction: str) -> RoxyActionClip:
    return RoxyActionClip(key=key, label=label, family=family, direction=direction)


# This is the shared, commercial-safe production manifest. Each entry becomes
# one approved clip and can then be reused by every recipe and household.
ROXY_ACTION_CLIPS: tuple[RoxyActionClip, ...] = (
    _clip("mix_dry", "Mezclar ingredientes secos", "cooking", "stir neutral dry ingredients together in a large bowl"),
    _clip("mix_wet", "Mezclar ingredientes húmedos", "cooking", "stir neutral wet ingredients together in a large bowl"),
    _clip("fold_batter", "Integrar con movimientos envolventes", "cooking", "fold a light batter gently with a silicone spatula"),
    _clip("whisk_eggs", "Batir huevos", "cooking", "whisk eggs in a bowl until evenly combined"),
    _clip("whisk_batter", "Batir una mezcla", "cooking", "whisk a neutral batter until smooth"),
    _clip("beat_cream", "Batir crema", "dessert", "beat cream in a chilled bowl until it thickens"),
    _clip("knead_dough", "Amasar", "baking", "fold, press, and turn bread dough repeatedly on a work surface"),
    _clip("roll_dough", "Estirar masa", "baking", "roll dough evenly with a wooden rolling pin"),
    _clip("shape_dough", "Dar forma a la masa", "baking", "shape dough into a smooth loaf with both hands"),
    _clip("rest_dough", "Dejar reposar la masa", "baking", "cover a bowl of dough and reveal it visibly risen"),
    _clip("flour_surface", "Enharinar la superficie", "baking", "dust a clean work surface lightly and evenly with flour"),
    _clip("sift_dry", "Tamizar ingredientes", "baking", "sift neutral dry ingredients into a clean bowl"),
    _clip("pour_liquid_bowl", "Verter líquido", "cooking", "pour a clear neutral liquid slowly into a mixing bowl"),
    _clip("add_dry_bowl", "Añadir ingrediente seco", "cooking", "add a measured neutral dry ingredient into a mixing bowl"),
    _clip("crack_eggs", "Cascar huevos", "cooking", "crack eggs cleanly into a small bowl and check for shell"),
    _clip("cut_dice", "Cortar en cubos", "cooking", "dice a neutral vegetable safely on a cutting board"),
    _clip("cut_slice", "Cortar en rodajas", "cooking", "slice a neutral vegetable evenly on a cutting board"),
    _clip("chop_herbs", "Picar hierbas", "cooking", "finely chop fresh herbs with a safe rocking motion"),
    _clip("mince_garlic", "Picar ajo", "cooking", "mince peeled garlic finely on a cutting board"),
    _clip("peel_produce", "Pelar frutas o vegetales", "cooking", "peel fresh produce safely over a clean work surface"),
    _clip("wash_produce", "Lavar frutas o vegetales", "cooking", "wash fresh produce thoroughly under running water"),
    _clip("grate_ingredient", "Rallar", "cooking", "grate a neutral firm ingredient safely with a box grater"),
    _clip("squeeze_citrus", "Exprimir cítricos", "cooking", "squeeze fresh citrus with a handheld press"),
    _clip("mash_food", "Triturar o machacar", "cooking", "mash a soft cooked ingredient until evenly textured"),
    _clip("blend_food", "Licuar alimentos", "cooking", "secure a blender lid and blend ingredients until smooth"),
    _clip("process_food", "Procesar alimentos", "cooking", "pulse ingredients safely in a food processor"),
    _clip("boil_water", "Hervir agua", "cooking", "bring water to a clear rolling boil in a pot"),
    _clip("simmer_pot", "Cocinar a fuego lento", "cooking", "stir a gently simmering pot with visible small bubbles"),
    _clip("saute_pan", "Sofreír", "cooking", "saute chopped ingredients in a pan while stirring continuously"),
    _clip("fry_shallow", "Freír", "cooking", "shallow fry food safely and turn it once with tongs"),
    _clip("sear_food", "Sellar o dorar", "cooking", "sear food in a hot pan until the surface browns"),
    _clip("stir_pot", "Revolver una olla", "cooking", "stir a pot steadily while the mixture changes texture"),
    _clip("drain_pasta", "Escurrir pasta", "cooking", "drain cooked pasta safely into a colander over a sink"),
    _clip("strain_sauce", "Colar una salsa", "cooking", "strain a smooth sauce through a fine mesh sieve"),
    _clip("bake_insert", "Introducir en el horno", "baking", "use oven mitts to place a prepared tray into an open oven"),
    _clip("bake_remove", "Retirar del horno", "baking", "use oven mitts to remove a browned baked item from the oven"),
    _clip("check_doneness", "Comprobar cocción", "cooking", "check doneness safely with an appropriate clean utensil"),
    _clip("cool_rack", "Dejar enfriar", "baking", "transfer a baked item carefully onto a cooling rack"),
    _clip("plate_food", "Emplatar", "cooking", "arrange a finished portion neatly on a clean plate"),
    _clip("garnish_food", "Decorar un plato", "cooking", "add a simple edible garnish to a plated dish"),
    _clip("melt_chocolate", "Derretir chocolate", "dessert", "melt chocolate gently while stirring until glossy"),
    _clip("cream_butter_sugar", "Cremar mantequilla y azúcar", "dessert", "beat butter and sugar until pale and fluffy"),
    _clip("pipe_frosting", "Aplicar crema con manga", "dessert", "pipe frosting neatly with a pastry bag"),
    _clip("spread_frosting", "Cubrir con crema", "dessert", "spread frosting evenly over a cake with an offset spatula"),
    _clip("decorate_dessert", "Decorar un postre", "dessert", "finish a dessert with a restrained edible decoration"),
    _clip("portion_dough", "Porcionar masa", "dessert", "divide dough into even portions on a tray"),
    _clip("scoop_icecream", "Servir helado", "dessert", "scoop ice cream cleanly into a dessert bowl"),
    _clip("caramelize_top", "Caramelizar la superficie", "dessert", "caramelize a dessert surface carefully with a kitchen torch"),
    _clip("add_ice", "Añadir hielo", "drinks", "add clean ice cubes to a serving glass"),
    _clip("measure_spirit", "Medir bebida", "drinks", "measure a clear beverage accurately with a jigger"),
    _clip("pour_drink", "Verter una bebida", "drinks", "pour a beverage smoothly into a serving glass"),
    _clip("muddle_drink", "Macerar", "drinks", "muddle citrus and herbs gently in a sturdy glass"),
    _clip("shake_cocktail", "Agitar coctelera", "drinks", "seal and shake a cocktail shaker with both hands"),
    _clip("stir_cocktail", "Mezclar un cóctel", "drinks", "stir a chilled drink smoothly in a mixing glass"),
    _clip("strain_cocktail", "Colar un cóctel", "drinks", "strain a mixed drink cleanly into a serving glass"),
    _clip("blend_drink", "Licuar una bebida", "drinks", "blend a cold beverage until evenly smooth"),
    _clip("rim_glass", "Preparar el borde de la copa", "drinks", "moisten and coat the rim of a glass evenly"),
    _clip("garnish_drink", "Decorar una bebida", "drinks", "add a simple fresh garnish to a prepared drink"),
    _clip("serve_hot_drink", "Servir bebida caliente", "drinks", "pour a hot beverage carefully into a heat-safe cup"),
    _clip("serve_cold_drink", "Servir bebida fría", "drinks", "present a finished cold beverage on a clean counter"),
)

ACTION_BY_KEY = {clip.key: clip for clip in ROXY_ACTION_CLIPS}


def action_catalog() -> list[dict[str, str]]:
    return [
        {"key": clip.key, "label": clip.label, "family": clip.family, "direction": clip.direction}
        for clip in ROXY_ACTION_CLIPS
    ]


def classify_recipe_step(step: Any, *, recipe_kind: Any = "") -> str:
    text = _normalize(step)
    kind = _normalize(recipe_kind)
    is_drink = any(word in f"{kind} {text}" for word in ("bebida", "drink", "cocktail", "coctel", "mojito", "margarita"))
    rules = (
        ("rim_glass", ("borde de la copa", "escarcha", "rim ")),
        ("muddle_drink", ("macera", "macerar", "muddle")),
        ("shake_cocktail", ("coctelera", "agita", "shake")),
        ("strain_cocktail", ("cuela en la copa", "colar el coctel", "strain")),
        ("stir_cocktail", ("mezcla en un vaso", "vaso mezclador")),
        ("add_ice", ("anade hielo", "agrega hielo", "cubos de hielo")),
        ("measure_spirit", ("mide el ron", "mide el vodka", "mide el whisky", "jigger")),
        ("garnish_drink", ("decora la copa", "adorna la bebida", "garnish")),
        ("blend_drink", ("licua la bebida", "licua con hielo", "frozen")),
        ("serve_hot_drink", ("sirve caliente", "taza caliente")),
        ("knead_dough", ("amasa", "amasar")),
        ("roll_dough", ("estira la masa", "rodillo")),
        ("shape_dough", ("forma el pan", "da forma", "bolea")),
        ("rest_dough", ("deja reposar", "dejar reposar", "deja crecer", "ferment", "duplica", "deja levar")),
        ("flour_surface", ("enharina", "espolvorea harina")),
        ("sift_dry", ("tamiza", "cierne")),
        ("crack_eggs", ("casca", "rompe los huevos")),
        ("whisk_eggs", ("bate los huevos", "batir los huevos")),
        ("beat_cream", ("bate la crema", "monta la crema", "nata montada")),
        ("fold_batter", ("movimientos envolventes", "integra suavemente")),
        ("cut_dice", ("corta en cubos", "corta en dados")),
        ("cut_slice", ("corta en rodajas", "rebana", "lamina")),
        ("chop_herbs", ("pica las hierbas", "pica el cilantro", "pica el perejil")),
        ("mince_garlic", ("pica el ajo", "ajo picado")),
        ("peel_produce", ("pela ", "pelar ")),
        ("wash_produce", ("lava ", "enjuaga ")),
        ("grate_ingredient", ("ralla ", "rallar ")),
        ("squeeze_citrus", ("exprime", "exprimir")),
        ("mash_food", ("machaca", "tritura", "haz pure")),
        ("process_food", ("procesador", "procesa")),
        ("boil_water", ("hierve el agua", "agua hirviendo")),
        ("simmer_pot", ("fuego lento", "cocina lentamente", "hervor suave")),
        ("saute_pan", ("sofrie", "saltea")),
        ("fry_shallow", ("frie", "freir")),
        ("sear_food", ("sella ", "dora la carne")),
        ("drain_pasta", ("escurre", "colador de pasta")),
        ("strain_sauce", ("cuela la salsa", "pasa por un colador")),
        ("bake_insert", ("mete al horno", "introduce en el horno", "hornea")),
        ("bake_remove", ("retira del horno", "saca del horno")),
        ("check_doneness", ("comprueba la coccion", "palillo salga limpio")),
        ("cool_rack", ("deja enfriar", "rejilla")),
        ("melt_chocolate", ("derrite el chocolate", "funde el chocolate")),
        ("cream_butter_sugar", ("crema la mantequilla", "bate mantequilla y azucar")),
        ("pipe_frosting", ("manga pastelera", "aplica la crema")),
        ("spread_frosting", ("cubre con crema", "extiende el glaseado")),
        ("portion_dough", ("porciona la masa", "divide la masa")),
        ("scoop_icecream", ("bola de helado", "sirve el helado")),
        ("caramelize_top", ("carameliza", "soplete")),
        ("decorate_dessert", ("decora el postre", "decora el pastel")),
        ("garnish_food", ("decora el plato", "adorna el plato")),
        ("plate_food", ("emplata", "sirve en un plato")),
        ("pour_liquid_bowl", ("vierte el agua", "vierte la leche", "anade el aceite", "agrega el aceite")),
        ("add_dry_bowl", ("anade la harina", "agrega la harina", "incorpora el azucar", "agrega la sal")),
        ("whisk_batter", ("bate ", "batir ")),
        ("mix_dry", ("mezcla los ingredientes secos", "mezcla la harina")),
        ("mix_wet", ("mezcla los ingredientes", "revuelve", "combina")),
        ("stir_pot", ("remueve", "revolver", "mezcla en la olla")),
        ("blend_food", ("licua", "en la licuadora")),
    )
    for key, needles in rules:
        if any(needle in text for needle in needles):
            return key
    if is_drink:
        return "pour_drink" if any(word in text for word in ("sirve", "vierte", "anade", "agrega")) else "serve_cold_drink"
    if any(word in kind for word in ("postre", "dessert", "dulce")):
        return "decorate_dessert"
    return "mix_wet"


def action_prompt(action_key: str) -> str:
    clip = ACTION_BY_KEY[action_key]
    return (
        "Use the exact same adult woman from the Roxy subject reference portrait; preserve her facial identity, age, "
        "skin tone, dark hair, and natural appearance. She is the only person present, wearing the same elegant "
        "forest-green apron in the same warm family kitchen. Start with her recognizable face for a brief moment, then "
        f"clearly {clip.direction}. Show the complete practical action with safe, anatomically correct hands and realistic "
        "food movement. Use generic unbranded ingredients and tools so this instructional clip can be reused across "
        "many recipes. Vertical mobile framing, steady medium close-up, warm natural light. No writing, letters, numbers, "
        "captions, subtitles, labels, logos, packaging, decorative B-roll, finished-dish hero shot, or other people."
    )
