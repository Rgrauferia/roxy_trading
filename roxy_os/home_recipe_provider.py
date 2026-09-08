"""Opt-in, human-only recipe provider boundary; never an editorial approval.

No network call occurs on import, configuration or availability checks. The
adapter does not store a catalog, call AI, translate, infer servings, or modify
household data. In particular, its records must NOT be passed through the local
template editorializer, which would replace the provider's actual instructions.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse

import requests


PROVIDER = "themealdb"
PROVIDER_URL = "https://www.themealdb.com/"
TERMS_URL = "https://www.themealdb.com/terms_of_use.php"
MAX_RESPONSE_BYTES = 512 * 1024
MAX_PROVIDER_RECORDS = 100
_PROVIDER_HOSTS = frozenset({"themealdb.com", "www.themealdb.com"})


class RecipeProviderUnavailable(RuntimeError):
    """Safe error: never includes provider response bodies, URLs with keys or PII."""


class RecipeProviderContentError(ValueError):
    """A provider record cannot pass the source/content boundary."""


def _enabled(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _bounded(value: Any, default: float, low: float, high: float) -> float:
    try:
        number = float(value)
    except (ValueError, TypeError):
        return default
    return max(low, min(number, high)) if math.isfinite(number) else default


@dataclass(frozen=True)
class HomeRecipeProviderConfig:
    enabled: bool = False
    commercial_license_confirmed: bool = False
    api_key: str = field(default="", repr=False)
    timeout_seconds: float = 5.0
    max_results: int = 12
    # Operator-maintained rights allowlist, NOT a claim supplied by API content.
    # Each listed ID requires documented commercial recipe AND photo rights.
    licensed_recipe_ids: tuple[str, ...] = ()

    @classmethod
    def from_env(cls) -> "HomeRecipeProviderConfig":
        ids = os.getenv("ROXY_HOME_THEMEALDB_LICENSED_RECIPE_IDS", "").split(",")
        return cls(
            enabled=_enabled(os.getenv("ROXY_HOME_RECIPE_PROVIDER_ENABLED")),
            commercial_license_confirmed=_enabled(os.getenv("ROXY_HOME_THEMEALDB_COMMERCIAL_LICENSE_CONFIRMED")),
            api_key=os.getenv("ROXY_HOME_THEMEALDB_API_KEY", "").strip(),
            timeout_seconds=_bounded(os.getenv("ROXY_HOME_RECIPE_PROVIDER_TIMEOUT_SECONDS"), 5, 1, 10),
            max_results=int(_bounded(os.getenv("ROXY_HOME_RECIPE_PROVIDER_MAX_RESULTS"), 12, 1, 20)),
            licensed_recipe_ids=tuple(sorted({value.strip() for value in ids if re.fullmatch(r"[0-9]{1,12}", value.strip())})),
        )

    @property
    def configured(self) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_-]{1,128}", self.api_key)) and self.api_key.lower() not in {
            "1", "test", "demo", "your_api_key", "your-api-key",
        }


def recipe_provider_availability(config: HomeRecipeProviderConfig | None = None) -> dict[str, Any]:
    config = config or HomeRecipeProviderConfig.from_env()
    ready = bool(config.enabled and config.configured and config.commercial_license_confirmed)
    reason = (
        "disabled" if not config.enabled else
        "awaiting_commercial_key" if not config.configured else
        "awaiting_license_confirmation" if not config.commercial_license_confirmed else
        "configured_not_live_verified"
    )
    return {
        "provider": PROVIDER, "enabled": config.enabled,
        "configured": config.configured, "license_confirmed": config.commercial_license_confirmed,
        "available": ready, "status": reason, "live_verified": False,
        "audience": "human", "language": "en", "translation_available": False,
        "terms_url": TERMS_URL, "requires_editorial_review": True,
    }


@dataclass(frozen=True)
class ProviderRecipe:
    """Immutable canonical original; callers receive independent JSON copies."""

    provider_id: str
    original_json: str = field(repr=False)
    rights_basis: str

    def to_dict(self) -> dict[str, Any]:
        original = json.loads(self.original_json)
        # Paragraphs keep source order/text. We do not invent timed microsteps.
        steps = [text.strip() for text in re.split(r"\r\n|\r|\n", original["instructions"]) if text.strip()]
        return {
            "provider": PROVIDER, "provider_id": self.provider_id,
            "title": original["title"], "language": "en", "audience": "human",
            "provider_original": original, "ingredients": [dict(item) for item in original["ingredients"]],
            "steps": steps, "servings": None, "servings_status": "not_provided_by_provider",
            "image_url": original["image_url"], "photo_verified": False,
            "sources": [{"title": "TheMealDB", "url": PROVIDER_URL}, *(
                [{"title": "Original recipe publisher", "url": original["source_url"]}]
                if original["source_url"] and original["source_url"] != PROVIDER_URL else []
            )],
            "rights": {"basis": self.rights_basis, "terms_url": TERMS_URL, "attribution_required": True},
            "editorial_status": "provider_content_needs_review",
            "generation_source": "external_recipe_provider", "can_cook": False, "can_add_to_shopping": False,
            "review_required": ["source_and_steps", "servings", "photo_match", "allergies", "spanish_translation"],
        }


def _text(value: Any, maximum: int, *, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
        raise RecipeProviderContentError("invalid_provider_field")
    if required and not value.strip():
        raise RecipeProviderContentError("missing_provider_field")
    return value


def _source_url(value: Any, *, required: bool = False) -> str:
    value = _text(value, 2048, required=required).strip()
    if not value:
        return ""
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        raise RecipeProviderContentError("invalid_source_url") from None
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or port not in {None, 443} or not re.fullmatch(r"[A-Za-z0-9.-]+", parsed.hostname)
            or "." not in parsed.hostname or re.fullmatch(r"[0-9.]+", parsed.hostname)
            or any(part in value for part in ("\\", "\r", "\n"))):
        raise RecipeProviderContentError("invalid_source_url")
    return value


def _normalize_record(raw: Any, config: HomeRecipeProviderConfig) -> ProviderRecipe:
    if not isinstance(raw, dict):
        raise RecipeProviderContentError("invalid_provider_record")
    provider_id = _text(raw.get("idMeal"), 12, required=True)
    if not re.fullmatch(r"[0-9]{1,12}", provider_id):
        raise RecipeProviderContentError("invalid_provider_id")
    title = _text(raw.get("strMeal"), 300, required=True)
    instructions = _text(raw.get("strInstructions"), 40000, required=True)
    source = _source_url(raw.get("strSource"))
    image_source = _source_url(raw.get("strImageSource"))
    image = _source_url(raw.get("strMealThumb"), required=True)
    if urlparse(image).hostname not in _PROVIDER_HOSTS or not urlparse(image).path.startswith("/images/media/meals/"):
        raise RecipeProviderContentError("unsupported_provider_image")
    external_source = any(urlparse(url).hostname not in _PROVIDER_HOSTS for url in (source, image_source) if url)
    explicit_rights = provider_id in config.licensed_recipe_ids
    cc_confirmed = str(raw.get("strCreativeCommonsConfirmed") or "").strip().lower() in {"yes", "true", "1"}
    if not explicit_rights and (external_source or not cc_confirmed):
        raise RecipeProviderContentError("content_rights_unconfirmed")
    ingredients = []
    for index in range(1, 21):
        name = _text(raw.get(f"strIngredient{index}"), 300)
        measure = _text(raw.get(f"strMeasure{index}"), 160)
        if not name.strip() and not measure.strip():
            continue
        if not name.strip() or not measure.strip():
            raise RecipeProviderContentError("ingredient_measure_missing")
        ingredients.append({"name": name, "measure": measure, "quantity": None, "unit": None})
    if not ingredients:
        raise RecipeProviderContentError("ingredients_missing")
    original = {
        "provider": PROVIDER, "provider_id": provider_id, "language": "en",
        "title": title, "instructions": instructions, "ingredients": ingredients,
        "category": _text(raw.get("strCategory"), 100), "area": _text(raw.get("strArea"), 100),
        "image_url": image, "source_url": source or PROVIDER_URL, "image_source_url": image_source,
        "creative_commons_confirmed": cc_confirmed,
    }
    return ProviderRecipe(provider_id, json.dumps(original, ensure_ascii=False, sort_keys=True),
                          "operator_documented_recipe_and_image_license" if explicit_rights else "provider_terms_and_cc_confirmed_artwork")


def _require_available(config: HomeRecipeProviderConfig, audience: str) -> None:
    if audience != "human":
        raise RecipeProviderUnavailable("human_recipes_only")
    if not recipe_provider_availability(config)["available"]:
        raise RecipeProviderUnavailable("recipe_provider_not_configured")


def _fetch(endpoint: str, params: dict[str, str], config: HomeRecipeProviderConfig,
           transport: Callable[..., Any] | None) -> dict[str, Any]:
    # Fixed hostname, endpoint names from code only; no redirect can leak key.
    url = f"https://www.themealdb.com/api/json/v1/{config.api_key}/{endpoint}"
    response = None
    try:
        timeout = _bounded(config.timeout_seconds, 5, 1, 10)
        deadline = time.monotonic() + timeout
        response = (transport or requests.get)(url, params=params, timeout=(min(3.0, timeout), timeout),
                                               allow_redirects=False, stream=True)
        if response.status_code != 200:
            raise RecipeProviderUnavailable("recipe_provider_request_failed")
        if "application/json" not in response.headers.get("Content-Type", "").lower():
            raise RecipeProviderUnavailable("recipe_provider_invalid_response")
        data = bytearray()
        for chunk in response.iter_content(chunk_size=16384):
            if time.monotonic() > deadline:
                raise RecipeProviderUnavailable("recipe_provider_deadline_exceeded")
            data.extend(chunk)
            if len(data) > MAX_RESPONSE_BYTES:
                raise RecipeProviderUnavailable("recipe_provider_response_too_large")
        payload = json.loads(data.decode("utf-8"))
        if not isinstance(payload, dict):
            raise RecipeProviderUnavailable("recipe_provider_invalid_response")
        return payload
    except RecipeProviderUnavailable:
        raise
    except Exception:
        # requests exceptions contain the API-key-bearing request URL.
        raise RecipeProviderUnavailable("recipe_provider_request_failed") from None
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass


def _records(payload: dict[str, Any]) -> list[Any]:
    if "meals" not in payload:
        raise RecipeProviderUnavailable("recipe_provider_invalid_response")
    meals = payload.get("meals")
    if meals is None:
        return []
    if not isinstance(meals, list) or len(meals) > MAX_PROVIDER_RECORDS:
        raise RecipeProviderUnavailable("recipe_provider_invalid_response")
    return meals


def search_provider_recipes(query: str, *, audience: str = "human", limit: int = 12,
                            config: HomeRecipeProviderConfig | None = None,
                            transport: Callable[..., Any] | None = None) -> tuple[ProviderRecipe, ...]:
    """One bounded user-driven search, English originals only, no auto-import."""
    config = config or HomeRecipeProviderConfig.from_env()
    _require_available(config, audience)
    if not isinstance(query, str) or not 2 <= len(query.strip()) <= 100 or any(ord(c) < 32 for c in query):
        raise ValueError("invalid_recipe_query")
    cap = min(int(_bounded(limit, 12, 1, 20)), int(_bounded(config.max_results, 12, 1, 20)))
    rows = _records(_fetch("search.php", {"s": query.strip()}, config, transport))
    recipes: list[ProviderRecipe] = []
    seen: set[str] = set()
    for row in rows:
        try:
            recipe = _normalize_record(row, config)
        except RecipeProviderContentError:
            continue
        if recipe.provider_id not in seen:
            recipes.append(recipe)
            seen.add(recipe.provider_id)
        if len(recipes) >= cap:
            break
    return tuple(recipes)


def get_provider_recipe(provider_id: str, *, audience: str = "human",
                        config: HomeRecipeProviderConfig | None = None,
                        transport: Callable[..., Any] | None = None) -> ProviderRecipe | None:
    """One detail lookup; returns None only for missing records, not rejected data."""
    config = config or HomeRecipeProviderConfig.from_env()
    _require_available(config, audience)
    if not isinstance(provider_id, str) or not re.fullmatch(r"[0-9]{1,12}", provider_id):
        raise ValueError("invalid_recipe_provider_id")
    rows = _records(_fetch("lookup.php", {"i": provider_id}, config, transport))
    if not rows:
        return None
    if len(rows) != 1:
        raise RecipeProviderContentError("unexpected_provider_records")
    result = _normalize_record(rows[0], config)
    if result.provider_id != provider_id:
        raise RecipeProviderContentError("provider_id_mismatch")
    return result
