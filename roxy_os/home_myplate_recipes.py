"""Transient, human-only MyPlate.food recipe reader (not a catalogue mirror).

The provider permits commercial live per-request calls, not bulk exports or
storage: https://myplate.food/api and https://myplate.food/partners (2026-09-11).
No network work on import; no persistence, prefetch, translations, AI completions,
nutrition calculations or household data. Source text is retained verbatim.
The process-wide limiter is conservative; the provider remains authoritative
across processes/replicas sharing an IP. Never retry a rejected request silently.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
import re
import threading
import time
from typing import Any, Callable
from urllib.parse import urlsplit

import requests


API_BASE = "https://myplate.food/api/v1"
PROVIDER = "MyPlate.food"
CATEGORY_OPTIONS = ("Main dish", "Dessert", "Beverage", "Salad", "Soup")
MAX_RESPONSE_BYTES = 512 * 1024
MAX_PAGE_SIZE = 24
MAX_OFFSET = 100_000
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_IMAGE_PATH = re.compile(r"/peppermint-cdn/myplate\.food-recipe-images/[a-z0-9][a-z0-9_-]*\.(?:jpg|jpeg|png|webp)\Z")


class MyPlateRecipeError(RuntimeError):
    """Safe for API responses; contains no raw upstream content or query text."""

    def __init__(self, code: str, message: str, status_code: int = 503,
                 retry_after: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after


def _invalid_content() -> MyPlateRecipeError:
    return MyPlateRecipeError("invalid_content", "La fuente no devolvió una receta completa y legible.", 422)


def _invalid_query() -> MyPlateRecipeError:
    return MyPlateRecipeError("invalid_query", "Revisa los filtros de la búsqueda de recetas.", 400)


def _text(value: Any, maximum: int, *, required: bool = False) -> str:
    if value is None and not required:
        return ""
    if (not isinstance(value, str) or len(value) > maximum
            or any(ord(char) < 32 and char not in "\n\r\t" for char in value)
            or (required and not value.strip())):
        raise _invalid_content()
    return value


def _integer(value: Any, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise _invalid_content()
    return value


def _slug(value: Any, *, input_value: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 160 or not _SLUG.fullmatch(value):
        raise _invalid_query() if input_value else _invalid_content()
    return value


def _url(value: Any, hosts: set[str], *, expected_path: str | None = None) -> str:
    value = _text(value, 2048, required=True)
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "https" and parsed.hostname in hosts
                 and parsed.port in (None, 443) and not parsed.username
                 and not parsed.password and not parsed.query and not parsed.fragment
                 and not any(c.isspace() or c == "\\" for c in value)
                 and (expected_path is None or parsed.path == expected_path))
    except ValueError:
        valid = False
    if not valid:
        raise _invalid_content()
    return value


def _image_url(value: Any) -> str:
    if value is None or value == "":
        return ""
    value = _url(value, {"storage.googleapis.com"})
    if not _IMAGE_PATH.fullmatch(urlsplit(value).path):
        raise _invalid_content()
    return value


def _translations(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 5:
        raise _invalid_content()
    result = {}
    for language, link in value.items():
        if language not in {"en", "es", "fr", "de", "ko"}:
            raise _invalid_content()
        link = _url(link, {"myplate.food"})
        path = urlsplit(link).path
        prefix = "/recipes/" if language == "en" else f"/{language}/recipes/"
        suffix = path.removeprefix(prefix)
        if (not path.startswith(prefix) or not suffix or "/" in suffix
                or "%" in suffix or suffix in {".", ".."}):
            raise _invalid_content()
        result[language] = link
    return result


def _summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise _invalid_content()
    slug = _slug(raw.get("slug"))
    canonical = _url(raw.get("recipe_url"), {"myplate.food"}, expected_path=f"/recipes/{slug}")
    if raw.get("canonical_url") is not None:
        _url(raw["canonical_url"], {"myplate.food"}, expected_path=f"/recipes/{slug}")
    if raw.get("api_url") is not None:
        _url(raw["api_url"], {"myplate.food"}, expected_path=f"/api/v1/recipes/{slug}")
    return {
        "slug": slug, "title": _text(raw.get("name"), 300, required=True),
        "description": _text(raw.get("description"), 6000),
        "category": _text(raw.get("category"), 100),
        "image_url": _image_url(raw.get("image_url")), "source_url": canonical,
        "language": "en", "audience": "human", "provider": PROVIDER,
        "translation_urls": _translations(raw.get("locales")),
        "image_note": "Imagen del proveedor, remasterizada con IA a partir del original.",
        "can_cook": False, "can_add_to_shopping": False,
    }


def _detail(raw: Any, requested_slug: str) -> dict[str, Any]:
    result = _summary(raw)
    if result["slug"] != requested_slug:
        raise _invalid_content()
    ingredients = raw.get("ingredients")
    if not isinstance(ingredients, list) or not 1 <= len(ingredients) <= 128:
        raise _invalid_content()
    normalized = []
    for item in ingredients:
        if not isinstance(item, dict):
            raise _invalid_content()
        # Do not lose an unrecognized measure/heading field on schema drift.
        if set(item) - {"text", "note"}:
            raise _invalid_content()
        note = item.get("note")
        normalized.append({"text": _text(item.get("text"), 4096, required=True),
                           "note": _text(note, 4096) if note is not None else None})
    original_source = raw.get("source_url")
    result.update({
        "ingredients": normalized,
        # A paragraph is not a numbered sequence; callers must not fabricate one.
        "directions": _text(raw.get("directions"), 80_000, required=True),
        "yield": _text(raw.get("yield"), 1000, required=True),
        "serving_size": _text(raw.get("serving_size"), 1000),
        "notes": _text(raw.get("notes"), 16_000),
        "contributor": _text(raw.get("contributor"), 4000),
        "source": _text(raw.get("source"), 6000, required=True),
        "original_source_url": _url(original_source, {"www.myplate.gov", "myplate.gov"},
                                    expected_path=f"/recipes/{requested_slug}") if original_source else "",
        "editorial_status": "external_original_not_individually_reviewed",
    })
    return result


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _invalid_content()
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise _invalid_content()


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise _invalid_content()
    return number


class _RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._minute: deque[float] = deque()
        self._details: deque[float] = deque()
        self._cooldown = 0.0

    def reserve(self, *, detail: bool) -> None:
        with self._lock:
            now = self._clock()
            while self._minute and self._minute[0] <= now - 60:
                self._minute.popleft()
            while self._details and self._details[0] <= now - 86400:
                self._details.popleft()
            retry = self._cooldown - now
            if len(self._minute) >= 20:
                retry = max(retry, self._minute[0] + 60 - now)
            if detail and len(self._details) >= 100:
                retry = max(retry, self._details[0] + 86400 - now)
            if retry > 0:
                raise MyPlateRecipeError("rate_limited", "La fuente alcanzó su límite temporal. Inténtalo más tarde.",
                                        429, max(1, math.ceil(retry)))
            self._minute.append(now)
            if detail:
                self._details.append(now)

    def defer(self, seconds: int) -> None:
        with self._lock:
            self._cooldown = max(self._cooldown, self._clock() + seconds)


def _retry_after(value: Any) -> int:
    if not isinstance(value, str) or len(value) > 100:
        return 60
    try:
        if re.fullmatch(r"[0-9]{1,10}", value):
            seconds = int(value)
        else:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            seconds = math.ceil((date - datetime.now(timezone.utc)).total_seconds())
        return max(1, min(86400, seconds))
    except (TypeError, ValueError, OverflowError):
        return 60


_LIMITER = _RateLimiter()


class MyPlateRecipeProvider:
    def __init__(self, *, request_get: Callable[..., Any] | None = None,
                 limiter: _RateLimiter | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self._request_get = request_get or requests.get
        self._limiter = limiter if limiter is not None else _LIMITER
        self._clock = clock

    def _request(self, path: str, params: dict[str, Any], *, detail: bool) -> dict[str, Any]:
        self._limiter.reserve(detail=detail)
        response = None
        start = self._clock()
        try:
            response = self._request_get(API_BASE + path, params=params, stream=True,
                                         timeout=(3, 5), allow_redirects=False,
                                         headers={"Accept": "application/json", "User-Agent": "RoxyHome/recipe-reader"})
            if response.status_code == 429:
                seconds = _retry_after(response.headers.get("Retry-After"))
                self._limiter.defer(seconds)
                raise MyPlateRecipeError("rate_limited", "La fuente alcanzó su límite temporal. Inténtalo más tarde.", 429, seconds)
            if response.status_code == 404:
                raise MyPlateRecipeError("not_found", "Esta receta ya no está disponible en la fuente.", 404)
            if response.status_code != 200:
                raise MyPlateRecipeError("unavailable", "La fuente de recetas no está disponible ahora.")
            if response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise _invalid_content()
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    declared = int(length)
                except (ValueError, TypeError):
                    raise _invalid_content() from None
                if not 0 <= declared <= MAX_RESPONSE_BYTES:
                    raise _invalid_content()
            body = bytearray()
            # Yield on every byte so a slow trickle cannot indefinitely postpone
            # the total deadline by keeping a large buffered read unfinished.
            for part in response.iter_content(chunk_size=1):
                if self._clock() - start > 10:
                    raise MyPlateRecipeError("timeout", "La fuente tardó demasiado en responder.")
                if not isinstance(part, bytes) or len(body) + len(part) > MAX_RESPONSE_BYTES:
                    raise _invalid_content()
                body.extend(part)
            decoded = json.loads(bytes(body).decode("utf-8"), object_pairs_hook=_json_object,
                                 parse_constant=_reject_constant, parse_float=_finite_float)
            if not isinstance(decoded, dict):
                raise _invalid_content()
            return decoded
        except MyPlateRecipeError:
            raise
        except requests.Timeout:
            raise MyPlateRecipeError("timeout", "La fuente tardó demasiado en responder.") from None
        except (requests.RequestException, OSError):
            raise MyPlateRecipeError("unavailable", "La fuente de recetas no está disponible ahora.") from None
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise _invalid_content() from None
        finally:
            if response is not None:
                try:
                    response.close()
                except (requests.RequestException, OSError):
                    pass

    def search(self, *, q: str = "", category: str = "", offset: int = 0,
               limit: int = MAX_PAGE_SIZE) -> dict[str, Any]:
        if (not isinstance(q, str) or len(q) > 120 or any(ord(c) < 32 for c in q)
                or category not in ("", *CATEGORY_OPTIONS)
                or type(offset) is not int or not 0 <= offset <= MAX_OFFSET
                or type(limit) is not int or not 1 <= limit <= MAX_PAGE_SIZE):
            raise _invalid_query()
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if q.strip():
            params["q"] = q.strip()
        if category:
            params["category"] = category
        raw = self._request("/recipes", params, detail=False)
        total = _integer(raw.get("total"), 0, MAX_OFFSET)
        count = _integer(raw.get("count"), 0, limit)
        rows = raw.get("results")
        if (not isinstance(rows, list) or len(rows) != count
                or count > max(0, total - offset) or (count == 0 and total > offset)):
            raise _invalid_content()
        recipes = [_summary(row) for row in rows]
        if len({row["slug"] for row in recipes}) != count:
            raise _invalid_content()
        return {"recipes": recipes, "total": total, "offset": offset, "limit": limit,
                "next_offset": offset + count if offset + count < total else None,
                "source": _text(raw.get("source"), 6000, required=True),
                "source_url": _url(raw.get("canonical_url"), {"myplate.food"}, expected_path="/recipes"),
                "provider": PROVIDER, "live": True, "audience": "human",
                "category_options": list(CATEGORY_OPTIONS), "storage": "transient_only"}

    def detail(self, slug: str) -> dict[str, Any]:
        slug = _slug(slug, input_value=True)
        raw = self._request(f"/recipes/{slug}", {}, detail=True)
        return {"recipe": _detail(raw, slug), "provider": PROVIDER,
                "live": True, "audience": "human", "storage": "transient_only"}


_PROVIDER = MyPlateRecipeProvider()


def search_recipes(*, q: str = "", category: str = "", offset: int = 0,
                   limit: int = MAX_PAGE_SIZE) -> dict[str, Any]:
    return _PROVIDER.search(q=q, category=category, offset=offset, limit=limit)


def get_recipe(slug: str) -> dict[str, Any]:
    return _PROVIDER.detail(slug)
