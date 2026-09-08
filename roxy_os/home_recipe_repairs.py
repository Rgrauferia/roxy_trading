"""Exact repairs to existing Home recipes, never a category-based generator.

These are Roxy's own preparations, not a licensed publisher's recipes. The USDA
reference supports food handling/temperatures only, not the recipe or its yield.
Do not turn unreviewed installed templates into recipes with this module.
"""
from copy import deepcopy

SAFETY_SOURCE = {
    "title": "USDA / FoodSafety.gov · temperaturas de seguridad (no autor de la receta)",
    "url": "https://www.foodsafety.gov/food-safety-charts/safe-minimum-internal-temperatures",
    "authority": "FoodSafety.gov",
}

CATEGORIES = {
    "eggs_toast": "breakfast", "avocado_toast": "breakfast", "omelet": "breakfast",
    "pancakes": "breakfast", "overnight_oats": "breakfast", "pizza": "baked",
    "rice": "rice", "arroz_con_pollo": "rice", "fried_rice": "rice",
    "salmon": "seafood", "tuna_bowl": "bowls_salads", "lentils": "soups",
    "hot_chocolate": "coffee_hot", "iced_coffee": "coffee_hot",
    "smoothie": "smoothies", "pina_colada_zero": "smoothies",
    "virgin_daiquiri": "smoothies",
}

