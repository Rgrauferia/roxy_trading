from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from typing import Any


def _identity(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"[^a-z0-9]+", " ", normalized.encode("ascii", "ignore").decode("ascii").lower()).strip()


def _ingredient(name: str, quantity: float, unit: str, notes: str = "") -> dict[str, Any]:
    return {"name": name, "quantity": quantity, "unit": unit, "notes": notes}


def _templates() -> dict[str, dict[str, Any]]:
    return {
        "bread": {
            "title": "Pan casero sencillo",
            "description": "Pan de miga tierna y corteza dorada preparado con ingredientes básicos.",
            "kind": "bread", "servings": 8,
            "ingredients": [_ingredient("Harina de trigo", 500, "gramo"), _ingredient("Agua tibia", 325, "mililitro"), _ingredient("Levadura seca", 7, "gramo"), _ingredient("Sal", 10, "gramo"), _ingredient("Aceite", 1, "cucharada")],
            "steps": ["Mezcla la harina con la levadura y la sal.", "Añade el agua y el aceite; amasa de 8 a 10 minutos.", "Cubre la masa y déjala crecer hasta duplicar su volumen, aproximadamente una hora.", "Forma el pan y déjalo reposar 30 minutos mientras calientas el horno a 220 °C.", "Hornea entre 25 y 30 minutos y deja enfriar antes de cortar."],
        },
        "pasta": {
            "title": "Pasta rápida con tomate y ajo", "description": "Una comida cotidiana, rápida y adaptable.",
            "kind": "meal", "servings": 2,
            "ingredients": [_ingredient("Pasta", 200, "gramo"), _ingredient("Tomate triturado", 400, "gramo"), _ingredient("Ajo", 2, "diente"), _ingredient("Aceite de oliva", 2, "cucharada"), _ingredient("Sal", 1, "cucharadita")],
            "steps": ["Hierve agua con sal y cocina la pasta hasta que esté al dente.", "Sofríe el ajo en el aceite durante un minuto.", "Añade el tomate y cocina a fuego medio durante 10 minutos.", "Escurre la pasta, mézclala con la salsa y sirve caliente."],
        },
        "chicken": {
            "title": "Pollo al ajo y limón", "description": "Pollo jugoso hecho en una sola sartén.",
            "kind": "meal", "servings": 2,
            "ingredients": [_ingredient("Pechuga de pollo", 2, "unidad"), _ingredient("Ajo", 2, "diente"), _ingredient("Limón", 1, "unidad"), _ingredient("Aceite", 1, "cucharada"), _ingredient("Sal", 0.5, "cucharadita")],
            "steps": ["Seca el pollo y sazónalo con sal.", "Calienta el aceite y cocina el pollo de 5 a 7 minutos por cada lado, hasta alcanzar 74 °C en el centro.", "Añade el ajo y cocina 30 segundos.", "Agrega el jugo de limón, deja reducir un minuto y sirve."],
        },
        "rice": {
            "title": "Arroz con vegetales", "description": "Arroz suelto con vegetales para una comida sencilla.",
            "kind": "meal", "servings": 3,
            "ingredients": [_ingredient("Arroz", 1, "taza"), _ingredient("Agua", 2, "taza"), _ingredient("Vegetales mixtos", 1, "taza"), _ingredient("Aceite", 1, "cucharada"), _ingredient("Sal", 0.5, "cucharadita")],
            "steps": ["Enjuaga el arroz hasta que el agua salga casi transparente.", "Sofríe los vegetales con el aceite durante 3 minutos.", "Añade el arroz, el agua y la sal; lleva a ebullición.", "Tapa y cocina a fuego bajo durante 18 minutos; reposa 5 minutos antes de soltarlo con un tenedor."],
        },
        "soup": {
            "title": "Sopa casera de vegetales", "description": "Sopa reconfortante con productos básicos.",
            "kind": "meal", "servings": 4,
            "ingredients": [_ingredient("Papa", 2, "unidad"), _ingredient("Zanahoria", 2, "unidad"), _ingredient("Cebolla", 1, "unidad"), _ingredient("Caldo", 1, "litro"), _ingredient("Aceite", 1, "cucharada")],
            "steps": ["Corta todos los vegetales en trozos similares.", "Sofríe la cebolla con el aceite durante 4 minutos.", "Añade la papa, la zanahoria y el caldo.", "Cocina suavemente de 20 a 25 minutos, hasta que los vegetales estén tiernos; ajusta la sal."],
        },
        "salad": {
            "title": "Ensalada fresca de aguacate y tomate", "description": "Ensalada rápida para acompañar cualquier comida.",
            "kind": "meal", "servings": 2,
            "ingredients": [_ingredient("Aguacate", 1, "unidad"), _ingredient("Tomate", 2, "unidad"), _ingredient("Pepino", 1, "unidad"), _ingredient("Limón", 1, "unidad"), _ingredient("Aceite de oliva", 1, "cucharada")],
            "steps": ["Lava y corta el tomate y el pepino.", "Corta el aguacate justo antes de servir.", "Mezcla todo con limón y aceite; sazona al gusto y sirve inmediatamente."],
        },
        "dessert": {
            "title": "Arroz con leche clásico", "description": "Postre cremoso con canela.",
            "kind": "dessert", "servings": 6,
            "ingredients": [_ingredient("Arroz", 1, "taza"), _ingredient("Leche", 4, "taza"), _ingredient("Azúcar", 0.5, "taza"), _ingredient("Canela", 1, "rama"), _ingredient("Vainilla", 1, "cucharadita")],
            "steps": ["Enjuaga el arroz y colócalo con la leche y la canela en una olla.", "Cocina a fuego bajo, removiendo con frecuencia, de 30 a 35 minutos.", "Añade el azúcar y la vainilla; cocina 5 minutos más.", "Retira la canela y sirve tibio o frío."],
        },
        "smoothie": {
            "title": "Batido de plátano", "description": "Bebida cremosa sin alcohol.",
            "kind": "drink", "drink_type": "non_alcoholic", "servings": 2,
            "ingredients": [_ingredient("Plátano", 2, "unidad"), _ingredient("Leche", 1.5, "taza"), _ingredient("Hielo", 1, "taza"), _ingredient("Vainilla", 0.5, "cucharadita")],
            "steps": ["Coloca todos los ingredientes en la licuadora.", "Licúa hasta obtener una textura homogénea.", "Sirve inmediatamente."],
        },
        "lemonade": {
            "title": "Limonada fresca", "description": "Bebida cítrica sin alcohol.",
            "kind": "drink", "drink_type": "non_alcoholic", "servings": 4,
            "ingredients": [_ingredient("Limón", 4, "unidad"), _ingredient("Agua", 4, "taza"), _ingredient("Azúcar", 0.33, "taza"), _ingredient("Hielo", 2, "taza")],
            "steps": ["Exprime los limones.", "Disuelve el azúcar en una taza de agua.", "Mezcla el jugo, el agua restante y el jarabe.", "Añade hielo y prueba antes de ajustar el dulzor."],
        },
        "cocktail": {
            "title": "Mojito clásico", "description": "Cóctel para adultos; incluye alternativa sin alcohol.",
            "kind": "drink", "drink_type": "alcoholic", "servings": 1,
            "ingredients": [_ingredient("Ron blanco", 50, "mililitro"), _ingredient("Limón", 1, "unidad"), _ingredient("Hierbabuena", 8, "hoja"), _ingredient("Azúcar", 2, "cucharadita"), _ingredient("Agua con gas", 100, "mililitro"), _ingredient("Hielo", 1, "taza")],
            "steps": ["Machaca suavemente la hierbabuena con el azúcar y el jugo de limón.", "Añade hielo y ron; completa con agua con gas.", "Remueve y sirve. Para la versión sin alcohol, omite el ron y aumenta el agua con gas."],
        },
    }


