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
    "default": ["Ninguna diagnosticada", "Sobrepeso", "Bajo peso", "Problema digestivo", "Problema dental", "Tratamiento activo", "Otra"],
}

GOALS = {
    "dog": ["Mantener peso", "Bajar peso", "Subir peso", "Piel y pelaje", "Digestión", "Articulaciones", "Energía", "Premios de entrenamiento"],
    "cat": ["Mantener peso", "Bajar peso", "Subir peso", "Hidratación", "Bolas de pelo", "Digestión", "Tracto urinario", "Enriquecimiento"],
    "fish": ["Agua estable", "Coloración", "Crecimiento", "Compatibilidad", "Reducir estrés", "Rutina de alimentación"],
    "reptile": ["Temperatura correcta", "Humedad correcta", "UVB", "Muda", "Peso", "Enriquecimiento"],
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
        {"brand": "Mazuri", "name": "Mini Bird Diet", "category": "Alimento formulado", "reason": "Dieta formulada para aves pequeñas no reproductoras; la transición debe ser gradual.", "source_url": "https://mazuri.com/products/mazuri-mini-bird-diets", "source_label": "Mazuri · producto oficial"},
        {"brand": "Harrison's", "name": "Adult Lifetime Fine", "category": "Alimento formulado", "reason": "Alternativa para determinadas aves adultas; confirma especie y tamaño de partícula con un veterinario aviar.", "source_url": "https://www.harrisonsbirdfoods.com/product/adult-lifetime-fine/", "source_label": "Harrison's · producto oficial"},
    ],
    "fish": [
        {"brand": "Hikari", "name": "Betta Bio-Gold", "category": "Alimento específico", "exact_terms": ["betta"], "reason": "Pellet flotante formulado para bettas; la cantidad depende del tamaño y se evita sobrealimentar.", "source_url": "https://www.hikariusa.com/tropical_folder/betta_bio_gold.html", "source_label": "Hikari · producto oficial"},
        {"brand": "Hikari", "name": "Micro Pellets", "category": "Alimento para peces pequeños", "reason": "Opción para peces tropicales pequeños; confirma especie, tamaño de boca y zona de alimentación.", "source_url": "https://www.hikariusa.com/tropical.html", "source_label": "Hikari · catálogo oficial"},
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
