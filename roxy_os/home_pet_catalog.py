from __future__ import annotations

from copy import deepcopy
from typing import Any


DOG_BREEDS = [
    "Affenpinscher", "Afghan Hound", "Airedale Terrier", "Akita", "Alaskan Malamute", "American Bulldog",
    "American Eskimo Dog", "American Staffordshire Terrier", "Australian Cattle Dog", "Australian Shepherd",
    "Basenji", "Basset Hound", "Beagle", "Belgian Malinois", "Bernese Mountain Dog", "Bichon Frise",
    "Bloodhound", "Border Collie", "Boston Terrier", "Boxer", "Brittany", "Bull Terrier", "Bulldog",
    "Bullmastiff", "Cane Corso", "Cavalier King Charles Spaniel", "Chihuahua", "Chinese Crested", "Chow Chow",
    "Cocker Spaniel", "Collie", "Corgi galés de Cardigan", "Corgi galés de Pembroke", "Dachshund", "Dalmatian",
    "Doberman Pinscher", "Dogo Argentino", "English Cocker Spaniel", "English Springer Spaniel", "French Bulldog",
    "German Shepherd Dog", "German Shorthaired Pointer", "Giant Schnauzer", "Golden Retriever", "Great Dane",
    "Great Pyrenees", "Greyhound", "Havanese", "Irish Setter", "Italian Greyhound", "Jack Russell Terrier",
    "Labrador Retriever", "Lhasa Apso", "Maltese", "Mastiff", "Miniature American Shepherd",
    "Miniature Pinscher", "Miniature Schnauzer", "Newfoundland", "Old English Sheepdog", "Papillon", "Pekingese",
    "Pomeranian", "Poodle Miniature", "Poodle Standard", "Poodle Toy", "Portuguese Water Dog", "Pug",
    "Rhodesian Ridgeback", "Rottweiler", "Saint Bernard", "Samoyed", "Schnauzer Standard", "Shetland Sheepdog",
    "Shiba Inu", "Shih Tzu", "Siberian Husky", "Staffordshire Bull Terrier", "Vizsla", "Weimaraner",
    "West Highland White Terrier", "Whippet", "Yorkshire Terrier", "Mestizo / raza mixta", "No sé la raza",
]

CAT_BREEDS = [
    "Abyssinian", "American Bobtail", "American Curl", "American Shorthair", "Balinese", "Bengal", "Birman",
    "Bombay", "British Shorthair", "Burmese", "Chartreux", "Cornish Rex", "Devon Rex", "Egyptian Mau",
    "European Burmese", "Exotic Shorthair", "Havana Brown", "Japanese Bobtail", "Korat", "LaPerm", "Maine Coon",
    "Manx", "Norwegian Forest Cat", "Ocicat", "Oriental", "Persian", "Ragamuffin", "Ragdoll", "Russian Blue",
    "Savannah", "Scottish Fold", "Selkirk Rex", "Siamese", "Siberian", "Singapura", "Somali", "Sphynx",
    "Tonkinese", "Turkish Angora", "Doméstico de pelo corto", "Doméstico de pelo largo",
    "Mestizo / raza mixta", "No sé la raza",
]

EXACT_SPECIES = {
    "bird": ["Periquito australiano", "Canario", "Cacatúa", "Ninfa / cockatiel", "Agapornis", "Loro gris africano", "Guacamayo", "Conure", "Pinzón", "Paloma", "Otra ave"],
    "fish": ["Betta splendens", "Goldfish / Carassius auratus", "Guppy", "Molly", "Platy", "Tetra neón", "Disco", "Pez ángel", "Cíclido africano", "Corydora", "Pleco", "Gourami", "Danio cebra", "Koi", "Pez marino", "Otro pez"],
    "reptile": ["Gecko leopardo", "Gecko crestado", "Dragón barbudo", "Iguana verde", "Camaleón velado", "Serpiente del maíz", "Pitón bola", "Boa constrictor", "Tortuga terrestre", "Tortuga acuática", "Uromastyx", "Escinco de lengua azul", "Otro reptil"],
    "amphibian": ["Ajolote", "Rana arborícola", "Rana dardo", "Rana Pacman", "Sapo", "Tritón", "Salamandra", "Otro anfibio"],
    "rabbit": ["Holland Lop", "Mini Lop", "Netherland Dwarf", "Lionhead", "Rex", "Mini Rex", "Dutch", "Flemish Giant", "English Angora", "Mestizo / no sé"],
    "guinea_pig": ["American", "Abyssinian", "Peruvian", "Silkie", "Teddy", "Texel", "Skinny", "Mestiza / no sé"],
    "hamster": ["Sirio", "Enano ruso Campbell", "Enano Winter White", "Roborovski", "Chino", "No sé"],
    "ferret": ["Hurón doméstico", "No sé"],
    "small_mammal": ["Rata doméstica", "Ratón doméstico", "Gerbo de Mongolia", "Chinchilla", "Degú", "Erizo pigmeo africano", "Petauro del azúcar", "Perrito de la pradera", "Otro pequeño mamífero"],
    "invertebrate": ["Tarántula", "Escorpión", "Milpiés", "Mantis religiosa", "Insecto palo", "Cucaracha de Madagascar", "Cangrejo ermitaño", "Camarón de acuario", "Caracol terrestre", "Caracol acuático", "Isópodos", "Otro invertebrado"],
    "farm_pet": ["Cerdo miniatura", "Cabra", "Oveja", "Gallina", "Pato", "Ganso", "Pavo", "Codorniz", "Alpaca", "Otro animal de granja"],
    "other": ["Otra especie doméstica", "Especie exótica con permiso", "No sé la especie exacta"],
}

