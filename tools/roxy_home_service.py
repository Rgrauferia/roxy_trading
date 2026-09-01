from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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
    exact_local_recipe,
    find_local_recipe,
    generate_local_recipe,
    local_recipe_catalog,
    local_recipe_by_key,
    local_recipe_catalog_summary,
)
from roxy_os.home_recipe_editorial import recipe_quality_issues
from roxy_os.home_recipe_library import (
    HomeRecipeLibraryStore,
    recipe_is_compatible,
    requested_servings,
    scale_recipe_payload,
)
from roxy_os.home_recipe_photos import (
    RecipePhotoGenerationConfig,
    RecipePhotoGenerationQueue,
    RecipePhotoStore,
)
from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_calendar import DEFAULT_TIMEZONE, HomeCalendarStore, parse_calendar_command
from roxy_os.home_calendar_google import GoogleCalendarConfig, GoogleCalendarSync
from roxy_os.home_commerce import (
    AFFILIATE_DISCLOSURE,
    HomeCommerceStore,
    create_purchase_links,
    personalize_items,
    public_providers,
)
from roxy_os.home_conversation import HomeConversationStore
from roxy_os.home_daily import build_home_daily_brief
from roxy_os.home_design import HomeDesignGenerator, HomeDesignStore, public_project
from roxy_os.home_family import HomeFamilyStore
from roxy_os.home_plants import HomePlantIdentifier, HomePlantStore, PLANT_CATALOG, public_plant
from roxy_os.home_product_intelligence import HomeProductIntelligence, ProductIntelligenceConfig
from roxy_os.home_food import HomeFoodStore, HomePermissionPolicy
from roxy_os.home_pet_catalog import pet_profile_completion, personalized_pet_care_plan, personalized_pet_nutrition_plan, personalized_pet_products, pet_profile_options
from roxy_os.home_price_recommendations import (
    PRICE_NOTICE,
    PriceFeedConfig,
    fetch_nearby_retailers,
    fetch_price_offers,
    recommend_prices,
)
from roxy_os.home_weekly_plans import (
    MEALS,
    create_local_weekly_plan,
    update_weekly_plan_day,
    update_weekly_plan_meal,
    weekly_plan_shopping_items,
)
from roxy_os.home_weather import HomeWeatherConfig, answer_weather_query, geocode_place, forecast_location, weather_for_profile
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
    price_alerts_enabled: bool = True
    price_drop_percent: int = Field(default=10, ge=5, le=50)
    location_enabled: bool = False
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_accuracy_m: float | None = Field(default=None, ge=0, le=100_000)


class CommercePrepareRequest(BaseModel):
    source: str = Field(default="shopping", pattern="^(shopping|recipe)$")
    recipe_id: str | None = Field(default=None, max_length=64)
    provider_ids: list[str] = Field(default_factory=list, max_length=10)


class CommerceCheckoutRequest(BaseModel):
    provider_id: str = Field(min_length=1, max_length=32)
    confirmed: bool = False


class ProductLookupRequest(BaseModel):
    barcode: str = Field(default="", max_length=32)
    query: str = Field(default="", max_length=160)


class HomeDesignProjectRequest(BaseModel):
    name: str = Field(default="", max_length=80)
    room_type: str = Field(pattern="^(living_room|bedroom|dining_room|kitchen|bathroom|office|patio|other)$")
    style: str = Field(pattern="^(warm_modern|minimal|natural|classic|bohemian|industrial|coastal|surprise_me)$")
    budget: float = Field(default=500, ge=0, le=100_000)
    measurements: str = Field(default="", max_length=500)
    keep_items: list[str] = Field(default_factory=list, max_length=20)
    priorities: list[str] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=1200)
    photo_data_url: str = Field(min_length=32, max_length=8_100_000)


class HomeDesignCommerceRequest(BaseModel):
    product_ids: list[str] = Field(default_factory=list, max_length=20)
    provider_ids: list[str] = Field(default_factory=list, max_length=10)
    tier: str = Field(default="balanced", pattern="^(economy|balanced|complete)$")


class HomeDesignProposalRequest(BaseModel):
    tier: str = Field(default="balanced", pattern="^(economy|balanced|complete)$")


class HomeDesignRevisionRequest(HomeDesignProposalRequest):
    instruction: str = Field(min_length=2, max_length=500)


class HomeDesignFitRequest(BaseModel):
    wall_width: float = Field(default=0, ge=0, le=2_000)
    passage_width: float = Field(default=0, ge=0, le=2_000)
    max_depth: float = Field(default=0, ge=0, le=2_000)


class HomePlantIdentifyRequest(BaseModel):
    photo_data_url: str = Field(min_length=32, max_length=8_100_000)


class HomeFamilyLocationRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=100_000)
    altitude_m: float | None = Field(default=None, ge=-500, le=20_000)
    speed_mps: float | None = Field(default=None, ge=0, le=120)
    heading_deg: float | None = Field(default=None, ge=0, le=360)
    recorded_at: str | None = Field(default=None, max_length=40)
    consent: bool = False


class HomeFamilyPlaceRequest(BaseModel):
    name: str = Field(default="", max_length=60)
    kind: str = Field(default="OTHER", pattern="^(HOME|WORK|STORE|OTHER)$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_m: float = Field(default=200, ge=50, le=1000)


class HomeFamilyProfileRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    marker_color: str = Field(default="FOREST", pattern="^(FOREST|GOLD|OCEAN|TERRACOTTA|PLUM|SLATE)$")
    photo_data_url: str = Field(default="", max_length=400_000)
    profile_emoji: str = Field(default="", max_length=8)


class HomeFamilyInvitationRequest(BaseModel):
    display_name: str = Field(default="", max_length=80)
    relationship: str = Field(default="Persona de confianza", max_length=40)


class HomeFamilyInvitationRedeemRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class HomePlantCreateRequest(BaseModel):
    display_name: str = Field(default="", max_length=60)
    species_key: str = Field(default="unknown", max_length=40)
    room: str = Field(default="", max_length=60)
    placement: str = Field(default="indoor", pattern="^(indoor|outdoor)$")
    pot_type: str = Field(default="unknown", max_length=30)
    drainage: bool = False
    light_exposure: str = Field(default="unknown", pattern="^(unknown|low|indirect|bright_indirect|direct_morning|direct_afternoon)$")
    notes: str = Field(default="", max_length=800)
    photo_data_url: str = Field(min_length=32, max_length=8_100_000)


class HomePlantUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=60)
    species_key: str | None = Field(default=None, max_length=40)
    room: str | None = Field(default=None, max_length=60)
    placement: str | None = Field(default=None, pattern="^(indoor|outdoor)$")
    pot_type: str | None = Field(default=None, max_length=30)
    drainage: bool | None = None
    light_exposure: str | None = Field(default=None, pattern="^(unknown|low|indirect|bright_indirect|direct_morning|direct_afternoon)$")
    notes: str | None = Field(default=None, max_length=800)


class HomePlantTaskCompleteRequest(BaseModel):
    observation: str = Field(default="", max_length=300)


class HomePlantJournalRequest(BaseModel):
    notes: str = Field(default="", max_length=600)
    photo_data_url: str = Field(default="", max_length=16_100_000)


class HomePlantVacationRequest(BaseModel):
    enabled: bool = False
    starts_on: str = Field(default="", max_length=10)
    ends_on: str = Field(default="", max_length=10)
    caregiver: str = Field(default="", max_length=80)
    notes: str = Field(default="", max_length=500)


class HomePlantReminderRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)
    time: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    reminder_minutes: int = Field(default=60, ge=0, le=43_200)


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
    catalog_key: str = Field(default="", max_length=120)


class RecipeImportRequest(BaseModel):
    source_type: str = Field(pattern="^(image|url)$")
    source: str = Field(min_length=1, max_length=2_100_000)
    audience: str = Field(default="human", pattern="^(human|pet)$")
    pet_species: str = Field(default="", max_length=32)


class RecipeImportCommitRequest(BaseModel):
    recipe: dict[str, Any]
    confirmed: bool = False


class PetProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    species: str = Field(pattern="^(dog|cat|ferret|rabbit|guinea_pig|hamster|small_mammal|bird|fish|reptile|amphibian|invertebrate|farm_pet|other)$")
    exact_species: str = Field(default="", max_length=100)
    breed: str = Field(default="", max_length=100)
    age_years: float | None = Field(default=None, ge=0, le=200)
    weight_kg: float | None = Field(default=None, gt=0, le=2_000)
    life_stage: str = Field(default="unknown", pattern="^(baby|young|adult|senior|unknown)$")
    sex: str = Field(default="unknown", pattern="^(female|male|unknown)$")
    sterilized: str = Field(default="unknown", pattern="^(yes|no|unknown)$")
    size_class: str = Field(default="unknown", pattern="^(toy|small|medium|large|giant|unknown)$")
    activity_level: str = Field(default="unknown", pattern="^(low|moderate|high|working|unknown)$")
    body_condition: str = Field(default="unknown", pattern="^(underweight|ideal|overweight|unknown)$")
    goals: list[str] = Field(default_factory=list, max_length=30)
    allergies: list[str] = Field(default_factory=list, max_length=30)
    conditions: list[str] = Field(default_factory=list, max_length=30)
    current_food: str = Field(default="", max_length=160)
    current_food_kind: str = Field(default="unknown", pattern="^(complete|veterinary|complementary|unknown)$")
    feeding_amount: float | None = Field(default=None, gt=0, le=100_000)
    feeding_unit: str = Field(default="", max_length=32)
    feeding_frequency: int = Field(default=0, ge=0, le=24)
    feeding_times: list[str] = Field(default_factory=list, max_length=24)
    feeding_amount_source: str = Field(default="unknown", pattern="^(label|veterinarian|specialist|unknown)$")
    feeding_notes: str = Field(default="", max_length=1_000)
    veterinarian_instructions: str = Field(default="", max_length=2_000)
    habitat_type: str = Field(default="", max_length=100)
    environment_notes: str = Field(default="", max_length=1_000)
    routine_notes: str = Field(default="", max_length=1_000)
    photo_data_url: str = Field(default="", max_length=1_500_000)


class PetMedicalRecordRequest(BaseModel):
    occurred_on: date | None = None
    record_type: str = Field(default="note", pattern="^(checkup|vaccine|diagnosis|treatment|surgery|lab|allergy|medication|weight|note)$")
    title: str = Field(min_length=1, max_length=120)
    provider: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=2_000)
    medications: list[str] = Field(default_factory=list, max_length=30)
    next_due_on: date | None = None
    weight_kg: float | None = Field(default=None, gt=0, le=2_000)
    attachment_name: str = Field(default="", max_length=120)
    attachment_type: str = Field(default="", max_length=40)
    attachment_data_url: str = Field(default="", max_length=1_500_000)


