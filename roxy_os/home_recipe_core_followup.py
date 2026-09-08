"""Named editorial corrections to Roxy's original human preparations.

This is deliberately not a category template or a generator. References support
safe handling only; they do not imply FDA authorship or kitchen testing. Apply
only while building the original catalog, never to user imports or pet recipes.
"""

from copy import deepcopy
from typing import Any


REVISION = "2026-09-08-core-followup"
SOURCE_CONTEXT = (
    "Preparación propia de Roxy revisada en ingredientes y secuencia. "
    "Las referencias respaldan seguridad alimentaria; no son autores de esta "
    "receta ni certifican una prueba de cocina. Los tiempos son orientativos."
)
HANDLING_SOURCE = {
    "title": "FDA · manipulación de alimentos (referencia de seguridad)",
    "url": "https://www.fda.gov/food/buy-store-serve-safe-food/safe-food-handling",
    "authority": "FDA",
}
EGG_SOURCE = {
    "title": "FDA · seguridad de huevos y preparaciones con huevo",
    "url": "https://www.fda.gov/food/buy-store-serve-safe-food/what-you-need-know-about-egg-safety",
    "authority": "FDA",
}
FLOUR_SOURCE = {
    "title": "FDA · cocinar la harina y no probar masas crudas",
    "url": "https://www.fda.gov/food/buy-store-serve-safe-food/handling-flour-safely-what-you-need-know",
    "authority": "FDA",
}

# These five originals have complete, distinct preparations. The caller may
# prefer them over an installed duplicate that is still explicitly a draft.
RECOVERABLE_ORIGINAL_KEYS = frozenset({
    "rice", "pina_colada_zero", "virgin_mojito", "overnight_oats", "tuna_bowl",
})

