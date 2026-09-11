"""Private preference foundation. No training, clinical or booking endpoints."""
from __future__ import annotations

import re
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request

from .domain import FitnessInputError, preview_readiness
from .repository import (FitnessConflict, FitnessConsentRequired,
                         FitnessStorageUnavailable, PostgresFitnessRepository)
from .schemas import FitnessConsentRequest, FitnessDeleteRequest, FitnessWriteRequest
from .sources import fitness_education_links
from .catalog import fitness_catalog, fitness_catalog_entry
from .programs import (ProgramCatalogUnavailable, ProgramNotFound,
                       program_catalog, program_detail)


def repository() -> PostgresFitnessRepository:
    return PostgresFitnessRepository.from_env()


def create_fitness_router(authenticate: Callable, rate_limit: Callable) -> APIRouter:
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
        if origin != str(request.base_url).rstrip("/") or request.headers.get("x-roxy-fitness-request") != "1":
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
                "education": fitness_education_links()}

    @router.get("/exercises")
    def exercises(request: Request, auth=Depends(authenticate)):
        rate_limit(request)
        return fitness_catalog()

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

    return router
