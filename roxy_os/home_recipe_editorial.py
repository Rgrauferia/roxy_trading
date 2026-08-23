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
    output: list[dict[str, Any]] = []
    for row in ingredients:
        replacement = _replacement(str(row.get("name") or ""), title, category)
        if len(replacement) == 1 and replacement[0]["quantity"] == 0:
            output.append(dict(row))
        else:
            output.extend(replacement)
    lower = _plain(title)
    additions: list[dict[str, Any]] = []
    if category == "breakfast" and any(word in lower for word in ("pancake", "waffle", "crepe")):
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
        if "huevos hervidos" in lower:
            return ["Coloca los huevos en una olla y cúbrelos con 3 cm de agua fría.", "Lleva el agua a ebullición; apaga el fuego, tapa y deja 10 a 12 minutos para yemas firmes.", "Prepara un recipiente con agua y hielo.", "Pasa los huevos al agua helada durante 5 minutos para detener la cocción.", "Golpea suavemente la cáscara, pela bajo agua corriente y sazona al servir."]
        if any(word in lower for word in ("huevo", "omelette", "tortilla", "shakshuka", "quiche", "hash")):
            return ["Lava, corta y mide los vegetales y rellenos antes de encender el fuego.", "Calienta una sartén a fuego medio con el aceite; cocina los vegetales de 4 a 6 minutos hasta que estén tiernos.", "Bate los huevos con la sal durante 30 segundos para integrar claras y yemas.", "Vierte los huevos y cocina a fuego medio-bajo, moviendo o doblando según la forma del plato.", "Cocina hasta que el huevo esté completamente cuajado y el centro alcance 71 °C.", "Retira del fuego, deja reposar 1 minuto y sirve caliente con sus acompañamientos."]
        if any(word in lower for word in ("avena", "yogur", "chia", "granola", "parfait", "bowl de frutas")):
            return ["Lava y seca la fruta; córtala en trozos de 2 cm.", "Mide la avena o granola y la leche o yogur para conservar la proporción indicada.", "Si lleva avena caliente, cocina a fuego medio de 5 a 7 minutos, removiendo; si es nocturna, mezcla en un frasco.", "Añade canela, miel o mantequilla de maní y mezcla hasta distribuirlos.", "Para la versión nocturna, tapa y refrigera al menos 6 horas; para yogur o parfait, arma las capas justo antes de comer.", "Termina con la fruta y sirve fría o tibia, según la receta."]
        if any(word in lower for word in ("pancake", "waffle", "crepe")):
            return ["Mezcla harina, sal y polvo de hornear en un recipiente.", "Bate aparte leche y huevo; vierte sobre los secos y mezcla solo hasta desaparecer la harina visible.", "Deja reposar la masa 5 minutos mientras calientas la plancha o waflera.", "Engrasa ligeramente y vierte porciones iguales.", "Cocina de 2 a 3 minutos hasta ver burbujas; voltea y dora 1 a 2 minutos, o cierra la waflera hasta que deje de salir vapor.", "Mantén calientes las piezas terminadas y sirve con la cobertura indicada."]
        return ["Prepara el relleno y corta los ingredientes en porciones uniformes.", "Tuesta o calienta el pan, tortilla o arepa hasta que esté dorado por fuera.", "Cocina el huevo hasta que clara y yema estén firmes.", "Distribuye el relleno caliente y añade queso o vegetales.", "Cierra, cocina 1 minuto más para fundir el queso y corta por la mitad.", "Sirve de inmediato para conservar la textura crujiente."]
    if category == "chicken":
        finish = _protein_finish(category, lower)
        if "con arroz" in lower:
            return ["Seca el pollo, córtalo en piezas iguales y sazónalo; enjuaga el arroz hasta que el agua salga clara.", "Calienta aceite en una olla amplia y dora el pollo de 3 a 4 minutos por lado; pásalo a un plato limpio.", "Sofríe cebolla, ajo y pimiento durante 4 minutos; añade el arroz y remueve 1 minuto.", "Vierte el caldo medido, devuelve el pollo y lleva a ebullición.", "Tapa, baja el fuego y cocina de 18 a 22 minutos, hasta que el arroz absorba el líquido y el pollo alcance 74 °C.", "Apaga el fuego, reposa tapado 5 minutos, suelta el arroz con un tenedor y sirve."]
        if any(word in lower for word in ("guisado", "salsa", "curry", "tikka", "sopa", "marsala", "champinon")):
            return ["Seca el pollo, córtalo en piezas de tamaño parejo y sazónalo por todos los lados.", "Calienta el aceite en una olla a fuego medio-alto y dora el pollo por tandas, 3 a 4 minutos por lado; resérvalo.", "Baja a fuego medio y sofríe ajo, cebolla y demás aromáticos durante 4 minutos, raspando el fondo.", "Añade la salsa, caldo o crema indicada y lleva a hervor suave.", f"Devuelve el pollo, tapa parcialmente y cocina de 12 a 20 minutos, {finish}.", "Prueba la salsa, ajusta sal, deja reposar 3 minutos y sirve con la guarnición indicada."]
        if any(word in lower for word in ("horno", "asado", "alita", "empanizado", "parmesano", "cordon bleu")):
            return ["Calienta el horno a 200 °C y prepara una bandeja con papel de hornear.", "Seca y sazona el pollo; si lleva empanizado, pásalo por harina, huevo y pan rallado en ese orden.", "Distribuye las piezas sin amontonarlas y rocía con aceite.", "Hornea 15 minutos, voltea las piezas y añade salsa o queso cuando corresponda.", f"Continúa de 10 a 20 minutos, {finish}.", "Deja reposar 3 minutos antes de cortar o servir."]
        if any(word in lower for word in ("taco", "fajita", "wrap", "sandwich", "enchilada")):
            return ["Corta el pollo en tiras de 1 cm y sazónalo; corta cebolla y pimiento del mismo tamaño.", "Calienta una sartén amplia a fuego medio-alto con aceite.", "Cocina el pollo de 6 a 8 minutos, removiendo, hasta alcanzar 74 °C; retíralo.", "Saltea cebolla y pimiento de 4 a 5 minutos y vuelve a incorporar el pollo.", "Calienta las tortillas o el pan y reparte el relleno; añade salsa y queso.", "Enrolla o arma las porciones y sirve inmediatamente."]
        return ["Seca el pollo y córtalo en piezas de grosor uniforme; sazona con sal y pimienta.", "Pica el ajo y mezcla los ingredientes de la salsa o marinada indicada.", "Calienta el aceite en una sartén a fuego medio-alto.", "Dora el pollo de 4 a 6 minutos por lado sin moverlo durante los primeros minutos.", f"Añade los aromáticos o la salsa, baja el fuego y cocina de 3 a 5 minutos, {finish}.", "Deja reposar el pollo 3 minutos, báñalo con la salsa y sirve."]
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
            return ["Escurre completamente el atún enlatado y desmenúzalo en un recipiente limpio.", "Lava, seca y corta los vegetales; cocina y enfría la base de arroz o quinoa si la receta la lleva.", "Mezcla el atún con limón, aceite o el aderezo indicado hasta que quede húmedo pero no líquido.", "Añade los vegetales y mezcla suavemente para conservar su textura.", "Monta la ensalada, bowl, tostada o sándwich justo antes de servir.", "Sirve enseguida o mantén refrigerado y no lo dejes a temperatura ambiente más de 2 horas."]
        if "croqueta" in lower and "atun" in lower:
            return ["Escurre bien el atún y mézclalo con huevo, pan rallado, cebolla y condimentos.", "Refrigera la mezcla 15 minutos para que tome firmeza.", "Forma croquetas iguales y pásalas por una capa fina de pan rallado.", "Calienta aceite a fuego medio y cocina de 3 a 4 minutos por lado hasta dorar.", "Comprueba que el centro alcance 74 °C y pásalas a papel absorbente.", "Deja reposar 2 minutos y sirve con limón o salsa."]
        return ["Seca el pescado o marisco con papel y sazónalo por ambos lados.", "Prepara ajo, cebolla, limón y demás ingredientes antes de calentar la sartén.", "Calienta el aceite a fuego medio-alto y coloca las piezas sin amontonarlas.", "Dora el primer lado sin mover; voltea y agrega los aromáticos.", f"Termina la cocción {finish}; los camarones deben verse firmes, perlados y opacos.", "Pasa a un plato limpio y sirve inmediatamente con los jugos de cocción."]
    if category == "meat":
        finish = _protein_finish(category, lower)
        if any(word in lower for word in ("lasana", "pastel de carne")):
            return ["Calienta el horno a 190 °C y engrasa una fuente; prepara la salsa y el relleno de carne por separado.", "Cocina la carne molida desmenuzándola hasta que no queden zonas rosadas y alcance 71 °C; escurre el exceso de grasa.", "Para lasaña, alterna salsa, pasta, carne y queso; para pastel, mezcla la carne con huevo y pan rallado y forma una pieza uniforme.", "Cubre y hornea 30 minutos; destapa durante los últimos 15 minutos para dorar.", "Comprueba que el centro alcance 74 °C.", "Deja reposar 10 minutos antes de cortar para conservar la forma."]
        if any(word in lower for word in ("albondiga", "hamburguesa", "picadillo", "carne molida")):
            return ["Mantén la carne molida fría y mezcla solo con los condimentos hasta integrarlos, sin compactarla de más.", "Forma porciones del mismo tamaño o desmenuza la carne directamente en una sartén caliente, según la receta.", "Cocina a fuego medio-alto, girando las piezas o removiendo el picadillo para dorarlo uniformemente.", "Añade cebolla, ajo, salsa o vegetales cuando la carne ya haya tomado color.", "Continúa hasta que no queden zonas rosadas y el centro alcance 71 °C.", "Deja reposar 3 minutos y sirve con la salsa o guarnición indicada."]
        if any(word in lower for word in ("guis", "ropa vieja", "mechada", "chili", "salsa", "desmenuzado", "sopa")):
            return ["Corta la proteína en piezas uniformes, sécala y sazónala.", "Calienta aceite en una olla y dora las piezas por tandas; reserva.", "Sofríe cebolla y ajo de 4 a 5 minutos y añade tomate, especias o salsa.", "Incorpora la proteína y suficiente caldo para cubrir parcialmente; lleva a hervor suave.", f"Tapa y cocina a fuego bajo hasta que esté tierna y segura, {finish}.", "Ajusta la sazón, deja reposar 3 minutos y sirve con la salsa."]
        if any(word in lower for word in ("taco", "fajita", "sandwich", "bowl", "ensalada", "tostada")):
            return ["Prepara primero tortillas, pan, arroz o vegetales y mantenlos listos para montar.", "Seca, sazona y corta la proteína en porciones uniformes.", "Calienta una sartén a fuego medio-alto y cocina la proteína sin amontonar.", f"Continúa la cocción {finish}; pásala a una tabla limpia.", "Corta o desmenuza la proteína y distribúyela sobre la base preparada.", "Añade vegetales y salsa, y sirve de inmediato."]
        return ["Seca la proteína con papel y sazónala por ambos lados.", "Prepara ajo, cebolla, limón y demás ingredientes antes de calentar la sartén.", "Calienta el aceite a fuego medio-alto y coloca las piezas sin amontonarlas.", "Dora el primer lado sin mover; voltea y agrega los aromáticos.", f"Termina la cocción {finish}.", "Pasa a un plato limpio, deja reposar cuando corresponda y sirve con los jugos de cocción."]
    if category == "rice":
        if "risotto" in lower:
            return ["Calienta el caldo y mantenlo a hervor muy suave.", "Sofríe cebolla y los ingredientes principales durante 4 minutos.", "Añade el arroz y tuéstalo 1 minuto, removiendo.", "Incorpora el caldo caliente de a un cucharón, esperando a que se absorba antes del siguiente.", "Cocina de 18 a 22 minutos hasta que el grano esté al dente y cremoso.", "Retira del fuego, añade queso o mantequilla, reposa 2 minutos y sirve."]
        if any(word in lower for word in ("frito", "chaufa")):
            return ["Usa arroz cocido y completamente frío; separa los granos con las manos limpias.", "Calienta un wok o sartén grande a fuego alto con aceite.", "Cocina huevo, proteína y vegetales por separado para no bajar la temperatura; reserva cada parte.", "Añade el arroz y saltéalo de 3 a 4 minutos hasta que esté bien caliente.", "Devuelve los ingredientes, agrega salsa de soja y mezcla 1 minuto.", "Comprueba que todo alcance 74 °C y sirve inmediatamente."]
        if "arroz con leche" in lower:
            return ["Enjuaga el arroz y colócalo en una olla con leche y canela.", "Lleva a hervor suave, baja el fuego y cocina 25 minutos, removiendo cada pocos minutos.", "Añade el azúcar cuando el arroz esté tierno para evitar que se endurezca.", "Cocina de 8 a 10 minutos más hasta que la mezcla cubra la cuchara.", "Retira la canela y reparte en recipientes limpios.", "Sirve tibio o enfría y refrigera dentro de 2 horas."]
        return ["Enjuaga el arroz en un colador hasta que el agua salga casi transparente.", "Sofríe aromáticos, vegetales o proteína en la olla según la receta.", "Añade el arroz y remueve 1 minuto para cubrir los granos con aceite.", "Vierte el agua o caldo medido, sazona y lleva a ebullición.", "Tapa, baja al mínimo y cocina sin destapar de 15 a 20 minutos; el integral necesita de 35 a 45 minutos.", "Apaga, reposa tapado 5 minutos y suelta los granos con un tenedor."]
    if category == "pasta":
        if any(word in lower for word in ("lasana", "canelon", "ziti al horno")):
            return ["Calienta el horno a 190 °C y engrasa una fuente para horno.", "Cuece la pasta hasta que quede flexible pero firme; escúrrela y sepárala para que no se pegue.", "Prepara la salsa y cocina por completo la carne o vegetales del relleno.", "Alterna capas uniformes de pasta, relleno, salsa y queso, terminando con salsa y queso.", "Cubre y hornea 25 minutos; destapa y hornea 15 minutos más, hasta que el centro alcance 74 °C.", "Deja reposar 10 minutos antes de cortar y servir."]
        if "sopa" in lower:
            return ["Corta los vegetales en piezas uniformes y lleva el caldo a hervor suave.", "Sofríe cebolla y ajo durante 4 minutos; añade los vegetales firmes.", "Vierte el caldo y cocina hasta que los vegetales estén casi tiernos.", "Añade los fideos y cuécelos el tiempo indicado en su envase, removiendo para que no se peguen.", "Comprueba que todos los ingredientes estén tiernos y que la sopa hierva antes de servir.", "Ajusta sal, deja reposar 2 minutos y sirve caliente."]
        return ["Pon a hervir 4 litros de agua y añade sal cuando rompa el hervor.", "Prepara la salsa en una sartén amplia: sofríe los aromáticos y cocina sus ingredientes hasta integrarlos.", "Cuece la pasta hasta 1 minuto antes del tiempo del paquete; reserva 1 taza del agua y escurre.", "Pasa la pasta a la sartén y añade media taza del agua reservada.", "Mezcla a fuego medio de 1 a 2 minutos hasta que la salsa se adhiera; agrega más agua si hace falta.", "Ajusta sal y pimienta, añade queso o hierbas y sirve caliente."]
    if category == "soups":
        return ["Lava, pela y corta los ingredientes en piezas del mismo tamaño.", "Calienta el aceite en una olla y sofríe cebolla y ajo durante 4 minutos.", "Añade vegetales, legumbres o proteína y cocina 3 minutos, removiendo.", "Vierte el caldo, lleva a ebullición y retira la espuma si aparece.", "Baja el fuego y cocina parcialmente tapado hasta que todo esté tierno; remueve cada 10 minutos.", "Tritura solo si es una crema, vuelve a calentar, ajusta sal y sirve humeante."]
    if category == "bowls_salads":
        return ["Lava y seca por completo hojas, frutas y vegetales; córtalos en piezas fáciles de comer.", "Cocina y enfría la base de arroz, quinoa, pasta o papa si la receta la incluye.", "Cocina la proteína por separado hasta su temperatura segura y déjala reposar antes de cortarla.", "Bate el aderezo en un recipiente hasta que quede emulsionado.", "Distribuye primero la base y luego vegetales, proteína y complementos sin mezclar en exceso.", "Añade el aderezo justo antes de servir para mantener la textura."]
    if category == "vegetarian":
        return ["Enjuaga legumbres o granos y corta los vegetales en tamaños uniformes.", "Calienta aceite a fuego medio y sofríe cebolla, ajo y especias durante 3 minutos.", "Añade los vegetales más firmes y cocina 5 minutos antes de incorporar los más tiernos.", "Agrega tofu, legumbres o grano y mezcla hasta cubrir con los condimentos.", "Cocina de 8 a 12 minutos, hasta que los vegetales estén tiernos pero mantengan forma.", "Prueba, ajusta sal y acidez y sirve con la guarnición indicada."]
    if category == "baked":
        if "pizza" in lower or any(word in lower for word in ("calzone", "stromboli", "rollito")):
            return ["Mezcla harina, levadura, sal y agua tibia; amasa de 8 a 10 minutos hasta que la masa esté lisa.", "Cubre y deja fermentar de 60 a 90 minutos, hasta que casi duplique su volumen.", "Calienta el horno a 245 °C con la bandeja o piedra dentro durante 30 minutos.", "Estira la masa sobre papel de hornear y distribuye una capa fina de salsa, queso y coberturas.", "Hornea de 10 a 15 minutos, hasta que la base esté firme y el borde dorado.", "Deja reposar 3 minutos antes de cortar para que el queso se asiente."]
        if any(word in lower for word in ("pan", "focaccia", "ciabatta", "brioche", "bollito", "pretzel", "croissant", "nudo")):
            return ["Pesa la harina, el agua, la levadura y la sal; mezcla hasta no ver harina seca.", "Amasa de 8 a 12 minutos, hasta obtener una masa elástica que se estire sin romperse fácilmente.", "Cubre y deja fermentar en un lugar templado hasta que duplique su volumen, de 60 a 90 minutos.", "Desgasifica suavemente, forma las piezas y deja levar de nuevo entre 30 y 45 minutos.", "Calienta el horno a 200 °C y hornea hasta que la superficie esté dorada y el centro alcance unos 93 °C.", "Enfría sobre rejilla al menos 30 minutos antes de cortar."]
        if any(word in lower for word in ("empanada", "pastelito")):
            return ["Calienta el horno a 200 °C y cubre una bandeja con papel de hornear.", "Prepara el relleno y cocínalo por completo; déjalo enfriar para que no humedezca la masa.", "Estira la masa, corta discos iguales y coloca una porción de relleno en el centro sin sobrecargar.", "Humedece los bordes, dobla y sella firmemente con un tenedor; pincela con huevo.", "Hornea de 18 a 25 minutos, hasta que la masa esté inflada y bien dorada.", "Deja reposar 5 minutos antes de servir porque el relleno estará muy caliente."]
        return ["Calienta el horno a 190 °C y engrasa una fuente del tamaño indicado.", f"Prepara el componente central de {title.lower()} y la salsa por separado para sazonarlos correctamente.", "Distribuye capas uniformes y cubre con el queso rallado.", "Tapa con papel de aluminio y hornea 25 minutos.", "Destapa y hornea de 10 a 15 minutos más, hasta que el centro alcance 74 °C y la superficie dore.", "Deja reposar 10 minutos antes de cortar o servir."]
    if category == "sides_sauces":
        if any(word in lower for word in ("salsa", "pesto", "chimichurri", "mojo", "gallo", "guacamole", "aderezo")):
            return ["Lava, seca y pica finamente todos los ingredientes frescos.", "Mide aceite, ácido, sal y especias antes de mezclarlos.", "Tritura o bate los ingredientes hasta obtener la textura propia de la salsa, sin procesar de más las salsas rústicas.", "Prueba y equilibra con sal, acidez o agua una cucharadita a la vez.", "Deja reposar de 10 a 20 minutos para que se integren los sabores.", "Sirve de inmediato o refrigera tapada y usa utensilios limpios."]
        return [f"Lava, pela cuando sea necesario y corta los componentes de {title.lower()} en piezas uniformes.", "Precalienta horno, sartén, vaporera o aceite antes de comenzar la cocción.", "Cocina en una sola capa para que las piezas se doren o ablanden de manera pareja.", "Voltea o remueve a mitad de cocción y comprueba la textura con un tenedor.", "Añade ajo, hierbas o salsa durante los últimos minutos para que no se quemen.", "Ajusta sal y sirve caliente."]
    if category == "desserts":
        if any(word in lower for word in ("flan", "natilla", "creme brulee", "panna cotta")):
            return ["Calienta el horno a 160 °C y prepara moldes y una fuente para baño María.", "Calienta la leche o crema sin que hierva.", "Bate huevos y azúcar solo hasta integrar; añade lentamente el líquido caliente mientras remueves.", "Cuela la mezcla, repártela en los moldes y coloca agua caliente hasta media altura.", "Hornea hasta que los bordes cuajen y el centro aún tiemble ligeramente; enfría primero a temperatura ambiente.", "Refrigera al menos 4 horas antes de desmoldar o servir."]
        if any(word in lower for word in ("galleta", "brownie", "pastel", "cupcake", "banana bread", "pie", "crumble")):
            return ["Calienta el horno a 175 °C y prepara el molde con grasa y papel de hornear.", "Mide los ingredientes y mezcla harina, sal y leudantes en un recipiente.", "Bate mantequilla o aceite con azúcar; incorpora los huevos uno a uno.", "Añade los secos y la leche en tandas, mezclando solo hasta integrar; agrega frutas o chocolate al final.", "Hornea hasta que los bordes estén firmes y un palillo salga con migas húmedas, no masa líquida.", "Enfría 15 minutos en el molde y termina de enfriar sobre rejilla antes de cortar o decorar."]
        return ["Mide y prepara todos los ingredientes antes de calentar o batir.", "Cocina la base a la temperatura indicada, removiendo para evitar grumos o quemaduras.", "Comprueba la textura: debe cubrir la cuchara, mantener la forma o dorarse uniformemente según el postre.", "Retira del calor y añade aromas delicados como vainilla o ralladura.", "Enfría de forma segura; refrigera los postres con leche o huevo dentro de 2 horas.", "Decora y sirve solo cuando la estructura esté firme."]
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
            return ["Enfría el vaso o la copa con hielo mientras mides cada ingrediente.", "Llena un vaso mezclador con hielo sólido hasta tres cuartas partes.", "Añade los destilados, vermut, azúcar o amargos en las cantidades indicadas.", "Remueve de 20 a 30 segundos para enfriar y diluir de forma controlada.", "Cuela en la copa fría o sirve sobre un cubo grande; decora y consume solo si eres adulto."]
        if any(word in lower for word in ("cuba libre", "gin tonic", "moscow mule", "paloma", "aperol", "tequila sunrise", "mimosa", "vodka lemonade")):
            return ["Enfría el vaso y mide los ingredientes para mantener la proporción de la receta.", "Llena el vaso con hielo limpio hasta arriba.", "Añade primero el destilado y el jugo o cítrico indicado.", "Completa lentamente con la bebida gaseosa para conservar las burbujas y remueve una sola vez.", "Decora y sirve inmediatamente; prepara una versión sin alcohol sustituyendo el destilado por agua con gas o jugo."]
        return ["Enfría la copa y llena una coctelera hasta la mitad con hielo.", "Mide y añade los ingredientes sin gas en las cantidades indicadas.", "Cierra y agita enérgicamente durante 12 a 15 segundos.", "Cuela en la copa fría o sobre hielo nuevo; añade cualquier bebida gaseosa después de colar.", "Decora y sirve una sola porción a personas adultas; ofrece una alternativa sin alcohol."]
    return ["Mide y prepara todos los ingredientes.", "Calienta el equipo de cocción indicado.", "Cocina los ingredientes en el orden de mayor a menor tiempo necesario.", "Controla tiempo, temperatura y textura durante la cocción.", "Ajusta la sazón y deja reposar cuando corresponda.", "Sirve a la temperatura adecuada."]


def editorialize_recipe(category: str, title: str, kind: str, ingredients: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], str]:
    exact = concretize_ingredients(title, category, ingredients)
    steps = detailed_steps(category, title, exact)
    description = f"{title} explicado de principio a fin, con tiempos, señales de cocción y porciones claras."
    return exact, steps, description