class PetCareCompletionRequest(BaseModel):
    routine_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_\-]+$")
    title: str = Field(min_length=1, max_length=120)
    outcome: str = Field(default="completed", pattern="^(completed|all|partial|refused)$")
    notes: str = Field(default="", max_length=500)


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


class HomePersonalizationRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=64)
    household_name: str | None = Field(default=None, min_length=1, max_length=64)
    theme: str = Field(default="classic", pattern="^(classic|olive|coastal|terracotta)$")
    background: str = Field(default="plant", pattern="^(plant|linen|clean|warm)$")
    avatar: str = Field(default="home", pattern="^(home|professional|monogram)$")
    response_style: str = Field(default="balanced", pattern="^(balanced|brief|close|explanatory)$")
    text_scale: str = Field(default="standard", pattern="^(compact|standard|large)$")


class CalendarEventRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    starts_at: datetime
    ends_at: datetime
    timezone: str = Field(default="America/New_York", min_length=1, max_length=64)
    category: str = Field(default="PERSONAL", pattern="^(PERSONAL|WORK|FAMILY|SCHOOL|APPOINTMENTS|HOME)$")
    reminder_minutes: int = Field(default=60, ge=0, le=43_200)
    location: str = Field(default="", max_length=240)
    notes: str = Field(default="", max_length=2000)
    participants: list[str] = Field(default_factory=list, max_length=50)
    recurrence: str = Field(default="NONE", pattern="^(NONE|DAILY|WEEKLY|WEEKDAYS)$")
    recurrence_until: date | None = None
    all_day: bool = False


class CalendarDraftRequest(CalendarEventRequest):
    confirmed: bool = False


class CalendarConfirmRequest(BaseModel):
    draft_id: str = Field(min_length=1, max_length=64)
    confirmed: bool = False


@dataclass(frozen=True)
class AuthContext:
    mode: str
    storage_user_id: str | None = None
    member_id: str | None = None


def _store() -> ShoppingListStore:
    return ShoppingListStore(os.getenv("ROXY_SHOPPING_LIST_PATH", "data/roxy_shopping_list.json"))


def _product_intelligence() -> HomeProductIntelligence:
    return HomeProductIntelligence(ProductIntelligenceConfig.from_env())


def _home_food_store() -> HomeFoodStore:
    return HomeFoodStore(os.getenv("ROXY_HOME_MEMORY_PATH", "data/roxy_home_food.json"))


def _recipe_library_store() -> HomeRecipeLibraryStore:
    return HomeRecipeLibraryStore(
        os.getenv("ROXY_HOME_RECIPE_LIBRARY_PATH", "data/roxy_home_recipe_library.sqlite")
    )


_RECIPE_PHOTO_STORES: dict[str, RecipePhotoStore] = {}
_RECIPE_PHOTO_QUEUES: dict[str, RecipePhotoGenerationQueue] = {}
_RECIPE_PHOTO_QUEUE_LOCK = threading.Lock()


def _all_recipe_photo_rows() -> list[dict[str, Any]]:
    rows = [
        *local_recipe_catalog({"profile": {"allergies": []}}),
        *(
            {**meal, "kind": "meal", "description": f"Resultado final de {meal.get('title') or 'la receta'}"}
            for meal in MEALS.values()
            if meal.get("title")
        ),
        *_home_food_store().all_saved_recipes(),
    ]
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for recipe in rows:
        title = re.sub(r"\s+", " ", str(recipe.get("title") or "")).strip()
        key = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii").casefold()
        if title and key not in seen:
            seen.add(key)
            unique.append(recipe)
    return unique


def _recipe_photo_store() -> RecipePhotoStore:
    path = os.getenv("ROXY_HOME_RECIPE_PHOTO_DIR", "data/roxy_home_recipe_photos")
    if path not in _RECIPE_PHOTO_STORES:
        _RECIPE_PHOTO_STORES[path] = RecipePhotoStore(path)
    return _RECIPE_PHOTO_STORES[path]


def _recipe_photo_queue() -> RecipePhotoGenerationQueue:
    path = os.getenv("ROXY_HOME_RECIPE_PHOTO_DIR", "data/roxy_home_recipe_photos")
    with _RECIPE_PHOTO_QUEUE_LOCK:
        if path not in _RECIPE_PHOTO_QUEUES:
            queue = RecipePhotoGenerationQueue(
                _recipe_photo_store(), RecipePhotoGenerationConfig.from_env()
            )
            _RECIPE_PHOTO_QUEUES[path] = queue
            queue.prewarm(_all_recipe_photo_rows())
    return _RECIPE_PHOTO_QUEUES[path]


def _schedule_recipe_photo(recipe: dict[str, Any]) -> str:
    """Keep optional artwork generation from blocking core recipe actions."""
    try:
        return _recipe_photo_queue().schedule(recipe)
    except (OSError, RuntimeError):
        return "UNAVAILABLE"


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


def _design_store() -> HomeDesignStore:
    return HomeDesignStore(
        os.getenv("ROXY_HOME_DESIGN_PATH", "data/roxy_home_design.json"),
        os.getenv("ROXY_HOME_DESIGN_IMAGE_DIR", "data/roxy_home_design"),
    )


def _plant_store() -> HomePlantStore:
    return HomePlantStore(
        os.getenv("ROXY_HOME_PLANTS_PATH", "data/roxy_home_plants.json"),
        os.getenv("ROXY_HOME_PLANTS_IMAGE_DIR", "data/roxy_home_plants"),
    )


def _family_store() -> HomeFamilyStore:
    return HomeFamilyStore(os.getenv("ROXY_HOME_FAMILY_PATH", "data/roxy_home_family.json"))


def _generate_home_design(owner_key: str, project_id: str) -> None:
    store = _design_store()
    try:
        project = store.project(owner_key, project_id)
        result = HomeDesignGenerator.from_env().generate(project)
        store.save_proposal(owner_key, project_id, result)
    except Exception:
        # Provider details and secrets must never be persisted or returned.
        store.mark_failed(owner_key, project_id)


def _calendar_store() -> HomeCalendarStore:
    return HomeCalendarStore(os.getenv("ROXY_HOME_CALENDAR_PATH", "data/roxy_home_calendar.json"))


def _calendar_google() -> GoogleCalendarSync:
    return GoogleCalendarSync(GoogleCalendarConfig.from_env())


def _sync_calendar_event(owner: str, event: dict[str, Any]) -> dict[str, Any]:
    try:
        if event.get("deleted"):
            return _calendar_google().delete_event(owner, str(event.get("id") or ""))
        return _calendar_google().upsert_event(owner, event)
    except Exception as exc:
        return {"synced": False, "reason": "provider_error", "message": str(exc)[:240]}


def _commerce_providers(
    profile: dict[str, Any],
    activity: dict[str, Any] | None = None,
    *,
    context: str = "shopping",
) -> list[dict[str, Any]]:
    rows = public_providers()
    rows = [row for row in rows if context == "design" or not row.get("design_only")]
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


def _conversation_store() -> HomeConversationStore:
    configured_path = str(os.getenv("ROXY_HOME_CONVERSATION_PATH") or "").strip()
    if not configured_path:
        state_path = os.getenv("ROXY_SHOPPING_LIST_PATH") or os.getenv("ROXY_HOME_MEMORY_PATH", "data/roxy_home_food.json")
        configured_path = str(
            Path(state_path).with_name(
                "roxy_home_conversations.json"
            )
        )
    return HomeConversationStore(
        configured_path,
        max_turns=int(os.getenv("ROXY_HOME_CONVERSATION_MAX_TURNS", "12")),
    )


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
    strict_editorial = str(os.getenv("ROXY_HOME_REQUIRE_VERIFIED_RECIPES") or "0").strip().lower() in {"1", "true", "yes", "on"}
    local_recipe = find_local_recipe(prompt, snapshot)
    if local_recipe is not None and (
        not strict_editorial or str(local_recipe.get("editorial_status") or "").startswith("verified")
    ):
        return scale_recipe_payload(local_recipe, requested_servings(prompt)), "local_recipe_catalog"
    shared_recipe = _recipe_library_store().find(prompt, snapshot, recipe_type=recipe_type)
    if shared_recipe is not None and (
        not strict_editorial or str(shared_recipe.get("editorial_status") or "").startswith("verified")
    ):
        return _with_private_allergy_notes(shared_recipe, snapshot), "shared_recipe_library"
    try:
        # Canonical content is generated without any household profile, pantry,
        # name or preference. Only that sanitized base may enter the global DB.
        expected_title = str((local_recipe or {}).get("title") or prompt).strip()
        generated = (
            _home_ai().curate_recipe(expected_title, {"profile": {}, "pantry": []})
            if strict_editorial
            else _home_ai().generate_recipe(prompt, {"profile": {}, "pantry": []}, deep=deep)
        )
        if strict_editorial:
            issues = recipe_quality_issues(generated, expected_title)
            if issues:
                raise ValueError("La revisión editorial rechazó la receta: " + " ".join(issues))
            generated = {**generated, "editorial_status": "verified_with_sources"}
        if not recipe_is_compatible(generated, snapshot):
            private_recipe = (
                _home_ai().curate_recipe(expected_title, snapshot)
                if strict_editorial
                else _home_ai().generate_recipe(prompt, snapshot, deep=deep)
            )
            if strict_editorial:
                issues = recipe_quality_issues(private_recipe, expected_title)
                if issues:
                    raise ValueError("La revisión editorial rechazó la variante privada: " + " ".join(issues))
                private_recipe = {**private_recipe, "editorial_status": "verified_with_sources"}
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
        if strict_editorial:
            raise
        return scale_recipe_payload(generate_local_recipe(prompt, snapshot), requested_servings(prompt)), "local_recipe_catalog"
    except Exception:
        if strict_editorial:
            raise
        return scale_recipe_payload(generate_local_recipe(prompt, snapshot), requested_servings(prompt)), "local_recipe_catalog"