COMMON_ALLERGIES = {
    "dog": ["Pollo", "Res", "Lácteos", "Huevo", "Trigo", "Maíz", "Soya", "Pescado", "Ninguna conocida", "Otra"],
    "cat": ["Pollo", "Res", "Pescado", "Lácteos", "Huevo", "Trigo", "Ninguna conocida", "Otra"],
    "default": ["Ninguna conocida", "Ingrediente específico", "Sensibilidad ambiental", "Otra"],
}

COMMON_CONDITIONS = {
    "dog": ["Ninguna diagnosticada", "Piel sensible", "Estómago sensible", "Sobrepeso", "Articulaciones", "Enfermedad renal", "Diabetes", "Alergia alimentaria", "Otra"],
    "cat": ["Ninguna diagnosticada", "Bolas de pelo", "Tracto urinario", "Sobrepeso", "Enfermedad renal", "Diabetes", "Alergia alimentaria", "Otra"],
    "fish": ["Ninguna observada", "Problema de aletas", "Puntos blancos", "Estrés", "Problema de flotación", "Tratamiento activo", "Otra"],
    "reptile": ["Ninguna diagnosticada", "Problemas de muda", "Bajo peso", "Enfermedad metabólica ósea", "Parásitos", "Tratamiento activo", "Otra"],
    "bird": ["Ninguna diagnosticada", "Picaje de plumas", "Sobrepeso", "Problema respiratorio", "Problema del pico", "Tratamiento activo", "Otra"],
    "small_mammal": ["Ninguna diagnosticada", "Problema dental", "Problema respiratorio", "Piel o pelaje", "Sobrepeso", "Problema digestivo", "Tratamiento activo", "Otra"],
    "amphibian": ["Ninguna observada", "Problema de piel", "Pérdida de apetito", "Problema de flotación", "Calidad del agua", "Tratamiento activo", "Otra"],
    "invertebrate": ["Ninguna observada", "Problema de muda", "Pérdida de apetito", "Lesión", "Parámetros del hábitat", "Tratamiento activo", "Otra"],
    "farm_pet": ["Ninguna diagnosticada", "Sobrepeso", "Problema digestivo", "Pezuñas o patas", "Piel o plumaje", "Parásitos", "Tratamiento activo", "Otra"],
    "default": ["Ninguna diagnosticada", "Sobrepeso", "Bajo peso", "Problema digestivo", "Problema dental", "Tratamiento activo", "Otra"],
}

GOALS = {
    "dog": ["Mantener peso", "Bajar peso", "Subir peso", "Piel y pelaje", "Digestión", "Articulaciones", "Energía", "Premios de entrenamiento"],
    "cat": ["Mantener peso", "Bajar peso", "Subir peso", "Hidratación", "Bolas de pelo", "Digestión", "Tracto urinario", "Enriquecimiento"],
    "fish": ["Agua estable", "Coloración", "Crecimiento", "Compatibilidad", "Reducir estrés", "Rutina de alimentación"],
    "reptile": ["Temperatura correcta", "Humedad correcta", "UVB", "Muda", "Peso", "Enriquecimiento"],
    "bird": ["Alimentación equilibrada", "Enriquecimiento", "Socialización", "Plumaje", "Peso", "Rutina diaria"],
    "small_mammal": ["Salud dental", "Peso", "Enriquecimiento", "Hábitat", "Socialización", "Rutina diaria"],
    "amphibian": ["Calidad del agua", "Temperatura", "Humedad", "Alimentación", "Muda", "Reducir estrés"],
    "invertebrate": ["Muda segura", "Humedad", "Temperatura", "Alimentación", "Hábitat", "Reducir estrés"],
    "farm_pet": ["Peso", "Alimentación", "Pezuñas o patas", "Enriquecimiento", "Refugio", "Convivencia"],
    "default": ["Mantener peso", "Mejorar alimentación", "Rutina diaria", "Hábitat", "Enriquecimiento", "Seguimiento de salud"],
}


