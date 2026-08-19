from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from roxy_os.home_ai import (
    HomeAIBudgetExceeded,
    HomeAIConfig,
    HomeAIConfigurationError,
    RoxyHomeAI,
)
from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_food import HomeFoodStore, HomePermissionPolicy
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
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 15 * 60
LOGIN_RATE_LIMIT_MAX = 10
_LOGIN_RATE_STATE: dict[str, dict[str, int]] = {}

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


class HomeProfileRequest(BaseModel):
    preferences: list[str] = Field(default_factory=list, max_length=50)
    allergies: list[str] = Field(default_factory=list, max_length=50)
    dislikes: list[str] = Field(default_factory=list, max_length=50)
    household_size: int = Field(default=1, ge=1, le=50)


class PantryItemRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    quantity: float = Field(default=1, gt=0, le=100_000)
    unit: str = Field(default="unidad", min_length=1, max_length=32)


class PantryRequest(BaseModel):
    items: list[PantryItemRequest] = Field(default_factory=list, max_length=500)


class HomePromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    mode: str = Field(default="routine", pattern="^(routine|deep)$")
    recipe_type: str = Field(default="general", pattern="^(general|alcoholic|non_alcoholic)$")


class RecipeScaleRequest(BaseModel):
    servings: float = Field(gt=0, le=100)


class RecipeShoppingRequest(BaseModel):
    confirmed: bool = False
    servings: float | None = Field(default=None, gt=0, le=100)


class CookingSessionActionRequest(BaseModel):
    action: str = Field(pattern="^(next|previous|restart|complete)$")


class CookingTimerRequest(BaseModel):
    duration_seconds: int = Field(gt=0, le=86_400)
    label: str = Field(default="Temporizador", max_length=120)


class RecipePersonalizeRequest(BaseModel):
    favorite: bool = False
    user_notes: str = Field(default="", max_length=2000)
    photo_data_url: str | None = Field(default=None, max_length=2_100_000)


class FoodSafetyRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class HomeLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class HomeBootstrapRequest(HomeLoginRequest):
    display_name: str = Field(min_length=1, max_length=64)
    household_name: str = Field(default="Nuestro hogar", min_length=1, max_length=64)
    storage_user_id: str = Field(default="local_user", min_length=1, max_length=96)


class HomeMemberRequest(HomeLoginRequest):
    display_name: str = Field(min_length=1, max_length=64)


@dataclass(frozen=True)
class AuthContext:
    mode: str
    storage_user_id: str | None = None
    member_id: str | None = None


def _store() -> ShoppingListStore:
    return ShoppingListStore(os.getenv("ROXY_SHOPPING_LIST_PATH", "data/roxy_shopping_list.json"))


def _home_food_store() -> HomeFoodStore:
    return HomeFoodStore(os.getenv("ROXY_HOME_MEMORY_PATH", "data/roxy_home_food.json"))


def _account_store() -> HomeAccountStore:
    return HomeAccountStore(os.getenv("ROXY_HOME_ACCOUNTS_PATH", "data/roxy_home_accounts.json"))


def _home_ai() -> RoxyHomeAI:
    return RoxyHomeAI(HomeAIConfig.from_env())


def _ai_call(callback: Any) -> dict[str, Any]:
    try:
        return callback()
    except HomeAIConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HomeAIBudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        # Provider errors stay server-side; no key, prompt internals or stack
        # details are returned to the browser.
        raise HTTPException(status_code=502, detail="Roxy Home no pudo completar la solicitud de IA.") from exc