STEPS = {
    "rice": [
        "Usa arroz blanco de grano largo. Enjuágalo en un colador y escurre; lava los vegetales y córtalos en dados pequeños de tamaño parecido.",
        "Calienta el aceite indicado en una olla con tapa a fuego medio. Sofríe los vegetales unos 3 minutos, removiendo.",
        "Incorpora el arroz, el agua y la sal de la lista. Remueve una vez y lleva a ebullición.",
        "Tapa, baja el fuego al mínimo y cocina unos 18 minutos sin remover. Comprueba que el arroz esté tierno y haya absorbido el agua; si sigue duro, añade un poco de agua caliente y continúa tapado unos minutos.",
        "Apaga y deja reposar tapado 5 minutos; separa los granos con un tenedor y sirve. Refrigera pronto las sobras en recipientes poco profundos, antes de 2 horas (1 hora si el ambiente supera 32 °C).",
    ],
    "pina_colada_zero": [
        "Usa piña pelada, sin el centro duro y cortada en trozos. Vierte primero la leche de coco y el jugo de piña en una licuadora apta para triturar hielo.",
        "Añade toda la piña y el hielo de la lista. Tapa y licúa hasta obtener una bebida uniforme; detén la máquina antes de abrir o acercar una espátula.",
        "Reparte en vasos y sirve inmediatamente. Esta versión no contiene ron ni requiere adornos o ingredientes adicionales.",
    ],
    "virgin_mojito": [
        "Lava el limón y la hierbabuena. Exprime el limón y retira las semillas; mezcla su jugo con el azúcar en un vaso resistente.",
        "Añade la hierbabuena y presiónala suavemente para liberar aroma, sin triturarla ni romper el vaso.",
        "Agrega el hielo y vierte lentamente el agua con gas. Remueve con suavidad y sirve enseguida; no añadas ron a esta versión sin alcohol.",
    ],
    "overnight_oats": [
        "En un recipiente limpio con tapa mezcla la avena en hojuelas, la leche pasteurizada y el yogur pasteurizado de la lista. No uses avena de grano entero ni cortada al acero para este mismo tiempo de remojo.",
        "Tapa y lleva inmediatamente al refrigerador a 4 °C o menos durante al menos 6 horas; no dejes la mezcla toda la noche sobre la encimera.",
        "Antes de servir, lava y corta la fruta y mézclala con la avena hidratada. Consume fría y guarda de nuevo cualquier sobrante en refrigeración.",
    ],
    "tuna_bowl": [
        "Abre las latas de atún listo para comer, escurre el líquido y desmenuza el contenido. Enjuaga y escurre los garbanzos ya cocidos; esta receta no usa pescado crudo ni garbanzos secos.",
        "Lava el pepino, los tomates y el limón. Corta pepino y tomate en dados sobre una tabla limpia y exprime el limón, retirando las semillas.",
        "Mezcla atún, garbanzos, pepino y tomate con el jugo de limón. Reparte y sirve; si lo preparas antes, consérvalo tapado a 4 °C o menos hasta comer.",
    ],
    "flan": [
        "Precalienta el horno a 175 °C. Prepara un molde metálico de unos 20 cm de diámetro y al menos 7 cm de alto, y una fuente mayor para el baño María.",
        "Calienta el azúcar en un cazo a fuego medio-bajo hasta que se derrita y tome color ámbar. Mueve el cazo con cuidado y retira antes de que humee. Vierte en el molde y gira usando protección; no toques el caramelo caliente.",
        "Mezcla los huevos, la leche condensada, la leche evaporada y la vainilla hasta integrar, sin batir espuma en exceso. Vierte sobre el caramelo.",
        "Pon el molde dentro de la fuente y añade agua caliente a la fuente exterior hasta aproximadamente la mitad de la altura del molde, sin que entre agua en el flan.",
        "Hornea unos 55–70 minutos. El borde debe estar cuajado y el centro temblar suavemente, sin oleadas de mezcla líquida; comprueba al menos 71.1 °C en el centro. Si sigue líquido, continúa revisando cada 5 minutos.",
        "Retira el molde del agua con manoplas. Deja salir el calor unos 30 minutos y refrigera a 4 °C o menos, sin esperar horas en la encimera. Enfría al menos 4 horas antes de desmoldar; no superes 2 horas fuera del frío (1 hora si supera 32 °C).",
        "Despega el borde con una espátula fina y vuelca sobre un plato con borde para recoger el caramelo. Guarda tapado en frío y consume en 3–4 días.",
    ],
    "tres_leches": [
        "Precalienta el horno a 175 °C y forra un molde cuadrado de unos 23 cm con papel para hornear. Separa claras y yemas en recipientes limpios y secos; no pruebes la masa cruda.",
        "Bate las claras hasta que formen espuma. Añade aproximadamente la mitad del azúcar poco a poco y sigue batiendo hasta obtener picos firmes y brillantes.",
        "En otro recipiente bate las yemas con el azúcar restante hasta que estén pálidas y espesas. Incorpora una parte de las claras para aligerar; luego añade el resto con movimientos envolventes.",
        "Tamiza la harina e incorpórala en varias tandas con una espátula, sin aplastar el aire. Esta versión obtiene su volumen del huevo batido y no lleva levadura añadida.",
        "Vierte en el molde y hornea unos 30–40 minutos, hasta que el centro recupere su forma al tocarlo suavemente y un palillo salga sin masa cruda. Si aún hay masa húmeda, continúa y comprueba de nuevo.",
        "Mientras se hornea, mezcla la leche condensada, la leche evaporada y la crema pasteurizada; conserva la mezcla en refrigeración. Deja templar el bizcocho unos 20 minutos en el molde.",
        "Pincha la superficie del bizcocho varias veces y vierte las tres leches poco a poco, dejando que se absorban entre añadidos. Cubre y refrigera de inmediato a 4 °C o menos durante al menos 4 horas; no dejes el pastel remojado enfriándose fuera del frigorífico.",
        "Corta y sirve frío. Esta versión no incluye cobertura adicional. Refrigera las porciones restantes y consúmelas en 3–4 días; no permanezcan fuera del frío más de 2 horas (1 hora si supera 32 °C).",
    ],
    "cheesecake": [
        "Precalienta el horno a 160 °C. Forra la base de un molde desmontable de unos 22 cm con papel para hornear. Usa queso crema entero pasteurizado; déjalo ablandar sólo lo necesario para poder mezclarlo.",
        "Tritura las galletas. Derrite la mantequilla a fuego bajo, mézclala con las migas y presiónalas en una capa uniforme sobre la base del molde.",
        "Bate el queso crema con el azúcar y la vainilla a velocidad baja hasta que no queden grumos. Incorpora los huevos de uno en uno, mezclando sólo lo necesario y sin probar el relleno crudo.",
        "Vierte el relleno sobre la base de galleta y alisa suavemente. Coloca el molde sobre una bandeja para recoger posibles fugas de mantequilla.",
        "Hornea unos 60–75 minutos. Los bordes deben estar firmes y el centro moverse ligeramente como una sola pieza, no como líquido; comprueba al menos 71.1 °C en el centro. Añade intervalos de 5 minutos si aún no está cuajado.",
        "Retira a una rejilla unos 30 minutos y lleva al refrigerador a 4 °C o menos. No lo dejes toda la noche en el horno ni esperes a que se enfríe completamente fuera: máximo 2 horas sin refrigeración (1 hora por encima de 32 °C).",
        "Refrigera al menos 6 horas antes de retirar el aro y cortar. Conserva tapado en frío y consume en 3–4 días; esta versión no lleva salsa ni cobertura adicional.",
    ],
    "brownies": [
        "Precalienta el horno a 175 °C y forra un molde cuadrado de unos 20 cm con papel para hornear. Trocea el chocolate de la lista; no pruebes la mezcla cruda.",
        "Derrite el chocolate con la mantequilla a fuego muy bajo, removiendo y retirando del calor en cuanto se integren. Deja templar unos minutos: la mezcla no debe seguir caliente al añadirla a los huevos.",
        "Bate los huevos con el azúcar hasta integrar. Incorpora poco a poco el chocolate templado mientras remueves, evitando cuajar los huevos con chocolate demasiado caliente.",
        "Añade la harina y mezcla con espátula sólo hasta que desaparezcan las partes secas. Vierte y nivela la masa en el molde preparado.",
        "Hornea unos 25–35 minutos. Comprueba que los bordes estén firmes y que un palillo en el centro salga con migas húmedas, no con masa líquida; la mezcla con huevo debe alcanzar al menos 71.1 °C. Continúa si falta cocción.",
        "Deja enfriar sobre una rejilla antes de levantar con el papel y cortar. No añadas helado, nueces ni cobertura sin incorporarlos también a la lista de ingredientes.",
    ],
    "apple_pie": [
        "Precalienta el horno a 190 °C. Lava, pela y descorazona las manzanas; córtalas en láminas finas de grosor parecido y mézclalas con el azúcar y la canela.",
        "Coloca una lámina de masa en un molde para tarta de unos 23 cm, ajustándola a la base y las paredes. Reparte las manzanas dentro, sin amontonarlas sólo en el centro.",
        "Distribuye toda la mantequilla de la lista en trocitos sobre las manzanas. Cubre con la segunda lámina, une y sella los bordes; abre varias ranuras arriba para que salga vapor.",
        "Coloca el molde sobre una bandeja y hornea unos 50–65 minutos, hasta que la masa esté dorada, el jugo burbujee por las ranuras y la manzana esté tierna al introducir una brocheta. Si el borde se dora antes, protégelo con papel de aluminio.",
        "Deja reposar al menos 1 hora sobre una rejilla antes de cortar para que el relleno se asiente. No pruebes masa cruda y respeta las instrucciones de cocción del envase si difieren para esa masa.",
    ],
    "bread": [
        "Mezcla la harina, la levadura seca instantánea y la sal en un cuenco grande. Usa agua tibia, no caliente, siguiendo la temperatura indicada en el envase de la levadura.",
        "Añade toda el agua y el aceite de la lista. Mezcla y amasa de 8 a 10 minutos hasta obtener una masa elástica; no pruebes la masa cruda.",
        "Cubre el cuenco y deja crecer en un lugar templado hasta que la masa duplique su volumen, alrededor de 1 hora; el tiempo cambia con la temperatura ambiente.",
        "Forma una hogaza y colócala en una bandeja con papel para hornear. Cubre y deja crecer unos 30–45 minutos, hasta que esté visiblemente esponjada. Precalienta el horno a 220 °C.",
        "Haz un corte superficial arriba y hornea aproximadamente 30–40 minutos, hasta que la corteza esté dorada y la base suene hueca al golpearla. Si la hogaza sigue pálida o pesada, continúa la cocción.",
        "Retira a una rejilla y deja enfriar al menos 1 hora antes de cortar, para que la miga se asiente. Este tiempo y una hogaza corresponden al lote base; si cambias mucho las porciones, prepara varias hogazas semejantes.",
    ],
    "whiskey_sour": [
        "Agita el whisky, el jugo de limón, el jarabe y el hielo de la lista en una coctelera cerrada durante unos 15 segundos.",
        "Cuela en un vaso frío y sirve. Esta versión no contiene clara de huevo ni necesita una rodaja adicional de limón.",
    ],
    "old_fashioned": [
        "Disuelve el azúcar con el agua y el amargo aromático de la lista en un vaso corto.",
        "Añade el cubo de hielo y el whisky; remueve durante 20–30 segundos y sirve. Esta versión se prepara sin piel de naranja añadida.",
    ],
    "manhattan": [
        "Vierte el whisky, el vermut dulce y el amargo aromático en un vaso mezclador con el hielo de la lista. Remueve unos 20–30 segundos hasta enfriar.",
        "Cuela en una copa fría y sirve sin el hielo del mezclador. Esta versión no requiere una cereza adicional.",
    ],
    "negroni": [
        "Vierte la ginebra, el vermut rojo y el aperitivo amargo sobre el cubo de hielo de la lista en un vaso corto.",
        "Remueve unos 20–30 segundos y sirve. Esta versión no requiere piel de naranja añadida.",
    ],
    "cosmopolitan": [
        "Agita el vodka, el licor de naranja, el jugo de arándano, el jugo de limón y el hielo de la lista en una coctelera cerrada durante unos 15 segundos.",
        "Cuela en una copa fría y sirve. No necesitas añadir piel de naranja ni otra decoración para preparar esta versión.",
    ],
    "aperol_spritz": [
        "Pon el hielo de la lista en una copa amplia y añade el vino prosecco y el aperitivo amargo de naranja.",
        "Completa lentamente con el agua con gas, remueve suavemente y sirve. No agites las bebidas gaseosas en una coctelera ni añadas naranja que no figure en la lista.",
    ],
    "mai_tai": [
        "Agita los dos rones, el licor de naranja, el jugo de limón, el jarabe de almendra y el hielo de la lista en una coctelera cerrada unos 15 segundos.",
        "Vierte en un vaso, con el hielo que ya utilizaste, y sirve. No requiere una rodaja adicional de limón; contiene almendra y alcohol.",
    ],
    "cookies": [
        "Precalienta el horno a 180 °C y prepara bandejas con papel para hornear. Usa mantequilla blanda, no derretida, y bátela con el azúcar blanco y el moreno hasta obtener una crema uniforme.",
        "Añade los huevos uno a uno y mezcla. Incorpora la harina sólo hasta que no se vea seca, y después reparte las chispas de chocolate en la masa. No pruebes la masa cruda.",
        "Forma porciones del tamaño de una cucharada y sepáralas unos 5 cm en la bandeja. Si la masa está demasiado blanda, refrigérala unos 20 minutos antes de formar las porciones.",
        "Hornea cada bandeja unos 10–14 minutos, hasta que los bordes estén dorados y el centro haya perdido el brillo de masa cruda. Son galletas sin impulsor añadido; no esperes que suban como un bizcocho.",
        "Deja reposar 5 minutos sobre la bandeja y pásalas a una rejilla para que se enfríen. La cantidad de galletas depende del tamaño; las porciones indicadas no equivalen necesariamente a una galleta cada una.",
    ],
    "pizza": [
        "Mezcla la harina con la levadura seca instantánea. Añade el agua tibia y el aceite de la lista; amasa unos 8 minutos hasta obtener una masa uniforme y elástica.",
        "Cubre y deja crecer alrededor de 1 hora, hasta que la masa duplique su volumen. No pruebes la masa cruda.",
        "Precalienta el horno a 240 °C. Estira la masa sobre papel para hornear en una pizza de unos 30–32 cm, o divide en pizzas más pequeñas de grosor similar.",
        "Reparte la salsa de tomate y la mozzarella, dejando un pequeño borde libre. Esta versión sólo lleva esos ingredientes; no requiere carnes ni otros añadidos.",
        "Hornea sobre una bandeja unos 12–18 minutos, hasta que la base esté firme, los bordes dorados y el queso fundido. Si la base sigue húmeda o cruda, continúa unos minutos vigilando que el queso no se queme.",
        "Retira con cuidado, deja reposar 2 minutos y corta. Si cambias el tamaño o grosor, ajusta el tiempo comprobando siempre la base.",
    ],
    "soup": [
        "Lava los vegetales; pela la papa, la zanahoria y la cebolla. Corta papa y zanahoria en dados de unos 2 cm y pica la cebolla.",
        "Calienta el aceite de la lista en una olla a fuego medio y cocina la cebolla unos 4 minutos, removiendo sin quemarla.",
        "Añade la papa, la zanahoria y el caldo. Lleva a hervor suave, baja el fuego y cocina parcialmente tapado unos 20–25 minutos.",
        "Comprueba con un tenedor que papa y zanahoria estén tiernas antes de servir. El caldo aporta su sazón; esta lista no incluye sal adicional.",
    ],
    "salad": [
        "Lava tomate, pepino, limón y la piel del aguacate antes de cortarlos. Usa una tabla y utensilios limpios.",
        "Corta el tomate y el pepino en dados. Abre el aguacate justo antes de servir, retira el hueso y corta la pulpa en láminas.",
        "Exprime el limón, retira sus semillas y mezcla el jugo con el aceite de oliva. Reparte sobre los vegetales y el aguacate, mezcla suavemente y sirve; esta versión no necesita sal ni otros ingredientes añadidos.",
    ],
}

