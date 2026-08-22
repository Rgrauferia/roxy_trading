from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from functools import lru_cache
from typing import Any

from roxy_os.home_recipe_catalog import installed_recipe_templates


def _identity(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"[^a-z0-9]+", " ", normalized.encode("ascii", "ignore").decode("ascii").lower()).strip()


def _ingredient(name: str, quantity: float, unit: str, notes: str = "") -> dict[str, Any]:
    return {"name": name, "quantity": quantity, "unit": unit, "notes": notes}


def _recipe(
    title: str,
    description: str,
    kind: str,
    servings: float,
    ingredients: list[tuple[str, float, str] | tuple[str, float, str, str]],
    steps: list[str],
    *,
    drink_type: str = "",
) -> dict[str, Any]:
    row = {
        "title": title,
        "description": description,
        "kind": kind,
        "servings": servings,
        "ingredients": [_ingredient(*ingredient) for ingredient in ingredients],
        "steps": steps,
    }
    if drink_type:
        row["drink_type"] = drink_type
    return row


@lru_cache(maxsize=1)
def _templates() -> dict[str, dict[str, Any]]:
    templates = {
        "bread": {
            "title": "Pan casero sencillo",
            "description": "Pan de miga tierna y corteza dorada preparado con ingredientes básicos.",
            "kind": "bread", "servings": 8,
            "ingredients": [_ingredient("Harina de trigo", 500, "gramo"), _ingredient("Agua tibia", 325, "mililitro"), _ingredient("Levadura seca", 7, "gramo"), _ingredient("Sal", 10, "gramo"), _ingredient("Aceite", 1, "cucharada")],
            "steps": ["Mezcla la harina con la levadura y la sal.", "Añade el agua y el aceite; amasa de 8 a 10 minutos.", "Cubre la masa y déjala crecer hasta duplicar su volumen, aproximadamente una hora.", "Forma el pan y déjalo reposar 30 minutos mientras calientas el horno a 220 °C.", "Hornea entre 25 y 30 minutos y deja enfriar antes de cortar."],
        },
        "pasta": {"title": "Pasta rápida con tomate y ajo", "description": "Una comida cotidiana, rápida y adaptable.", "kind": "meal", "servings": 2, "ingredients": [_ingredient("Pasta", 200, "gramo"), _ingredient("Tomate triturado", 400, "gramo"), _ingredient("Ajo", 2, "diente"), _ingredient("Aceite de oliva", 2, "cucharada"), _ingredient("Sal", 1, "cucharadita")], "steps": ["Hierve agua con sal y cocina la pasta hasta que esté al dente.", "Sofríe el ajo en el aceite durante un minuto.", "Añade el tomate y cocina a fuego medio durante 10 minutos.", "Escurre la pasta, mézclala con la salsa y sirve caliente."]},
        "chicken": {"title": "Pollo al ajo y limón", "description": "Pollo jugoso hecho en una sola sartén.", "kind": "meal", "servings": 2, "ingredients": [_ingredient("Pechuga de pollo", 2, "unidad"), _ingredient("Ajo", 2, "diente"), _ingredient("Limón", 1, "unidad"), _ingredient("Aceite", 1, "cucharada"), _ingredient("Sal", 0.5, "cucharadita")], "steps": ["Seca el pollo y sazónalo con sal.", "Calienta el aceite y cocina el pollo de 5 a 7 minutos por cada lado, hasta alcanzar 74 °C en el centro.", "Añade el ajo y cocina 30 segundos.", "Agrega el jugo de limón, deja reducir un minuto y sirve."]},
        "rice": {"title": "Arroz con vegetales", "description": "Arroz suelto con vegetales para una comida sencilla.", "kind": "meal", "servings": 3, "ingredients": [_ingredient("Arroz", 1, "taza"), _ingredient("Agua", 2, "taza"), _ingredient("Vegetales mixtos", 1, "taza"), _ingredient("Aceite", 1, "cucharada"), _ingredient("Sal", 0.5, "cucharadita")], "steps": ["Enjuaga el arroz hasta que el agua salga casi transparente.", "Sofríe los vegetales con el aceite durante 3 minutos.", "Añade el arroz, el agua y la sal; lleva a ebullición.", "Tapa y cocina a fuego bajo durante 18 minutos; reposa 5 minutos antes de soltarlo con un tenedor."]},
        "soup": {"title": "Sopa casera de vegetales", "description": "Sopa reconfortante con productos básicos.", "kind": "meal", "servings": 4, "ingredients": [_ingredient("Papa", 2, "unidad"), _ingredient("Zanahoria", 2, "unidad"), _ingredient("Cebolla", 1, "unidad"), _ingredient("Caldo", 1, "litro"), _ingredient("Aceite", 1, "cucharada")], "steps": ["Corta todos los vegetales en trozos similares.", "Sofríe la cebolla con el aceite durante 4 minutos.", "Añade la papa, la zanahoria y el caldo.", "Cocina suavemente de 20 a 25 minutos, hasta que los vegetales estén tiernos; ajusta la sal."]},
        "salad": {"title": "Ensalada fresca de aguacate y tomate", "description": "Ensalada rápida para acompañar cualquier comida.", "kind": "meal", "servings": 2, "ingredients": [_ingredient("Aguacate", 1, "unidad"), _ingredient("Tomate", 2, "unidad"), _ingredient("Pepino", 1, "unidad"), _ingredient("Limón", 1, "unidad"), _ingredient("Aceite de oliva", 1, "cucharada")], "steps": ["Lava y corta el tomate y el pepino.", "Corta el aguacate justo antes de servir.", "Mezcla todo con limón y aceite; sazona al gusto y sirve inmediatamente."]},
        "dessert": {"title": "Arroz con leche clásico", "description": "Postre cremoso con canela.", "kind": "dessert", "servings": 6, "ingredients": [_ingredient("Arroz", 1, "taza"), _ingredient("Leche", 4, "taza"), _ingredient("Azúcar", 0.5, "taza"), _ingredient("Canela", 1, "rama"), _ingredient("Vainilla", 1, "cucharadita")], "steps": ["Enjuaga el arroz y colócalo con la leche y la canela en una olla.", "Cocina a fuego bajo, removiendo con frecuencia, de 30 a 35 minutos.", "Añade el azúcar y la vainilla; cocina 5 minutos más.", "Retira la canela y sirve tibio o frío."]},
        "smoothie": {"title": "Batido de plátano", "description": "Bebida cremosa sin alcohol.", "kind": "drink", "drink_type": "non_alcoholic", "servings": 2, "ingredients": [_ingredient("Plátano", 2, "unidad"), _ingredient("Leche", 1.5, "taza"), _ingredient("Hielo", 1, "taza"), _ingredient("Vainilla", 0.5, "cucharadita")], "steps": ["Coloca todos los ingredientes en la licuadora.", "Licúa hasta obtener una textura homogénea.", "Sirve inmediatamente."]},
        "lemonade": {"title": "Limonada fresca", "description": "Bebida cítrica sin alcohol.", "kind": "drink", "drink_type": "non_alcoholic", "servings": 4, "ingredients": [_ingredient("Limón", 4, "unidad"), _ingredient("Agua", 4, "taza"), _ingredient("Azúcar", 0.33, "taza"), _ingredient("Hielo", 2, "taza")], "steps": ["Exprime los limones.", "Disuelve el azúcar en una taza de agua.", "Mezcla el jugo, el agua restante y el jarabe.", "Añade hielo y prueba antes de ajustar el dulzor."]},
        "orange_juice": {"title": "Jugo de naranja fresco", "description": "Bebida natural sin alcohol y recién exprimida.", "kind": "drink", "drink_type": "non_alcoholic", "servings": 2, "ingredients": [_ingredient("Naranja", 6, "unidad"), _ingredient("Hielo", 1, "taza", "opcional")], "steps": ["Lava y corta las naranjas por la mitad.", "Exprime las naranjas y cuela el jugo si prefieres una textura lisa.", "Sirve inmediatamente con hielo."]},
        "hot_chocolate": {"title": "Chocolate caliente cremoso", "description": "Bebida caliente sin alcohol para compartir.", "kind": "drink", "drink_type": "non_alcoholic", "servings": 2, "ingredients": [_ingredient("Leche", 2, "taza"), _ingredient("Cacao en polvo", 2, "cucharada"), _ingredient("Azúcar", 2, "cucharada"), _ingredient("Vainilla", 0.5, "cucharadita")], "steps": ["Calienta la leche a fuego medio sin dejarla hervir.", "Añade el cacao y el azúcar; bate hasta eliminar los grumos.", "Agrega la vainilla y sirve caliente."]},
        "iced_coffee": {"title": "Café frío cremoso", "description": "Café refrescante sin alcohol.", "kind": "drink", "drink_type": "non_alcoholic", "servings": 1, "ingredients": [_ingredient("Café fuerte", 1, "taza", "frío"), _ingredient("Leche", 0.5, "taza"), _ingredient("Hielo", 1, "taza"), _ingredient("Azúcar", 1, "cucharadita", "opcional")], "steps": ["Prepara el café y déjalo enfriar.", "Llena un vaso con hielo y vierte el café.", "Añade la leche, endulza al gusto y remueve."]},
        "pina_colada_zero": {"title": "Piña colada sin alcohol", "description": "Bebida tropical cremosa apta para toda la familia.", "kind": "drink", "drink_type": "non_alcoholic", "servings": 2, "ingredients": [_ingredient("Piña", 2, "taza", "en trozos"), _ingredient("Leche de coco", 1, "taza"), _ingredient("Hielo", 1, "taza"), _ingredient("Jugo de piña", 0.5, "taza")], "steps": ["Coloca todos los ingredientes en la licuadora.", "Licúa hasta obtener una textura cremosa.", "Sirve enseguida y decora con un trozo de piña."]},
        "pina_colada": {"title": "Piña colada clásica", "description": "Cóctel tropical para adultos; ofrece una versión sin alcohol.", "kind": "drink", "drink_type": "alcoholic", "servings": 2, "ingredients": [_ingredient("Ron blanco", 90, "mililitro"), _ingredient("Piña", 2, "taza", "en trozos"), _ingredient("Leche de coco", 1, "taza"), _ingredient("Hielo", 1, "taza")], "steps": ["Coloca el ron, la piña, la leche de coco y el hielo en la licuadora.", "Licúa hasta obtener una textura cremosa.", "Sirve inmediatamente. Para una versión sin alcohol, omite el ron y añade media taza de jugo de piña."]},
        "margarita": {"title": "Margarita clásica", "description": "Cóctel cítrico para adultos con alternativa sin alcohol.", "kind": "drink", "drink_type": "alcoholic", "servings": 1, "ingredients": [_ingredient("Tequila", 50, "mililitro"), _ingredient("Licor de naranja", 25, "mililitro"), _ingredient("Jugo de limón", 25, "mililitro"), _ingredient("Hielo", 1, "taza"), _ingredient("Sal", 1, "cucharadita", "para el borde")], "steps": ["Humedece el borde de la copa con limón y pásalo por sal.", "Agita el tequila, el licor, el jugo y el hielo durante 15 segundos.", "Cuela y sirve. Para una alternativa sin alcohol, reemplaza los licores por jugo de naranja y agua con gas."]},
        "cocktail": {"title": "Mojito clásico", "description": "Cóctel para adultos; incluye alternativa sin alcohol.", "kind": "drink", "drink_type": "alcoholic", "servings": 1, "ingredients": [_ingredient("Ron blanco", 50, "mililitro"), _ingredient("Limón", 1, "unidad"), _ingredient("Hierbabuena", 8, "hoja"), _ingredient("Azúcar", 2, "cucharadita"), _ingredient("Agua con gas", 100, "mililitro"), _ingredient("Hielo", 1, "taza")], "steps": ["Machaca suavemente la hierbabuena con el azúcar y el jugo de limón.", "Añade hielo y ron; completa con agua con gas.", "Remueve y sirve. Para la versión sin alcohol, omite el ron y aumenta el agua con gas."]},
    }
    templates.update(_expanded_templates())
    templates.update(installed_recipe_templates())
    for row in templates.values():
        if row.get("category"):
            continue
        if row.get("drink_type") == "alcoholic":
            row["category"] = "cocktails"
        elif row.get("kind") == "drink":
            row["category"] = "juices"
        elif row.get("kind") == "dessert":
            row["category"] = "desserts"
        elif row.get("kind") == "bread":
            row["category"] = "baked"
        else:
            row["category"] = "pasta" if re.search(r"pasta|espagueti|lasa", _identity(row.get("title"))) else "chicken" if "pollo" in _identity(row.get("title")) else "bowls_salads" if re.search(r"bowl|ensalada", _identity(row.get("title"))) else "soups" if re.search(r"sopa|lenteja", _identity(row.get("title"))) else "meat"
    return templates