def _assistant_shopping_intent(text: str) -> str:
    normalized = text.lower().strip()
    plain = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")
    if re.search(r"\bcuando\s+(?:yo\s+)?digo\b.+\b(?:me\s+refiero\s+a|quiero\s+decir|significa)\b", plain):
        return "shopping_teach_alias"
    if re.fullmatch(r"(?:(?:si|sí)(?:,?\s+confirmo)?|confirmo|confirmar|confirmalo|confírmalo|hazlo|correcto)[.! ]*", normalized):
        return "calendar_confirm"
    if re.fullmatch(r"(?:no|cancelar|cancelalo|cancélalo|olvidalo|olvídalo)[.! ]*", normalized):
        return "calendar_discard"
    if (
        re.search(r"\b(clima|pronostico|weather|temperatura|lluvia|llover|llovera|soleado|nublado|tormenta|huracan)\b", plain)
        or re.search(r"\b(que|como)\s+(?:tiempo|dia)\s+(?:hace|hara|estara)\b", plain)
        or re.search(r"\b(probabilidad|posibilidad)\b.*\b(lluvia|llover|tormenta)\b", plain)
    ):
        return "weather_query"
    if re.search(r"\b(que tengo hoy|que hay hoy|resumen de hoy|como esta mi dia|que es importante hoy)\b", plain):
        return "daily_query"
    if re.search(r"\b(que tengo|mi agenda|mis eventos|mis citas|que hay)\b.*\b(hoy|manana|semana|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", plain):
        return "calendar_query"
    if re.search(r"\b(cancela|cancelar|elimina|eliminar|borra|borrar)\b.*\b(evento|cita|reunion|llamada|calendario|agenda)\b", plain):
        return "calendar_cancel"
    if (
        re.search(r"\b(agenda|agendar|programa|programar|crea|crear|anade|agrega|pon)\b.*\b(evento|cita|reunion|llamada|calendario|escuela|dentista|medico)\b", plain)
        or re.search(r"\b(?:evento\s+en|al|en\s+el|para\s+el)\s+(?:mi\s+)?(?:calendario|agenda)\b", plain)
        or re.search(r"\b(?:calendario|agenda)\b.*\b(?:hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo|a\s+las?)\b", plain)
        or re.search(r"\b(dentista|medico|cita|reunion|llamada)\b.*\b(hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo|\d{1,2})\b", plain)
        or re.search(r"\b(llevar|recoger)\b.*\b(escuela|colegio|veterinario|medico|dentista)\b", plain)
        or re.search(r"\b(?:hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b.*\b(?:a\s+las?|\d{1,2}:\d{2})\b.*\b(?:trabajar|trabajo|turno|veterinario|dentista|medico|cita|reunion|llamada)\b", plain)
    ):
        return "calendar_create"
    if re.search(r"\b(que hay|que tengo|inventario|muestrame|revisa)\b.*\b(despensa|alacena)\b", plain):
        return "pantry_query"
    if (
        re.search(r"\b(se acabo|se terminaron|no queda|quita|elimina|borra|saca)\b.*\b(despensa|alacena)\b", plain)
        or re.search(r"\b(se acabo|se terminaron|ya no queda)\b", plain)
    ):
        return "pantry_remove"
    if (
        re.search(r"\b(compre|compramos|acabo de comprar)\b", plain)
        or re.search(r"\b(guarda|registra|anota|agrega|pon)\b.*\b(despensa|alacena)\b", plain)
    ):
        return "pantry_add"
    weekly_intent = _assistant_weekly_intent(text)
    if weekly_intent:
        return weekly_intent
    if re.search(r"\b(donde|dónde|compara|comparar|economico|económico|barato|precio|precios|oferta|ofertas)\b.*\b(comprar|compra|producto|productos|lista|tienda|comercio|walmart|amazon|instacart)\b", normalized):
        return "commerce_compare"
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


def _assistant_product_alias(text: str) -> tuple[str, str] | None:
    match = re.search(
        r"(?is)\bcuando\s+(?:yo\s+)?digo\s+(.+?)\s*,?\s*(?:me\s+refiero\s+a|quiero\s+decir|significa)\s+(.+?)\s*[.!?]*$",
        str(text or "").strip(),
    )
    if not match:
        return None
    phrase = " ".join(match.group(1).strip(" \"'.,:;-").split())[:120]
    canonical = " ".join(match.group(2).strip(" \"'.,:;-").split())[:120]
    return (phrase, canonical) if phrase and canonical else None


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
    if re.search(r"\b(que podemos cocinar|que cocinar|que preparo)\b.*\b(lo que hay|despensa|alacena)\b", normalized):
        return "weekly_from_pantry"
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


def _plain_home_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"[^a-z0-9]+", " ", normalized.encode("ascii", "ignore").decode("ascii").lower()).strip()


def _looks_like_calendar_statement(value: Any) -> bool:
    """Fail closed before a sentence is allowed to become a shopping item."""
    plain = _plain_home_text(value)
    has_schedule_word = bool(re.search(
        r"\b(calendario|agenda|evento|cita|reunion|llamada|veterinario|dentista|medico|turno)\b",
        plain,
    ))
    has_time = bool(re.search(
        r"\b(hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo|a las?|\d{1,2}:\d{2}|[ap] m)\b",
        plain,
    ))
    is_errand = bool(re.search(r"\b(llevar|recoger|trabajar|trabajo)\b", plain))
    return "calendario" in plain or "agenda" in plain or (has_schedule_word and has_time) or (is_errand and has_time)


_SHOPPING_AMBIGUITIES: tuple[dict[str, Any], ...] = (
    {
        "pattern": r"^(?:la\s+)?pasta(?:s)?$",
        "question": "¿Te refieres a un tubo de pasta dental o a pasta para comer?",
        "options": (
            {"name": "Pasta dental", "unit": "tubo", "aliases": ("dental", "dientes", "dentifrico", "la de dientes", "pasta dental", "primera", "primero", "opcion 1")},
            {"name": "Pasta", "unit": "paquete", "aliases": ("comida", "comer", "alimenticia", "espagueti", "macarrones", "pasta para comer", "segunda", "segundo", "opcion 2")},
        ),
    },
    {
        "pattern": r"^(?:la\s+)?crema$",
        "question": "¿Te refieres a crema para cocinar o a crema para la piel?",
        "options": (
            {"name": "Crema de leche", "unit": "envase", "aliases": ("cocinar", "comida", "leche", "crema para cocinar")},
            {"name": "Crema corporal", "unit": "envase", "aliases": ("piel", "cuerpo", "corporal", "crema para la piel")},
        ),
    },
    {
        "pattern": r"^(?:el\s+)?jabon$",
        "question": "¿Te refieres a jabón para el cuerpo, jabón para lavar platos o detergente para ropa?",
        "options": (
            {"name": "Jabón corporal", "unit": "unidad", "aliases": ("cuerpo", "bano", "personal", "jabon corporal", "primera", "opcion 1")},
            {"name": "Jabón para platos", "unit": "botella", "aliases": ("platos", "fregar", "lavaplatos", "segunda", "opcion 2")},
            {"name": "Detergente para ropa", "unit": "botella", "aliases": ("ropa", "lavadora", "detergente", "tercera", "opcion 3")},
        ),
    },
    {
        "pattern": r"^(?:el\s+)?aceite$",
        "question": "¿Te refieres a aceite para cocinar, aceite para el cabello o aceite para el automóvil?",
        "options": (
            {"name": "Aceite de cocina", "unit": "botella", "aliases": ("cocinar", "comida", "cocina", "primera", "opcion 1")},
            {"name": "Aceite para el cabello", "unit": "botella", "aliases": ("cabello", "pelo", "segunda", "opcion 2")},
            {"name": "Aceite de motor", "unit": "botella", "aliases": ("carro", "auto", "motor", "tercera", "opcion 3")},
        ),
    },
    {
        "pattern": r"^(?:el\s+)?papel$",
        "question": "¿Te refieres a papel higiénico, papel de cocina o papel para imprimir?",
        "options": (
            {"name": "Papel higiénico", "unit": "paquete", "aliases": ("higienico", "bano", "papel higienico")},
            {"name": "Papel de cocina", "unit": "paquete", "aliases": ("cocina", "toalla", "papel toalla")},
            {"name": "Papel para imprimir", "unit": "paquete", "aliases": ("imprimir", "impresora", "oficina")},
        ),
    },
    {
        "pattern": r"^(?:el\s+)?(?:pad|pads)$",
        "question": "¿Te refieres a empapadores para mascota, toallas sanitarias o a un dispositivo electrónico?",
        "options": (
            {"name": "Empapadores para mascota", "unit": "paquete", "aliases": ("mascota", "perro", "luna", "empapador", "pee pad")},
            {"name": "Toallas sanitarias", "unit": "paquete", "aliases": ("sanitaria", "periodo", "menstrual")},
            {"name": "Tableta electrónica", "unit": "unidad", "aliases": ("electronico", "tableta", "ipad", "dispositivo")},
        ),
    },
)


