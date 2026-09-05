"""Species-aware habitat observations. No diagnoses, dosing or universal stocking rule."""
from __future__ import annotations

from copy import deepcopy
import math
import re
import unicodedata
from typing import Any


def identity(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()).strip()


def exact_identity(pet: dict) -> str:
    return identity(f"{pet.get('exact_species', '')} {pet.get('breed', '')}")


PARROTS = ("periquito australiano", "budgie", "melopsittacus", "ninfa", "cockatiel", "agapornis", "loro gris", "african grey", "guacamayo", "macaw", "conure", "cacatua")


def bird_diet_group(pet: dict) -> str:
    name = exact_identity(pet)
    if any(term in name for term in ("lorikeet", "lori", "trichoglossus", "eos bornea")):
        return "nectar"
    if any(term in name for term in ("mina", "mynah", "gracula")):
        return "softbill"
    if any(term in name for term in ("canario", "canary", "serinus canaria")):
        return "canary"
    if any(term in name for term in PARROTS):
        return "parrot"
    return "unverified"


def question(key, label, *, options=None, unit="", low=0, high=10000):
    row = {"key": key, "label": label, "kind": "select" if options else "number", "unit": unit}
    if options:
        row["options"] = options
    else:
        row.update(min=low, max=high)
    return row


YES_NO = ["Sí", "No", "No sé"]
COMMON = [question("residents", "¿Cuántos animales viven en este recinto?", low=1, high=1000),
          {"key": "companions", "label": "Especies, cantidad y sexo de sus compañeros", "kind": "text"},
          question("length_cm", "Largo útil del recinto", unit="cm", low=1),
          question("width_cm", "Ancho útil del recinto", unit="cm", low=1),
          question("height_cm", "Alto útil del recinto", unit="cm", low=1)]
QUESTIONS = {
    "fish": [question("water_type", "Tipo de agua", options=["Dulce", "Marina", "Salobre", "No sé"]),
             question("volume_l", "Volumen real de agua (sin decoración)", unit="L", low=0.1, high=100000),
             question("cycled", "¿Ciclado confirmado con pruebas de agua?", options=YES_NO),
             question("filter", "¿Tiene filtro biológico funcionando?", options=YES_NO),
             question("temperature_c", "Temperatura medida del agua", unit="°C", low=0, high=50),
             question("ph", "pH medido", low=0, high=14),
             question("ammonia", "Amoniaco total medido", unit="mg/L", high=100),
             question("nitrite", "Nitrito medido", unit="mg/L", high=100),
             question("nitrate", "Nitrato medido", unit="mg/L", high=1000),
             question("adult_length_cm", "Tamaño adulto previsto por pez", unit="cm", low=0.1, high=500)],
    "bird": [question("weaned", "¿Come sola, sin alimentación a mano?", options=YES_NO),
             question("flight_hours", "Tiempo diario fuera del recinto, en un espacio seguro", unit="h", high=24),
             question("bar_spacing_cm", "Separación entre barrotes", unit="cm", low=0.1, high=20),
             question("diet_type", "Base de su alimentación actual", options=["Pellet específico", "Semillas", "Néctar formulado", "Dieta indicada por veterinario", "Otra / no sé"]),
             question("air_hazards", "¿Hay humo, aerosoles o utensilios antiadherentes sobrecalentados cerca?", options=YES_NO),
             question("sleep_hours", "Horas de descanso sin interrupciones", unit="h", high=24)],
    "reptile": [question("warm_c", "Temperatura medida en zona cálida", unit="°C", low=0, high=60),
                question("cool_c", "Temperatura medida en zona fresca", unit="°C", low=0, high=60),
                question("humidity", "Humedad medida", unit="%", high=100),
                question("thermostat", "¿Las fuentes de calor tienen termostato?", options=YES_NO),
                question("uvb", "¿Tiene iluminación UVB adecuada a su especie?", options=YES_NO),
                {"key": "uvb_details", "label": "Modelo, distancia y fecha de instalación de UVB", "kind": "text"},
                {"key": "substrate", "label": "Sustrato y refugios", "kind": "text"}],
    "default": [{"key": "substrate", "label": "Suelo, sustrato y refugios", "kind": "text"},
                question("temperature_c", "Temperatura medida del hábitat", unit="°C", low=-20, high=60),
                question("humidity", "Humedad medida, si corresponde", unit="%", high=100),
                {"key": "specialist_plan", "label": "Necesidades e indicaciones de su especialista", "kind": "text"}],
}


def habitat_questions(pet: dict) -> list[dict]:
    species = pet.get("species")
    rows = deepcopy(COMMON + QUESTIONS.get(species, QUESTIONS["default"]))
    if species == "amphibian" or (species == "invertebrate" and any(t in exact_identity(pet) for t in ("acu", "camaron", "shrimp"))):
        rows += deepcopy(QUESTIONS["fish"])
    return list({row["key"]: row for row in rows}.values())


