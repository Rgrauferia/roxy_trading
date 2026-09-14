"""Versioned editorial adult exercise sessions, separate from clinical plan gates.

Sources and exact variants were reviewed in reports/home-fitness-213/content-audit.md.
No member data, provider calls, loading algorithm, clinical approval or media are used.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import math
from typing import Any

CONTENT_VERSION = "home-training-213-v1"
CHECKED_ON = "2026-09-14"


class TrainingContentError(ValueError):
    """An unknown or invalid editorial session must never become a saved session."""


SOURCES = {
    "strength": {"title": "Original de consulta: ejercicios de fuerza", "url": "https://www.nhs.uk/live-well/exercise/strength-exercises/"},
    "flexibility": {"title": "Original de consulta: flexibilidad", "url": "https://www.nhs.uk/live-well/exercise/flexibility-exercises/"},
    "sitting": {"title": "Original de consulta: movimientos en silla", "url": "https://www.nhs.uk/live-well/exercise/sitting-exercises/"},
    "weights": {"title": "Mayo Clinic: técnica con pesas", "url": "https://www.mayoclinic.org/healthy-lifestyle/fitness/in-depth/weight-training/art-20045842"},
    "squat": {"title": "Mayo Clinic: sentadilla con mancuernas", "url": "https://www.mayoclinic.org/healthy-lifestyle/fitness/multimedia/squat/vid-20084682"},
    "row": {"title": "Mayo Clinic: remo con mancuerna", "url": "https://www.mayoclinic.org/healthy-lifestyle/fitness/multimedia/bent-over-row/vid-20084680"},
    "curl": {"title": "Mayo Clinic: curl con mancuerna", "url": "https://www.mayoclinic.org/healthy-lifestyle/fitness/multimedia/biceps-curl/vid-20084675"},
    "press": {"title": "Mayo Clinic: press de pecho con mancuernas", "url": "https://www.mayoclinic.org/healthy-lifestyle/fitness/multimedia/chest-press/vid-20084677"},
    "calf": {"title": "Mayo Clinic: elevación de talones con mancuernas", "url": "https://www.mayoclinic.org/healthy-lifestyle/fitness/multimedia/calf-raise/vid-20084681"},
    "core": {"title": "Mayo Clinic: técnica para el centro del cuerpo", "url": "https://www.mayoclinic.org/healthy-lifestyle/fitness/in-depth/core-strength/art-20546851"},
    "core_start": {"title": "Mayo Clinic: comenzar con cinco repeticiones", "url": "https://newsnetwork.mayoclinic.org/discussion/ready-to-run-how-to-strengthen-your-core/"},
    "yoga": {"title": "Cleveland Clinic: primeras posturas de yoga", "url": "https://health.clevelandclinic.org/yoga-for-beginners"},
    "yoga_chair": {"title": "Cleveland Clinic: yoga de pie y en silla", "url": "https://health.clevelandclinic.org/yoga-poses-improve-flexibility"},
    "cdc": {"title": "CDC: series y repeticiones para adultos", "url": "https://www.cdc.gov/physical-activity-basics/adding-adults/what-counts.html"},
    "acsm": {"title": "ACSM: recomendaciones de fuerza de 2026", "url": "https://acsm.org/resistance-training-guidelines-update-2026/"},
    "recovery": {"title": "NIDDK: recuperación entre días de fuerza", "url": "https://www.niddk.nih.gov/health-information/weight-management/healthy-eating-physical-activity-for-life/health-tips-for-adults"},
}

EQUIPMENT_LABELS = {
    "bodyweight": "Peso corporal", "chair": "Silla estable, sin ruedas ni brazos",
    "wall": "Pared despejada y firme", "dumbbells": "Mancuernas",
    "bench": "Banco plano estable", "mat": "Colchoneta antideslizante",
}
CAPABILITY_LABELS = {
    "standing": "Puedo permanecer de pie y caminar con control",
    "sit_to_stand": "Puedo sentarme y levantarme de una silla",
    "hip_hinge": "Conozco la inclinación desde la cadera con espalda estable",
    "free_weights": "Puedo sujetar y mover mancuernas con control",
    "bench_transfer": "Sé colocar las mancuernas y entrar y salir del banco con seguridad",
    "floor_transfer": "Puedo bajar al suelo y volver a levantarme",
    "kneeling": "Puedo apoyarme sobre manos y rodillas",
}
OGL_ATTRIBUTION = "Contains public sector information licensed under the Open Government Licence v3.0."
OGL_URL = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"


def _links(*keys: str) -> list[dict[str, str]]:
    return [dict(SOURCES[key]) for key in dict.fromkeys(keys)]


def _dose(*, reps: int | None = None, reps_max: int | None = None, sets: int = 1,
          seconds: int | None = None, seconds_max: int | None = None,
          per_side: bool = False, hold_seconds: int | None = None,
          hold_seconds_max: int | None = None, hold_breaths: int | None = None,
          breaths_min: int | None = None, breaths_max: int | None = None,
          basis: str = "source", label: str, note: str = "") -> dict[str, Any]:
    return {"sets": sets, "reps_min": reps, "reps_max": reps_max if reps_max is not None else reps,
            "seconds": seconds, "seconds_max": seconds_max if seconds_max is not None else seconds,
            "per_side": per_side, "hold_seconds": hold_seconds,
            "hold_seconds_max": hold_seconds_max if hold_seconds_max is not None else hold_seconds,
            "hold_breaths": hold_breaths, "breaths_min": breaths_min, "breaths_max": breaths_max,
            "basis": basis, "label": label, "note": note}


def _exercise(id: str, name: str, instructions: list[str], dose: dict[str, Any], *,
              equipment: tuple[str, ...] = ("bodyweight",), capabilities: tuple[str, ...] = (),
              sources: tuple[str, ...], cue: str, phase: str = "work",
              load_recordable: bool = False) -> dict[str, Any]:
    return {"id": id, "name": name, "phase": phase, "instructions": instructions,
            "cue": cue, "dose": dose, "tracking_unit": "reps" if dose["reps_min"] is not None else "seconds",
            "equipment": list(equipment), "capabilities": list(capabilities), "source_links": _links(*sources),
            "rest": {"mode": "manual", "suggested_seconds": None,
                     "label": "Descansa y continúa cuando estés listo. Puedes pausar o terminar en cualquier momento."},
            "load": None, "load_recordable": load_recordable,
            "media": None, "technical_demonstration": False}


def _walk(phase: str) -> dict[str, Any]:
    warming = phase == "warmup"
    return _exercise(
        "walking-warmup" if warming else "walking-cooldown",
        "Entra en movimiento" if warming else "Baja el ritmo",
        ["Deja espacio libre para caminar y coloca el material fuera del paso.",
         "Camina a un ritmo cómodo; mueve los brazos con naturalidad y respira sin contener el aire.",
         "Aumenta el ritmo gradualmente sin agotarte." if warming else "Ve más despacio hasta recuperar una respiración tranquila; prolonga el cierre si lo necesitas."],
        _dose(seconds=300 if warming else 180, label="5 min de caminata suave" if warming else "3 min suaves, o más si lo necesitas",
              basis="source" if warming else "editorial",
              note="Se elige el extremo inferior del calentamiento de 5–10 min de la fuente." if warming else "Duración orientativa elegida para cerrar esta sesión; no es una dosis publicada."),
        capabilities=("standing",), sources=("weights",), cue="Respira con normalidad.", phase=phase)


SIT_STAND = _exercise("chair-sit-stand", "Levántate de la silla", [
    "Apoya ambos pies en el suelo, separados al ancho de la cadera, y siéntate cerca del borde de una silla firme.",
    "Inclina un poco el tronco y levántate despacio, mirando al frente.",
    "Ponte erguido y vuelve a sentarte con control; las manos pueden ayudarte a guiar la bajada."],
    _dose(reps=5, label="1 serie · 5 repeticiones"), equipment=("bodyweight", "chair"),
    capabilities=("standing", "sit_to_stand"), sources=("strength",), cue="Controla la bajada; no te dejes caer.")
MINI_SQUAT = _exercise("chair-mini-squat", "Mini sentadilla con apoyo", [
    "De pie detrás de la silla, sujeta suavemente el respaldo y separa los pies al ancho de la cadera.",
    "Flexiona las rodillas lentamente dentro de un recorrido cómodo, manteniendo la espalda estable.",
    "Mantén las rodillas orientadas como los pies y vuelve a erguirte sin tirarte del respaldo."],
    _dose(reps=5, label="1 serie · 5 repeticiones"), equipment=("bodyweight", "chair"),
    capabilities=("standing",), sources=("strength",), cue="La silla da apoyo; revisa que no se deslice.")
CALF_CHAIR = _exercise("chair-calf-raise", "Eleva los talones con apoyo", [
    "Colócate detrás de la silla, con ambas manos en el respaldo y los pies apoyados.",
    "Sube los dos talones despacio, hasta una altura que puedas controlar.",
    "Baja los talones suavemente y vuelve a apoyar toda la planta antes de repetir."],
    _dose(reps=5, label="1 serie · 5 repeticiones"), equipment=("bodyweight", "chair"),
    capabilities=("standing",), sources=("strength",), cue="Evita los rebotes.")
SIDE_LEG = _exercise("chair-side-leg-lift", "Abre una pierna con apoyo", [
    "Apoya las manos en el respaldo de una silla firme y mantén el tronco erguido.",
    "Separa una pierna hacia el lado hasta donde puedas sin inclinar la cintura.",
    "Vuelve al centro con control. Completa ese lado y después cambia de pierna."],
    _dose(reps=5, per_side=True, label="1 serie · 5 repeticiones por lado"), equipment=("bodyweight", "chair"),
    capabilities=("standing",), sources=("strength",), cue="La pelvis se mantiene al frente.")
HIP_EXTENSION = _exercise("chair-hip-extension", "Lleva la pierna atrás", [
    "De pie, sujeta el respaldo y alarga suavemente el cuerpo hacia arriba.",
    "Lleva una pierna recta hacia atrás sin arquear la zona lumbar.",
    "Mantén hasta 5 segundos si resulta cómodo, vuelve al apoyo y repite en ambos lados."],
    _dose(reps=5, per_side=True, hold_seconds=5, label="5 por lado · hasta 5 s en cada elevación",
          note="Cinco segundos es un máximo de la fuente; puedes volver antes."), equipment=("bodyweight", "chair"),
    capabilities=("standing",), sources=("strength",), cue="Acorta el recorrido si la espalda comienza a arquearse.")
WALL_PUSH = _exercise("wall-pushup", "Flexión en la pared", [
    "Sitúate a un brazo de distancia de una pared firme. Coloca las palmas a la altura del pecho, con los dedos hacia arriba.",
    "Acerca el cuerpo doblando los codos junto al tronco; mantén la espalda recta.",
    "Empuja con las manos para volver despacio. Haz una pausa entre series y conserva un recorrido cómodo."],
    _dose(reps=5, reps_max=10, sets=3, label="3 series · 5–10 repeticiones"), equipment=("bodyweight", "wall"),
    capabilities=("standing",), sources=("strength",), cue="Mueve el cuerpo en bloque, sin hundir la cintura.")
DB_SQUAT = _exercise("dumbbell-squat", "Sentadilla con mancuernas a los lados", [
    "Sujeta las mancuernas junto al cuerpo, con pies aproximadamente al ancho de los hombros.",
    "Flexiona caderas y rodillas como al sentarte, manteniendo el tronco estable y las rodillas alineadas con los pies.",
    "En esta variante, limita la bajada a unos 90 grados de rodilla como máximo; vuelve a subir con control."],
    _dose(reps=12, reps_max=15, label="1 serie · 12–15 repeticiones"), equipment=("bodyweight", "dumbbells"),
    capabilities=("standing", "free_weights"), sources=("squat",), cue="Usa un peso que te permita conservar el control; no hay kilos predeterminados.", load_recordable=True)
DB_ROW = _exercise("dumbbell-bent-row", "Remo inclinado, un brazo cada vez", [
    "Con pies separados y rodillas suaves, inclínate desde la cadera. La espalda permanece estable y la mancuerna cuelga bajo el hombro.",
    "Lleva el codo hacia atrás hasta alinearlo aproximadamente con el tronco; evita adelantar o girar el hombro.",
    "Baja despacio. Completa el lado, deja el peso de forma controlada y cambia de brazo."],
    _dose(reps=12, reps_max=15, per_side=True, label="1 serie · 12–15 repeticiones por brazo"), equipment=("bodyweight", "dumbbells"),
    capabilities=("standing", "hip_hinge", "free_weights"), sources=("row",), cue="Mantén quieto el tronco y evita el impulso.", load_recordable=True)
DB_CURL = _exercise("dumbbell-curl", "Curl de bíceps de pie", [
    "Sujeta una mancuerna con la palma hacia delante y el codo cerca del cuerpo.",
    "Dobla el codo para subir el peso, sin balancear el brazo ni flexionar la muñeca.",
    "Desciende lentamente. Completa las repeticiones y cambia de brazo."],
    _dose(reps=12, reps_max=15, per_side=True, label="1 serie · 12–15 repeticiones por brazo"), equipment=("bodyweight", "dumbbells"),
    capabilities=("standing", "free_weights"), sources=("curl",), cue="Muñeca recta y codo cerca del costado.", load_recordable=True)
DB_CALF = _exercise("dumbbell-calf-raise", "Talones con mancuernas", [
    "De pie con una mancuerna en cada mano, deja los brazos a los lados y separa los pies de forma cómoda.",
    "Eleva ambos talones sin doblar las rodillas ni perder el equilibrio.",
    "Apoya los talones de nuevo lentamente. Si no controlas el equilibrio, termina esta variante y elige la sesión con silla."],
    _dose(reps=12, reps_max=15, label="1 serie · 12–15 repeticiones"), equipment=("bodyweight", "dumbbells"),
    capabilities=("standing", "free_weights"), sources=("calf",), cue="Evita rebotes y no añadas carga si pierdes estabilidad.", load_recordable=True)
DB_PRESS = _exercise("dumbbell-flat-bench-press", "Press en banco plano", [
    "Prepara un banco plano firme y una carga que ya puedas colocar y retirar con control. Túmbate con cabeza apoyada y pies estables.",
    "Sujeta las mancuernas sobre el pecho, con antebrazos verticales y codos flexionados.",
    "Empuja hacia arriba sin bloquear los codos. Baja suavemente, sin dejar que los codos caigan por debajo de la línea del torso."],
    _dose(reps=12, reps_max=15, label="1 serie · 12–15 repeticiones"), equipment=("bodyweight", "dumbbells", "bench"),
    capabilities=("free_weights", "bench_transfer"), sources=("press",), cue="Mantén la cabeza relajada; no empujes con los pies.", load_recordable=True)
NECK = _exercise("seated-neck-rotation", "Mira a cada lado", [
    "Siéntate erguido con los hombros relajados y la mirada al frente.",
    "Gira la cabeza despacio hacia un hombro hasta un punto cómodo, sin forzar.",
    "Mantén 5 segundos, vuelve al centro y repite hacia el otro lado."],
    _dose(reps=3, per_side=True, hold_seconds=5, label="3 por lado · 5 s de pausa"), equipment=("bodyweight", "chair"),
    sources=("flexibility",), cue="Los hombros permanecen quietos.")
CHEST = _exercise("seated-chest-opening", "Abre el pecho en la silla", [
    "Siéntate erguido sin descansar sobre el respaldo y apoya los pies.",
    "Lleva los hombros un poco atrás y abajo; abre suavemente los brazos a los lados.",
    "Eleva el pecho hasta notar un estiramiento ligero. Mantén 5–10 segundos y relaja antes de repetir."],
    _dose(reps=5, hold_seconds=5, hold_seconds_max=10, label="5 repeticiones · 5–10 s"), equipment=("bodyweight", "chair"),
    sources=("sitting",), cue="No busques dolor ni arquees la espalda para llegar más lejos.")
TWIST = _exercise("seated-upper-body-turn", "Gira suavemente el tronco", [
    "Siéntate con los pies firmes, cruza los brazos sobre el pecho y alarga la espalda.",
    "Gira el tronco a un lado sin desplazar la pelvis, dentro de un recorrido cómodo.",
    "Mantén 5 segundos y vuelve al frente. Cambia de lado con el mismo control."],
    _dose(reps=5, per_side=True, hold_seconds=5, label="5 por lado · 5 s de pausa"), equipment=("bodyweight", "chair"),
    sources=("sitting",), cue="Gira despacio, sin tirar de los brazos.")
SIDE_BEND = _exercise("standing-side-bend", "Inclina el cuerpo hacia un lado", [
    "Ponte de pie con los pies separados al ancho de la cadera y los brazos a los lados.",
    "Desliza una mano por el costado al inclinarte ligeramente, sin girar hacia delante.",
    "Espera 2 segundos, vuelve al centro y repite por el otro lado."],
    _dose(reps=3, per_side=True, hold_seconds=2, label="3 por lado · 2 s de pausa"),
    capabilities=("standing",), sources=("flexibility",), cue="Busca un recorrido pequeño y cómodo.")
CALF_STRETCH = _exercise("wall-calf-stretch", "Estira la pantorrilla en la pared", [
    "Apoya las manos en la pared. Adelanta un pie y lleva el otro atrás, dejando ambos talones apoyados.",
    "Flexiona la rodilla delantera y mantén recta la pierna de atrás hasta notar un estiramiento suave.",
    "Respira sin rebotes; vuelve al centro y cambia de lado."],
    _dose(reps=3, per_side=True, hold_seconds=5, basis="editorial", label="3 por lado · hasta 5 s cómodos",
          note="La técnica y las 3 repeticiones por lado proceden del original; la pausa de hasta 5 s es una elección editorial, no un tiempo publicado."),
    equipment=("bodyweight", "wall"), capabilities=("standing",), sources=("flexibility",), cue="Mantén el talón posterior en contacto con el suelo.")
MOUNTAIN = _exercise("yoga-standing-mountain", "Montaña: encuentra tu apoyo", [
    "De pie, separa los pies al ancho de la cadera y reparte el apoyo entre ambos.",
    "Alarga suavemente la espalda; deja hombros y brazos relajados.",
    "Respira con naturalidad, sin ponerte rígido. Sal de la postura antes si deja de resultar cómoda."],
    _dose(seconds=30, basis="editorial", label="Hasta 30 s cómodos",
          note="El original propone permanecer mientras resulte cómodo; 30 s es una referencia editorial opcional."),
    capabilities=("standing",), sources=("yoga",), cue="No contengas la respiración.")
TREE = _exercise("yoga-supported-tree-toes", "Árbol con los dedos apoyados", [
    "Colócate junto a una silla firme y sujeta el respaldo.",
    "Acerca un pie al tobillo contrario manteniendo los dedos de ese pie en el suelo.",
    "Respira 3–5 veces, vuelve a apoyar ambos pies y cambia de lado."],
    _dose(breaths_min=3, breaths_max=5, per_side=True, label="3–5 respiraciones por lado"), equipment=("bodyweight", "chair"),
    capabilities=("standing",), sources=("yoga",), cue="Esta variante conserva los dedos en el suelo; no subas el pie a la rodilla.")
CAT_COW = _exercise("yoga-seated-cat-cow", "Gato y vaca en la silla", [
    "Siéntate erguido y lleva los brazos hacia delante a la altura de los hombros.",
    "Redondea suavemente la espalda alta y mira hacia el regazo.",
    "Al comenzar una exhalación, abre los brazos hacia atrás y eleva la mirada cómodamente. Alterna ambas formas al ritmo de tu respiración."],
    _dose(reps=5, basis="editorial", label="5 ciclos suaves a tu ritmo",
          note="Un ciclo incluye ambas formas. Cinco ciclos es una elección editorial; no hay respiraciones de duración obligatoria."),
    equipment=("bodyweight", "chair"), sources=("yoga_chair",), cue="El movimiento empieza con la respiración; no fuerces la espalda.")
SHOULDERS = _exercise("yoga-seated-shoulder-roll", "Círculos suaves de hombros", [
    "Siéntate alto y deja las manos descansando de forma cómoda.",
    "Al exhalar, eleva suavemente los hombros y dibuja un círculo hacia atrás.",
    "Deja caer los hombros con suavidad y repite sin acelerar."],
    _dose(reps=5, label="5 círculos hacia atrás"), equipment=("bodyweight", "chair"),
    sources=("yoga_chair",), cue="Mantén el cuello relajado.")
BRIDGE = _exercise("floor-glute-bridge", "Puente de glúteos", [
    "Túmbate boca arriba con rodillas flexionadas, pies apoyados y espalda en posición neutra.",
    "Activa el abdomen y eleva la pelvis hasta alinear hombros, caderas y rodillas.",
    "Respira 3 veces y baja con control antes de repetir."],
    _dose(reps=5, hold_breaths=3, basis="editorial", label="5 repeticiones · 3 respiraciones arriba",
          note="Selección editorial inicial; conserva las respiraciones de la técnica."),
    equipment=("bodyweight", "mat"), capabilities=("floor_transfer",), sources=("core", "core_start"), cue="No arquees la zona lumbar.")
AB_PRESS = _exercise("floor-single-leg-abdominal-press", "Presión de mano y rodilla", [
    "Boca arriba y con rodillas flexionadas, eleva una pierna hasta formar ángulos rectos en cadera y rodilla.",
    "Apoya la mano del mismo lado en la rodilla. Mano y rodilla presionan una contra otra sin desplazar la pelvis.",
    "Mantén 3 respiraciones, vuelve al apoyo y cambia de lado."],
    _dose(reps=5, per_side=True, hold_breaths=3, basis="editorial", label="5 por lado · 3 respiraciones",
          note="Selección editorial inicial; conserva las respiraciones de la técnica."),
    equipment=("bodyweight", "mat"), capabilities=("floor_transfer",), sources=("core", "core_start"), cue="La espalda conserva su curva natural.")
QUADRUPED_ARM = _exercise("quadruped-arm-reach", "Cuadrupedia: alcanza con un brazo", [
    "Apoya manos y rodillas en la colchoneta; manos bajo hombros y cuello alineado con la espalda.",
    "Activa el abdomen y extiende un brazo hacia delante sin girar el tronco.",
    "Mantén 3 respiraciones, vuelve al apoyo y cambia de brazo. Las dos rodillas siguen en el suelo."],
    _dose(reps=5, per_side=True, hold_breaths=3, basis="editorial", label="5 por brazo · 3 respiraciones",
          note="Selección editorial inicial de la fase de brazo."),
    equipment=("bodyweight", "mat"), capabilities=("floor_transfer", "kneeling"), sources=("core", "core_start"), cue="No combines brazo y pierna en esta variante.")


def _seated_transition(phase: str) -> dict[str, Any]:
    warming = phase == "warmup"
    return _exercise("seated-arrival" if warming else "seated-closing", "Encuentra tu ritmo" if warming else "Termina con calma", [
        "Usa una silla estable y apoya los pies cómodamente.",
        "Siéntate erguido sin ponerte rígido y afloja los hombros.",
        "Respira con naturalidad y prepara un movimiento pequeño." if warming else "Deja que la respiración se calme antes de levantarte sin prisa."],
        _dose(seconds=90, basis="editorial", label="Unos 90 s, a tu ritmo",
              note="Pausa editorial para entrar o salir de la práctica; puedes prolongarla."),
        equipment=("bodyweight", "chair"), capabilities=("sit_to_stand",), sources=("yoga_chair",), cue="No hay que sincronizarse con un reloj.", phase=phase)


def _intermediate(exercise: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(exercise)
    value["dose"] = _dose(reps=8, reps_max=12, sets=2, per_side=exercise["dose"]["per_side"],
                          basis="editorial", label="2 series · 8–12 repeticiones" + (" por brazo" if exercise["dose"]["per_side"] else ""),
                          note="Selección editorial dentro del rango general del CDC; no es una rutina publicada ni una carga calculada.")
    value["source_links"].extend(_links("cdc", "acsm"))
    return value


def _estimate(exercises: list[dict[str, Any]]) -> dict[str, Any]:
    """A reproducible planning estimate, not measured duration or timed prescription."""
    work = [entry for entry in exercises if entry["phase"] == "work"]
    lower = upper = 0
    for entry in work:
        dose = entry["dose"]
        sides = 2 if dose["per_side"] else 1
        sets = dose["sets"]
        if dose["reps_min"] is not None:
            move_low, move_high = (8, 12) if entry["id"] == "yoga-seated-cat-cow" else (4, 6)
            hold_low = dose["hold_seconds"] or 0
            hold_high = dose["hold_seconds_max"] or 0
            if dose["hold_breaths"]:
                hold_low += dose["hold_breaths"] * 4
                hold_high += dose["hold_breaths"] * 6
            lower += sets * sides * dose["reps_min"] * (move_low + hold_low)
            upper += sets * sides * dose["reps_max"] * (move_high + hold_high)
        elif dose["seconds"] is not None:
            lower += sets * sides * dose["seconds"]
            upper += sets * sides * dose["seconds_max"]
        else:
            lower += sets * sides * dose["breaths_min"] * 4
            upper += sets * sides * dose["breaths_max"] * 6
    transitions = len(work) + 1
    set_breaks = sum(entry["dose"]["sets"] - 1 for entry in work)
    components = {
        "warmup": [sum(e["dose"]["seconds"] for e in exercises if e["phase"] == "warmup")] * 2,
        "work": [lower, upper],
        "between_exercises": [max(0, len(work) - 1) * 30, max(0, len(work) - 1) * 90],
        "between_sets": [set_breaks * 60, set_breaks * 120],
        "reading_and_transitions": [transitions * 20, transitions * 40],
        "cooldown": [sum(e["dose"]["seconds"] for e in exercises if e["phase"] == "cooldown")] * 2,
    }
    return {"min": math.ceil(sum(c[0] for c in components.values()) / 60),
            "max": math.ceil(sum(c[1] for c in components.values()) / 60), "kind": "editorial_estimate",
            "source_duration_seconds": None, "components_seconds": components,
            "assumptions": [
                "Incluye calentamiento, cierre, lectura, cambios de posición y pausas.",
                "Para reservar tiempo se estiman 4–6 s por repetición y por respiración; un ciclo de gato-vaca usa 8–12 s. No son tempos obligatorios.",
                "Se reservan 30–90 s entre ejercicios, 60–120 s entre series y 20–40 s por transición. Son supuestos editoriales; el descanso siempre es manual.",
                "Puedes necesitar más tiempo. No aceleres ni elimines descansos para terminar dentro de la reserva.",
            ]}


def _program(id: str, title: str, summary: str, modality: str, level: str,
             locations: tuple[str, ...], exercises: list[dict[str, Any]], *,
             scope: str, extra_capabilities: tuple[str, ...] = (), source_keys: tuple[str, ...] = (),
             ogl: bool = False) -> dict[str, Any]:
    equipment = sorted({item for e in exercises for item in e["equipment"]})
    capabilities = sorted({item for e in exercises for item in e["capabilities"]} | set(extra_capabilities))
    links = {link["url"]: dict(link) for e in exercises for link in e["source_links"]}
    links.update({link["url"]: link for link in _links(*source_keys)})
    return {"id": id, "title": title, "summary": summary, "modality": modality, "level": level,
            "locations": list(locations), "audience": "adults_general", "content_version": CONTENT_VERSION,
            "requirements": {"equipment": equipment, "capabilities": capabilities, "equipment_complete": True},
            "estimated_minutes": _estimate(exercises), "source_duration_seconds": None,
            "exercise_count": sum(e["phase"] == "work" for e in exercises),
            "scope": scope, "exercises": deepcopy(exercises), "source_links": list(links.values()),
            "editorial_source_audit": True, "review_type": "editorial_source_audit", "reviewed_on": CHECKED_ON,
            "review_note": "Selección y redacción editorial de Roxy con ayuda de IA, contrastadas con fuentes. Sin certificación profesional ni evaluación clínica individual.",
            "clinical_approval": False, "prescribed_load": None, "auto_progression": False,
            "rest_policy": "manual", "weight_based_selection": False,
            "progression_note": "Registra lo que realmente hiciste. Repite la sesión con buena técnica; los registros no aumentan por sí solos series, carga o dificultad.",
            "recovery": {"avoid_consecutive_days": modality in {"strength", "core"},
                         "group": "general_strength" if modality in {"strength", "core"} else None,
                         "label": "Deja al menos un día sin entrenar los mismos músculos entre sesiones de fuerza." if modality in {"strength", "core"} else "Elige la frecuencia y las pausas según cómo te sientas."},
            "before_start": ["Revisa los movimientos y confirma que puedes hacer sus posiciones y transiciones.",
                             "Muévete con control y respira. Detén un movimiento si provoca dolor o mareo; si tienes dudas sobre tu salud o una lesión, consulta antes de practicarlo."],
            "attribution": {"text": OGL_ATTRIBUTION, "url": OGL_URL, "adapted": True, "checked_on": CHECKED_ON} if ogl else None,
            "media": None, "technical_demonstration": False}


def _build_programs() -> list[dict[str, Any]]:
    return [
        _program("home-bodyweight-foundations", "Tu fuerza empieza en casa", "Silla, pared y movimientos controlados para dar el primer paso.",
                 "strength", "beginner", ("home", "gym"),
                 [_walk("warmup"), SIT_STAND, MINI_SQUAT, CALF_CHAIR, SIDE_LEG, HIP_EXTENSION, WALL_PUSH, _walk("cooldown")],
                 scope="Iniciación con apoyo para piernas y empuje de brazos. No equivale a un programa completo de fuerza semanal.",
                 source_keys=("acsm", "recovery"), ogl=True),
        _program("home-dumbbell-foundations", "Mancuernas, a tu ritmo", "Piernas, espalda, brazos y empuje en pared, sin banco ni ejercicios en el suelo.",
                 "strength", "beginner", ("home", "gym"),
                 [_walk("warmup"), DB_SQUAT, DB_ROW, WALL_PUSH, DB_CURL, DB_CALF, _walk("cooldown")],
                 scope="Sesión de iniciación con mancuernas. Practica primero las variantes que no conoces; no sustituye una evaluación de técnica ni cubre por sí sola toda la semana.",
                 source_keys=("acsm", "recovery"), ogl=True),
        _program("gym-dumbbell-foundations", "Fuerza en el estudio", "Dos series por movimiento, mancuernas y banco plano para quien ya domina estas variantes.",
                 "strength", "intermediate", ("gym", "home"),
                 [_walk("warmup"), *[_intermediate(e) for e in (DB_SQUAT, DB_PRESS, DB_ROW, DB_CURL, DB_CALF)], _walk("cooldown")],
                 scope="Piernas y torso con experiencia previa. No incluye barra, máquinas ni una promesa de entrenamiento exhaustivo de todos los grupos.",
                 source_keys=("acsm", "recovery")),
        _program("gentle-mobility", "Muévete con más espacio", "Un recorrido tranquilo por cuello, pecho, tronco y pantorrillas, con silla y pared.",
                 "mobility", "beginner", ("home", "gym"),
                 [_seated_transition("warmup"), NECK, CHEST, TWIST, SIDE_BEND, CALF_STRETCH, _seated_transition("cooldown")],
                 scope="Movilidad suave de pie y en silla. No es rehabilitación ni tratamiento de dolor.", ogl=True),
        _program("yoga-gentle-start", "Yoga: una pausa que se mueve", "Posturas de pie y sentadas; respiración, apoyo y pequeños movimientos sin bajar al suelo.",
                 "yoga", "beginner", ("home", "gym"),
                 [_seated_transition("warmup"), MOUNTAIN, TREE, CAT_COW, SHOULDERS, _seated_transition("cooldown")],
                 scope="Selección inicial de cuatro movimientos de yoga con apoyo. No es una clase completa ni una práctica terapéutica."),
        _program("core-foundations", "Control del centro", "Puente, presión abdominal y alcance en cuadrupedia para practicar estabilidad con calma.",
                 "core", "beginner", ("home", "gym"),
                 [_walk("warmup"), BRIDGE, AB_PRESS, QUADRUPED_ARM, _walk("cooldown")],
                 scope="Práctica básica del abdomen y la pelvis en el suelo. Es una sesión de control del centro, no una clase de Pilates.",
                 source_keys=("recovery",)),
    ]


def _validate(programs: list[dict[str, Any]]) -> None:
    ids: set[str] = set()
    for program in programs:
        if not program["id"] or program["id"] in ids:
            raise TrainingContentError("Identidad de rutina no válida.")
        ids.add(program["id"])
        if program["content_version"] != CONTENT_VERSION or program["clinical_approval"] is not False:
            raise TrainingContentError("Revisión de rutina no válida.")
        requirements = program["requirements"]
        if not requirements["equipment_complete"] or not set(requirements["equipment"]) <= EQUIPMENT_LABELS.keys() or not set(requirements["capabilities"]) <= CAPABILITY_LABELS.keys():
            raise TrainingContentError("Requisitos de rutina incompletos.")
        exercises = program["exercises"]
        if len({e["id"] for e in exercises}) != len(exercises) or exercises[0]["phase"] != "warmup" or exercises[-1]["phase"] != "cooldown":
            raise TrainingContentError("Secuencia de rutina no válida.")
        for entry in exercises:
            dose = entry["dose"]
            if len(entry["instructions"]) < 3 or not entry["source_links"] or entry["rest"]["mode"] != "manual":
                raise TrainingContentError("Instrucciones de rutina incompletas.")
            if entry["load"] is not None or entry["media"] is not None or entry["technical_demonstration"] is not False:
                raise TrainingContentError("Carga o demostración no revisada.")
            if not set(entry["equipment"]) <= set(requirements["equipment"]) or not set(entry["capabilities"]) <= set(requirements["capabilities"]):
                raise TrainingContentError("Faltan requisitos de un movimiento.")
            axes = sum(dose[key] is not None for key in ("reps_min", "seconds", "breaths_min"))
            if axes != 1 or dose["basis"] not in {"source", "editorial"} or type(dose["sets"]) is not int or dose["sets"] < 1:
                raise TrainingContentError("Dosis de rutina no válida.")
            for low, high in (("reps_min", "reps_max"), ("seconds", "seconds_max"), ("breaths_min", "breaths_max"), ("hold_seconds", "hold_seconds_max")):
                if dose[low] is not None and (type(dose[low]) is not int or type(dose[high]) is not int or not 0 < dose[low] <= dose[high]):
                    raise TrainingContentError("Rango de dosis no válido.")
        if program["estimated_minutes"] != _estimate(exercises):
            raise TrainingContentError("La estimación ya no corresponde a esta rutina.")


_PROGRAMS = _build_programs()
_validate(_PROGRAMS)
CONTENT_DIGEST = sha256(json.dumps(_PROGRAMS, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
TRAINING_IDS = frozenset(program["id"] for program in _PROGRAMS)


def _ensure_reviewed() -> None:
    _validate(_PROGRAMS)
    digest = sha256(json.dumps(_PROGRAMS, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    if digest != CONTENT_DIGEST:
        raise TrainingContentError("El contenido cambió después de su revisión.")


def training_catalog() -> dict[str, Any]:
    """Return immutable-by-copy public summaries; never inspect personal health data."""
    _ensure_reviewed()
    summaries = [{key: deepcopy(value) for key, value in program.items() if key != "exercises"} for program in _PROGRAMS]
    return {"content_version": CONTENT_VERSION, "content_digest": CONTENT_DIGEST,
            "editorial_source_audit": True, "review_type": "editorial_source_audit", "clinical_approval": False,
            "reviewed_on": CHECKED_ON, "programs": summaries, "total": len(summaries),
            "equipment_labels": dict(EQUIPMENT_LABELS), "capability_labels": dict(CAPABILITY_LABELS)}


def training_detail(program_id: str) -> dict[str, Any]:
    """Return a reviewed exact variant; do not normalize unknown IDs into matches."""
    if not isinstance(program_id, str) or program_id not in TRAINING_IDS:
        raise TrainingContentError("Esta rutina no está disponible.")
    _ensure_reviewed()
    program = next(program for program in _PROGRAMS if program["id"] == program_id)
    return {**deepcopy(program), "content_digest": CONTENT_DIGEST}