PRODUCTS = {
    "dog": [
        {"brand": "Purina Pro Plan", "name": "Complete Essentials Adult Chicken & Rice", "category": "Alimento completo", "life_stages": ["adult"], "reason": "Fórmula completa para mantenimiento adulto; confirma en la etiqueta la declaración de adecuación nutricional.", "source_url": "https://www.purina.com/pro-plan/dogs/adult-dog-food", "source_label": "Purina · línea oficial"},
        {"brand": "Purina Pro Plan", "name": "Sensitive Skin & Stomach Salmon & Rice", "category": "Alimento completo", "conditions": ["piel sensible", "estómago sensible"], "reason": "Opción comercial formulada para sistemas sensibles y disponible por etapa y tamaño.", "source_url": "https://www.purina.com/pro-plan/dogs/sensitive-stomach-skin-dog-food", "source_label": "Purina · producto oficial"},
        {"brand": "Royal Canin", "name": "Breed Health Nutrition", "category": "Alimento específico por raza", "requires_breed": True, "reason": "Línea que permite buscar una fórmula por raza y tamaño; la coincidencia exacta depende del catálogo vigente del fabricante.", "source_url": "https://www.royalcanin.com/us/dogs/products/breed-health-nutrition", "source_label": "Royal Canin · catálogo oficial"},
        {"brand": "Hill's Science Diet", "name": "Adult Perfect Weight", "category": "Control de peso", "goals": ["bajar peso"], "reason": "Alternativa para conversar con el veterinario cuando el objetivo es controlar peso.", "source_url": "https://www.hillspet.com/dog-food", "source_label": "Hill's · catálogo oficial"},
        {"brand": "KONG", "name": "Classic", "category": "Enriquecimiento", "goals": ["premios de entrenamiento", "energía"], "reason": "Juguete rellenable para enriquecimiento y entrega controlada de parte de su ración.", "source_url": "https://www.kongcompany.com/catalogue/K1/", "source_label": "KONG · producto oficial"},
    ],
    "cat": [
        {"brand": "Purina Pro Plan", "name": "Complete Essentials Adult", "category": "Alimento completo", "life_stages": ["adult"], "reason": "Opción de mantenimiento adulto; confirma la declaración de adecuación nutricional y la etapa en la etiqueta.", "source_url": "https://www.purina.com/pro-plan/cats", "source_label": "Purina · línea oficial"},
        {"brand": "Royal Canin", "name": "Feline Care Nutrition", "category": "Alimento especializado", "reason": "Línea comercial con opciones por necesidad; no sustituye una dieta veterinaria prescrita.", "source_url": "https://www.royalcanin.com/us/cats/products", "source_label": "Royal Canin · catálogo oficial"},
        {"brand": "Hill's Science Diet", "name": "Adult Indoor", "category": "Alimento completo", "reason": "Alternativa para gatos adultos de interior; verifica etapa y adecuación nutricional en el empaque.", "source_url": "https://www.hillspet.com/cat-food", "source_label": "Hill's · catálogo oficial"},
        {"brand": "Catit", "name": "Flower Fountain", "category": "Hidratación", "goals": ["hidratación", "tracto urinario"], "reason": "Fuente de agua como apoyo de hidratación y enriquecimiento; requiere limpieza y cambio de filtros.", "source_url": "https://catit.us/products/catit-flower-fountain", "source_label": "Catit · producto oficial"},
    ],
    "rabbit": [
        {"brand": "Oxbow", "name": "Essentials Adult Rabbit Food", "category": "Pellet uniforme", "life_stages": ["adult", "senior"], "reason": "Pellet uniforme a base de heno Timothy; el heno de pasto ilimitado sigue siendo la base.", "source_url": "https://oxbowanimalhealth.com/product/essentials-adult-rabbit-food/", "source_label": "Oxbow · producto oficial"},
        {"brand": "Oxbow", "name": "Western Timothy Hay", "category": "Heno", "reason": "Heno de pasto para la base diaria de un conejo sano, salvo indicación veterinaria distinta.", "source_url": "https://oxbowanimalhealth.com/our-products/hay/", "source_label": "Oxbow · catálogo oficial"},
        {"brand": "Oxbow", "name": "Enriched Life", "category": "Enriquecimiento", "goals": ["enriquecimiento"], "reason": "Accesorios de exploración y masticación supervisada.", "source_url": "https://oxbowanimalhealth.com/our-products/enrichment/", "source_label": "Oxbow · catálogo oficial"},
    ],
    "guinea_pig": [
        {"brand": "Oxbow", "name": "Essentials Adult Guinea Pig Food", "category": "Pellet uniforme", "reason": "Pellet específico para cobayas; debe acompañarse de heno, agua y el plan de vitamina C indicado.", "source_url": "https://oxbowanimalhealth.com/our-products/fortified-food/", "source_label": "Oxbow · catálogo oficial"},
        {"brand": "Oxbow", "name": "Western Timothy Hay", "category": "Heno", "reason": "Heno de pasto para acceso diario y salud digestiva y dental.", "source_url": "https://oxbowanimalhealth.com/our-products/hay/", "source_label": "Oxbow · catálogo oficial"},
    ],
    "hamster": [
        {"brand": "Oxbow", "name": "Essentials Hamster & Gerbil Food", "category": "Alimento uniforme", "reason": "Alimento comercial uniforme para reducir selección de ingredientes; confirma especie y etapa en la etiqueta.", "source_url": "https://oxbowanimalhealth.com/our-products/fortified-food/", "source_label": "Oxbow · catálogo oficial"},
        {"brand": "Niteangel", "name": "Multi-Chamber Hamster House", "category": "Hábitat", "goals": ["hábitat", "enriquecimiento"], "reason": "Refugio de múltiples cámaras para conducta de anidación; confirma medidas y material.", "source_url": "https://www.niteangelpet.com/collections/hamster-hideouts", "source_label": "Niteangel · catálogo oficial"},
    ],
    "bird": [
        {"brand": "Mazuri", "name": "Mini Bird Diet", "category": "Alimento formulado", "exact_terms": ["periquito", "canario", "ninfa", "cockatiel", "agapornis", "pinzón"], "reason": "Dieta formulada para aves pequeñas no reproductoras; la transición debe ser gradual.", "source_url": "https://mazuri.com/products/mazuri-mini-bird-diets", "source_label": "Mazuri · producto oficial"},
        {"brand": "Harrison's", "name": "Adult Lifetime Fine", "category": "Alimento formulado", "exact_terms": ["periquito", "canario", "ninfa", "cockatiel", "agapornis", "conure", "pinzón"], "reason": "Alternativa para determinadas aves adultas; confirma especie y tamaño de partícula con un veterinario aviar.", "source_url": "https://www.harrisonsbirdfoods.com/product/adult-lifetime-fine/", "source_label": "Harrison's · producto oficial"},
    ],
    "fish": [
        {"brand": "Hikari", "name": "Betta Bio-Gold", "category": "Alimento específico", "exact_terms": ["betta"], "reason": "Pellet flotante formulado para bettas; la cantidad depende del tamaño y se evita sobrealimentar.", "source_url": "https://www.hikariusa.com/tropical_folder/betta_bio_gold.html", "source_label": "Hikari · producto oficial"},
        {"brand": "Hikari", "name": "Micro Pellets", "category": "Alimento para peces pequeños", "exact_terms": ["guppy", "molly", "platy", "tetra", "danio"], "reason": "Opción para peces tropicales pequeños; confirma especie, tamaño de boca y zona de alimentación.", "source_url": "https://www.hikariusa.com/tropical.html", "source_label": "Hikari · catálogo oficial"},
        {"brand": "API", "name": "Freshwater Master Test Kit", "category": "Control del agua", "goals": ["agua estable", "reducir estrés"], "reason": "Kit para medir parámetros básicos; interpreta los resultados según la especie y el ciclado.", "source_url": "https://apifishcare.com/product/freshwater-master-test-kit", "source_label": "API · producto oficial"},
        {"brand": "Seachem", "name": "Prime", "category": "Acondicionador de agua", "reason": "Acondicionador concentrado; usa solo la dosis de la etiqueta para el volumen real.", "source_url": "https://www.seachem.com/prime.php", "source_label": "Seachem · producto oficial"},
    ],
    "reptile": [
        {"brand": "Zoo Med", "name": "Leopard Gecko Food", "category": "Alimento específico", "exact_terms": ["gecko leopardo"], "reason": "Producto formulado para gecko leopardo; confirma cómo encaja con insectos vivos y suplementación.", "source_url": "https://zoomed.com/leopard-gecko-food/", "source_label": "Zoo Med · producto oficial"},
        {"brand": "Zoo Med", "name": "Repti Calcium", "category": "Suplemento", "requires_vet": True, "reason": "La versión con o sin D3 depende de especie, dieta y exposición UVB.", "source_url": "https://zoomed.com/repti-calcium-without-d3/", "source_label": "Zoo Med · producto oficial"},
        {"brand": "Zoo Med", "name": "Digital Thermometer Humidity Gauge", "category": "Monitoreo de hábitat", "goals": ["temperatura correcta", "humedad correcta"], "reason": "Permite vigilar temperatura y humedad; los rangos dependen de la especie exacta.", "source_url": "https://zoomed.com/digital-combo-thermometer-humidity-gauge/", "source_label": "Zoo Med · producto oficial"},
    ],
    "ferret": [
        {"brand": "Mazuri", "name": "Ferret Diet", "category": "Alimento formulado", "reason": "Alimento formulado para hurones; confirma etapa, condición corporal e historial digestivo.", "source_url": "https://mazuri.com/products/mazuri-ferret-diet", "source_label": "Mazuri · producto oficial"},
    ],
    "small_mammal": [
        {"brand": "Oxbow", "name": "Essentials Adult Rat Food", "category": "Alimento uniforme", "exact_terms": ["rata"], "reason": "Alimento uniforme específico para ratas adultas; evita depender de mezclas que permitan selección.", "source_url": "https://oxbowanimalhealth.com/our-products/fortified-food/", "source_label": "Oxbow · catálogo oficial"},
        {"brand": "Oxbow", "name": "Essentials Chinchilla Food", "category": "Alimento específico", "exact_terms": ["chinchilla"], "reason": "Pellet formulado para chinchillas; el heno de pasto y el agua siguen siendo esenciales.", "source_url": "https://oxbowanimalhealth.com/our-products/fortified-food/", "source_label": "Oxbow · catálogo oficial"},
        {"brand": "Oxbow", "name": "Western Timothy Hay", "category": "Heno", "exact_terms": ["chinchilla", "degú"], "reason": "Heno de pasto para especies herbívoras; confirma el plan según la especie exacta.", "source_url": "https://oxbowanimalhealth.com/our-products/hay/", "source_label": "Oxbow · catálogo oficial"},
        {"brand": "Mazuri", "name": "Hedgehog Diet", "category": "Alimento específico", "exact_terms": ["erizo"], "reason": "Dieta formulada para erizos; revisa etapa, peso y transición gradual.", "source_url": "https://mazuri.com/collections/exotic-pets", "source_label": "Mazuri · catálogo oficial"},
    ],
    "amphibian": [
        {"brand": "Hikari", "name": "Sinking Carnivore Pellets", "category": "Alimento acuático", "exact_terms": ["ajolote"], "reason": "Pellet hundible para carnívoros acuáticos; confirma tamaño de bocado y cantidad para el ajolote.", "source_url": "https://www.hikariusa.com/tropical.html", "source_label": "Hikari · catálogo oficial"},
        {"brand": "API", "name": "Freshwater Master Test Kit", "category": "Control del agua", "exact_terms": ["ajolote", "tritón"], "reason": "Ayuda a vigilar amoníaco, nitrito, nitrato y pH en hábitats acuáticos ciclado.", "source_url": "https://apifishcare.com/product/freshwater-master-test-kit", "source_label": "API · producto oficial"},
        {"brand": "Zoo Med", "name": "Digital Thermometer Humidity Gauge", "category": "Monitoreo de hábitat", "reason": "Permite vigilar temperatura y humedad; el rango correcto depende de la especie exacta.", "source_url": "https://zoomed.com/digital-combo-thermometer-humidity-gauge/", "source_label": "Zoo Med · producto oficial"},
    ],
    "invertebrate": [
        {"brand": "Zoo Med", "name": "Eco Earth", "category": "Sustrato", "reason": "Sustrato de fibra de coco; profundidad y humedad deben adaptarse a la especie y a la muda.", "source_url": "https://zoomed.com/eco-earth-loose-coconut-fiber-substrate/", "source_label": "Zoo Med · producto oficial"},
        {"brand": "Zoo Med", "name": "Digital Thermometer Humidity Gauge", "category": "Monitoreo de hábitat", "reason": "Monitoreo básico del microclima; confirma los rangos para la especie exacta.", "source_url": "https://zoomed.com/digital-combo-thermometer-humidity-gauge/", "source_label": "Zoo Med · producto oficial"},
    ],
    "farm_pet": [
        {"brand": "Mazuri", "name": "Mini Pig Active Adult", "category": "Alimento específico", "exact_terms": ["cerdo"], "reason": "Alimento formulado para cerdos miniatura adultos; ajusta ración a condición corporal y actividad.", "source_url": "https://mazuri.com/collections/mini-pig", "source_label": "Mazuri · catálogo oficial"},
        {"brand": "Purina Animal Nutrition", "name": "Poultry Feeds", "category": "Alimento por etapa", "exact_terms": ["gallina", "pato", "ganso", "pavo", "codorniz"], "reason": "Líneas por especie y etapa; confirma que la fórmula corresponda al ave y su fase de vida.", "source_url": "https://www.purinamills.com/chicken-feed", "source_label": "Purina · catálogo oficial"},
    ],
}


