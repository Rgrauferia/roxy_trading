from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import time
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from roxy_os.shopping_list import ShoppingListStore, normalize_shopping_user


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
SESSION_COOKIE = "roxy_shopping_session"
# A trusted household device should not need recurring pairing. The signed,
# HttpOnly cookie remains revocable by rotating ROXY_HOME_API_KEY, while normal
# Safari/PWA sessions stay connected for one year.
SESSION_TTL_SECONDS = 365 * 24 * 60 * 60
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX = 120
_RATE_STATE: dict[str, dict[str, int]] = {}

app = FastAPI(
    title="Roxy Home",
    description="Servicio privado e independiente para la Lista NFC de Roxy Home.",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


class ShoppingCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    quantity: float = Field(default=1, gt=0, le=100_000)
    unit: str = Field(default="unidad", min_length=1, max_length=32)
    category: str = Field(default="GENERAL", min_length=1, max_length=32)
    notes: str = Field(default="", max_length=1000)


class ShoppingQuantityRequest(BaseModel):
    quantity: float = Field(gt=0, le=100_000)


class AssistantCommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


def _store() -> ShoppingListStore:
    return ShoppingListStore(os.getenv("ROXY_SHOPPING_LIST_PATH", "data/roxy_shopping_list.json"))


def _assistant_shopping_intent(text: str) -> str:
    normalized = text.lower().strip()
    if re.search(r"\b(quita|quitar|elimina|borra)\b", normalized):
        return "shopping_remove"
    if re.search(r"\b(agrega|agregar|añade|anade|apunta|comprar|necesito)\b", normalized):
        return "shopping_add"
    if re.search(r"(lista de compras?|qué falta comprar|que falta comprar|qué necesito comprar|que necesito comprar)", normalized):
        return "shopping_query"
    return "general"


def _assistant_shopping_requests(text: str) -> list[dict[str, Any]]:
    cleaned = re.sub(
        r"(?i)^.*?\b(?:agrega(?:r)?|añade|anade|apunta|comprar|necesito|quita(?:r)?|elimina|borra)\b\s+",
        "",
        text,
    ).strip()
    cleaned = re.sub(
        r"(?i)\s+(?:a|de)\s+(?:mi|la)\s+lista(?:\s+de\s+compras?)?\s*$",
        "",
        cleaned,
    ).strip()
    requests: list[dict[str, Any]] = []
    for raw in re.split(r",|\s+y\s+", cleaned):
        value = re.sub(r"\s+", " ", raw).strip(" .;:-")
        if not value:
            continue
        quantity = 1.0
        quantity_match = re.match(r"(?i)^(\d+(?:[.,]\d+)?)\s+(.+)$", value)
        if quantity_match:
            quantity = float(quantity_match.group(1).replace(",", "."))
            value = quantity_match.group(2).strip()
        value = re.sub(r"(?i)^(?:de|el|la|los|las)\s+", "", value).strip()
        if value:
            requests.append({"name": value[:120], "quantity": quantity, "unit": "unidad"})
    return requests


def _allowed_users() -> set[str]:
    configured = os.getenv("ROXY_STATE_SYNC_USERS", "local_user")
    return {normalize_shopping_user(value) for value in configured.split(",") if value.strip()}


def _allowed_user(user_id: str) -> str:
    user = normalize_shopping_user(user_id)
    if user not in _allowed_users():
        raise HTTPException(status_code=403, detail="Usuario no autorizado")
    return user


def _api_key() -> str:
    key = str(os.getenv("ROXY_HOME_API_KEY") or "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="Roxy Home no está configurado")
    return key


def _session_cookie(user_id: str) -> str:
    expires = int(time.time()) + SESSION_TTL_SECONDS
    encoded = base64.urlsafe_b64encode(f"{user_id}|{expires}".encode()).decode().rstrip("=")
    signature = hmac.new(_api_key().encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _cookie_user(value: str) -> str | None:
    encoded, separator, signature = str(value or "").partition(".")
    if not separator or not encoded or not signature:
        return None
    try:
        expected = hmac.new(_api_key().encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        user_id, raw_expires = decoded.rsplit("|", 1)
        if int(raw_expires) < int(time.time()):
            return None
        return normalize_shopping_user(user_id)
    except (HTTPException, ValueError, UnicodeDecodeError):
        return None


def _authenticate(request: Request) -> str:
    cookie_user = _cookie_user(request.cookies.get(SESSION_COOKIE, ""))
    if cookie_user:
        return f"cookie:{cookie_user}"
    authorization = str(request.headers.get("Authorization") or "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta la clave de acceso")
    supplied = authorization.split(" ", 1)[1]
    if not hmac.compare_digest(supplied, _api_key()):
        raise HTTPException(status_code=403, detail="Clave de acceso incorrecta")
    return "bearer"


def _authorize_user(user_id: str, auth: str) -> str:
    user = _allowed_user(user_id)
    if auth.startswith("cookie:") and not hmac.compare_digest(auth.split(":", 1)[1], user):
        raise HTTPException(status_code=403, detail="La sesión pertenece a otro usuario")
    return user


def _rate_limit(request: Request) -> None:
    key = str(request.client.host if request.client else "unknown")
    now = int(time.time())
    state = _RATE_STATE.get(key)
    if state is None or now - state["start"] >= RATE_LIMIT_WINDOW_SECONDS:
        _RATE_STATE[key] = {"start": now, "count": 1}
        return
    if state["count"] >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Demasiadas solicitudes; inténtalo de nuevo en un minuto")
    state["count"] += 1


def _security_headers(response: Response) -> Response:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    return response


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/home", status_code=307)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "roxy-home"}


@app.get("/home", response_class=FileResponse)
@app.get("/lista", response_class=FileResponse)
def shopping_page() -> Response:
    response = FileResponse(ASSETS_DIR / "roxy_list.html", media_type="text/html")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self' blob: https://esm.sh https://cdn.jsdelivr.net https://esm.run; "
        "connect-src 'self' https://api.elevenlabs.io https://*.elevenlabs.io "
        "wss://api.elevenlabs.io wss://*.elevenlabs.io; media-src 'self' blob:; "
        "worker-src 'self' blob:; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
    return _security_headers(response)


@app.get("/lista-manifest.json")
def shopping_manifest() -> Response:
    response = JSONResponse(
        {
            "id": "/home",
            "name": "Roxy Home – Lista de compras",
            "short_name": "Lista Roxy",
            "description": "Lista de compras privada y sincronizada de Roxy Home.",
            "start_url": "/home",
            "scope": "/home",
            "display": "standalone",
            "orientation": "portrait-primary",
            "background_color": "#f7f4ed",
            "theme_color": "#173f2b",
            "icons": [{"src": "/assets/roxy_avatar_icon.jpg", "sizes": "512x512", "type": "image/jpeg"}],
        },
        headers={"Cache-Control": "public, max-age=3600"},
    )
    return _security_headers(response)


@app.get("/lista-sw.js")
def shopping_service_worker() -> Response:
    response = FileResponse(
        ASSETS_DIR / "roxy_list_sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/lista"},
    )
    return _security_headers(response)


@app.get("/home-sw.js")
def home_service_worker() -> Response:
    response = FileResponse(
        ASSETS_DIR / "roxy_list_sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/home"},
    )
    return _security_headers(response)


@app.post("/v1/shopping/session/{user_id}")
def create_session(user_id: str, request: Request) -> Response:
    _rate_limit(request)
    auth = _authenticate(request)
    user = _authorize_user(user_id, auth)
    response = JSONResponse({"status": "PAIRED", "user_id": user})
    response.set_cookie(
        SESSION_COOKIE,
        _session_cookie(user),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return _security_headers(response)


@app.delete("/v1/shopping/session")
def delete_session() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return _security_headers(response)


@app.get("/v1/assistant/session/{user_id}")
def assistant_session(user_id: str, request: Request, auth: str = Depends(_authenticate)) -> dict[str, Any]:
    """Return non-secret configuration for the shared public ElevenLabs agent."""
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    agent_id = str(
        os.getenv("ELEVENLABS_AGENT_ID") or "agent_6101kwchebzdf91rfk9757wq0mk4"
    ).strip()
    if not agent_id:
        raise HTTPException(status_code=503, detail="Roxy ElevenLabs no está configurada")
    snapshot = _store().snapshot(user, limit=100)
    return {
        "status": "READY",
        "provider": "ElevenLabs",
        "agent_id": agent_id,
        "voice_mode": "public_websocket",
        "connection_type": "websocket",
        "user_id": user,
        "dynamic_variables": {
            "user_name": user,
            "preferred_language": "es",
            "current_app": "Roxy Home",
            "current_page": "Lista de compras",
            "shopping_pending_count": int(snapshot.get("pending_count") or 0),
            "roxy_identity": "La misma Roxy de Roxy Trading, Roxy Home y Roxy Finance",
        },
    }


@app.post("/v1/assistant/command/{user_id}")
def assistant_command(
    user_id: str,
    payload: AssistantCommandRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    """Execute safe Roxy OS commands issued through ElevenLabs client tools."""
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    command_text = payload.text.strip()
    # Voice naturally says “agrega pan a mi lista de compra”. The shared
    # router also recognizes “lista de compra” as a read query, so remove only
    # this destination suffix when an explicit write verb is present.
    if re.search(r"(?i)\b(agrega|añade|anade|apunta|quita|elimina|borra)\b", command_text):
        command_text = re.sub(
            r"(?i)\s+(?:a|de)\s+(?:mi|la)\s+lista(?:\s+de\s+compras?)?\s*$",
            "",
            command_text,
        ).strip()
    intent = _assistant_shopping_intent(command_text)
    agent = "shopping" if intent.startswith("shopping_") else "general"
    store = _store()
    rows: list[dict[str, Any]] = []
    if intent == "shopping_query":
        rows = store.list_items(user, statuses={"PENDING"}, limit=50)
        if rows:
            labels = [
                f"{item.get('quantity') or 1:g} {item.get('unit') or 'unidad'} de {item.get('name') or ''}"
                for item in rows
            ]
            message = "En tu lista tengo: " + ", ".join(labels) + "."
        else:
            message = "No tengo artículos pendientes en tu lista de compra."
    elif intent == "shopping_remove":
        removed: list[dict[str, Any]] = []
        missing: list[str] = []
        for row in _assistant_shopping_requests(command_text):
            try:
                removed.append(store.delete_named(user, row["name"]))
            except KeyError:
                missing.append(str(row["name"]))
        rows = removed
        message = (
            "Quité de tu lista: " + ", ".join(str(item.get("name")) for item in removed) + "."
            if removed
            else "No encontré esos artículos en tus pendientes."
        )
        if missing:
            message += " No encontré: " + ", ".join(missing) + "."
    elif intent == "shopping_add":
        for row in _assistant_shopping_requests(command_text):
            rows.append(
                store.add(
                    user,
                    row["name"],
                    quantity=row.get("quantity") or 1,
                    unit=row.get("unit") or "unidad",
                    source="elevenlabs_voice",
                )
            )
        message = (
            "Listo, agregué a tu lista: " + ", ".join(str(item.get("name")) for item in rows) + "."
            if rows
            else "Dime qué artículos quieres agregar a la lista."
        )
    else:
        # General knowledge stays inside the ElevenLabs agent. This endpoint is
        # deliberately limited to durable Roxy Home actions.
        message = "La herramienta de Roxy Home solo ejecuta consultas y cambios de la lista de compras."
    return {
        "ok": True,
        "intent": intent,
        "agent": agent,
        "message": message,
        "data": {"items": rows},
        "snapshot": store.snapshot(user, limit=100),
    }


@app.get("/v1/shopping/{user_id}")
def read_list(user_id: str, request: Request, auth: str = Depends(_authenticate)) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _store()
    snapshot = store.snapshot(user, limit=1000)
    snapshot["items"] = store.list_items(user, include_archived=False, limit=1000)
    snapshot["sync_state"] = "SERVER_SYNCED"
    return snapshot


@app.post("/v1/shopping/{user_id}", status_code=201)
def create_item(
    user_id: str,
    payload: ShoppingCreateRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _store()
    try:
        item = store.add(
            user,
            payload.name,
            quantity=payload.quantity,
            unit=payload.unit,
            category=payload.category,
            notes=payload.notes,
            source="roxy_home_pwa",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "CREATED", "item": item, "snapshot": store.snapshot(user, limit=1000)}


@app.patch("/v1/shopping/{user_id}/{item_id}")
def update_quantity(
    user_id: str,
    item_id: str,
    payload: ShoppingQuantityRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        item = _store().set_quantity(user, item_id, payload.quantity)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Artículo no encontrado") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "UPDATED", "item": item}


@app.delete("/v1/shopping/{user_id}/{item_id}")
def delete_item(
    user_id: str,
    item_id: str,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        item = _store().delete(user, item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Artículo no encontrado") from exc
    return {"status": "DELETED", "item": item}


@app.post("/v1/shopping/{user_id}/complete")
def complete_purchase(
    user_id: str,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    result = _store().complete_purchase(user)
    return {"status": "COMPLETED" if result.get("completed") else "EMPTY", **result}