def _expanded_templates() -> dict[str, dict[str, Any]]:
    """Popular recipes that keep routine Home requests local and inexpensive."""
    return {
        # Alcoholic drinks. Every entry is explicitly for adults.
        "daiquiri": _recipe("Daiquiri clásico", "Cóctel de ron para adultos, fresco y cítrico.", "drink", 1, [("Ron blanco", 60, "mililitro"), ("Jugo de limón", 30, "mililitro"), ("Jarabe simple", 15, "mililitro"), ("Hielo", 1, "taza")], ["Enfría una copa.", "Agita todos los ingredientes con hielo durante 15 segundos.", "Cuela en la copa y sirve."], drink_type="alcoholic"),
        "cuba_libre": _recipe("Cuba libre", "Cóctel de ron para adultos con cola y limón.", "drink", 1, [("Ron", 50, "mililitro"), ("Refresco de cola", 120, "mililitro"), ("Limón", 0.5, "unidad"), ("Hielo", 1, "taza")], ["Llena un vaso alto con hielo.", "Añade el ron y el jugo de limón.", "Completa con cola, remueve suavemente y sirve."], drink_type="alcoholic"),
        "gin_tonic": _recipe("Gin tonic", "Combinado de ginebra para adultos.", "drink", 1, [("Ginebra", 50, "mililitro"), ("Agua tónica", 150, "mililitro"), ("Limón", 1, "rodaja"), ("Hielo", 1, "taza")], ["Llena una copa con hielo.", "Añade la ginebra y completa lentamente con tónica.", "Remueve una vez y aromatiza con limón."], drink_type="alcoholic"),
        "whiskey_sour": _recipe("Whisky sour", "Cóctel de whisky para adultos con equilibrio cítrico.", "drink", 1, [("Whisky", 60, "mililitro"), ("Jugo de limón", 30, "mililitro"), ("Jarabe simple", 20, "mililitro"), ("Hielo", 1, "taza")], ["Agita el whisky, el limón y el jarabe con hielo.", "Cuela sobre hielo fresco.", "Decora con una rodaja de limón."], drink_type="alcoholic"),
        "old_fashioned": _recipe("Old fashioned", "Cóctel clásico de whisky para adultos.", "drink", 1, [("Whisky bourbon", 60, "mililitro"), ("Azúcar", 1, "cucharadita"), ("Amargo aromático", 3, "gota"), ("Agua", 1, "cucharadita"), ("Hielo", 1, "cubo grande")], ["Disuelve el azúcar con el amargo y el agua en un vaso corto.", "Añade el hielo y el whisky.", "Remueve de 20 a 30 segundos y sirve con piel de naranja."], drink_type="alcoholic"),
        "manhattan": _recipe("Manhattan", "Cóctel de whisky y vermut para adultos.", "drink", 1, [("Whisky", 60, "mililitro"), ("Vermut dulce", 30, "mililitro"), ("Amargo aromático", 2, "gota"), ("Hielo", 1, "taza")], ["Remueve todos los ingredientes con hielo hasta enfriar.", "Cuela en una copa fría.", "Decora con una cereza."], drink_type="alcoholic"),
        "negroni": _recipe("Negroni", "Cóctel italiano amargo para adultos.", "drink", 1, [("Ginebra", 30, "mililitro"), ("Vermut rojo", 30, "mililitro"), ("Aperitivo amargo", 30, "mililitro"), ("Hielo", 1, "cubo grande")], ["Vierte los tres licores sobre hielo.", "Remueve hasta enfriar.", "Sirve con piel de naranja."], drink_type="alcoholic"),
        "martini": _recipe("Martini seco", "Cóctel de ginebra para adultos.", "drink", 1, [("Ginebra", 60, "mililitro"), ("Vermut seco", 10, "mililitro"), ("Hielo", 1, "taza"), ("Aceituna", 1, "unidad")], ["Remueve la ginebra y el vermut con mucho hielo.", "Cuela en una copa bien fría.", "Añade la aceituna y sirve."], drink_type="alcoholic"),
        "cosmopolitan": _recipe("Cosmopolitan", "Cóctel afrutado de vodka para adultos.", "drink", 1, [("Vodka", 40, "mililitro"), ("Licor de naranja", 20, "mililitro"), ("Jugo de arándano", 30, "mililitro"), ("Jugo de limón", 15, "mililitro"), ("Hielo", 1, "taza")], ["Agita todos los ingredientes con hielo.", "Cuela en una copa fría.", "Decora con piel de naranja."], drink_type="alcoholic"),
        "moscow_mule": _recipe("Moscow mule", "Cóctel de vodka y jengibre para adultos.", "drink", 1, [("Vodka", 50, "mililitro"), ("Cerveza de jengibre", 120, "mililitro"), ("Jugo de limón", 15, "mililitro"), ("Hielo", 1, "taza")], ["Llena un vaso con hielo.", "Añade vodka y limón.", "Completa con cerveza de jengibre y remueve suavemente."], drink_type="alcoholic"),
        "tequila_sunrise": _recipe("Tequila sunrise", "Cóctel de tequila para adultos con naranja.", "drink", 1, [("Tequila", 50, "mililitro"), ("Jugo de naranja", 120, "mililitro"), ("Granadina", 15, "mililitro"), ("Hielo", 1, "taza")], ["Vierte tequila y naranja sobre hielo.", "Añade lentamente la granadina para crear el degradado.", "No remuevas antes de servir."], drink_type="alcoholic"),
        "paloma": _recipe("Paloma", "Cóctel mexicano de tequila para adultos.", "drink", 1, [("Tequila", 50, "mililitro"), ("Refresco de toronja", 120, "mililitro"), ("Jugo de limón", 15, "mililitro"), ("Sal", 1, "pizca"), ("Hielo", 1, "taza")], ["Escarcha opcionalmente el vaso con sal.", "Añade hielo, tequila y limón.", "Completa con refresco de toronja y remueve."], drink_type="alcoholic"),
        "sangria": _recipe("Sangría clásica", "Bebida de vino para adultos preparada para compartir.", "drink", 6, [("Vino tinto", 750, "mililitro"), ("Naranja", 1, "unidad"), ("Manzana", 1, "unidad"), ("Agua con gas", 250, "mililitro"), ("Azúcar", 2, "cucharada"), ("Hielo", 2, "taza")], ["Corta la fruta en trozos pequeños.", "Mezcla la fruta, el vino y el azúcar; enfría al menos una hora.", "Añade hielo y agua con gas justo antes de servir."], drink_type="alcoholic"),
        "mimosa": _recipe("Mimosa", "Cóctel espumoso para adultos.", "drink", 1, [("Vino espumoso", 75, "mililitro"), ("Jugo de naranja", 75, "mililitro")], ["Enfría ambos ingredientes.", "Sirve primero el vino espumoso.", "Añade lentamente el jugo de naranja y sirve sin remover demasiado."], drink_type="alcoholic"),
        "aperol_spritz": _recipe("Aperol spritz", "Cóctel espumoso y amargo para adultos.", "drink", 1, [("Vino prosecco", 90, "mililitro"), ("Aperitivo amargo de naranja", 60, "mililitro"), ("Agua con gas", 30, "mililitro"), ("Hielo", 1, "taza")], ["Llena una copa con hielo.", "Añade prosecco, aperitivo y agua con gas.", "Remueve suavemente y sirve con naranja."], drink_type="alcoholic"),
        "bloody_mary": _recipe("Bloody Mary", "Cóctel salado de vodka para adultos.", "drink", 1, [("Vodka", 45, "mililitro"), ("Jugo de tomate", 120, "mililitro"), ("Jugo de limón", 15, "mililitro"), ("Salsa inglesa", 2, "gota"), ("Salsa picante", 2, "gota"), ("Hielo", 1, "taza")], ["Añade todos los ingredientes a un vaso con hielo.", "Remueve hasta enfriar.", "Prueba, ajusta picante y sirve."], drink_type="alcoholic"),
        "espresso_martini": _recipe("Espresso martini", "Cóctel de café y vodka para adultos.", "drink", 1, [("Vodka", 45, "mililitro"), ("Licor de café", 25, "mililitro"), ("Café espresso", 30, "mililitro", "frío"), ("Hielo", 1, "taza")], ["Enfría el espresso.", "Agita enérgicamente todos los ingredientes con hielo.", "Cuela en una copa fría y sirve."], drink_type="alcoholic"),
        "caipirinha": _recipe("Caipiriña", "Cóctel brasileño de cachaça para adultos.", "drink", 1, [("Cachaça", 60, "mililitro"), ("Limón", 1, "unidad"), ("Azúcar", 2, "cucharadita"), ("Hielo", 1, "taza")], ["Corta el limón y machácalo suavemente con el azúcar.", "Llena el vaso con hielo.", "Añade la cachaça, remueve y sirve."], drink_type="alcoholic"),
        "mai_tai": _recipe("Mai Tai", "Cóctel tropical de ron para adultos.", "drink", 1, [("Ron añejo", 45, "mililitro"), ("Ron blanco", 15, "mililitro"), ("Licor de naranja", 15, "mililitro"), ("Jugo de limón", 25, "mililitro"), ("Jarabe de almendra", 15, "mililitro"), ("Hielo", 1, "taza")], ["Agita todos los ingredientes con hielo.", "Vierte en un vaso con hielo fresco.", "Decora con limón y sirve."], drink_type="alcoholic"),
        "long_island": _recipe("Long Island iced tea", "Cóctel fuerte para adultos; servir con moderación.", "drink", 1, [("Vodka", 15, "mililitro"), ("Ginebra", 15, "mililitro"), ("Ron blanco", 15, "mililitro"), ("Tequila", 15, "mililitro"), ("Licor de naranja", 15, "mililitro"), ("Jugo de limón", 25, "mililitro"), ("Refresco de cola", 60, "mililitro"), ("Hielo", 1, "taza")], ["Agita los licores y el limón con hielo.", "Vierte en un vaso alto con hielo.", "Completa con cola, remueve suavemente y sirve una sola porción."], drink_type="alcoholic"),
        "vodka_lemonade": _recipe("Limonada con vodka", "Cóctel cítrico sencillo para adultos.", "drink", 1, [("Vodka", 45, "mililitro"), ("Limonada", 150, "mililitro"), ("Hielo", 1, "taza"), ("Limón", 1, "rodaja")], ["Llena un vaso con hielo.", "Añade vodka y limonada.", "Remueve suavemente y sirve con limón."], drink_type="alcoholic"),
        "virgin_daiquiri": _recipe("Daiquiri de fresa sin alcohol", "Bebida frozen de fresa sin alcohol.", "drink", 2, [("Fresa", 2, "taza"), ("Jugo de limón", 45, "mililitro"), ("Jarabe simple", 30, "mililitro"), ("Hielo", 2, "taza")], ["Coloca todos los ingredientes en la licuadora.", "Licúa hasta obtener una textura frozen uniforme.", "Sirve inmediatamente."], drink_type="non_alcoholic"),
        "virgin_mojito": _recipe("Mojito sin alcohol", "Versión fresca del mojito apta sin alcohol.", "drink", 1, [("Limón", 1, "unidad"), ("Hierbabuena", 8, "hoja"), ("Azúcar", 2, "cucharadita"), ("Agua con gas", 150, "mililitro"), ("Hielo", 1, "taza")], ["Machaca suavemente hierbabuena, azúcar y limón.", "Añade hielo y completa con agua con gas.", "Remueve y sirve."], drink_type="non_alcoholic"),
        "virgin_margarita": _recipe("Margarita sin alcohol", "Bebida cítrica sin alcohol.", "drink", 1, [("Jugo de naranja", 60, "mililitro"), ("Jugo de limón", 30, "mililitro"), ("Agua con gas", 60, "mililitro"), ("Hielo", 1, "taza"), ("Sal", 1, "cucharadita", "para el borde")], ["Escarcha el vaso con limón y sal.", "Agita los jugos con hielo.", "Sirve y completa con agua con gas."], drink_type="non_alcoholic"),

        # Common meals.
        "arroz_con_pollo": _recipe("Arroz con pollo", "Plato casero completo y rendidor.", "meal", 4, [("Pollo", 700, "gramo"), ("Arroz", 2, "taza"), ("Caldo de pollo", 4, "taza"), ("Pimiento", 1, "unidad"), ("Cebolla", 1, "unidad"), ("Ajo", 3, "diente"), ("Aceite", 2, "cucharada")], ["Dora el pollo sazonado y resérvalo.", "Sofríe cebolla, pimiento y ajo.", "Añade arroz, caldo y pollo; tapa y cocina a fuego bajo unos 25 minutos.", "Reposa cinco minutos antes de servir." ]),
        "ropa_vieja": _recipe("Ropa vieja", "Carne deshebrada al estilo cubano.", "meal", 6, [("Falda de res", 1, "kilogramo"), ("Tomate triturado", 400, "gramo"), ("Pimiento", 2, "unidad"), ("Cebolla", 1, "unidad"), ("Ajo", 4, "diente"), ("Caldo", 2, "taza")], ["Cocina la carne en el caldo hasta que esté tierna y deshébrala.", "Sofríe cebolla, pimiento y ajo.", "Añade tomate, carne y parte del caldo.", "Cocina suavemente 25 minutos y ajusta la sazón." ]),
        "picadillo": _recipe("Picadillo casero", "Carne molida guisada con tomate.", "meal", 4, [("Carne molida", 700, "gramo"), ("Tomate triturado", 300, "gramo"), ("Cebolla", 1, "unidad"), ("Pimiento", 1, "unidad"), ("Ajo", 2, "diente"), ("Aceituna", 0.5, "taza")], ["Sofríe cebolla, pimiento y ajo.", "Añade la carne y cocina hasta dorar.", "Incorpora tomate y aceitunas.", "Cocina 15 minutos a fuego medio y sirve." ]),
        "pollo_guisado": _recipe("Pollo guisado", "Pollo tierno en salsa casera.", "meal", 4, [("Pollo", 1, "kilogramo"), ("Tomate", 3, "unidad"), ("Papa", 3, "unidad"), ("Cebolla", 1, "unidad"), ("Pimiento", 1, "unidad"), ("Caldo", 2, "taza")], ["Dora el pollo sazonado.", "Añade cebolla y pimiento y sofríe cinco minutos.", "Incorpora tomate, papa y caldo.", "Tapa y cocina suavemente hasta que el pollo alcance 74 °C y la papa esté tierna." ]),
        "tacos": _recipe("Tacos de carne", "Tacos caseros rápidos con acompañamientos frescos.", "meal", 4, [("Carne molida", 600, "gramo"), ("Tortilla", 12, "unidad"), ("Cebolla", 1, "unidad"), ("Tomate", 2, "unidad"), ("Lechuga", 2, "taza"), ("Queso", 1, "taza")], ["Cocina la carne con la mitad de la cebolla y sazona.", "Calienta las tortillas.", "Rellena con carne, lechuga, tomate, cebolla y queso.", "Sirve inmediatamente." ]),
        "lasagna": _recipe("Lasaña de carne", "Lasaña clásica con salsa de tomate y queso.", "meal", 8, [("Lámina de lasaña", 12, "unidad"), ("Carne molida", 700, "gramo"), ("Salsa de tomate", 700, "gramo"), ("Queso mozzarella", 400, "gramo"), ("Queso ricotta", 400, "gramo")], ["Cocina la carne y mézclala con la salsa.", "Alterna capas de salsa, pasta, ricotta y mozzarella.", "Cubre y hornea a 190 °C durante 35 minutos.", "Destapa, gratina 10 minutos y reposa antes de cortar." ]),
        "pizza": _recipe("Pizza casera", "Pizza familiar de masa sencilla.", "meal", 4, [("Harina de trigo", 400, "gramo"), ("Agua tibia", 250, "mililitro"), ("Levadura seca", 7, "gramo"), ("Salsa de tomate", 1, "taza"), ("Queso mozzarella", 300, "gramo"), ("Aceite", 1, "cucharada")], ["Mezcla harina, levadura, agua y aceite; amasa ocho minutos.", "Deja crecer la masa una hora.", "Estira, añade salsa, queso y tus ingredientes.", "Hornea a 240 °C de 12 a 16 minutos." ]),
        "meatballs": _recipe("Albóndigas en salsa", "Albóndigas tiernas en salsa de tomate.", "meal", 4, [("Carne molida", 700, "gramo"), ("Huevo", 1, "unidad"), ("Pan rallado", 0.5, "taza"), ("Salsa de tomate", 500, "gramo"), ("Ajo", 2, "diente")], ["Mezcla carne, huevo, pan rallado, ajo y sal.", "Forma las albóndigas y dóralas.", "Añade la salsa y cocina tapado 20 minutos.", "Comprueba que el centro esté completamente cocido." ]),
        "fried_rice": _recipe("Arroz frito", "Arroz salteado rápido con vegetales y huevo.", "meal", 4, [("Arroz cocido frío", 4, "taza"), ("Huevo", 3, "unidad"), ("Vegetales mixtos", 2, "taza"), ("Salsa de soja", 3, "cucharada"), ("Aceite", 2, "cucharada")], ["Revuelve los huevos en una sartén y resérvalos.", "Saltea los vegetales.", "Añade el arroz frío y cocina a fuego alto.", "Incorpora huevo y salsa de soja y sirve caliente." ]),
        "salmon": _recipe("Salmón al horno", "Salmón sencillo con limón y ajo.", "meal", 4, [("Filete de salmón", 4, "unidad"), ("Limón", 1, "unidad"), ("Ajo", 2, "diente"), ("Aceite de oliva", 2, "cucharada")], ["Calienta el horno a 200 °C.", "Coloca el salmón en una bandeja y añade aceite, ajo y limón.", "Hornea de 12 a 15 minutos, hasta alcanzar el punto seguro y deseado.", "Sirve inmediatamente." ]),
        "lentils": _recipe("Lentejas guisadas", "Guiso reconfortante de lentejas y vegetales.", "meal", 6, [("Lenteja", 2, "taza"), ("Agua o caldo", 7, "taza"), ("Zanahoria", 2, "unidad"), ("Papa", 2, "unidad"), ("Cebolla", 1, "unidad"), ("Ajo", 2, "diente")], ["Enjuaga las lentejas.", "Sofríe cebolla, ajo y zanahoria.", "Añade lentejas, papa y caldo.", "Cocina suavemente de 30 a 40 minutos hasta que estén tiernas." ]),
        "omelet": _recipe("Tortilla francesa con queso", "Desayuno rápido de huevo y queso.", "meal", 1, [("Huevo", 3, "unidad"), ("Queso", 0.5, "taza"), ("Mantequilla", 1, "cucharadita")], ["Bate los huevos con una pizca de sal.", "Derrite la mantequilla y vierte los huevos.", "Añade queso cuando los bordes cuajen.", "Dobla y cocina hasta que el huevo esté completamente cuajado." ]),
        "overnight_oats": _recipe("Avena nocturna con frutas", "Desayuno frío que se prepara la noche anterior.", "meal", 1, [("Avena", 0.5, "taza"), ("Leche", 0.75, "taza"), ("Yogur natural", 0.25, "taza"), ("Fruta", 0.5, "taza")], ["Mezcla la avena, la leche y el yogur en un recipiente con tapa.", "Refrigera durante la noche o al menos seis horas.", "Añade la fruta justo antes de servir." ]),
        "eggs_toast": _recipe("Huevos con tostada integral", "Desayuno rápido, completo y sencillo.", "meal", 1, [("Huevo", 2, "unidad"), ("Pan integral", 2, "rebanada"), ("Aceite", 1, "cucharadita")], ["Tuesta el pan.", "Calienta el aceite y cocina los huevos hasta que la clara y la yema alcancen el punto seguro deseado.", "Sirve los huevos sobre las tostadas." ]),
        "avocado_toast": _recipe("Tostada de aguacate y huevo", "Desayuno saciante con aguacate y huevo.", "meal", 1, [("Pan integral", 2, "rebanada"), ("Aguacate", 0.5, "unidad"), ("Huevo", 1, "unidad"), ("Limón", 0.25, "unidad")], ["Tuesta el pan.", "Machaca el aguacate con unas gotas de limón.", "Cocina el huevo completamente y colócalo sobre la tostada con aguacate." ]),
        "pancakes": _recipe("Panqueques de avena", "Panqueques rápidos de avena y plátano.", "meal", 2, [("Avena", 0.75, "taza"), ("Huevo", 1, "unidad"), ("Plátano", 1, "unidad"), ("Leche", 0.25, "taza")], ["Licúa la avena, el huevo, el plátano y la leche.", "Calienta una sartén antiadherente.", "Cocina porciones pequeñas hasta que aparezcan burbujas, voltea y cocina hasta que el centro esté hecho." ]),
        "chicken_bowl": _recipe("Bowl de pollo y vegetales", "Comida rápida que aprovecha pollo y arroz ya cocidos.", "meal", 2, [("Pechuga de pollo cocida", 2, "unidad"), ("Vegetales mixtos", 3, "taza"), ("Arroz cocido", 1, "taza")], ["Calienta el pollo hasta que esté bien caliente en el centro.", "Saltea o recalienta los vegetales.", "Reparte arroz, pollo y vegetales en dos bowls y sirve." ]),
        "tuna_bowl": _recipe("Bowl de atún y garbanzos", "Comida fresca sin cocción y rica en proteína.", "meal", 2, [("Atún", 2, "lata"), ("Garbanzos cocidos", 1.5, "taza"), ("Pepino", 1, "unidad"), ("Tomate", 2, "unidad"), ("Limón", 1, "unidad")], ["Escurre el atún y los garbanzos.", "Lava y corta el pepino y el tomate.", "Mezcla todo con jugo de limón y sirve frío." ]),
        "chicken_wrap": _recipe("Wrap de pollo y aguacate", "Cena rápida para aprovechar pollo cocido.", "meal", 2, [("Pollo cocido", 240, "gramo"), ("Tortilla integral", 2, "unidad"), ("Aguacate", 1, "unidad"), ("Tomate", 1, "unidad")], ["Calienta el pollo hasta que esté bien caliente.", "Corta el tomate y el aguacate.", "Reparte el relleno entre las tortillas, enrolla y sirve." ]),
        "quesadilla": _recipe("Quesadilla de pollo y vegetales", "Cena rápida de sartén con pollo y queso.", "meal", 2, [("Tortilla", 4, "unidad"), ("Pollo cocido", 200, "gramo"), ("Queso", 1, "taza"), ("Vegetales mixtos", 1, "taza")], ["Calienta el pollo y los vegetales.", "Distribuye pollo, vegetales y queso sobre dos tortillas y cubre con las restantes.", "Cocina cada quesadilla por ambos lados hasta que el queso se derrita y el centro esté bien caliente." ]),

        # Common desserts.
        "flan": _recipe("Flan de vainilla", "Postre de caramelo suave y cremoso.", "dessert", 8, [("Huevo", 5, "unidad"), ("Leche condensada", 1, "lata"), ("Leche evaporada", 1, "lata"), ("Vainilla", 1, "cucharadita"), ("Azúcar", 1, "taza")], ["Derrite el azúcar hasta formar caramelo y cubre el molde.", "Licúa huevos, leches y vainilla.", "Vierte en el molde y hornea a baño María a 175 °C unos 55 minutos.", "Enfría por completo antes de desmoldar." ]),
        "tres_leches": _recipe("Pastel de tres leches", "Bizcocho húmedo con mezcla de tres leches.", "dessert", 12, [("Harina de trigo", 1.5, "taza"), ("Huevo", 5, "unidad"), ("Azúcar", 1, "taza"), ("Leche condensada", 1, "lata"), ("Leche evaporada", 1, "lata"), ("Crema de leche", 1, "taza")], ["Hornea un bizcocho con harina, huevos y azúcar a 175 °C.", "Mezcla las tres leches.", "Pincha el bizcocho tibio y vierte la mezcla poco a poco.", "Refrigera al menos cuatro horas antes de decorar." ]),
        "cheesecake": _recipe("Cheesecake clásico", "Tarta cremosa de queso con base de galleta.", "dessert", 10, [("Queso crema", 700, "gramo"), ("Galleta", 250, "gramo"), ("Mantequilla", 100, "gramo"), ("Azúcar", 1, "taza"), ("Huevo", 3, "unidad"), ("Vainilla", 1, "cucharadita")], ["Mezcla galleta triturada con mantequilla y presiona en el molde.", "Bate queso, azúcar y vainilla; incorpora los huevos uno a uno.", "Hornea a 160 °C unos 55 minutos.", "Enfría y refrigera al menos cuatro horas." ]),
        "brownies": _recipe("Brownies de chocolate", "Brownies húmedos con centro intenso de chocolate.", "dessert", 12, [("Chocolate", 200, "gramo"), ("Mantequilla", 150, "gramo"), ("Azúcar", 1, "taza"), ("Huevo", 3, "unidad"), ("Harina de trigo", 0.75, "taza")], ["Derrite chocolate y mantequilla.", "Bate huevos con azúcar e incorpora el chocolate.", "Añade la harina sin mezclar en exceso.", "Hornea a 175 °C de 22 a 28 minutos." ]),
        "cookies": _recipe("Galletas con chispas de chocolate", "Galletas clásicas doradas por fuera y suaves por dentro.", "dessert", 18, [("Harina de trigo", 2.25, "taza"), ("Mantequilla", 1, "taza"), ("Azúcar", 0.75, "taza"), ("Azúcar morena", 0.75, "taza"), ("Huevo", 2, "unidad"), ("Chispas de chocolate", 2, "taza")], ["Bate mantequilla y azúcares.", "Añade huevos y luego harina.", "Incorpora las chispas y forma porciones.", "Hornea a 180 °C de 9 a 12 minutos." ]),
        "chocolate_cake": _recipe("Pastel de chocolate", "Pastel de chocolate esponjoso y familiar.", "dessert", 12, [("Harina de trigo", 2, "taza"), ("Cacao en polvo", 0.75, "taza"), ("Azúcar", 2, "taza"), ("Huevo", 2, "unidad"), ("Leche", 1, "taza"), ("Aceite", 0.5, "taza")], ["Mezcla los ingredientes secos.", "Añade huevos, leche y aceite y bate hasta integrar.", "Vierte en un molde preparado.", "Hornea a 175 °C de 30 a 35 minutos y enfría antes de decorar." ]),
        "bread_pudding": _recipe("Pudín de pan", "Postre casero para aprovechar pan del día anterior.", "dessert", 10, [("Pan", 500, "gramo"), ("Leche", 4, "taza"), ("Huevo", 4, "unidad"), ("Azúcar", 1, "taza"), ("Vainilla", 1, "cucharadita"), ("Canela", 1, "cucharadita")], ["Remoja el pan en la leche.", "Mezcla huevos, azúcar, vainilla y canela.", "Combina todo y vierte en un molde.", "Hornea a 175 °C de 45 a 55 minutos." ]),
        "tiramisu": _recipe("Tiramisú", "Postre frío de café y crema de mascarpone.", "dessert", 8, [("Queso mascarpone", 500, "gramo"), ("Bizcocho de soletilla", 300, "gramo"), ("Café", 2, "taza", "frío"), ("Huevo pasteurizado", 4, "unidad"), ("Azúcar", 0.75, "taza"), ("Cacao en polvo", 2, "cucharada")], ["Bate los huevos pasteurizados con azúcar y mezcla con mascarpone.", "Pasa brevemente los bizcochos por café.", "Alterna capas de bizcocho y crema.", "Refrigera al menos seis horas y espolvorea cacao." ]),
        "apple_pie": _recipe("Tarta de manzana", "Tarta clásica de manzana y canela.", "dessert", 8, [("Masa para tarta", 2, "lámina"), ("Manzana", 6, "unidad"), ("Azúcar", 0.75, "taza"), ("Canela", 1, "cucharadita"), ("Mantequilla", 2, "cucharada")], ["Corta las manzanas y mézclalas con azúcar y canela.", "Coloca una masa en el molde y añade el relleno.", "Cubre con la segunda masa y abre salidas de vapor.", "Hornea a 190 °C de 45 a 55 minutos." ]),
        "carrot_cake": _recipe("Pastel de zanahoria", "Pastel especiado y húmedo con zanahoria.", "dessert", 12, [("Zanahoria rallada", 3, "taza"), ("Harina de trigo", 2, "taza"), ("Azúcar", 1.5, "taza"), ("Huevo", 4, "unidad"), ("Aceite", 1, "taza"), ("Canela", 2, "cucharadita")], ["Mezcla harina, canela y azúcar.", "Añade huevos, aceite y zanahoria.", "Vierte en un molde preparado.", "Hornea a 175 °C de 35 a 40 minutos." ]),
    }


