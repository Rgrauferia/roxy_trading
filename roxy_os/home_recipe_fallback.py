from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from functools import lru_cache
from typing import Any

from roxy_os.home_recipe_catalog import installed_recipe_templates
from roxy_os.home_recipe_editorial import editorialize_recipe


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


def _pet_templates() -> dict[str, dict[str, Any]]:
    dog = _recipe(
        "Galletas de avena y plátano para perros", "Premio horneado ocasional, sin azúcar, chocolate, pasas ni xilitol.", "other", 18,
        [("Plátano maduro", 1, "unidad"), ("Avena en hojuelas", 1.5, "taza")],
        ["Calienta el horno a 175 °C y cubre una bandeja con papel para hornear.", "Tritura el plátano hasta obtener un puré sin trozos grandes.", "Muele una taza de avena hasta formar harina y mézclala con el puré y la avena restante.", "Extiende la masa a 6 milímetros, corta porciones pequeñas y colócalas en la bandeja.", "Hornea de 15 a 18 minutos, hasta que estén firmes; enfría por completo antes de ofrecer una."],
    )
    dog.update(audience="pet", pet_species="dog", safety_class="treat", veterinary_note="Premio ocasional; no sustituye un alimento completo. Confirma la porción con tu veterinario si tu perro tiene alergias o una dieta especial.", photo_asset="/assets/roxy_home/recipes/pets/dog-banana-oat-treats.jpg")
    dog_pumpkin = _recipe(
        "Galletas de calabaza y avena para perros", "Premio horneado sencillo con calabaza pura, sin azúcar ni especias.", "other", 20,
        [("Puré de calabaza 100 % natural", 0.75, "taza"), ("Avena en hojuelas", 2, "taza"), ("Huevo", 1, "unidad")],
        ["Calienta el horno a 175 °C y cubre una bandeja con papel para hornear.", "Muele la avena hasta obtener una harina gruesa y confirma que el puré no contenga azúcar, xilitol ni especias.", "Bate el huevo con el puré y añade la avena poco a poco hasta formar una masa manejable.", "Extiende la masa a 6 milímetros, corta porciones pequeñas y colócalas separadas en la bandeja.", "Hornea de 18 a 22 minutos, enfría por completo y ofrece una porción acorde con el tamaño de tu perro."],
    )
    dog_pumpkin.update(audience="pet", pet_species="dog", safety_class="treat", veterinary_note="Premio ocasional; no sustituye un alimento completo. Usa solo calabaza pura y confirma la porción con tu veterinario.", photo_asset="/assets/roxy_home/recipes/pets/dog-pumpkin-oat-biscuits.png")
    dog_yogurt = _recipe(
        "Bocaditos helados de yogur y arándanos para perros", "Premio congelado de yogur natural sin azúcar ni xilitol.", "other", 12,
        [("Yogur natural sin azúcar ni xilitol", 1, "taza"), ("Arándanos frescos", 0.5, "taza")],
        ["Lee la etiqueta del yogur y confirma que sea natural, sin azúcar, xilitol, chocolate ni saborizantes.", "Lava los arándanos y tritura la mitad con un tenedor.", "Mezcla el yogur con los arándanos triturados y reparte la mezcla en moldes pequeños.", "Añade uno o dos arándanos enteros a cada molde y congela durante al menos tres horas.", "Desmolda una porción y deja que se suavice uno o dos minutos antes de ofrecerla; no la uses si tu perro no tolera lácteos."],
    )
    dog_yogurt.update(audience="pet", pet_species="dog", safety_class="treat", veterinary_note="Premio ocasional; no sustituye un alimento completo. Evítalo si tu perro tiene sensibilidad a los lácteos y consulta al veterinario ante cualquier dieta especial.", photo_asset="/assets/roxy_home/recipes/pets/dog-blueberry-yogurt-bites.png")
    dog_meatballs = _recipe(
        "Mini albóndigas de pollo y zanahoria para perros", "Bocaditos de pollo completamente cocidos, sin sal, ajo ni cebolla.", "other", 16,
        [("Pollo molido sin condimentos", 300, "gramo"), ("Zanahoria", 0.5, "taza", "rallada fina"), ("Huevo", 1, "unidad")],
        ["Calienta el horno a 190 °C y cubre una bandeja con papel para hornear.", "Revisa que el pollo no contenga sal, ajo, cebolla, salsas ni condimentos añadidos.", "Mezcla el pollo con la zanahoria y el huevo hasta distribuirlos de forma uniforme.", "Forma bolitas pequeñas y hornéalas de 14 a 18 minutos, hasta que el centro alcance 74 °C.", "Enfría por completo, divide según el tamaño de tu perro y refrigera el resto por un máximo de dos días."],
    )
    dog_meatballs.update(audience="pet", pet_species="dog", safety_class="treat", veterinary_note="Premio ocasional; no sustituye un alimento completo. Ajusta el tamaño y la cantidad con tu veterinario.", photo_asset="/assets/roxy_home/recipes/pets/dog-chicken-carrot-meatballs.png")
    bernese_source = {"title": "AKC · Bernese Mountain Dog", "url": "https://www.akc.org/dog-breeds/bernese-mountain-dog/", "authority": "American Kennel Club"}
    bernese_variants: dict[str, dict[str, Any]] = {}
    for key, base, title, description, variety in [
        ("bernese_young_banana_oat", dog, "Mini premios de plátano y avena para Bernese joven", "Bocados pequeños para entrenamiento de un Bernese Mountain Dog joven; se cuentan como premios y no reemplazan su alimento completo.", "Horneado"),
        ("bernese_young_pumpkin_oat", dog_pumpkin, "Galletas pequeñas de calabaza para Bernese joven", "Premio ocasional en piezas pequeñas para un Bernese Mountain Dog joven, sin convertirlo en una ración completa.", "Horneado"),
        ("bernese_young_blueberry_yogurt", dog_yogurt, "Bocaditos fríos de arándanos para Bernese joven", "Premio frío ocasional para un Bernese Mountain Dog joven, únicamente si tolera lácteos y su veterinario no indicó evitarlos.", "Frío"),
        ("bernese_young_chicken_carrot", dog_meatballs, "Mini bocados de pollo para Bernese joven", "Bocados cocidos y pequeños para entrenamiento de un Bernese Mountain Dog joven; la cantidad depende del peso real y del plan veterinario.", "Proteína horneada"),
    ]:
        row = deepcopy(base)
        row.update(
            title=title,
            description=description,
            pet_exact_terms=["bernese mountain", "bernese mountain dog"],
            pet_life_stages=["baby", "young"],
            pet_variety=variety,
            personalization_scope="breed_and_life_stage",
            editorial_status="verified_veterinary_guidance",
            sources=[bernese_source],
        )
        bernese_variants[key] = row
    cat = _recipe(
        "Bocaditos de pollo cocido para gatos", "Pollo simple y completamente cocido para usar como premio ocasional.", "other", 8,
        [("Pechuga de pollo sin piel ni hueso", 120, "gramo"), ("Agua", 2, "taza")],
        ["Revisa que el pollo no tenga piel, huesos, sal, ajo, cebolla ni condimentos.", "Coloca el pollo y el agua en una olla pequeña y lleva a hervor suave.", "Cocina de 12 a 15 minutos, hasta que el centro alcance 74 °C y no quede parte rosada.", "Deja enfriar, desmenuza muy fino y divide en bocados pequeños adecuados para tu gato.", "Ofrece solo una porción pequeña y refrigera el resto por un máximo de dos días."],
    )
    cat.update(audience="pet", pet_species="cat", safety_class="treat", veterinary_note="Premio ocasional; no sustituye una dieta completa para gatos. Consulta al veterinario para alimentación habitual.", photo_asset="/assets/roxy_home/recipes/pets/cat-cooked-chicken-bites.jpg")
    cat_salmon = _recipe(
        "Lascas de salmón cocido para gatos", "Salmón simple, sin espinas, piel, sal ni condimentos.", "other", 8,
        [("Filete de salmón sin piel ni espinas", 120, "gramo")],
        ["Pasa los dedos por el filete y retira cualquier espina, piel o resto de escama.", "Calienta el horno a 190 °C y coloca el salmón en una fuente sin aceite ni condimentos.", "Hornea de 10 a 14 minutos, hasta que se desmenuce con facilidad y alcance al menos 63 °C en el centro.", "Déjalo enfriar por completo y revisa nuevamente que no haya espinas.", "Separa lascas muy pequeñas, ofrece una porción ocasional y refrigera el resto por un máximo de dos días."],
    )
    cat_salmon.update(audience="pet", pet_species="cat", safety_class="treat", veterinary_note="Premio ocasional; no sustituye una dieta completa para gatos. Consulta al veterinario si tu gato tiene enfermedad renal, alergias o una dieta prescrita.", photo_asset="/assets/roxy_home/recipes/pets/cat-cooked-salmon-flakes.png")
    cat_turkey = _recipe(
        "Mini tortitas de pavo para gatos", "Pavo completamente cocido y sin condimentos para ofrecer en pequeñas cantidades.", "other", 10,
        [("Pavo molido sin condimentos", 180, "gramo"), ("Agua", 1, "cucharada")],
        ["Comprueba que el pavo no incluya sal, ajo, cebolla, salsas, cereales ni especias.", "Forma tortitas pequeñas y finas con las manos ligeramente humedecidas.", "Calienta una sartén antiadherente a fuego medio-bajo, sin aceite ni mantequilla.", "Cocina las tortitas por ambos lados hasta que alcancen 74 °C y no quede carne rosada.", "Enfría por completo, corta un trozo pequeño para servir y refrigera el resto por un máximo de dos días."],
    )
    cat_turkey.update(audience="pet", pet_species="cat", safety_class="treat", veterinary_note="Premio ocasional; no sustituye una dieta completa y equilibrada para gatos. Confirma la porción con tu veterinario.", photo_asset="/assets/roxy_home/recipes/pets/cat-turkey-mini-patties.png")
    cat_egg_chicken = _recipe(
        "Bocaditos de huevo y pollo para gatos", "Pequeños bocados de huevo y pollo completamente cocidos, sin lácteos ni condimentos.", "other", 10,
        [("Huevo", 1, "unidad"), ("Pollo cocido sin piel ni hueso", 60, "gramo")],
        ["Desmenuza el pollo cocido muy fino y confirma que no tenga piel, huesos, sal, ajo ni cebolla.", "Bate el huevo solo, sin leche, mantequilla, sal ni condimentos.", "Cocina el huevo en una sartén antiadherente a fuego bajo hasta que quede completamente cuajado.", "Incorpora el pollo, cocina un minuto más y deja enfriar por completo.", "Corta bocados muy pequeños, ofrece una porción ocasional y refrigera el resto por un máximo de un día."],
    )
    cat_egg_chicken.update(audience="pet", pet_species="cat", safety_class="treat", veterinary_note="Premio ocasional; no sustituye una dieta completa para gatos. Consulta al veterinario si existe sensibilidad al huevo o al pollo.", photo_asset="/assets/roxy_home/recipes/pets/cat-egg-chicken-bites.png")
    ferret_source = {"title": "Oxbow · guía de cuidado del hurón", "url": "https://oxbowanimalhealth.com/wp-content/uploads/2023/10/Ferret-Care-Guide-Jul-2022.pdf", "authority": "Oxbow Animal Health"}
    ferret = _recipe(
        "Bocaditos de pavo cocido para hurones", "Premio pequeño de carne simple y completamente cocida, sin cereales ni condimentos.", "other", 10,
        [("Pavo molido sin condimentos", 150, "gramo")],
        ["Comprueba que el pavo no contenga sal, ajo, cebolla, salsas, vegetales ni cereales añadidos.", "Calienta una sartén antiadherente a fuego medio-bajo, sin aceite ni mantequilla.", "Añade el pavo y sepáralo en trozos muy pequeños mientras se cocina.", "Cocina hasta alcanzar 74 °C y hasta que no quede carne rosada; escurre la grasa sobrante.", "Deja enfriar por completo y ofrece uno o dos trozos pequeños como premio ocasional."],
    )
    ferret.update(audience="pet", pet_species="ferret", safety_class="treat", veterinary_note="Premio ocasional; no sustituye una dieta completa para hurones. Consulta a un veterinario de animales exóticos.", photo_asset="/assets/roxy_home/recipes/pets/ferret-cooked-turkey-bites.jpg", sources=[ferret_source])
    ferret_hearts = _recipe(
        "Bocaditos de corazón de pollo para hurones", "Víscera simple completamente cocida y cortada en porciones muy pequeñas.", "other", 12,
        [("Corazones de pollo limpios", 150, "gramo")],
        ["Retira grasa visible y confirma que los corazones no tengan sal, salsas, vegetales ni condimentos.", "Enjuágalos, sécalos y córtalos por la mitad para que se cocinen de manera uniforme.", "Cocínalos en una sartén antiadherente a fuego medio-bajo, sin aceite, durante 8 a 10 minutos.", "Comprueba que el centro alcance 74 °C y que no quede tejido crudo.", "Enfría por completo, corta trozos muy pequeños y ofrece solo uno o dos como premio ocasional."],
    )
    ferret_hearts.update(audience="pet", pet_species="ferret", safety_class="treat", veterinary_note="Premio ocasional y en poca cantidad; no sustituye un alimento completo. Las vísceras no deben desplazar su dieta habitual. Consulta a un veterinario de animales exóticos.", photo_asset="/assets/roxy_home/recipes/pets/ferret-chicken-heart-bites.png", sources=[ferret_source])
    ferret_egg = _recipe(
        "Bocaditos de huevo cocido para hurones", "Huevo completamente cocido, sin leche, mantequilla ni condimentos.", "other", 8,
        [("Huevo", 1, "unidad")],
        ["Rompe el huevo en un recipiente limpio y bátelo sin añadir leche, aceite, sal ni especias.", "Calienta una sartén antiadherente a fuego bajo.", "Vierte el huevo y remueve hasta que esté completamente cuajado y no quede parte líquida.", "Déjalo enfriar por completo y divídelo en trozos muy pequeños.", "Ofrece uno o dos trozos como premio ocasional y desecha lo que permanezca a temperatura ambiente más de dos horas."],
    )
    ferret_egg.update(audience="pet", pet_species="ferret", safety_class="treat", veterinary_note="Premio ocasional; no sustituye una dieta completa para hurones. Confirma la frecuencia con un veterinario de animales exóticos.", photo_asset="/assets/roxy_home/recipes/pets/ferret-cooked-egg-bites.png", sources=[ferret_source])
    ferret_beef = _recipe(
        "Bocaditos de res cocida para hurones", "Carne magra completamente cocida y sin vegetales, cereales ni condimentos.", "other", 12,
        [("Carne molida de res magra sin condimentos", 180, "gramo")],
        ["Comprueba que la carne no incluya sal, ajo, cebolla, salsas, cereales ni especias.", "Calienta una sartén antiadherente a fuego medio-bajo, sin aceite ni mantequilla.", "Añade la carne y sepárala en trozos pequeños mientras se cocina.", "Cocina hasta que no quede carne rosada y el centro alcance al menos 71 °C; escurre la grasa sobrante.", "Enfría por completo y ofrece uno o dos trozos pequeños como premio ocasional."],
    )
    ferret_beef.update(audience="pet", pet_species="ferret", safety_class="treat", veterinary_note="Premio ocasional; no sustituye una dieta completa para hurones. Consulta a un veterinario de animales exóticos.", photo_asset="/assets/roxy_home/recipes/pets/ferret-cooked-beef-bites.png", sources=[ferret_source])
    ferret_extra_specs = {
        "ferret_poached_chicken": ("Hebras de pollo cocido para hurones", "Pechuga de pollo sin piel ni hueso", 150, "gramo", "Cocina el pollo en agua a hervor suave hasta que el centro alcance 74 °C.", "Desmenúzalo en hebras muy cortas y ofrece una cantidad pequeña cuando esté completamente frío."),
        "ferret_baked_duck": ("Mini bocados de pato para hurones", "Pechuga de pato sin piel ni hueso", 150, "gramo", "Hornea el pato sin aceite ni condimentos hasta que el centro alcance 74 °C.", "Retira la grasa visible, deja enfriar y corta uno o dos bocados muy pequeños."),
        "ferret_cooked_lamb": ("Miguitas de cordero para hurones", "Cordero magro molido sin condimentos", 150, "gramo", "Cocina el cordero en una sartén antiadherente, sin aceite, hasta alcanzar 71 °C.", "Escurre la grasa, enfría por completo y separa una porción mínima."),
        "ferret_turkey_medallions": ("Mini medallones de pavo para hurones", "Pavo molido sin condimentos", 150, "gramo", "Forma medallones muy pequeños y hornéalos a 190 °C hasta que el centro alcance 74 °C.", "Déjalos enfriar, divide cada medallón y ofrece solo uno o dos trozos."),
    }
    ferret_extras = {}
    for key, (title, ingredient, quantity, unit, cooking, serving) in ferret_extra_specs.items():
        row = _recipe(
            title, "Premio de proteína animal simple, completamente cocida y sin cereales ni condimentos.", "other", 12,
            [(ingredient, quantity, unit)],
            [
                "Lávate las manos y limpia la superficie antes de manipular la carne.",
                "Confirma que el ingrediente no contenga sal, ajo, cebolla, salsas, vegetales ni cereales añadidos.",
                cooking,
                serving,
                "Refrigera el resto por un máximo de dos días y úsalo solo como premio ocasional.",
            ],
        )
        row.update(audience="pet", pet_species="ferret", pet_category="pet_treats", safety_class="treat", veterinary_note="Premio ocasional; no sustituye el alimento completo de un hurón. Confirma ingredientes y porción con un veterinario de animales exóticos.", sources=[ferret_source], editorial_status="verified_veterinary_guidance")
        ferret_extras[key] = row
    recipes = {
        "dog_banana_oat_treats": dog,
        "dog_pumpkin_oat_biscuits": dog_pumpkin,
        "dog_blueberry_yogurt_bites": dog_yogurt,
        "dog_chicken_carrot_meatballs": dog_meatballs,
        "cat_cooked_chicken_bites": cat,
        "cat_cooked_salmon_flakes": cat_salmon,
        "cat_turkey_mini_patties": cat_turkey,
        "cat_egg_chicken_bites": cat_egg_chicken,
        "ferret_cooked_turkey_bites": ferret,
        "ferret_chicken_heart_bites": ferret_hearts,
        "ferret_cooked_egg_bites": ferret_egg,
        "ferret_cooked_beef_bites": ferret_beef,
    }
    recipes.update(bernese_variants)
    recipes.update(ferret_extras)
    rabbit_source = {"title": "Merck Veterinary Manual · Nutrición de conejos", "url": "https://www.merckvetmanual.com/exotic-and-laboratory-animals/rabbits/nutrition-of-rabbits", "authority": "Merck Veterinary Manual"}
    guinea_source = {"title": "Merck Veterinary Manual · Nutrición de cobayas", "url": "https://www.merckvetmanual.com/exotic-and-laboratory-animals/guinea-pigs/housing-and-nutrition-of-guinea-pigs", "authority": "Merck Veterinary Manual"}
    hamster_source = {"title": "Merck Veterinary Manual · Hámsteres", "url": "https://www.merckvetmanual.com/exotic-and-laboratory-animals/rodents/hamsters", "authority": "Merck Veterinary Manual"}
    bird_source = {"title": "Merck Veterinary Manual · Alimentación de aves de compañía", "url": "https://www.merckvetmanual.com/en-us/veterinary/bird-owners/choosing-and-taking-care-of-a-pet-bird/feeding-a-pet-bird", "authority": "Merck Veterinary Manual"}
    additions = {
        "rabbit_morning_greens": _recipe(
            "Verdes frescos de la mañana para conejos", "Complemento fresco de hojas lavadas; el heno sigue siendo la base de la alimentación.", "other", 1,
            [("Lechuga romana", 1, "hoja"), ("Cilantro", 2, "ramita")],
            ["Lávate las manos y usa una tabla limpia, sin restos de cebolla, ajo ni condimentos.", "Lava muy bien la lechuga y el cilantro con agua corriente.", "Sacude el exceso de agua y revisa que no haya partes marchitas o dañadas.", "Rompe las hojas con las manos en trozos fáciles de tomar; no añadas sal, aceite ni aderezos.", "Sirve una cantidad acorde con el plan indicado por su veterinario junto con heno y agua fresca; retira lo que no coma en dos horas."],
        ),
        "rabbit_pepper_herb_plate": _recipe(
            "Platito de pimiento y hierbas para conejos", "Pequeño complemento de vegetales frescos, sin fruta ni ingredientes azucarados.", "other", 1,
            [("Pimiento rojo", 1, "tira pequeña"), ("Perejil", 2, "ramita"), ("Lechuga romana", 1, "hoja")],
            ["Lávate las manos y limpia la superficie de preparación.", "Lava el pimiento, el perejil y la lechuga con agua corriente.", "Retira del pimiento el tallo, las semillas y las partes blancas; corta una tira pequeña en cubos.", "Rompe la lechuga y mezcla suavemente con el pimiento y el perejil, sin sal ni aderezo.", "Ofrece solo la porción acordada con su veterinario y mantén disponible heno de pasto y agua fresca."],
        ),
        "rabbit_cucumber_basil_bites": _recipe(
            "Bocaditos de pepino y albahaca para conejos", "Premio fresco y pequeño para ofrecer de forma ocasional.", "other", 4,
            [("Pepino", 2, "rodaja fina"), ("Albahaca fresca", 2, "hoja")],
            ["Lávate las manos y enjuaga el pepino y la albahaca bajo agua corriente.", "Corta dos rodajas finas de pepino y después divide cada una por la mitad.", "Seca suavemente las hojas de albahaca y córtalas en tiras pequeñas.", "Coloca una pizca de albahaca sobre cada trozo de pepino; no añadas sal, aceite ni especias.", "Ofrece un solo trozo como premio ocasional y retira lo que no coma pronto; no reemplaza heno, pellets apropiados ni agua."],
        ),
        "guinea_morning_vitamin_c": _recipe(
            "Pimiento y hojas de la mañana para cobayas", "Complemento fresco con pimiento; no sustituye pellets formulados ni heno.", "other", 1,
            [("Pimiento rojo", 2, "tira pequeña"), ("Lechuga romana", 1, "hoja"), ("Cilantro", 2, "ramita")],
            ["Lávate las manos y usa utensilios limpios.", "Lava el pimiento, la lechuga y el cilantro con agua corriente.", "Retira tallo, semillas y partes blancas del pimiento y córtalo en tiras pequeñas.", "Rompe las hojas y combina los vegetales sin sal, aceite, azúcar ni aderezos.", "Sirve la cantidad indicada para tu cobaya junto con heno, pellets específicos y agua; retira las sobras frescas en dos horas."],
        ),
        "guinea_cucumber_pepper_plate": _recipe(
            "Platito fresco de pepino y pimiento para cobayas", "Complemento vegetal hidratante en una porción controlada.", "other", 1,
            [("Pepino", 2, "rodaja fina"), ("Pimiento verde", 1, "tira pequeña")],
            ["Lava tus manos, el cuchillo y la tabla antes de comenzar.", "Enjuaga el pepino y el pimiento con agua corriente.", "Retira el tallo y las semillas del pimiento y córtalo en cubos pequeños.", "Divide las rodajas de pepino en trozos y mézclalas con el pimiento, sin condimentos.", "Ofrece una porción pequeña dentro de su ración habitual de vegetales y retira las sobras en dos horas."],
        ),
        "guinea_herb_foraging_cup": _recipe(
            "Copa de hierbas para explorar para cobayas", "Pequeño enriquecimiento de hojas frescas y seguras.", "other", 1,
            [("Cilantro", 3, "ramita"), ("Perejil", 1, "ramita"), ("Lechuga romana", 1, "hoja")],
            ["Consulta el plan alimentario de tu cobaya si tiene antecedentes urinarios o una dieta prescrita.", "Lava todas las hojas con agua corriente y desecha las partes dañadas.", "Sécalas suavemente y corta la lechuga en tiras anchas.", "Coloca las hierbas dentro de la hoja doblada para formar un pequeño paquete de exploración, sin cuerda ni sujetadores.", "Entrégalo bajo supervisión y retira las hojas que no consuma en dos horas; no reemplaza heno ni pellets formulados."],
        ),
        "hamster_morning_oat": _recipe(
            "Avena simple de la mañana para hámsteres", "Porción diminuta y ocasional; el alimento completo para hámster sigue siendo la base.", "other", 1,
            [("Avena en hojuelas simple", 1, "cucharadita"), ("Agua", 2, "cucharadita")],
            ["Confirma que la avena sea simple, sin azúcar, saborizantes, chocolate, frutas secas ni edulcorantes.", "Mezcla la avena y el agua en un recipiente pequeño apto para calor.", "Cocina hasta que la avena esté blanda y haya absorbido el agua; no añadas leche, sal ni miel.", "Déjala enfriar completamente y separa una porción del tamaño indicado por su veterinario.", "Ofrece solo una cantidad diminuta y retira las sobras húmedas en una hora para evitar que las almacene."],
        ),
        "hamster_egg_crumb": _recipe(
            "Miguita de huevo cocido para hámsteres", "Premio proteico diminuto y completamente cocido.", "other", 4,
            [("Huevo", 1, "unidad")],
            ["Coloca el huevo en una olla, cúbrelo con agua y llévalo a hervor.", "Cocínalo 10 minutos para que la clara y la yema queden completamente firmes.", "Enfríalo en agua, pélalo y corta una miguita muy pequeña, sin sal ni condimentos.", "Deja que la porción alcance temperatura ambiente antes de ofrecerla.", "Entrega solo la cantidad aprobada para su especie y tamaño; refrigera el resto para consumo humano y retira cualquier sobra de la jaula en una hora."],
        ),
        "hamster_cucumber_seedless": _recipe(
            "Cuadrito de pepino para hámsteres", "Premio fresco de tamaño muy pequeño para ofrecer ocasionalmente.", "other", 2,
            [("Pepino", 1, "rodaja muy fina")],
            ["Lava tus manos, el cuchillo y el pepino con agua corriente.", "Corta una rodaja muy fina y retira las semillas grandes si las hubiera.", "Divide la rodaja en dos cuadritos diminutos, adecuados al tamaño del hámster.", "Seca la superficie con papel limpio para reducir el exceso de humedad.", "Ofrece un solo cuadrito y retíralo en una hora si lo guarda; no sustituye el alimento completo formulado."],
        ),
        "bird_morning_chop": _recipe(
            "Chop de vegetales de la mañana para aves", "Complemento fresco para aves que ya toleran estos vegetales; la dieta formulada sigue siendo la base.", "other", 2,
            [("Pimiento rojo", 1, "tira"), ("Brócoli", 1, "florete pequeño"), ("Zanahoria", 1, "rodaja fina")],
            ["Confirma con un veterinario aviar que estos vegetales sean apropiados para la especie de tu ave.", "Lava tus manos, la tabla y todos los vegetales con agua corriente.", "Retira semillas y tallo del pimiento y pica todos los vegetales en trozos adecuados al tamaño del pico.", "Mézclalos sin sal, aceite, aguacate, ajo, cebolla ni condimentos.", "Sirve una porción pequeña en un recipiente limpio y retírala después de dos horas; no reemplaza pellets formulados ni agua."],
        ),
        "bird_quinoa_vegetable": _recipe(
            "Quinoa tibia con vegetales para aves", "Complemento ocasional de quinoa cocida y vegetales, adaptado a la especie.", "other", 4,
            [("Quinoa", 2, "cucharada"), ("Agua", 0.25, "taza"), ("Pimiento rojo", 1, "tira pequeña")],
            ["Enjuaga la quinoa varias veces hasta que el agua salga clara.", "Cocínala en el agua sin sal ni aceite hasta que esté tierna y el líquido se absorba.", "Lava el pimiento, retira tallo y semillas y pícalo muy fino.", "Mezcla una pequeña cantidad de pimiento con la quinoa y deja enfriar por completo.", "Sirve una porción apropiada para la especie y retira las sobras en dos horas; conserva el resto refrigerado por un máximo de un día."],
        ),
        "bird_apple_carrot": _recipe(
            "Picadito de manzana y zanahoria para aves", "Premio fresco ocasional; la manzana se prepara sin semillas ni corazón.", "other", 3,
            [("Manzana", 1, "gajo pequeño"), ("Zanahoria", 1, "rodaja fina")],
            ["Confirma con un veterinario aviar que la preparación sea apropiada para la especie de tu ave.", "Lava la manzana y la zanahoria con agua corriente.", "Retira por completo semillas, corazón y tallo de la manzana.", "Pica la fruta y la zanahoria en trozos adecuados al tamaño del pico, sin azúcar, miel ni condimentos.", "Ofrece una porción pequeña como premio y retira las sobras en dos horas; la fruta no debe desplazar su dieta formulada."],
        ),
    }
    species_sources = {"rabbit": rabbit_source, "guinea_pig": guinea_source, "hamster": hamster_source, "bird": bird_source}
    category_by_key = {
        "rabbit_morning_greens": "pet_morning", "rabbit_pepper_herb_plate": "pet_fresh", "rabbit_cucumber_basil_bites": "pet_treats",
        "guinea_morning_vitamin_c": "pet_morning", "guinea_cucumber_pepper_plate": "pet_fresh", "guinea_herb_foraging_cup": "pet_treats",
        "hamster_morning_oat": "pet_morning", "hamster_egg_crumb": "pet_treats", "hamster_cucumber_seedless": "pet_fresh",
        "bird_morning_chop": "pet_morning", "bird_quinoa_vegetable": "pet_fresh", "bird_apple_carrot": "pet_treats",
    }
    species_by_key = {key: key.split("_", 1)[0] for key in additions}
    species_by_key.update({key: "guinea_pig" for key in additions if key.startswith("guinea_")})
    for key, recipe in additions.items():
        species = species_by_key[key]
        recipe.update(
            audience="pet", pet_species=species, pet_category=category_by_key[key], safety_class="treat",
            veterinary_note="Complemento o premio ocasional; no sustituye una dieta completa. Confirma ingredientes y porción con un veterinario que conozca esta especie.",
            sources=[species_sources[species]], editorial_status="verified_veterinary_guidance",
        )
    recipes.update(additions)
    pet_food_source = {
        "title": "FDA · Alimento completo y equilibrado",
        "url": "https://www.fda.gov/animal-veterinary/animal-health-literacy/complete-and-balanced-pet-food",
        "authority": "U.S. Food and Drug Administration",
    }
    watermelon_source = {
        "title": "AKC · sandía para perros",
        "url": "https://www.akc.org/expert-advice/nutrition/can-dogs-eat-watermelon/",
        "authority": "American Kennel Club",
    }
    extra_treats = {
        "dog_dehydrated_chicken": ("dog", "Tiritas deshidratadas de pollo para perros", "Pechuga de pollo sin piel ni hueso", 250, "gramo", "Corta el pollo en tiras finas y uniformes, sin aceite, sal ni condimentos.", "Deshidrata a 74 °C hasta que las tiras estén completamente cocidas y secas; comprueba primero que el centro haya alcanzado 74 °C."),
        "dog_hard_boiled_egg": ("dog", "Bocaditos de huevo hervido para perros", "Huevo", 1, "unidad", "Hierve el huevo durante 10 minutos, enfríalo y retira toda la cáscara.", "Corta una porción pequeña de clara y yema completamente firmes, sin sal, aceite, mayonesa ni condimentos."),
        "dog_dehydrated_turkey": ("dog", "Láminas deshidratadas de pavo para perros", "Pechuga de pavo sin piel ni hueso", 250, "gramo", "Corta el pavo en láminas finas y confirma que no contenga salmuera, ajo, cebolla ni condimentos.", "Deshidrata a 74 °C hasta que esté completamente cocido y seco, sin zonas blandas o rosadas."),
        "dog_sweet_potato_chews": ("dog", "Tiritas horneadas de batata para perros", "Batata", 1, "unidad", "Lava, pela y corta la batata en tiras delgadas.", "Hornea las tiras a 120 °C de dos a tres horas, girándolas a mitad de cocción."),
        "dog_apple_carrot_oat": ("dog", "Mini bocados de manzana, zanahoria y avena", "Manzana sin semillas ni corazón", 0.5, "unidad", "Ralla la manzana y la zanahoria después de retirar semillas y corazón.", "Mezcla con avena molida, forma bocados pequeños y hornea a 175 °C hasta que estén firmes."),
        "dog_turkey_pumpkin": ("dog", "Bocaditos de pavo y calabaza", "Pavo molido sin condimentos", 250, "gramo", "Mezcla el pavo con puré de calabaza 100 % natural, sin especias.", "Forma porciones pequeñas y hornea a 190 °C hasta que el centro alcance 74 °C."),
        "dog_beef_green_bean": ("dog", "Mini albóndigas de res y judías verdes", "Res molida magra sin condimentos", 250, "gramo", "Pica muy fino las judías verdes simples y mézclalas con la carne.", "Forma bolitas pequeñas y hornea hasta que la carne alcance 71 °C."),
        "dog_frozen_banana_pumpkin": ("dog", "Cubitos fríos de plátano y calabaza", "Plátano maduro", 1, "unidad", "Tritura el plátano con puré de calabaza simple, sin azúcar ni especias.", "Reparte en moldes pequeños y congela por al menos tres horas."),
        "dog_chicken_training_bits": ("dog", "Daditos de pollo para entrenamiento", "Pechuga de pollo sin piel ni hueso", 200, "gramo", "Corta el pollo sin condimentos en dados muy pequeños.", "Hornea a 190 °C hasta que todos los dados alcancen 74 °C en el centro."),
        "cat_whitefish_flakes": ("cat", "Lascas de pescado blanco para gatos", "Filete de bacalao sin piel ni espinas", 120, "gramo", "Revisa cuidadosamente el pescado y elimina piel y espinas.", "Hornea sin aceite ni condimentos hasta que se desmenuce y esté completamente cocido."),
        "cat_beef_crumbles": ("cat", "Miguitas de res cocida para gatos", "Res molida magra sin condimentos", 120, "gramo", "Separa la carne en miguitas pequeñas en una sartén antiadherente.", "Cocina sin aceite ni condimentos hasta alcanzar 71 °C y escurre la grasa."),
        "cat_plain_shrimp": ("cat", "Trocitos de camarón cocido para gatos", "Camarón crudo pelado y desvenado", 80, "gramo", "Confirma que el camarón esté pelado, desvenado y sin sal ni aditivos.", "Hiérvelo en agua simple hasta que quede opaco y completamente cocido."),
        "cat_turkey_flakes": ("cat", "Lascas de pavo cocido para gatos", "Pechuga de pavo sin piel ni hueso", 120, "gramo", "Revisa que el pavo no contenga salmuera, ajo, cebolla ni condimentos.", "Hornéalo sin aceite hasta que alcance 74 °C y desmenúzalo muy fino."),
        "cat_rabbit_morsels": ("cat", "Bocaditos de conejo cocido para gatos", "Carne de conejo deshuesada sin condimentos", 120, "gramo", "Retira por completo huesos, grasa visible y cualquier condimento.", "Cocina la carne hasta que esté completamente hecha y córtala en bocados mínimos."),
        "cat_dehydrated_chicken": ("cat", "Miguitas deshidratadas de pollo para gatos", "Pechuga de pollo sin piel ni hueso", 180, "gramo", "Corta el pollo en láminas muy finas y uniformes, sin aceite ni condimentos.", "Deshidrata a 74 °C hasta que esté completamente cocido y seco; al enfriar, separa miguitas muy pequeñas."),
        "cat_hard_boiled_egg": ("cat", "Miguitas de huevo hervido para gatos", "Huevo", 1, "unidad", "Hierve el huevo durante 10 minutos, enfríalo y retira toda la cáscara.", "Separa una miguita de clara y yema totalmente firmes, sin leche, aceite, sal ni condimentos."),
        "cat_dehydrated_whitefish": ("cat", "Lascas deshidratadas de pescado blanco para gatos", "Filete de pescado blanco sin piel ni espinas", 160, "gramo", "Revisa el filete con cuidado, retira piel y todas las espinas y córtalo en láminas finas.", "Deshidrata hasta que el pescado esté completamente cocido y seco; vuelve a revisar espinas antes de desmenuzar."),
    }
    for key, (species, title, ingredient_name, quantity, unit, prep, cooking) in extra_treats.items():
        recipe = _recipe(
            title,
            "Premio casero ocasional preparado sin sal, ajo, cebolla, azúcar ni condimentos.",
            "other",
            10,
            [(ingredient_name, quantity, unit)],
            [
                "Lávate las manos y limpia la superficie y los utensilios antes de comenzar.",
                prep,
                cooking,
                "Deja enfriar por completo y divide en porciones muy pequeñas adecuadas al tamaño de la mascota.",
                "Ofrece solo como premio ocasional y refrigera el resto por un máximo de dos días; no sustituye su alimento completo.",
            ],
        )
        recipe.update(
            audience="pet", pet_species=species, pet_category="pet_treats", safety_class="treat",
            veterinary_note="Premio ocasional; no sustituye una dieta completa y equilibrada. Confirma ingredientes y porción con tu veterinario si existen alergias, enfermedad o dieta prescrita.",
            sources=[pet_food_source], editorial_status="verified_veterinary_guidance",
        )
        if "dehydrated" in key:
            recipe["pet_variety"] = "Deshidratado"
        elif "hard_boiled" in key:
            recipe["pet_variety"] = "Hervido"
        recipes[key] = recipe
    bernese_exact_specs = [
        ("bernese_young_turkey_pumpkin", "dog_turkey_pumpkin", "Bocaditos de pavo y calabaza para Bernese joven", "Premios pequeños de proteína cocida para entrenamiento; la cantidad se ajusta al peso real de un Bernese joven.", "/assets/roxy_home/recipes/pets/bernese-turkey-pumpkin.jpg", "Proteína horneada"),
        ("bernese_young_beef_green_bean", "dog_beef_green_bean", "Mini albóndigas de res para Bernese joven", "Bocados cocidos de res magra y judías verdes para uso ocasional, separados del alimento completo diario.", "/assets/roxy_home/recipes/pets/bernese-beef-green-bean.jpg", "Proteína horneada"),
        ("bernese_young_banana_pumpkin", "dog_frozen_banana_pumpkin", "Cubitos fríos de plátano y calabaza para Bernese joven", "Premio congelado ocasional en cubos pequeños, sin azúcar, especias ni xilitol.", "/assets/roxy_home/recipes/pets/bernese-banana-pumpkin.jpg", "Congelado"),
        ("bernese_young_sweet_potato", "dog_sweet_potato_chews", "Tiritas horneadas de batata para Bernese joven", "Tiras simples y horneadas para ofrecer de forma ocasional y siempre con supervisión.", "/assets/roxy_home/recipes/pets/bernese-sweet-potato.jpg", "Horneado crujiente"),
        ("bernese_young_apple_carrot", "dog_apple_carrot_oat", "Bocaditos de manzana y zanahoria para Bernese joven", "Alternativa horneada con fruta sin semillas ni corazón; se ofrece en piezas pequeñas y solo como premio.", "/assets/roxy_home/recipes/pets/bernese-apple-carrot.jpg", "Horneado frutal"),
        ("bernese_young_chicken_training", "dog_chicken_training_bits", "Daditos de pollo para entrenamiento de Bernese joven", "Proteína simple completamente cocida, cortada en dados pequeños y contabilizada dentro de sus premios diarios.", "/assets/roxy_home/recipes/pets/bernese-chicken-training.jpg", "Proteína simple"),
    ]
    for key, source_key, title, description, photo_asset, variety in bernese_exact_specs:
        row = deepcopy(recipes[source_key])
        row.update(
            title=title,
            description=description,
            photo_asset=photo_asset,
            pet_exact_terms=["bernese mountain", "bernese mountain dog"],
            pet_life_stages=["baby", "young"],
            pet_variety=variety,
            personalization_scope="breed_and_life_stage",
            sources=[bernese_source, pet_food_source],
        )
        recipes[key] = row
    bernese_fresh_specs = {
        "bernese_young_watermelon": _recipe(
            "Cubitos congelados de sandía para Bernese joven",
            "Premio fresco ocasional preparado solo con sandía sin semillas, sin cáscara y en cubos pequeños.",
            "other", 12,
            [("Sandía sin semillas ni cáscara", 1, "taza")],
            [
                "Lávate las manos, limpia la superficie y enjuaga el exterior de la sandía antes de cortarla.",
                "Retira por completo la cáscara, la parte blanca y cualquier semilla visible.",
                "Corta la pulpa en cubos pequeños apropiados para entrenamiento; no añadas azúcar ni endulzantes.",
                "Congela los cubos separados durante al menos tres horas y deja suavizar una pieza uno o dos minutos antes de ofrecerla.",
                "Ofrece solo una pequeña cantidad ocasional y evita esta preparación si existe diabetes, intolerancia o una dieta veterinaria que limite fruta.",
            ],
        ),
        "bernese_young_egg_oat": _recipe(
            "Mini bocados de huevo y avena para Bernese joven",
            "Premio horneado suave con huevo completamente cocido, sin leche, mantequilla, sal ni condimentos.",
            "other", 14,
            [("Huevo", 1, "unidad"), ("Avena en hojuelas", 0.75, "taza")],
            [
                "Calienta el horno a 175 °C y cubre una bandeja con papel para hornear.",
                "Muele la mitad de la avena y confirma que no tenga azúcar, saborizantes ni xilitol.",
                "Bate el huevo sin leche ni condimentos y mézclalo con toda la avena.",
                "Forma bocados muy pequeños y hornéalos de 12 a 15 minutos, hasta que el huevo esté completamente cocido.",
                "Enfría por completo, ofrece una sola porción ocasional y refrigera el resto por un máximo de dos días.",
            ],
        ),
    }
    for key, row in bernese_fresh_specs.items():
        row.update(
            audience="pet", pet_species="dog", pet_category="pet_treats", safety_class="treat",
            veterinary_note="Premio ocasional; no sustituye un alimento completo. Si el perfil aún no tiene alergias, peso o alimento actual confirmados, revisa el ingrediente y la porción con su veterinario antes de incorporarlo.",
            photo_asset={
                "bernese_young_watermelon": "/assets/roxy_home/recipes/pets/bernese-watermelon-frozen.jpg",
                "bernese_young_egg_oat": "/assets/roxy_home/recipes/pets/bernese-egg-oat.jpg",
            }[key],
            pet_exact_terms=["bernese mountain", "bernese mountain dog"], pet_life_stages=["baby", "young"],
            pet_variety={"bernese_young_watermelon": "Congelado fresco", "bernese_young_egg_oat": "Horneado suave"}[key],
            personalization_scope="breed_and_life_stage",
            sources=[bernese_source, pet_food_source] + ([watermelon_source] if key == "bernese_young_watermelon" else []),
            editorial_status="verified_veterinary_guidance",
        )
        recipes[key] = row
    feeding_guide_specs = {
        "fish_general_feeding": ("fish", [], "Guía base para peces de acuario", "Alimento completo específico para la especie y el tamaño de boca", "Observa qué ejemplares comen, retira sobrantes y relaciona cualquier cambio de apetito con la calidad y temperatura del agua.", "Manual Veterinario Merck · peces de acuario", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/aquarium-fishes/management-of-aquarium-fish"),
        "fish_betta_feeding": ("fish", ["betta"], "Rutina de alimentación para betta", "Alimento completo específico para betta", "Observa que coma cada porción y retira lo que quede sin consumir.", "Manual Veterinario Merck · peces de acuario", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/aquarium-fishes/management-of-aquarium-fish"),
        "fish_goldfish_feeding": ("fish", ["goldfish", "carassius"], "Rutina de alimentación para goldfish", "Alimento completo específico para goldfish", "Ajusta la presentación del alimento al tamaño de la boca y evita que queden restos en el agua.", "Manual Veterinario Merck · peces de acuario", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/aquarium-fishes/management-of-aquarium-fish"),
        "fish_tropical_feeding": ("fish", ["guppy", "molly", "platy", "tetra", "danio", "corydora", "gourami"], "Rutina para peces tropicales pequeños", "Alimento completo para la especie y tamaño de boca", "Comprueba que los habitantes alcancen el alimento sin sobrealimentar el acuario.", "Manual Veterinario Merck · peces de acuario", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/aquarium-fishes/management-of-aquarium-fish"),
        "reptile_leopard_gecko_feeding": ("reptile", ["gecko leopardo"], "Rutina alimentaria para gecko leopardo", "Insectos alimentadores apropiados para la especie", "Registra apetito, muda y peso; la suplementación depende del UVB, la dieta y la indicación profesional.", "Manual Veterinario Merck · reptiles", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/reptiles/management-and-husbandry-of-reptiles"),
        "reptile_bearded_dragon_feeding": ("reptile", ["dragon barbudo"], "Rutina alimentaria para dragón barbudo", "Alimento apropiado para su etapa de vida", "Separa alimento animal y vegetal según etapa y confirma calcio, UVB y porciones con un veterinario de exóticos.", "Manual Veterinario Merck · reptiles", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/reptiles/management-and-husbandry-of-reptiles"),
        "reptile_general_feeding": ("reptile", [], "Guía base para reptiles", "Dieta formulada o presas apropiadas para la especie exacta", "Confirma con un veterinario de exóticos el tipo de alimento, suplementación, UVB, temperatura y frecuencia antes de cambiar la dieta.", "Manual Veterinario Merck · reptiles", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/reptiles/management-and-husbandry-of-reptiles"),
        "amphibian_axolotl_feeding": ("amphibian", ["ajolote"], "Rutina de alimentación para ajolote", "Alimento hundible apropiado para ajolote", "Retira sobrantes y registra apetito junto con temperatura, amoníaco, nitrito, nitrato y pH.", "ARAV · cuidado de reptiles y anfibios", "https://arav.org/"),
        "amphibian_general_feeding": ("amphibian", [], "Guía base para anfibios", "Alimento apropiado para la especie exacta y su etapa", "La alimentación cambia entre especies acuáticas, terrestres e insectívoras; confirma presas, suplementación y frecuencia con un veterinario de exóticos.", "ARAV · cuidado de reptiles y anfibios", "https://arav.org/"),
        "small_mammal_general_feeding": ("small_mammal", [], "Plan alimentario para pequeños mamíferos", "Alimento formulado para la especie exacta", "Ratas, ratones, chinchillas, degús, erizos y otros pequeños mamíferos no comparten la misma dieta; usa la fórmula de la especie y registra peso y apetito.", "Manual Veterinario Merck · nutrición de roedores", "https://www.merckvetmanual.com/management-and-nutrition/nutrition-exotic-and-zoo-animals/nutrition-in-rodents-and-lagomorphs"),
        "invertebrate_general_feeding": ("invertebrate", [], "Plan seguro para invertebrados", "Alimento o presas apropiadas para la especie exacta", "No uses una dieta genérica: confirma especie, etapa, tipo de presa, agua, temperatura, humedad y relación con la muda antes de definir la rutina.", "Manual Veterinario Merck · nutrición de animales exóticos", "https://www.merckvetmanual.com/management-and-nutrition/nutrition-exotic-and-zoo-animals/overview-of-nutrition-exotic-and-zoo-animals"),
        "farm_pet_general_feeding": ("farm_pet", [], "Plan por especie y etapa para mascotas de granja", "Alimento completo correspondiente a la especie, etapa y función", "No intercambies alimentos entre especies o etapas; sigue la etiqueta y confirma con un veterinario o nutricionista animal el acceso a agua, forraje y minerales.", "Manual Veterinario Merck · animales de traspatio", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/backyard-poultry/management-of-backyard-poultry"),
        "other_species_identification": ("other", [], "Identificar la especie antes de definir su alimentación", "Plan pendiente de identificar la especie exacta", "Roxy no propondrá ingredientes, cantidades ni frecuencia hasta guardar la especie exacta y confirmar que su tenencia y cuidado sean apropiados.", "Manual Veterinario Merck · bienestar de mascotas no tradicionales", "https://www.merckvetmanual.com/special-subjects/animal-welfare/animal-welfare"),
        "bird_budgie_pellet_rotation": ("bird", ["periquito"], "Rotación de pellets y vegetales para periquito", "Pellet formulado para periquito y vegetales aprobados", "Registra qué pellets y vegetales acepta; no permitas que seleccione únicamente semillas y retira el alimento fresco antes de que se estropee.", "Manual Veterinario Merck · alimentación de aves", "https://www.merckvetmanual.com/bird-owners/choosing-and-taking-care-of-a-pet-bird/feeding-a-pet-bird"),
        "bird_cockatiel_fresh_rotation": ("bird", ["ninfa", "cockatiel"], "Rotación fresca para ninfa o cockatiel", "Pellet del tamaño adecuado y vegetales ricos en vitamina A", "Introduce un vegetal cada vez, registra aceptación y heces, y evita aguacate, alcohol, chocolate, cafeína y alimentos salados.", "Manual Veterinario Merck · alimentación de aves", "https://www.merckvetmanual.com/bird-owners/choosing-and-taking-care-of-a-pet-bird/feeding-a-pet-bird"),
        "fish_betta_frozen_rotation": ("fish", ["betta"], "Rotación de alimento congelado para betta", "Alimento congelado comercial compatible con betta", "Descongela únicamente la porción indicada, comprueba que el betta la ingiera y retira cualquier resto para proteger la calidad del agua.", "Manual Veterinario Merck · peces de acuario", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/aquarium-fish/nutritional-diseases-of-fish"),
        "fish_goldfish_fresh_rotation": ("fish", ["goldfish", "carassius"], "Rotación alimentaria para goldfish", "Alimento completo para goldfish en formato adecuado", "Alterna solo formatos compatibles con el tamaño y la flotabilidad del pez; observa abdomen, heces y parámetros del agua antes de repetir.", "Manual Veterinario Merck · peces de acuario", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/aquarium-fish/nutritional-diseases-of-fish"),
        "reptile_leopard_gecko_live_rotation": ("reptile", ["gecko leopardo"], "Rotación de insectos para gecko leopardo", "Insectos alimentadores del tamaño apropiado y correctamente nutridos", "Usa variedad de presas criadas como alimento, nunca insectos silvestres; registra la suplementación indicada, el apetito, el peso y cada muda.", "Manual Veterinario Merck · reptiles", "https://www.merckvetmanual.com/all-other-pets/reptiles/providing-a-home-for-a-reptile"),
        "reptile_bearded_dragon_greens": ("reptile", ["dragon barbudo"], "Rotación de hojas para dragón barbudo", "Hojas y vegetales aprobados para su etapa", "La proporción vegetal y animal cambia con la edad; registra cada ingrediente por separado y no añadas suplementos sin revisar dieta, calcio y UVB.", "Manual Veterinario Merck · reptiles", "https://www.merckvetmanual.com/all-other-pets/reptiles/providing-a-home-for-a-reptile"),
        "amphibian_axolotl_earthworm": ("amphibian", ["ajolote", "axolotl"], "Servicio de lombriz para ajolote", "Lombriz criada como alimento y del tamaño apropiado", "Ofrece con pinzas limpias sin lastimar al ajolote, confirma que trague con normalidad y retira restos mientras registras temperatura y parámetros del agua.", "ARAV · reptiles y anfibios", "https://arav.org/"),
        "amphibian_frog_insect_rotation": ("amphibian", ["rana", "sapo"], "Rotación de insectos para rana o sapo", "Insectos alimentadores apropiados para la especie y tamaño", "No uses insectos silvestres; relaciona apetito con temperatura y humedad, y confirma cualquier suplementación con el veterinario de exóticos.", "ARAV · reptiles y anfibios", "https://arav.org/"),
        "small_mammal_chinchilla_hay": ("small_mammal", ["chinchilla"], "Selección diaria de heno para chinchilla", "Heno de pasto limpio, seco y aromático", "Renueva el heno contaminado, registra consumo y heces, y no conviertas fruta seca, semillas o premios azucarados en parte habitual.", "Oxbow · guía de alimentos fortificados", "https://oxbowanimalhealth.com/wp-content/uploads/2023/07/Oxbow-All-About-Fortified-Foods-Apr-2022.pdf"),
        "small_mammal_rat_fresh_rotation": ("small_mammal", ["rata domestica"], "Rotación fresca para rata doméstica", "Alimento uniforme para rata y complemento fresco aprobado", "Presenta un complemento a la vez, en cantidad pequeña, y registra aceptación, peso y heces sin desplazar el alimento formulado.", "Oxbow · guía de alimentos fortificados", "https://oxbowanimalhealth.com/wp-content/uploads/2023/07/Oxbow-All-About-Fortified-Foods-Apr-2022.pdf"),
        "invertebrate_tarantula_feeder": ("invertebrate", ["tarantula"], "Rutina de presa para tarántula", "Presa criada como alimento y del tamaño apropiado", "Retira cualquier presa no consumida, especialmente antes de una muda; no fuerces la alimentación y registra humedad, abdomen y fecha de muda.", "Manual Veterinario Merck · animales exóticos", "https://www.merckvetmanual.com/management-and-nutrition/nutrition-exotic-and-zoo-animals/overview-of-nutrition-exotic-and-zoo-animals"),
        "invertebrate_hermit_crab_station": ("invertebrate", ["cangrejo ermitano"], "Estación variada para cangrejo ermitaño", "Alimento específico y fuentes minerales aprobadas para la especie", "Mantén recipientes separados de agua dulce y salada correctamente preparada, retira sobrantes y registra actividad, muda y humedad.", "Manual Veterinario Merck · animales exóticos", "https://www.merckvetmanual.com/management-and-nutrition/nutrition-exotic-and-zoo-animals/overview-of-nutrition-exotic-and-zoo-animals"),
        "farm_pet_mini_pig_enrichment": ("farm_pet", ["cerdo miniatura"], "Enriquecimiento alimentario para cerdo miniatura", "Parte medida de su alimento completo para cerdo miniatura", "Reserva parte de la ración indicada para una búsqueda supervisada; registra peso y condición corporal y no añadas calorías fuera del plan.", "Mazuri · nutrición para cerdo miniatura", "https://mazuri.com/collections/mini-pig"),
        "farm_pet_poultry_foraging": ("farm_pet", ["gallina", "pato", "ganso", "pavo", "codorniz"], "Forrajeo medido para ave de traspatio", "Parte de su alimento completo correspondiente a especie y etapa", "Distribuye una parte medida en un área limpia y segura; no sustituyas la fórmula de su especie ni ofrezcas alimento mohoso o contaminado.", "Manual Veterinario Merck · aves de traspatio", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/backyard-poultry/management-of-backyard-poultry"),
        "rabbit_hay_quality_check": ("rabbit", [], "Selección de heno diario para conejo", "Heno de pasto limpio, seco y aromático", "Mantén heno disponible, retira partes húmedas o contaminadas y relaciona cualquier descenso de consumo o de heces con atención veterinaria rápida.", "Manual Veterinario Merck · nutrición de conejos", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/rabbits/nutrition-of-rabbits"),
        "rabbit_pellet_label_plan": ("rabbit", [], "Plan de pellet por etapa para conejo", "Pellet uniforme correspondiente a su etapa", "Mide solo la cantidad indicada por etiqueta o veterinario, registra el peso y evita mezclas que permitan seleccionar semillas o piezas.", "Manual Veterinario Merck · nutrición de conejos", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/rabbits/nutrition-of-rabbits"),
        "guinea_vitamin_c_rotation": ("guinea_pig", [], "Rotación fresca de vitamina C para cobaya", "Vegetal fresco aprobado rico en vitamina C", "Introduce un vegetal a la vez, registra tolerancia y retira sobrantes; no añadas vitamina C al agua sin indicación porque la dosis y estabilidad son impredecibles.", "Manual Veterinario Merck · nutrición de cobayas", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/guinea-pigs/housing-and-nutrition-of-guinea-pigs"),
        "guinea_hay_pellet_plan": ("guinea_pig", [], "Plan de heno y pellet para cobaya", "Heno de pasto y pellet uniforme específico para cobaya", "Mantén heno disponible, mide el pellet por etiqueta y registra peso, apetito, heces y desgaste dental.", "Manual Veterinario Merck · nutrición de cobayas", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/guinea-pigs/housing-and-nutrition-of-guinea-pigs"),
        "hamster_uniform_food_foraging": ("hamster", [], "Forrajeo con alimento uniforme para hámster", "Parte medida de su alimento completo para hámster", "Esconde una parte de la ración en zonas limpias, revisa reservas húmedas y registra consumo sin añadir mezcla de semillas no contabilizada.", "Manual Veterinario Merck · hámsteres", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/rodents/hamsters"),
        "hamster_protein_rotation": ("hamster", [], "Rotación proteica segura para hámster", "Complemento proteico aprobado para su especie exacta", "Confirma el ingrediente y una porción diminuta, introdúcelo solo y retira lo que almacene antes de que se deteriore.", "Manual Veterinario Merck · hámsteres", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/rodents/hamsters"),
        "fish_betta_pellet_observation": ("fish", ["betta"], "Prueba de pellet por pellet para betta", "Pellet completo específico para betta y tamaño de boca", "Entrega la cantidad indicada de forma gradual, observa cada ingestión y detente si quedan restos o el abdomen cambia de forma.", "Manual Veterinario Merck · peces de acuario", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/aquarium-fish/nutritional-diseases-of-fish"),
        "reptile_leopard_gecko_calcium_log": ("reptile", ["gecko leopardo"], "Registro de calcio para gecko leopardo", "Suplemento de calcio elegido según dieta y exposición UVB", "No determines D3 o frecuencia por intuición; registra producto, fecha, presas, UVB y la indicación exacta del especialista.", "Manual Veterinario Merck · reptiles", "https://www.merckvetmanual.com/all-other-pets/reptiles/providing-a-home-for-a-reptile"),
        "amphibian_axolotl_pellet_rotation": ("amphibian", ["ajolote", "axolotl"], "Rotación de pellet hundible para ajolote", "Pellet hundible completo del tamaño apropiado", "Ofrece una porción controlada, confirma que llegue al fondo y sea ingerida, y retira todo sobrante mientras registras los parámetros del agua.", "ARAV · reptiles y anfibios", "https://arav.org/"),
        "small_mammal_chinchilla_pellet": ("small_mammal", ["chinchilla"], "Plan de pellet uniforme para chinchilla", "Pellet uniforme específico para chinchilla", "Mide la porción de etiqueta, mantén el heno como base y registra peso, apetito y heces antes de cualquier cambio.", "Oxbow · guía de alimentos fortificados", "https://oxbowanimalhealth.com/wp-content/uploads/2023/07/Oxbow-All-About-Fortified-Foods-Apr-2022.pdf"),
        "small_mammal_chinchilla_foraging": ("small_mammal", ["chinchilla"], "Forrajeo seco para chinchilla", "Parte de su heno y pellet habituales", "Distribuye solo alimento ya contabilizado en lugares secos y limpios; evita frutas secas y premios azucarados.", "Oxbow · guía de alimentos fortificados", "https://oxbowanimalhealth.com/wp-content/uploads/2023/07/Oxbow-All-About-Fortified-Foods-Apr-2022.pdf"),
        "invertebrate_tarantula_molt_pause": ("invertebrate", ["tarantula"], "Pausa alimentaria segura durante la muda de tarántula", "Agua limpia; presas suspendidas mientras existan señales de muda", "Retira presas vivas, no manipules ni fuerces la alimentación y registra postura, humedad y fecha hasta que se recupere por completo.", "Manual Veterinario Merck · animales exóticos", "https://www.merckvetmanual.com/management-and-nutrition/nutrition-exotic-and-zoo-animals/overview-of-nutrition-exotic-and-zoo-animals"),
        "invertebrate_tarantula_water_check": ("invertebrate", ["tarantula"], "Revisión de agua para tarántula", "Agua limpia en recipiente estable y poco profundo", "Limpia y rellena sin humedecer todo el recinto a ciegas; registra consumo visible, humedad y cualquier cambio del abdomen.", "Manual Veterinario Merck · animales exóticos", "https://www.merckvetmanual.com/management-and-nutrition/nutrition-exotic-and-zoo-animals/overview-of-nutrition-exotic-and-zoo-animals"),
        "farm_pet_mini_pig_label_plan": ("farm_pet", ["cerdo miniatura"], "Plan de alimento completo para cerdo miniatura", "Alimento completo de cerdo miniatura para su etapa", "Pesa la porción según etiqueta o veterinario, divídela en sus horarios guardados y registra peso y condición corporal semanalmente.", "Mazuri · nutrición para cerdo miniatura", "https://mazuri.com/collections/mini-pig"),
        "farm_pet_mini_pig_fresh_rotation": ("farm_pet", ["cerdo miniatura"], "Rotación fresca medida para cerdo miniatura", "Vegetal aprobado contabilizado dentro de su plan", "Introduce un vegetal simple, sin sal ni aderezos, registra tolerancia y evita convertir sobras humanas en parte de la dieta.", "Mazuri · nutrición para cerdo miniatura", "https://mazuri.com/collections/mini-pig"),
    }
    for key, (species, exact_terms, title, ingredient, observation, source_title, source_url) in feeding_guide_specs.items():
        guide = _recipe(
            title, "Guía de alimentación que se ajusta a la especie exacta, el producto y las condiciones del hábitat.", "other", 1,
            [(ingredient, 1, "porción según etiqueta")],
            [
                "Confirma la especie exacta, la etapa de vida y cualquier indicación veterinaria guardada.",
                "Lee la etiqueta del alimento y usa la cantidad indicada para el tamaño y la etapa de la mascota.",
                "Ofrece una porción controlada y observa que la mascota pueda ingerirla normalmente.",
                observation,
                "Registra cambios de apetito, peso, conducta o calidad del entorno y consulta a un especialista ante cualquier señal anormal.",
            ],
        )
        guide.update(audience="pet", pet_species=species, pet_exact_terms=exact_terms, pet_category="pet_feeding", safety_class="feeding_guide", veterinary_note="Guía orientativa; la etiqueta y el veterinario de exóticos determinan alimento, cantidad y frecuencia.", sources=[{"title": source_title, "url": source_url, "authority": source_title.split(" · ", 1)[0]}], editorial_status="verified_veterinary_guidance")
        recipes[key] = guide
    broader_guide_sources = {
        "dog": ("Manual Veterinario Merck · perros", "https://www.merckvetmanual.com/dog-owners"),
        "cat": ("Manual Veterinario Merck · gatos", "https://www.merckvetmanual.com/cat-owners"),
        "ferret": ("Manual Veterinario Merck · hurones", "https://www.merckvetmanual.com/all-other-pets/ferrets/providing-a-home-for-a-ferret"),
        "rabbit": ("Manual Veterinario Merck · conejos", "https://www.merckvetmanual.com/all-other-pets/rabbits/providing-a-home-for-a-rabbit"),
        "guinea_pig": ("Manual Veterinario Merck · cobayas", "https://www.merckvetmanual.com/all-other-pets/guinea-pigs/diet-for-a-guinea-pig"),
        "hamster": ("Manual Veterinario Merck · hámsteres", "https://www.merckvetmanual.com/all-other-pets/hamsters/providing-a-home-for-a-hamster"),
        "bird": ("Manual Veterinario Merck · aves", "https://www.merckvetmanual.com/bird-owners/choosing-and-taking-care-of-a-pet-bird/feeding-a-pet-bird"),
        "fish": ("Manual Veterinario Merck · peces", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/aquarium-fish/nutritional-diseases-of-fish"),
        "reptile": ("Manual Veterinario Merck · reptiles", "https://www.merckvetmanual.com/all-other-pets/reptiles/providing-a-home-for-a-reptile"),
        "amphibian": ("ARAV · anfibios", "https://arav.org/"),
        "small_mammal": ("Manual Veterinario Merck · pequeños mamíferos", "https://www.merckvetmanual.com/management-and-nutrition/nutrition-exotic-and-zoo-animals/nutrition-in-rodents-and-lagomorphs"),
        "invertebrate": ("Manual Veterinario Merck · animales exóticos", "https://www.merckvetmanual.com/management-and-nutrition/nutrition-exotic-and-zoo-animals/overview-of-nutrition-exotic-and-zoo-animals"),
        "farm_pet": ("Manual Veterinario Merck · animales de traspatio", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/backyard-poultry/management-of-backyard-poultry"),
    }
    species_labels = {
        "dog": "perros", "cat": "gatos", "ferret": "hurones", "rabbit": "conejos",
        "guinea_pig": "cobayas", "hamster": "hámsteres", "bird": "aves", "fish": "peces",
        "reptile": "reptiles", "amphibian": "anfibios", "small_mammal": "pequeños mamíferos",
        "invertebrate": "invertebrados", "farm_pet": "mascotas de granja",
    }
    guide_variants = (
        ("appetite_log", "Registro de apetito para {label}", "Alimento habitual específico para la especie", "Registra cuánto ofreciste, cuánto consumió y cualquier cambio de conducta o heces."),
        ("food_storage", "Conservación segura del alimento para {label}", "Alimento habitual y su envase original", "Anota fecha de apertura, lote y caducidad; desecha alimento húmedo, contaminado o con olor anormal."),
        ("hydration_check", "Revisión de hidratación para {label}", "Agua limpia o medio acuático correspondiente", "Comprueba disponibilidad, limpieza y consumo visible; en especies acuáticas registra también los parámetros del agua."),
        ("weekly_tolerance", "Control semanal de peso y tolerancia para {label}", "Registro de peso, apetito y alimento actual", "Compara la tendencia con registros anteriores sin cambiar dosis ni dieta por una sola medición."),
    )
    for species, label in species_labels.items():
        source_title, source_url = broader_guide_sources[species]
        for suffix, title_template, ingredient, observation in guide_variants:
            guide = _recipe(
                title_template.format(label=label),
                "Guía práctica para observar la respuesta individual de la mascota sin inventar porciones ni sustituir su plan profesional.",
                "other", 1, [(ingredient, 1, "revisión")],
                [
                    "Confirma la especie exacta, etapa, alimento actual y cualquier indicación veterinaria guardada.",
                    "Usa la etiqueta original y prepara únicamente la cantidad ya definida para esta mascota.",
                    "Observa apetito, conducta, postura y facilidad para comer o beber sin forzarla.",
                    observation,
                    "Guarda el registro y consulta a un profesional ante pérdida de apetito, peso, dolor o un cambio persistente.",
                ],
            )
            guide.update(
                audience="pet", pet_species=species, pet_category="pet_feeding", safety_class="feeding_guide",
                veterinary_note="Guía de seguimiento; no modifica alimento, dosis ni frecuencia sin la etiqueta o el profesional correspondiente.",
                sources=[{"title": source_title, "url": source_url, "authority": source_title.split(" · ", 1)[0]}],
                editorial_status="verified_veterinary_guidance",
            )
            recipes[f"{species}_{suffix}"] = guide
    default_pet_photos = {
        "dog": "/assets/roxy_home/recipes/pets/dog-treat-variety.webp",
        "cat": "/assets/roxy_home/recipes/pets/cat-protein-variety.webp",
        "ferret": "/assets/roxy_home/recipes/pets/ferret-protein-variety.webp",
        "rabbit": "/assets/roxy_home/recipes/pets/small-herbivore-feeding.webp",
        "guinea_pig": "/assets/roxy_home/recipes/pets/small-herbivore-feeding.webp",
        "hamster": "/assets/roxy_home/recipes/pets/small-omnivore-feeding.webp",
        "small_mammal": "/assets/roxy_home/recipes/pets/small-omnivore-feeding.webp",
        "bird": "/assets/roxy_home/recipes/pets/bird-feeding.webp",
        "fish": "/assets/roxy_home/recipes/pets/aquatic-feeding.webp",
        "reptile": "/assets/roxy_home/recipes/pets/reptile-amphibian-feeding.webp",
        "amphibian": "/assets/roxy_home/recipes/pets/reptile-amphibian-feeding.webp",
        "invertebrate": "/assets/roxy_home/recipes/pets/invertebrate-feeding.webp",
        "farm_pet": "/assets/roxy_home/recipes/pets/farm-pet-feeding.webp",
        "other": "/assets/roxy_home/recipes/pets/species-identification.webp",
    }
    # A recipe card must show the preparation it names. These curated collection
    # photographs are composed so each preparation can receive its own crop; the
    # older category-wide images remain only as honest fallbacks for care guides.
    exact_recipe_photos = {
        "dog_hard_boiled_egg": ("/assets/roxy_home/recipes/pets/dog-treat-collection.webp", "31% 23%"),
        "dog_dehydrated_turkey": ("/assets/roxy_home/recipes/pets/dog-treat-collection.webp", "18% 55%"),
        "dog_dehydrated_chicken": ("/assets/roxy_home/recipes/pets/dog-treat-collection.webp", "80% 28%"),
        "dog_turkey_pumpkin": ("/assets/roxy_home/recipes/pets/bernese-turkey-pumpkin.jpg", "50% 50%"),
        "dog_frozen_banana_pumpkin": ("/assets/roxy_home/recipes/pets/bernese-banana-pumpkin.jpg", "50% 50%"),
        "dog_chicken_training_bits": ("/assets/roxy_home/recipes/pets/bernese-chicken-training.jpg", "50% 50%"),
        "dog_beef_green_bean": ("/assets/roxy_home/recipes/pets/bernese-beef-green-bean.jpg", "50% 50%"),
        "dog_apple_carrot_oat": ("/assets/roxy_home/recipes/pets/bernese-apple-carrot.jpg", "50% 50%"),
        "dog_sweet_potato_chews": ("/assets/roxy_home/recipes/pets/bernese-sweet-potato.jpg", "50% 50%"),
        "cat_dehydrated_whitefish": ("/assets/roxy_home/recipes/pets/cat-protein-collection.webp", "31% 27%"),
        "cat_dehydrated_chicken": ("/assets/roxy_home/recipes/pets/cat-protein-collection.webp", "31% 58%"),
        "cat_rabbit_morsels": ("/assets/roxy_home/recipes/pets/cat-protein-collection.webp", "78% 44%"),
        "cat_turkey_flakes": ("/assets/roxy_home/recipes/pets/cat-protein-collection.webp", "66% 25%"),
        "cat_whitefish_flakes": ("/assets/roxy_home/recipes/pets/cat-protein-collection.webp", "31% 27%"),
        "cat_beef_crumbles": ("/assets/roxy_home/recipes/pets/cat-protein-collection.webp", "39% 78%"),
        "cat_plain_shrimp": ("/assets/roxy_home/recipes/pets/cat-protein-collection.webp", "72% 78%"),
        "ferret_poached_chicken": ("/assets/roxy_home/recipes/pets/ferret-protein-collection.webp", "55% 24%"),
        "ferret_cooked_lamb": ("/assets/roxy_home/recipes/pets/ferret-protein-collection.webp", "27% 54%"),
        "ferret_baked_duck": ("/assets/roxy_home/recipes/pets/ferret-protein-collection.webp", "76% 48%"),
        "ferret_turkey_medallions": ("/assets/roxy_home/recipes/pets/ferret-protein-collection.webp", "55% 76%"),
    }
    for key, recipe in recipes.items():
        if not recipe.get("pet_category"):
            title = _identity(recipe.get("title"))
            recipe["pet_category"] = "pet_morning" if "huevo" in title else "pet_fresh" if re.search(r"helado|yogur|salmon", title) else "pet_treats"
        recipe.setdefault("photo_asset", default_pet_photos[recipe["pet_species"]])
        if key in exact_recipe_photos:
            recipe["photo_asset"], recipe["photo_focus"] = exact_recipe_photos[key]
        recipe.setdefault("editorial_status", "verified_veterinary_guidance")
    return recipes


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
    templates.update(_pet_templates())
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
    vague_phrases = ("metodo indicado", "segun corresponda", "orden indicado", "punto correcto", "cocina u hornea")
    for row in templates.values():
        steps_text = _identity(" ".join(str(step) for step in row.get("steps") or []))
        if len(row.get("steps") or []) >= 5 and not any(phrase in steps_text for phrase in vague_phrases):
            continue
        ingredients, steps, description = editorialize_recipe(
            str(row.get("category") or ""),
            str(row.get("title") or "Receta"),
            str(row.get("kind") or "meal"),
            list(row.get("ingredients") or []),
        )
        row["ingredients"] = ingredients
        row["steps"] = steps
        row["description"] = description
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
    recipe["sources"] = [deepcopy(row) for row in recipe.get("sources") or [] if isinstance(row, dict)]
    recipe["generation_source"] = "local_recipe_catalog"
    return recipe


def find_local_recipe(prompt: str, snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Return a common curated recipe, or ``None`` when OpenAI is warranted."""
    key = _local_recipe_key(prompt)
    return _prepare_local_recipe(key, snapshot) if key else None


def local_recipe_by_key(key: str, snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Return the exact installed recipe selected by the trusted catalog UI."""
    catalog_key = str(key or "").strip()
    if not catalog_key or catalog_key not in _unique_catalog_templates():
        return None
    return _prepare_local_recipe(catalog_key, snapshot)


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


def personalized_pet_recipe_catalog(pet: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a pet-owned view of the curated catalog without pretending treats are complete diets."""
    species = str(pet.get("species") or "other")
    pet_name = str(pet.get("name") or "esta mascota").strip()
    identity = str(pet.get("breed") or pet.get("exact_species") or species).strip()
    identity_key = _identity(identity)
    stage = str(pet.get("life_stage") or "unknown")
    stage_label = {"baby": "bebé", "young": "joven", "adult": "adulta", "senior": "senior"}.get(stage, "etapa pendiente")
    allergy_aliases = {
        "pollo": {"pollo", "chicken"}, "pavo": {"pavo", "turkey"}, "res": {"res", "beef"},
        "pescado": {"pescado", "salmon", "bacalao", "camaron", "fish", "shrimp"},
        "huevo": {"huevo", "egg"}, "lacteos": {"yogur", "leche", "queso", "lacteo", "dairy"},
        "trigo": {"trigo", "harina", "wheat"}, "avena": {"avena", "oat"},
    }
    blocked: set[str] = set()
    for allergy in pet.get("allergies") or []:
        normalized = _identity(allergy)
        if normalized.startswith("ninguna"):
            continue
        blocked.update(allergy_aliases.get(normalized, {normalized}))
    rows: list[dict[str, Any]] = []
    for source in local_recipe_catalog(snapshot):
        if source.get("audience") != "pet" or source.get("pet_species") != species:
            continue
        exact_terms = [_identity(value) for value in source.get("pet_exact_terms") or [] if _identity(value)]
        if exact_terms and not any(term in identity_key for term in exact_terms):
            continue
        life_stages = [str(value) for value in source.get("pet_life_stages") or []]
        if life_stages and stage != "unknown" and stage not in life_stages:
            continue
        ingredient_text = _identity(" ".join(str(item.get("name") or "") for item in source.get("ingredients") or [] if isinstance(item, dict)))
        matched_allergies = sorted(value for value in blocked if value and value in ingredient_text)
        if matched_allergies:
            continue
        row = deepcopy(source)
        dimensions = [identity]
        if stage != "unknown":
            dimensions.append(f"etapa {stage_label}")
        if blocked:
            dimensions.append(f"sin {len(blocked)} ingrediente(s) bloqueado(s)")
        if exact_terms:
            scope = row.get("personalization_scope") or "exact_identity"
            reason = f"Coincide con {identity} y con la etapa {stage_label} guardada para {pet_name}."
        elif row.get("safety_class") == "feeding_guide":
            scope = "species_feeding_protocol"
            reason = f"Es una guía para {pet_name}, compatible con {identity}; la cantidad y frecuencia se mantienen ligadas a su etiqueta, entorno y especialista."
        else:
            scope = "species_safe_treat"
            reason = f"Es un premio compatible con la especie de {pet_name}, filtrado por su etapa y restricciones guardadas."
        row.update(
            pet_id=str(pet.get("id") or ""), pet_name=pet_name, profile_label=f"Para {pet_name} · {' · '.join(dimensions)}",
            personalization_scope=scope, personalization_reason=reason,
            excluded_allergies=sorted(blocked),
        )
        if species == "fish" and "betta" in identity_key:
            row.update(photo_asset="/assets/roxy_home/recipes/pets/betta-feeding.webp", photo_focus="50% 48%")
        elif species == "reptile" and "gecko leopardo" in identity_key:
            row.update(photo_asset="/assets/roxy_home/recipes/pets/leopard-gecko-feeding.webp", photo_focus="48% 52%")
        rows.append(row)
    return sorted(
        rows,
        key=lambda row: (
            0 if row.get("pet_exact_terms") else 1,
            0 if row.get("pet_variety") in {"Deshidratado", "Hervido"} else 1,
            str(row.get("title") or "").casefold(),
        ),
    )


def exact_local_recipe(title: str) -> dict[str, Any] | None:
    """Return one installed recipe only when its normalized title is exact."""
    wanted = _identity(title)
    for key, recipe in _unique_catalog_templates().items():
        if _identity(recipe.get("title")) == wanted:
            return {"catalog_key": key, **deepcopy(recipe)}
    return None


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
