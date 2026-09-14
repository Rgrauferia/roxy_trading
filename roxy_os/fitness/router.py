"""Private preference foundation. No training, clinical or booking endpoints."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, field_validator, model_validator

from .domain import FitnessInputError, preview_readiness
from .repository import (FitnessConflict, FitnessConsentRequired,
                         FitnessStorageUnavailable, PostgresFitnessRepository)
from .schemas import FitnessConsentRequest, FitnessDeleteRequest, FitnessWriteRequest, StrictModel
from .schemas import ConfirmedTrainingRequirements
from .training_content import training_catalog, training_detail, TrainingContentError
from .training_logs import (TrainingLogsRepository, TrainingLog, TrainingLogWrite,
                            TrainingLogConsentWrite, TrainingLogDeleteWrite)
from .training_targets import TrainingTargets
from .activity_plan import (ActivityPlanRepository, ActivityPlanWrite,
                            ActivityConsentWrite, ActivityStatusWrite)
from .measurements import (MeasurementsRepository, Measurement,
                           MeasurementWrite, MeasurementConsentWrite,
                           MeasurementDeleteWrite)
from .sources import fitness_education_links
from .catalog import fitness_catalog, fitness_catalog_entry
from .classes import ClassCatalogUnavailable, class_catalog
from .programs import (ProgramCatalogUnavailable, ProgramNotFound,
                       program_catalog, program_detail)


def repository() -> PostgresFitnessRepository:
    return PostgresFitnessRepository.from_env()


class ActivityProposalRequest(StrictModel):
    expected_version: int = Field(ge=0, le=2**53 - 1)
    start_date: str
    program_ids: list[str] = Field(min_length=1, max_length=3)


class TrainingPreviewRequest(StrictModel):
    program_id: str = Field(min_length=1, max_length=80)
    confirmed_requirements: ConfirmedTrainingRequirements
    start_date: str | None = None
    training_targets: TrainingTargets | None = None
    source_session_id: str | None = None
    expected_logs_version: int | None = Field(default=None, ge=0, le=2**53 - 1)

    @field_validator("source_session_id")
    @classmethod
    def valid_source_id(cls, value):
        if value is not None:
            TrainingLog.valid_id(value)
        return value

    @model_validator(mode="after")
    def source_version(self):
        if (self.source_session_id is None) != (self.expected_logs_version is None):
            raise ValueError("Vuelve a abrir el entrenamiento anterior para revisar su referencia.")
        return self


def create_fitness_router(authenticate: Callable, rate_limit: Callable, same_origin: Callable | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/fitness/v1")

    def personal(request: Request, auth=Depends(authenticate)) -> str:
        rate_limit(request)
        if auth.mode != "member" or not auth.member_id:
            raise HTTPException(403, detail={"code": "personal_login_required", "message": "Entra con tu perfil personal. El acceso compartido del hogar no permite guardar preferencias de Ejercicio."})
        # A cookie can change in another tab. This header only asserts the
        # identity the screen was opened for; it never selects a data owner.
        if request.headers.get("x-roxy-fitness-member") != auth.member_id:
            raise HTTPException(409, detail={"code": "identity_changed", "message": "Cambió la persona conectada. Recarga Roxy Home antes de abrir o modificar Ejercicio."})
        return auth.member_id

    def mutation(request: Request, member: str = Depends(personal)) -> tuple[str, str]:
        # SameSite alone is not a CSRF boundary. No cookie mutation without an
        # exact same-origin browser request and a non-simple explicit header.
        origin = request.headers.get("origin", "")
        origin_ok = same_origin(request) if same_origin else origin == str(request.base_url).rstrip("/")
        if not origin_ok or request.headers.get("x-roxy-fitness-request") != "1":
            raise HTTPException(403, detail={"code": "csrf_rejected", "message": "Abre Ejercicio desde Roxy Home e inténtalo de nuevo."})
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(415, "Usa application/json.")
        key = request.headers.get("idempotency-key", "")
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", key):
            raise HTTPException(422, "Falta una clave de idempotencia válida.")
        return member, key

    def perform(callback):
        try:
            return callback(repository())
        except FitnessStorageUnavailable:
            raise HTTPException(503, detail={"code": "private_storage_unavailable", "message": "No pude confirmar la operación con el almacenamiento privado. Revisa la conexión antes de dar por guardados o eliminados tus cambios; puedes explorar sin guardar."}) from None
        except FitnessConflict as exc:
            raise HTTPException(409, detail={"code": "version_conflict", "message": str(exc)}) from None
        except FitnessConsentRequired as exc:
            raise HTTPException(403, detail={"code": "consent_required", "message": str(exc)}) from None
        except ProgramCatalogUnavailable:
            raise HTTPException(503, detail={"code": "program_catalog_unavailable", "message": "No pude verificar las guías. Tu plan no se ha modificado."}) from None
        except TrainingContentError:
            raise HTTPException(422, detail="No pude verificar esa rutina. Vuelve a abrirla antes de continuar.") from None
        except FitnessInputError as exc:
            raise HTTPException(422, detail=str(exc)) from None

    @router.get("/status")
    def status(request: Request, auth=Depends(authenticate)):
        rate_limit(request)
        return {"release": "foundation-preview", "personal_login": auth.mode == "member" and bool(auth.member_id), "member_id": auth.member_id if auth.mode == "member" else None,
                "storage": repository().configuration_status(), "can_activate_plans": False,
                "clinical_review": "pending", "catalogue": "educational_originals_available_training_review_pending",
                "screening": "not_available", "bookings_enabled": False,
                "wearables_enabled": False, "supplement_recommendations_enabled": False,
                "editorial_routines_enabled": True, "training_logs_enabled": True,
                "education": fitness_education_links()}

    @router.get("/exercises")
    def exercises(request: Request, auth=Depends(authenticate)):
        rate_limit(request)
        return fitness_catalog()

    @router.get("/classes")
    def classes(request: Request, auth=Depends(authenticate)):
        rate_limit(request)
        try:
            return class_catalog()
        except ClassCatalogUnavailable:
            raise HTTPException(503, detail={"code": "class_catalog_unavailable", "message": "No pude verificar las clases. Inténtalo de nuevo; tu plan no se ha modificado."}) from None

    @router.get("/exercises/{exercise_id}")
    def exercise(exercise_id: str, request: Request, auth=Depends(authenticate)):
        rate_limit(request)
        entry = fitness_catalog_entry(exercise_id)
        if entry is None:
            raise HTTPException(404, "No existe esa ficha original.")
        return entry

    def read_program(callback):
        try:
            return callback()
        except ProgramNotFound:
            raise HTTPException(404, detail={"code": "program_not_found", "message": "No existe ese programa."}) from None
        except ProgramCatalogUnavailable:
            raise HTTPException(503, detail={"code": "program_catalog_unavailable", "message": "No pude verificar las guías. Inténtalo de nuevo; no se ha creado ninguna agenda."}) from None

    @router.get("/programs")
    def programs(request: Request, auth=Depends(authenticate)):
        rate_limit(request)
        return read_program(program_catalog)

    @router.get("/programs/{program_id}")
    def program(program_id: str, request: Request, auth=Depends(authenticate)):
        rate_limit(request)
        return read_program(lambda: program_detail(program_id))

    @router.get("/me/profile")
    def profile(member: str = Depends(personal)):
        return perform(lambda repo: repo.snapshot(member))

    @router.get("/training/programs")
    def training_programs(request: Request, auth=Depends(authenticate)):
        rate_limit(request)
        try:
            return training_catalog()
        except TrainingContentError:
            raise HTTPException(503, detail="No pude verificar las rutinas. Inténtalo de nuevo.") from None

    @router.get("/training/programs/{program_id}")
    def training_program(program_id: str, request: Request, auth=Depends(authenticate)):
        rate_limit(request)
        from .training_selection import TRAINING_IDS
        if program_id not in TRAINING_IDS:
            raise HTTPException(404, detail="No existe esa rutina.")
        try:
            return training_detail(program_id)
        except TrainingContentError:
            raise HTTPException(503, detail="No pude verificar la rutina. Inténtalo de nuevo.") from None

    @router.post("/me/training/preview")
    def training_preview(payload: TrainingPreviewRequest, identity=Depends(mutation)):
        from .training_selection import preview_training
        member, _key = identity
        def propose(repo):
            with repo._transaction(member) as cursor:
                profile = repo._read(cursor, member)
                ActivityPlanRepository.available(cursor)
                agenda = ActivityPlanRepository.read(cursor, member)
                if payload.source_session_id is not None:
                    TrainingLogsRepository.available(cursor)
                    logs = TrainingLogsRepository.read(cursor, member)
                    if logs["version"] != payload.expected_logs_version:
                        raise FitnessConflict("El registro anterior cambió. Vuelve a abrirlo antes de preparar otra sesión.")
                    source = next((row for row in logs["logs"] if row["session_id"] == payload.source_session_id), None)
                    if source is None or source["program_id"] != payload.program_id or source["content_version"] != training_detail(payload.program_id)["content_version"]:
                        raise FitnessInputError("No pude verificar ese entrenamiento anterior en tu perfil. Vuelve a elegir una rutina.")
            if not profile["profile"] or (profile["consent"] or {}).get("granted") is not True:
                raise FitnessInputError("Completa y guarda primero tus preferencias y disponibilidad de Ejercicio.")
            result = preview_training(profile["profile"], payload.program_id, payload.confirmed_requirements,
                                      start_date=payload.start_date, existing_plan=agenda["plan"], training_targets=payload.training_targets)
            return {"proposal": result, "profile_version": profile["version"], "activity_plan_version": agenda["version"]}
        return perform(propose)

    @router.patch("/me/profile")
    def save_profile(payload: FitnessWriteRequest, identity=Depends(mutation)):
        member, key = identity
        return perform(lambda repo: repo.save_profile(member, payload.profile, expected_version=payload.expected_version, idempotency_key=key))

    @router.post("/me/consents")
    def consent(payload: FitnessConsentRequest, identity=Depends(mutation)):
        member, key = identity
        return perform(lambda repo: repo.set_consent(member, payload.consent, expected_version=payload.expected_version, idempotency_key=key))

    @router.post("/plans/preview")
    def preview(identity=Depends(mutation)):
        member, _key = identity
        state = perform(lambda repo: repo.snapshot(member))
        return preview_readiness(state["profile"], consent_active=bool((state["consent"] or {}).get("granted")))

    @router.get("/me/data")
    def export(member: str = Depends(personal)):
        return perform(lambda repo: repo.export_data(member))

    @router.delete("/me/data")
    def delete(payload: FitnessDeleteRequest, identity=Depends(mutation)):
        member, key = identity
        return perform(lambda repo: repo.delete_data(member, expected_version=payload.expected_version, idempotency_key=key))

    @router.get("/me/activity-plan")
    def activity_plan(member: str = Depends(personal)):
        return perform(lambda repo: ActivityPlanRepository(repo).snapshot(member))

    @router.post("/me/activity-plan/proposal")
    def activity_proposal(payload: ActivityProposalRequest, identity=Depends(mutation)):
        from .proposals import build_proposal
        member, _key = identity

        def propose(repo):
            with repo._transaction(member) as cursor:
                state = repo._read(cursor, member)
                ActivityPlanRepository.available(cursor)
                agenda = ActivityPlanRepository.read(cursor, member)
            if payload.expected_version != agenda["version"]:
                raise FitnessConflict("Tu plan cambió. Vuelve a cargarlo antes de organizar nuevas fechas.")
            profile = state["profile"]
            consent = state["consent"] or {}
            if not profile or consent.get("granted") is not True:
                raise FitnessInputError("Completa y guarda primero tus preferencias y disponibilidad de Ejercicio.")
            plan = agenda["plan"] or {}
            if plan.get("sessions") and plan["timezone"] != profile["timezone"]:
                raise FitnessInputError("La zona horaria de tus preferencias y tu plan es distinta. Ajusta las preferencias al horario de tu plan antes de proponer fechas.")
            result = build_proposal(profile, payload.start_date, payload.program_ids,
                                    datetime.now(timezone.utc), existing_sessions=plan.get("sessions", []))
            return {"proposal": result, "profile_version": state["version"],
                    "activity_plan_version": agenda["version"]}

        return perform(propose)

    @router.put("/me/activity-plan")
    def save_activity_plan(payload: ActivityPlanWrite, identity=Depends(mutation)):
        member, key = identity
        options = {"expected_profile_version": payload.expected_profile_version} if payload.expected_profile_version is not None else {}
        return perform(lambda repo: ActivityPlanRepository(repo).save(member, payload.plan, expected_version=payload.expected_version, idempotency_key=key, **options))

    @router.post("/me/activity-plan/consent")
    def activity_consent(payload: ActivityConsentWrite, identity=Depends(mutation)):
        member, key = identity
        return perform(lambda repo: ActivityPlanRepository(repo).consent(member, payload.consent, expected_version=payload.expected_version, idempotency_key=key))

    @router.patch("/me/activity-plan/sessions/{session_id}")
    def activity_status(session_id: str, payload: ActivityStatusWrite, identity=Depends(mutation)):
        member, key = identity
        try:
            from .activity_plan import ActivitySession
            ActivitySession.valid_id(session_id)
        except ValueError:
            raise HTTPException(422, detail="Identificador de actividad inválido.") from None
        return perform(lambda repo: ActivityPlanRepository(repo).set_status(member, session_id, payload.status, expected_version=payload.expected_version, idempotency_key=key))

    @router.get("/me/activity-plan/data")
    def export_activity_plan(member: str = Depends(personal)):
        return perform(lambda repo: ActivityPlanRepository(repo).export_data(member))

    @router.delete("/me/activity-plan/data")
    def delete_activity_plan(payload: FitnessDeleteRequest, identity=Depends(mutation)):
        member, key = identity
        return perform(lambda repo: ActivityPlanRepository(repo).delete_data(member, expected_version=payload.expected_version, idempotency_key=key))

    @router.get("/me/measurements")
    def measurements(member: str = Depends(personal)):
        return perform(lambda repo: MeasurementsRepository(repo).snapshot(member))

    @router.put("/me/measurements")
    def save_measurement(payload: MeasurementWrite, identity=Depends(mutation)):
        member, key = identity
        return perform(lambda repo: MeasurementsRepository(repo).save(member, payload.measurement, expected_version=payload.expected_version, idempotency_key=key))

    @router.post("/me/measurements/consent")
    def measurement_consent(payload: MeasurementConsentWrite, identity=Depends(mutation)):
        member, key = identity
        return perform(lambda repo: MeasurementsRepository(repo).consent(member, payload.consent, expected_version=payload.expected_version, idempotency_key=key))

    @router.get("/me/measurements/export")
    def export_measurements(member: str = Depends(personal)):
        return perform(lambda repo: MeasurementsRepository(repo).export_data(member))

    @router.delete("/me/measurements/{measurement_id}")
    def delete_measurement(measurement_id: str, payload: MeasurementDeleteWrite, identity=Depends(mutation)):
        member, key = identity
        try:
            Measurement.valid_id(measurement_id)
        except ValueError:
            raise HTTPException(422, detail="Identificador de medición inválido.") from None
        return perform(lambda repo: MeasurementsRepository(repo).remove(member, measurement_id, expected_version=payload.expected_version, idempotency_key=key))

    @router.delete("/me/measurements")
    def delete_measurements(payload: MeasurementDeleteWrite, identity=Depends(mutation)):
        member, key = identity
        return perform(lambda repo: MeasurementsRepository(repo).delete_data(member, expected_version=payload.expected_version, idempotency_key=key))

    @router.get("/me/training-logs")
    def training_logs(member: str = Depends(personal)):
        return perform(lambda repo: TrainingLogsRepository(repo).snapshot(member))

    @router.get("/me/training-progress")
    def training_progress(member: str = Depends(personal)):
        from .training_progress import training_progress as summarize_progress
        def summarize(repo):
            snapshot = TrainingLogsRepository(repo).snapshot(member)
            try:
                return summarize_progress(snapshot)
            except TrainingContentError:
                raise HTTPException(503, detail="No pude verificar las rutinas de tu historial. Tus registros no se han modificado.") from None
        return perform(summarize)

    @router.put("/me/training-logs")
    def save_training_log(payload: TrainingLogWrite, identity=Depends(mutation)):
        member, key = identity
        return perform(lambda repo: TrainingLogsRepository(repo).save(member, payload.log, expected_version=payload.expected_version, idempotency_key=key))

    @router.post("/me/training-logs/consent")
    def training_log_consent(payload: TrainingLogConsentWrite, identity=Depends(mutation)):
        member, key = identity
        return perform(lambda repo: TrainingLogsRepository(repo).consent(member, payload.consent, expected_version=payload.expected_version, idempotency_key=key))

    @router.get("/me/training-logs/export")
    def export_training_logs(member: str = Depends(personal)):
        return perform(lambda repo: TrainingLogsRepository(repo).export_data(member))

    @router.delete("/me/training-logs/{session_id}")
    def delete_training_log(session_id: str, payload: TrainingLogDeleteWrite, identity=Depends(mutation)):
        member, key = identity
        try:
            TrainingLog.valid_id(session_id)
        except ValueError:
            raise HTTPException(422, detail="Identificador de sesión inválido.") from None
        return perform(lambda repo: TrainingLogsRepository(repo).remove(member, session_id, expected_version=payload.expected_version, idempotency_key=key))

    @router.delete("/me/training-logs")
    def delete_training_logs(payload: TrainingLogDeleteWrite, identity=Depends(mutation)):
        member, key = identity
        return perform(lambda repo: TrainingLogsRepository(repo).delete_data(member, expected_version=payload.expected_version, idempotency_key=key))

    return router