CATEGORIES = {
    "rice": "rice", "overnight_oats": "breakfast", "tuna_bowl": "bowls_salads",
    "pina_colada_zero": "smoothies", "virgin_mojito": "juices", "pizza": "baked",
    "salad": "bowls_salads", "soup": "soups",
}
EGG_KEYS = frozenset({"flan", "cheesecake", "tres_leches", "brownies", "cookies"})
FLOUR_KEYS = frozenset({"tres_leches", "brownies", "cookies", "apple_pie", "bread", "pizza"})


def apply_core_followup(key: str, recipe: dict[str, Any]) -> bool:
    """Apply a named original repair in place; return whether it was reviewed.

    Unknown, installed and pet rows are never promoted, even when their title
    resembles an original. User IDs/photos/favorites and ingredients stay intact.
    """
    if key not in STEPS or key.startswith("installed_") or recipe.get("audience") == "pet":
        return False
    recipe["steps"] = list(STEPS[key])
    if key in CATEGORIES:
        recipe["category"] = CATEGORIES[key]
    recipe["editorial_status"] = "reviewed_local"
    recipe["editorial_revision"] = REVISION
    recipe["source_context"] = SOURCE_CONTEXT
    sources = [HANDLING_SOURCE]
    if key in EGG_KEYS:
        sources.append(EGG_SOURCE)
    if key in FLOUR_KEYS:
        sources.append(FLOUR_SOURCE)
    recipe["sources"] = deepcopy(sources)
    # Clarify which pantry variants the existing quantities assume, without
    # changing shopping amounts or adding foods absent from the preparation.
    notes = {
        "rice": {"Arroz": "blanco de grano largo"},
        "overnight_oats": {"Avena": "en hojuelas", "Leche": "pasteurizada", "Yogur natural": "pasteurizado"},
        "tuna_bowl": {"Atún": "en conserva, listo para comer; escurrido", "Garbanzos cocidos": "listos para comer; escurridos"},
        "bread": {"Levadura seca": "instantánea"},
        "pizza": {"Levadura seca": "instantánea"},
        "flan": {"Leche condensada": "lata estándar de unos 397 g", "Leche evaporada": "lata estándar de unos 354 ml"},
        "tres_leches": {"Leche condensada": "lata estándar de unos 397 g", "Leche evaporada": "lata estándar de unos 354 ml", "Crema de leche": "pasteurizada"},
        "cheesecake": {"Queso crema": "entero, pasteurizado", "Galleta": "dulce, tipo digestive o Graham"},
    }.get(key, {})
    for ingredient in recipe.get("ingredients", []):
        if ingredient.get("name") in notes:
            ingredient["notes"] = notes[ingredient["name"]]
    return True
