from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any
import unicodedata


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
        {"brand": "Ruffwear", "name": "Front Range Harness", "category": "Arnés para paseo", "exact_terms": ["bernese mountain"], "image_url": "/assets/roxy_home/products/pets/ruffwear-front-range-harness.png", "reason": "Su construcción acolchada y cuatro puntos de ajuste ofrecen una opción concreta para los paseos de {pet_name}. La talla no se deduce por la raza: mide el contorno de la parte más ancha del pecho antes de elegirla.", "source_url": "https://ruffwear.com/products/front-range-everyday-dog-harness", "source_label": "Ruffwear · producto oficial", "requires_measurement": True},
        {"brand": "earthbath", "name": "Oatmeal & Aloe Shampoo Fragrance Free 16 fl oz", "category": "Baño y pelaje", "exact_terms": ["bernese mountain"], "image_url": "/assets/roxy_home/products/pets/earthbath-oatmeal-aloe-shampoo.png", "reason": "Es una opción sin fragancia y con pH equilibrado para limpiar el manto abundante de {pet_name}. El fabricante la indica para animales mayores de seis semanas; evita ojos y oídos y no la uses sobre piel lesionada sin consultar al veterinario.", "source_url": "https://www.earthbath.com/products/oatmeal-aloe-shampoo-fragrance-free", "source_label": "earthbath · producto oficial"},
        {"brand": "Purina Pro Plan", "name": "Complete Essentials Adult Chicken & Rice", "category": "Alimento completo", "life_stages": ["adult"], "reason": "Fórmula completa para mantenimiento adulto; confirma en la etiqueta la declaración de adecuación nutricional.", "source_url": "https://www.purina.com/pro-plan/dogs/adult-dog-food", "source_label": "Purina · línea oficial"},
        {"brand": "Purina Pro Plan", "name": "Sensitive Skin & Stomach Salmon & Rice", "category": "Alimento completo", "conditions": ["piel sensible", "estómago sensible"], "reason": "Opción comercial formulada para sistemas sensibles y disponible por etapa y tamaño.", "source_url": "https://www.purina.com/pro-plan/dogs/sensitive-stomach-skin-dog-food", "source_label": "Purina · producto oficial"},
        {"brand": "Royal Canin", "name": "Breed Health Nutrition", "category": "Alimento específico por raza", "requires_breed": True, "reason": "Línea que permite buscar una fórmula por raza y tamaño; la coincidencia exacta depende del catálogo vigente del fabricante.", "source_url": "https://www.royalcanin.com/us/dogs/products/breed-health-nutrition", "source_label": "Royal Canin · catálogo oficial"},
        {"brand": "Hill's Science Diet", "name": "Adult Perfect Weight", "category": "Control de peso", "goals": ["bajar peso"], "goal_required": True, "reason": "Alternativa para conversar con el veterinario cuando el objetivo es controlar peso.", "source_url": "https://www.hillspet.com/dog-food", "source_label": "Hill's · catálogo oficial"},
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