def pet_profile_options() -> dict[str, Any]:
    return {
        "breeds": {"dog": DOG_BREEDS, "cat": CAT_BREEDS},
        "exact_species": deepcopy(EXACT_SPECIES),
        "allergies": deepcopy(COMMON_ALLERGIES),
        "conditions": deepcopy(COMMON_CONDITIONS),
        "goals": deepcopy(GOALS),
        "sources": [
            {"label": "AKC · razas de perros", "url": "https://www.akc.org/dog-breeds/"},
            {"label": "CFA · razas de gatos", "url": "https://cfa.org/breeds/"},
            {"label": "FDA · alimento completo y equilibrado", "url": "https://www.fda.gov/animal-veterinary/animal-health-literacy/complete-and-balanced-pet-food"},
            {"label": "WSAVA · cómo seleccionar alimento", "url": "https://wsava.org/wp-content/uploads/2021/04/Selecting-a-pet-food-for-your-pet-updated-2021_WSAVA-Global-Nutrition-Toolkit.pdf"},
        ],
    }


def personalized_pet_products(pet: dict[str, Any]) -> list[dict[str, Any]]:
    species = str(pet.get("species") or "other")
    exact = f"{pet.get('exact_species', '')} {pet.get('breed', '')}".lower()
    stage = str(pet.get("life_stage") or "unknown")
    conditions = {str(value).lower() for value in pet.get("conditions") or []}
    goals = {str(value).lower() for value in pet.get("goals") or []}
    vet_context = bool(
        conditions - {"ninguna diagnosticada", "ninguna observada"}
        or str(pet.get("veterinarian_instructions") or "").strip()
    )
    rows: list[dict[str, Any]] = []
    for source in PRODUCTS.get(species, []):
        row = deepcopy(source)
        exact_terms = [str(value).lower() for value in row.pop("exact_terms", [])]
        if exact_terms and not any(term in exact for term in exact_terms):
            continue
        row_goals = {str(value).lower() for value in row.pop("goals", [])}
        row_conditions = {str(value).lower() for value in row.pop("conditions", [])}
        life_stages = set(row.pop("life_stages", []))
        if row_goals and not row_goals.intersection(goals):
            continue
        if row_conditions and not row_conditions.intersection(conditions):
            continue
        score = 50
        if row_goals & goals:
            score += 25
        if row_conditions & conditions:
            score += 30
        if life_stages and stage in life_stages:
            score += 15
        if row.get("requires_breed") and str(pet.get("breed") or "").strip():
            score += 15
            row["name"] = f"{row['name']} · buscar {pet['breed']}"
        requires_vet = bool(row.get("requires_vet"))
        if vet_context and row.get("category") in {
            "Alimento completo", "Control de peso", "Alimento especializado", "Alimento específico por raza"
        }:
            requires_vet = True
        row.update(
            id=f"{species}:{len(rows)+1}:{row['brand'].lower().replace(' ', '-')}",
            score=min(score, 100),
            requires_vet=requires_vet,
            shopping_name=f"{row['brand']} {row['name']}",
            disclosure="Revisa etiqueta, tamaño, disponibilidad y precio. Roxy no sustituye una prescripción veterinaria.",
        )
        rows.append(row)
    return sorted(rows, key=lambda item: (-int(item["score"]), item["brand"], item["name"]))