def validate_observations(pet: dict, values: Any) -> dict:
    if not isinstance(values, dict) or len(values) > 30:
        raise ValueError("Los datos del hábitat no son válidos.")
    fields = {row["key"]: row for row in habitat_questions(pet)}
    clean = {}
    for key, value in values.items():
        if key not in fields:
            raise ValueError("Ese dato no corresponde al hábitat de esta mascota.")
        field = fields[key]
        if value is None or value == "":
            clean[key] = None
        elif field["kind"] == "number":
            try:
                number = float(value)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Revisa {field['label']}.") from exc
            if isinstance(value, bool) or not math.isfinite(number) or not field["min"] <= number <= field["max"] or (key == "residents" and number != int(number)):
                raise ValueError(f"Revisa {field['label']} y su unidad.")
            clean[key] = number
        elif field["kind"] == "select":
            if value not in field["options"]:
                raise ValueError(f"Selecciona una opción válida para {field['label']}.")
            clean[key] = value
        else:
            if not isinstance(value, str) or len(value) > 500:
                raise ValueError("Usa un texto de hasta 500 caracteres.")
            clean[key] = value.strip()
    return clean


SOURCES = {
    "fish": ("Merck · manejo de peces de acuario", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/aquarium-fishes/management-of-aquarium-fish"),
    "bird": ("RSPCA · entorno de aves", "https://www.rspca.org.uk/adviceandwelfare/pets/birds/environment"),
    "reptile": ("Merck · manejo de reptiles", "https://www.merckvetmanual.com/exotic-and-laboratory-animals/reptiles/management-of-reptiles"),
}
BETTA_SOURCE = "https://kb.rspca.org.au/categories/companion-animals/fish/how-should-i-care-for-my-siamese-fighting-fish"
GECKO_SOURCE = "https://www.rspca.org.uk/adviceandwelfare/pets/other/leopardgecko"


def habitat_plan(pet: dict) -> dict:
    species = pet.get("species", "other")
    exact = exact_identity(pet)
    saved = pet.get("habitat_observations") or {}
    values = saved.get("values") or {}
    title = {"fish": "Su acuario", "bird": "Su espacio y vuelo", "reptile": "Su terrario", "amphibian": "Su hábitat y agua"}.get(species, "Su hábitat")
    sections, alerts, sources = [], [], []
    def add(title, text):
        sections.append({"title": title, "text": text})
    def source(label, url):
        sources.append({"label": label, "url": url})
    if species in SOURCES:
        source(*SOURCES[species])
    coverage = "group_guidance"
    if species == "fish":
        add("Agua y mantenimiento", "Registra mediciones reales: agua transparente no demuestra que esté segura. La filtración biológica y los cambios parciales no se sustituyen entre sí. La frecuencia y el volumen de cada cambio se ajustan a las pruebas, al acuario y a sus habitantes; no vacíes todo ni laves el material biológico con agua clorada.")
        add("Espacio y convivencia", "El tamaño adulto, número de peces, necesidad de cardumen, territorio y filtración importan. Roxy no aplica una regla universal de litros por pez ni confirma compatibilidad con nombres incompletos. Antes de añadir compañeros, confirma sus requisitos y el espacio disponible.")
        add("Productos para el agua", "Antes de elegir acondicionador, filtro o test, confirma agua dulce, marina o salobre y volumen real. No mezcles tratamientos ni añadas sal, medicamentos o reguladores de pH sin una indicación específica.")
        if values.get("cycled") != "Sí":
            alerts.append("Ciclado sin confirmar: no añadas más peces hasta verificar el ciclo con pruebas.")
        for key, label in (("ammonia", "Amoniaco"), ("nitrite", "Nitrito")):
            if values.get(key) is not None and values[key] > 0:
                alerts.append(f"{label} detectable: revisa de inmediato la calidad del agua con un especialista. No es una indicación para dosificar medicamentos.")
        if "betta" in exact or "siamese fighting" in exact:
            coverage = "exact_species"
            source("RSPCA Australia · Betta splendens", BETTA_SOURCE)
            add("Betta: espacio y compañeros", "Planifica al menos 20 L para un betta, con filtración y temperatura estable; más agua no garantiza convivencia. Dos machos no deben compartir acuario. Otros compañeros requieren evaluación individual: no hay una lista universal de compañeros seguros.")
            if values.get("volume_l") is not None and values["volume_l"] < 20:
                alerts.append("El volumen guardado está por debajo del objetivo de 20 L para un betta. Revisa una ampliación con un especialista.")
            if values.get("residents", 1) > 1 or values.get("companions"):
                alerts.append("Convivencia del betta pendiente de revisión: cantidad, especie y sexo de todos los habitantes son necesarios.")
        elif "goldfish" in exact or "carassius" in exact:
            source("RSPCA · elegir acuario", "https://www.rspca.org.uk/adviceandwelfare/pets/fish/environment")
            add("Goldfish: planificar su crecimiento", "La referencia de RSPCA es al menos 60 L por goldfish. No es una capacidad garantizada: variedad, longitud adulta, dimensiones y filtración pueden exigir más espacio o un estanque.")
            if values.get("residents") and values.get("volume_l") is not None and values["volume_l"] < 60 * values["residents"]:
                alerts.append("El volumen no alcanza la referencia de 60 L por goldfish para el número de habitantes indicado; confirma cuáles son goldfish y revisa el espacio.")
    elif species == "bird":
        add("Vuelo y recinto", "Registra espacio útil, separación de barrotes y tiempo de vuelo seguro. Incluye perchas de distintos diámetros y forrajeo sin bloquear las alas. Cierra ventanas y apaga ventiladores antes de salir del recinto; no dejes acceso a la cocina.")
        add("Aire y compañía", "Evita humo, aerosoles y vapores de utensilios antiadherentes sobrecalentados. La convivencia requiere identificar especies, sexo, tamaño y comportamiento; nunca la des por segura solo porque sean aves.")
        group = bird_diet_group(pet)
        if group == "nectar":
            coverage = "diet_group"
            add("Loris y lorikeets: néctar específico", "Necesitan una alimentación especializada para nectarívoros. No uses la dieta de semillas o pellets de otro loro ni néctar casero de azúcar. Respeta la preparación del fabricante y retira el alimento deteriorado; confirma el plan con un veterinario aviar.")
            source("VCA · alimentación de loris", "https://vcahospitals.com/central-park/know-your-pet/lories-and-lorikeets-feeding")
        elif group == "canary":
            coverage = "exact_species"
            add("Canario: alimentación específica", "Una dieta solo de semillas es incompleta. Usa alimento formulado para canarios, con los complementos indicados y cambios graduales vigilando el peso. Si hay varios, cada uno debe acceder al alimento y al agua.")
            source("VCA · alimentación del canario", "https://vcahospitals.com/know-your-pet/canaries-feeding")
        elif group == "parrot":
            coverage = "diet_group"
            add("Psitácidas: dieta y forrajeo", "Elige alimento formulado para la especie y tamaño del pico, con vegetales compatibles. Semillas y premios no deben desplazar la dieta base. No ofrezcas aguacate; cualquier transición debe comprobar que el ave realmente come.")
            source("RSPCA · dieta de loros", "https://www.rspca.org.uk/adviceandwelfare/pets/birds/diet")
        else:
            add("Dieta por confirmar", "Esta identificación no tiene una dieta específica revisada en Roxy. No se aplicará automáticamente la dieta de un loro. Guarda su nombre común y científico y consulta a un veterinario aviar.")
        if values.get("weaned") == "No" or pet.get("life_stage") == "baby":
            alerts.append("Ave sin destetar o en etapa bebé: alimentación a mano solo con orientación profesional. No se ofrecen recetas para adultos.")
        if values.get("air_hazards") == "Sí":
            alerts.append("Hay un riesgo ambiental registrado. Aleja al ave de vapores y humo; si muestra dificultad respiratoria busca atención veterinaria urgente.")
    elif species == "reptile":
        add("Clima medido, no estimado", "Mide las zonas cálida y fresca por separado, además de humedad. No uses la temperatura exterior del clima como lectura del terrario. Protege las fuentes de calor y contrólalas con termostato.")
        add("Luz, alimento y convivencia", "UVB, distancia, malla, refugios y suplementos dependen de la especie. No copies el plan de una tortuga a una serpiente o un gecko. No mezcles especies ni cambies dosis de calcio o vitaminas sin revisar el plan.")
        if "gecko leopardo" in exact or "eublepharis macularius" in exact:
            coverage = "exact_species"
            source("RSPCA · gecko leopardo", GECKO_SOURCE)
            add("Gecko leopardo", "Referencia RSPCA: zona cálida de 28–30 °C, fresca de 24–26 °C y humedad general de 30–40 %, además de un refugio húmedo. Son referencias de esa especie, no rangos para todos los reptiles. Revisa el punto y método de medición.")
            add("Alimentación del gecko leopardo", "Invertebrados adecuados a su tamaño, con variedad y suplementación revisada. La referencia distingue juveniles (diario) y adultos (días alternos); la condición individual puede cambiar el plan. Retira insectos no consumidos.")
        if values.get("thermostat") == "No":
            alerts.append("Fuente de calor sin termostato: revisa el control y protección para evitar sobrecalentamiento o quemaduras.")
    else:
        add("Necesidades propias de su especie", "Guarda el nombre exacto, medidas, compañeros, alimento y plan del especialista. No se trasladan requisitos de otras mascotas a este perfil. Las especies no documentadas necesitan revisión antes de recomendar dieta, convivencia o parámetros ambientales.")
    return {"title": title, "coverage": coverage, "questions": habitat_questions(pet), "values": values,
            "recorded_at": saved.get("recorded_at", ""), "sections": sections, "alerts": alerts,
            "sources": sources, "history": deepcopy((pet.get("habitat_history") or [])[-12:]),
            "disclosure": "Datos introducidos por ti; no son lecturas de sensores. Roxy no diagnostica ni controla equipos. Una especie registrada no implica que esté permitida en tu localidad."}
