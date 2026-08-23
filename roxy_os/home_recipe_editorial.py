"""Editorial completion for Roxy Home's installed cookbook.

The installed catalog is deliberately deterministic and offline.  This module
turns the compact catalog entries into usable recipes: concrete ingredients,
ordered actions, times, temperatures and observable doneness cues.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _plain(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"[^a-z0-9]+", " ", normalized.encode("ascii", "ignore").decode("ascii").lower()).strip()


def _ingredient(name: str, quantity: float, unit: str, notes: str = "") -> dict[str, Any]:
    return {"name": name, "quantity": quantity, "unit": unit, "notes": notes}


FRUITS = ("naranja", "manzana", "piña", "mango", "guayaba", "papaya", "sandía", "melón", "fresa", "zanahoria", "remolacha", "limón", "maracuyá", "tamarindo", "durazno", "banana", "coco", "aguacate", "açaí")


def _named_fruit(title: str, default: str = "Fresa") -> str:
    plain = _plain(title)
    for fruit in FRUITS:
        if _plain(fruit) in plain:
            return fruit.capitalize()
    return default


def _replacement(name: str, title: str, category: str) -> list[dict[str, Any]]:
    key = _plain(name)
    lower = _plain(title)
    direct: dict[str, list[dict[str, Any]]] = {
        "crema y queso parmesano": [_ingredient("Crema de leche", 1.5, "taza"), _ingredient("Queso parmesano rallado", 1, "taza")],
        "muffin ingles jamon y salsa holandesa": [_ingredient("Muffin inglés", 2, "unidad"), _ingredient("Jamón cocido", 4, "rebanada"), _ingredient("Salsa holandesa", .5, "taza")],
        "papas y cebolla": [_ingredient("Papa", 500, "gramo"), _ingredient("Cebolla", 1, "unidad")],
        "tomate pimiento y especias": [_ingredient("Tomate triturado", 400, "gramo"), _ingredient("Pimiento rojo", 1, "unidad"), _ingredient("Comino y pimentón", 1, "cucharadita")],
        "miel y mostaza": [_ingredient("Miel", 2, "cucharada"), _ingredient("Mostaza Dijon", 2, "cucharada")],
        "limon y ajo": [_ingredient("Limón", 1, "unidad"), _ingredient("Ajo", 2, "diente")],
        "jamon y queso": [_ingredient("Jamón cocido", 100, "gramo"), _ingredient("Queso", 100, "gramo")],
        "leche y canela": [_ingredient("Leche entera", 4, "taza"), _ingredient("Canela", 1, "rama")],
        "mezcla de tres leches": [_ingredient("Leche evaporada", 1, "taza"), _ingredient("Leche condensada", 1, "taza"), _ingredient("Crema de leche", 1, "taza")],
        "tomate cebolla y cilantro": [_ingredient("Tomate", 3, "unidad"), _ingredient("Cebolla", .5, "unidad"), _ingredient("Cilantro", .25, "taza")],
        "lechuga romana y aderezo cesar": [_ingredient("Lechuga romana", 1, "unidad"), _ingredient("Aderezo César", .5, "taza")],
        "pepino tomate aceitunas y feta": [_ingredient("Pepino", 1, "unidad"), _ingredient("Tomate", 3, "unidad"), _ingredient("Aceitunas", .5, "taza"), _ingredient("Queso feta", 150, "gramo")],
        "tomate mozzarella y albahaca": [_ingredient("Tomate", 3, "unidad"), _ingredient("Mozzarella fresca", 250, "gramo"), _ingredient("Albahaca", .25, "taza")],
        "carne molida y tomate": [_ingredient("Carne molida", 500, "gramo"), _ingredient("Tomate triturado", 400, "gramo")],
        "huevo queso y panceta": [_ingredient("Huevo pasteurizado", 3, "unidad"), _ingredient("Queso pecorino o parmesano", 1, "taza"), _ingredient("Panceta", 150, "gramo")],
        "azafran mariscos y vegetales": [_ingredient("Azafrán", .25, "cucharadita"), _ingredient("Mariscos", 500, "gramo"), _ingredient("Pimiento rojo", 1, "unidad")],
        "curry y leche de coco": [_ingredient("Curry en polvo", 2, "cucharadita"), _ingredient("Leche de coco", 1, "lata")],
        "jamon y pina": [_ingredient("Jamón cocido", 150, "gramo"), _ingredient("Piña", 1.5, "taza")],
    }
    if key in direct:
        return direct[key]
    if key == "avena o granola":
        return [_ingredient("Granola", 1, "taza")] if "granola" in lower or "parfait" in lower else [_ingredient("Avena en hojuelas", 1, "taza")]
    if key == "leche o yogur":
        return [_ingredient("Yogur natural", 1.5, "taza")] if "yogur" in lower or "parfait" in lower else [_ingredient("Leche", 1.5, "taza")]
    if key == "aceite o mantequilla":
        return [_ingredient("Mantequilla", 1, "cucharada")]
    if key == "liquido de coccion":
        if "leche" in lower:
            return [_ingredient("Leche", 4, "taza")]
        if any(word in lower for word in ("risotto", "paella", "pollo", "jambalaya", "biryani")):
            return [_ingredient("Caldo bajo en sal", 4, "taza")]
        return [_ingredient("Agua", 4, "taza")]
    if key == "pasta o fideos":
        if "lasana" in lower:
            return [_ingredient("Láminas de lasaña", 12, "unidad")]
        if any(word in lower for word in ("fideo", "lo mein", "pad thai", "ramen")):
            return [_ingredient("Fideos", 400, "gramo")]
        return [_ingredient("Pasta seca", 400, "gramo")]
    if key == "salsa o caldo":
        if any(word in lower for word in ("sopa", "ramen", "minestrone")):
            return [_ingredient("Caldo bajo en sal", 1, "litro")]
        if "alfredo" in lower or "cuatro quesos" in lower:
            return [_ingredient("Crema de leche", 1.5, "taza")]
        return [_ingredient("Salsa de tomate", 2, "taza")]
    if key in {"vegetales", "vegetales variados", "vegetales mixtos"}:
        return [_ingredient("Pimiento rojo", 1, "unidad"), _ingredient("Zanahoria", 2, "unidad"), _ingredient("Calabacín", 1, "unidad")]
    if key == "proteina vegetal o base":
        if "tofu" in lower:
            return [_ingredient("Tofu firme", 500, "gramo")]
        if "quinoa" in lower:
            return [_ingredient("Quinoa cocida", 2, "taza")]
        if "garbanzo" in lower or "hummus" in lower or "falafel" in lower:
            return [_ingredient("Garbanzos cocidos", 2, "taza")]
        return [_ingredient("Frijoles negros cocidos", 2, "taza")]
    if key == "ingrediente principal":
        if "papa" in lower:
            return [_ingredient("Papa", 800, "gramo")]
        if "pollo" in lower:
            return [_ingredient("Pechuga de pollo", 800, "gramo")]
        if "vegetal" in lower:
            return [_ingredient("Berenjena y calabacín", 800, "gramo")]
        return [_ingredient(title, 800, "gramo")]
    if key == "crema o salsa":
        return [_ingredient("Salsa bechamel", 2, "taza")]
    if key == "queso para gratinar":
        return [_ingredient("Queso mozzarella rallado", 1, "taza")]
    if key == "harina o base":
        return [_ingredient("Harina de trigo", 2, "taza")]
    if key == "cafe te o cacao":
        if "matcha" in lower:
            return [_ingredient("Matcha en polvo", 1, "cucharadita")]
        if "chai" in lower:
            return [_ingredient("Té chai", 1, "bolsita")]
        if re.search(r"\bte\b", lower):
            return [_ingredient("Té", 1, "bolsita")]
        if "golden milk" in lower:
            return [_ingredient("Cúrcuma molida", .5, "cucharadita")]
        if "chocolate" in lower:
            return [_ingredient("Cacao en polvo", 2, "cucharada")]
        return [_ingredient("Café molido", 2, "cucharada")]
    if key == "agua o leche":
        return [_ingredient("Leche", 1, "taza")] if any(word in lower for word in ("latte", "cappuccino", "mocha", "chocolate", "leche", "cortadito")) else [_ingredient("Agua", 1, "taza")]
    if key in {"fruta fresca", "fruta"}:
        if "horchata" in lower:
            return [_ingredient("Arroz blanco", 1, "taza"), _ingredient("Canela", 1, "rama")]
        if "jamaica" in lower:
            return [_ingredient("Flor de jamaica seca", 1, "taza")]
        if "jugo verde" in lower or "smoothie verde" in lower:
            return [_ingredient("Espinaca", 2, "taza"), _ingredient("Pepino", 1, "unidad"), _ingredient("Manzana verde", 1, "unidad")]
        if "apio" in lower:
            return [_ingredient("Apio", 6, "tallo")]
        if "jengibre" in lower:
            return [_ingredient("Jengibre fresco", 40, "gramo"), _ingredient("Limón", 1, "unidad")]
        if "ponche" in lower:
            return [_ingredient("Naranja", 2, "unidad"), _ingredient("Piña", 2, "taza"), _ingredient("Manzana", 1, "unidad")]
        if "proteina" in lower:
            return [_ingredient("Banana", 1, "unidad"), _ingredient("Proteína en polvo", 1, "medida")]
        if "tropical" in lower:
            return [_ingredient("Mango", 1, "taza"), _ingredient("Piña", 1, "taza")]
        if "galleta" in lower:
            return [_ingredient("Galletas", 6, "unidad"), _ingredient("Banana", 1, "unidad")]
        return [_ingredient(_named_fruit(title), 4 if category == "juices" else 2, "taza")]
    if key == "leche yogur o agua":
        return [_ingredient("Leche", 1.5, "taza")]
    return [dict(name=name, quantity=0, unit="unidad", notes="")]  # replaced with original values by caller


def concretize_ingredients(title: str, category: str, ingredients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _plain(title) == "cafe cubano":
        # Canonical cafecito brewed in a moka pot.  Keep this separate from
        # café con leche, espresso, matcha and the rest of the hot-drink
        # family: they do not share ingredients or preparation technique.
        return [
            _ingredient("Agua", 1.25, "taza", "para la base de una cafetera moka"),
            _ingredient("Café espresso molido de tueste oscuro", 1 / 3, "taza", "sin compactarlo en el filtro"),
            _ingredient("Azúcar blanca", .25, "taza", "usa hasta 1/3 de taza si lo prefieres más dulce"),
        ]
    if _plain(title) == "avena con manzana":
        return [
            _ingredient("Avena en hojuelas", .5, "taza"),
            _ingredient("Leche o agua", 1, "taza"),
            _ingredient("Manzana", .5, "unidad", "picada en cubos pequeños"),
            _ingredient("Canela molida", .5, "cucharadita"),
            _ingredient("Miel o azúcar", 1, "cucharadita", "al gusto"),
        ]
    output: list[dict[str, Any]] = []
    for row in ingredients:
        replacement = _replacement(str(row.get("name") or ""), title, category)
        if len(replacement) == 1 and replacement[0]["quantity"] == 0:
            output.append(dict(row))
        else:
            output.extend(replacement)
    lower = _plain(title)
    additions: list[dict[str, Any]] = []
    if category == "breakfast" and "avena con manzana" in lower:
        additions = [_ingredient("Manzana", .5, "unidad"), _ingredient("Canela molida", .5, "cucharadita"), _ingredient("Miel", 1, "cucharadita", "o azúcar al gusto")]
    elif category == "breakfast" and any(word in lower for word in ("pancake", "waffle", "crepe")):
        additions = [_ingredient("Polvo de hornear", 2, "cucharadita"), _ingredient("Azúcar", 2, "cucharada"), _ingredient("Mantequilla", 2, "cucharada")]
    elif category == "breakfast" and any(word in lower for word in ("sandwich", "bagel", "burrito", "arepa")):
        additions = [_ingredient("Huevo", 2, "unidad"), _ingredient("Queso", 80, "gramo"), _ingredient("Pan, bagel, tortilla o arepa", 2, "unidad")]
    elif category == "breakfast" and "huevo" in lower:
        additions = [_ingredient("Pimienta negra", .25, "cucharadita")]
    elif category == "chicken" and "alfredo" in lower:
        additions = [_ingredient("Fettuccine", 400, "gramo"), _ingredient("Mantequilla", 2, "cucharada"), _ingredient("Pimienta negra", .25, "cucharadita")]
    elif category == "chicken" and "con arroz" in lower:
        additions = [_ingredient("Arroz de grano largo", 2, "taza"), _ingredient("Caldo de pollo", 4, "taza"), _ingredient("Cebolla", 1, "unidad"), _ingredient("Pimiento", 1, "unidad")]
    elif category == "chicken" and any(word in lower for word in ("taco", "fajita", "wrap", "enchilada")):
        additions = [_ingredient("Tortillas", 8, "unidad"), _ingredient("Pimiento", 2, "unidad"), _ingredient("Cebolla", 1, "unidad")]
    elif category == "chicken" and "sopa" in lower:
        additions = [_ingredient("Caldo de pollo", 1, "litro"), _ingredient("Zanahoria", 2, "unidad"), _ingredient("Apio", 2, "tallo")]
    elif category == "meat" and any(word in lower for word in ("taco", "fajita", "sandwich", "sloppy")):
        additions = [_ingredient("Tortillas o pan", 8, "unidad"), _ingredient("Pimiento", 1, "unidad")]
    elif category == "meat" and "lasana" in lower:
        additions = [_ingredient("Láminas de lasaña", 12, "unidad"), _ingredient("Salsa de tomate", 3, "taza"), _ingredient("Queso mozzarella", 300, "gramo")]
    elif category == "meat" and any(word in lower for word in ("albondiga", "hamburguesa", "pastel de carne")):
        additions = [_ingredient("Huevo", 1, "unidad"), _ingredient("Pan rallado", .75, "taza"), _ingredient("Sal", .5, "cucharadita")]
    elif category == "seafood" and "ceviche" in lower:
        additions = [_ingredient("Cebolla morada", .5, "unidad"), _ingredient("Cilantro", .25, "taza"), _ingredient("Ají", 1, "unidad")]
    elif category == "seafood" and "paella" in lower:
        additions = [_ingredient("Arroz de grano corto", 2, "taza"), _ingredient("Caldo de pescado", 4, "taza"), _ingredient("Tomate", 2, "unidad")]
    elif category == "seafood" and "pasta" in lower:
        additions = [_ingredient("Pasta seca", 400, "gramo"), _ingredient("Salsa de tomate o crema", 2, "taza")]
    elif category == "seafood" and "con arroz" in lower:
        additions = [_ingredient("Arroz", 2, "taza"), _ingredient("Caldo de pescado", 4, "taza"), _ingredient("Cebolla", 1, "unidad")]
    elif category == "seafood" and "croqueta" in lower:
        additions = [_ingredient("Huevo", 1, "unidad"), _ingredient("Pan rallado", 1, "taza"), _ingredient("Cebolla", .5, "unidad")]
    elif category == "pasta" and any(word in lower for word in ("lasana", "canelon", "ziti")):
        additions = [_ingredient("Queso mozzarella", 300, "gramo"), _ingredient("Queso ricotta", 300, "gramo"), _ingredient("Carne molida o vegetales", 500, "gramo")]
    elif category == "baked" and "pizza" in lower:
        additions = [_ingredient("Salsa de tomate", 1, "taza"), _ingredient("Queso mozzarella", 300, "gramo")]
    elif category == "baked" and any(word in lower for word in ("empanada", "pastelito")):
        additions = [_ingredient("Carne molida", 500, "gramo"), _ingredient("Cebolla", 1, "unidad"), _ingredient("Huevo", 1, "unidad")]
    elif category == "baked" and "croissant" in lower:
        additions = [_ingredient("Mantequilla fría", 250, "gramo"), _ingredient("Leche", 1, "taza")]
    elif category == "desserts" and any(word in lower for word in ("pastel", "cupcake", "banana bread")):
        additions = [_ingredient("Polvo de hornear", 2, "cucharadita"), _ingredient("Mantequilla", .5, "taza")]
    elif category == "coffee_hot" and any(word in lower for word in ("latte", "cappuccino", "flat white", "cortadito", "mocha")):
        additions = [_ingredient("Café espresso", 30, "mililitro")]
    elif category == "coffee_hot" and "affogato" in lower:
        additions = [_ingredient("Helado de vainilla", 1, "bola"), _ingredient("Café espresso", 30, "mililitro")]
    elif category == "juices" and "mojito sin alcohol" in lower:
        additions = [_ingredient("Hierbabuena", 10, "hoja"), _ingredient("Limón", 1, "unidad"), _ingredient("Agua con gas", 150, "mililitro")]
    existing = {_plain(row["name"]) for row in output}
    for row in additions:
        if _plain(row["name"]) not in existing:
            output.append(row)
            existing.add(_plain(row["name"]))
    return output


def _protein_finish(category: str, lower: str) -> str:
    if category == "chicken":
        return "hasta que la parte más gruesa alcance 74 °C; mide lejos del hueso"
    if category == "seafood":
        return "hasta 63 °C; el pescado debe verse opaco y los mariscos firmes"
    if any(word in lower for word in ("molida", "hamburguesa", "albondiga", "pastel de carne", "sloppy")):
        return "hasta que el centro alcance 71 °C"
    return "hasta que el centro alcance 63 °C y luego déjala reposar 3 minutos"


def detailed_steps(category: str, title: str, ingredients: list[dict[str, Any]]) -> list[str]:
    lower = _plain(title)
    ingredient_names = ", ".join(str(row.get("name") or "").strip() for row in ingredients if row.get("name"))
    if lower == "cafe cubano":
        return [
            "Desenrosca una cafetera moka limpia. Llena la cámara inferior con 1 1/4 tazas de agua, sin sobrepasar la válvula de seguridad.",
            "Coloca el embudo y llénalo con 1/3 de taza de café espresso molido de tueste oscuro; nivela la superficie sin prensar el café.",
            "Limpia cualquier grano del borde, enrosca bien la parte superior y pon la moka destapada a fuego medio.",
            "Coloca 1/4 de taza de azúcar en una jarrita resistente al calor. Cuando salgan las primeras gotas de café, retira aproximadamente media cucharada y viértela sobre el azúcar.",
            "Devuelve la moka al fuego. Bate enérgicamente el azúcar con esas primeras gotas durante 1 a 2 minutos, hasta formar una crema espesa de color beige claro llamada espumita.",
            "Retira la moka del fuego cuando el flujo se aclare y empiece a borbotear; cierra la tapa para evitar salpicaduras y no dejes que el café hierva.",
            "Vierte lentamente el café terminado sobre la espumita y remueve con suavidad hasta que una capa fina de espuma quede en la superficie.",
            "Reparte de inmediato en cuatro tacitas pequeñas de espresso, procurando que cada porción reciba un poco de espumita.",
        ]
    if title == "Pollo Alfredo":
        return [
            "Corta el pollo en filetes de grosor parejo, sécalo y sazónalo con sal y pimienta; pica finamente el ajo.",
            "Hierve 3 litros de agua con sal y cocina el fettuccine hasta que esté al dente; reserva 1 taza del agua y escurre.",
            "Calienta el aceite en una sartén grande a fuego medio-alto. Dora el pollo de 4 a 6 minutos por lado, hasta que alcance 74 °C; pásalo a un plato y déjalo reposar.",
            "Baja a fuego medio. Derrite la mantequilla en la misma sartén, añade el ajo y remueve 30 segundos sin dejar que se queme.",
            "Vierte la crema y cocina 2 minutos a hervor suave. Agrega el parmesano poco a poco, removiendo hasta obtener una salsa lisa; afina con agua de la pasta si queda espesa.",
            "Incorpora el fettuccine, mezcla durante 1 minuto y ajusta sal y pimienta. Rebana el pollo, colócalo encima y sirve inmediatamente.",
        ]
    if category == "breakfast":
        if "avena con manzana" in lower:
            return [
                "Pela media manzana y córtala en cubos pequeños de aproximadamente 1 cm.",
                "Vierte 1 taza de leche o agua en una olla pequeña y llévala a ebullición a fuego medio-alto.",
                "Añade 1/2 taza de avena en hojuelas y los cubos de manzana.",
                "Baja el fuego a medio-bajo en cuanto la mezcla vuelva a hervir.",
                "Cocina de 5 a 7 minutos y remueve cada minuto para que la avena no se pegue.",
                "Apaga el fuego cuando la avena esté cremosa y la manzana se pueda atravesar fácilmente con un tenedor.",
                "Sirve la avena en un tazón y espolvorea 1/2 cucharadita de canela.",
                "Termina con miel o azúcar al gusto y deja reposar 1 minuto antes de comer.",
            ]
        if "avena con leche y canela" in lower:
            return ["Vierte la leche en una olla pequeña y caliéntala a fuego medio hasta que comience a humear.", "Añade la avena en hojuelas y baja el fuego a medio-bajo.", "Cocina de 5 a 7 minutos, removiendo cada minuto para evitar que se pegue.", "Agrega la canela y mezcla durante 30 segundos.", "Apaga cuando la avena esté cremosa pero aún conserve algo de textura.", "Sirve en un tazón, endulza al gusto y deja reposar 1 minuto."]
        if "avena con banana" in lower:
            return ["Pela la banana; machaca una mitad y corta la otra en rodajas.", "Calienta la leche en una olla pequeña hasta que empiece a humear.", "Añade la avena y la banana machacada; baja a fuego medio-bajo.", "Cocina de 5 a 7 minutos y remueve cada minuto.", "Retira del fuego cuando la mezcla esté cremosa y añade la mantequilla de maní.", "Sirve en un tazón, coloca las rodajas de banana encima y deja reposar 1 minuto."]
        if "avena nocturna" in lower:
            return ["Lava la fruta, sécala y córtala en trozos pequeños.", "Coloca la avena, la leche y la mitad de la fruta en un frasco con tapa.", "Remueve durante 30 segundos hasta que toda la avena quede humedecida.", "Tapa el frasco y refrigera durante al menos 6 horas.", "Al día siguiente, remueve y añade 1 o 2 cucharadas de leche si está demasiado espesa.", "Termina con la fruta restante y sirve fría."]
        if "pudin de chia" in lower:
            return ["Vierte la leche en un frasco y añade las semillas de chía.", "Remueve durante 1 minuto para separar todas las semillas.", "Deja reposar 10 minutos y vuelve a remover para romper cualquier grumo.", "Tapa y refrigera durante al menos 4 horas.", "Comprueba que la mezcla tenga textura de pudín; añade una cucharada de leche si está muy firme.", "Sirve con la fruta por encima."]
        if "granola" in lower and "yogur" not in lower and "parfait" not in lower:
            return ["Calienta el horno a 160 °C y cubre una bandeja con papel de hornear.", "Mezcla la avena, los frutos secos, la canela y una pizca de sal.", "Añade miel y aceite; remueve hasta humedecer todas las hojuelas.", "Extiende la mezcla en una capa uniforme y presiónala ligeramente.", "Hornea de 22 a 28 minutos y remueve una vez a mitad de cocción.", "Enfría por completo en la bandeja antes de romperla y guardarla."]
        if any(word in lower for word in ("yogur", "parfait")):
            return ["Lava, seca y corta la fruta en trozos pequeños.", "Coloca la mitad del yogur en el fondo de un vaso o tazón.", "Añade la mitad de la fruta y una capa fina de granola.", "Repite las capas con el yogur y la fruta restantes.", "Termina con granola y miel justo antes de servir.", "Sirve inmediatamente para que la granola se mantenga crujiente."]
        if "bowl de frutas" in lower:
            return ["Lava toda la fruta bajo agua corriente y sécala.", "Pela la fruta que lo necesite y retira semillas y tallos.", "Corta cada fruta en piezas de tamaño parecido.", "Coloca primero las frutas firmes y después las más delicadas en un tazón.", "Añade unas gotas de limón y mezcla una sola vez.", "Sirve inmediatamente o refrigera tapado hasta 2 horas."]
        if "huevos hervidos" in lower:
            return ["Coloca los huevos en una olla y cúbrelos con 3 cm de agua fría.", "Lleva el agua a ebullición; apaga el fuego, tapa y deja 10 a 12 minutos para yemas firmes.", "Prepara un recipiente con agua y hielo.", "Pasa los huevos al agua helada durante 5 minutos para detener la cocción.", "Golpea suavemente la cáscara, pela bajo agua corriente y sazona al servir."]
        if any(word in lower for word in ("huevo", "omelette", "tortilla", "shakshuka", "quiche", "hash")):
            return ["Lava, corta y mide los vegetales y rellenos antes de encender el fuego.", "Calienta una sartén a fuego medio con el aceite; cocina los vegetales de 4 a 6 minutos hasta que estén tiernos.", "Bate los huevos con la sal durante 30 segundos para integrar claras y yemas.", f"Vierte los huevos y prepara {title.lower()} a fuego medio-bajo, manteniendo el relleno distribuido de manera uniforme.", "Cocina hasta que el huevo esté completamente cuajado y el centro alcance 71 °C.", "Retira del fuego, deja reposar 1 minuto y sirve caliente."]
        if any(word in lower for word in ("pancake", "waffle", "crepe")):
            return ["Mezcla harina, sal y polvo de hornear en un recipiente.", "Bate aparte leche y huevo; vierte sobre los secos y mezcla solo hasta desaparecer la harina visible.", "Deja reposar la masa 5 minutos mientras calientas la superficie de cocción.", "Engrasa ligeramente y vierte porciones iguales.", f"Cocina cada porción de {title.lower()} de 2 a 3 minutos por el primer lado y de 1 a 2 minutos por el segundo, hasta dorar.", "Mantén calientes las piezas terminadas y sírvelas con fruta o miel."]
        return ["Prepara el relleno y corta los ingredientes en porciones uniformes.", "Tuesta o calienta el pan, tortilla o arepa hasta que esté dorado por fuera.", "Cocina el huevo hasta que clara y yema estén firmes.", "Distribuye el relleno caliente y añade queso o vegetales.", "Cierra, cocina 1 minuto más para fundir el queso y corta por la mitad.", "Sirve de inmediato para conservar la textura crujiente."]
    if category == "chicken":
        finish = _protein_finish(category, lower)
        if "con arroz" in lower:
            return ["Seca el pollo, córtalo en piezas iguales y sazónalo; enjuaga el arroz hasta que el agua salga clara.", "Calienta aceite en una olla amplia y dora el pollo de 3 a 4 minutos por lado; pásalo a un plato limpio.", "Sofríe cebolla, ajo y pimiento durante 4 minutos; añade el arroz y remueve 1 minuto.", "Vierte el caldo medido, devuelve el pollo y lleva a ebullición.", "Tapa, baja el fuego y cocina de 18 a 22 minutos, hasta que el arroz absorba el líquido y el pollo alcance 74 °C.", "Apaga el fuego, reposa tapado 5 minutos, suelta el arroz con un tenedor y sirve."]
        if any(word in lower for word in ("guisado", "salsa", "curry", "tikka", "sopa", "marsala", "champinon")):
            return ["Seca el pollo, córtalo en piezas de tamaño parejo y sazónalo por todos los lados.", "Calienta el aceite en una olla a fuego medio-alto y dora el pollo por tandas, 3 a 4 minutos por lado; resérvalo.", "Baja a fuego medio y sofríe el ajo y los vegetales durante 4 minutos, raspando el fondo.", f"Añade los componentes líquidos de {title.lower()} medidos en la lista de ingredientes y lleva a hervor suave.", f"Devuelve el pollo, tapa parcialmente y cocina de 12 a 20 minutos, {finish}.", "Prueba la salsa, ajusta sal, deja reposar 3 minutos y sirve caliente."]
        if any(word in lower for word in ("horno", "asado", "alita", "empanizado", "parmesano", "cordon bleu")):
            return ["Calienta el horno a 200 °C y prepara una bandeja con papel de hornear.", f"Seca el pollo y cúbrelo con los condimentos de {title.lower()}.", "Distribuye las piezas sin amontonarlas y rocía con aceite.", "Hornea 15 minutos y voltea todas las piezas para que se doren de manera uniforme.", f"Continúa de 10 a 20 minutos, {finish}.", "Deja reposar 3 minutos antes de cortar o servir."]
        if any(word in lower for word in ("taco", "fajita", "wrap", "sandwich", "enchilada")):
            return ["Corta el pollo en tiras de 1 cm y sazónalo; corta cebolla y pimiento del mismo tamaño.", "Calienta una sartén amplia a fuego medio-alto con aceite.", "Cocina el pollo de 6 a 8 minutos, removiendo, hasta alcanzar 74 °C; retíralo.", "Saltea cebolla y pimiento de 4 a 5 minutos y vuelve a incorporar el pollo.", "Calienta las tortillas o el pan y reparte el relleno; añade salsa y queso.", "Enrolla o arma las porciones y sirve inmediatamente."]
        return ["Seca el pollo y córtalo en piezas de grosor uniforme; sazona con sal y pimienta.", f"Pica el ajo y mide todos los ingredientes de {title.lower()}: {ingredient_names}.", "Calienta el aceite en una sartén a fuego medio-alto.", "Dora el pollo de 4 a 6 minutos por lado sin moverlo durante los primeros minutos.", f"Añade el ajo y los ingredientes restantes, baja el fuego y cocina de 3 a 5 minutos, {finish}.", "Deja reposar el pollo 3 minutos, báñalo con los jugos de la sartén y sirve."]
    if category == "seafood":
        finish = _protein_finish(category, lower)
        if "ceviche" in lower:
            return ["Corta el pescado en cubos de 2 cm y mantenlo refrigerado mientras preparas los demás ingredientes.", "Escalda el pescado en agua a hervor suave de 2 a 3 minutos, hasta que esté opaco y alcance 63 °C.", "Pásalo a una bandeja limpia y enfríalo en el refrigerador durante 15 minutos.", "Mezcla jugo de limón, cebolla, cilantro y ají; incorpora el pescado frío con utensilios limpios.", "Refrigera de 20 a 30 minutos para integrar los sabores y sirve bien frío dentro de las siguientes 2 horas."]
        if "paella" in lower:
            return ["Calienta el caldo con el azafrán y mantenlo caliente sin hervir.", "Sofríe cebolla, ajo y pimiento en la paellera durante 5 minutos; añade tomate y cocina 3 minutos.", "Agrega el arroz y remueve 1 minuto; vierte el caldo caliente y distribuye el grano en una capa uniforme.", "Cocina 10 minutos a fuego medio sin remover y luego 8 minutos a fuego bajo.", "Coloca los mariscos sobre el arroz durante los últimos 5 a 8 minutos, hasta que el pescado alcance 63 °C y los camarones estén firmes, perlados y opacos.", "Retira del fuego, cubre 5 minutos y sirve con limón; desecha las conchas que no se hayan abierto."]
        if "pasta" in lower:
            return ["Hierve agua con sal y cuece la pasta hasta 1 minuto antes de quedar al dente; reserva una taza del agua.", "Seca y sazona los camarones o mariscos mientras se calienta aceite en una sartén amplia.", "Cocina el marisco de 1 a 2 minutos por lado, hasta que esté firme, perlado y opaco; resérvalo.", "Sofríe ajo 30 segundos, añade la salsa y cocina de 3 a 5 minutos a hervor suave.", "Incorpora la pasta con media taza del agua reservada y mezcla 1 minuto; devuelve el marisco solo para calentarlo.", "Ajusta sal y acidez, termina con hierbas y sirve inmediatamente."]
        if "con arroz" in lower:
            return ["Enjuaga el arroz; seca y sazona los camarones o el pescado.", "Sofríe cebolla, ajo y pimiento durante 4 minutos en una olla amplia.", "Añade el arroz y remueve 1 minuto; vierte el caldo, tapa y cocina a fuego bajo 12 minutos.", "Coloca el marisco sobre el arroz, vuelve a tapar y cocina de 5 a 7 minutos más.", "Comprueba que el pescado alcance 63 °C o que los camarones estén firmes, perlados y opacos.", "Reposa 5 minutos, suelta el arroz y sirve con limón."]
        if "atun" in lower and any(word in lower for word in ("ensalada", "sandwich", "bowl", "tostada")):
            return ["Escurre completamente el atún enlatado y desmenúzalo en un recipiente limpio.", "Lava, seca y corta los vegetales en piezas pequeñas.", "Mezcla el atún con limón y aceite hasta que quede húmedo pero no líquido.", "Añade los vegetales y mezcla suavemente para conservar su textura.", f"Monta {title.lower()} en el recipiente de servir.", "Sirve enseguida o mantén refrigerado y no lo dejes a temperatura ambiente más de 2 horas."]
        if "croqueta" in lower and "atun" in lower:
            return ["Escurre bien el atún y mézclalo con huevo, pan rallado, cebolla y condimentos.", "Refrigera la mezcla 15 minutos para que tome firmeza.", "Forma croquetas iguales y pásalas por una capa fina de pan rallado.", "Calienta aceite a fuego medio y cocina de 3 a 4 minutos por lado hasta dorar.", "Comprueba que el centro alcance 74 °C y pásalas a papel absorbente.", "Deja reposar 2 minutos y sirve con limón o salsa."]
        return ["Seca el pescado o marisco con papel y sazónalo por ambos lados.", "Prepara ajo, cebolla, limón y demás ingredientes antes de calentar la sartén.", "Calienta el aceite a fuego medio-alto y coloca las piezas sin amontonarlas.", "Dora el primer lado sin mover; voltea y agrega los aromáticos.", f"Termina la cocción {finish}; los camarones deben verse firmes, perlados y opacos.", "Pasa a un plato limpio y sirve inmediatamente con los jugos de cocción."]
    if category == "meat":
        finish = _protein_finish(category, lower)
        if any(word in lower for word in ("lasana", "pastel de carne")):
            return ["Calienta el horno a 190 °C y engrasa una fuente; prepara la salsa y el relleno de carne por separado.", "Cocina la carne molida desmenuzándola hasta que no queden zonas rosadas y alcance 71 °C; escurre el exceso de grasa.", "Para lasaña, alterna salsa, pasta, carne y queso; para pastel, mezcla la carne con huevo y pan rallado y forma una pieza uniforme.", "Cubre y hornea 30 minutos; destapa durante los últimos 15 minutos para dorar.", "Comprueba que el centro alcance 74 °C.", "Deja reposar 10 minutos antes de cortar para conservar la forma."]
        if any(word in lower for word in ("albondiga", "hamburguesa", "picadillo", "carne molida")):
            return ["Mantén la carne molida fría y mezcla solo con los condimentos hasta integrarlos, sin compactarla de más.", f"Forma porciones iguales para {title.lower()} y colócalas en una sartén caliente.", "Cocina a fuego medio-alto y gira las piezas para dorarlas uniformemente.", "Añade cebolla, ajo y tomate cuando la carne ya haya tomado color.", "Continúa hasta que no queden zonas rosadas y el centro alcance 71 °C.", "Deja reposar 3 minutos y sirve caliente."]
        if any(word in lower for word in ("guis", "ropa vieja", "mechada", "chili", "salsa", "desmenuzado", "sopa")):
            return ["Corta la proteína en piezas uniformes, sécala y sazónala.", "Calienta aceite en una olla y dora las piezas por tandas; reserva.", "Sofríe cebolla y ajo de 4 a 5 minutos y añade tomate, especias o salsa.", "Incorpora la proteína y suficiente caldo para cubrir parcialmente; lleva a hervor suave.", f"Tapa y cocina a fuego bajo hasta que esté tierna y segura, {finish}.", "Ajusta la sazón, deja reposar 3 minutos y sirve con la salsa."]
        if any(word in lower for word in ("taco", "fajita", "sandwich", "bowl", "ensalada", "tostada")):
            return ["Prepara primero tortillas, pan, arroz o vegetales y mantenlos listos para montar.", "Seca, sazona y corta la proteína en porciones uniformes.", "Calienta una sartén a fuego medio-alto y cocina la proteína sin amontonar.", f"Continúa la cocción {finish}; pásala a una tabla limpia.", "Corta o desmenuza la proteína y distribúyela sobre la base preparada.", "Añade vegetales y salsa, y sirve de inmediato."]
        return ["Seca la carne con papel y sazónala por ambos lados.", f"Mide los ingredientes de {title.lower()}: {ingredient_names}.", "Calienta el aceite a fuego medio-alto y coloca las piezas sin amontonarlas.", "Dora el primer lado sin mover; voltea y agrega el ajo y la cebolla.", f"Termina la cocción {finish}.", "Pasa a un plato limpio, deja reposar 3 minutos y sirve con los jugos de cocción."]
    if category == "rice":
        if "risotto" in lower:
            return ["Calienta el caldo y mantenlo a hervor muy suave.", f"Corta los ingredientes de {title.lower()} y sofríelos durante 4 minutos.", "Añade el arroz y tuéstalo 1 minuto, removiendo.", "Incorpora el caldo caliente de a un cucharón, esperando a que se absorba antes del siguiente.", "Cocina de 18 a 22 minutos hasta que el grano esté al dente y cremoso.", "Retira del fuego, añade queso o mantequilla, reposa 2 minutos y sirve."]
        if any(word in lower for word in ("frito", "chaufa")):
            return ["Usa arroz cocido y completamente frío; separa los granos con las manos limpias.", "Calienta un wok o sartén grande a fuego alto con aceite.", "Cocina huevo, proteína y vegetales por separado para no bajar la temperatura; reserva cada parte.", "Añade el arroz y saltéalo de 3 a 4 minutos hasta que esté bien caliente.", "Devuelve los ingredientes, agrega salsa de soja y mezcla 1 minuto.", "Comprueba que todo alcance 74 °C y sirve inmediatamente."]
        if "arroz con leche" in lower:
            return ["Enjuaga el arroz y colócalo en una olla con leche y canela.", "Lleva a hervor suave, baja el fuego y cocina 25 minutos, removiendo cada pocos minutos.", "Añade el azúcar cuando el arroz esté tierno para evitar que se endurezca.", "Cocina de 8 a 10 minutos más hasta que la mezcla cubra la cuchara.", "Retira la canela y reparte en recipientes limpios.", "Sirve tibio o enfría y refrigera dentro de 2 horas."]
        return ["Enjuaga el arroz en un colador hasta que el agua salga casi transparente.", f"Sofríe durante 4 minutos los ingredientes adicionales de {title.lower()}.", "Añade el arroz y remueve 1 minuto para cubrir los granos con aceite.", "Vierte el líquido medido, sazona y lleva a ebullición.", "Tapa, baja al mínimo y cocina sin destapar de 15 a 20 minutos.", "Apaga, reposa tapado 5 minutos y suelta los granos con un tenedor."]
    if category == "pasta":
        if any(word in lower for word in ("lasana", "canelon", "ziti al horno")):
            return ["Calienta el horno a 190 °C y engrasa una fuente para horno.", "Cuece la pasta hasta que quede flexible pero firme; escúrrela y sepárala para que no se pegue.", "Prepara la salsa y cocina por completo la carne o vegetales del relleno.", "Alterna capas uniformes de pasta, relleno, salsa y queso, terminando con salsa y queso.", "Cubre y hornea 25 minutos; destapa y hornea 15 minutos más, hasta que el centro alcance 74 °C.", "Deja reposar 10 minutos antes de cortar y servir."]
        if "sopa" in lower:
            return ["Corta los vegetales en piezas uniformes y lleva el caldo a hervor suave.", "Sofríe cebolla y ajo durante 4 minutos; añade los vegetales firmes.", "Vierte el caldo y cocina 10 minutos, hasta que los vegetales estén casi tiernos.", "Añade los fideos y cuécelos de 6 a 9 minutos, removiendo para que no se peguen.", "Comprueba que los fideos y vegetales estén tiernos y que la sopa hierva antes de servir.", "Ajusta sal, deja reposar 2 minutos y sirve caliente."]
        return ["Pon a hervir 4 litros de agua y añade sal cuando rompa el hervor.", "Prepara la salsa en una sartén amplia: sofríe los aromáticos y cocina sus ingredientes hasta integrarlos.", "Cuece la pasta hasta 1 minuto antes del tiempo del paquete; reserva 1 taza del agua y escurre.", "Pasa la pasta a la sartén y añade media taza del agua reservada.", "Mezcla a fuego medio de 1 a 2 minutos hasta que la salsa se adhiera; agrega más agua si hace falta.", "Ajusta sal y pimienta, añade queso o hierbas y sirve caliente."]
    if category == "soups":
        if "crema" in lower:
            return ["Lava, pela y corta los vegetales en cubos del mismo tamaño.", "Calienta el aceite en una olla y sofríe cebolla y ajo durante 4 minutos.", "Añade los vegetales y cocina 3 minutos, removiendo.", "Vierte el caldo, lleva a ebullición y baja el fuego.", "Cocina parcialmente tapado de 18 a 25 minutos, hasta que todo esté muy tierno.", "Tritura hasta obtener una crema lisa, vuelve a calentar, ajusta sal y sirve humeante."]
        return ["Lava, pela y corta los ingredientes en piezas del mismo tamaño.", "Calienta el aceite en una olla y sofríe cebolla y ajo durante 4 minutos.", "Añade los vegetales, legumbres o carne y cocina 3 minutos, removiendo.", "Vierte el caldo, lleva a ebullición y retira la espuma de la superficie.", "Baja el fuego y cocina parcialmente tapado de 20 a 35 minutos, hasta que todo esté tierno.", "Ajusta la sal, deja reposar 3 minutos y sirve humeante."]
    if category == "bowls_salads":
        return ["Lava y seca por completo hojas, frutas y vegetales; córtalos en piezas fáciles de comer.", "Cocina y enfría la base de arroz, quinoa, pasta o papa si la receta la incluye.", "Cocina la proteína por separado hasta su temperatura segura y déjala reposar antes de cortarla.", "Bate el aderezo en un recipiente hasta que quede emulsionado.", "Distribuye primero la base y luego vegetales, proteína y complementos sin mezclar en exceso.", "Añade el aderezo justo antes de servir para mantener la textura."]
    if category == "vegetarian":
        return ["Enjuaga las legumbres o granos y corta los vegetales en tamaños uniformes.", "Calienta aceite a fuego medio y sofríe cebolla, ajo y especias durante 3 minutos.", "Añade los vegetales más firmes y cocina 5 minutos antes de incorporar los más tiernos.", "Agrega la proteína vegetal y mezcla hasta cubrirla con los condimentos.", "Cocina de 8 a 12 minutos, hasta que los vegetales estén tiernos pero mantengan forma.", "Prueba, ajusta sal y acidez y sirve caliente."]
    if category == "baked":
        if "pizza" in lower or any(word in lower for word in ("calzone", "stromboli", "rollito")):
            return ["Mezcla harina, levadura, sal y agua tibia; amasa de 8 a 10 minutos hasta que la masa esté lisa.", "Cubre y deja fermentar de 60 a 90 minutos, hasta que casi duplique su volumen.", "Calienta el horno a 245 °C con la bandeja o piedra dentro durante 30 minutos.", "Estira la masa sobre papel de hornear y distribuye una capa fina de salsa, queso y coberturas.", "Hornea de 10 a 15 minutos, hasta que la base esté firme y el borde dorado.", "Deja reposar 3 minutos antes de cortar para que el queso se asiente."]
        if any(word in lower for word in ("pan", "focaccia", "ciabatta", "brioche", "bollito", "pretzel", "croissant", "nudo")):
            return ["Pesa la harina, el agua, la levadura y la sal; mezcla hasta no ver harina seca.", "Amasa de 8 a 12 minutos, hasta obtener una masa elástica que se estire sin romperse fácilmente.", "Cubre y deja fermentar en un lugar templado hasta que duplique su volumen, de 60 a 90 minutos.", "Desgasifica suavemente, forma las piezas y deja levar de nuevo entre 30 y 45 minutos.", "Calienta el horno a 200 °C y hornea hasta que la superficie esté dorada y el centro alcance unos 93 °C.", "Enfría sobre rejilla al menos 30 minutos antes de cortar."]
        if any(word in lower for word in ("empanada", "pastelito")):
            return ["Calienta el horno a 200 °C y cubre una bandeja con papel de hornear.", "Prepara el relleno y cocínalo por completo; déjalo enfriar para que no humedezca la masa.", "Estira la masa, corta discos iguales y coloca una porción de relleno en el centro sin sobrecargar.", "Humedece los bordes, dobla y sella firmemente con un tenedor; pincela con huevo.", "Hornea de 18 a 25 minutos, hasta que la masa esté inflada y bien dorada.", "Deja reposar 5 minutos antes de servir porque el relleno estará muy caliente."]
        return ["Calienta el horno a 190 °C y engrasa una fuente mediana.", f"Prepara por separado los ingredientes de {title.lower()}: {ingredient_names}.", "Distribuye capas uniformes y cubre con el queso rallado.", "Tapa con papel de aluminio y hornea 25 minutos.", "Destapa y hornea de 10 a 15 minutos más, hasta que el centro alcance 74 °C y la superficie dore.", "Deja reposar 10 minutos antes de cortar o servir."]
    if category == "sides_sauces":
        if any(word in lower for word in ("salsa", "pesto", "chimichurri", "mojo", "gallo", "guacamole", "aderezo")):
            return ["Lava, seca y pica finamente todos los ingredientes frescos.", "Mide aceite, ácido, sal y especias antes de mezclarlos.", "Tritura o bate los ingredientes hasta obtener la textura propia de la salsa, sin procesar de más las salsas rústicas.", "Prueba y equilibra con sal, acidez o agua una cucharadita a la vez.", "Deja reposar de 10 a 20 minutos para que se integren los sabores.", "Sirve de inmediato o refrigera tapada y usa utensilios limpios."]
        return [f"Lava, pela cuando sea necesario y corta los componentes de {title.lower()} en piezas uniformes.", "Precalienta horno, sartén, vaporera o aceite antes de comenzar la cocción.", "Cocina en una sola capa para que las piezas se doren o ablanden de manera pareja.", "Voltea o remueve a mitad de cocción y comprueba la textura con un tenedor.", "Añade ajo, hierbas o salsa durante los últimos minutos para que no se quemen.", "Ajusta sal y sirve caliente."]
    if category == "desserts":
        if any(word in lower for word in ("flan", "natilla", "creme brulee", "panna cotta")):
            return ["Calienta el horno a 160 °C y prepara moldes y una fuente para baño María.", "Calienta la leche o crema sin que hierva.", "Bate huevos y azúcar solo hasta integrar; añade lentamente el líquido caliente mientras remueves.", "Cuela la mezcla, repártela en los moldes y coloca agua caliente hasta media altura.", "Hornea hasta que los bordes cuajen y el centro aún tiemble ligeramente; enfría primero a temperatura ambiente.", "Refrigera al menos 4 horas antes de desmoldar o servir."]
        if any(word in lower for word in ("galleta", "brownie", "pastel", "cupcake", "banana bread", "pie", "crumble")):
            return ["Calienta el horno a 175 °C y prepara el molde con grasa y papel de hornear.", "Mide los ingredientes y mezcla harina, sal y leudantes en un recipiente.", "Bate mantequilla o aceite con azúcar; incorpora los huevos uno a uno.", "Añade los secos y la leche en tandas, mezclando solo hasta integrar; agrega frutas o chocolate al final.", "Hornea hasta que los bordes estén firmes y un palillo salga con migas húmedas, no masa líquida.", "Enfría 15 minutos en el molde y termina de enfriar sobre rejilla antes de cortar o decorar."]
        return [f"Mide los ingredientes de {title.lower()}: {ingredient_names}.", "Combina primero los ingredientes secos y después incorpora los líquidos poco a poco.", "Cocina a fuego medio-bajo, removiendo continuamente para evitar grumos y quemaduras.", "Retira del calor cuando la mezcla cubra la parte posterior de una cuchara.", "Pasa a recipientes limpios y refrigera dentro de las siguientes 2 horas.", "Enfría hasta que esté firme, decora y sirve."]
    if category == "coffee_hot":
        if any(word in lower for word in ("helado", "iced", "cold brew", "frappe", "smoothie", "chai helado")):
            return ["Prepara una porción concentrada de café o té y déjala enfriar por completo.", "Llena el vaso o la licuadora con el hielo medido.", "Vierte primero la bebida fría y luego añade leche y jarabe.", "Remueve durante 20 segundos; para frappé o smoothie, licúa de 30 a 45 segundos.", "Prueba, ajusta el dulzor y sirve inmediatamente."]
        if "affogato" in lower:
            return ["Enfría una copa o taza pequeña durante 10 minutos.", "Coloca una bola firme de helado de vainilla en la copa.", "Prepara un espresso de 30 ml justo antes de servir.", "Vierte el espresso caliente directamente sobre el helado.", "Sirve inmediatamente para conservar el contraste de temperaturas."]
        return ["Calienta la taza y mide el café, té, matcha o cacao.", "Prepara el espresso o la infusión con agua entre 90 y 96 °C; para matcha, bate con agua a unos 80 °C.", "Calienta la leche sin hervir y espúmala hasta 60–65 °C cuando la receta lleve leche.", "Vierte primero el café o la infusión; agrega después leche, espuma, cacao o especias.", "Remueve solo si la bebida lo requiere, prueba el dulzor y sirve inmediatamente."]
    if category == "juices":
        return ["Lava la fruta y las hierbas bajo agua corriente; pela y retira semillas cuando sea necesario.", "Corta todo en trozos que entren con facilidad en la licuadora o extractor.", "Exprime o licúa con el agua medida de 45 a 60 segundos.", "Cuela solo si deseas una textura más fina; no añadas hielo antes de colar.", "Prueba y ajusta acidez o dulzor poco a poco.", "Añade hielo y sirve inmediatamente; refrigera cualquier sobrante."]
    if category == "smoothies":
        return ["Lava y corta la fruta; usa al menos una parte congelada para una textura espesa.", "Vierte primero la leche, yogur o agua en la licuadora.", "Añade fruta, hielo y los complementos medidos.", "Licúa 30 segundos a velocidad baja y luego 45 segundos a velocidad alta.", "Detén, raspa los lados y ajusta con líquido una cucharada a la vez.", "Sirve inmediatamente; para un bowl, usa menos líquido y termina con fruta o granola."]
    if category == "cocktails":
        if "sangria" in lower:
            return ["Lava la fruta y córtala en cubos o rodajas finas, retirando semillas.", "Coloca la fruta y el azúcar en una jarra y presiona suavemente para liberar aroma sin triturarla.", "Añade el vino frío, remueve hasta disolver el azúcar y tapa la jarra.", "Refrigera al menos 1 hora y hasta 4 horas para integrar los sabores.", "Agrega hielo y agua con gas justo antes de servir; ofrece una versión sin alcohol sustituyendo el vino por jugo de uva."]
        if any(word in lower for word in ("pina colada", "daiquiri de fresa")):
            return ["Enfría las copas y mide todos los ingredientes antes de licuar.", "Coloca primero los líquidos y después la fruta y el hielo en la licuadora.", "Licúa de 30 a 45 segundos, hasta obtener una textura uniforme y sin trozos grandes de hielo.", "Prueba y ajusta acidez o dulzor sin añadir más alcohol.", "Sirve inmediatamente; para una versión sin alcohol, omite el destilado y reemplázalo con jugo de fruta."]
        if any(word in lower for word in ("old fashioned", "manhattan", "negroni", "martini")):
            return ["Enfría el vaso o la copa con hielo mientras mides cada ingrediente.", "Llena un vaso mezclador con hielo sólido hasta tres cuartas partes.", f"Añade las cantidades de la lista para preparar {title.lower()}.", "Remueve de 20 a 30 segundos para enfriar y diluir de forma controlada.", "Cuela en la copa fría o sirve sobre un cubo grande; decora y consume solo si eres adulto."]
        if any(word in lower for word in ("cuba libre", "gin tonic", "moscow mule", "paloma", "aperol", "tequila sunrise", "mimosa", "vodka lemonade")):
            return ["Enfría el vaso y mide todos los ingredientes.", "Llena el vaso con hielo limpio hasta arriba.", "Añade primero el destilado y después el jugo cítrico de la lista.", "Completa lentamente con la bebida gaseosa para conservar las burbujas y remueve una sola vez.", "Decora y sirve inmediatamente; prepara una versión sin alcohol sustituyendo el destilado por agua con gas."]
        return ["Enfría la copa y llena una coctelera hasta la mitad con hielo.", f"Mide los ingredientes de {title.lower()}: {ingredient_names}.", "Añade a la coctelera todos los ingredientes sin gas y agita de 12 a 15 segundos.", "Cuela en la copa fría o sobre hielo nuevo; añade la bebida gaseosa al final.", "Decora y sirve una sola porción a personas adultas; ofrece una alternativa sin alcohol."]
    return ["Mide y prepara todos los ingredientes.", "Calienta el equipo de cocción indicado.", "Cocina los ingredientes en el orden de mayor a menor tiempo necesario.", "Controla tiempo, temperatura y textura durante la cocción.", "Ajusta la sazón y deja reposar cuando corresponda.", "Sirve a la temperatura adecuada."]


def editorialize_recipe(category: str, title: str, kind: str, ingredients: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], str]:
    exact = concretize_ingredients(title, category, ingredients)
    steps = detailed_steps(category, title, exact)
    description = f"{title} explicado de principio a fin, con tiempos, señales de cocción y porciones claras."
    return exact, steps, description


def canonical_recipe_metadata(title: str) -> dict[str, Any]:
    """Return provenance only for individually reviewed, canonical recipes."""
    if _plain(title) == "cafe cubano":
        return {
            "description": "Cafecito cubano fuerte y dulce, preparado en cafetera moka y terminado con su espumita tradicional.",
            "servings": 4,
            "editorial_status": "verified",
            "canonical_variant": "Cafecito cubano en cafetera moka con espumita",
            "prep_minutes": 8,
            "cook_minutes": 7,
            "sources": [
                {
                    "title": "Cafecito (Cuban Coffee)",
                    "url": "https://www.cafebustelo.com/coffee/recipes/hot-coffee/cafecito",
                    "authority": "Café Bustelo",
                }
            ],
        }
    if _plain(title) in {"avena con manzana", "pollo alfredo"}:
        return {"editorial_status": "reviewed"}
    return {"editorial_status": "needs_canonical_review"}


_GENERIC_RECIPE_PHRASES = (
    "método indicado", "según corresponda", "orden indicado", "punto correcto",
    "cocina u hornea", "ingrediente principal", "según la receta", "cuando corresponda",
    "salsa indicada", "guarnición indicada", "proporción indicada", "equipo indicado",
)


def recipe_quality_issues(recipe: dict[str, Any], expected_title: str = "") -> list[str]:
    """Reject structurally complete but editorially generic recipe payloads."""
    issues: list[str] = []
    title = str(recipe.get("title") or "").strip()
    ingredients = [row for row in recipe.get("ingredients") or [] if isinstance(row, dict) and row.get("name")]
    steps = [str(step or "").strip() for step in recipe.get("steps") or [] if str(step or "").strip()]
    instructions = " ".join(steps).casefold()
    if expected_title and _plain(title) != _plain(expected_title):
        issues.append("El título no coincide exactamente con la receta solicitada.")
    if len(ingredients) < 3:
        issues.append("Faltan ingredientes medidos.")
    if len(steps) < 5:
        issues.append("Faltan pasos atómicos de preparación.")
    if any(phrase in instructions for phrase in _GENERIC_RECIPE_PHRASES):
        issues.append("La preparación contiene instrucciones genéricas.")
    if steps and not any(re.search(r"\b\d+(?:[.,]\d+)?\b", step) for step in steps):
        issues.append("La preparación no incluye ningún tiempo, cantidad o temperatura verificable.")
    if _plain(expected_title) == "cafe cubano":
        ingredient_text = _plain(" ".join(str(row.get("name") or "") for row in ingredients))
        if not all(value in ingredient_text for value in ("cafe", "agua", "azucar")):
            issues.append("El café cubano requiere café, agua y azúcar.")
        if not all(value in _plain(instructions) for value in ("moka", "espumita")):
            issues.append("Faltan la cafetera moka o la técnica de la espumita.")
        if any(value in _plain(instructions) for value in ("matcha", "cacao", "espuma de leche")):
            issues.append("La preparación mezcla técnicas ajenas al café cubano.")
    return issues