def _assistant_shopping_intent(text: str) -> str:
    normalized = text.lower().strip()
    if re.search(r"\b(agrega|añade|anade|pon|pasa)\b.*\bingredientes?\b.*\b(lista|carrito)\b", normalized):
        return "recipe_to_shopping"
    if re.search(r"\b(guiame|guíame|guia|guía)\b|\b(cocinar|preparar)\b.*\bpaso a paso\b|\bempezar a cocinar\b", normalized):
        return "cooking_start"
    if re.search(r"\b(siguiente paso|continua|continúa|adelante)\b", normalized):
        return "cooking_next"
    if re.search(r"\b(paso anterior|anterior paso|atras|atrás)\b", normalized):
        return "cooking_previous"
    if re.search(r"\b(repite|repetir|cual es el paso|cuál es el paso)\b", normalized):
        return "cooking_current"
    if re.search(r"\b(temporizador|timer)\b", normalized) and re.search(r"\b(pon|inicia|iniciar|programa|programar)\b", normalized):
        return "cooking_timer_set"
    if re.search(r"\b(cuanto|cuánto)\b.*\b(falta|queda)\b|\btiempo restante\b", normalized):
        return "cooking_timer_query"
    if re.search(r"\b(termine|terminé|finaliza|finalizar)\b.*\b(receta|cocina|cocinar)\b", normalized):
        return "cooking_complete"
    if re.search(r"\b(receta|cocinar|cocino|preparar|preparo)\b", normalized):
        return "recipe_generate"
    if re.search(r"\b(quita|quitar|elimina|borra|saca|sacar|remueve|remover)\b|\bya no necesito\b", normalized):
        return "shopping_remove"
    if re.search(r"\b(agrega|agregar|añade|anade|apunta|comprar|necesito)\b", normalized):
        return "shopping_add"
    if re.search(r"(lista de compras?|qué falta comprar|que falta comprar|qué necesito comprar|que necesito comprar)", normalized):
        return "shopping_query"
    return "general"