# A broader verified shelf. These are species-specific essentials, not paid rankings;
# exact identity, life stage, conditions and selected goals still gate the rows below.
PRODUCTS["dog"].extend([
    {"brand": "Virbac", "name": "C.E.T. Enzymatic Toothpaste", "category": "Higiene dental", "reason": "Apoya la rutina dental de {pet_name}; usa únicamente pasta formulada para perros y confirma la técnica con su veterinario.", "source_url": "https://us.virbac.com/home/our-products/pagecontent/product-selector/cet-enzymatic-toothpaste-dog-cat.html", "source_label": "Virbac · producto oficial"},
    {"brand": "Ruffwear", "name": "Front Range Harness", "category": "Paseo", "reason": "Arnés acolchado con cuatro puntos de ajuste para {pet_name}; la talla depende del contorno real del pecho, no de la raza.", "requires_measurement": True, "source_url": "https://ruffwear.com/products/front-range-everyday-dog-harness", "source_label": "Ruffwear · producto oficial"},
])
PRODUCTS["cat"].extend([
    {"brand": "Catit", "name": "Senses 2.0 Food Tree", "category": "Enriquecimiento alimentario", "reason": "Permite que {pet_name} trabaje por parte de su ración y ayuda a reducir la velocidad al comer; úsalo con su alimento habitual medido.", "source_url": "https://catit.us/products/catit-senses-2-0-food-tree", "source_label": "Catit · producto oficial"},
    {"brand": "Virbac", "name": "C.E.T. Enzymatic Toothpaste", "category": "Higiene dental", "reason": "Producto dental formulado para gatos que puede integrarse a la rutina de {pet_name}; la aceptación y técnica deben introducirse gradualmente.", "source_url": "https://us.virbac.com/home/our-products/pagecontent/product-selector/cet-enzymatic-toothpaste-dog-cat.html", "source_label": "Virbac · producto oficial"},
    {"brand": "Catit", "name": "PIXI Smart Fountain", "category": "Hidratación", "reason": "Fuente con filtración y control de flujo para mantener agua disponible para {pet_name}; limpia bomba, depósito y filtro con la frecuencia del fabricante.", "source_url": "https://catit.us/products/catit-pixi-smart-fountain", "source_label": "Catit · producto oficial"},
    {"brand": "FURminator", "name": "Undercoat deShedding Tool Medium/Large Cat Long Hair", "category": "Cuidado del manto", "exact_terms": ["maine coon", "bosque de noruega", "ragdoll", "siberiano"], "reason": "La variedad de pelo largo registrada para {pet_name} necesita control del subpelo; elige la talla por peso real y úsala únicamente sobre piel sana.", "requires_measurement": True, "source_url": "https://www.furminator.com/products/deshed/cat/undercoat-deshedding-tool-medium-large-cat-long-hair.aspx", "source_label": "FURminator · producto oficial"},
    {"brand": "KONG", "name": "Connects Window Teaser", "category": "Enriquecimiento", "reason": "Añade una sesión de caza simulada y movimiento para {pet_name}; supervisa el juego y guarda el juguete si alguna pieza se afloja.", "source_url": "https://www.kongcompany.com/catalogue/CA42/", "source_label": "KONG · producto oficial"},
])
PRODUCTS["rabbit"].extend([
    {"brand": "Oxbow", "name": "Garden Select Adult Rabbit Food", "category": "Pellet uniforme", "life_stages": ["adult", "senior"], "reason": "Fórmula adulta específica para conejo que evita la selección de piezas; para {pet_name}, el heno de pasto continúa siendo la base.", "source_url": "https://oxbowanimalhealth.com/product/garden-select-adult-rabbit-food/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Oxbow", "name": "Enriched Life Crazy Hay Ball", "category": "Forrajeo y masticación", "reason": "Accesorio de Timothy para explorar, rodar y masticar, conductas naturales que enriquecen el día de {pet_name}.", "source_url": "https://oxbowanimalhealth.com/product/enriched-life-crazy-hay-ball/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Oxbow", "name": "Timothy CLUB Tunnel", "category": "Refugio y forrajeo", "reason": "Túnel comestible de heno para exploración y refugio de {pet_name}; comprueba medidas, desgaste y limpieza antes de incorporarlo.", "requires_measurement": True, "source_url": "https://oxbowanimalhealth.com/product/timothy-club-tunnel/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Oxbow", "name": "Natural Science Digestive Support", "category": "Apoyo digestivo", "reason": "Suplemento de fibra para pequeños herbívoros; para {pet_name} solo debe añadirse después de revisar dieta, síntomas y dosis con su veterinario.", "requires_vet": True, "source_url": "https://oxbowanimalhealth.com/product/natural-science-digestive-support/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Oxbow", "name": "Simple Rewards Timothy Treats", "category": "Premio medido", "reason": "Premio basado en heno para {pet_name}; úsalo en una cantidad pequeña y sin reducir su acceso continuo a heno de pasto.", "source_url": "https://oxbowanimalhealth.com/product/simple-rewards-timothy-treats/", "source_label": "Oxbow · producto oficial"},
])
PRODUCTS["guinea_pig"].extend([
    {"brand": "Oxbow", "name": "Natural Science Vitamin C", "category": "Vitamina C", "reason": "Suplemento específico para pequeños herbívoros; para {pet_name}, la dosis solo debe seguir la etiqueta o la indicación veterinaria.", "requires_vet": True, "source_url": "https://oxbowanimalhealth.com/product/natural-science-vitamin-c-support/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Oxbow", "name": "Enriched Life Crazy Hay Ball", "category": "Forrajeo y masticación", "reason": "Combina heno Timothy con exploración y masticación para {pet_name}; no sustituye el acceso continuo a heno limpio.", "source_url": "https://oxbowanimalhealth.com/product/enriched-life-crazy-hay-ball/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Oxbow", "name": "Garden Select Adult Guinea Pig Food", "category": "Pellet uniforme", "life_stages": ["adult", "senior"], "reason": "Fórmula adulta específica para cobayas; para {pet_name}, se combina con heno, agua y la vitamina C indicada, sin adivinar cantidades.", "source_url": "https://oxbowanimalhealth.com/product/garden-select-adult-guinea-pig-food/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Oxbow", "name": "Timothy CLUB Tunnel", "category": "Refugio y forrajeo", "reason": "Túnel de heno para esconderse y explorar; verifica que el tamaño permita a {pet_name} entrar y salir sin quedar atrapada.", "requires_measurement": True, "source_url": "https://oxbowanimalhealth.com/product/timothy-club-tunnel/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Oxbow", "name": "Natural Science Digestive Support", "category": "Apoyo digestivo", "reason": "Producto veterinario de apoyo que no reemplaza la dieta ni una evaluación; úsalo para {pet_name} solo con dosis confirmada.", "requires_vet": True, "source_url": "https://oxbowanimalhealth.com/product/natural-science-digestive-support/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Oxbow", "name": "Western Timothy Hay", "category": "Heno", "reason": "Heno de pasto para acceso diario y desgaste dental de {pet_name}; descarta material húmedo, polvoriento o con olor anormal.", "source_url": "https://oxbowanimalhealth.com/product/western-timothy-hay/", "source_label": "Oxbow · producto oficial"},
])
PRODUCTS["hamster"].extend([
    {"brand": "Niteangel", "name": "Super-Silent Hamster Exercise Wheel", "category": "Ejercicio", "reason": "Rueda de superficie sólida para la actividad nocturna de {pet_name}; selecciona diámetro según su especie exacta y comprueba que corra sin arquear la espalda.", "requires_measurement": True, "source_url": "https://www.niteangelpet.com/collections/hamster-wheels", "source_label": "Niteangel · catálogo oficial"},
    {"brand": "Oxbow", "name": "Enriched Life Crazy Hay Ball", "category": "Forrajeo", "reason": "Añade exploración y manipulación al entorno de {pet_name}; úsalo como enriquecimiento, no como reemplazo de su alimento formulado.", "source_url": "https://oxbowanimalhealth.com/product/enriched-life-crazy-hay-ball/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Niteangel", "name": "Multi-Chamber Hamster House", "category": "Refugio", "reason": "Refugio de varias cámaras para que {pet_name} organice nido y almacenamiento; elige el tamaño según su especie exacta y recinto.", "requires_measurement": True, "source_url": "https://www.niteangelpet.com/collections/hamster-hideouts", "source_label": "Niteangel · catálogo oficial"},
    {"brand": "Kaytee", "name": "Clean & Cozy White Bedding", "category": "Sustrato", "reason": "Cama de papel para excavar y anidar; confirma profundidad, ventilación y tolerancia de {pet_name}, y cambia las zonas húmedas con regularidad.", "source_url": "https://www.kaytee.com/all-products/small-animal/clean-cozy-white-bedding", "source_label": "Kaytee · producto oficial"},
    {"brand": "Kaytee", "name": "Come Along Small Animal Carrier", "category": "Transporte", "reason": "Transportador ventilado para traslados de {pet_name}; selecciona la talla por medidas reales y no lo uses como vivienda permanente.", "requires_measurement": True, "source_url": "https://www.kaytee.com/all-products/small-animal/kaytee-come-along-carrier", "source_label": "Kaytee · producto oficial"},
    {"brand": "Zoo Med", "name": "Digital Terrarium Thermometer", "category": "Control del entorno", "reason": "Permite vigilar la temperatura del recinto de {pet_name}; interpreta la lectura según su especie exacta y ubicación del sensor.", "source_url": "https://zoomed.com/digital-terrarium-thermometer/", "source_label": "Zoo Med · producto oficial"},
])
PRODUCTS["bird"].extend([
    {"brand": "Harrison's", "name": "High Potency Fine", "category": "Transición alimentaria", "exact_terms": ["periquito", "canario", "ninfa", "cockatiel", "agapornis", "pinzón"], "reason": "Fórmula fina que el fabricante utiliza en determinadas transiciones y etapas; para {pet_name}, confirma especie, etapa y duración con un veterinario aviar.", "requires_vet": True, "source_url": "https://www.harrisonsbirdfoods.com/product/high-potency-fine/", "source_label": "Harrison's · producto oficial"},
    {"brand": "Lafeber", "name": "Classic Nutri-Berries", "category": "Forrajeo alimentario", "reason": "Formato de alimento para manipular y explorar; selecciona la versión que corresponda al tamaño y especie de {pet_name}.", "select_before_cart": True, "source_url": "https://lafeber.com/product/classic-nutri-berries/", "source_label": "Lafeber · catálogo oficial"},
    {"brand": "Lafeber", "name": "Avi-Cakes", "category": "Forrajeo alimentario", "reason": "Formato que combina nutrición y manipulación; para {pet_name}, elige la presentación de su especie y tamaño de pico antes de añadirla.", "select_before_cart": True, "source_url": "https://lafeber.com/product/avi-cakes/", "source_label": "Lafeber · catálogo oficial"},
    {"brand": "Lafeber", "name": "Premium Daily Diet Pellets", "category": "Alimento formulado", "reason": "Línea de pellets en tamaños distintos; selecciona la fórmula exacta de la especie y tamaño de pico de {pet_name}, no una presentación genérica.", "select_before_cart": True, "source_url": "https://lafeber.com/product/premium-daily-diet-pellets/", "source_label": "Lafeber · catálogo oficial"},
])
PRODUCTS["fish"].extend([
    {"brand": "Hikari", "name": "Freeze Dried Daphnia", "category": "Rotación alimentaria", "exact_terms": ["betta", "guppy", "molly", "platy", "tetra", "danio"], "reason": "Opción de rotación para peces pequeños compatibles; para {pet_name}, ajusta al tamaño de boca y retira sobrantes.", "source_url": "https://www.hikariusa.com/freeze_dried_folder/fd_daphnia.html", "source_label": "Hikari · producto oficial"},
    {"brand": "Seachem", "name": "Ammonia Alert", "category": "Vigilancia del agua", "reason": "Monitor continuo de amoníaco libre para el acuario de {pet_name}; no reemplaza las pruebas completas ni el mantenimiento del sistema.", "source_url": "https://www.seachem.com/ammonia-alert.php", "source_label": "Seachem · producto oficial"},
    {"brand": "Zoo Med", "name": "Micro Floating Betta Pellets", "category": "Alimento específico", "exact_terms": ["betta"], "reason": "Pellet flotante diseñado para betta; para {pet_name}, usa la cantidad de etiqueta compatible con su tamaño y retira cualquier sobrante.", "source_url": "https://zoomed.com/betta/", "source_label": "Zoo Med · catálogo oficial para betta"},
    {"brand": "Zoo Med", "name": "Betta Bed Leaf Hammock", "category": "Descanso y enriquecimiento", "exact_terms": ["betta"], "reason": "Hoja de descanso cerca de la superficie para un betta como {pet_name}; colócala según la guía y mantenla limpia.", "source_url": "https://zoomed.com/betta/", "source_label": "Zoo Med · catálogo oficial para betta"},
    {"brand": "Zoo Med", "name": "Digital Betta Thermometer", "category": "Temperatura del agua", "exact_terms": ["betta"], "reason": "Termómetro destinado a acuarios de betta; permite relacionar apetito y actividad de {pet_name} con la temperatura real.", "source_url": "https://zoomed.com/betta/", "source_label": "Zoo Med · catálogo oficial para betta"},
    {"brand": "API", "name": "Freshwater Master Test Kit", "category": "Pruebas del agua", "reason": "Kit para medir parámetros básicos de agua dulce; registra los resultados del acuario de {pet_name} y actúa según el ciclado y la especie.", "source_url": "https://apifishcare.com/product/freshwater-master-test-kit", "source_label": "API · producto oficial"},
])
PRODUCTS["reptile"].extend([
    {"brand": "Zoo Med", "name": "ReptiTemp Digital Infrared Thermometer", "category": "Temperatura", "reason": "Permite medir superficies concretas del gradiente térmico de {pet_name}; compara las lecturas con el rango de su especie exacta.", "source_url": "https://zoomed.com/reptitemp-digital-infrared-thermometer/", "source_label": "Zoo Med · producto oficial"},
    {"brand": "Zoo Med", "name": "ReptiSafe Water Conditioner", "category": "Agua segura", "reason": "Acondicionador para el agua usada con reptiles; calcula la dosis con el volumen real del recipiente de {pet_name}.", "source_url": "https://zoomed.com/reptisafe-water-conditioner/", "source_label": "Zoo Med · producto oficial"},
    {"brand": "Zoo Med", "name": "Repti Calcium Without D3", "category": "Calcio", "reason": "Suplemento de calcio; para {pet_name}, la elección entre fórmulas con o sin D3 depende de dieta, UVB y criterio veterinario.", "requires_vet": True, "source_url": "https://zoomed.com/repti-calcium-without-d3/", "source_label": "Zoo Med · producto oficial"},
    {"brand": "Zoo Med", "name": "Digital Combo Thermometer Humidity Gauge", "category": "Microclima", "reason": "Registra temperatura y humedad en el terrario de {pet_name}; coloca el sensor donde permita comprobar su gradiente real.", "source_url": "https://zoomed.com/digital-combo-thermometer-humidity-gauge/", "source_label": "Zoo Med · producto oficial"},
    {"brand": "Zoo Med", "name": "ReptiSun UVB Lamp", "category": "Iluminación UVB", "reason": "Línea UVB con intensidades y tamaños diferentes; elige para {pet_name} solo después de confirmar especie, distancia y dimensiones del terrario.", "select_before_cart": True, "source_url": "https://zoomed.com/reptisun/", "source_label": "Zoo Med · catálogo oficial"},
])
PRODUCTS["ferret"].extend([
    {"brand": "Oxbow", "name": "Enriched Life Play Garden", "category": "Enriquecimiento", "image_url": "https://oxbowanimalhealth.com/wp-content/uploads/2022/04/744845-96649_6_Enriched_Life_Play_Garden_main.png", "reason": "Actividad de exploración compatible con hurones para la rutina diaria de {pet_name}; supervisa para evitar ingestión o desgaste peligroso.", "source_url": "https://oxbowanimalhealth.com/product/enriched-life-play-garden/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Oxbow", "name": "Enriched Life Woven Hideout", "category": "Refugio", "image_url": "https://oxbowanimalhealth.com/wp-content/uploads/2022/04/744845-96537_6_Enriched_Life_Woven_Hideout_-_M_main.png", "reason": "Refugio de acceso abierto compatible con hurones para que {pet_name} descanse y se esconda; selecciona el tamaño correcto y revisa su estado con frecuencia.", "requires_measurement": True, "source_url": "https://oxbowanimalhealth.com/product/enriched-life-woven-hideout/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Oxbow", "name": "Essentials Ferret Food", "category": "Alimento formulado", "image_url": "https://oxbowanimalhealth.com/wp-content/uploads/2022/05/744845-96833_9_Essentials_Ferret_4lb_main.png", "reason": "Alimento completo formulado para hurones; compara con la dieta actual de {pet_name} y realiza cualquier transición de forma gradual.", "requires_vet": True, "source_url": "https://oxbowanimalhealth.com/product/essentials-ferret-food/", "source_label": "Oxbow · producto oficial"},
    {"brand": "MidWest Homes for Pets", "name": "Ferret Nation Double Unit", "category": "Hábitat", "image_url": "https://www.midwesthomes4pets.com/wp-content/uploads/181_1.jpg", "reason": "Hábitat multinivel para hurones; confirma que dimensiones, rampas y separación de barrotes sean adecuadas para {pet_name} y su convivencia.", "requires_measurement": True, "source_url": "https://www.midwesthomes4pets.com/product/small-animal/habitats-cages/ferret-nation/", "source_label": "MidWest · producto oficial"},
    {"brand": "Kaytee", "name": "Come Along Small Animal Carrier", "category": "Transporte", "image_url": "https://www.kaytee.com/-/media/Project/OneWeb/Kaytee/US/all-products/small-animal/come-along-carrier/Large/045125623055_Come_Along_Carrier_Lrg_pk_front.jpg", "reason": "Transportador ventilado para traslados de {pet_name}; elige la talla por medidas reales y añade una base segura para el viaje.", "requires_measurement": True, "source_url": "https://www.kaytee.com/all-products/small-animal/come-along-carrier", "source_label": "Kaytee · producto oficial"},
])
PRODUCTS["small_mammal"].extend([
    {"brand": "Oxbow", "name": "Poof! Chinchilla Dust Bath", "category": "Baño de polvo", "exact_terms": ["chinchilla"], "reason": "Polvo de baño específico para el cuidado del manto de una chinchilla como {pet_name}; ofrece sesiones controladas y mantén el material seco.", "source_url": "https://oxbowanimalhealth.com/product/poof-chinchilla-dust-bath/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Oxbow", "name": "Enriched Life Crazy Hay Ball", "category": "Forrajeo y masticación", "exact_terms": ["chinchilla", "rata", "raton", "gerbo", "degu"], "reason": "Favorece exploración, juego y masticación en especies compatibles; para {pet_name}, confirma que el material encaje con su especie y dieta.", "source_url": "https://oxbowanimalhealth.com/product/enriched-life-crazy-hay-ball/", "source_label": "Oxbow · producto oficial"},
    {"brand": "Mazuri", "name": "Rat & Mouse Diet", "category": "Alimento formulado", "exact_terms": ["rata", "raton"], "reason": "Fórmula uniforme para ratas y ratones; para {pet_name}, verifica etapa, peso y la tabla de alimentación antes de cambiar su dieta.", "source_url": "https://mazuri.com/collections/rat-mouse", "source_label": "Mazuri · catálogo oficial"},
    {"brand": "Oxbow", "name": "Essentials Hamster & Gerbil Food", "category": "Alimento formulado", "exact_terms": ["gerbo"], "reason": "Alimento uniforme para hámsteres y gerbos que reduce la selección de piezas; ajusta la cantidad al perfil de {pet_name}.", "source_url": "https://oxbowanimalhealth.com/our-products/fortified-food/", "source_label": "Oxbow · catálogo oficial"},
    {"brand": "Oxbow", "name": "Western Timothy Hay", "category": "Heno", "exact_terms": ["perrito de la pradera"], "reason": "Heno de pasto como recurso de fibra y forrajeo para {pet_name}; confirma el resto del plan con un veterinario de exóticos.", "source_url": "https://oxbowanimalhealth.com/our-products/hay/", "source_label": "Oxbow · catálogo oficial"},
    {"brand": "Zoo Med", "name": "Digital Terrarium Thermometer", "category": "Control del entorno", "reason": "Permite registrar la temperatura del espacio de {pet_name}; el rango correcto depende de su especie exacta y su veterinario de exóticos.", "source_url": "https://zoomed.com/digital-terrarium-thermometer/", "source_label": "Zoo Med · producto oficial"},
    {"brand": "Kaytee", "name": "Come Along Small Animal Carrier", "category": "Transporte", "reason": "Transportador ventilado para pequeños animales; mide a {pet_name}, confirma material y talla, y úsalo solo para traslados supervisados.", "requires_measurement": True, "source_url": "https://www.kaytee.com/all-products/small-animal/kaytee-come-along-carrier", "source_label": "Kaytee · producto oficial"},
    {"brand": "Exotic Nutrition", "name": "Digital Small Animal Scale", "category": "Seguimiento de peso", "reason": "Permite registrar cambios de peso de {pet_name} en casa; confirma capacidad y precisión adecuadas para su especie y comparte tendencias con su veterinario.", "requires_measurement": True, "source_url": "https://exoticnutrition.com/", "source_label": "Exotic Nutrition · fabricante oficial"},
])
PRODUCTS["amphibian"].extend([
    {"brand": "Seachem", "name": "Prime", "category": "Acondicionador de agua", "exact_terms": ["ajolote", "triton"], "reason": "Acondiciona agua dulce; para el sistema acuático de {pet_name}, usa únicamente la dosis de etiqueta para el volumen real.", "source_url": "https://www.seachem.com/prime.php", "source_label": "Seachem · producto oficial"},
    {"brand": "Zoo Med", "name": "Digital Terrarium Thermometer", "category": "Temperatura", "reason": "Ayuda a vigilar la temperatura del entorno de {pet_name}; el rango correcto depende de su especie exacta y no se debe adivinar.", "source_url": "https://zoomed.com/digital-terrarium-thermometer/", "source_label": "Zoo Med · producto oficial"},
    {"brand": "Zoo Med", "name": "Digital Combo Thermometer Humidity Gauge", "category": "Microclima", "reason": "Registra temperatura y humedad del hábitat de {pet_name}; interpreta ambos valores según su especie exacta, no con un rango genérico.", "source_url": "https://zoomed.com/digital-combo-thermometer-humidity-gauge/", "source_label": "Zoo Med · producto oficial"},
])
PRODUCTS["invertebrate"].extend([
    {"brand": "Zoo Med", "name": "Digital Terrarium Thermometer", "category": "Temperatura", "reason": "Permite registrar la temperatura del microhábitat de {pet_name}; interpreta el valor según su especie y etapa.", "source_url": "https://zoomed.com/digital-terrarium-thermometer/", "source_label": "Zoo Med · producto oficial"},
    {"brand": "Zoo Med", "name": "Angled Stainless Steel Feeding Tongs", "category": "Alimentación segura", "exact_terms": ["tarantula", "escorpion", "mantis", "insecto palo"], "reason": "Ayuda a manipular alimento y retirar restos manteniendo distancia; no fuerces a {pet_name} a comer ni dejes presas durante la muda.", "source_url": "https://zoomed.com/", "source_label": "Zoo Med · fabricante oficial"},
    {"brand": "Zoo Med", "name": "Creature Habitat Kit", "category": "Hábitat", "exact_terms": ["tarantula", "escorpion", "mantis", "insecto palo", "escarabajo"], "reason": "Recinto para pequeños invertebrados; selecciona el tamaño y la ventilación según la especie exacta de {pet_name}, nunca solo por apariencia.", "requires_measurement": True, "source_url": "https://zoomed.com/creature-habitat-kit/", "source_label": "Zoo Med · producto oficial"},
    {"brand": "Zoo Med", "name": "Digital Combo Thermometer Humidity Gauge", "category": "Microclima", "reason": "Permite registrar temperatura y humedad del microhábitat de {pet_name}; usa los rangos de su especie y etapa exactas.", "source_url": "https://zoomed.com/digital-combo-thermometer-humidity-gauge/", "source_label": "Zoo Med · producto oficial"},
    {"brand": "Zoo Med", "name": "Creature Soil", "category": "Sustrato", "reason": "Sustrato para invertebrados; confirma para {pet_name} profundidad, humedad, riesgo de ingestión y compatibilidad con la muda.", "select_before_cart": True, "source_url": "https://zoomed.com/creature-soil/", "source_label": "Zoo Med · producto oficial"},
])
PRODUCTS["farm_pet"].extend([
    {"brand": "Mazuri", "name": "Mini Pig Treats", "category": "Premio medido", "exact_terms": ["cerdo miniatura"], "reason": "Premio formulado para cerdo miniatura; para {pet_name}, debe contarse dentro de su plan calórico y control de condición corporal.", "source_url": "https://mazuri.com/collections/mini-pig", "source_label": "Mazuri · catálogo oficial"},
    {"brand": "Mazuri", "name": "Mini Pig Active Adult", "category": "Alimento por etapa", "exact_terms": ["cerdo miniatura"], "life_stages": ["adult"], "reason": "Fórmula completa para cerdo miniatura adulto activo; confirma peso, condición corporal y porción de {pet_name} antes de cualquier transición.", "requires_vet": True, "source_url": "https://mazuri.com/collections/mini-pig", "source_label": "Mazuri · catálogo oficial"},
    {"brand": "Mazuri", "name": "Mini Pig Youth", "category": "Alimento por etapa", "exact_terms": ["cerdo miniatura"], "life_stages": ["baby", "young"], "reason": "Fórmula para la etapa de crecimiento de un cerdo miniatura; úsala para {pet_name} únicamente si su edad y condición coinciden con la etiqueta.", "requires_vet": True, "source_url": "https://mazuri.com/collections/mini-pig", "source_label": "Mazuri · catálogo oficial"},
    {"brand": "Jolly Pets", "name": "Push-N-Play Ball", "category": "Enriquecimiento", "exact_terms": ["cerdo miniatura"], "reason": "Pelota rígida para empujar y explorar; selecciona un diámetro que {pet_name} no pueda ingerir y supervisa cada sesión.", "requires_measurement": True, "source_url": "https://jollypets.com/products/push-n-play-dog-toy", "source_label": "Jolly Pets · producto oficial"},
    {"brand": "Mazuri", "name": "Waterfowl Maintenance Diet", "category": "Alimento por especie", "exact_terms": ["pato", "ganso"], "life_stages": ["adult", "senior"], "reason": "Fórmula de mantenimiento para aves acuáticas adultas; confirma que especie, etapa y acceso al agua de {pet_name} coincidan con la etiqueta.", "source_url": "https://mazuri.com/collections/waterfowl", "source_label": "Mazuri · catálogo oficial"},
    {"brand": "Little Giant", "name": "DuraFlex Rubber Feed Pan", "category": "Comedero resistente", "reason": "Recipiente flexible y resistente para servir la porción medida de {pet_name}; elige capacidad según su especie, cantidad real y forma de alimentación, y lávalo después de cada uso.", "requires_measurement": True, "source_url": "https://miller-mfg.com/products/rubber-feed-pan", "source_label": "Miller Manufacturing · producto oficial"},
    {"brand": "Little Giant", "name": "Flat Back Bucket", "category": "Agua y rutina", "reason": "Recipiente de pared plana para organizar agua o alimento de {pet_name}; confirma capacidad, anclaje seguro y limpieza diaria según su especie antes de elegirlo.", "requires_measurement": True, "source_url": "https://miller-mfg.com/collections/buckets", "source_label": "Miller Manufacturing · catálogo oficial"},
    {"brand": "Mazuri", "name": "Mini Pig Mature Maintenance", "category": "Alimento de mantenimiento", "exact_terms": ["cerdo miniatura"], "conditions": ["sobrepeso"], "reason": "Fórmula de mantenimiento para cerdos miniatura maduros o menos activos; para {pet_name}, solo se muestra porque su perfil registra control de peso y requiere confirmar edad y condición corporal.", "requires_vet": True, "source_url": "https://mazuri.com/collections/mini-pig", "source_label": "Mazuri · catálogo oficial"},
    {"brand": "Purina Animal Nutrition", "name": "Goat Feed", "category": "Alimento por especie", "exact_terms": ["cabra"], "reason": "Línea formulada para cabras; la opción de {pet_name} debe elegirse según edad, función, condición corporal y forraje disponible.", "select_before_cart": True, "source_url": "https://www.purinamills.com/goat-feed", "source_label": "Purina · catálogo oficial"},
    {"brand": "Purina Animal Nutrition", "name": "Sheep Feed", "category": "Alimento por especie", "exact_terms": ["oveja"], "reason": "Línea específica para ovejas; selecciona la fórmula de {pet_name} por etapa y evita intercambiar minerales destinados a otras especies.", "select_before_cart": True, "source_url": "https://www.purinamills.com/sheep-feed", "source_label": "Purina · catálogo oficial"},
    {"brand": "Mazuri", "name": "Alpaca Maintenance Diet", "category": "Alimento por especie", "exact_terms": ["alpaca"], "reason": "Dieta formulada para camélidos; para {pet_name}, confirma etapa, forraje, peso y cantidad con su veterinario o nutricionista animal.", "requires_vet": True, "source_url": "https://mazuri.com/collections/alpaca-llama", "source_label": "Mazuri · catálogo oficial"},
])


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
    normalize = lambda value: re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower()).strip()
    exact = normalize(f"{pet.get('exact_species', '')} {pet.get('breed', '')}")
    stage = str(pet.get("life_stage") or "unknown")
    conditions = {str(value).lower() for value in pet.get("conditions") or []}
    goals = {str(value).lower() for value in pet.get("goals") or []}
    allergies = {normalize(value) for value in pet.get("allergies") or [] if not normalize(value).startswith("ninguna")}
    allergen_aliases = {
        "pollo": {"pollo", "chicken", "poultry"}, "res": {"res", "beef"},
        "pescado": {"pescado", "fish", "salmon", "tuna"}, "huevo": {"huevo", "egg"},
        "trigo": {"trigo", "wheat"}, "maiz": {"maiz", "corn"}, "soya": {"soya", "soy"},
        "lacteos": {"leche", "milk", "dairy", "cheese", "yogurt"},
    }
    vet_context = bool(
        conditions - {"ninguna diagnosticada", "ninguna observada"}
        or str(pet.get("veterinarian_instructions") or "").strip()
    )
    rows: list[dict[str, Any]] = []
    for source in PRODUCTS.get(species, []):
        row = deepcopy(source)
        product_text = normalize(f"{row.get('brand', '')} {row.get('name', '')}")
        if any(any(alias in product_text for alias in allergen_aliases.get(allergy, {allergy})) for allergy in allergies):
            continue
        exact_terms = [normalize(value) for value in row.pop("exact_terms", [])]
        if exact_terms and not any(term in exact for term in exact_terms):
            continue
        row_goals = {str(value).lower() for value in row.pop("goals", [])}
        row_conditions = {str(value).lower() for value in row.pop("conditions", [])}
        life_stages = set(row.pop("life_stages", []))
        if life_stages and stage != "unknown" and stage not in life_stages:
            continue
        if row_conditions and not row_conditions.intersection(conditions):
            continue
        if row.pop("goal_required", False) and not row_goals.intersection(goals):
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
            personalization_scope = "exact_identity"
        elif life_stages and stage in life_stages:
            personalization_scope = "life_stage"
        elif row_goals & goals:
            personalization_scope = "selected_goal"
        else:
            personalization_scope = "species_essential"
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
            personalization_scope=personalization_scope,
            requires_measurement=bool(row.get("requires_measurement")),
        )
        pet_name = str(pet.get("name") or "esta mascota")
        identity = str(pet.get("breed") or pet.get("exact_species") or species).strip()
        stage_label = {"baby": "bebé", "young": "joven", "adult": "adulta", "senior": "senior"}.get(stage, "etapa pendiente")
        reason = str(row.get("reason") or "").format(
            pet_name=pet_name,
            breed=identity or "su especie",
        )
        row["profile_label"] = f"Para {pet_name} · {identity} · {stage_label}"
        row["reason"] = reason if pet_name.lower() in reason.lower() else f"Para {pet_name}, según su perfil {identity} y etapa {stage_label}: {reason}"
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