CARE_LIBRARY = {
    "dog": {
        "feeding": "Alimento completo para su etapa, tamaño y condición corporal; los premios deben ser una parte pequeña del día.",
        "habitat": "Agua fresca, descanso cómodo, ejercicio y un espacio seguro adaptado a su movilidad.",
        "routine": "Comidas medidas, paseos, juego, higiene dental y control periódico de peso.",
        "social": "Presentaciones graduales y supervisadas con personas y otros animales.",
        "watch": "Cambios de apetito, sed, peso, vómitos, diarrea, dolor o dificultad para respirar requieren atención.",
    },
    "cat": {
        "feeding": "Alimento completo felino por etapa, agua accesible y control de porciones; evita cambios bruscos.",
        "habitat": "Areneros limpios, escondites, zonas altas, rascadores y recursos separados en hogares con varios gatos.",
        "routine": "Juego de caza, cepillado según pelaje, cuidado dental y seguimiento de peso e hidratación.",
        "social": "La convivencia se introduce con separación inicial, intercambio de olores y acceso gradual.",
        "watch": "No comer, esfuerzo al orinar, respiración anormal o letargo marcado son señales de atención urgente.",
    },
    "ferret": {
        "feeding": "Dieta comercial específica para hurones, alta en proteína animal y baja en carbohidratos; agua y alimento disponibles.",
        "habitat": "Zona segura, fresca y bien ventilada, con refugio, bandeja higiénica y protección contra escapes.",
        "routine": "Necesita varias horas diarias de juego supervisado fuera del recinto y enriquecimiento rotativo.",
        "social": "Puede convivir con hurones compatibles tras presentación; no se deja sin supervisión con presas pequeñas.",
        "watch": "Debilidad repentina, salivación, convulsiones, falta de apetito o sobrecalentamiento requieren veterinario de exóticos.",
    },
    "rabbit": {
        "feeding": "Heno de pasto como base, agua, verduras apropiadas y pellet medido según etapa y condición.",
        "habitat": "Espacio amplio con suelo firme, escondite, bandeja, objetos seguros para roer y ejercicio diario.",
        "routine": "Revisa a diario apetito, heces y dientes; cepilla según pelaje y controla uñas y peso.",
        "social": "La convivencia entre conejos requiere emparejamiento gradual y supervisado; protege de perros y gatos.",
        "watch": "Dejar de comer o producir heces, abdomen distendido o dificultad respiratoria es una urgencia.",
    },
    "guinea_pig": {
        "feeding": "Heno de pasto ilimitado, pellet específico con vitamina C, verduras apropiadas y agua fresca.",
        "habitat": "Recinto ventilado de suelo sólido, refugios, cama seca y espacio para moverse.",
        "routine": "Retira alimento fresco sobrante, limpia agua diariamente y vigila peso, dientes, uñas y vitamina C.",
        "social": "Son sociales; la pareja o grupo debe ser compatible, con espacio y recursos suficientes.",
        "watch": "No comer, heces reducidas, respiración ruidosa o pérdida de peso requiere atención rápida.",
    },
    "hamster": {
        "feeding": "Alimento uniforme apropiado para hámster, agua y extras seguros en cantidades pequeñas.",
        "habitat": "Recinto seguro con suelo sólido, cama profunda, material de nido, escondites y rueda del tamaño correcto.",
        "routine": "Respeta su ciclo nocturno, limpia por zonas y revisa reservas de comida, agua y peso.",
        "social": "La mayoría se mantiene individualmente; juntar adultos puede provocar peleas graves.",
        "watch": "Diarrea, respiración dificultosa, bultos, heridas o dejar de comer requiere veterinario de exóticos.",
    },
    "small_mammal": {
        "feeding": "La dieta cambia entre rata, ratón, gerbo, chinchilla, degú, erizo y petauro; usa alimento específico de especie.",
        "habitat": "Recinto seguro con ventilación, sustrato, refugios y enriquecimiento adecuados a su forma de trepar, excavar o correr.",
        "routine": "Controla agua, apetito, peso, dientes, piel y limpieza sin eliminar constantemente todos sus olores familiares.",
        "social": "La necesidad de compañía varía mucho: confirma sexo, especie y compatibilidad antes de juntarlos.",
        "watch": "Pérdida de peso, dientes largos, dificultad respiratoria, diarrea o lesiones necesitan veterinario de exóticos.",
    },
    "bird": {
        "feeding": "La dieta debe corresponder a la especie; una mezcla solo de semillas suele ser insuficiente para muchas aves de compañía.",
        "habitat": "Espacio para extender alas, perchas variadas, luz, sueño protegido y aire libre de humo y aerosoles.",
        "routine": "Agua y recipientes limpios, alimento fresco, tiempo seguro de vuelo o actividad y enriquecimiento diario.",
        "social": "Necesita interacción acorde a su especie; las presentaciones con otras aves son graduales y con cuarentena veterinaria.",
        "watch": "Respirar con esfuerzo, permanecer embolado, caídas, sangrado o dejar de comer requiere veterinario aviar.",
    },
    "fish": {
        "feeding": "Alimento específico por especie, tamaño de boca y zona de alimentación; evita sobrealimentar.",
        "habitat": "Acuario ciclado con volumen, temperatura, filtración y parámetros adecuados a la especie exacta.",
        "routine": "Comprueba temperatura y conducta a diario; mide agua y realiza cambios parciales según resultados, nunca por calendario ciego.",
        "social": "Compatibilidad depende de especie, sexo, temperamento, volumen y número; no añadas compañeros sin verificar todo el conjunto.",
        "watch": "Boqueo, aletas pegadas, puntos, heridas, hinchazón o amoníaco/nitrito detectables requieren corrección inmediata.",
    },
    "reptile": {
        "feeding": "La dieta y suplementación dependen de si es insectívoro, herbívoro o carnívoro y de la especie exacta.",
        "habitat": "Terrario con gradiente térmico, humedad, iluminación/UVB, sustrato y refugios específicos; mide, no adivines.",
        "routine": "Registra temperaturas, humedad, alimentación, heces, peso y mudas; limpia sin alterar el microclima necesario.",
        "social": "Muchos reptiles viven mejor solos; no mezcles especies y evita presas vivas que puedan lesionarlos.",
        "watch": "Respiración con boca abierta, quemaduras, muda retenida grave, debilidad o rechazo prolongado de alimento requiere veterinario ARAV.",
    },
    "amphibian": {
        "feeding": "Presas o alimento apropiados por especie y tamaño; cualquier suplemento debe corresponder al plan del especialista.",
        "habitat": "Temperatura, humedad y calidad de agua exactas; evita químicos, metales y manipulación innecesaria de la piel.",
        "routine": "Mide los parámetros relevantes, retira residuos y usa agua tratada con cambios parciales ajustados al sistema.",
        "social": "No mezcles especies; compañeros y densidad solo se consideran tras confirmar compatibilidad y riesgo de depredación.",
        "watch": "Lesiones de piel, flotación anormal, pérdida de apetito, hinchazón o cambios bruscos de conducta requieren especialista.",
    },
    "invertebrate": {
        "feeding": "La frecuencia, presa y suplementación dependen de la especie; retira alimento vivo que pueda molestar durante la muda.",
        "habitat": "Recinto a prueba de escapes con ventilación, sustrato, humedad, temperatura y refugio propios de la especie.",
        "routine": "Revisa agua, microclima, restos y señales de premuda; evita manipular durante o después de la muda.",
        "social": "La mayoría no debe mezclarse salvo especies coloniales conocidas; confirma riesgos de canibalismo y toxinas.",
        "watch": "Caídas, muda fallida, pérdida de extremidades, deshidratación o inmovilidad fuera del patrón normal requieren especialista.",
    },
    "farm_pet": {
        "feeding": "Usa alimento formulado para especie, etapa y función; evita raciones de otra especie y controla condición corporal.",
        "habitat": "Refugio seco, ventilación, sombra, agua, cercado seguro y espacio apropiado para moverse y descansar.",
        "routine": "Revisa apetito, agua, patas o pezuñas, piel/plumaje, heces, peso y prevención veterinaria.",
        "social": "Muchas especies son gregarias, pero sexo, tamaño, cuernos y jerarquía exigen espacio y presentaciones seguras.",
        "watch": "No levantarse, distensión, dificultad respiratoria, heridas, cojera severa o no comer requiere veterinario.",
    },
    "other": {
        "feeding": "Identifica primero la especie exacta; no uses una dieta de otra mascota como sustituto.",
        "habitat": "Roxy necesita especie, origen legal y requisitos ambientales antes de sugerir un hábitat concreto.",
        "routine": "Registra alimentación, agua, peso o tamaño, conducta, eliminación y condiciones del entorno.",
        "social": "No juntes especies o individuos hasta confirmar compatibilidad con una fuente veterinaria especializada.",
        "watch": "Ante signos anormales, contacta a un veterinario con experiencia en esa especie.",
    },
}