def _canonical_shopping_request(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    plain = _plain_home_text(result.get("name"))
    if re.fullmatch(r"(?:h?elado|ice cream)\s+(?:de\s+)?(?:dulce de leche|arequipe|cajeta)", plain):
        result["name"] = "Helado de dulce de leche"
        if str(result.get("unit") or "unidad") == "unidad":
            result["unit"] = "envase"
    elif plain in {"dulce de leche", "arequipe", "cajeta"}:
        result["name"] = "Dulce de leche"
        if str(result.get("unit") or "unidad") == "unidad":
            result["unit"] = "lata"
    elif re.fullmatch(r"(?:pasta|crema)\s+(?:de|para)?\s*dientes?", plain) or plain in {"dentifrico", "toothpaste"}:
        result["name"] = "Pasta dental"
        if str(result.get("unit") or "unidad") == "unidad":
            result["unit"] = "tubo"
    elif re.search(r"\b(?:pad|pads|empapador|empapadores)\b", plain) and re.search(r"\b(?:luna|bella|perro|perra|mascota)\b", plain):
        result["name"] = "Empapadores para mascota"
        if str(result.get("unit") or "unidad") == "unidad":
            result["unit"] = "paquete"
    return result


def _shopping_clarification(rows: list[dict[str, Any]], original: str) -> dict[str, Any] | None:
    for row in rows:
        name = _plain_home_text(row.get("name"))
        for ambiguity in _SHOPPING_AMBIGUITIES:
            if re.fullmatch(str(ambiguity["pattern"]), name):
                return {
                    "kind": "shopping_product",
                    "original": original,
                    "question": ambiguity["question"],
                    "options": [dict(option) for option in ambiguity["options"]],
                }
        if name in {"esto", "eso", "aquello", "lo", "lo que dije", "lo de antes"} or len(name.split()) > 10:
            return {
                "kind": "shopping_product",
                "original": original,
                "question": "No estoy segura de qué producto quieres agregar. ¿Puedes decirme solo el nombre del artículo?",
                "options": [],
            }
    return None


def _resolve_shopping_clarification(pending: dict[str, Any], answer: str) -> dict[str, Any] | None:
    plain = _plain_home_text(answer)
    if not plain or len(plain.split()) > 10:
        return None
    for option in pending.get("options") or []:
        aliases = [_plain_home_text(alias) for alias in option.get("aliases") or []]
        if any(alias and (plain == alias or re.search(rf"\b{re.escape(alias)}\b", plain)) for alias in aliases):
            return {"name": option.get("name"), "quantity": 1, "unit": option.get("unit") or "unidad"}
    return None


def _assistant_pantry_requests(text: str) -> list[dict[str, Any]]:
    cleaned = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(
        r"(?i)^.*?\b(?:compre|compramos|acabo de comprar|guarda|registrar|registra|anota|agrega|pon|se acabo|se terminaron|ya no queda|quita|elimina|borra|saca)\b\s+",
        "",
        cleaned,
    )
    cleaned = re.sub(r"(?i)\s+(?:en|a|de)\s+(?:mi|la)\s+(?:despensa|alacena)\s*$", "", cleaned).strip()
    return _assistant_shopping_requests(f"agrega {cleaned}")


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


def _calendar_command_range(text: str, *, current: date | None = None) -> tuple[datetime, datetime]:
    today = current or date.today()
    normalized = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    if "manana" in normalized:
        target = today + timedelta(days=1)
        return datetime.combine(target, datetime.min.time()), datetime.combine(target + timedelta(days=1), datetime.min.time())
    for label, weekday in _WEEKDAY_INDEX.items():
        if re.search(rf"\b{label}\b", normalized):
            target = today + timedelta(days=(weekday - today.weekday()) % 7)
            return datetime.combine(target, datetime.min.time()), datetime.combine(target + timedelta(days=1), datetime.min.time())
    if "semana" in normalized:
        return datetime.combine(today, datetime.min.time()), datetime.combine(today + timedelta(days=7), datetime.min.time())
    return datetime.combine(today, datetime.min.time()), datetime.combine(today + timedelta(days=1), datetime.min.time())


def _calendar_spoken_event(event: dict[str, Any]) -> str:
    starts_at = datetime.fromisoformat(str(event.get("starts_at")))
    day = starts_at.strftime("%d/%m/%Y")
    hour = starts_at.strftime("%I:%M %p").lstrip("0").replace("AM", "a. m.").replace("PM", "p. m.")
    reminder = int(event.get("reminder_minutes") or 0)
    reminder_copy = "sin recordatorio" if not reminder else f"con aviso {reminder} minutos antes" if reminder < 60 else f"con aviso {reminder // 60} hora{'s' if reminder // 60 != 1 else ''} antes"
    return f"{event.get('title')}, el {day} a las {hour}, {reminder_copy}"


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


def _calendar_owner_key(auth: AuthContext, user: str) -> str:
    # Calendar entries are private to the signed-in person, even though food,
    # pantry and shopping are intentionally shared by the household.
    return f"member:{auth.member_id}" if auth.mode == "member" and auth.member_id else f"legacy:{user}"


def _conversation_owner_key(auth: AuthContext, user: str) -> str:
    # Conversation memory belongs to the person, not to the shared household.
    return f"member:{auth.member_id}" if auth.mode == "member" and auth.member_id else f"legacy:{user}"


def _conversation_needs_deep_reasoning(text: str) -> bool:
    plain = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    return len(plain) > 220 or bool(
        re.search(
            r"\b(analiza|comparame|compara|recomienda|recomendacion|por que|conviene|decidir|"
            r"ventajas|desventajas|mejor opcion|planifica|estrategia|prioriza|argumenta)\b",
            plain,
        )
    )


def _conversation_snapshot(user: str, auth: AuthContext) -> dict[str, Any]:
    food = _home_food_store().snapshot(user)
    member = _member_for_auth(auth)
    personal_preferences = (member or {}).get("preferences") or {}
    moment = datetime.now(ZoneInfo(os.getenv("ROXY_HOME_TIMEZONE", DEFAULT_TIMEZONE)))
    try:
        events = _calendar_store().list_events(
            _calendar_owner_key(auth, user),
            start=moment - timedelta(hours=6),
            end=moment + timedelta(days=31),
        )
    except ValueError:
        events = []
    brief = build_home_daily_brief(
        display_name="",
        shopping=_store().snapshot(user, limit=100),
        food=food,
        calendar={"events": events},
        now=moment,
    )
    return {
        "profile": {
            **(food.get("profile") or {}),
            "communication_style": personal_preferences.get("response_style") or "balanced",
        },
        "pantry": food.get("pantry") or [],
        "shopping": _store().list_items(user, statuses={"PENDING"}, limit=100),
        "today_meals": brief.get("today_meals") or [],
        "calendar": [
            {
                "title": row.get("title"),
                "starts_at": row.get("starts_at"),
                "ends_at": row.get("ends_at"),
                "calendar": row.get("calendar"),
            }
            for row in events[:20]
        ],
    }


def _conversation_speech(result: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in ("answer", "reasoning_summary", "recommendation", "follow_up"):
        value = " ".join(str(result.get(field) or "").split()).strip()
        if value and not any(value.casefold() in part.casefold() or part.casefold() in value.casefold() for part in parts):
            parts.append(value)
    return " ".join(parts).strip()


def _daily_brief(user: str, auth: AuthContext) -> dict[str, Any]:
    moment = datetime.now(ZoneInfo(os.getenv("ROXY_HOME_TIMEZONE", DEFAULT_TIMEZONE)))
    try:
        events = _calendar_store().list_events(
            _calendar_owner_key(auth, user),
            start=moment - timedelta(days=1),
            end=moment + timedelta(days=369),
        )
    except ValueError:
        events = []
    member = _member_for_auth(auth)
    return build_home_daily_brief(
        display_name=str(member.get("display_name") or "") if member else "",
        shopping=_store().snapshot(user, limit=100),
        food=_home_food_store().snapshot(user),
        calendar={"events": events},
        now=moment,
    )


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
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=(self)"
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
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: blob: https://maps.googleapis.com "
        "https://maps.gstatic.com https://*.googleapis.com https://*.gstatic.com "
        "https://images.openfoodfacts.org https://*.rainviewer.com "
        "https://*.basemaps.cartocdn.com https://tile.openstreetmap.org; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' blob: https://esm.sh https://cdn.jsdelivr.net https://esm.run "
        "https://maps.googleapis.com https://maps.gstatic.com; "
        "connect-src 'self' https://api.elevenlabs.io https://*.elevenlabs.io "
        "wss://api.elevenlabs.io wss://*.elevenlabs.io https://maps.googleapis.com "
        "https://maps.gstatic.com https://*.googleapis.com https://*.gstatic.com "
        "https://api.rainviewer.com https://*.rainviewer.com "
        "https://*.basemaps.cartocdn.com https://tile.openstreetmap.org; "
        "media-src 'self' blob:; "
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
            "icons": [{"src": "/assets/roxy_home_avatar.jpg", "sizes": "768x768", "type": "image/jpeg"}],
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
        recipe = exact_local_recipe(clean_title) or _home_food_store().find_saved_recipe_by_title(clean_title)
        state = _recipe_photo_queue().schedule(recipe) if recipe else "NOT_IN_CATALOG"
        if state == "PENDING":
            response = JSONResponse(
                {"status": "GENERATING", "detail": "Roxy está creando la imagen exacta de esta receta"},
                status_code=202,
                headers={"Retry-After": "5", "Cache-Control": "no-store"},
            )
            return _security_headers(response)
        raise HTTPException(status_code=404, detail="Aún no hay una imagen exacta y aprobada para esta receta")
    path, metadata = resolved
    response = FileResponse(path, media_type=str(metadata.get("media_type") or "image/jpeg"))
    response.headers["Cache-Control"] = "public, max-age=2592000, immutable"
    response.headers["X-Roxy-Photo-Source"] = str(metadata.get("provider") or "Roxy Home")[:64]
    return _security_headers(response)


@app.get("/v1/home-food/recipe-photo-coverage")
def recipe_photo_coverage() -> dict[str, Any]:
    rows = _all_recipe_photo_rows()
    ready = sum(1 for recipe in rows if _recipe_photo_store().resolve(str(recipe.get("title") or "")) is not None)
    return {
        "status": "COMPLETE" if ready == len(rows) else "GENERATING",
        "expected": len(rows),
        "ready": ready,
        "missing": max(0, len(rows) - ready),
        "queue": _recipe_photo_queue().public_status(),
        "failures": _recipe_photo_queue().failure_summary(),
    }


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


@app.put("/v1/home-account/preferences")
def home_account_preferences(
    payload: HomePersonalizationRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    member = _member_for_auth(auth)
    if member is None:
        raise HTTPException(status_code=409, detail="Primero entra con tu perfil personal")
    try:
        updated = _account_store().update_personalization(
            member["id"],
            display_name=payload.display_name,
            household_name=payload.household_name,
            preferences={
                "theme": payload.theme,
                "background": payload.background,
                "avatar": payload.avatar,
                "response_style": payload.response_style,
                "text_scale": payload.text_scale,
            },
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "UPDATED", "mode": "member", "requires_profile_setup": False, **updated}


def _family_member(auth: AuthContext) -> dict[str, Any]:
    member = _member_for_auth(auth)
    if member is None:
        raise HTTPException(status_code=409, detail="Mi familia requiere un perfil personal de esta casa")
    return member


def _family_context(member: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    store = _family_store()
    household_id, access_scope = store.resolve_household(member["household_id"], member["id"])
    household_members = _account_store().members(member["id"])
    if access_scope == "HOUSEHOLD":
        store.remember_household_members(household_id, household_members)
    return household_id, access_scope, household_members


@app.get("/v1/home-family")
def home_family_snapshot(request: Request, auth: AuthContext = Depends(_authenticate)) -> dict[str, Any]:
    _rate_limit(request)
    member = _family_member(auth)
    household_id, access_scope, household_members = _family_context(member)
    result = _family_store().snapshot(
        household_id, household_members if access_scope == "HOUSEHOLD" else [], member["id"]
    )
    result["access_scope"] = access_scope
    result["can_manage_connections"] = access_scope == "HOUSEHOLD" and member.get("role") == "OWNER"
    result["map"] = {
        "provider": "GOOGLE_MAPS" if os.getenv("ROXY_HOME_GOOGLE_MAPS_BROWSER_KEY", "").strip() else "UNCONFIGURED",
        "browser_key": os.getenv("ROXY_HOME_GOOGLE_MAPS_BROWSER_KEY", "").strip(),
        "map_id": os.getenv("ROXY_HOME_GOOGLE_MAP_ID", "").strip(),
    }
    return result


@app.put("/v1/home-family/location")
def home_family_update_location(
    payload: HomeFamilyLocationRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    member = _family_member(auth)
    household_id, _access_scope, _members = _family_context(member)
    try:
        result = _family_store().update_location(
            household_id, member["id"],
            latitude=payload.latitude, longitude=payload.longitude,
            accuracy_m=payload.accuracy_m, altitude_m=payload.altitude_m,
            speed_mps=payload.speed_mps, heading_deg=payload.heading_deg,
            recorded_at=payload.recorded_at, consent=payload.consent,
            shopping_pending=int(_store().snapshot(member["storage_user_id"]).get("pending_count") or 0),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "UPDATED", **result}


@app.put("/v1/home-family/profile")
def home_family_customize_profile(
    payload: HomeFamilyProfileRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    member = _family_member(auth)
    household_id, _access_scope, _members = _family_context(member)
    try:
        profile = _family_store().customize_member(
            household_id,
            member["id"],
            display_name=payload.display_name,
            marker_color=payload.marker_color,
            photo_data_url=payload.photo_data_url,
            profile_emoji=payload.profile_emoji,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "UPDATED", "profile": profile}


@app.get("/v1/home-family/members/{member_id}/history")
def home_family_history(
    member_id: str,
    request: Request,
    limit: int = 500,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    viewer = _family_member(auth)
    household_id, access_scope, household_members = _family_context(viewer)
    family = _family_store().snapshot(household_id, household_members if access_scope == "HOUSEHOLD" else [], viewer["id"])
    allowed = {str(row.get("id")) for row in family.get("members") or []}
    if member_id not in allowed:
        raise HTTPException(status_code=404, detail="Miembro no encontrado en esta casa")
    return {"status": "READY", "member_id": member_id, "points": _family_store().history(household_id, member_id, limit=limit)}


@app.delete("/v1/home-family/location", status_code=204)
def home_family_stop_location(
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> Response:
    _rate_limit(request)
    member = _family_member(auth)
    household_id, _access_scope, _members = _family_context(member)
    _family_store().stop_sharing(household_id, member["id"])
    return _security_headers(Response(status_code=204))


@app.post("/v1/home-family/places", status_code=201)
def home_family_save_place(
    payload: HomeFamilyPlaceRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    member = _family_member(auth)
    household_id, access_scope, _members = _family_context(member)
    if access_scope != "HOUSEHOLD":
        raise HTTPException(status_code=403, detail="Una conexión externa no puede modificar los lugares de esta casa")
    try:
        place = _family_store().save_place(
            household_id, name=payload.name, kind=payload.kind,
            latitude=payload.latitude, longitude=payload.longitude, radius_m=payload.radius_m,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "CREATED", "place": place}


@app.delete("/v1/home-family/places/{place_id}", status_code=204)
def home_family_delete_place(
    place_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> Response:
    _rate_limit(request)
    member = _family_member(auth)
    household_id, access_scope, _members = _family_context(member)
    if access_scope != "HOUSEHOLD":
        raise HTTPException(status_code=403, detail="Una conexión externa no puede modificar los lugares de esta casa")
    if not _family_store().delete_place(household_id, place_id):
        raise HTTPException(status_code=404, detail="Lugar no encontrado")
    return _security_headers(Response(status_code=204))


@app.post("/v1/home-family/invitations", status_code=201)
def home_family_create_invitation(
    payload: HomeFamilyInvitationRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    member = _family_member(auth)
    household_id, access_scope, _members = _family_context(member)
    if access_scope != "HOUSEHOLD" or member.get("role") != "OWNER":
        raise HTTPException(status_code=403, detail="Solo la persona propietaria de la casa puede invitar conexiones")
    invitation = _family_store().create_invitation(
        household_id, actor_id=member["id"], display_name=payload.display_name, relationship=payload.relationship
    )
    return {"status": "CREATED", "invitation": invitation, "access_scope": "NEXO_ONLY"}


@app.post("/v1/home-family/invitations/redeem")
def home_family_redeem_invitation(
    payload: HomeFamilyInvitationRedeemRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    member = _family_member(auth)
    try:
        result = _family_store().redeem_invitation(payload.token, member)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "CONNECTED", **result}


@app.delete("/v1/home-family/connections/{member_id}", status_code=204)
def home_family_revoke_connection(
    member_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> Response:
    _rate_limit(request)
    member = _family_member(auth)
    household_id, access_scope, _members = _family_context(member)
    if access_scope != "HOUSEHOLD" or member.get("role") != "OWNER":
        raise HTTPException(status_code=403, detail="Solo la persona propietaria de la casa puede retirar conexiones")
    if not _family_store().revoke_connection(household_id, member_id):
        raise HTTPException(status_code=404, detail="Conexión no encontrada")
    return _security_headers(Response(status_code=204))


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
    owner_key = _conversation_owner_key(auth, user)
    conversation_store = _conversation_store()
    pending_clarification = conversation_store.pending_clarification(owner_key)
    resolved_shopping_row: dict[str, Any] | None = None
    if pending_clarification and pending_clarification.get("kind") == "shopping_product":
        if not pending_clarification.get("options") and len(_plain_home_text(command_text).split()) <= 10:
            conversation_store.clear_clarification(owner_key)
            command_text = f"agrega {command_text}"
            intent = "shopping_add"
        else:
            resolved_shopping_row = _resolve_shopping_clarification(pending_clarification, command_text)
        if resolved_shopping_row:
            conversation_store.clear_clarification(owner_key)
            intent = "shopping_add"
        elif re.fullmatch(r"(?i)(?:no|ninguna|ninguno|cancelar|olvidalo|olvídalo)[.! ]*", command_text):
            conversation_store.clear_clarification(owner_key)
            intent = "shopping_clarify"
        elif intent == "general" and len(_plain_home_text(command_text).split()) <= 10:
            intent = "shopping_clarify"
        else:
            # A new explicit command replaces the unanswered clarification.
            conversation_store.clear_clarification(owner_key)
    if intent == "shopping_add" and resolved_shopping_row is None and _looks_like_calendar_statement(command_text):
        intent = "calendar_create"
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
        else "home_daily"
        if intent == "daily_query"
        else "home_weather"
        if intent == "weather_query"
        else "home_calendar"
        if intent.startswith("calendar_")
        else "home_commerce"
        if intent.startswith("commerce_")
        else "home_food"
        if intent.startswith("recipe_") or intent.startswith("cooking_") or intent.startswith("weekly_") or intent.startswith("pantry_")
        else "shopping"
        if intent == "shopping_clarify"
        else "home_ai"
    )
    store = _store()
    rows: list[dict[str, Any]] = []
    extra: dict[str, Any] = {}
    if intent == "shopping_teach_alias":
        learned = _assistant_product_alias(command_text)
        if learned is None:
            message = "Dime la frase y el producto real. Por ejemplo: cuando digo las blancas, me refiero a empapadores absorbentes para mascota."
        else:
            phrase, canonical_name = learned
            learned_row = store.learn_alias(user, phrase, canonical_name)
            message = f"Entendido. Cuando digas {phrase}, lo guardaré como {learned_row['name']}."
            extra["learned_alias"] = learned_row
    elif intent == "shopping_clarify":
        if pending_clarification and re.fullmatch(r"(?i)(?:no|ninguna|ninguno|cancelar|olvidalo|olvídalo)[.! ]*", command_text):
            message = "De acuerdo. No agregué nada a la lista."
        else:
            message = str((pending_clarification or {}).get("question") or "No estoy segura de cuál producto quieres. ¿Puedes especificarlo?")
            extra["clarification"] = pending_clarification or {}
    elif intent == "weather_query":
        profile = _commerce_store().profile(_commerce_owner_key(auth, user))
        try:
            weather = answer_weather_query(command_text, profile, config=HomeWeatherConfig.from_env())
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=502, detail="El servicio del clima no respondió. Inténtalo nuevamente en unos minutos.") from exc
        message = str(weather.get("message") or "No pude interpretar esa consulta del clima.")
        extra["weather"] = weather
    elif intent == "daily_query":
        brief = _daily_brief(user, auth)
        message = str(brief.get("summary") or "Aquí tienes lo importante de hoy.")
        details = [
            str(card.get("title") or "").strip()
            for card in (brief.get("cards") or [])[1:]
            if str(card.get("title") or "").strip()
        ]
        if details:
            message += " Además: " + "; ".join(details) + "."
        extra["daily_brief"] = brief
    elif intent.startswith("pantry_"):
        home_store = _home_food_store()
        if intent == "pantry_query":
            pantry = home_store.snapshot(user).get("pantry") or []
            rows = pantry
            message = (
                "En la despensa tienes: "
                + ", ".join(f"{row.get('quantity'):g} {row.get('unit')} de {row.get('name')}" for row in pantry[:30])
                + "."
                if pantry
                else "La despensa está vacía. Puedes decirme qué acabas de comprar."
            )
        elif intent == "pantry_add":
            requests = _assistant_pantry_requests(command_text)
            if not requests:
                raise HTTPException(status_code=422, detail="Dime qué producto compraste o quieres guardar en la despensa.")
            pantry = home_store.upsert_pantry(user, requests)
            rows = requests
            message = "Actualicé la despensa con: " + ", ".join(str(row.get("name")) for row in requests) + "."
            extra["pantry"] = pantry
        else:
            requests = _assistant_pantry_requests(command_text)
            if not requests:
                raise HTTPException(status_code=422, detail="Dime qué producto ya no queda en la despensa.")
            removed, missing = home_store.remove_pantry(user, [row["name"] for row in requests])
            rows = removed
            message = (
                "Quité de la despensa: " + ", ".join(str(row.get("name")) for row in removed) + "."
                if removed
                else "No encontré esos productos en la despensa."
            )
            if missing:
                message += " No encontré: " + ", ".join(missing) + "."
            extra["pantry"] = home_store.snapshot(user).get("pantry") or []
    elif intent.startswith("calendar_"):
        calendar_store = _calendar_store()
        owner_key = _calendar_owner_key(auth, user)
        if intent == "calendar_create":
            try:
                draft_data = parse_calendar_command(command_text)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if draft_data.pop("needs_clarification", False):
                message = "Puedo repetir ese evento de lunes a viernes. ¿Desde qué fecha comienza y en qué fecha termina?"
                extra["calendar_needs_clarification"] = True
            else:
                conflicts = calendar_store.conflicts(owner_key, draft_data)
                draft = calendar_store.save_draft(owner_key, draft_data)
                message = f"Voy a programar {_calendar_spoken_event(draft)}."
                if conflicts:
                    message += f" Atención: coincide con {conflicts[0].get('title')}."
                message += " ¿Lo confirmo?"
                extra["calendar_draft"] = draft
                extra["calendar_conflicts"] = conflicts
        elif intent == "calendar_confirm":
            try:
                event = calendar_store.confirm_draft(owner_key)
            except KeyError as exc:
                raise HTTPException(status_code=409, detail="No hay ningún evento pendiente de confirmación.") from exc
            if event.get("deleted"):
                message = f"Cancelé {event.get('title')} en tu calendario."
            else:
                message = f"Listo. Guardé {_calendar_spoken_event(event)}."
            sync_result = _sync_calendar_event(owner_key, event)
            if sync_result.get("synced"):
                message += " También quedó sincronizado con Google Calendar."
            elif sync_result.get("reason") == "not_connected":
                message += " Quedó guardado en Roxy Home, pero todavía debes conectar Google Calendar para recibirlo en el teléfono."
            else:
                message += " Quedó guardado en Roxy Home, pero Google Calendar no pudo sincronizarlo. Puedes reintentar desde Calendario."
            extra["calendar_event"] = event
            extra["calendar_sync"] = sync_result
        elif intent == "calendar_discard":
            if calendar_store.pending_draft(owner_key) is None:
                raise HTTPException(status_code=409, detail="No hay ningún cambio de calendario pendiente.")
            calendar_store.discard_draft(owner_key)
            message = "De acuerdo. No hice ningún cambio en tu calendario."
        elif intent == "calendar_query":
            start, end = _calendar_command_range(command_text)
            events = calendar_store.list_events(owner_key, start=start, end=end)
            if events:
                message = "En tu agenda tienes: " + "; ".join(_calendar_spoken_event(event) for event in events[:8]) + "."
            else:
                message = "No tienes compromisos programados para ese periodo."
            extra["calendar_events"] = events
        else:
            start = datetime.combine(date.today() - timedelta(days=1), datetime.min.time())
            end = datetime.combine(date.today() + timedelta(days=366), datetime.min.time())
            events = calendar_store.list_events(owner_key, start=start, end=end)
            command_words = {
                word for word in re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", command_text).encode("ascii", "ignore").decode("ascii").lower())
                if len(word) > 3 and word not in {"cancelar", "cancela", "eliminar", "elimina", "evento", "calendario", "agenda"}
            }
            candidates = [event for event in events if command_words & set(re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", str(event.get("title") or "")).encode("ascii", "ignore").decode("ascii").lower()))]
            if not candidates:
                raise HTTPException(status_code=404, detail="No encontré ese evento en tu calendario.")
            draft = calendar_store.save_delete_draft(owner_key, candidates[0]["id"])
            message = f"Voy a cancelar {candidates[0].get('title')}. ¿Lo confirmo?"
            extra["calendar_draft"] = draft
    elif intent.startswith("weekly_"):
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
                    pantry_words = (
                        pantry_match.group(1).strip(" .")
                        if pantry_match
                        else ", ".join(
                            str(row.get("name") or "").strip()
                            for row in (food_snapshot.get("pantry") or [])
                            if str(row.get("name") or "").strip()
                        )
                    )
                    if not pantry_words:
                        raise HTTPException(
                            status_code=409,
                            detail="Tu despensa está vacía. Dime qué tienes en casa y te propongo una receta.",
                        )
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
    elif intent == "commerce_compare":
        owner_key = _commerce_owner_key(auth, user)
        commerce_store = _commerce_store()
        profile = commerce_store.profile(owner_key)
        raw_items = store.list_items(user, statuses={"PENDING"}, limit=100)
        if not raw_items:
            raise HTTPException(status_code=409, detail="No hay productos pendientes para comparar.")
        food_snapshot = _home_food_store().snapshot(user)
        items = personalize_items(raw_items, profile, food_snapshot.get("profile", {}).get("allergies", []))
        config = PriceFeedConfig.from_env()
        if not config.configured:
            message = "Aún no tengo una fuente autorizada de precios en tiempo real. Puedo abrir las búsquedas en los comercios conectados, pero no inventaré precios ni ahorros."
            extra["price_recommendations"] = {"status": "PRICE_SOURCE_NOT_CONNECTED", "recommendations": []}
        else:
            try:
                offers = fetch_price_offers(items, profile, config=config)
            except ConnectionError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            result = recommend_prices(items, offers, profile, max_age_minutes=config.max_age_minutes)
            recommendations = result.get("recommendations") or []
            if recommendations:
                message = "Estas son mis mejores opciones verificadas: " + "; ".join(
                    f"{row['shopping_item']} en {row['retailer_name']} por ${row['price']:.2f}"
                    for row in recommendations[:5]
                ) + ". Confirma el precio final dentro de la tienda."
            else:
                message = "No encontré precios vigentes y comparables para los productos de tu lista. No voy a inventar una recomendación."
            extra["price_recommendations"] = result
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
        shopping_requests = (
            [resolved_shopping_row]
            if resolved_shopping_row is not None
            else [_canonical_shopping_request(row) for row in _assistant_shopping_requests(command_text)]
        )
        ambiguity = None if resolved_shopping_row is not None else _shopping_clarification(shopping_requests, command_text)
        if ambiguity:
            pending = conversation_store.save_clarification(owner_key, ambiguity)
            intent = "shopping_clarify"
            message = str(pending.get("question") or ambiguity["question"])
            extra["clarification"] = pending
            shopping_requests = []
        for row in shopping_requests:
            if _looks_like_calendar_statement(row.get("name")):
                continue
            rows.append(
                store.add(
                    user,
                    row["name"],
                    quantity=row.get("quantity") or 1,
                    unit=row.get("unit") or "unidad",
                    source="elevenlabs_voice",
                )
            )
        if intent == "shopping_add":
            message = (
                "Listo, agregué a tu lista: " + ", ".join(
                    f"{item.get('quantity'):g} {item.get('unit')} de {item.get('name')}" for item in rows
                ) + "."
                if rows
                else "No identifiqué un producto seguro para agregar. Dime el nombre del artículo."
            )
    else:
        member = _member_for_auth(auth)
        result = _ai_call(
            lambda: _home_ai().converse(
                command_text,
                _conversation_snapshot(user, auth),
                history=conversation_store.turns(owner_key),
                display_name=str(member.get("display_name") or "") if member else "",
                deep=_conversation_needs_deep_reasoning(command_text),
            )
        )
        message = _conversation_speech(result)
        if not message:
            raise HTTPException(status_code=502, detail="Roxy Home devolvió una respuesta vacía.")
        conversation_store.remember(owner_key, user=command_text, assistant=message, topic="home_conversation")
        extra["conversation"] = {
            "answer": result.get("answer") or "",
            "reasoning_summary": result.get("reasoning_summary") or "",
            "recommendation": result.get("recommendation") or "",
            "follow_up": result.get("follow_up") or "",
            "confidence": result.get("confidence") or "medium",
            "model_profile": result.get("model_profile") or "luna",
        }
    spoken = message if intent == "general" else _personalize(message, auth)
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


@app.get("/v1/home-daily/{user_id}")
def read_home_daily(
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    """Return one private, deterministic briefing for the signed-in person."""
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    return _daily_brief(user, auth)


@app.get("/v1/home-plants/{user_id}")
def read_home_plants(
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    result = _plant_store().snapshot(user, user)
    result["identification_configured"] = HomePlantIdentifier.from_env().configured
    result["species"] = [
        {"key": key, "common_name": value["common_name"], "scientific_name": value["scientific_name"]}
        for key, value in PLANT_CATALOG.items()
    ]
    return result


@app.post("/v1/home-plants/{user_id}/identify")
def identify_home_plant(
    user_id: str,
    payload: HomePlantIdentifyRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    _authorize_user(user_id, auth)
    try:
        proposal = HomePlantIdentifier.from_env().identify(payload.photo_data_url)
    except (ValueError, HomeAIConfigurationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="No pude analizar la foto. Puedes elegir la especie manualmente.") from exc
    return {"status": "CONFIRMATION_REQUIRED", "proposal": proposal}


@app.post("/v1/home-plants/{user_id}", status_code=201)
def create_home_plant(
    user_id: str,
    payload: HomePlantCreateRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    values = payload.model_dump()
    identification: dict[str, Any] | None = None
    if values.get("species_key") == "unknown":
        try:
            identification = HomePlantIdentifier.from_env().identify(values["photo_data_url"])
        except Exception:
            identification = {"status": "UNAVAILABLE", "species_key": "unknown", "confidence": 0, "alternatives": [], "warning": "Elige la especie para confirmar el cuidado."}
    try:
        row = _plant_store().create(user, user, values, identification)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "CREATED", "plant": public_plant(row, user), "identification": identification}


@app.patch("/v1/home-plants/{user_id}/{plant_id}")
def update_home_plant(
    user_id: str,
    plant_id: str,
    payload: HomePlantUpdateRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        row = _plant_store().update(user, plant_id, payload.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Planta no encontrada.") from exc
    return {"status": "UPDATED", "plant": public_plant(row, user)}


@app.delete("/v1/home-plants/{user_id}/{plant_id}", status_code=204)
def delete_home_plant(
    user_id: str,
    plant_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> Response:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        _plant_store().delete(user, plant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Planta no encontrada.") from exc
    return Response(status_code=204)


@app.get("/v1/home-plants/{user_id}/{plant_id}/image")
def read_home_plant_image(
    user_id: str,
    plant_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> FileResponse:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        row = _plant_store().plant(user, plant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.") from exc
    path = Path(str(row.get("photo_path") or ""))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    return FileResponse(path, media_type=str(row.get("photo_media_type") or "image/jpeg"))


@app.post("/v1/home-plants/{user_id}/{plant_id}/tasks/{task_id}/complete")
def complete_home_plant_task(
    user_id: str,
    plant_id: str,
    task_id: str,
    payload: HomePlantTaskCompleteRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    member = _member_for_auth(auth) or {}
    actor = str(member.get("display_name") or "Miembro del hogar")
    try:
        row = _plant_store().complete_task(user, plant_id, task_id, actor, payload.observation)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Tarea o planta no encontrada.") from exc
    return {"status": "COMPLETED", "plant": public_plant(row, user)}


@app.post("/v1/home-plants/{user_id}/{plant_id}/journal", status_code=201)
def add_home_plant_journal(
    user_id: str,
    plant_id: str,
    payload: HomePlantJournalRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        entry = _plant_store().add_journal(user, plant_id, user, payload.notes, payload.photo_data_url)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Planta no encontrada.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    entry.pop("photo_path", None)
    entry.pop("photo_media_type", None)
    return {"status": "CREATED", "entry": entry}


@app.get("/v1/home-plants/{user_id}/{plant_id}/journal/{entry_id}/image")
def read_home_plant_journal_image(
    user_id: str,
    plant_id: str,
    entry_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> FileResponse:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        row = _plant_store().plant(user, plant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.") from exc
    entry = next((item for item in row.get("journal", []) if item.get("id") == entry_id), None)
    path = Path(str((entry or {}).get("photo_path") or ""))
    if not entry or not path.is_file():
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    return FileResponse(path, media_type=str(entry.get("photo_media_type") or "image/jpeg"))


@app.put("/v1/home-plants/{user_id}/vacation")
def update_home_plant_vacation(
    user_id: str,
    payload: HomePlantVacationRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    return {"status": "UPDATED", "vacation": _plant_store().set_vacation(user, payload.model_dump())}


@app.post("/v1/home-plants/{user_id}/{plant_id}/reminders", status_code=201)
def create_home_plant_reminder(
    user_id: str,
    plant_id: str,
    payload: HomePlantReminderRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        plant = _plant_store().plant(user, plant_id)
        task = next(item for item in plant.get("care_tasks", []) if item.get("id") == payload.task_id)
    except (KeyError, StopIteration) as exc:
        raise HTTPException(status_code=404, detail="Tarea o planta no encontrada.") from exc
    try:
        starts_at = datetime.fromisoformat(f"{task['due_date']}T{payload.time}:00").replace(tzinfo=ZoneInfo(DEFAULT_TIMEZONE))
        event = _calendar_store().create(
            _calendar_owner_key(auth, user),
            {
                "title": f"Cuidar {plant['display_name']}: {str(task.get('title') or 'revisar planta')}",
                "starts_at": starts_at.isoformat(),
                "ends_at": (starts_at + timedelta(minutes=15)).isoformat(),
                "timezone": DEFAULT_TIMEZONE,
                "category": "HOME",
                "reminder_minutes": payload.reminder_minutes,
                "notes": f"Tarea de Mi jardín en Roxy Home. {plant.get('soil_rule', '')}",
                "recurrence": "NONE",
                "all_day": False,
            },
            source="home_plants",
        )
        _plant_store().link_task_calendar(user, plant_id, payload.task_id, event["id"])
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail="No pude preparar este recordatorio.") from exc
    return {"status": "CREATED", "event": event, "sync": _sync_calendar_event(_calendar_owner_key(auth, user), event)}


@app.get("/v1/home-weather/{user_id}")
def read_home_weather(
    user_id: str,
    request: Request,
    days: int = 16,
    place: str = "",
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    """Return a server-side forecast without exposing provider credentials."""
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    profile = _commerce_store().profile(_commerce_owner_key(auth, user))
    config = HomeWeatherConfig.from_env()
    try:
        if place.strip():
            location = geocode_place(place, config=config)
            if location is None:
                raise HTTPException(status_code=404, detail="No encontré ese lugar. Prueba con ciudad y estado.")
            return forecast_location(
                location["latitude"],
                location["longitude"],
                label=location["label"],
                days=days,
                timezone_name=location["timezone"],
                config=config,
            )
        return weather_for_profile(profile, days=days, config=config)
    except HTTPException:
        raise
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="El servicio del clima no respondió. Inténtalo nuevamente en unos minutos.") from exc


@app.get("/v1/home-calendar/{user_id}")
def read_home_calendar(
    user_id: str,
    start: datetime,
    end: datetime,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    owner = _calendar_owner_key(auth, user)
    try:
        events = _calendar_store().list_events(owner, start=start, end=end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    google_status = _calendar_google().status(owner)
    return {
        "status": "READY",
        "events": events,
        "pending_draft": _calendar_store().pending_draft(owner),
        "sync": {
            "native_export": True,
            "provider": "ICS",
            "google_calendar": google_status,
            "message": google_status["message"],
        },
    }


@app.post("/v1/home-calendar/{user_id}/drafts", status_code=201)
def create_calendar_draft(
    user_id: str,
    payload: CalendarDraftRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    owner = _calendar_owner_key(auth, user)
    raw = payload.model_dump(exclude={"confirmed"})
    try:
        conflicts = _calendar_store().conflicts(owner, raw)
        draft = _calendar_store().save_draft(owner, raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "CONFIRMATION_REQUIRED", "draft": draft, "conflicts": conflicts}


@app.post("/v1/home-calendar/{user_id}/drafts/confirm", status_code=201)
def confirm_calendar_draft(
    user_id: str,
    payload: CalendarConfirmRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    if not payload.confirmed:
        raise HTTPException(status_code=409, detail="Confirma el evento antes de guardarlo.")
    try:
        event = _calendar_store().confirm_draft(_calendar_owner_key(auth, user), payload.draft_id, source="ui")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="La propuesta de calendario ya no está disponible.") from exc
    sync_result = _sync_calendar_event(_calendar_owner_key(auth, user), event)
    return {"status": "CREATED", "event": event, "sync": sync_result}


@app.delete("/v1/home-calendar/{user_id}/drafts", status_code=204)
def discard_calendar_draft(
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> Response:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    _calendar_store().discard_draft(_calendar_owner_key(auth, user))
    return Response(status_code=204)


@app.put("/v1/home-calendar/{user_id}/events/{event_id}")
def update_calendar_event(
    user_id: str,
    event_id: str,
    payload: CalendarEventRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    owner = _calendar_owner_key(auth, user)
    try:
        conflicts = _calendar_store().conflicts(owner, payload.model_dump(), exclude_id=event_id)
        event = _calendar_store().update(owner, event_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Evento no encontrado.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    sync_result = _sync_calendar_event(owner, event)
    return {"status": "UPDATED", "event": event, "conflicts": conflicts, "sync": sync_result}


@app.delete("/v1/home-calendar/{user_id}/events/{event_id}", status_code=204)
def delete_calendar_event(
    user_id: str,
    event_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> Response:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        owner = _calendar_owner_key(auth, user)
        _calendar_store().delete(owner, event_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Evento no encontrado.") from exc
    _sync_calendar_event(owner, {"id": event_id, "deleted": True})
    return Response(status_code=204)


@app.get("/v1/home-calendar/{user_id}/google/connect")
def connect_google_calendar(
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> RedirectResponse:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        url = _calendar_google().authorization_url(_calendar_owner_key(auth, user))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return RedirectResponse(url, status_code=303)


@app.get("/v1/home-calendar/google/callback")
def google_calendar_callback(state: str, code: str = "", error: str = "") -> RedirectResponse:
    if error or not code:
        return RedirectResponse("/lista?calendar_sync=denied#calendario", status_code=303)
    google = _calendar_google()
    try:
        owner = google.exchange_code(state, code)
        google.sync_all(owner, _calendar_store().owned_events(owner))
    except Exception:
        return RedirectResponse("/lista?calendar_sync=error#calendario", status_code=303)
    return RedirectResponse("/lista?calendar_sync=connected#calendario", status_code=303)


@app.post("/v1/home-calendar/{user_id}/google/sync")
def sync_google_calendar(
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    owner = _calendar_owner_key(auth, user)
    try:
        result = _calendar_google().sync_all(owner, _calendar_store().owned_events(owner))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "SYNCED", **result}


@app.delete("/v1/home-calendar/{user_id}/google/connection", status_code=204)
def disconnect_google_calendar(
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> Response:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    _calendar_google().disconnect(_calendar_owner_key(auth, user))
    return Response(status_code=204)


@app.get("/v1/home-calendar/{user_id}/events/{event_id}.ics")
def export_calendar_event(
    user_id: str,
    event_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> Response:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        content = _calendar_store().export_ics(_calendar_owner_key(auth, user), event_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Evento no encontrado.") from exc
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="roxy-evento-{event_id[:8]}.ics"'},
    )


@app.get("/v1/shopping/{user_id}")
def read_list(user_id: str, request: Request, auth: str = Depends(_authenticate)) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    store = _store()
    snapshot = store.snapshot(user, limit=1000)
    snapshot["items"] = store.list_items(user, include_archived=False, limit=1000)
    snapshot["sync_state"] = "SERVER_SYNCED"
    return snapshot


@app.get("/v1/home-products/{user_id}/status")
def home_product_status(
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    _authorize_user(user_id, auth)
    return {"status": "READY", "sources": _product_intelligence().status()}


@app.post("/v1/home-products/{user_id}/lookup")
def home_product_lookup(
    user_id: str,
    payload: ProductLookupRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    _authorize_user(user_id, auth)
    try:
        return _product_intelligence().lookup(barcode=payload.barcode, query=payload.query)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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


@app.get("/v1/home-design/{user_id}")
def read_home_design(
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    owner_key = _commerce_owner_key(auth, user)
    generator = HomeDesignGenerator.from_env()
    return {
        "status": "READY",
        "generation_configured": generator.configured,
        "projects": [public_project(row, user) for row in _design_store().projects(owner_key)],
    }


@app.post("/v1/home-design/{user_id}/projects", status_code=201)
def create_home_design_project(
    user_id: str,
    payload: HomeDesignProjectRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        project = _design_store().create(_commerce_owner_key(auth, user), user, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "CREATED", "project": public_project(project, user)}


@app.post("/v1/home-design/{user_id}/projects/{project_id}/proposal", status_code=202)
def generate_home_design_proposal(
    user_id: str,
    project_id: str,
    payload: HomeDesignProposalRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    owner_key = _commerce_owner_key(auth, user)
    generator = HomeDesignGenerator.from_env()
    if not generator.configured:
        raise HTTPException(status_code=503, detail="La generación visual de Roxy Renueva todavía no está conectada.")
    try:
        store = _design_store()
        store.select_tier(owner_key, project_id, payload.tier)
        project = store.mark_generating(owner_key, project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado") from exc
    background_tasks.add_task(_generate_home_design, owner_key, project_id)
    return {"status": "GENERATING", "project": public_project(project, user)}


@app.post("/v1/home-design/{user_id}/projects/{project_id}/analysis")
def analyze_home_design_project(
    user_id: str,
    project_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    owner_key = _commerce_owner_key(auth, user)
    store = _design_store()
    generator = HomeDesignGenerator.from_env()
    if not generator.configured:
        raise HTTPException(status_code=503, detail="El análisis visual de Roxy Renueva todavía no está conectado.")
    try:
        project = store.project(owner_key, project_id)
        project = store.save_analysis(owner_key, project_id, generator.analyze(project))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado") from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail="Roxy no pudo analizar esta foto. Inténtalo nuevamente.") from exc
    return {"status": "ANALYZED", "project": public_project(project, user)}


@app.post("/v1/home-design/{user_id}/projects/{project_id}/revision", status_code=202)
def revise_home_design_project(
    user_id: str,
    project_id: str,
    payload: HomeDesignRevisionRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    owner_key = _commerce_owner_key(auth, user)
    generator = HomeDesignGenerator.from_env()
    if not generator.configured:
        raise HTTPException(status_code=503, detail="La generación visual de Roxy Renueva todavía no está conectada.")
    try:
        store = _design_store()
        store.request_revision(owner_key, project_id, payload.instruction, payload.tier)
        project = store.mark_generating(owner_key, project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    background_tasks.add_task(_generate_home_design, owner_key, project_id)
    return {"status": "GENERATING", "project": public_project(project, user)}


@app.put("/v1/home-design/{user_id}/projects/{project_id}/measurements")
def update_home_design_measurements(
    user_id: str,
    project_id: str,
    payload: HomeDesignFitRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        project = _design_store().update_fit_constraints(
            _commerce_owner_key(auth, user), project_id, payload.model_dump()
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "UPDATED", "project": public_project(project, user)}


@app.get("/v1/home-design/{user_id}/projects/{project_id}/image/{kind}")
def read_home_design_image(
    user_id: str,
    project_id: str,
    kind: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> FileResponse:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        project = _design_store().project(_commerce_owner_key(auth, user), project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado") from exc
    if kind == "original":
        path, media_type = project.get("photo_path"), project.get("photo_media_type")
    elif kind == "proposal":
        path, media_type = project.get("proposal_path"), "image/png"
    else:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    if not path or not Path(path).is_file():
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "private, max-age=300"})


@app.delete("/v1/home-design/{user_id}/projects/{project_id}")
def delete_home_design_project(
    user_id: str,
    project_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        _design_store().delete(_commerce_owner_key(auth, user), project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado") from exc
    return {"status": "DELETED"}


@app.post("/v1/home-design/{user_id}/projects/{project_id}/commerce", status_code=201)
def prepare_home_design_purchase(
    user_id: str,
    project_id: str,
    payload: HomeDesignCommerceRequest,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    owner_key = _commerce_owner_key(auth, user)
    try:
        store = _design_store()
        project = store.select_tier(owner_key, project_id, payload.tier)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado") from exc
    products = project.get("products") or []
    wanted = set(payload.product_ids)
    items = [row for row in products if not wanted or row.get("id") in wanted]
    if not items:
        raise HTTPException(status_code=409, detail="Selecciona al menos un producto.")
    profile = _commerce_store().profile(owner_key)
    activity = _commerce_store().activity(owner_key)
    provider_rows = _commerce_providers(profile, activity, context="design")
    known = {row["id"] for row in provider_rows}
    requested = list(dict.fromkeys(payload.provider_ids)) if payload.provider_ids else [row["id"] for row in provider_rows]
    if not requested or any(provider not in known for provider in requested):
        raise HTTPException(status_code=422, detail="Selecciona proveedores compatibles.")
    prepared_items = personalize_items(items, profile, [])
    tier_label = next(
        (row.get("label") for row in project.get("budget_tiers") or [] if row.get("id") == payload.tier),
        payload.tier,
    )
    for row in prepared_items:
        target = float(row.get("budget_target") or 0)
        priority = "pieza principal" if row.get("priority") == "essential" else "complemento opcional"
        row["reason"] = (
            f"{priority.capitalize()} · presupuesto estimado ${target:,.0f}. "
            "El comercio confirmará el producto, sus medidas, disponibilidad y precio real."
        )
    fit = project.get("fit_constraints") or {}
    if any(float(value or 0) > 0 for value in fit.values()):
        fit_labels = {"wall_width": "pared", "passage_width": "paso", "max_depth": "profundidad"}
        limits = ", ".join(f"{fit_labels.get(key, key)} {float(value):g} in" for key, value in fit.items() if float(value or 0) > 0)
        for row in prepared_items:
            row["reason"] = f"{row['reason']} Verifica las dimensiones publicadas contra: {limits}."
    preparation = _commerce_store().save_preparation(
        owner_key,
        user,
        source="design",
        source_title=f"Opción {tier_label} para {project['name']}",
        items=prepared_items,
        providers=requested,
    )
    return {"status": "PREPARED", "preparation": preparation, "providers": provider_rows}


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
    price_activity = store.price_activity(owner_key)
    providers = _commerce_providers(profile, activity)
    return {
        "status": "READY",
        "profile": profile,
        "providers": providers,
        "activity": activity,
        "price_activity": price_activity,
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


@app.get("/v1/home-commerce/{user_id}/recommendations")
def read_home_price_recommendations(
    user_id: str,
    request: Request,
    auth: AuthContext = Depends(_authenticate),
) -> dict[str, Any]:
    """Compare only fresh, retailer-supplied offers for the authenticated member."""

    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    owner_key = _commerce_owner_key(auth, user)
    commerce_store = _commerce_store()
    profile = commerce_store.profile(owner_key)
    config = PriceFeedConfig.from_env()
    nearby_retailers: list[dict[str, Any]] = []
    retailer_discovery_message = ""
    if config.retailer_discovery_configured and profile.get("postal_code"):
        try:
            nearby_retailers = fetch_nearby_retailers(profile, config=config)
        except ConnectionError as exc:
            retailer_discovery_message = str(exc)
    raw_items = _store().list_items(user, statuses={"PENDING"}, limit=100)
    if not raw_items:
        return {
            "status": "EMPTY_LIST",
            "configured": config.configured,
            "recommendations": [],
            "unpriced_items": [],
            "nearby_retailers": nearby_retailers,
            "retailer_discovery_message": retailer_discovery_message,
            "price_activity": commerce_store.price_activity(owner_key),
            "updated_at": "",
            "notice": PRICE_NOTICE,
        }
    food_snapshot = _home_food_store().snapshot(user)
    items = personalize_items(raw_items, profile, food_snapshot.get("profile", {}).get("allergies", []))
    if not config.configured:
        return {
            "status": "PRICE_SOURCE_NOT_CONNECTED",
            "configured": False,
            "recommendations": [],
            "unpriced_items": [row["name"] for row in items],
            "nearby_retailers": nearby_retailers,
            "retailer_discovery_message": retailer_discovery_message,
            "price_activity": commerce_store.price_activity(owner_key),
            "updated_at": "",
            "notice": PRICE_NOTICE,
            "message": (
                "Roxy aún no tiene una fuente autorizada de precios en tiempo real. "
                "Puedes buscar los productos en los comercios disponibles, pero no mostraré precios inventados."
            ),
        }
    try:
        offers = fetch_price_offers(items, profile, config=config)
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    result = recommend_prices(items, offers, profile, max_age_minutes=config.max_age_minutes)
    price_activity = commerce_store.record_price_recommendations(
        owner_key,
        result.get("recommendations") or [],
        alert_percent=int(profile.get("price_drop_percent") or 10),
        alerts_enabled=profile.get("price_alerts_enabled") is not False,
    )
    return {
        "configured": True,
        **result,
        "nearby_retailers": nearby_retailers,
        "retailer_discovery_message": retailer_discovery_message,
        "price_activity": price_activity,
    }


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
    for recipe in snapshot.get("recipes", []):
        _schedule_recipe_photo(recipe)
    for plan in snapshot.get("weekly_plans", []):
        for day in plan.get("days", []):
            for meal in day.get("meals", []):
                _schedule_recipe_photo({**meal, "kind": "meal"})
    pets = snapshot.get("pets") or []
    return {
        **snapshot,
        "pet_options": pet_profile_options(),
        "pet_recommendations": {
            str(pet.get("id")): personalized_pet_products(pet) for pet in pets if pet.get("id")
        },
        "pet_care_plans": {
            str(pet.get("id")): personalized_pet_care_plan(pet) for pet in pets if pet.get("id")
        },
        "pet_nutrition_plans": {
            str(pet.get("id")): personalized_pet_nutrition_plan(pet) for pet in pets if pet.get("id")
        },
        "pet_profile_completions": {
            str(pet.get("id")): pet_profile_completion(pet) for pet in pets if pet.get("id")
        },
        "local_catalog": local_recipe_catalog_summary(),
        "local_recipes": local_recipe_catalog(snapshot),
        "shared_recipe_library": _recipe_library_store().summary(),
        "recipe_image_service": _recipe_photo_queue().public_status(),
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
    if payload.catalog_key:
        recipe_data = local_recipe_by_key(payload.catalog_key, snapshot)
        if recipe_data is None:
            raise HTTPException(status_code=404, detail="Esa receta ya no está disponible en el catálogo.")
        generation_mode = "local_catalog_exact"
    else:
        recipe_data, generation_mode = _ai_call(lambda: _recipe_with_resilience(
            payload.prompt,
            snapshot,
            deep=payload.mode == "deep",
            recipe_type=payload.recipe_type,
        ))
    if payload.recipe_type != "general":
        recipe_data = {**recipe_data, "kind": "drink", "drink_type": payload.recipe_type}
    try:
        recipe = store.save_recipe(user, recipe_data, mode=payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Roxy devolvió una receta incompleta.") from exc
    _schedule_recipe_photo(recipe)
    return {"status": "CREATED", "recipe": recipe, "generation_mode": generation_mode}


@app.post("/v1/home-food/{user_id}/recipe-imports")
def preview_recipe_import(user_id: str, payload: RecipeImportRequest, request: Request, auth: str = Depends(_authenticate)) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    if payload.source_type == "image" and not re.match(r"^data:image/(?:jpeg|png|webp);base64,", payload.source):
        raise HTTPException(status_code=422, detail="La imagen debe ser JPEG, PNG o WebP.")
    if payload.source_type == "url" and not re.match(r"^https?://", payload.source, flags=re.IGNORECASE):
        raise HTTPException(status_code=422, detail="Escribe un enlace web completo.")
    try:
        result = _ai_call(lambda: _home_ai().import_recipe(
            payload.source, _home_food_store().snapshot(user), source_type=payload.source_type,
            audience=payload.audience, pet_species=payload.pet_species,
        ))
        if result.get("needs_clarification"):
            return {"status": "NEEDS_CLARIFICATION", "question": result.get("clarification_question") or "Necesito una captura más clara para importar esta receta con seguridad."}
        recipe = HomeFoodStore._normalize_recipe({
            **result, "audience": payload.audience,
            "pet_species": payload.pet_species if payload.audience == "pet" else "",
            "generation_source": f"import_{payload.source_type}",
        })
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "READY_FOR_REVIEW", "recipe": recipe}


@app.post("/v1/home-food/{user_id}/recipe-imports/commit", status_code=201)
def commit_recipe_import(user_id: str, payload: RecipeImportCommitRequest, request: Request, auth: str = Depends(_authenticate)) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    if not payload.confirmed:
        raise HTTPException(status_code=409, detail="Confirma la receta después de revisarla.")
    try:
        recipe = _home_food_store().save_recipe(user, payload.recipe, mode="routine")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _schedule_recipe_photo(recipe)
    return {"status": "CREATED", "recipe": recipe}


@app.post("/v1/home-food/{user_id}/pets", status_code=201)
def upsert_home_pet(user_id: str, payload: PetProfileRequest, request: Request, auth: str = Depends(_authenticate)) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        pet = _home_food_store().upsert_pet(user, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "SAVED", "pet": pet}


@app.post("/v1/home-food/{user_id}/pets/{pet_id}/medical-history", status_code=201)
def add_home_pet_medical_record(
    user_id: str,
    pet_id: str,
    payload: PetMedicalRecordRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        record = _home_food_store().add_pet_medical_record(user, pet_id, **payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Mascota no encontrada") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "CREATED", "record": record}


@app.post("/v1/home-food/{user_id}/pets/{pet_id}/care-log", status_code=201)
def complete_home_pet_care_routine(
    user_id: str,
    pet_id: str,
    payload: PetCareCompletionRequest,
    request: Request,
    auth: str = Depends(_authenticate),
) -> dict[str, Any]:
    _rate_limit(request)
    user = _authorize_user(user_id, auth)
    try:
        entry = _home_food_store().complete_pet_care_routine(user, pet_id, **payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Mascota no encontrada") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "COMPLETED", "entry": entry}


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