def _local_recipe_key(prompt: str) -> str | None:
    query = _identity(prompt)
    alcohol_free = bool(re.search(r"\b(sin alcohol|no alcohol|no uses ningun ingrediente con alcohol|virgen|mocktail)\b", query))
    alcohol_requested = not alcohol_free and bool(
        re.search(r"\b(con alcohol|bebida alcoholica|para adultos|ingrediente alcoholico|vodka|ron|tequila|whisky|ginebra|licor)\b", query)
    )
    installed_matches = [
        (key, _identity(row.get("title")))
        for key, row in _templates().items()
        if key.startswith("installed_") and _identity(row.get("title")) in query
    ]
    if installed_matches:
        key = max(installed_matches, key=lambda item: len(item[1]))[0]
        drink_type = str(_templates()[key].get("drink_type") or "")
        if alcohol_free and drink_type == "alcoholic":
            return None
        if alcohol_requested and drink_type == "non_alcoholic":
            return None
        return key
    if re.search(r"\bpina colada\b", query):
        return "pina_colada_zero" if alcohol_free else "pina_colada"
    if re.search(r"\bmargarita\b", query):
        return "virgin_margarita" if alcohol_free else "margarita"
    if re.search(r"\bmojito\b", query):
        return "virgin_mojito" if alcohol_free else "cocktail"
    if re.search(r"\bdaiquiri\b", query) and alcohol_free:
        return "virgin_daiquiri"
    if re.search(r"\blimonada\b", query) and alcohol_requested:
        return "vodka_lemonade"
    if re.search(r"\b(coctel|cocktail|trago|bebida alcoholica)\b", query) and not alcohol_free:
        return "cocktail"

    aliases: tuple[tuple[str, str], ...] = (
        ("daiquiri", r"\bdaiquiri\b"),
        ("cuba_libre", r"\b(cuba libre|ron con cola|cubata)\b"),
        ("gin_tonic", r"\b(gin tonic|gintonic|ginebra con tonica)\b"),
        ("whiskey_sour", r"\b(whisky sour|whiskey sour|coctel de whisky)\b"),
        ("old_fashioned", r"\b(old fashioned)\b"),
        ("manhattan", r"\bmanhattan\b"),
        ("negroni", r"\bnegroni\b"),
        ("martini", r"(?<!espresso )\bmartini\b(?! de cafe)"),
        ("cosmopolitan", r"\b(cosmopolitan|cosmopolitan)\b"),
        ("moscow_mule", r"\b(moscow mule|mula de moscu)\b"),
        ("tequila_sunrise", r"\b(tequila sunrise|amanecer de tequila)\b"),
        ("paloma", r"\bpaloma\b"),
        ("sangria", r"\bsangria\b"),
        ("mimosa", r"\bmimosa\b"),
        ("aperol_spritz", r"\b(aperol spritz|spritz)\b"),
        ("bloody_mary", r"\b(bloody mary)\b"),
        ("espresso_martini", r"\b(espresso martini|martini de cafe)\b"),
        ("caipirinha", r"\b(caipirina|caipirinha)\b"),
        ("mai_tai", r"\b(mai tai)\b"),
        ("long_island", r"\b(long island|long island iced tea)\b"),
        ("hot_chocolate", r"\b(chocolate caliente|chocolate a la taza|cocoa)\b"),
        ("iced_coffee", r"\b(cafe frio|cafe helado|iced coffee|frappe)\b"),
        ("orange_juice", r"\b(jugo de naranja|zumo de naranja|naranjada)\b"),
        ("smoothie", r"\b(batido|smoothie|licuado)\b"),
        ("lemonade", r"\b(bebida|jugo|zumo|limonada|refresco|coctel|cocktail|trago)\b"),

        # Desserts come before generic rice, bread and cake matches.
        ("tres_leches", r"\b(tres leches|pastel de tres leches)\b"),
        ("cheesecake", r"\b(cheesecake|tarta de queso|pastel de queso)\b"),
        ("brownies", r"\b(brownie|brownies)\b"),
        ("cookies", r"\b(galleta|galletas|cookies)\b"),
        ("chocolate_cake", r"\b(pastel de chocolate|torta de chocolate|bizcocho de chocolate)\b"),
        ("bread_pudding", r"\b(pudin de pan|budin de pan|pudding de pan)\b"),
        ("tiramisu", r"\btiramisu\b"),
        ("apple_pie", r"\b(tarta de manzana|pastel de manzana|apple pie)\b"),
        ("carrot_cake", r"\b(pastel de zanahoria|torta de zanahoria|carrot cake)\b"),
        ("flan", r"\bflan\b"),
        ("dessert", r"\b(arroz con leche|postre|dulce|pastel|tarta|bizcocho|helado)\b"),

        ("arroz_con_pollo", r"\barroz con pollo\b"),
        ("ropa_vieja", r"\bropa vieja\b"),
        ("picadillo", r"\bpicadillo\b"),
        ("pollo_guisado", r"\b(pollo guisado|pollo en salsa)\b"),
        ("tacos", r"\b(taco|tacos)\b"),
        ("lasagna", r"\b(lasana|lasagna)\b"),
        ("pizza", r"\b(pizza|pizzeta)\b"),
        ("meatballs", r"\b(albondiga|albondigas|meatballs)\b"),
        ("fried_rice", r"\b(arroz frito|arroz chino)\b"),
        ("salmon", r"\b(salmon al horno|salmon)\b"),
        ("lentils", r"\b(lenteja|lentejas)\b"),
        ("overnight_oats", r"\b(avena nocturna|overnight oats)\b"),
        ("eggs_toast", r"\b(huevos? con tostada|tostada con huevos?)\b"),
        ("avocado_toast", r"\b(tostada de aguacate|tostada con aguacate)\b"),
        ("pancakes", r"\b(panqueque|panqueques|pancake|pancakes)\b"),
        ("chicken_bowl", r"\b(bowl de pollo|tazon de pollo)\b"),
        ("tuna_bowl", r"\b(bowl de atun|atun y garbanzos)\b"),
        ("chicken_wrap", r"\b(wrap de pollo|rollo de pollo)\b"),
        ("quesadilla", r"\b(quesadilla|quesadillas)\b"),
        ("omelet", r"\b(omelet|omelette|tortilla francesa)\b"),
        ("bread", r"\b(pan|baguette|focaccia|brioche|masa)\b"),
        ("pasta", r"\b(pasta|espagueti|espaguetis|spaghetti|macarron|macarrones|fideo|fideos)\b"),
        ("chicken", r"\b(pollo|pechuga|comida|plato)\b"),
        ("rice", r"\barroz\b"),
        ("soup", r"\b(sopa|caldo|crema de vegetales)\b"),
        ("salad", r"\b(ensalada|aguacate)\b"),
    )
    key = next((key for key, pattern in aliases if re.search(pattern, query)), None)
    if not key:
        return None
    drink_type = str(_templates()[key].get("drink_type") or "")
    if alcohol_free and drink_type == "alcoholic":
        return None
    if alcohol_requested and drink_type == "non_alcoholic":
        return None
    return key


