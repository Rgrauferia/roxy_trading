from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from roxy_os.home_ai import (
    HomeAIBudgetExceeded,
    HomeAIConfig,
    HomeAIConfigurationError,
    RoxyHomeAI,
)
from roxy_os.home_recipe_fallback import (
    find_local_recipe,
    generate_local_recipe,
    local_recipe_catalog,
    local_recipe_catalog_summary,
)
from roxy_os.home_recipe_library import (
    HomeRecipeLibraryStore,
    recipe_is_compatible,
    requested_servings,
    scale_recipe_payload,
)
from roxy_os.home_recipe_photos import RecipePhotoStore
from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_commerce import (
    AFFILIATE_DISCLOSURE,
    HomeCommerceStore,
    create_purchase_links,
    personalize_items,
    public_providers,
)
from roxy_os.home_food import HomeFoodStore, HomePermissionPolicy
from roxy_os.home_weekly_plans import (
    create_local_weekly_plan,
    update_weekly_plan_day,
    update_weekly_plan_meal,
    weekly_plan_shopping_items,
)
from roxy_os.home_recipe_videos import (
    FalHailuoVideoProvider,
    HomeRecipeVideoConfig,
    HomeRecipeVideoStore,
    VIDEO_PROMPT_VERSION,
    submit_recipe_video,
    sync_recipe_video,
)
from roxy_os.home_voice import ElevenLabsHomeVoice, HomeVoiceConfig
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


class CommerceProfileRequest(BaseModel):
    objective: str = Field(default="balanced", pattern="^(balanced|lowest_price|organic|favorites)$")
    organic_preference: str = Field(default="no_preference", pattern="^(required|preferred|no_preference)$")
    favorite_retailers: list[str] = Field(default_factory=list, max_length=30)
    favorite_brands: list[str] = Field(default_factory=list, max_length=30)
    avoided_brands: list[str] = Field(default_factory=list, max_length=30)
    dietary_labels: list[str] = Field(default_factory=list, max_length=30)
    allow_substitutions: bool = True
    postal_code: str = Field(default="", max_length=12)


class CommercePrepareRequest(BaseModel):
    source: str = Field(default="shopping", pattern="^(shopping|recipe)$")
    recipe_id: str | None = Field(default=None, max_length=64)
    provider_ids: list[str] = Field(default_factory=list, max_length=10)


class CommerceCheckoutRequest(BaseModel):
    provider_id: str = Field(min_length=1, max_length=32)
    confirmed: bool = False


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


class WeeklyPlanRequest(BaseModel):
    style: str = Field(default="normal", pattern="^(fitness|normal|quick|weight_loss)$")
    people: int = Field(default=1, ge=1, le=20)
    max_minutes: int = Field(default=25, ge=5, le=180)
    weekly_budget: float = Field(default=85, ge=0, le=10_000)
    cook_days: int = Field(default=2, ge=1, le=7)
    meal_scope: str = Field(default="all", pattern="^(all|lunch_dinner|dinner_only)$")


class WeeklyPlanShoppingRequest(BaseModel):
    confirmed: bool = False
    excluded_days: list[int] = Field(default_factory=list, max_length=7)


class WeeklyPlanMealRequest(BaseModel):
    day_index: int = Field(ge=0, le=6)
    meal_index: int = Field(ge=0, le=2)
    action: str = Field(pattern="^(swap|favorite)$")


class WeeklyPlanDayRequest(BaseModel):
    day_index: int = Field(ge=0, le=6)
    action: str = Field(pattern="^(cooked|leftovers|skip|reset)$")


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


class RecipeVideoRequest(BaseModel):
    visibility: str = Field(default="shared", pattern="^(shared|household)$")
    confirmed: bool = False


class RecipeVideoReviewRequest(BaseModel):
    approved: bool
    notes: str = Field(default="", max_length=1000)


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


def _recipe_library_store() -> HomeRecipeLibraryStore:
    return HomeRecipeLibraryStore(
        os.getenv("ROXY_HOME_RECIPE_LIBRARY_PATH", "data/roxy_home_recipe_library.sqlite")
    )


_RECIPE_PHOTO_STORES: dict[str, RecipePhotoStore] = {}


def _recipe_photo_store() -> RecipePhotoStore:
    path = os.getenv("ROXY_HOME_RECIPE_PHOTO_DIR", "data/roxy_home_recipe_photos")
    if path not in _RECIPE_PHOTO_STORES:
        _RECIPE_PHOTO_STORES[path] = RecipePhotoStore(path)
    return _RECIPE_PHOTO_STORES[path]


def _recipe_video_store() -> HomeRecipeVideoStore:
    return HomeRecipeVideoStore(
        os.getenv("ROXY_HOME_VIDEO_LIBRARY_PATH", "data/roxy_home_recipe_video_library.json")
    )


def _recipe_video_config() -> HomeRecipeVideoConfig:
    return HomeRecipeVideoConfig.from_env()


def _recipe_video_public_status() -> dict[str, Any]:
    status = _recipe_video_config().public_status()
    status["action_library"] = _recipe_video_store().action_library_status()
    return status


def _recipe_video_provider(config: HomeRecipeVideoConfig) -> FalHailuoVideoProvider:
    return FalHailuoVideoProvider(config)


def _home_voice_config() -> HomeVoiceConfig:
    return HomeVoiceConfig.from_env()


