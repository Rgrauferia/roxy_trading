from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
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
    "ferret": ["Ninguna diagnosticada", "Enfermedad suprarrenal", "Insulinoma o hipoglucemia", "Problema dental", "Problema digestivo", "Enfermedad cardíaca", "Tratamiento activo", "Otra"],
    "rabbit": ["Ninguna diagnosticada", "Problema dental", "Estasis gastrointestinal", "Problema urinario", "Pododermatitis", "Problema respiratorio", "Tratamiento activo", "Otra"],
    "guinea_pig": ["Ninguna diagnosticada", "Deficiencia de vitamina C", "Problema dental", "Problema respiratorio", "Pododermatitis", "Problema urinario", "Tratamiento activo", "Otra"],
    "hamster": ["Ninguna diagnosticada", "Problema dental", "Problema de abazones", "Problema respiratorio", "Diarrea o cola mojada", "Lesión", "Tratamiento activo", "Otra"],
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
    "ferret": ["Mantener peso", "Proteína animal", "Digestión", "Piel y pelaje", "Salud dental", "Juego diario", "Enriquecimiento", "Seguimiento de glucosa"],
    "rabbit": ["Heno y salud dental", "Digestión", "Mantener peso", "Hidratación", "Enriquecimiento", "Convivencia"],
    "guinea_pig": ["Vitamina C", "Heno y salud dental", "Digestión", "Mantener peso", "Enriquecimiento", "Convivencia"],
    "hamster": ["Alimentación equilibrada", "Salud dental", "Mantener peso", "Forrajeo", "Hábitat", "Enriquecimiento"],
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
        {"brand": "Royal Canin", "name": "Large Puppy Dry", "category": "Alimento para crecimiento", "exact_terms": ["bernese mountain"], "life_stages": ["baby", "young"], "image_url": "/assets/roxy_home/products/pets/royal-canin-large-puppy.jpg", "reason": "{pet_name} está registrada como Bernese Mountain Dog joven, una raza grande. Esta fórmula completa está indicada por el fabricante para cachorros de razas grandes de 25 a 45 kg de peso adulto y hasta 15 meses; confirma su edad y peso actuales antes de cambiar su alimento.", "source_url": "https://www.royalcanin.com/us/dogs/products/retail-products/large-puppy-3006", "source_label": "Royal Canin · producto oficial"},
        {"brand": "Hill's Science Diet", "name": "Puppy Large Breed Chicken & Brown Rice", "category": "Alimento para crecimiento", "exact_terms": ["bernese mountain"], "life_stages": ["baby", "young"], "image_url": "/assets/roxy_home/products/pets/hills-large-breed-puppy.jpg", "reason": "Coincide con el perfil joven y de raza grande de {pet_name}. Hill's lo recomienda para cachorros que superarán 55 lb de adultos y hasta 18 meses; su edad, peso, tolerancias y alimento actual siguen pendientes de confirmar.", "source_url": "https://www.hillspet.com/dog-food/science-diet-puppy-large-breed-dry", "source_label": "Hill's · producto oficial"},
        {"brand": "FURminator", "name": "Undercoat deShedding Tool Large Dog Long Hair", "category": "Cuidado del doble manto", "exact_terms": ["bernese mountain"], "image_url": "/assets/roxy_home/products/pets/furminator-large-long-hair.jpg", "reason": "El Bernese Mountain Dog tiene manto doble, largo y abundante. Esta herramienta está diseñada para perros de pelo largo de más de 50 lb; comprueba el peso actual de {pet_name} y úsala suavemente sobre piel sana.", "source_url": "https://www.furminator.com/products/tools/deshedding-tools/undercoat-deshedding-tool-large-dog-long-hair", "source_label": "FURminator · producto oficial", "requires_vet": True},
        {"brand": "KONG", "name": "Classic X-Large", "category": "Enriquecimiento", "exact_terms": ["bernese mountain"], "image_url": "/assets/roxy_home/products/pets/kong-classic.webp", "reason": "La talla X-Large está publicada para perros de 60 a 90 lb y permite usar parte de la ración como enriquecimiento. Confirma primero el peso y la forma de morder de {pet_name}; supervisa el uso y retíralo si se daña.", "source_url": "https://www.kongcompany.com/catalogue/KXL/", "source_label": "KONG · producto oficial", "requires_vet": True},
        {"brand": "KONG", "name": "Wobbler Large", "category": "Comedero interactivo", "exact_terms": ["bernese mountain"], "image_url": "/assets/roxy_home/products/pets/kong-wobbler-large.jpg", "reason": "La versión Large está indicada por KONG para perros medianos y grandes. Puede convertir parte de la ración de {pet_name} en una actividad de olfato y movimiento; no es un juguete para morder y debe usarse con supervisión.", "source_url": "https://www.kongcompany.com/wobbler/", "source_label": "KONG · producto oficial"},
        {"brand": "Virbac", "name": "C.E.T. Enzymatic Toothpaste Poultry Flavor 70 g", "category": "Higiene dental", "exact_terms": ["bernese mountain"], "image_url": "/assets/roxy_home/products/pets/virbac-cet-toothpaste.png", "reason": "La higiene dental debe formar parte del cuidado de {pet_name}. Esta pasta enzimática está formulada para perros y no contiene agentes espumantes; confirma con su veterinario la técnica y suspende si observa intolerancia al sabor avícola.", "source_url": "https://us.virbac.com/home/our-products/pagecontent/product-selector/cet-enzymatic-toothpaste-dog-cat.html", "source_label": "Virbac · producto oficial"},
        {"brand": "Ruffwear", "name": "Front Range Leash 5 ft", "category": "Paseo diario", "exact_terms": ["bernese mountain"], "image_url": "/assets/roxy_home/products/pets/ruffwear-front-range-leash.png", "reason": "Para una Bernese joven como {pet_name}, una correa con asa acolchada, clip giratorio bloqueable y asa de tráfico permite organizar paseos diarios con mayor control. La correa no reemplaza un arnés bien ajustado ni el entrenamiento.", "source_url": "https://ruffwear.com/products/front-range-lightweight-dog-leash?variant=39464180088915", "source_label": "Ruffwear · producto oficial"},
        {"brand": "Chris Christensen", "name": "Big G Slicker Brush Large", "category": "Cepillado del manto", "exact_terms": ["bernese mountain"], "image_url": "/assets/roxy_home/products/pets/chris-christensen-big-g.jpg", "reason": "El manto largo y denso de {pet_name} necesita cepillado regular. La Big G Large está pensada para trabajar el cuerpo y sus púas largas alcanzan mantos densos; úsala con suavidad, por secciones y nunca sobre piel irritada.", "source_url": "https://chrischristensen.com/collections/brushes-slicker-brushes/products/chris-christensen-big-g-slicker-brushes", "source_label": "Chris Christensen · producto oficial"},
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
        {"brand": "Mazuri", "name": "Ferret Diet", "category": "Alimento formulado", "reason": "Alimento formulado para hurones; confirma etapa, condición corporal e historial digestivo.", "image_url": "https://mazuri.com/cdn/shop/files/727613022037_Front_2000x2000_75394396-58f4-4565-abe5-5631bdb301c8.jpg?v=1765908984", "source_url": "https://mazuri.com/products/mazuri-ferret-diet", "source_label": "Mazuri · producto oficial"},
        {"brand": "Oxbow", "name": "Essentials Ferret Food", "category": "Alimento completo", "reason": "Fórmula uniforme para hurones de todas las edades; ajusta la cantidad para mantener una condición corporal adecuada.", "image_url": "https://oxbowanimalhealth.com/wp-content/uploads/2022/05/744845-96833_9_Essentials_Ferret_4lb_main.png", "source_url": "https://oxbowanimalhealth.com/product/essentials-ferret-food/?_species=ferrets", "source_label": "Oxbow · producto oficial"},
        {"brand": "Wysong", "name": "Ferret Epigen 90", "category": "Alimento formulado", "reason": "Alimento seco concentrado para hurones; requiere una transición gradual y control de tolerancia digestiva.", "image_url": "https://www.wysong.net/cdn/shop/products/085835985081_w.png?v=1654265997", "source_url": "https://www.wysong.net/products/ferret-epigen-90", "source_label": "Wysong · producto oficial"},
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


