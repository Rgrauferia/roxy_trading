"""Reviewed pointers to original exercise classes, without media redistribution.

This is an editorial discovery directory. It never assigns a workout, infers
personal suitability or calls a provider. Unknown metadata stays unknown.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


CATALOG_PATH = Path(__file__).resolve().parents[2] / "data/home_fitness_classes_209.json"
CATALOG_VERSION = "fitness-original-classes-209-v1"
CHECKED_ON = "2026-09-14"
MAX_BYTES = 96 * 1024
MODALITIES = frozenset({"yoga", "pilates", "cardio", "strength", "calisthenics", "mobility", "balance"})
LEVELS = frozenset({"beginner", "basic_experience", "basic_fitness", "all_levels"})
NHS_ROOT = "https://www.nhs.uk/live-well/exercise/"
MAYO_ROOT = "https://www.mayoclinic.org/healthy-lifestyle/fitness/multimedia/"
NHS_SOURCES = {
    "nhs-yoga-vinyasa": "pilates-and-yoga/yoga-with-lj/",
    "nhs-pilates-beginners": "pilates-and-yoga/pilates-for-beginners/",
    "nhs-pilates-pyjama": "pilates-and-yoga/pyjama-pilates/",
    "nhs-pilates-chair": "pilates-and-yoga/chair-based-pilates-exercise-video/",
    "nhs-aerobics-beginners": "aerobic-exercises/aerobics-for-beginners/",
    "nhs-wake-up": "aerobic-exercises/wake-up-workout/",
    "nhs-dance-la-bomba": "aerobic-exercises/dance-la-bomba/",
    "nhs-belly-dance": "aerobic-exercises/belly-dancing-for-beginners/",
    "nhs-strength-abs": "strength-and-resistance/body-blast-abs/",
    "nhs-strength-arms": "strength-and-resistance/body-blast-arms/",
    "nhs-strength-legs": "strength-and-resistance/body-blast-legs/",
    "nhs-strength-bums": "strength-and-resistance/body-blast-bums/",
    "nhs-strength-waist": "strength-and-resistance/body-blast-waist/",
    "nhs-warm-up": "strength-and-resistance/body-blast-warm-up/",
    "nhs-cool-down": "strength-and-resistance/body-blast-cool-down/",
}
MAYO_SOURCES = {
    "mayo-squat": "squat/vid-20084663",
    "mayo-modified-pushup": "modified-pushup/vid-20084674",
    "mayo-step-up": "step-up/vid-20084661",
}
SOURCE_URLS = {**{key: NHS_ROOT + path for key, path in NHS_SOURCES.items()},
               **{key: MAYO_ROOT + path for key, path in MAYO_SOURCES.items()}}
# Updated only with a reviewed directory edit. Formatting changes are harmless;
# changed facts, new claims or injected fields require another release review.
REVIEWED_DATA_SHA256 = "ee211a184d5a5c28e36f608439c5996a56101e9b5c72ed0b22f43d112b2dd920"


class ClassCatalogUnavailable(ValueError):
    """Incomplete or changed source facts must not be displayed as verified."""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _constant(_value):
    raise ValueError("non_finite_number")


def _text(value, maximum=1200):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or re.search(r"[\x00-\x1f\x7f<>]", value)):
        raise ValueError("invalid_text")
    return value


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("invalid_date")
    return date.fromisoformat(value)


def _validate(row):
    if not isinstance(row, dict) or row.get("id") not in SOURCE_URLS:
        raise ValueError("unknown_source")
    if row.get("source_url") != SOURCE_URLS[row["id"]]:
        raise ValueError("changed_source")
    parsed = urlsplit(row["source_url"])
    if parsed.scheme != "https" or parsed.query or parsed.fragment:
        raise ValueError("invalid_source_url")
    nhs = row["id"] in NHS_SOURCES
    if (row.get("publisher") != ("NHS" if nhs else "Mayo Clinic")
            or row.get("creator") != ("InstructorLive" if nhs else "Mayo Clinic")
            or row.get("format") != ("class" if nhs else "technique")
            or row.get("language") != "en"):
        raise ValueError("changed_source_identity")
    if (row.get("clinical_approval") is not False
            or row.get("can_activate_plans") is not False
            or row.get("embed_url") is not None
            or row.get("media_mode") != "external_link"):
        raise ValueError("unsupported_capability")
    for field in ("title_es", "title_original", "description_es"):
        _text(row.get(field))
    if row.get("checked_on") != CHECKED_ON:
        raise ValueError("unreviewed_date")
    dated_fields = [row.get("source_reviewed_on"), row.get("source_updated_on")]
    if not any(dated_fields) or any(_date(value) > _date(CHECKED_ON) for value in dated_fields if value is not None):
        raise ValueError("invalid_source_date")
    modalities = row.get("modalities")
    if (not isinstance(modalities, list) or not 1 <= len(modalities) <= 3
            or any(not isinstance(value, str) or value not in MODALITIES for value in modalities)
            or len(set(modalities)) != len(modalities) or row.get("modality") != modalities[0]):
        raise ValueError("invalid_modality")
    if row.get("level") is not None and row["level"] not in LEVELS:
        raise ValueError("invalid_level")
    duration = row.get("duration_minutes")
    if duration is not None and (type(duration) is not int or not 1 <= duration <= 180):
        raise ValueError("invalid_duration")
    if row.get("duration_note_es") is not None:
        _text(row["duration_note_es"])
    if duration is None and not row.get("duration_note_es"):
        raise ValueError("missing_duration_explanation")
    equipment = row.get("equipment")
    if not isinstance(equipment, list) or len(equipment) > 6 or row.get("equipment_complete") is not False:
        raise ValueError("unverified_equipment")
    for item in equipment:
        if not isinstance(item, dict) or item.get("requirement") not in {"required", "optional"}:
            raise ValueError("invalid_equipment")
        _text(item.get("name_es"), 200)
    notes = row.get("source_notes_es")
    if not isinstance(notes, list) or len(notes) > 4:
        raise ValueError("invalid_source_notes")
    for note in notes:
        _text(note)
    return deepcopy(row)


def class_catalog():
    """Return all verified discovery rows or fail, never a partial fake success."""
    try:
        with CATALOG_PATH.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("catalogue_too_large")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=_constant)
        canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if sha256(canonical).hexdigest() != REVIEWED_DATA_SHA256:
            raise ValueError("unreviewed_directory_change")
        if (data.get("product") != "roxy-home" or type(data.get("version")) is not int
                or data["version"] != 1 or data.get("checked_on") != CHECKED_ON):
            raise ValueError("invalid_catalogue")
        rows = data.get("classes")
        if not isinstance(rows, list) or len(rows) != len(SOURCE_URLS):
            raise ValueError("incomplete_catalogue")
        validated = [_validate(row) for row in rows]
        if {row["id"] for row in validated} != set(SOURCE_URLS):
            raise ValueError("duplicate_source")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError, RecursionError, OverflowError):
        raise ClassCatalogUnavailable("fitness_class_catalog_unavailable") from None
    return {
        "version": CATALOG_VERSION,
        "checked_on": CHECKED_ON,
        "status": "external_original_classes",
        "classes": validated,
        "count": len(validated),
        "class_count": sum(row["format"] == "class" for row in validated),
        "technique_count": sum(row["format"] == "technique" for row in validated),
        "clinical_approval": False,
        "can_activate_plans": False,
        "notice_es": "Clases y demostraciones generales para explorar. La edad o el peso por sí solos no indican qué ejercicio es adecuado para una persona.",
        "media_notice_es": "Se abren en la web original, en inglés. Roxy no aloja estos vídeos ni cambia la voz de sus instructores.",
        "safety_notice_es": "Revisa las indicaciones de cada fuente. Si tienes una lesión, una condición de salud, embarazo o dudas sobre tu nivel, consulta antes de empezar. Detente si aparece dolor o malestar.",
        "metadata_notice_es": "Títulos y descripciones editoriales en español; no constituyen una traducción del vídeo ni una recomendación personal. Material no indicado significa sin confirmar.",
        "metadata_attribution": "Contains public sector information licensed under the Open Government Licence v3.0.",
        "metadata_license_url": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
    }