def _assistant_shopping_requests(text: str) -> list[dict[str, Any]]:
    cleaned = re.sub(
        r"(?i)^.*?\b(?:agrega(?:r)?|añade|anade|apunta|comprar|necesito|quita(?:r)?|elimina|borra|saca(?:r)?|remueve|remover)\b\s+",
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
        word_numbers = {"un":1,"una":1,"uno":1,"dos":2,"tres":3,"cuatro":4,"cinco":5,"seis":6,"media":.5,"medio":.5}
        quantity_match = re.match(r"(?i)^(\d+(?:[.,]\d+)?|un|una|uno|dos|tres|cuatro|cinco|seis|media|medio)\s+(.+)$", value)
        if quantity_match:
            raw_quantity = quantity_match.group(1).lower()
            quantity = word_numbers.get(raw_quantity, float(raw_quantity.replace(",", ".")) if raw_quantity[0].isdigit() else 1)
            value = quantity_match.group(2).strip()
        unit = "unidad"
        unit_match = re.match(r"(?i)^(paquetes?|botellas?|bolsas?|litros?|kilos?|kilogramos?|gramos?|docenas?|latas?|tazas?|unidades?)\s+(?:de\s+)?(.+)$", value)
        if unit_match:
            raw_unit = unit_match.group(1).lower()
            unit_aliases = {"paquetes":"paquete","botellas":"botella","bolsas":"bolsa","litros":"litro","kilos":"kilo","kilogramos":"kilogramo","gramos":"gramo","docenas":"docena","latas":"lata","tazas":"taza","unidades":"unidad"}
            unit = unit_aliases.get(raw_unit, raw_unit)
            value = unit_match.group(2).strip()
        value = re.sub(r"(?i)^(?:de|el|la|los|las|un|una|unos|unas)\s+", "", value).strip()
        if value:
            requests.append({"name": value[:120], "quantity": quantity, "unit": unit})
    return requests


def _timer_seconds(text: str) -> int | None:
    normalized = text.lower().replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(segundos?|minutos?|horas?)", normalized)
    if not match:
        words = {"un":1,"una":1,"dos":2,"tres":3,"cuatro":4,"cinco":5,"diez":10,"quince":15,"veinte":20,"treinta":30}
        match = re.search(r"\b(" + "|".join(words) + r")\b\s*(segundos?|minutos?|horas?)", normalized)
        if not match:
            return None
        amount = float(words[match.group(1)])
    else:
        amount = float(match.group(1))
    unit = match.group(2)
    return int(amount * (3600 if unit.startswith("hora") else 60 if unit.startswith("minuto") else 1))


def _voice_item_identity(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized.encode("ascii", "ignore").decode("ascii").lower()).strip()
    words = []
    for word in normalized.split():
        if len(word) > 4 and word.endswith("es"):
            word = word[:-2]
        elif len(word) > 3 and word.endswith("s"):
            word = word[:-1]
        words.append(word)
    return " ".join(words)


def _delete_voice_item(store: ShoppingListStore, user: str, name: str) -> dict[str, Any]:
    try:
        return store.delete_named(user, name)
    except KeyError:
        target = _voice_item_identity(name)
        matches = [
            item
            for item in store.list_items(user, statuses={"PENDING"}, limit=1000)
            if _voice_item_identity(item.get("name")) == target
        ]
        if len(matches) == 1:
            return store.delete(user, matches[0]["id"])
        raise


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


def _member_session_cookie(member: dict[str, Any]) -> str:
    expires = int(time.time()) + SESSION_TTL_SECONDS
    raw = f"member|{member['id']}|{member['storage_user_id']}|{expires}"
    encoded = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
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
        if decoded.startswith("member|"):
            return None
        user_id, raw_expires = decoded.rsplit("|", 1)
        if int(raw_expires) < int(time.time()):
            return None
        return normalize_shopping_user(user_id)
    except (HTTPException, ValueError, UnicodeDecodeError):
        return None


def _cookie_auth(value: str) -> AuthContext | None:
    encoded, separator, signature = str(value or "").partition(".")
    if not separator or not encoded or not signature:
        return None
    try:
        expected = hmac.new(_api_key().encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        if decoded.startswith("member|"):
            _, member_id, storage_user_id, raw_expires = decoded.split("|", 3)
            if int(raw_expires) < int(time.time()):
                return None
            member = _account_store().member(member_id)
            if member is None or not hmac.compare_digest(member["storage_user_id"], normalize_shopping_user(storage_user_id)):
                return None
            return AuthContext("member", member["storage_user_id"], member["id"])
        user_id, raw_expires = decoded.rsplit("|", 1)
        if int(raw_expires) < int(time.time()):
            return None
        return AuthContext("legacy", normalize_shopping_user(user_id))
    except (HTTPException, ValueError, UnicodeDecodeError):
        return None


def _authenticate(request: Request) -> AuthContext:
    cookie_auth = _cookie_auth(request.cookies.get(SESSION_COOKIE, ""))
    if cookie_auth:
        return cookie_auth
    authorization = str(request.headers.get("Authorization") or "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta la clave de acceso")
    supplied = authorization.split(" ", 1)[1]
    if not hmac.compare_digest(supplied, _api_key()):
        raise HTTPException(status_code=403, detail="Clave de acceso incorrecta")
    return AuthContext("bearer")


def _authorize_user(user_id: str, auth: AuthContext) -> str:
    user = _allowed_user(user_id)
    if auth.storage_user_id and not hmac.compare_digest(auth.storage_user_id, user):
        raise HTTPException(status_code=403, detail="La sesión pertenece a otro usuario")
    return user


def _member_for_auth(auth: AuthContext) -> dict[str, Any] | None:
    return _account_store().member(auth.member_id) if auth.mode == "member" and auth.member_id else None


def _set_session_cookie(response: Response, value: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        value,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )


def _personalize(message: str, auth: AuthContext) -> str:
    member = _member_for_auth(auth)
    name = str(member.get("display_name") or "").strip() if member else ""
    return f"Claro, {name}. {message}" if name else message


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


def _login_rate_limit(request: Request, username: str) -> None:
    key = f"{request.client.host if request.client else 'unknown'}:{username.strip().lower()}"
    now = int(time.time())
    state = _LOGIN_RATE_STATE.get(key)
    if state is None or now - state["start"] >= LOGIN_RATE_LIMIT_WINDOW_SECONDS:
        _LOGIN_RATE_STATE[key] = {"start": now, "count": 1}
        return
    if state["count"] >= LOGIN_RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Demasiados intentos de acceso; espera quince minutos.")
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
    if _account_store().household_configured(user):
        raise HTTPException(status_code=409, detail="Este hogar ya usa perfiles personales; inicia sesión con tu usuario")
    response = JSONResponse({"status": "PAIRED", "user_id": user})
    _set_session_cookie(response, _session_cookie(user))
    return _security_headers(response)


@app.delete("/v1/shopping/session")
def delete_session() -> Response:
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return _security_headers(response)


@app.get("/v1/home-account/me")
def home_account_me(request: Request, auth: AuthContext = Depends(_authenticate)) -> dict[str, Any]:
    _rate_limit(request)
    member = _member_for_auth(auth)
    if member:
        return {"status": "AUTHENTICATED", "mode": "member", "requires_profile_setup": False, **member}
    if auth.storage_user_id:
        return {
            "status": "LEGACY_SESSION",
            "mode": "legacy",
            "requires_profile_setup": not _account_store().household_configured(auth.storage_user_id),
            "storage_user_id": auth.storage_user_id,
            "display_name": "",
            "role": "LEGACY",
        }
    raise HTTPException(status_code=401, detail="Inicia sesión en Roxy Home")


@app.post("/v1/home-account/login")
def home_account_login(payload: HomeLoginRequest, request: Request) -> Response:
    _login_rate_limit(request, payload.username)
    member = _account_store().authenticate(payload.username, payload.password)
    if member is None:
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    response = JSONResponse({"status": "AUTHENTICATED", "mode": "member", **member})
    _set_session_cookie(response, _member_session_cookie(member))
    return _security_headers(response)


@app.post("/v1/home-account/bootstrap", status_code=201)
def home_account_bootstrap(
    payload: HomeBootstrapRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> Response:
    _rate_limit(request)
    if auth.mode == "member":
        raise HTTPException(status_code=409, detail="El hogar ya tiene una sesión personal")
    storage_user = _authorize_user(payload.storage_user_id, auth)
    try:
        member = _account_store().bootstrap(
            storage_user,
            household_name=payload.household_name,
            username=payload.username,
            display_name=payload.display_name,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    response = JSONResponse({"status": "CREATED", "mode": "member", **member}, status_code=201)
    _set_session_cookie(response, _member_session_cookie(member))
    return _security_headers(response)


@app.get("/v1/home-account/members")
def home_account_members(request: Request, auth: AuthContext = Depends(_authenticate)) -> dict[str, Any]:
    _rate_limit(request)
    member = _member_for_auth(auth)
    if member is None:
        raise HTTPException(status_code=409, detail="Primero crea tu perfil personal")
    return {"status": "READY", "members": _account_store().members(member["id"])}


@app.post("/v1/home-account/members", status_code=201)
def home_account_add_member(
    payload: HomeMemberRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    member = _member_for_auth(auth)
    if member is None:
        raise HTTPException(status_code=409, detail="Primero crea tu perfil personal")
    try:
        created = _account_store().add_member(
            member["id"], username=payload.username, display_name=payload.display_name, password=payload.password
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "CREATED", "member": created}


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
    member = _member_for_auth(auth)
    display_name = member["display_name"] if member else user
    return {
        "status": "READY",
        "provider": "ElevenLabs",
        "agent_id": agent_id,
        "voice_mode": "public_websocket",
        "connection_type": "websocket",
        "user_id": user,
        "dynamic_variables": {
            "user_name": display_name,
            "member_id": member["id"] if member else "legacy",
            "household_name": member["household_name"] if member else "Roxy Home",
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
    intent = _assistant_shopping_intent(command_text)
    # Voice naturally says “agrega pan a mi lista de compra”. The shared
    # router also recognizes “lista de compra” as a read query, so remove only
    # this destination suffix when an explicit write verb is present.
    if intent in {"shopping_add", "shopping_remove"}:
        command_text = re.sub(
            r"(?i)\s+(?:a|de)\s+(?:mi|la)\s+lista(?:\s+de\s+compras?)?\s*$",
            "",
            command_text,
        ).strip()
    agent = (
        "shopping"
        if intent.startswith("shopping_")
        else "home_food"
        if intent.startswith("recipe_") or intent.startswith("cooking_")
        else "general"
    )
    store = _store()
    rows: list[dict[str, Any]] = []
    extra: dict[str, Any] = {}
    if intent == "recipe_generate":
        home_store = _home_food_store()
        recipe_data = _ai_call(
            lambda: _home_ai().generate_recipe(command_text, home_store.snapshot(user), deep=False)
        )
        try:
            recipe = home_store.save_recipe(user, recipe_data, mode="routine")
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Roxy devolvió una receta incompleta.") from exc
        ingredients = ", ".join(
            f"{row.get('quantity'):g} {row.get('unit')} de {row.get('name')}"
            for row in recipe.get("ingredients", [])
        )
        message = f"Te preparé {recipe['title']} para {recipe['servings']:g} porciones. Ingredientes: {ingredients}."
        if recipe.get("steps"):
            message += " Preparación: " + " ".join(
                f"{index}. {step}" for index, step in enumerate(recipe["steps"], start=1)
            )
        message += " Si te gusta, dime: agrega los ingredientes de esta receta a mi lista."
        extra["recipe"] = recipe
    elif intent == "recipe_to_shopping":
        home_store = _home_food_store()
        recipes = home_store.snapshot(user).get("recipes", [])
        if not recipes:
            raise HTTPException(status_code=409, detail="Primero pide o crea una receta.")
        # The spoken command itself is the explicit confirmation required to
        # convert the most recently approved recipe into shopping items.
        conversion = home_store.commit_recipe_to_shopping(
            user,
            recipes[-1]["id"],
            store,
            confirmed=True,
        )
        rows = conversion.get("items", [])
        if rows:
            message = "Agregué los ingredientes que faltaban: " + ", ".join(
                str(item.get("name")) for item in rows
            ) + "."
        else:
            message = "Según tu despensa, ya tienes todos los ingredientes de esa receta."
        extra["recipe_id"] = recipes[-1]["id"]
    elif intent.startswith("cooking_"):
        home_store = _home_food_store()
        home_snapshot = home_store.snapshot(user)
        sessions = home_snapshot.get("cooking_sessions", [])
        active = next((row for row in reversed(sessions) if row.get("status") == "ACTIVE"), None)
        if intent == "cooking_start":
            recipes = home_snapshot.get("recipes", [])
            if not recipes:
                raise HTTPException(status_code=409, detail="Primero pide o crea una receta.")
            session = home_store.start_cooking_session(user, recipes[-1]["id"])
        else:
            if active is None:
                raise HTTPException(status_code=409, detail="No hay una receta activa. Dime: guíame paso a paso.")
            if intent == "cooking_timer_set":
                seconds = _timer_seconds(command_text)
                if seconds is None:
                    raise HTTPException(status_code=422, detail="Dime la duración, por ejemplo: pon un temporizador de 20 minutos.")
                timer = home_store.add_cooking_timer(user, active["id"], duration_seconds=seconds, label="Temporizador de cocina")
                detail = home_store.cooking_session_detail(user, active["id"])
                message = f"Temporizador iniciado por {seconds // 60} minutos." if seconds >= 60 else f"Temporizador iniciado por {seconds} segundos."
                extra["cooking"] = detail
                extra["timer"] = timer
                return {"ok":True,"intent":intent,"agent":agent,"message":_personalize(message,auth),"data":{"items":[],**extra},"snapshot":store.snapshot(user,limit=100)}
            if intent == "cooking_timer_query":
                detail = home_store.cooking_session_detail(user, active["id"])
                timers = [row for row in detail["session"].get("timers", []) if row.get("status") == "ACTIVE"]
                message = "No hay temporizadores activos." if not timers else "Quedan " + ", ".join(f"{row.get('remaining_seconds',0)//60} minutos y {row.get('remaining_seconds',0)%60} segundos" for row in timers) + "."
                extra["cooking"] = detail
                return {"ok":True,"intent":intent,"agent":agent,"message":_personalize(message,auth),"data":{"items":[],**extra},"snapshot":store.snapshot(user,limit=100)}
            action = {
                "cooking_next": "next",
                "cooking_previous": "previous",
                "cooking_complete": "complete",
            }.get(intent)
            session = home_store.update_cooking_session(user, active["id"], action) if action else active
        detail = home_store.cooking_session_detail(user, session["id"])
        if detail["session"].get("status") == "COMPLETED":
            message = f"Terminamos {detail['recipe']['title']}. La receta seguirá guardada en tu biblioteca."
        else:
            message = (
                f"Paso {detail['step_number']} de {len(detail['recipe'].get('steps') or [])}: "
                f"{detail['current_step']}"
            )
        extra["cooking"] = detail
    elif intent == "shopping_query":
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
                removed.append(_delete_voice_item(store, user, row["name"]))
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
        "message": _personalize(message, auth),
        "data": {"items": rows, **extra},
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


@app.get("/v1/home-food/{user_id}")
def read_home_food(user_id: str, request: Request, auth: str = Depends(_authenticate)) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    return _home_food_store().snapshot(user)


@app.put("/v1/home-food/{user_id}/profile")
def update_home_profile(
    user_id: str,
    payload: HomeProfileRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    profile = _home_food_store().update_profile(user, **payload.model_dump())
    return {"status": "UPDATED", "profile": profile}


@app.put("/v1/home-food/{user_id}/pantry")
def update_home_pantry(
    user_id: str,
    payload: PantryRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        items = _home_food_store().replace_pantry(user, [row.model_dump() for row in payload.items])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "UPDATED", "items": items}


@app.post("/v1/home-food/{user_id}/recipes", status_code=201)
def generate_home_recipe(
    user_id: str,
    payload: HomePromptRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _home_food_store()
    snapshot = store.snapshot(user)
    recipe_data = _ai_call(
        lambda: _home_ai().generate_recipe(payload.prompt, snapshot, deep=payload.mode == "deep")
    )
    if payload.recipe_type != "general":
        recipe_data = {**recipe_data, "kind": "drink", "drink_type": payload.recipe_type}
    try:
        recipe = store.save_recipe(user, recipe_data, mode=payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Roxy devolvió una receta incompleta.") from exc
    return {"status": "CREATED", "recipe": recipe}


@app.patch("/v1/home-food/{user_id}/recipes/{recipe_id}")
def personalize_home_recipe(
    user_id: str,
    recipe_id: str,
    payload: RecipePersonalizeRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        recipe = _home_food_store().personalize_recipe(user, recipe_id, **payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Receta no encontrada") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "UPDATED", "recipe": recipe}


@app.post("/v1/home-food/{user_id}/recipes/{recipe_id}/cooking-sessions", status_code=201)
def start_home_cooking_session(
    user_id: str,
    recipe_id: str,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _home_food_store()
    try:
        session = store.start_cooking_session(user, recipe_id)
        return {"status": "STARTED", **store.cooking_session_detail(user, session["id"])}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Receta no encontrada") from exc


@app.get("/v1/home-food/{user_id}/cooking-sessions/{session_id}")
def read_home_cooking_session(
    user_id: str,
    session_id: str,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        return {"status": "READY", **_home_food_store().cooking_session_detail(user, session_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sesión de cocina no encontrada") from exc


@app.post("/v1/home-food/{user_id}/cooking-sessions/{session_id}")
def update_home_cooking_session(
    user_id: str,
    session_id: str,
    payload: CookingSessionActionRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _home_food_store()
    try:
        store.update_cooking_session(user, session_id, payload.action)
        return {"status": "UPDATED", **store.cooking_session_detail(user, session_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sesión de cocina no encontrada") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/v1/home-food/{user_id}/cooking-sessions/{session_id}/timers", status_code=201)
def create_home_cooking_timer(
    user_id: str,
    session_id: str,
    payload: CookingTimerRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _home_food_store()
    try:
        timer = store.add_cooking_timer(user, session_id, **payload.model_dump())
        return {"status":"STARTED","timer":timer,**store.cooking_session_detail(user,session_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sesión de cocina no encontrada") from exc


@app.delete("/v1/home-food/{user_id}/cooking-sessions/{session_id}/timers/{timer_id}")
def cancel_home_cooking_timer(
    user_id: str,
    session_id: str,
    timer_id: str,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        timer = _home_food_store().cancel_cooking_timer(user, session_id, timer_id)
        return {"status":"CANCELLED","timer":timer}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Temporizador no encontrado") from exc


@app.post("/v1/home-food/{user_id}/substitutions")
def suggest_home_substitutions(
    user_id: str,
    payload: HomePromptRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    snapshot = _home_food_store().snapshot(user)
    result = _ai_call(lambda: _home_ai().substitutions(payload.prompt, snapshot))
    return {"status": "READY", "result": result}


@app.post("/v1/home-food/{user_id}/recipes/{recipe_id}/scale")
def scale_home_recipe(
    user_id: str,
    recipe_id: str,
    payload: RecipeScaleRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        recipe = _home_food_store().scale_recipe(user, recipe_id, payload.servings)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Receta no encontrada") from exc
    return {"status": "SCALED", "recipe": recipe}


@app.post("/v1/home-food/{user_id}/recipes/{recipe_id}/shopping-preview")
def preview_recipe_shopping(
    user_id: str,
    recipe_id: str,
    payload: RecipeShoppingRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        preview = _home_food_store().shopping_preview(user, recipe_id, servings=payload.servings)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Receta no encontrada") from exc
    return {"status": "PREVIEW", **preview}


@app.post("/v1/home-food/{user_id}/recipes/{recipe_id}/shopping-commit")
def commit_recipe_shopping(
    user_id: str,
    recipe_id: str,
    payload: RecipeShoppingRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    decision = HomePermissionPolicy.decision("recipe_to_shopping", confirmed=payload.confirmed)
    if decision != "ALLOW":
        raise HTTPException(status_code=409, detail="CONFIRMATION_REQUIRED")
    try:
        return _home_food_store().commit_recipe_to_shopping(
            user,
            recipe_id,
            _store(),
            confirmed=True,
            servings=payload.servings,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Receta no encontrada") from exc


@app.post("/v1/home-food/{user_id}/weekly-plans", status_code=201)
def create_home_weekly_plan(
    user_id: str,
    payload: HomePromptRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _home_food_store()
    result = _ai_call(
        lambda: _home_ai().weekly_plan(payload.prompt, store.snapshot(user), deep=payload.mode == "deep")
    )
    try:
        plan = store.save_weekly_plan(user, result)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Roxy devolvió un plan incompleto.") from exc
    return {"status": "CREATED", "plan": plan}


@app.post("/v1/home-food/{user_id}/food-safety")
def research_food_safety(
    user_id: str,
    payload: FoodSafetyRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    result = _ai_call(lambda: _home_ai().food_safety(payload.question, _home_food_store().snapshot(user)))
    return {"status": "READY", "result": result}