EXACT_STEPS = {
    "eggs_toast": [
        "Tuesta las rebanadas de pan integral indicadas en los ingredientes hasta que estén doradas; colócalas en un plato.",
        "Calienta el aceite de la lista en una sartén antiadherente a fuego medio-bajo.",
        "Casca los huevos por separado en una taza limpia y deslízalos con cuidado a la sartén; si no caben sin amontonarlos, cocina por tandas.",
        "Cocina sin fuego fuerte hasta que las claras estén opacas. Voltea con una espátula y termina hasta que clara y yema estén firmes, sin partes líquidas.",
        "Sirve los huevos junto al pan tostado. Esta preparación no lleva carne, vegetales ni salsa añadida.",
    ],
    "avocado_toast": [
        "Tuesta el pan integral indicado en la lista. Lava el aguacate antes de cortarlo y usa la cantidad indicada.",
        "Machaca la pulpa con el jugo del limón de la lista en un cuenco limpio.",
        "Pon el huevo en un cazo, cúbrelo con agua y lleva a ebullición. Retira del fuego, tapa y deja 12 minutos para un huevo grande.",
        "Enfría el huevo bajo agua fría, pélalo y córtalo. Comprueba que la clara y la yema estén firmes; si queda líquido, termina de cocinarlo antes de servir.",
        "Reparte el aguacate sobre las tostadas y añade el huevo cocido. Sirve inmediatamente.",
    ],
    "omelet": [
        "Bate los huevos en un cuenco hasta mezclar claras y yemas. Ten listo el queso de la lista.",
        "Derrite la mantequilla indicada en una sartén antiadherente de unos 20 cm a fuego medio-bajo. Si preparas más de una porción, haz tortillas individuales por tandas.",
        "Vierte los huevos y mueve suavemente los bordes cuajados hacia el centro con una espátula, dejando que el huevo líquido toque la sartén.",
        "Cuando casi no quede huevo líquido, distribuye el queso sobre una mitad y dobla la otra mitad encima.",
        "Termina a fuego bajo hasta que el huevo esté cuajado y el centro alcance 71 °C. Sirve caliente; no debe seguir líquido por dentro.",
    ],
    "pancakes": [
        "Licúa la avena, el huevo, el plátano pelado y la leche hasta formar una mezcla uniforme. Deja reposar 5 minutos para hidratar la avena.",
        "Calienta una sartén antiadherente limpia a fuego medio-bajo. Esta receta no requiere aceite si la superficie es realmente antiadherente.",
        "Vierte porciones de unas 2 cucharadas, dejando espacio entre ellas para poder voltearlas.",
        "Cocina unos 2–3 minutos hasta que los bordes estén firmes y aparezcan burbujas. Voltea con una espátula y cocina 1–2 minutos más.",
        "Comprueba que el centro no esté húmedo ni tenga masa cruda; la mezcla con huevo debe alcanzar 71 °C. Si se doran demasiado rápido, baja el fuego.",
        "Repite con el resto de la mezcla y reparte las porciones previstas. No añadas coberturas que no estén previstas en tu lista.",
    ],
    "chicken_wrap": [
        "Usa la cantidad indicada de pollo ya cocido y conservado en refrigeración. No empieces con pollo crudo: esta receta es para aprovechar pollo cocido.",
        "Córtalo en tiras y recaliéntalo tapado a fuego bajo o en microondas, removiendo para que alcance 74 °C en todo el centro. No hace falta aceite.",
        "Lava el tomate y el aguacate, corta el tomate en dados y la pulpa del aguacate en láminas, usando una tabla limpia.",
        "Calienta las tortillas integrales en una sartén seca unos 20–30 segundos por lado, solo hasta que sean flexibles.",
        "Reparte pollo, tomate y aguacate entre las tortillas. Dobla los laterales y enrolla desde la base para contener el relleno.",
        "Sirve enseguida. Esta versión no lleva lechuga ni salsa adicional; si las añades, actualiza también los ingredientes.",
    ],
    "quesadilla": [
        "Usa pollo previamente cocido y refrigerado. Corta el pollo y los vegetales en trozos pequeños.",
        "En una sartén antiadherente, cocina los vegetales a fuego medio-bajo hasta que estén tiernos. Añade el pollo y calienta todo hasta 74 °C; si se pega, añade una cucharada de agua.",
        "Distribuye el relleno y el queso sobre la mitad de las tortillas; cubre cada una con otra tortilla.",
        "Calienta cada quesadilla en sartén seca a fuego medio-bajo, 2–3 minutos por lado, volteando con cuidado hasta que el queso se derrita y el centro esté caliente.",
        "Corta cada quesadilla en triángulos y sirve 1 por persona. Usa una tabla limpia para no contaminar el relleno cocido.",
    ],
    "picadillo": [
        "Lava y pica la cebolla y el pimiento; pela y pica el ajo. Escurre las aceitunas.",
        "Cocina la carne molida en una sartén amplia antiadherente a fuego medio, separándola con una espátula para que no queden bloques.",
        "Añade cebolla, pimiento y ajo. Cocina removiendo unos 5 minutos, hasta que se ablanden.",
        "Incorpora el tomate triturado y las aceitunas. Cocina a fuego bajo unos 15 minutos, removiendo; añade un poco de agua si se seca.",
        "Comprueba con termómetro que la carne molida alcance 71 °C. Reparte las porciones previstas; no uses el color como única señal de seguridad.",
    ],
    "chicken": [
        "Seca las pechugas con papel de cocina, sin lavar el pollo crudo. Iguala su grosor a unos 2 cm y sazona con la sal indicada.",
        "Calienta el aceite de la lista en una sartén amplia a fuego medio. Añade el pollo dejando espacio entre las piezas y cocina por tandas si hace falta.",
        "Cocina aproximadamente 5–7 minutos por lado, ajustando el fuego para que no se queme. El tiempo depende del grosor: comprueba 74 °C en la parte más gruesa con termómetro.",
        "Baja el fuego, añade el ajo picado y remueve unos 30 segundos sin dejar que se queme.",
        "Añade el jugo de limón y deja burbujear 1 minuto. Sirve una pechuga por persona con la salsa de la sartén.",
    ],
}

def repair_core_recipe(key, recipe):
    """Modify only the named original; preserve distinct drinks and short recipes."""
    if key in CATEGORIES:
        recipe["category"] = CATEGORIES[key]
    if key in EXACT_STEPS:
        recipe["steps"] = list(EXACT_STEPS[key])
        recipe["editorial_status"] = "reviewed_local"
        recipe["editorial_revision"] = "2026-09-08-exact-recipe"
        recipe["sources"] = [deepcopy(SAFETY_SOURCE)]
        recipe["source_context"] = "Preparación de Roxy. La fuente respalda seguridad alimentaria, no autoría ni validación de esta receta."
