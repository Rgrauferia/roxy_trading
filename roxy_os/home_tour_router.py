"""Member-bound tutorial state and a fixed-script official audio endpoint."""
from typing import Any, Callable
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from roxy_os.home_tour import catalogue, normalize_progress, speech_for
from roxy_os.home_recipe_profile import RecipeProfileConflictError


class TourProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    progress: dict[str, Any]


class TourSpeech(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chapter: str = Field(min_length=1, max_length=40)


def create_home_tour_router(authenticate: Callable, account_store: Callable,
                            same_origin: Callable, rate_limit: Callable, voice_response: Callable):
    router = APIRouter(prefix="/v1/home-tour")

    def member(request, auth, mutation=False):
        rate_limit(request)
        if getattr(auth, "mode", None) != "member":
            raise HTTPException(403, "Entra con tu perfil personal para abrir la guía.")
        current = account_store().member(auth.member_id)
        if (not current or current["id"] != request.headers.get("x-roxy-member-id")
                or str(current.get("session_version", 0)) != request.headers.get("x-roxy-session-version")
                or current.get("session_version", 0) != auth.session_version):
            raise HTTPException(409, "Tu sesión cambió. Vuelve a abrir la guía.")
        if mutation and not same_origin(request):
            raise HTTPException(403, "Abre la guía desde Roxy Home.")
        return current

    @router.get("")
    def read(request: Request, response: Response, auth=Depends(authenticate)):
        current = member(request, auth)
        response.headers["Cache-Control"] = "private, no-store"
        return {**catalogue(), **account_store().get_home_tour(current["id"])}

    @router.put("")
    def save(payload: TourProgress, request: Request, response: Response, auth=Depends(authenticate)):
        current = member(request, auth, True)
        try:
            result = account_store().update_home_tour(current["id"], progress=normalize_progress(payload.progress),
                                                      expected_revision=payload.expected_revision)
        except RecipeProfileConflictError as exc:
            raise HTTPException(409, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        response.headers["Cache-Control"] = "private, no-store"
        return result

    @router.post("/speech")
    def speech(payload: TourSpeech, request: Request, auth=Depends(authenticate)):
        current = member(request, auth, True)
        text = speech_for(payload.chapter)
        if text is None:
            raise HTTPException(404, "No encontramos ese capítulo.")
        # All members share these public scripts, never a personal transcript.
        # Cache key also includes the configured voice/model and the exact text.
        try:
            result = voice_response(text, "home-tutorial-v1")
        except HTTPException as exc:
            if exc.status_code == 503:
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                code = detail.get("code", "unavailable")
                message = detail.get("message", "") if code in {"payment_issue", "access_denied"} else "La voz oficial no está disponible ahora. Puedes reintentar o continuar leyendo."
                raise HTTPException(503, {"code": code, "message": message}) from None
            raise
        fresh = account_store().member(current["id"])
        if not fresh or fresh.get("session_version", 0) != auth.session_version:
            raise HTTPException(409, "Tu sesión cambió. Vuelve a abrir la guía.")
        return result

    return router