def generate_local_recipe(prompt: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return a transparent, curated recipe when the external AI is unavailable."""
    query = _identity(prompt)
    if re.search(r"\b(mojito|coctel|cocktail|ron|vodka|tequila|whisky|alcoholica|para adultos)\b", query):
        key = "cocktail"
    elif re.search(r"\b(batido|smoothie|licuado)\b", query):
        key = "smoothie"
    elif re.search(r"\b(bebida|jugo|zumo|limonada|refresco)\b", query):
        key = "lemonade"
    elif re.search(r"\b(pan|baguette|focaccia|brioche|masa)\b", query):
        key = "bread"
    elif re.search(r"\b(pasta|espagueti|espaguetis|spaghetti|macarron|macarrones|fideo|fideos|lasana)\b", query):
        key = "pasta"
    elif re.search(r"\b(pollo|pechuga)\b", query):
        key = "chicken"
    elif re.search(r"\b(arroz)\b", query):
        key = "rice"
    elif re.search(r"\b(sopa|caldo|crema)\b", query):
        key = "soup"
    elif re.search(r"\b(ensalada|aguacate)\b", query):
        key = "salad"
    elif re.search(r"\b(postre|dulce|flan|pastel|tarta)\b", query):
        key = "dessert"
    else:
        key = "chicken"

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