def _submit_recipe_video_background(
    store: HomeRecipeVideoStore,
    provider: FalHailuoVideoProvider,
    video_id: str,
) -> None:
    try:
        submit_recipe_video(store, provider, video_id)
    except ConnectionError:
        # submit_recipe_video already persists FAILED without leaking provider
        # details. Cooking must continue even when media generation is down.
        return


def _queue_recipe_video_for_cooking(
    user: str,
    recipe: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> tuple[str, dict[str, Any] | None]:
    """Queue missing shared media; beginning to cook is the user's intent."""

    config = _recipe_video_config()
    store = _recipe_video_store()
    existing = store.find_for_recipe(user, recipe)
    if existing is not None:
        existing["reused"] = True
        return "REUSED", existing
    estimated_cost = store.estimated_generation_cost(recipe, config)
    allow_missing = str(os.getenv("ROXY_HOME_VIDEO_AUTO_GENERATE_MISSING_ACTIONS", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if estimated_cost > 0 and not allow_missing:
        return "LIBRARY_BUILDING", None
    if estimated_cost > 0 and not config.configured:
        return config.state.upper(), None
    if estimated_cost > 0 and store.monthly_reserved_usd() + estimated_cost > config.monthly_budget_usd:
        return "BUDGET_LIMIT", None
    record, reused = store.create_or_reuse(user, recipe, config, visibility="shared")
    public = store._public(record, user)
    public["reused"] = reused
    fully_reused = record.get("status") == "READY"
    if not reused and not fully_reused:
        background_tasks.add_task(
            _submit_recipe_video_background,
            store,
            _recipe_video_provider(config),
            record["id"],
        )
    return ("REUSED" if reused or fully_reused else "QUEUED"), public


def _commerce_store() -> HomeCommerceStore:
    return HomeCommerceStore(os.getenv("ROXY_HOME_COMMERCE_PATH", "data/roxy_home_commerce.json"))


def _commerce_providers(profile: dict[str, Any], activity: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows = public_providers()
    favorites = {str(name).casefold(): index for index, name in enumerate(profile.get("favorite_retailers") or [])}
    counts = (activity or {}).get("provider_counts") or {}
    rows.sort(
        key=lambda row: (
            favorites.get(str(row["name"]).casefold(), 999),
            not row["configured"],
            -int(counts.get(row["id"], 0)),
            row["name"],
        )
    )
    for row in rows:
        row["handoff_count"] = int(counts.get(row["id"], 0))
    return rows


def _commerce_disclosure(providers: list[dict[str, Any]]) -> str:
    notices = [AFFILIATE_DISCLOSURE]
    for provider in providers:
        notice = str(provider.get("disclosure") or "").strip()
        if provider.get("configured") and notice and notice not in notices:
            notices.append(notice)
    return " ".join(notices)


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


def _with_private_allergy_notes(recipe: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    result = {**recipe, "allergen_notes": list(recipe.get("allergen_notes") or [])}
    allergies = [str(value).strip() for value in ((snapshot.get("profile") or {}).get("allergies") or []) if str(value).strip()]
    if allergies:
        private_note = "Alergias de este hogar: " + ", ".join(allergies) + ". Verifica etiquetas y contaminación cruzada."
        if private_note not in result["allergen_notes"]:
            result["allergen_notes"].append(private_note)
    return result


def _recipe_with_resilience(
    prompt: str,
    snapshot: dict[str, Any],
    *,
    deep: bool,
    recipe_type: str = "general",
) -> tuple[dict[str, Any], str]:
    """Use the curated catalog first and reserve OpenAI for uncommon recipes."""
    local_recipe = find_local_recipe(prompt, snapshot)
    if local_recipe is not None:
        return scale_recipe_payload(local_recipe, requested_servings(prompt)), "local_recipe_catalog"
    shared_recipe = _recipe_library_store().find(prompt, snapshot, recipe_type=recipe_type)
    if shared_recipe is not None:
        return _with_private_allergy_notes(shared_recipe, snapshot), "shared_recipe_library"
    try:
        # Canonical content is generated without any household profile, pantry,
        # name or preference. Only that sanitized base may enter the global DB.
        generated = _home_ai().generate_recipe(
            prompt,
            {"profile": {}, "pantry": []},
            deep=deep,
        )
        if not recipe_is_compatible(generated, snapshot):
            private_recipe = _home_ai().generate_recipe(prompt, snapshot, deep=deep)
            return {
                **scale_recipe_payload(private_recipe, requested_servings(prompt)),
                "shared_recipe_id": "",
                "generation_source": "openai_private",
            }, "openai_private"
        published = _recipe_library_store().publish(
            prompt,
            generated,
            source="openai",
            recipe_type=recipe_type,
        )
        generated = _with_private_allergy_notes({
            **scale_recipe_payload(generated, requested_servings(prompt)),
            "shared_recipe_id": published.get("id") or "",
            "generation_source": "openai",
        }, snapshot)
        return generated, "openai"
    except (HomeAIConfigurationError, HomeAIBudgetExceeded, ValueError, KeyError):
        return scale_recipe_payload(generate_local_recipe(prompt, snapshot), requested_servings(prompt)), "local_recipe_catalog"
    except Exception:
        return scale_recipe_payload(generate_local_recipe(prompt, snapshot), requested_servings(prompt)), "local_recipe_catalog"


def _assistant_shopping_intent(text: str) -> str:
    normalized = text.lower().strip()
    weekly_intent = _assistant_weekly_intent(text)
    if weekly_intent:
        return weekly_intent
    if re.search(r"\b(prepara|preparar|busca|buscar|encuentra|encontrar)\b.*\b(compra|carrito)\b", normalized):
        return "commerce_prepare"
    if re.search(r"\b(agrega|añade|anade|pon|pasa|mete|incluye|echa)\b.*\bingredientes?\b.*\b(lista|carrito)\b", normalized):
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
    natural_recipe_request = bool(
        re.search(r"\b(dame|hazme|prep[aá]ra(?:me)?|ensena(?:me)?|ens[eé]ña(?:me)?)\b", normalized)
        or re.search(r"\b(quiero|quisiera)\b.*\b(hacer|preparar|cocinar)\b", normalized)
    )
    if natural_recipe_request and find_local_recipe(text, {}) is not None:
        return "recipe_generate"
    # People commonly request drinks and desserts without saying "receta"
    # ("dame un mojito", "hazme un flan"). Keep this ahead of shopping
    # mutations, but require a preparation verb so "agrega jugo" continues to
    # mean an item for the shopping list.
    if re.search(
        r"\b(dame|hazme|prep[aá]ra(?:me)?|ensena(?:me)?|ens[eé]ña(?:me)?)\b.*"
        r"\b(bebida|coctel|cóctel|mojito|margarita|daiquiri|limonada|jugo|zumo|"
        r"batido|licuado|smoothie|cafe|café|te|té|chocolate caliente|postre|flan|"
        r"pastel|tarta|galleta|helado)\b",
        normalized,
    ) or re.search(
        r"\b(quiero|quisiera)\b.*\b(hacer|preparar)\b.*"
        r"\b(bebida|coctel|cóctel|mojito|margarita|daiquiri|limonada|jugo|zumo|"
        r"batido|licuado|smoothie|postre|flan|pastel|tarta|galleta|helado)\b",
        normalized,
    ):
        return "recipe_generate"
    if re.search(r"\b(receta|cocinar|cocino|preparar|preparo)\b", normalized):
        return "recipe_generate"
    if re.search(r"\b(quita|quitar|elimina|eliminar|borra|borrar|saca|sacar|remueve|remover|retira|retirar|descarta)\b|\bya no (?:necesito|hace falta)\b", normalized):
        return "shopping_remove"
    if re.search(r"\b(agrega|agregar|añade|anade|apunta|anota|comprar|necesito|pon|mete|incluye|echa|echame|échame|suma|sumale|súmale|trae)\b", normalized):
        return "shopping_add"
    if re.search(r"(lista de compras?|qué falta comprar|que falta comprar|qué necesito comprar|que necesito comprar|qué hay que comprar|que hay que comprar|qué tenemos pendiente|que tenemos pendiente|muéstrame la lista|muestrame la lista)", normalized):
        return "shopping_query"
    return "general"


def _assistant_weekly_intent(text: str) -> str:
    """Recognize ordinary household language before the generic recipe router."""
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized.encode("ascii", "ignore").decode("ascii").lower()).strip()
    if re.search(r"\b(organiza|organizar|crea|crear|prepara|preparar|haz|armar|arma)\b.*\b(plan|semana|menu)\b", normalized):
        return "weekly_create"
    if re.search(r"\b(que comemos|que cenamos|que desayunamos|que toca|comida de|receta de)\b.*\b(hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", normalized):
        return "weekly_recipe" if "receta" in normalized else "weekly_query"
    if re.search(r"\b(hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b.*\b(no cocino|no cocinare|no voy a cocinar|no cocine|no podremos cocinar)\b", normalized):
        return "weekly_from_pantry" if re.search(r"\btengo\b", normalized) else "weekly_skip"
    if re.search(r"\b(no cocino|no cocinare|no voy a cocinar|no cocine|no podremos cocinar)\b.*\b(hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", normalized):
        return "weekly_from_pantry" if re.search(r"\btengo\b", normalized) else "weekly_skip"
    if re.search(r"\b(tengo|nos queda|me queda)\b", normalized) and re.search(r"\b(que hago|que preparo|que cocino|comer|cena|almuerzo|hoy)\b", normalized):
        return "weekly_from_pantry"
    if re.search(r"\b(sobras|sobro|sobraron|comeremos lo de ayer|comemos lo de ayer)\b", normalized):
        return "weekly_leftovers"
    if re.search(r"\b(ya cocine|ya prepare|comida lista|cena lista)\b", normalized):
        return "weekly_cooked"
    if re.search(r"\b(restablece|restaurar|deshaz|deshacer)\b.*\b(hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo|dia)\b", normalized):
        return "weekly_reset"
    return ""


_WEEKDAY_INDEX = {
    "lunes": 0,
    "martes": 1,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sabado": 5,
    "domingo": 6,
}


def _weekly_day_index(text: str, plan: dict[str, Any] | None = None, *, current: date | None = None) -> int:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized.encode("ascii", "ignore").decode("ascii").lower()).strip()
    today = current or date.today()
    target = today + timedelta(days=1 if re.search(r"\bmanana\b", normalized) else 0)
    for label, index in _WEEKDAY_INDEX.items():
        if re.search(rf"\b{label}\b", normalized):
            target = today + timedelta(days=(index - today.weekday()) % 7)
            break
    for day_index, day in enumerate((plan or {}).get("days") or []):
        try:
            if date.fromisoformat(str(day.get("date") or "")) == target:
                return day_index
        except ValueError:
            continue
    # Legacy plans began the following Monday. Their first row is rebased to
    # today by the UI, so conversational commands use the same relative index.
    return min((target - today).days, max(len((plan or {}).get("days") or []) - 1, 0))


def _weekly_meal_type(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized.encode("ascii", "ignore").decode("ascii").lower()).strip()
    if re.search(r"\b(desayuno|desayunar)\b", normalized):
        return "breakfast"
    if re.search(r"\b(almuerzo|comida|almorzar)\b", normalized):
        return "lunch"
    return "dinner"


def _weekly_plan_for_conversation(home_store: HomeFoodStore, user: str) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot = home_store.snapshot(user)
    plans = snapshot.get("weekly_plans") or []
    if plans:
        return plans[-1], snapshot
    settings = snapshot.get("meal_planning") or {}
    plan = create_local_weekly_plan(
        snapshot,
        style=str(settings.get("style") or "normal"),
        people=int(settings.get("people") or (snapshot.get("profile") or {}).get("household_size") or 1),
        max_minutes=int(settings.get("max_minutes") or 25),
        weekly_budget=float(settings.get("weekly_budget") or 85),
        cook_days=int(settings.get("cook_days") or 2),
        meal_scope=str(settings.get("meal_scope") or "all"),
    )
    return home_store.save_weekly_plan(user, plan), snapshot


def _weekly_meal_for_command(plan: dict[str, Any], text: str) -> tuple[int, dict[str, Any], dict[str, Any]]:
    day_index = _weekly_day_index(text, plan)
    days = plan.get("days") or []
    if not days:
        raise ValueError("El plan semanal no tiene días disponibles.")
    day_index = min(day_index, len(days) - 1)
    day = days[day_index]
    meal_type = _weekly_meal_type(text)
    meals = day.get("meals") or []
    meal = next((row for row in meals if row.get("meal_type") == meal_type), None)
    if meal is None and meals:
        meal = meals[-1]
    if meal is None:
        raise ValueError("Ese día no tiene comidas programadas.")
    return day_index, day, meal


def _assistant_shopping_requests(text: str) -> list[dict[str, Any]]:
    cleaned = re.sub(
        r"(?i)^.*?\b(?:agrega(?:r)?|añade|anade|apunta|anota|comprar|necesito|pon|mete|incluye|echa|échame|echame|suma|súmale|sumale|trae|quita(?:r)?|elimina(?:r)?|borra(?:r)?|saca(?:r)?|remueve|remover|retira(?:r)?|descarta)\b\s+",
        "",
        text,
    ).strip()
    cleaned = re.sub(
        r"(?i)\s+(?:a|de|en)\s+(?:mi|la)\s+lista(?:\s+de\s+compras?)?\s*$",
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


def _commerce_owner_key(auth: AuthContext, user: str) -> str:
    # Shopping and pantry stay shared by household, while retailer/brand and
    # budget preferences belong to the authenticated person.
    return f"member:{auth.member_id}" if auth.mode == "member" and auth.member_id else f"legacy:{user}"


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
def health() -> dict[str, str | int]:
    return {"status": "ok", "service": "roxy-home", "video_prompt_version": VIDEO_PROMPT_VERSION}


@app.get("/home", response_class=FileResponse)
@app.get("/lista", response_class=FileResponse)
def shopping_page() -> Response:
    response = FileResponse(ASSETS_DIR / "roxy_list.html", media_type="text/html")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
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


@app.get("/v1/home-food/recipe-photo")
def recipe_photo(title: str, request: Request) -> Response:
    _rate_limit(request)
    clean_title = re.sub(r"\s+", " ", str(title or "")).strip()
    if not clean_title or len(clean_title) > 160:
        raise HTTPException(status_code=422, detail="Nombre de receta inválido")
    try:
        resolved = _recipe_photo_store().resolve(clean_title)
    except (OSError, ValueError):
        resolved = None
    if resolved is None:
        raise HTTPException(status_code=404, detail="Aún no hay una imagen exacta y aprobada para esta receta")
    path, metadata = resolved
    response = FileResponse(path, media_type=str(metadata.get("media_type") or "image/jpeg"))
    response.headers["Cache-Control"] = "public, max-age=2592000, immutable"
    response.headers["X-Roxy-Photo-Source"] = str(metadata.get("provider") or "Roxy Home")[:64]
    return _security_headers(response)


@app.get("/v1/home-food/recipe-photo-info")
def recipe_photo_info(title: str, request: Request) -> Response:
    _rate_limit(request)
    clean_title = re.sub(r"\s+", " ", str(title or "")).strip()
    if not clean_title or len(clean_title) > 160:
        raise HTTPException(status_code=422, detail="Nombre de receta inválido")
    try:
        resolved = _recipe_photo_store().resolve(clean_title)
    except (OSError, ValueError):
        resolved = None
    if resolved is None:
        return _security_headers(JSONResponse({"available": False}))
    _, metadata = resolved
    return _security_headers(
        JSONResponse(
            {
                "available": True,
                "title": str(metadata.get("title") or clean_title),
                "creator": "Roxy Home",
                "license": "Imagen propia",
                "license_url": "",
                "source_url": "",
                "provider": str(metadata.get("provider") or "Roxy Home"),
            }
        )
    )


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
            r"(?i)\s+(?:a|de|en)\s+(?:mi|la)\s+lista(?:\s+de\s+compras?)?\s*$",
            "",
            command_text,
        ).strip()
    agent = (
        "shopping"
        if intent.startswith("shopping_")
        else "home_commerce"
        if intent.startswith("commerce_")
        else "home_food"
        if intent.startswith("recipe_") or intent.startswith("cooking_") or intent.startswith("weekly_")
        else "general"
    )
    store = _store()
    rows: list[dict[str, Any]] = []
    extra: dict[str, Any] = {}
    if intent.startswith("weekly_"):
        home_store = _home_food_store()
        if intent == "weekly_create":
            snapshot = home_store.snapshot(user)
            settings = snapshot.get("meal_planning") or {}
            plan = home_store.save_weekly_plan(
                user,
                create_local_weekly_plan(
                    snapshot,
                    style=str(settings.get("style") or "normal"),
                    people=int(settings.get("people") or (snapshot.get("profile") or {}).get("household_size") or 1),
                    max_minutes=int(settings.get("max_minutes") or 25),
                    weekly_budget=float(settings.get("weekly_budget") or 85),
                    cook_days=int(settings.get("cook_days") or 2),
                    meal_scope=str(settings.get("meal_scope") or "all"),
                ),
            )
            message = "Organicé una nueva semana usando tus preferencias y las recetas disponibles de Roxy. Puedes preguntarme qué toca cualquier día."
            extra["weekly_plan"] = plan
            extra["shopping_preview"] = weekly_plan_shopping_items(plan)
        else:
            plan, food_snapshot = _weekly_plan_for_conversation(home_store, user)
            day_index, day, meal = _weekly_meal_for_command(plan, command_text)
            if intent == "weekly_query":
                meal_labels = ", ".join(
                    f"{ {'breakfast':'desayuno','lunch':'comida','dinner':'cena'}.get(str(row.get('meal_type')), 'comida')}: {row.get('title')}"
                    for row in day.get("meals") or []
                )
                message = f"Para {day.get('day')}, tenemos {meal_labels}."
            elif intent in {"weekly_skip", "weekly_leftovers", "weekly_cooked", "weekly_reset"}:
                action = {
                    "weekly_skip": "skip",
                    "weekly_leftovers": "leftovers",
                    "weekly_cooked": "cooked",
                    "weekly_reset": "reset",
                }[intent]
                updated = update_weekly_plan_day(plan, day_index=day_index, action=action)
                plan = home_store.replace_weekly_plan(user, str(plan["id"]), updated)
                message = {
                    "weekly_skip": f"Entendido. Quité la cocina de {day.get('day')} y reorganicé las comidas siguientes.",
                    "weekly_leftovers": f"Perfecto. Marqué {day.get('day')} como día de sobras y actualicé lo que falta comprar.",
                    "weekly_cooked": f"Perfecto. Marqué la comida de {day.get('day')} como preparada.",
                    "weekly_reset": f"Restablecí {day.get('day')} dentro del plan semanal.",
                }[intent]
            else:
                recipe_prompt = str(meal.get("title") or command_text)
                if intent == "weekly_from_pantry":
                    pantry_match = re.search(r"(?i)\btengo\b\s+(.+)$", command_text)
                    pantry_words = pantry_match.group(1).strip(" .") if pantry_match else command_text
                    recipe_prompt = f"Receta sencilla para hoy con {pantry_words}"
                recipe_data = find_local_recipe(recipe_prompt, food_snapshot)
                generation_mode = "local_recipe_catalog"
                if recipe_data is None:
                    recipe_data, generation_mode = _recipe_with_resilience(recipe_prompt, food_snapshot, deep=False)
                recipe = home_store.save_recipe(user, recipe_data, mode="routine")
                if intent == "weekly_from_pantry":
                    meal_type = str(meal.get("meal_type") or _weekly_meal_type(command_text))
                    replacement = {
                        "key": f"saved:{recipe['id']}",
                        "recipe_id": recipe["id"],
                        "title": recipe["title"],
                        "minutes": int(recipe.get("minutes") or plan.get("max_minutes") or 25),
                        "ingredients": list(recipe.get("ingredients") or []),
                        "favorite": False,
                        "meal_type": meal_type,
                        "servings": recipe.get("servings") or plan.get("people") or 1,
                    }
                    meals = day.get("meals") or []
                    meal_index = next((index for index, row in enumerate(meals) if row is meal), len(meals) - 1)
                    meals[meal_index] = replacement
                    day["status"] = "scheduled"
                    day["status_note"] = "Roxy adaptó esta comida a los ingredientes disponibles en casa."
                    plan = home_store.replace_weekly_plan(user, str(plan["id"]), plan)
                    message = f"Con lo que tienes, adapté la comida de {day.get('day')} a {recipe['title']} y guardé la receta. No añadí nada a compras; puedo decirte qué falta si quieres."
                else:
                    message = f"La receta de {day.get('day')} es {recipe['title']}. Ya la guardé para que puedas abrirla o pedirme que te guíe paso a paso."
                extra["recipe"] = recipe
                extra["generation_mode"] = generation_mode
            extra["weekly_plan"] = plan
            extra["day_index"] = day_index
            extra["shopping_preview"] = weekly_plan_shopping_items(plan)
    elif intent == "commerce_prepare":
        food_snapshot = _home_food_store().snapshot(user)
        use_recipe = bool(re.search(r"\bingredientes?\b|\breceta\b", command_text.lower()))
        if use_recipe:
            recipes = food_snapshot.get("recipes", [])
            if not recipes:
                raise HTTPException(status_code=409, detail="Primero pide o crea una receta.")
            preview = _home_food_store().shopping_preview(user, recipes[-1]["id"])
            raw_items = preview["items"]
            source = "recipe"
            source_title = f"Ingredientes para {preview['title']}"
        else:
            raw_items = store.list_items(user, statuses={"PENDING"}, limit=100)
            source = "shopping"
            source_title = "Lista de compras de Roxy Home"
        if not raw_items:
            raise HTTPException(status_code=409, detail="No hay productos pendientes para preparar.")
        owner_key = _commerce_owner_key(auth, user)
        commerce_store = _commerce_store()
        items = personalize_items(
            raw_items,
            commerce_store.profile(owner_key),
            food_snapshot.get("profile", {}).get("allergies", []),
        )
        providers = _commerce_providers(commerce_store.profile(owner_key))
        preparation = commerce_store.save_preparation(
            owner_key,
            user,
            source=source,
            source_title=source_title,
            items=items,
            providers=[row["id"] for row in providers],
        )
        message = "Preparé los productos para que elijas un comercio y revises la compra. Yo no pagaré ni finalizaré nada por ti."
        extra["preparation"] = preparation
        extra["providers"] = providers
    elif intent == "recipe_generate":
        home_store = _home_food_store()
        # The ElevenLabs client tool currently allows only one second for its
        # response. A remote model can exceed that even when it succeeds, which
        # made the voice agent announce a false failure before the recipe
        # appeared on screen. Voice requests use the curated local catalog so
        # the complete, durable recipe returns inside the tool deadline. The
        # regular recipe screen continues to use OpenAI with resilient fallback.
        recipe_data = generate_local_recipe(command_text, home_store.snapshot(user))
        generation_mode = "voice_local_recipe_catalog"
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
        extra["generation_mode"] = generation_mode
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
                spoken = _personalize(message, auth)
                return {"ok":True,"intent":intent,"agent":agent,"message":spoken,"speech":spoken,"must_speak":True,"data":{"items":[],**extra},"snapshot":store.snapshot(user,limit=100)}
            if intent == "cooking_timer_query":
                detail = home_store.cooking_session_detail(user, active["id"])
                timers = [row for row in detail["session"].get("timers", []) if row.get("status") == "ACTIVE"]
                message = "No hay temporizadores activos." if not timers else "Quedan " + ", ".join(f"{row.get('remaining_seconds',0)//60} minutos y {row.get('remaining_seconds',0)%60} segundos" for row in timers) + "."
                extra["cooking"] = detail
                spoken = _personalize(message, auth)
                return {"ok":True,"intent":intent,"agent":agent,"message":spoken,"speech":spoken,"must_speak":True,"data":{"items":[],**extra},"snapshot":store.snapshot(user,limit=100)}
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
    spoken = _personalize(message, auth)
    return {
        "ok": True,
        "intent": intent,
        "agent": agent,
        "message": spoken,
        "speech": spoken,
        "must_speak": True,
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


@app.get("/v1/home-commerce/{user_id}")
def read_home_commerce(
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _commerce_store()
    owner_key = _commerce_owner_key(auth, user)
    profile = store.profile(owner_key)
    activity = store.activity(owner_key)
    providers = _commerce_providers(profile, activity)
    return {
        "status": "READY",
        "profile": profile,
        "providers": providers,
        "activity": activity,
        "disclosure": _commerce_disclosure(providers),
    }


@app.put("/v1/home-commerce/{user_id}/profile")
def update_home_commerce_profile(
    user_id: str,
    payload: CommerceProfileRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        profile = _commerce_store().update_profile(_commerce_owner_key(auth, user), payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "UPDATED", "profile": profile}


@app.post("/v1/home-commerce/{user_id}/preparations", status_code=201)
def prepare_home_purchase(
    user_id: str,
    payload: CommercePrepareRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    food_snapshot = _home_food_store().snapshot(user)
    if payload.source == "recipe":
        if not payload.recipe_id:
            raise HTTPException(status_code=422, detail="Selecciona una receta para preparar la compra.")
        try:
            source = _home_food_store().shopping_preview(user, payload.recipe_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Receta no encontrada") from exc
        raw_items = source["items"]
        source_title = f"Ingredientes para {source['title']}"
    else:
        raw_items = _store().list_items(user, statuses={"PENDING"}, limit=100)
        source_title = "Lista de compras de Roxy Home"
    if not raw_items:
        raise HTTPException(status_code=409, detail="No hay productos pendientes para preparar.")
    owner_key = _commerce_owner_key(auth, user)
    profile = _commerce_store().profile(owner_key)
    activity = _commerce_store().activity(owner_key)
    provider_rows = _commerce_providers(profile, activity)
    known = {row["id"] for row in provider_rows}
    requested = list(dict.fromkeys(payload.provider_ids)) if payload.provider_ids else [row["id"] for row in provider_rows]
    if not requested or any(provider not in known for provider in requested):
        raise HTTPException(status_code=422, detail="Selecciona proveedores compatibles.")
    items = personalize_items(raw_items, profile, food_snapshot.get("profile", {}).get("allergies", []))
    preparation = _commerce_store().save_preparation(
        owner_key,
        user,
        source=payload.source,
        source_title=source_title,
        items=items,
        providers=requested,
    )
    return {"status": "PREPARED", "preparation": preparation, "providers": provider_rows}


@app.post("/v1/home-commerce/{user_id}/preparations/{preparation_id}/checkout")
def create_home_purchase_link(
    user_id: str,
    preparation_id: str,
    payload: CommerceCheckoutRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    if payload.confirmed is not True:
        raise HTTPException(status_code=409, detail="CONFIRMATION_REQUIRED")
    owner_key = _commerce_owner_key(auth, user)
    try:
        preparation = _commerce_store().preparation(owner_key, preparation_id)
        result = create_purchase_links(payload.provider_id, preparation)
        handoff = _commerce_store().record_handoff(
            owner_key,
            preparation_id,
            provider_id=payload.provider_id,
            provider_name=str(result["provider"]["name"]),
            mode=str(result["mode"]),
            link_count=len(result.get("links") or []),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Preparación no encontrada") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "READY_FOR_REVIEW", "disclosure": AFFILIATE_DISCLOSURE, "handoff": handoff, **result}


@app.get("/v1/home-food/{user_id}")
def read_home_food(user_id: str, request: Request, auth: str = Depends(_authenticate)) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    snapshot = _home_food_store().snapshot(user)
    return {
        **snapshot,
        "local_catalog": local_recipe_catalog_summary(),
        "local_recipes": local_recipe_catalog(snapshot),
        "shared_recipe_library": _recipe_library_store().summary(),
        "recipe_video_service": _recipe_video_public_status(),
        "voice_service": _home_voice_config().public_status(),
    }


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
    recipe_data, generation_mode = _recipe_with_resilience(
        payload.prompt,
        snapshot,
        deep=payload.mode == "deep",
        recipe_type=payload.recipe_type,
    )
    if payload.recipe_type != "general":
        recipe_data = {**recipe_data, "kind": "drink", "drink_type": payload.recipe_type}
    try:
        recipe = store.save_recipe(user, recipe_data, mode=payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Roxy devolvió una receta incompleta.") from exc
    return {"status": "CREATED", "recipe": recipe, "generation_mode": generation_mode}


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


@app.delete("/v1/home-food/{user_id}/recipes/{recipe_id}")
def delete_home_recipe(
    user_id: str,
    recipe_id: str,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        recipe = _home_food_store().delete_recipe(user, recipe_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Receta no encontrada") from exc
    return {"status": "DELETED", "recipe": recipe}


@app.get("/v1/home-food/{user_id}/recipes/{recipe_id}/video")
def read_home_recipe_video(
    user_id: str,
    recipe_id: str,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        recipe = _home_food_store().get_recipe(user, recipe_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Receta no encontrada") from exc
    config = _recipe_video_config()
    video = _recipe_video_store().find_for_recipe(user, recipe)
    return {"status": "READY" if video and video.get("status") == "READY" else "AVAILABLE", "video": video, "service": _recipe_video_public_status()}


@app.post("/v1/home-food/{user_id}/recipes/{recipe_id}/video", status_code=202)
def create_home_recipe_video(
    user_id: str,
    recipe_id: str,
    payload: RecipeVideoRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        recipe = _home_food_store().get_recipe(user, recipe_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Receta no encontrada") from exc
    config = _recipe_video_config()
    store = _recipe_video_store()
    existing = store.find_for_recipe(user, recipe)
    if existing:
        existing["reused"] = True
        return {"status": "REUSED", "video": existing, "service": _recipe_video_public_status()}
    estimated_cost = store.estimated_generation_cost(recipe, config)
    if estimated_cost > 0 and not config.configured:
        raise HTTPException(
            status_code=503,
            detail="La videoteca no cubre todavía todos estos pasos y el generador no está disponible.",
        )
    if payload.confirmed is not True and estimated_cost > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CONFIRMATION_REQUIRED",
                "estimated_cost_usd": estimated_cost,
                "message": "Confirma antes de generar. Roxy reutilizará este video después.",
            },
        )
    if estimated_cost > 0 and store.monthly_reserved_usd() + estimated_cost > config.monthly_budget_usd:
        raise HTTPException(status_code=429, detail="Se alcanzó el presupuesto mensual de videos de Roxy Home.")
    record, reused = store.create_or_reuse(user, recipe, config, visibility=payload.visibility)
    fully_reused = record.get("status") == "READY"
    if not reused and not fully_reused:
        try:
            record = submit_recipe_video(store, _recipe_video_provider(config), record["id"])
        except ConnectionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    public = store._public(record, user)
    public["reused"] = reused
    return {"status": "REUSED" if reused or fully_reused else "PROCESSING", "video": public, "service": _recipe_video_public_status()}


@app.post("/v1/home-food/{user_id}/recipe-videos/{video_id}/sync")
def sync_home_recipe_video(
    user_id: str,
    video_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _recipe_video_store()
    try:
        record = store.accessible_internal(user, video_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Video no encontrado") from exc
    if record.get("owner_user_id") != user and record.get("status") != "READY":
        raise HTTPException(status_code=403, detail="Este video pertenece a otro hogar.")
    config = _recipe_video_config()
    if record.get("status") not in {"REVIEW", "READY", "FAILED", "REJECTED"} and not config.configured:
        raise HTTPException(status_code=503, detail="El proveedor de videos no está disponible.")
    if record.get("status") not in {"REVIEW", "READY", "FAILED", "REJECTED"}:
        record = sync_recipe_video(store, _recipe_video_provider(config), config, video_id)
    return {"status": record.get("status"), "video": store._public(record, user)}


@app.post("/v1/home-food/{user_id}/recipe-videos/{video_id}/review")
def review_home_recipe_video(
    user_id: str,
    video_id: str,
    payload: RecipeVideoReviewRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    config = _recipe_video_config()
    supplied = str(request.headers.get("X-Roxy-Video-Admin-Key") or "")
    if not config.admin_key or not hmac.compare_digest(supplied, config.admin_key):
        raise HTTPException(status_code=403, detail="Revisión administrativa requerida.")
    try:
        record = _recipe_video_store().approve(video_id, approved=payload.approved, notes=payload.notes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Video no encontrado") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": record.get("status"), "video": _recipe_video_store()._public(record, user)}


@app.get("/v1/home-food/{user_id}/recipe-videos/{video_id}/clips/{clip_index}", response_class=FileResponse)
def read_home_recipe_video_clip(
    user_id: str,
    video_id: str,
    clip_index: int,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> Response:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _recipe_video_store()
    try:
        record = store.accessible_internal(user, video_id)
        clips = record.get("clips") or []
        clip = clips[clip_index] if 0 <= clip_index < len(clips) else None
        if not clip or not clip.get("media_path"):
            raise KeyError(video_id)
        media_path = Path(str(clip["media_path"])).resolve()
        media_path.relative_to(_recipe_video_config().media_dir.resolve())
        if not media_path.is_file():
            raise KeyError(video_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Clip no encontrado") from exc
    response = FileResponse(
        media_path,
        media_type="video/mp4",
        filename=f"roxy-{video_id}-{clip_index + 1}.mp4",
        content_disposition_type="inline",
    )
    response.headers["Cache-Control"] = (
        "public, max-age=86400" if record.get("visibility") == "shared" and record.get("status") == "READY" else "private, no-store"
    )
    return _security_headers(response)


@app.post("/v1/home-food/{user_id}/recipes/{recipe_id}/cooking-sessions", status_code=201)
def start_home_cooking_session(
    user_id: str,
    recipe_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _home_food_store()
    try:
        session = store.start_cooking_session(user, recipe_id)
        detail = store.cooking_session_detail(user, session["id"])
        video_status, video = _queue_recipe_video_for_cooking(user, detail["recipe"], background_tasks)
        return {
            "status": "STARTED",
            **detail,
            "recipe_video_status": video_status,
            "recipe_video": video,
        }
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


@app.post("/v1/home-food/{user_id}/cooking-sessions/{session_id}/speech", response_class=FileResponse)
def speak_home_cooking_step(user_id: str, session_id: str, request: Request, auth: str = Depends(_authenticate)) -> Response:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        detail = _home_food_store().cooking_session_detail(user, session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Sesión de cocina no encontrada") from exc
    text = "Receta terminada. Buen provecho." if detail["session"].get("status") == "COMPLETED" else f"Paso {detail['step_number']}. {detail['current_step']}"
    config = _home_voice_config()
    if not config.configured:
        raise HTTPException(status_code=503, detail="Falta conectar la voz oficial de Roxy Home")
    try:
        audio_path = ElevenLabsHomeVoice(config).synthesize(text, user_id=user)
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="No se pudo generar la voz oficial de Roxy") from exc
    return FileResponse(audio_path, media_type="audio/mpeg", filename="roxy-paso.mp3", headers={"Cache-Control": "private, max-age=31536000, immutable"})


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
    payload: WeeklyPlanRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _home_food_store()
    result = create_local_weekly_plan(
        store.snapshot(user),
        style=payload.style,
        people=payload.people,
        max_minutes=payload.max_minutes,
        weekly_budget=payload.weekly_budget,
        cook_days=payload.cook_days,
        meal_scope=payload.meal_scope,
    )
    try:
        planning = store.update_meal_planning(user, **payload.model_dump())
        plan = store.save_weekly_plan(user, result)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Roxy devolvió un plan incompleto.") from exc
    return {"status": "CREATED", "plan": plan, "meal_planning": planning}


@app.post("/v1/home-food/{user_id}/weekly-plans/{plan_id}/shopping-commit")
def commit_home_weekly_plan_shopping(
    user_id: str,
    plan_id: str,
    payload: WeeklyPlanShoppingRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    if payload.confirmed is not True:
        raise HTTPException(status_code=409, detail="CONFIRMATION_REQUIRED")
    try:
        plan = _home_food_store().get_weekly_plan(user, plan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plan semanal no encontrado") from exc
    items = weekly_plan_shopping_items(plan, {index for index in payload.excluded_days if 0 <= index <= 6})
    added = [
        _store().add(
            user,
            row["name"],
            quantity=row["quantity"],
            unit=row["unit"],
            category="FOOD",
            notes="Plan semanal de Roxy Home",
            source="roxy_home_weekly_plan",
        )
        for row in items
    ]
    return {"status": "ADDED", "plan_id": plan_id, "items": added}


@app.patch("/v1/home-food/{user_id}/weekly-plans/{plan_id}/meal")
def change_home_weekly_plan_meal(
    user_id: str,
    plan_id: str,
    payload: WeeklyPlanMealRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _home_food_store()
    try:
        plan = store.get_weekly_plan(user, plan_id)
        updated = update_weekly_plan_meal(
            plan,
            store.snapshot(user),
            day_index=payload.day_index,
            meal_index=payload.meal_index,
            action=payload.action,
        )
        saved = store.replace_weekly_plan(user, plan_id, updated)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plan semanal no encontrado") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "UPDATED", "plan": saved}


@app.patch("/v1/home-food/{user_id}/weekly-plans/{plan_id}/day")
def change_home_weekly_plan_day(
    user_id: str,
    plan_id: str,
    payload: WeeklyPlanDayRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _home_food_store()
    try:
        plan = store.get_weekly_plan(user, plan_id)
        updated = update_weekly_plan_day(plan, day_index=payload.day_index, action=payload.action)
        saved = store.replace_weekly_plan(user, plan_id, updated)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plan semanal no encontrado") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    preview = weekly_plan_shopping_items(saved)
    return {"status": "UPDATED", "plan": saved, "shopping_preview": preview}


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
