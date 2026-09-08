"""Deterministic preparation and timing helpers, NOT clinically approved rules."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from .schemas import FitnessProfileInput


class FitnessInputError(ValueError):
    pass


def _seconds(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 86400:
        raise FitnessInputError(f"{label}: duración inválida.")
    return float(value)


@dataclass(frozen=True)
class ExerciseTiming:
    exercise_id: str
    sets: int
    work_seconds_per_set_per_side: float
    rest_seconds_between_sets: float
    unilateral: bool = False
    side_transition_seconds: float = 0
    equipment_adjustment_seconds: float = 0

    def total_seconds(self) -> float:
        if not isinstance(self.exercise_id, str) or not self.exercise_id.strip():
            raise FitnessInputError("El movimiento necesita un ID real.")
        if isinstance(self.sets, bool) or not isinstance(self.sets, int) or not 1 <= self.sets <= 100:
            raise FitnessInputError("Número de series inválido.")
        if not isinstance(self.unilateral, bool):
            raise FitnessInputError("La lateralidad debe ser explícita.")
        work = _seconds(self.work_seconds_per_set_per_side, "Trabajo")
        if work == 0:
            raise FitnessInputError("Falta la duración de trabajo.")
        rest = _seconds(self.rest_seconds_between_sets, "Descanso")
        side = _seconds(self.side_transition_seconds, "Cambio de lado")
        setup = _seconds(self.equipment_adjustment_seconds, "Ajuste")
        if not self.unilateral and side:
            raise FitnessInputError("Un movimiento bilateral no tiene cambio de lado.")
        sides = 2 if self.unilateral else 1
        return self.sets * work * sides + (self.sets - 1) * rest + self.sets * (sides - 1) * side + setup


def validate_session_duration(
    exercises: Sequence[ExerciseTiming], *, available_seconds: float,
    warmup_seconds: float = 0, cooldown_seconds: float = 0,
    transition_seconds: float = 0, travel_seconds: float = 0,
    trusted_catalog: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pure arithmetic for reviewed inputs; availability excludes travel.

    Caller supplies only its server-controlled, current, reviewed/right-valid catalog.
    This helper cannot approve a catalog, a dose, technique, recovery or a person.
    """
    catalog = trusted_catalog or {}
    if not exercises or len(exercises) > 100:
        raise FitnessInputError("La sesión necesita movimientos revisados.")
    for movement in exercises:
        entry = catalog.get(movement.exercise_id)
        if not isinstance(entry, dict) or entry.get("review_status") != "approved" or entry.get("rights_valid") is not True or entry.get("active") is not True:
            raise FitnessInputError("Movimiento no autorizado o pendiente de revisión.")
    available = _seconds(available_seconds, "Ventana disponible")
    total = (_seconds(warmup_seconds, "Preparación") + sum(item.total_seconds() for item in exercises)
             + max(0, len(exercises) - 1) * _seconds(transition_seconds, "Transiciones")
             + _seconds(cooldown_seconds, "Cierre"))
    travel = _seconds(travel_seconds, "Desplazamiento")
    return {"valid_duration": total <= available, "training_seconds": total,
            "travel_seconds": travel, "calendar_seconds": total + travel,
            "available_seconds": available, "overrun_seconds": max(0, total - available),
            "clinical_approval": False}


def preview_readiness(profile: FitnessProfileInput | dict[str, Any] | None, *, consent_active: bool, **_unused: Any) -> dict[str, Any]:
    """The release has no approved protocols. It can never produce a routine.

    No browser-supplied flags, source rows or AI response can override this gate.
    """
    common = {"can_activate": False, "medical_clearance": False, "sessions": [],
              "prescriptions": [], "clinical_rule_version": None, "data_origin": "self_declared"}
    if not consent_active:
        return {**common, "status": "needs_more_information", "reason_code": "consent_required",
                "message": "Primero decide si quieres guardar preferencias personales de Ejercicio."}
    parsed = FitnessProfileInput.model_validate(profile) if isinstance(profile, dict) else profile
    missing = []
    if parsed is None:
        missing = ["profile"]
    else:
        missing = [key for key in ("age_band", "primary_goal", "session_minutes", "availability", "locations") if not getattr(parsed, key)]
    if missing:
        return {**common, "status": "needs_more_information", "reason_code": "profile_incomplete",
                "missing_fields": missing, "message": "Puedes explorar la sección. Faltan preferencias para preparar un borrador."}
    return {**common, "status": "needs_professional_review", "reason_code": "content_review_required",
            "message": "Preferencias guardadas. El catálogo, el cribado y las plantillas aún necesitan revisión profesional antes de ofrecer un entrenamiento. No es una autorización médica."}