CARE_SOURCES = {
    "ferret": ("Manual Veterinario Merck · hurones", "https://www.merckvetmanual.com/all-other-pets/ferrets/providing-a-home-for-a-ferret"),
    "rabbit": ("Manual Veterinario Merck · conejos", "https://www.merckvetmanual.com/all-other-pets/rabbits/providing-a-home-for-a-rabbit"),
    "guinea_pig": ("Manual Veterinario Merck · cobayas", "https://www.merckvetmanual.com/all-other-pets/guinea-pigs/diet-for-a-guinea-pig"),
    "hamster": ("Manual Veterinario Merck · hámsteres", "https://www.merckvetmanual.com/all-other-pets/hamsters/providing-a-home-for-a-hamster"),
    "small_mammal": ("Manual Veterinario Merck · roedores", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/rodents/rodents"),
    "bird": ("Association of Avian Veterinarians · cuidado básico", "https://www.aav.org/resource/resmgr/pdf_2019/AAV_Basic-Care-for-Companion.pdf"),
    "reptile": ("Manual Veterinario Merck · reptiles", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/reptiles/management-and-husbandry-of-reptiles"),
    "amphibian": ("ARAV · veterinarios de reptiles y anfibios", "https://arav.org/"),
    "fish": ("Manual Veterinario Merck · peces", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/aquarium-fishes/management-of-aquarium-fish"),
}


def personalized_pet_care_plan(pet: dict[str, Any]) -> dict[str, Any]:
    species = str(pet.get("species") or "other")
    exact = str(pet.get("exact_species") or pet.get("breed") or "").strip()
    template = CARE_LIBRARY.get(species, CARE_LIBRARY["other"])
    source_label, source_url = CARE_SOURCES.get(
        species,
        ("Manual Veterinario Merck · bienestar de mascotas no tradicionales", "https://www.merckvetmanual.com/special-subjects/animal-welfare/animal-welfare"),
    )
    sections = [
        {"id": "feeding", "icon": "nutrition", "title": "Alimentación", "text": template["feeding"]},
        {"id": "habitat", "icon": "home_and_garden", "title": "Hábitat", "text": template["habitat"]},
        {"id": "routine", "icon": "event_repeat", "title": "Rutina", "text": template["routine"]},
        {"id": "social", "icon": "diversity_1", "title": "Convivencia", "text": template["social"]},
        {"id": "watch", "icon": "health_and_safety", "title": "Qué vigilar", "text": template["watch"], "urgent": True},
    ]
    if pet.get("veterinarian_instructions"):
        sections.insert(0, {
            "id": "vet", "icon": "medical_information", "title": "Indicación veterinaria guardada",
            "text": str(pet["veterinarian_instructions"]), "protected": True,
        })
    return {
        "title": f"Plan de {str(pet.get('name') or 'tu mascota')}",
        "intro": f"Cuidado para {exact or 'la especie pendiente de identificar'}." if exact else "Completa la especie exacta para afinar rangos, alimentación y convivencia.",
        "sections": sections,
        "source_label": source_label,
        "source_url": source_url,
        "needs_exact_species": species in {"bird", "fish", "reptile", "amphibian", "small_mammal", "invertebrate", "farm_pet", "other"} and not exact,
        "legal_note": "Las especies silvestres o reguladas pueden requerir permisos; Roxy no recomienda capturar fauna ni mantener una especie ilegal.",
    }