def _prepare_local_recipe(key: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    recipe = deepcopy(_templates()[key])
    profile = (snapshot or {}).get("profile") or {}
    allergies = [_identity(value) for value in profile.get("allergies") or []]
    notes = ["Receta del catálogo local de Roxy Home; confirma marcas e ingredientes según tus necesidades."]
    if allergies:
        notes.append("Alergias registradas: " + ", ".join(str(value) for value in profile.get("allergies") or []) + ". Evita contaminación cruzada.")
    recipe["allergen_notes"] = notes
    recipe["sources"] = []
    recipe["generation_source"] = "local_recipe_catalog"
    return recipe


def find_local_recipe(prompt: str, snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Return a common curated recipe, or ``None`` when OpenAI is warranted."""
    key = _local_recipe_key(prompt)
    return _prepare_local_recipe(key, snapshot) if key else None


def local_recipe_catalog_summary() -> dict[str, int]:
    rows = list(_unique_catalog_templates().values())
    return {
        "total": len(rows),
        "meals": sum(row.get("kind") in {"meal", "bread"} for row in rows),
        "desserts": sum(row.get("kind") == "dessert" for row in rows),
        "drinks": sum(row.get("kind") == "drink" for row in rows),
        "alcoholic_drinks": sum(row.get("drink_type") == "alcoholic" for row in rows),
        "non_alcoholic_drinks": sum(row.get("drink_type") == "non_alcoholic" for row in rows),
        "categories": len({row.get("category") for row in rows if row.get("category")}),
    }


def local_recipe_catalog(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the installed cookbook without creating user-owned copies."""
    return [
        {"catalog_key": key, **_prepare_local_recipe(key, snapshot)}
        for key in sorted(_unique_catalog_templates(), key=lambda value: str(_templates()[value].get("title") or value).casefold())
    ]


def _unique_catalog_templates() -> dict[str, dict[str, Any]]:
    """Prefer the new categorized edition when a legacy title is duplicated."""
    templates = _templates()
    unique: dict[str, dict[str, Any]] = {}
    seen_titles: set[str] = set()
    for key in sorted(templates, key=lambda value: (not value.startswith("installed_"), value)):
        title = _identity(templates[key].get("title") or key)
        if title and title not in seen_titles:
            unique[key] = templates[key]
            seen_titles.add(title)
    return unique


def generate_local_recipe(prompt: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Always return a safe recipe when a remote provider is unavailable."""
    return find_local_recipe(prompt, snapshot) or _prepare_local_recipe("chicken", snapshot)
