"""Fixed source programmes for reading and voluntary calendar organisation.

This catalogue neither screens a person nor prescribes or activates training.
It does not call providers, store member data or invent missing exercise doses.
Source extraction hashes protect correspondence, not clinical suitability.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re


CATALOG_PATH = Path(__file__).resolve().parents[2] / "data/home_fitness_source_programs_192.json"
CATALOG_VERSION = "fitness-source-programs-192-v1"
MAX_BYTES = 512 * 1024
MAX_SOURCE_BYTES = 96 * 1024
LICENSE_URL = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
TERMS_URL = "https://www.nhs.uk/our-policies/terms-and-conditions/"
SOURCE_PROGRAMS = {
    "gentle-strength": {
        "source_url": "https://www.nhs.uk/live-well/exercise/strength-exercises/",
        "source_version": "2024-02-28", "title_en": "Strength exercises", "exercise_count": 7,
    },
    "gentle-balance": {
        "source_url": "https://www.nhs.uk/live-well/exercise/balance-exercises/",
        "source_version": "2023-11-07", "title_en": "Balance exercises", "exercise_count": 5,
    },
    "gentle-flexibility": {
        "source_url": "https://www.nhs.uk/live-well/exercise/flexibility-exercises/",
        "source_version": "2023-11-20", "title_en": "Flexibility exercises", "exercise_count": 4,
    },
}


class ProgramCatalogUnavailable(ValueError):
    """Missing or invalid release content is never an empty successful guide."""


class ProgramNotFound(ValueError):
    """An unknown exact ID is not replaced with a similar programme."""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _constant(_value):
    raise ValueError("non_finite_number")


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non_finite_number")
    return result


def _json(raw):
    return json.loads(raw, object_pairs_hook=_object, parse_constant=_constant, parse_float=_float)


def _text(value, maximum=6000):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value)
            or re.search(r"</?[A-Za-z][^>]*>", value)):
        raise ValueError("invalid_plain_text")
    return value


def _lines(value, *, optional=False):
    if not isinstance(value, list) or not (0 if optional else 1) <= len(value) <= 40:
        raise ValueError("invalid_lines")
    for line in value:
        _text(line)
    return value


def _slug(value):
    if not isinstance(value, str) or len(value) > 100 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
        raise ValueError("invalid_id")
    return value


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("invalid_hash")
    return value


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("invalid_date")
    return date.fromisoformat(value)


def _validate(row):
    if not isinstance(row, dict):
        raise ValueError("invalid_programme")
    program_id = _slug(row.get("id"))
    expected = SOURCE_PROGRAMS.get(program_id)
    if expected is None:
        raise ValueError("unreviewed_programme")
    for field in ("source_url", "source_version", "title_en"):
        if row.get(field) != expected[field]:
            raise ValueError("source_identity_mismatch")
    if row.get("license_url") != LICENSE_URL or row.get("terms_url") != TERMS_URL:
        raise ValueError("source_rights_mismatch")
    if _date(row.get("checked_on")) < _date(row["source_version"]):
        raise ValueError("check_predates_source")
    for field in ("title_es", "attribution_en", "attribution_es", "frequency_en", "frequency_es"):
        _text(row.get(field), 2000)
    for field in ("intro_en", "intro_es"):
        _lines(row.get(field))
    if len(row["intro_en"]) != len(row["intro_es"]):
        raise ValueError("incomplete_translation")
    _lines(row.get("notes_es", []), optional=True)
    _hash(row.get("source_html_sha256"))
    raw = row.get("raw_source")
    if not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("invalid_source_extract")
    if hashlib.sha256(raw.encode("utf-8")).hexdigest() != _hash(row.get("source_sha256")):
        raise ValueError("source_hash_mismatch")
    # Reject any attempt to turn an educational source row into a clinical gate.
    for field in ("active_training", "can_activate_training", "can_activate_plans", "clinical_approval", "can_persist"):
        if field in row and row[field] is not False:
            raise ValueError("unsupported_activation_claim")
    for field in ("duration_seconds", "rest_seconds", "progression"):
        if field in row and row[field] is not None:
            raise ValueError("unsupported_dose")
    exercises = row.get("exercises")
    if not isinstance(exercises, list) or len(exercises) != expected["exercise_count"]:
        raise ValueError("incomplete_programme")
    original_exercises, public_exercises, seen = [], [], set()
    for exercise in exercises:
        if not isinstance(exercise, dict):
            raise ValueError("invalid_exercise")
        exercise_id = _slug(exercise.get("id"))
        if exercise_id in seen:
            raise ValueError("duplicate_exercise")
        seen.add(exercise_id)
        for field in ("name_en", "name_es"):
            _text(exercise.get(field), 300)
        for field in ("instructions_en", "instructions_es"):
            _lines(exercise.get(field))
        if len(exercise["instructions_en"]) != len(exercise["instructions_es"]):
            raise ValueError("incomplete_translation")
        for field in ("duration_seconds", "rest_seconds", "sets", "reps", "weight_kg", "weight_lb"):
            if field in exercise and exercise[field] is not None:
                raise ValueError("unsupported_structured_dose")
        original_exercises.append({key: exercise[key] for key in ("id", "name_en", "instructions_en")})
        public_exercises.append({key: deepcopy(exercise[key]) for key in ("id", "name_en", "name_es", "instructions_en", "instructions_es")})
    original = {"title_en": row["title_en"], "intro_en": row["intro_en"],
                "frequency_en": row["frequency_en"], "exercises": original_exercises}
    if _json(raw) != original:
        raise ValueError("source_extract_mismatch")
    public = {key: deepcopy(row[key]) for key in (
        "id", "title_en", "title_es", "source_url", "source_version", "checked_on",
        "source_sha256", "source_html_sha256", "frequency_en", "frequency_es",
        "intro_en", "intro_es", "attribution_en", "attribution_es", "license_url", "terms_url",
    )}
    public.update(exercises=public_exercises, exercise_count=len(exercises),
                  notes_es=deepcopy(row.get("notes_es", [])), duration_seconds=None)
    return public


def _catalog():
    try:
        with CATALOG_PATH.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("catalogue_too_large")
        data = _json(raw.decode("utf-8"))
        if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
            raise ValueError("invalid_version")
        rows = data.get("programs")
        if not isinstance(rows, list) or not 1 <= len(rows) <= len(SOURCE_PROGRAMS):
            raise ValueError("invalid_selection")
        programs = [_validate(row) for row in rows]
        for field in ("id", "title_en", "title_es", "source_url", "source_sha256"):
            if len({row[field].casefold() for row in programs}) != len(programs):
                raise ValueError("duplicate_selection")
        return programs
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise ProgramCatalogUnavailable("fitness_program_catalog_unavailable") from None


def _metadata():
    return {"version": CATALOG_VERSION, "status": "education_only", "active_training": False,
            "can_activate_plans": False, "clinical_approval": False, "can_persist": False,
            "notice_es": "Programas publicados para lectura y organización voluntaria. No son una prescripción de Roxy ni una evaluación de seguridad personal.",
            "translation_notice_es": "El texto en español es una adaptación de Roxy bajo OGL; no una traducción aprobada por NHS.",
            "media_notice_es": "Esta selección no incorpora fotos ni vídeos; no se sustituye una demostración por otra variante."}


def program_catalog():
    """Return small complete summaries; no personal or external side effects."""
    fields = ("id", "title_en", "title_es", "source_url", "source_version", "checked_on",
              "source_sha256", "frequency_en", "frequency_es", "exercise_count",
              "license_url", "terms_url", "duration_seconds")
    programs = [{key: row[key] for key in fields} for row in _catalog()]
    return {"programs": programs, "total": len(programs), **_metadata()}


def program_detail(program_id):
    """Resolve only exact approved source identities, without activating training."""
    if not isinstance(program_id, str) or program_id not in SOURCE_PROGRAMS:
        raise ProgramNotFound("fitness_program_not_found")
    row = next((row for row in _catalog() if row["id"] == program_id), None)
    if row is None:
        raise ProgramNotFound("fitness_program_not_found")
    return {"program": row, **_metadata()}
