"""Catálogo editorial instalado con Roxy Home.

Las recetas de este módulo no dependen de una llamada remota.  Se construyen a
partir de bases culinarias deterministas y se entregan completas (ingredientes y
pasos), de modo que el recetario siga funcionando sin conexión y OpenAI quede
reservado para solicitudes que no estén aquí.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any


CATEGORY_META: dict[str, dict[str, str]] = {
    "breakfast": {"title": "Desayunos", "description": "Huevos, avena, yogur, pancakes y tostadas", "icon": "egg_alt"},
    "chicken": {"title": "Pollo", "description": "Recetas cotidianas de pollo", "icon": "skillet"},
    "meat": {"title": "Carnes", "description": "Res y cerdo", "icon": "outdoor_grill"},
    "seafood": {"title": "Pescados y mariscos", "description": "Pescados, atún y camarones", "icon": "set_meal"},
    "rice": {"title": "Arroces", "description": "Arroces, risottos y paellas", "icon": "rice_bowl"},
    "pasta": {"title": "Pastas y fideos", "description": "Pastas, lasañas y fideos", "icon": "ramen_dining"},
    "soups": {"title": "Sopas, cremas y guisos", "description": "Platos de cuchara reconfortantes", "icon": "soup_kitchen"},
    "bowls_salads": {"title": "Bowls y ensaladas", "description": "Comidas frescas y completas", "icon": "salad"},
    "vegetarian": {"title": "Vegetarianas", "description": "Recetas sin carne", "icon": "eco"},
    "baked": {"title": "Horneados", "description": "Pizzas, panes, masas y gratinados", "icon": "bakery_dining"},
    "sides_sauces": {"title": "Acompañamientos y salsas", "description": "Guarniciones y básicos caseros", "icon": "tapas"},
    "desserts": {"title": "Postres", "description": "Dulces clásicos para compartir", "icon": "cake"},
    "coffee_hot": {"title": "Café y bebidas calientes", "description": "Café caliente, frío, té y chocolate", "icon": "coffee"},
    "juices": {"title": "Jugos y refrescantes", "description": "Jugos, limonadas y aguas frescas", "icon": "local_drink"},
    "smoothies": {"title": "Batidos y smoothies", "description": "Frutas, proteína y bowls", "icon": "blender"},
    "cocktails": {"title": "Cócteles", "description": "Recetas para adultos preservadas del recetario", "icon": "local_bar"},
}


GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("breakfast", "Huevos", ("Huevos revueltos", "Huevos fritos", "Huevos hervidos", "Tortilla española", "Omelette de jamón y queso", "Omelette de vegetales", "Huevos rancheros", "Huevos Benedict", "Shakshuka", "Sándwich de huevo")),
    ("breakfast", "Avena, yogur y cereales", ("Avena con leche y canela", "Avena nocturna con frutas", "Avena con manzana", "Avena con banana y mantequilla de maní", "Yogur con fruta y granola", "Yogur griego con miel", "Pudín de chía", "Parfait de yogur", "Granola casera", "Bowl de frutas")),
    ("breakfast", "Pancakes, waffles y tostadas", ("Pancakes tradicionales", "Pancakes de avena", "Pancakes de banana", "Waffles clásicos", "Tostadas francesas", "Tostada con aguacate", "Tostada con huevo", "Tostada con mantequilla de maní", "Crepes dulces", "Crepes de jamón y queso")),
    ("chicken", "Pollo", ("Pollo al ajo", "Pollo asado", "Pollo a la plancha", "Pollo guisado", "Pollo al horno con papas", "Pollo en salsa de tomate", "Pollo con limón", "Pollo con miel y mostaza", "Pollo parmesano", "Pollo Alfredo", "Pollo teriyaki", "Pollo al curry", "Fajitas de pollo", "Tacos de pollo", "Enchiladas de pollo", "Pollo empanizado", "Alitas al horno", "Pollo con arroz", "Salteado de pollo y vegetales", "Sándwich de pollo")),
    ("meat", "Res", ("Ropa vieja", "Picadillo cubano", "Albóndigas en salsa", "Carne con papas", "Bistec encebollado", "Bistec a la plancha", "Carne asada", "Carne guisada", "Hamburguesa casera", "Pastel de carne", "Tacos de carne", "Fajitas de res", "Carne salteada con vegetales", "Chili con carne", "Lasaña de carne")),
    ("meat", "Cerdo", ("Lechón asado", "Chuletas de cerdo", "Cerdo agridulce", "Cerdo al horno", "Costillas BBQ", "Lomo de cerdo", "Cerdo desmenuzado", "Masas de cerdo fritas", "Tacos de cerdo", "Sándwich cubano")),
    ("seafood", "Pescados y mariscos", ("Salmón al horno", "Salmón a la plancha", "Salmón con limón y ajo", "Tilapia al horno", "Filete de pescado empanizado", "Pescado a la plancha", "Tacos de pescado", "Ceviche", "Camarones al ajillo", "Camarones empanizados", "Camarones con arroz", "Pasta con camarones", "Salteado de camarones", "Paella de mariscos", "Bowl de atún y garbanzos", "Ensalada de atún", "Croquetas de atún", "Sándwich de atún")),
    ("rice", "Arroces", ("Arroz blanco", "Arroz amarillo", "Arroz integral", "Arroz con pollo", "Arroz congrí", "Moros y cristianos", "Arroz con vegetales", "Arroz frito", "Arroz frito con pollo", "Arroz frito con camarones", "Arroz con salchichas", "Arroz con frijoles", "Arroz mexicano", "Arroz pilaf", "Risotto de hongos", "Risotto de pollo", "Paella", "Arroz con leche")),
    ("pasta", "Pastas y fideos", ("Espaguetis con salsa de tomate", "Espaguetis con albóndigas", "Espaguetis a la boloñesa", "Pasta Alfredo", "Pasta carbonara", "Pasta con pollo", "Pasta con camarones", "Pasta con vegetales", "Pasta al pesto", "Macarrones con queso", "Pasta primavera", "Lasaña de carne", "Lasaña de pollo", "Lasaña vegetariana", "Fettuccine Alfredo", "Raviolis con salsa", "Pad Thai", "Lo mein", "Fideos salteados", "Sopa de fideos")),
    ("soups", "Sopas, cremas y guisos", ("Sopa de pollo con fideos", "Sopa de vegetales", "Sopa de tomate", "Sopa de lentejas", "Sopa de frijoles", "Sopa de tortilla", "Sopa de res", "Sopa de garbanzos", "Crema de calabaza", "Crema de brócoli", "Crema de papa", "Crema de champiñones", "Crema de vegetales", "Chili con carne", "Guiso de pollo", "Guiso de res", "Lentejas guisadas", "Garbanzos guisados", "Ajiaco", "Potaje de frijoles negros")),
    ("bowls_salads", "Bowls", ("Bowl de pollo y arroz", "Bowl de pollo y vegetales", "Bowl de salmón", "Bowl de atún y garbanzos", "Burrito bowl", "Taco bowl", "Bowl mediterráneo", "Bowl vegetariano", "Bowl de quinoa", "Poke bowl")),
    ("bowls_salads", "Ensaladas", ("Ensalada César", "Ensalada César con pollo", "Ensalada griega", "Ensalada de pasta", "Ensalada de papa", "Ensalada de atún", "Ensalada de garbanzos", "Ensalada de pollo", "Ensalada caprese", "Ensalada de aguacate", "Ensalada de quinoa", "Ensalada mixta")),
    ("vegetarian", "Vegetarianas", ("Tacos de vegetales", "Burrito vegetariano", "Hamburguesa vegetariana", "Curry de garbanzos", "Lentejas con arroz", "Pasta con vegetales", "Lasaña vegetariana", "Arroz frito vegetariano", "Quesadillas de vegetales", "Chili vegetariano", "Berenjena parmesana", "Vegetales salteados", "Falafel", "Hummus con vegetales", "Bowl de quinoa", "Sopa de lentejas", "Pizza de vegetales", "Champiñones rellenos")),
    ("baked", "Pizzas", ("Pizza margarita", "Pizza de pepperoni", "Pizza de queso", "Pizza de jamón", "Pizza hawaiana", "Pizza de pollo BBQ", "Pizza de vegetales", "Pizza de champiñones", "Pizza blanca", "Pizza de pan francés", "Pizza con pan de ajo", "Rollitos de pizza", "Calzone", "Stromboli")),
    ("baked", "Panes y masas", ("Pan blanco", "Pan integral", "Pan cubano", "Pan de ajo", "Pan de queso", "Focaccia", "Ciabatta", "Brioche", "Pan de banana", "Pan de maíz", "Bollitos", "Pretzels", "Empanadas", "Pastelitos", "Croissants", "Masa básica de pizza")),
    ("baked", "Gratines y platos de horno", ("Lasaña", "Ziti al horno", "Macarrones gratinados", "Pollo gratinado", "Papas gratinadas", "Pastel de papa", "Pastel de carne", "Vegetales al horno", "Salmón al horno", "Pollo con papas al horno")),
    ("sides_sauces", "Acompañamientos y salsas", ("Puré de papas", "Papas fritas", "Papas al horno", "Papas asadas", "Yuca con mojo", "Plátanos maduros", "Tostones", "Vegetales al vapor", "Vegetales asados", "Frijoles negros", "Arroz blanco", "Ensalada mixta", "Salsa de tomate", "Salsa Alfredo", "Pesto", "Chimichurri", "Mojo cubano", "Pico de gallo", "Guacamole", "Aderezo César", "Salsa BBQ")),
    ("desserts", "Postres", ("Flan", "Arroz con leche", "Tres leches", "Natilla", "Cheesecake", "Pastel de chocolate", "Pastel de vainilla", "Pastel de zanahoria", "Brownies", "Galletas con chocolate", "Galletas de avena", "Cupcakes", "Tiramisú", "Pudín de pan", "Churros", "Donas", "Helado casero", "Mousse de chocolate", "Pie de manzana", "Pie de limón", "Frutas con yogur", "Banana bread")),
    ("coffee_hot", "Cafés calientes", ("Café espresso", "Café americano", "Café cubano", "Cortadito", "Café con leche", "Cappuccino", "Latte", "Mocha", "Macchiato", "Flat white", "Café de olla", "Café con dulce de leche", "Pumpkin spice latte", "Café con canela")),
    ("coffee_hot", "Cafés fríos", ("Café helado", "Cold brew", "Iced latte", "Iced mocha", "Frappé de café", "Frappé de mocha", "Café helado con vainilla", "Café helado con caramelo", "Affogato", "Smoothie de café")),
    ("coffee_hot", "Sin café", ("Chocolate caliente", "Matcha latte", "Chai latte", "Golden milk", "Té con limón", "Té de jengibre", "Té helado", "Leche caliente con canela")),
    ("juices", "Jugos naturales", ("Jugo de naranja", "Jugo de manzana", "Jugo de piña", "Jugo de mango", "Jugo de guayaba", "Jugo de papaya", "Jugo de sandía", "Jugo de melón", "Jugo de fresa", "Jugo de zanahoria", "Jugo de remolacha", "Jugo verde", "Jugo de piña y pepino", "Jugo de naranja y zanahoria", "Jugo de mango y naranja", "Jugo de fresa y limón")),
    ("juices", "Limonadas y aguas", ("Limonada tradicional", "Limonada de fresa", "Limonada de coco", "Limonada con menta", "Agua de pepino y limón", "Agua de jamaica", "Agua de horchata", "Agua de sandía", "Té helado con limón", "Té dulce", "Piña colada sin alcohol", "Mojito sin alcohol")),
    ("smoothies", "Batidos y smoothies", ("Batido de fresa", "Batido de chocolate", "Batido de vainilla", "Batido de mango", "Batido de guayaba", "Batido de mamey", "Batido de papaya", "Smoothie de fresa y banana", "Smoothie de mango y piña", "Smoothie de naranja y banana", "Smoothie verde", "Smoothie de frutos rojos", "Smoothie de avena y banana", "Smoothie de café", "Smoothie de mantequilla de maní", "Smoothie de proteína", "Smoothie de yogur y frutas", "Smoothie bowl de açaí")),
)


def _slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def infer_recipe_category(title: str, kind: str = "meal", drink_type: str = "") -> str:
    """Place remote or user-created recipes in the same installed taxonomy."""
    text = _slug(title).replace("_", " ")
    if drink_type == "alcoholic":
        return "cocktails"
    if kind == "drink":
        if re.search(r"\b(cafe|espresso|latte|mocha|cappuccino|te|chocolate|matcha|chai)\b", text):
            return "coffee_hot"
        if re.search(r"\b(batido|smoothie|frappe)\b", text):
            return "smoothies"
        return "juices"
    if kind == "dessert" or re.search(r"\b(flan|pastel|tarta|pie|galleta|brownie|helado|mousse|tiramisu|churro|dona|natilla)\b", text):
        return "desserts"
    if kind == "bread" or re.search(r"\b(pizza|pan|focaccia|ciabatta|brioche|croissant|calzone|stromboli|horno|gratin)\b", text):
        return "baked"
    if re.search(r"\b(desayuno|huevo|avena|yogur|pancake|waffle|tostada|crepe|granola)\b", text):
        return "breakfast"
    if re.search(r"\b(pollo|alita)\b", text):
        return "chicken"
    if re.search(r"\b(salmon|pescado|camaron|atun|ceviche|marisco|tilapia)\b", text):
        return "seafood"
    if re.search(r"\b(arroz|risotto|paella|congri)\b", text):
        return "rice"
    if re.search(r"\b(pasta|espagueti|lasana|fideo|ravioli|macarron|pad thai|lo mein)\b", text):
        return "pasta"
    if re.search(r"\b(sopa|crema|guiso|potaje|ajiaco|chili)\b", text):
        return "soups"
    if re.search(r"\b(bowl|ensalada|poke)\b", text):
        return "bowls_salads"
    if re.search(r"\b(vegetarian|vegetal|garbanzo|lenteja|falafel|hummus|quinoa|berenjena)\b", text):
        return "vegetarian"
    if re.search(r"\b(salsa|pure|papa|yuca|toston|guacamole|chimichurri|mojo|aderezo)\b", text):
        return "sides_sauces"
    return "meat"


def _ingredient(name: str, quantity: float, unit: str, notes: str = "") -> dict[str, Any]:
    return {"name": name, "quantity": quantity, "unit": unit, "notes": notes}


CHARACTERISTIC_INGREDIENTS: tuple[tuple[str, tuple[str, float, str]], ...] = (
    ("huevos benedict", ("Muffin inglés, jamón y salsa holandesa", 2, "porción")),
    ("tortilla espanola", ("Papas y cebolla", 600, "gramo")),
    ("shakshuka", ("Tomate, pimiento y especias", 3, "taza")),
    ("mantequilla de mani", ("Mantequilla de maní", 2, "cucharada")),
    ("miel y mostaza", ("Miel y mostaza", 3, "cucharada")),
    ("dulce de leche", ("Dulce de leche", 2, "cucharada")),
    ("frutos rojos", ("Frutos rojos", 1, "taza")),
    ("jamon y queso", ("Jamón y queso", 150, "gramo")),
    ("limon y ajo", ("Limón y ajo", 1, "porción")),
    ("pina y pepino", ("Piña y pepino", 3, "taza")),
    ("naranja y zanahoria", ("Naranja y zanahoria", 4, "unidad")),
    ("mango y naranja", ("Mango y naranja", 3, "taza")),
    ("fresa y limon", ("Fresa y limón", 3, "taza")),
    ("fresa y banana", ("Fresa y banana", 3, "taza")),
    ("mango y pina", ("Mango y piña", 3, "taza")),
    ("naranja y banana", ("Naranja y banana", 3, "taza")),
    ("yogur y frutas", ("Yogur y frutas", 2, "taza")),
    ("arroz con leche", ("Leche y canela", 4, "taza")),
    ("tres leches", ("Mezcla de tres leches", 3, "taza")),
    ("pico de gallo", ("Tomate, cebolla y cilantro", 2, "taza")),
    ("cesar", ("Lechuga romana y aderezo César", 1, "porción")),
    ("griega", ("Pepino, tomate, aceitunas y feta", 3, "taza")),
    ("caprese", ("Tomate, mozzarella y albahaca", 3, "taza")),
    ("boloñesa", ("Carne molida y tomate", 500, "gramo")),
    ("carbonara", ("Huevo, queso y panceta", 1, "porción")),
    ("paella", ("Azafrán, mariscos y vegetales", 1, "porción")),
    ("teriyaki", ("Salsa teriyaki", .5, "taza")),
    ("alfredo", ("Crema y queso parmesano", 2, "taza")),
    ("pesto", ("Albahaca, piñones y parmesano", 1, "taza")),
    ("pasta", ("Pasta", 400, "gramo")),
    ("curry", ("Curry y leche de coco", 2, "taza")),
    ("agridulce", ("Salsa agridulce", 1, "taza")),
    ("bbq", ("Salsa BBQ", 1, "taza")),
    ("parmesan", ("Queso parmesano", 1, "taza")),
    ("parmesano", ("Queso parmesano", 1, "taza")),
    ("empanizado", ("Pan rallado", 2, "taza")),
    ("pepperoni", ("Pepperoni", 150, "gramo")),
    ("hawaiana", ("Jamón y piña", 2, "taza")),
    ("champinon", ("Champiñones", 300, "gramo")),
    ("hongos", ("Hongos", 300, "gramo")),
    ("vegetal", ("Vegetales variados", 3, "taza")),
    ("garbanzo", ("Garbanzos", 2, "taza")),
    ("lenteja", ("Lentejas", 2, "taza")),
    ("frijol", ("Frijoles", 2, "taza")),
    ("quinoa", ("Quinoa", 2, "taza")),
    ("aguacate", ("Aguacate", 2, "unidad")),
    ("banana", ("Banana", 2, "unidad")),
    ("manzana", ("Manzana", 2, "unidad")),
    ("fresa", ("Fresa", 2, "taza")),
    ("mango", ("Mango", 2, "taza")),
    ("guayaba", ("Guayaba", 2, "taza")),
    ("mamey", ("Mamey", 2, "taza")),
    ("papaya", ("Papaya", 2, "taza")),
    ("sandia", ("Sandía", 4, "taza")),
    ("melon", ("Melón", 4, "taza")),
    ("pina", ("Piña", 3, "taza")),
    ("naranja", ("Naranja", 6, "unidad")),
    ("zanahoria", ("Zanahoria", 4, "unidad")),
    ("remolacha", ("Remolacha", 2, "unidad")),
    ("chocolate", ("Chocolate o cacao", .5, "taza")),
    ("vainilla", ("Vainilla", 1, "cucharadita")),
    ("canela", ("Canela", 1, "cucharadita")),
    ("calabaza", ("Calabaza", 700, "gramo")),
    ("brocoli", ("Brócoli", 500, "gramo")),
    ("papa", ("Papas", 700, "gramo")),
    ("tomate", ("Tomate", 500, "gramo")),
    ("camaron", ("Camarones", 600, "gramo")),
    ("salmon", ("Salmón", 600, "gramo")),
    ("atun", ("Atún", 2, "lata")),
    ("pollo", ("Pollo", 700, "gramo")),
    ("jamon", ("Jamón", 150, "gramo")),
    ("queso", ("Queso", 200, "gramo")),
)


def _add_characteristic_ingredients(title: str, ingredients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = _slug(title).replace("_", " ")
    existing = {_slug(row["name"]) for row in ingredients}
    enriched = list(ingredients)
    for phrase, ingredient in CHARACTERISTIC_INGREDIENTS:
        if phrase in normalized and _slug(ingredient[0]) not in existing:
            enriched.append(_ingredient(*ingredient))
            existing.add(_slug(ingredient[0]))
    return enriched


def _base_for(category: str, title: str) -> tuple[str, float, list[dict[str, Any]], list[str]]:
    """Return a safe, practical local base. Titles add the characteristic ingredient."""
    lower = _slug(title).replace("_", " ")
    if category == "breakfast":
        if any(word in lower for word in ("huevo", "omelette", "tortilla", "shakshuka")):
            return "meal", 2, [_ingredient("Huevos", 4, "unidad"), _ingredient("Aceite de oliva", 1, "cucharada"), _ingredient("Sal", .25, "cucharadita")], ["Prepara y mide todos los ingredientes.", "Cocina los huevos a fuego medio hasta alcanzar el punto indicado por la receta.", "Ajusta la sal y sirve recién hecho."]
        if any(word in lower for word in ("avena", "yogur", "chia", "granola", "fruta", "parfait")):
            return "meal", 2, [_ingredient("Avena o granola", 1, "taza"), _ingredient("Leche o yogur", 1.5, "taza"), _ingredient("Fruta fresca", 1, "taza")], ["Mide los ingredientes.", "Combina la base cremosa con la avena o granola.", "Termina con fruta y sirve; refrigera si la receta es nocturna."]
        if any(word in lower for word in ("tostada", "sandwich")):
            return "meal", 2, [_ingredient("Pan", 4, "rebanada"), _ingredient("Aceite o mantequilla", 1, "cucharada")], ["Prepara la cubierta o el relleno.", "Tuesta el pan hasta que esté dorado.", "Monta la tostada o sándwich y sirve de inmediato."]
        return "meal", 4, [_ingredient("Harina", 1, "taza"), _ingredient("Leche", 1, "taza"), _ingredient("Huevo", 1, "unidad")], ["Mezcla los ingredientes hasta que no queden grumos grandes.", "Cocina por porciones sobre una superficie caliente.", "Dora por ambos lados y sirve."]
    if category == "chicken":
        return "meal", 4, [_ingredient("Pollo", 700, "gramo"), _ingredient("Ajo", 2, "diente"), _ingredient("Aceite de oliva", 1, "cucharada"), _ingredient("Sal", .5, "cucharadita")], ["Seca, corta y sazona el pollo.", "Cocínalo con el método indicado hasta dorar.", "Comprueba que el centro alcance 74 °C y deja reposar antes de servir."]
    if category == "meat":
        protein = "Cerdo" if any(word in lower for word in ("cerdo", "lechon", "chuleta", "costilla", "lomo", "cubano")) else "Carne de res"
        return "meal", 4, [_ingredient(protein, 700, "gramo"), _ingredient("Cebolla", 1, "unidad"), _ingredient("Ajo", 2, "diente"), _ingredient("Aceite", 1, "cucharada")], ["Corta y sazona la carne.", "Dórala por tandas y añade los aromáticos.", "Termina la cocción hasta que esté tierna y alcance una temperatura segura."]
    if category == "seafood":
        protein = "Camarones" if "camaron" in lower else "Atún" if "atun" in lower else "Pescado"
        return "meal", 4, [_ingredient(protein, 600, "gramo"), _ingredient("Limón", 1, "unidad"), _ingredient("Ajo", 2, "diente"), _ingredient("Aceite de oliva", 1, "cucharada")], ["Limpia y seca el pescado o marisco.", "Sazona y cocina con el método indicado.", "Sirve cuando esté opaco y completamente cocido; evita sobrecocinar."]
    if category == "rice":
        return ("dessert" if "leche" in lower else "meal"), 4, [_ingredient("Arroz", 2, "taza"), _ingredient("Líquido de cocción", 4, "taza"), _ingredient("Sal", .5, "cucharadita")], ["Enjuaga el arroz hasta que el agua salga clara.", "Añade el líquido y los ingredientes característicos; lleva a ebullición.", "Tapa, cocina a fuego bajo y deja reposar antes de servir."]
    if category == "pasta":
        return "meal", 4, [_ingredient("Pasta o fideos", 400, "gramo"), _ingredient("Salsa o caldo", 2, "taza"), _ingredient("Aceite de oliva", 1, "cucharada")], ["Prepara la salsa o el caldo de la receta.", "Cocina la pasta hasta que esté al dente.", "Combina, ajusta la sazón y sirve caliente."]
    if category == "soups":
        return "meal", 4, [_ingredient("Caldo", 1, "litro"), _ingredient("Vegetales", 3, "taza"), _ingredient("Cebolla", 1, "unidad"), _ingredient("Aceite", 1, "cucharada")], ["Corta los ingredientes en tamaños parejos.", "Sofríe los aromáticos y añade el caldo.", "Cocina suavemente hasta que todo esté tierno; tritura si es una crema."]
    if category in {"bowls_salads", "vegetarian"}:
        return "meal", 4, [_ingredient("Vegetales variados", 4, "taza"), _ingredient("Proteína vegetal o base", 2, "taza"), _ingredient("Aderezo", .5, "taza")], ["Lava y corta todos los vegetales.", "Cocina la base o proteína que lo necesite.", "Distribuye en porciones, añade el aderezo y sirve."]
    if category == "baked":
        baked_kind = "bread" if re.search(r"\b(pizza|pan|focaccia|ciabatta|brioche|bollito|pretzel|empanada|pastelito|croissant|masa|calzone|stromboli|rollito)\b", lower) else "meal"
        if baked_kind == "meal":
            return "meal", 6, [_ingredient("Ingrediente principal", 800, "gramo"), _ingredient("Crema o salsa", 2, "taza"), _ingredient("Queso para gratinar", 1, "taza")], ["Prepara el ingrediente principal y calienta el horno.", "Distribuye en una fuente con la salsa y el queso.", "Hornea hasta que el centro esté cocido y la superficie dorada."]
        return baked_kind, 6, [_ingredient("Harina", 3, "taza"), _ingredient("Agua tibia", 1, "taza"), _ingredient("Levadura", 7, "gramo"), _ingredient("Sal", 1, "cucharadita")], ["Mezcla y amasa hasta obtener una masa lisa.", "Deja reposar cubierta hasta que aumente de volumen.", "Forma, añade la cubierta correspondiente y hornea hasta dorar."]
    if category == "sides_sauces":
        return "meal", 4, [_ingredient("Ingrediente principal", 500, "gramo"), _ingredient("Aceite de oliva", 2, "cucharada"), _ingredient("Sal", .5, "cucharadita")], ["Prepara el ingrediente principal.", "Cocina o mezcla con los aromáticos de la receta.", "Ajusta textura y sazón antes de servir."]
    if category == "desserts":
        return "dessert", 8, [_ingredient("Harina o base", 2, "taza"), _ingredient("Azúcar", .75, "taza"), _ingredient("Leche", 1, "taza"), _ingredient("Huevos", 2, "unidad")], ["Mide y prepara todos los ingredientes.", "Mezcla la base siguiendo el orden indicado.", "Cocina u hornea hasta el punto correcto y deja enfriar antes de servir."]
    if category == "coffee_hot":
        return "drink", 1, [_ingredient("Café, té o cacao", 1, "porción"), _ingredient("Agua o leche", 1, "taza")], ["Prepara la base de la bebida.", "Añade leche, hielo o especias según corresponda.", "Mezcla y sirve a la temperatura adecuada."]
    if category == "juices":
        return "drink", 4, [_ingredient("Fruta fresca", 4, "taza"), _ingredient("Agua", 2, "taza"), _ingredient("Hielo", 2, "taza")], ["Lava y corta la fruta.", "Licúa o exprime con el agua.", "Cuela si lo deseas, añade hielo y sirve."]
    return "drink", 2, [_ingredient("Fruta", 2, "taza"), _ingredient("Leche, yogur o agua", 1.5, "taza"), _ingredient("Hielo", 1, "taza")], ["Coloca todos los ingredientes en la licuadora.", "Licúa hasta obtener una textura uniforme.", "Ajusta la consistencia y sirve inmediatamente."]


@lru_cache(maxsize=1)
def installed_recipe_templates() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for category, subcategory, titles in GROUPS:
        for title in titles:
            key = f"installed_{_slug(title)}"
            if key in rows:
                continue
            kind, servings, ingredients, steps = _base_for(category, title)
            ingredients = _add_characteristic_ingredients(title, ingredients)
            rows[key] = {
                "title": title,
                "description": f"Receta práctica de {title.lower()}, incluida en Roxy Home.",
                "kind": kind,
                "category": category,
                "subcategory": subcategory,
                "servings": servings,
                "ingredients": ingredients,
                "steps": steps,
                "drink_type": "non_alcoholic" if category in {"coffee_hot", "juices", "smoothies"} else "",
            }
    return rows
