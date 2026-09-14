"""Optional, explicitly chosen goals for a later session, never actual results.

The numeric bounds match manually entered training records; they are storage
bounds, not a recommendation, progression rule or a source-derived dose.
This module deliberately does not import activity_plan or training_logs, so the
agenda can validate target structure without a circular dependency or a read.
"""
from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, field_validator, model_validator

from .domain import FitnessInputError
from .repository import FitnessConflict, FitnessStorageUnavailable
from .schemas import StrictModel


def _finite_number(value):
    try:
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError("Introduce un número finito para el objetivo, sin texto ni valores especiales.")
    return value


class TrainingTargetLoad(StrictModel):
    value: float = Field(ge=0, le=2500)
    unit: Literal["kg", "lb"]

    @field_validator("value", mode="before")
    @classmethod
    def finite(cls, value):
        return _finite_number(value)


class TrainingTargetSet(StrictModel):
    reps: int | None = Field(default=None, ge=1, le=10000)
    seconds: float | None = Field(default=None, gt=0, le=86400)
    load: TrainingTargetLoad | None = None

    @field_validator("seconds", mode="before")
    @classmethod
    def finite(cls, value):
        return None if value is None else _finite_number(value)

    @model_validator(mode="after")
    def one_axis(self):
        if (self.reps is None) == (self.seconds is None):
            raise ValueError("Cada serie elegida necesita repeticiones o segundos, sin combinar ambos.")
        return self


class TrainingTargetExercise(StrictModel):
    exercise_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    sets: list[TrainingTargetSet] = Field(min_length=1, max_length=20)


TrainingTargets = Annotated[list[TrainingTargetExercise], Field(min_length=1, max_length=100)]
_TARGETS = TypeAdapter(TrainingTargets)


def _work_exercises(program_id, content_version):
    from .training_content import training_detail, TrainingContentError
    try:
        detail = training_detail(program_id)
    except TrainingContentError:
        raise FitnessInputError("Esta rutina ya no está disponible. Vuelve a elegirla antes de guardar objetivos.") from None
    if content_version != detail["content_version"]:
        raise FitnessConflict("Los detalles de la rutina cambiaron. Revísala antes de elegir los objetivos de otra sesión.")
    exercises = [item for item in detail["exercises"] if item["phase"] == "work"]
    expected = {item["id"]: item for item in exercises}
    if not expected or len(expected) != len(exercises) or any(
            item["tracking_unit"] not in {"reps", "seconds"} for item in exercises):
        raise FitnessStorageUnavailable()
    return expected


def validate_training_targets(program_id, content_version, targets):
    """Return chosen targets in content order; absence stays absent.

    Structure can be parsed without loading today's content for historical
    agenda reads. Call this function only for new or changed session targets.
    Partial exercise coverage is deliberate: an unchosen target has no value.
    """
    if targets is None:
        return None
    parsed = _TARGETS.validate_python(targets)
    chosen = {item.exercise_id: item for item in parsed}
    if len(chosen) != len(parsed):
        raise FitnessInputError("No repitas ejercicios en los objetivos de la sesión.")
    expected = _work_exercises(program_id, content_version)
    if not set(chosen).issubset(expected):
        raise FitnessInputError("Elige objetivos solo para los ejercicios de trabajo de esta rutina.")
    for exercise_id, target in chosen.items():
        definition = expected[exercise_id]
        axis = definition["tracking_unit"]
        if any(getattr(series, axis) is None for series in target.sets):
            raise FitnessInputError("Usa la unidad indicada para cada objetivo: repeticiones o segundos.")
        if definition.get("load_recordable") is not True and any(series.load is not None for series in target.sets):
            raise FitnessInputError("Este ejercicio no admite carga añadida en sus objetivos.")
    return [chosen[exercise_id].model_dump(mode="json") for exercise_id in expected if exercise_id in chosen]


def targets_from_log(log):
    """Project a member-authorized saved record for an explicit repeat preview.

    The caller must retrieve and authorize the record and its version. Original
    entered units are retained; stored normalizations and completion metadata
    are not goals. This function never mutates the log, records a result, fills
    omitted exercises from source doses, or increases any entered value.
    """
    if not isinstance(log, dict):
        raise FitnessInputError("No se pudo leer el registro elegido para repetir la sesión.")
    expected = _work_exercises(log.get("program_id"), log.get("content_version"))
    exercises = log.get("exercises")
    if not isinstance(exercises, list) or len(exercises) != len(expected) or any(
            not isinstance(item, dict) or not isinstance(item.get("exercise_id"), str) for item in exercises):
        raise FitnessInputError("El registro debe corresponder a los ejercicios de esta rutina.")
    if {item["exercise_id"] for item in exercises} != set(expected):
        raise FitnessInputError("El registro debe corresponder a los ejercicios de esta rutina.")
    chosen = []
    for item in exercises:
        if type(item.get("skipped")) is not bool or not isinstance(item.get("sets"), list):
            raise FitnessInputError("El registro necesita indicar qué ejercicios se realizaron u omitieron.")
        if item["skipped"]:
            if item["sets"]:
                raise FitnessInputError("Un ejercicio omitido no puede contener series realizadas.")
            continue
        if any(not isinstance(series, dict) or not set(series).issubset({"reps", "seconds", "load", "load_kg"})
               for series in item["sets"]):
            raise FitnessInputError("Las series del registro elegido no son válidas.")
        chosen.append({"exercise_id": item["exercise_id"], "sets": [
            {key: value for key, value in series.items() if key != "load_kg"}
            for series in item["sets"]]})
    return validate_training_targets(log["program_id"], log["content_version"], chosen) if chosen else None