def pet_profile_completion(pet: dict[str, Any]) -> dict[str, Any]:
    """Return a species-aware, explainable checklist without inventing care data."""
    species = str(pet.get("species") or "other")
    checks: list[dict[str, Any]] = []

    def add(field: str, label: str, step: int, complete: bool, reason: str) -> None:
        checks.append({"field": field, "label": label, "step": step, "complete": bool(complete), "reason": reason})

    def known_identity(value: Any) -> bool:
        text = str(value or "").strip().lower()
        return bool(text) and not text.startswith(("no sé", "no se", "otro", "otra", "especie exótica", "especie exotica"))

    if species in {"dog", "cat"}:
        breed = str(pet.get("breed") or "").strip()
        add("breed", "Raza o mezcla", 1, known_identity(breed) or "mestiz" in breed.lower(), "Afina tamaño, etapa y productos compatibles.")
    else:
        add("exact_species", "Especie exacta", 1, known_identity(pet.get("exact_species")), "Evita aplicar cuidados genéricos a especies diferentes.")
    add("life_stage", "Etapa de vida", 2, str(pet.get("life_stage") or "unknown") != "unknown", "Cambia alimentación, frecuencia y señales que deben vigilarse.")
    if species not in {"fish", "amphibian", "invertebrate"}:
        add("weight_kg", "Peso actual", 2, pet.get("weight_kg") not in {None, ""}, "Permite seguir cambios y conversar con el veterinario con datos concretos.")
    add("health", "Alergias y condiciones confirmadas", 2, bool(pet.get("allergies")) and bool(pet.get("conditions")), "Confirma aunque no haya ninguna conocida para filtrar recomendaciones.")
    add("current_food", "Alimento actual", 3, bool(str(pet.get("current_food") or "").strip()), "Separa la dieta habitual de premios y complementos.")
    add("current_food_kind", "Tipo de alimento", 3, str(pet.get("current_food_kind") or "unknown") != "unknown", "Aclara si es completo, veterinario o complementario.")
    add("feeding_frequency", "Frecuencia y horarios", 3, int(pet.get("feeding_frequency") or 0) > 0 and bool(pet.get("feeding_times")), "Organiza el seguimiento sin inventar una frecuencia.")
    add("feeding_amount_source", "Fuente de la cantidad", 3, str(pet.get("feeding_amount_source") or "unknown") != "unknown", "La cantidad debe venir de la etiqueta, veterinario o especialista.")
    measured_species = {"dog", "cat", "ferret", "rabbit", "guinea_pig", "hamster", "small_mammal", "bird", "farm_pet"}
    if species in measured_species:
        add("feeding_amount", "Cantidad y unidad", 3, pet.get("feeding_amount") not in {None, ""} and bool(str(pet.get("feeding_unit") or "").strip()), "Registra la cantidad indicada; Roxy no la calcula automáticamente.")
    environment_species = {"ferret", "rabbit", "guinea_pig", "hamster", "small_mammal", "bird", "fish", "reptile", "amphibian", "invertebrate", "farm_pet", "other"}
    if species in environment_species:
        add("habitat_type", "Tipo de hábitat", 4, bool(str(pet.get("habitat_type") or "").strip()), "Personaliza limpieza, agua, temperatura o seguridad del recinto.")
        add("environment_notes", "Datos del entorno", 4, bool(str(pet.get("environment_notes") or "").strip()), "Conserva volumen, temperatura, humedad u otros parámetros relevantes.")
    add("routine_notes", "Rutina del hogar", 5, bool(str(pet.get("routine_notes") or "").strip()), "Adapta los recordatorios a la vida real de la mascota.")
    completed = sum(1 for item in checks if item["complete"])
    percent = round(completed / len(checks) * 100) if checks else 100
    missing = [{key: value for key, value in item.items() if key != "complete"} for item in checks if not item["complete"]]
    return {
        "percent": percent,
        "completed": completed,
        "total": len(checks),
        "status": "complete" if not missing else "nearly_ready" if percent >= 75 else "needs_details",
        "next_step": int(missing[0]["step"]) if missing else 1,
        "missing": missing,
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
        if life_stages and stage != "unknown" and stage not in life_stages:
            continue
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
        if exact_terms:
            score += 20
            row["identity_specific"] = True
        if row.get("requires_breed") and str(pet.get("breed") or "").strip():
            score += 15
            row["select_before_cart"] = True
            row["reason"] = f"{row['reason']} Busca una fórmula que indique compatibilidad con {pet['breed']}; Roxy no la añadirá sin elegir el producto exacto."
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
        row["reason"] = str(row.get("reason") or "").format(
            pet_name=str(pet.get("name") or "esta mascota"),
            breed=str(pet.get("breed") or pet.get("exact_species") or "su especie"),
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
    "dog": ("Manual Veterinario Merck · perros", "https://www.merckvetmanual.com/dog-owners"),
    "cat": ("Manual Veterinario Merck · gatos", "https://www.merckvetmanual.com/cat-owners"),
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


PET_INFORMATION = {
    "dog": {"life_expectancy": "10–15 años", "characteristics": "Social, sensible a la rutina y con necesidades de ejercicio que cambian mucho según raza, edad y tamaño.", "common_health": "Enfermedad dental, obesidad, alergias, problemas articulares y afecciones propias de cada raza.", "feeding": "Habitualmente 2 comidas al día en adultos; cachorros suelen necesitar más tomas. La etiqueta y el veterinario determinan la cantidad.", "fun_fact": "El olfato canino puede distinguir información que para nosotros es completamente imperceptible."},
    "cat": {"life_expectancy": "12–18 años", "characteristics": "Cazador crepuscular, territorial y muy sensible a cambios bruscos en recursos, olores y rutina.", "common_health": "Enfermedad dental, obesidad, enfermedad renal, problemas urinarios y diabetes.", "feeding": "Varias porciones pequeñas encajan con su conducta natural; la cantidad diaria depende del alimento, peso y etapa.", "fun_fact": "Los gatos usan sus bigotes para medir espacios y percibir corrientes de aire cercanas."},
    "ferret": {"life_expectancy": "5–10 años", "characteristics": "Curioso, activo, sociable y experto en entrar por espacios pequeños; necesita juego supervisado y un hogar protegido contra escapes.", "common_health": "Enfermedad suprarrenal, insulinoma, problemas dentales, obstrucciones digestivas y cardiopatías.", "feeding": "Necesita alimento completo específico, alto en proteína animal, disponible en varias tomas o acceso frecuente según el plan profesional.", "fun_fact": "Duerme gran parte del día, pero al despertar concentra mucha energía en periodos intensos de exploración y juego."},
    "rabbit": {"life_expectancy": "8–12 años", "characteristics": "Animal social y de presa que necesita espacio, escondites, ejercicio y oportunidades seguras para roer.", "common_health": "Problemas dentales, estasis gastrointestinal, pododermatitis y afecciones urinarias.", "feeding": "Heno de pasto disponible todo el día; verduras y pellet medido se ajustan por peso, edad y condición.", "fun_fact": "Sus dientes crecen continuamente, por eso la fibra y la masticación son esenciales."},
    "guinea_pig": {"life_expectancy": "5–7 años", "characteristics": "Muy social, vocal y rutinario; se beneficia de compañía compatible y de refugios múltiples.", "common_health": "Déficit de vitamina C, enfermedad dental, problemas respiratorios y pododermatitis.", "feeding": "Heno siempre disponible, pellet específico y vegetales apropiados; necesita vitamina C dietaria todos los días.", "fun_fact": "No produce su propia vitamina C, igual que los seres humanos."},
    "hamster": {"life_expectancy": "2–3 años", "characteristics": "Nocturno, excavador y recolector; la mayoría de especies domésticas adultas vive mejor individualmente.", "common_health": "Problemas dentales, lesiones, afecciones respiratorias, tumores y diarrea o cola mojada.", "feeding": "Una ración diaria medida de alimento específico, con agua permanente y extras seguros muy limitados.", "fun_fact": "Puede transportar una cantidad sorprendente de alimento en sus abazones hasta el nido."},
    "bird": {"life_expectancy": "Depende de la especie: 5–60+ años", "characteristics": "Inteligente, social y muy sensible al ambiente; sueño, aire limpio, vuelo seguro y enriquecimiento son fundamentales.", "common_health": "Problemas respiratorios, obesidad, deficiencias nutricionales, picaje y afecciones del pico.", "feeding": "La frecuencia y composición dependen de la especie; muchas aves necesitan alimento formulado más vegetales, no solo semillas.", "fun_fact": "Muchas aves ven parte del espectro ultravioleta, un mundo de colores invisible para nosotros."},
    "fish": {"life_expectancy": "Depende de la especie: 2–20+ años", "characteristics": "Su bienestar depende tanto de la química y estabilidad del agua como de la alimentación y el espacio.", "common_health": "Problemas de aletas, parásitos, infecciones, trastornos de flotación y estrés por mala calidad del agua.", "feeding": "Porciones pequeñas según especie, tamaño de boca y zona de alimentación; evita que sobre alimento en el agua.", "fun_fact": "Los peces pueden aprender rutinas, reconocer señales y recordar rutas o lugares de alimentación."},
    "reptile": {"life_expectancy": "Depende de la especie: 5–50+ años", "characteristics": "Ectotermo: temperatura, humedad, iluminación y dieta deben reproducir necesidades muy específicas.", "common_health": "Enfermedad metabólica ósea, parásitos, problemas respiratorios, quemaduras y muda retenida.", "feeding": "Puede comer diariamente o solo algunas veces por semana; la especie y etapa exactas determinan la frecuencia.", "fun_fact": "Algunos reptiles perciben calor o luz ultravioleta de formas que los humanos no pueden."},
    "small_mammal": {"life_expectancy": "Depende de la especie: 2–15 años", "characteristics": "Las necesidades cambian radicalmente entre ratas, chinchillas, degús, erizos y otros pequeños mamíferos.", "common_health": "Problemas dentales, respiratorios, digestivos y de piel; confirma siempre la especie exacta.", "feeding": "Usa alimento y frecuencia específicos de la especie; no intercambies dietas entre pequeños mamíferos.", "fun_fact": "Muchos pequeños mamíferos construyen mapas mentales muy precisos de túneles, refugios y recursos."},
    "amphibian": {"life_expectancy": "Depende de la especie: 5–20+ años", "characteristics": "Piel permeable y gran sensibilidad a químicos, temperatura, humedad y calidad del agua.", "common_health": "Infecciones de piel, problemas de agua, estrés, deshidratación y trastornos nutricionales.", "feeding": "Presas o alimento del tamaño correcto según especie; la frecuencia varía con edad, tamaño y temperatura.", "fun_fact": "Muchos anfibios absorben agua a través de la piel en lugar de beber como los mamíferos."},
    "invertebrate": {"life_expectancy": "Depende de la especie: meses–25+ años", "characteristics": "La muda, el sustrato y el microclima determinan gran parte de su cuidado.", "common_health": "Deshidratación, lesiones, muda fallida y parámetros ambientales inadecuados.", "feeding": "La presa y frecuencia dependen por completo de la especie y de si está antes o después de una muda.", "fun_fact": "Algunas tarántulas pueden vivir décadas, mientras los machos de la misma especie viven mucho menos."},
    "farm_pet": {"life_expectancy": "Depende de la especie: 5–20+ años", "characteristics": "Necesita espacio, refugio, compañía apropiada y manejo preventivo adaptado a su especie y tamaño.", "common_health": "Parásitos, obesidad, problemas digestivos, lesiones y afecciones de patas o pezuñas.", "feeding": "Ración formulada para su especie y etapa, con acceso permanente a agua y forraje cuando corresponda.", "fun_fact": "Muchas especies de granja reconocen individuos, aprenden rutinas y forman vínculos sociales duraderos."},
    "other": {"life_expectancy": "Confirma primero la especie exacta", "characteristics": "Roxy necesita una identificación exacta para ofrecer información responsable y evitar cuidados incompatibles.", "common_health": "Las enfermedades y señales de alerta dependen de la especie.", "feeding": "No uses la dieta de otra mascota; confirma alimento, cantidad y frecuencia con una fuente especializada.", "fun_fact": "Cada especie ocupa un nicho distinto; identificarla correctamente es el primer paso de un buen cuidado."},
}


PET_BREED_INFORMATION = {
    "bernesemountain": {
        "display_name": "Bernese Mountain Dog",
        "life_expectancy": "7–10 años",
        "characteristics": "Los Bernese Mountain Dog suelen ser dulces, afectuosos, inteligentes y muy unidos a su familia. Para Bella, registrada como joven, son importantes la socialización temprana, el entrenamiento con refuerzo positivo y el ejercicio diario moderado; su personalidad individual puede variar.",
        "common_health": "Por predisposición de raza conviene vigilar displasia de cadera o codo, cáncer —incluido el sarcoma histiocítico—, dilatación-torsión gástrica, problemas cardíacos y de tiroides. Esto no significa que Bella tenga estas condiciones.",
        "feeding": "Bella es una Bernese Mountain Dog joven: necesita alimento completo para perros jóvenes de raza grande, porciones medidas y un crecimiento gradual. La etiqueta del alimento y su veterinario determinan la cantidad y la frecuencia.",
        "frequency": "Joven: 2–3 comidas según edad y plan",
        "fun_fact": "La raza nació como perro de trabajo en granjas suizas y se hizo conocida por ayudar a mover ganado y tirar de carros.",
        "source_label": "AKC y BMDCA · Bernese Mountain Dog",
        "source_url": "https://www.bmdca.org/diseases-and-conditions",
    },
}
PET_BREED_INFORMATION["bernesemountaindog"] = PET_BREED_INFORMATION["bernesemountain"]

PET_FEEDING_FREQUENCY = {
    "dog": "Adultos: normalmente 2 veces al día",
    "cat": "2–4 porciones pequeñas al día",
    "ferret": "Varias comidas pequeñas al día",
    "rabbit": "Heno siempre; pellet y verduras medidos",
    "guinea_pig": "Heno siempre; alimento fresco diario",
    "hamster": "1 ración medida al día",
    "bird": "Alimento diario; frecuencia según especie",
    "fish": "1–2 tomas pequeñas según especie",
    "reptile": "Desde diario hasta semanal según especie",
    "small_mammal": "Frecuencia específica para su especie",
    "amphibian": "Según edad, especie y temperatura",
    "invertebrate": "Según especie y ciclo de muda",
    "farm_pet": "Ración diaria según especie y etapa",
    "other": "Pendiente de identificar la especie",
}


PET_DAILY_ROUTINES = {
    "dog": [
        ("morning_meal", "07:30", "Alimentación de la mañana", "Servir la porción habitual guardada.", "nutrition", "daily"),
        ("morning_walk", "08:00", "Paseo y necesidades", "Paseo adaptado a su edad, movilidad y clima.", "directions_walk", "daily"),
        ("evening_meal", "18:30", "Alimentación de la tarde", "Mantener agua fresca y la porción indicada.", "nutrition", "daily"),
        ("daily_check", "20:00", "Revisión rápida", "Apetito, agua, heces, energía y cualquier cambio visible.", "health_and_safety", "daily"),
    ],
    "cat": [
        ("morning_meal", "07:30", "Alimentación de la mañana", "Servir la porción habitual y renovar el agua.", "nutrition", "daily"),
        ("litter_check", "09:00", "Revisar arenero", "Retirar residuos y observar cambios en orina o heces.", "cleaning_services", "daily"),
        ("evening_meal", "18:30", "Alimentación de la tarde", "Seguir su alimento completo e indicaciones guardadas.", "nutrition", "daily"),
        ("enrichment", "20:00", "Juego y enriquecimiento", "Juego breve según su movilidad y temperamento.", "toys", "daily"),
    ],
    "ferret": [
        ("morning_check", "08:00", "Comida, agua y estado general", "Comprobar alimento completo, agua, apetito y energía.", "nutrition", "daily"),
        ("safe_play", "12:00", "Juego supervisado", "Tiempo fuera del recinto en una zona segura para hurones.", "toys", "daily"),
        ("evening_check", "19:00", "Revisión de la tarde", "Revisar alimento, agua, arenero y conducta habitual.", "health_and_safety", "daily"),
        ("habitat_clean", "10:00", "Limpieza del recinto", "Limpieza parcial y revisión de cama, refugios y arenero.", "cleaning_services", "weekly"),
    ],
    "rabbit": [
        ("hay_water", "07:30", "Heno y agua", "Confirmar heno disponible, agua fresca y apetito normal.", "grass", "daily"),
        ("litter_check", "09:00", "Revisar zona de eliminación", "Retirar residuos y observar cantidad y aspecto de las heces.", "cleaning_services", "daily"),
        ("movement", "18:00", "Movimiento y enriquecimiento", "Acceso seguro a ejercicio, escondites y objetos para roer.", "directions_run", "daily"),
        ("health_check", "20:00", "Revisión rápida", "Apetito, postura, dientes visibles y conducta habitual.", "health_and_safety", "daily"),
    ],
    "guinea_pig": [
        ("hay_water", "07:30", "Heno, agua y alimento", "Confirmar heno continuo, agua y su alimento habitual.", "grass", "daily"),
        ("vitamin_food", "18:00", "Alimento fresco planificado", "Seguir la fuente de vitamina C y porciones indicadas.", "nutrition", "daily"),
        ("habitat_check", "19:00", "Revisar recinto", "Retirar zonas húmedas y observar heces, apetito y convivencia.", "home_and_garden", "daily"),
        ("weight_check", "10:00", "Control de peso", "Registrar el peso con el mismo método para detectar tendencias.", "monitor_weight", "weekly"),
    ],
    "hamster": [
        ("evening_food", "19:00", "Comida y agua", "Reponer su alimento habitual y confirmar que el bebedero funciona.", "nutrition", "daily"),
        ("evening_check", "20:00", "Revisión al despertar", "Observar ojos, movilidad, respiración y conducta nocturna.", "health_and_safety", "daily"),
        ("spot_clean", "10:00", "Limpieza por zonas", "Retirar únicamente áreas húmedas o sucias y conservar olores familiares.", "cleaning_services", "weekly"),
    ],
    "bird": [
        ("morning_food", "08:00", "Comida y agua fresca", "Renovar recipientes y seguir la dieta propia de su especie.", "nutrition", "daily"),
        ("social_time", "12:00", "Actividad y convivencia", "Vuelo o enriquecimiento seguro según especie y confianza.", "flutter_dash", "daily"),
        ("evening_check", "19:00", "Revisión del día", "Observar apetito, heces, plumaje, respiración y postura.", "health_and_safety", "daily"),
        ("habitat_clean", "10:00", "Limpieza del espacio", "Limpiar superficies y revisar perchas, juguetes y seguridad.", "cleaning_services", "weekly"),
    ],
    "fish": [
        ("morning_observation", "08:30", "Observar acuario", "Revisar conducta, respiración, temperatura y equipos.", "water", "daily"),
        ("feeding_plan", "09:00", "Alimentación planificada", "Usar únicamente el alimento y la frecuencia definidos para la especie.", "nutrition", "daily"),
        ("evening_observation", "19:00", "Revisión de la tarde", "Observar apetito, flotación, lesiones y funcionamiento del filtro.", "visibility", "daily"),
        ("water_maintenance", "10:00", "Mantenimiento del agua", "Medir parámetros y hacer solo el cambio parcial previsto para el sistema.", "science", "weekly"),
    ],
    "reptile": [
        ("environment_check", "08:00", "Temperatura, luz y humedad", "Comprobar el gradiente y equipos según la especie exacta.", "device_thermostat", "daily"),
        ("feeding_plan", "10:00", "Revisar plan de alimentación", "Alimentar únicamente si corresponde hoy según especie, edad y plan guardado.", "nutrition", "daily"),
        ("evening_check", "19:00", "Revisión del animal", "Observar postura, ojos, respiración, piel, heces y actividad.", "health_and_safety", "daily"),
        ("habitat_clean", "10:00", "Mantenimiento del terrario", "Retirar residuos y revisar sustrato, refugios y equipos.", "cleaning_services", "weekly"),
    ],
    "amphibian": [
        ("environment_check", "08:00", "Agua, temperatura y humedad", "Comprobar los parámetros propios de la especie sin manipularla.", "water", "daily"),
        ("feeding_plan", "18:00", "Revisar plan de alimentación", "Alimentar solo si corresponde y retirar presas no consumidas.", "nutrition", "daily"),
        ("health_check", "20:00", "Observación sin manipular", "Revisar piel, postura, apetito y comportamiento desde fuera.", "visibility", "daily"),
        ("habitat_maintenance", "10:00", "Mantenimiento del hábitat", "Realizar el cuidado parcial programado para agua o sustrato.", "cleaning_services", "weekly"),
    ],
}


def personalized_pet_routines(pet: dict[str, Any]) -> list[dict[str, Any]]:
    species = str(pet.get("species") or "other")
    fallback = [
        ("morning_check", "08:00", "Revisión de la mañana", "Comprobar agua, alimento, entorno y conducta habitual.", "pets", "daily"),
        ("evening_check", "19:00", "Revisión de la tarde", "Registrar apetito, actividad, eliminación y cualquier cambio.", "health_and_safety", "daily"),
        ("habitat_maintenance", "10:00", "Mantenimiento del hábitat", "Realizar la limpieza parcial apropiada para la especie.", "cleaning_services", "weekly"),
    ]
    logs = [row for row in pet.get("care_log", []) if isinstance(row, dict)]
    today = datetime.now(timezone.utc).date().isoformat()
    routines = []
    for routine_id, time, title, detail, icon, cadence in PET_DAILY_ROUTINES.get(species, fallback):
        latest = next((row for row in reversed(logs) if row.get("routine_id") == routine_id), None)
        completed_at = str((latest or {}).get("completed_at") or "")
        routines.append({
            "id": routine_id, "time": time, "title": title, "detail": detail, "icon": icon,
            "cadence": cadence, "completed_today": completed_at[:10] == today,
            "last_completed_at": completed_at,
        })
    return routines


NUTRITION_FRAMEWORKS = {
    "dog": "Usa un alimento completo para su etapa y tamaño. La cantidad debe venir de la etiqueta, el fabricante o su veterinario y ajustarse con la condición corporal.",
    "cat": "Usa un alimento completo para gatos y su etapa. Divide la cantidad diaria indicada sin compensar premios con reducciones improvisadas.",
    "ferret": "Usa un alimento completo específico para hurones, alto en proteína animal y bajo en carbohidratos. No sustituyas su dieta con premios caseros.",
    "rabbit": "El heno apropiado debe ser la base continua; hojas, pellets y premios dependen de edad, peso y criterio veterinario.",
    "guinea_pig": "Necesita heno continuo y una fuente diaria fiable de vitamina C; confirma pellets y vegetales apropiados con su veterinario.",
    "hamster": "Usa una dieta completa para su especie y vigila el alimento almacenado; no calcules consumo solo por el recipiente vacío.",
    "small_mammal": "La dieta cambia mucho entre roedores y otros pequeños mamíferos. Confirma especie exacta antes de fijar ingredientes o frecuencia.",
    "bird": "La proporción de alimento formulado, vegetales y otros componentes depende de la especie. Evita dietas basadas solo en semillas.",
    "fish": "Alimento, tamaño de partícula, días y frecuencia dependen de la especie, temperatura y sistema. Retira sobrantes y no sobrealimentes.",
    "reptile": "Presa, vegetales, suplementos y frecuencia dependen de especie, edad, temperatura y UVB. Roxy no presupone alimentación diaria.",
    "amphibian": "Tipo de presa, suplementación y frecuencia dependen de especie, etapa y temperatura. Retira alimento no consumido.",
    "invertebrate": "La presa y frecuencia dependen de especie, tamaño y muda. No dejes alimento vivo molestando a un animal en premuda.",
    "farm_pet": "Usa una ración formulada para especie, etapa y función; nunca intercambies alimento entre especies sin indicación profesional.",
    "other": "Identifica la especie exacta antes de establecer dieta, ingredientes o frecuencia.",
}


def personalized_pet_nutrition_plan(pet: dict[str, Any]) -> dict[str, Any]:
    species = str(pet.get("species") or "other")
    source_label, source_url = CARE_SOURCES.get(
        species,
        ("Manual Veterinario Merck · bienestar animal", "https://www.merckvetmanual.com/special-subjects/animal-welfare/animal-welfare"),
    )
    amount = pet.get("feeding_amount")
    unit = str(pet.get("feeding_unit") or "").strip()
    frequency = int(pet.get("feeding_frequency") or 0)
    times = [str(value) for value in pet.get("feeding_times") or [] if str(value).strip()]
    logs = [row for row in pet.get("care_log", []) if isinstance(row, dict) and row.get("routine_id") == "feeding_observation"]
    return {
        "title": f"Alimentación de {str(pet.get('name') or 'tu mascota')}",
        "current_food": str(pet.get("current_food") or "").strip(),
        "food_kind": str(pet.get("current_food_kind") or "unknown"),
        "framework": NUTRITION_FRAMEWORKS.get(species, NUTRITION_FRAMEWORKS["other"]),
        "amount": amount,
        "unit": unit,
        "frequency": frequency,
        "times": times,
        "amount_source": str(pet.get("feeding_amount_source") or "unknown"),
        "feeding_notes": str(pet.get("feeding_notes") or "").strip(),
        "configured": bool(pet.get("current_food") and (amount or frequency or times)),
        "needs_professional_amount": not bool(amount),
        "last_feeding": deepcopy(logs[-1]) if logs else None,
        "source_label": source_label,
        "source_url": source_url,
        "safety_note": "Las indicaciones veterinarias y la etiqueta del alimento siempre prevalecen. Roxy no calcula dosis médicas ni inventa porciones.",
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
    information = deepcopy(PET_INFORMATION.get(species, PET_INFORMATION["other"]))
    information["frequency"] = PET_FEEDING_FREQUENCY.get(species, PET_FEEDING_FREQUENCY["other"])
    breed_key = "".join(character for character in exact.casefold() if character.isalnum())
    breed_information = PET_BREED_INFORMATION.get(breed_key)
    if breed_information:
        information.update({key: value for key, value in breed_information.items() if key not in {"source_label", "source_url"}})
        information["scope"] = "breed"
        source_label = str(breed_information["source_label"])
        source_url = str(breed_information["source_url"])
    return {
        "title": f"Plan de {str(pet.get('name') or 'tu mascota')}",
        "intro": f"Cuidado para {exact or 'la especie pendiente de identificar'}." if exact else "Completa la especie exacta para afinar rangos, alimentación y convivencia.",
        "sections": sections,
        "information": information,
        "routines": personalized_pet_routines(pet),
        "routine_notes": str(pet.get("routine_notes") or "").strip(),
        "source_label": source_label,
        "source_url": source_url,
        "needs_exact_species": species in {"bird", "fish", "reptile", "amphibian", "small_mammal", "invertebrate", "farm_pet", "other"} and not exact,
        "legal_note": "Las especies silvestres o reguladas pueden requerir permisos; Roxy no recomienda capturar fauna ni mantener una especie ilegal.",
    }
