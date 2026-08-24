from __future__ import annotations

import json
import os
import re
import hashlib
import base64
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from copy import deepcopy


PRICE_NOTICE = (
    "Precios consultados en comercios externos. Pueden cambiar por ubicación, membresía, "
    "impuestos o disponibilidad; confirma el total en la tienda antes de pagar."
)
_FEED_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_FEED_CACHE_LOCK = threading.Lock()
_PRODUCT_TERM_ALIASES = {
    "aceite": {"oil"}, "agua": {"water"}, "arroz": {"rice"}, "azucar": {"sugar"},
    "cafe": {"coffee"}, "camarones": {"shrimp"}, "detergente": {"detergent"},
    "harina": {"flour"}, "huevos": {"egg", "eggs"}, "jabon": {"soap"},
    "leche": {"milk"}, "levadura": {"yeast"}, "mantequilla": {"butter"},
    "pan": {"bread"}, "papel": {"paper"}, "pasta": {"pasta"}, "pollo": {"chicken"},
    "queso": {"cheese"}, "sal": {"salt"}, "suavizante": {"softener"},
    "trigo": {"wheat"}, "vainilla": {"vanilla"},
}
_PRODUCT_STOPWORDS = {"a", "al", "con", "de", "del", "el", "en", "la", "las", "los", "para", "sin", "y"}


def _text(value: Any, limit: int = 180) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _fold(value: Any) -> str:
    import unicodedata

    return " ".join(
        re.sub(
            r"[^a-z0-9]+",
            " ",
            unicodedata.normalize("NFD", _text(value, 400)).encode("ascii", "ignore").decode().lower(),
        ).split()
    )


def _https_url(value: Any) -> str:
    url = _text(value, 2000)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("La oferta contiene un enlace no seguro.")
    return url


def _optional_https_url(value: Any) -> str:
    if not _text(value, 2000):
        return ""
    try:
        return _https_url(value)
    except ValueError:
        return ""


def _timestamp(value: Any) -> datetime:
    raw = _text(value, 80)
    if not raw:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("La oferta no contiene una fecha de consulta válida.") from exc
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


def _money(value: Any) -> float:
    try:
        result = round(float(value), 2)
    except (TypeError, ValueError) as exc:
        raise ValueError("La oferta no contiene un precio válido.") from exc
    if not 0 < result < 1_000_000:
        raise ValueError("La oferta no contiene un precio válido.")
    return result


@dataclass(frozen=True)
class PriceFeedConfig:
    url: str
    api_key: str
    max_age_minutes: int = 180
    timeout_seconds: int = 12
    kroger_client_id: str = ""
    kroger_client_secret: str = ""
    kroger_base_url: str = "https://api.kroger.com/v1"

    @classmethod
    def from_env(cls) -> "PriceFeedConfig":
        return cls(
            url=_text(os.getenv("ROXY_HOME_PRICE_FEED_URL"), 2000),
            api_key=_text(os.getenv("ROXY_HOME_PRICE_FEED_API_KEY"), 1000),
            max_age_minutes=max(5, min(int(os.getenv("ROXY_HOME_PRICE_MAX_AGE_MINUTES", "180")), 1440)),
            timeout_seconds=max(2, min(int(os.getenv("ROXY_HOME_PRICE_TIMEOUT_SECONDS", "12")), 30)),
            kroger_client_id=_text(os.getenv("ROXY_HOME_KROGER_CLIENT_ID"), 500),
            kroger_client_secret=_text(os.getenv("ROXY_HOME_KROGER_CLIENT_SECRET"), 1000),
            kroger_base_url=_text(os.getenv("ROXY_HOME_KROGER_API_URL") or "https://api.kroger.com/v1", 2000),
        )

    @property
    def configured(self) -> bool:
        return self.generic_configured or self.kroger_configured

    @property
    def generic_configured(self) -> bool:
        if not self.url or not self.api_key:
            return False
        try:
            _https_url(self.url)
        except ValueError:
            return False
        return True

    @property
    def kroger_configured(self) -> bool:
        if not self.kroger_client_id or not self.kroger_client_secret:
            return False
        try:
            _https_url(self.kroger_base_url)
        except ValueError:
            return False
        return True


def _kroger_json(request: urllib.request.Request, timeout: int) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise ConnectionError("Kroger no pudo actualizar precios en este momento.") from exc
    if not isinstance(payload, dict):
        raise ConnectionError("Kroger respondió con un formato no compatible.")
    return payload


def _kroger_token(config: PriceFeedConfig) -> str:
    credential = base64.b64encode(
        f"{config.kroger_client_id}:{config.kroger_client_secret}".encode("utf-8")
    ).decode("ascii")
    request = urllib.request.Request(
        _https_url(f"{config.kroger_base_url.rstrip('/')}/connect/oauth2/token"),
        data=urllib.parse.urlencode(
            {"grant_type": "client_credentials", "scope": "product.compact"}
        ).encode("ascii"),
        headers={
            "Authorization": f"Basic {credential}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "Roxy-Home/1.0",
        },
        method="POST",
    )
    token = _text(_kroger_json(request, config.timeout_seconds).get("access_token"), 4000)
    if not token:
        raise ConnectionError("Kroger no entregó una sesión de catálogo válida.")
    return token


def _kroger_product_url(description: str, product_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _fold(description)).strip("-") or "producto"
    return _https_url(f"https://www.kroger.com/p/{slug}/{urllib.parse.quote(product_id, safe='')}")


def _product_match_score(requested_name: Any, product_title: Any) -> float:
    requested = [word for word in _fold(requested_name).split() if word not in _PRODUCT_STOPWORDS]
    product_words = set(_fold(product_title).split())
    if not requested or not product_words:
        return 0.0
    groups = [{word, *_PRODUCT_TERM_ALIASES.get(word, set())} for word in requested]
    return sum(bool(group & product_words) for group in groups) / len(groups)


def _package_unit_price(price: float, package_label: Any) -> tuple[float | None, str]:
    """Convert common US package sizes into comparable base-unit prices."""

    label = _fold(package_label)
    match = re.search(
        r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>fl oz|fluid ounce|oz|ounce|lb|pound|gal|gallon|qt|quart|pt|pint|kg|kilogram|g|gram|l|liter|ml|milliliter|ct|count)\b",
        label,
    )
    if not match:
        return None, ""
    amount = float(match.group("amount"))
    unit = match.group("unit")
    conversions = {
        "gal": (128, "fl oz"), "gallon": (128, "fl oz"),
        "qt": (32, "fl oz"), "quart": (32, "fl oz"),
        "pt": (16, "fl oz"), "pint": (16, "fl oz"),
        "fl oz": (1, "fl oz"), "fluid ounce": (1, "fl oz"),
        "lb": (16, "oz"), "pound": (16, "oz"), "oz": (1, "oz"), "ounce": (1, "oz"),
        "kg": (1000, "g"), "kilogram": (1000, "g"), "g": (1, "g"), "gram": (1, "g"),
        "l": (1000, "ml"), "liter": (1000, "ml"), "ml": (1, "ml"), "milliliter": (1, "ml"),
        "ct": (1, "count"), "count": (1, "count"),
    }
    multiplier, comparison_unit = conversions[unit]
    base_amount = amount * multiplier
    return (round(price / base_amount, 4), comparison_unit) if base_amount > 0 else (None, "")


def _kroger_offers(
    items: list[dict[str, Any]], profile: dict[str, Any], config: PriceFeedConfig
) -> list[dict[str, Any]]:
    postal_code = _text(profile.get("postal_code"), 12)
    if not postal_code:
        return []
    token = _kroger_token(config)
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Roxy-Home/1.0",
    }
    base = config.kroger_base_url.rstrip("/")
    location_url = _https_url(
        f"{base}/locations?" + urllib.parse.urlencode(
            {"filter.zipCode.near": postal_code, "filter.limit": 1}
        )
    )
    locations = _kroger_json(
        urllib.request.Request(location_url, headers=headers), config.timeout_seconds
    ).get("data")
    if not isinstance(locations, list) or not locations:
        return []
    location_id = _text(locations[0].get("locationId"), 80)
    if not location_id:
        return []

    observed_at = datetime.now(timezone.utc).isoformat()
    offers: list[dict[str, Any]] = []
    # A short bounded list keeps voice and mobile requests responsive and stays
    # comfortably below Kroger's public API quota. The surrounding cache avoids
    # repeating identical lookups.
    for row in items[:12]:
        query = _text(row.get("query") or row.get("name"), 120)
        product_url = _https_url(
            f"{base}/products?" + urllib.parse.urlencode(
                {"filter.term": query, "filter.locationId": location_id, "filter.limit": 6}
            )
        )
        products = _kroger_json(
            urllib.request.Request(product_url, headers=headers), config.timeout_seconds
        ).get("data")
        if not isinstance(products, list):
            continue
        for product in products[:6]:
            variants = product.get("items") if isinstance(product, dict) else None
            variant = variants[0] if isinstance(variants, list) and variants else {}
            price_data = variant.get("price") if isinstance(variant, dict) else {}
            if not isinstance(price_data, dict):
                continue
            regular = price_data.get("promo") or price_data.get("regular")
            try:
                price = _money(regular)
            except ValueError:
                continue
            description = _text(product.get("description"), 180)
            product_id = _text(product.get("productId"), 80)
            if not description or not product_id:
                continue
            match_score = _product_match_score(row.get("name"), description)
            if match_score < 0.6:
                continue
            images = product.get("images") if isinstance(product.get("images"), list) else []
            image_url = ""
            for image in images:
                sizes = image.get("sizes") if isinstance(image, dict) else []
                if isinstance(sizes, list):
                    candidate = next((entry.get("url") for entry in reversed(sizes) if isinstance(entry, dict) and entry.get("url")), "")
                    if candidate:
                        try:
                            image_url = _https_url(candidate)
                        except ValueError:
                            image_url = ""
                        break
            folded = _fold(f"{description} {product.get('categories') or ''}")
            package_label = _text(variant.get("size"), 80)
            unit_price, comparison_unit = _package_unit_price(price, package_label)
            offers.append(
                {
                    "item_name": _text(row.get("name"), 120),
                    "retailer_id": "kroger",
                    "retailer_name": _text(locations[0].get("chain") or "Kroger", 80),
                    "product_title": description,
                    "brand": _text(product.get("brand"), 80),
                    "price": price,
                    "currency": "USD",
                    "package_label": package_label,
                    "unit_price": unit_price,
                    "comparison_unit": comparison_unit,
                    "organic_certified": "organic" in folded,
                    "availability": "available",
                    "product_url": _kroger_product_url(description, product_id),
                    "image_url": image_url,
                    "observed_at": observed_at,
                    "source": "Kroger Products API",
                    "match_score": match_score,
                }
            )
    return offers


def fetch_price_offers(
    items: list[dict[str, Any]],
    profile: dict[str, Any],
    *,
    config: PriceFeedConfig | None = None,
) -> list[dict[str, Any]]:
    """Read live offers from an approved server-to-server catalog feed.

    The browser never receives the feed credential. An absent feed returns no offers,
    so Roxy cannot accidentally turn affiliate search links into claimed prices.
    """

    config = config or PriceFeedConfig.from_env()
    if not config.configured:
        return []
    endpoint = _https_url(config.url) if config.generic_configured else _https_url(config.kroger_base_url)
    payload = {
        "postal_code": _text(profile.get("postal_code"), 12),
        "currency": "USD",
        "items": [
            {
                "name": _text(row.get("name"), 120),
                "query": _text(row.get("query") or row.get("name"), 300),
                "quantity": float(row.get("quantity") or 1),
                "unit": _text(row.get("unit") or "unidad", 32),
            }
            for row in items[:40]
            if _text(row.get("name"), 120)
        ],
    }
    cache_seconds = max(0, min(int(os.getenv("ROXY_HOME_PRICE_CACHE_SECONDS", "900")), 3600))
    cache_key = hashlib.sha256(f"{endpoint}\0{json.dumps(payload, ensure_ascii=False, sort_keys=True)}".encode()).hexdigest()
    if cache_seconds:
        with _FEED_CACHE_LOCK:
            cached = _FEED_CACHE.get(cache_key)
            if cached and cached[0] > time.monotonic():
                return deepcopy(cached[1])
    if config.generic_configured:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Roxy-Home/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:  # nosec B310
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise ConnectionError("No pude actualizar los precios en este momento.") from exc
        offers = result.get("offers") if isinstance(result, dict) else None
        if not isinstance(offers, list):
            raise ConnectionError("La fuente de precios respondió con un formato no compatible.")
    else:
        offers = _kroger_offers(items, profile, config)
    offers = offers[:1000]
    if cache_seconds:
        with _FEED_CACHE_LOCK:
            _FEED_CACHE[cache_key] = (time.monotonic() + cache_seconds, deepcopy(offers))
            if len(_FEED_CACHE) > 500:
                expired = [key for key, value in _FEED_CACHE.items() if value[0] <= time.monotonic()]
                for key in expired:
                    _FEED_CACHE.pop(key, None)
    return offers


def _normalize_offer(raw: dict[str, Any], max_age_minutes: int) -> dict[str, Any] | None:
    observed = _timestamp(raw.get("observed_at"))
    now = datetime.now(timezone.utc)
    if observed < now - timedelta(minutes=max_age_minutes) or observed > now + timedelta(minutes=5):
        return None
    currency = _text(raw.get("currency") or "USD", 3).upper()
    if currency != "USD":
        return None
    unit_price = raw.get("unit_price")
    normalized_unit_price = _money(unit_price) if unit_price not in (None, "") else None
    comparison_unit = _fold(raw.get("comparison_unit"))[:32]
    if normalized_unit_price is None:
        comparison_unit = ""
    labels = [_text(value, 60) for value in (raw.get("dietary_labels") or []) if _text(value, 60)]
    return {
        "item_name": _text(raw.get("item_name"), 120),
        "retailer_id": _text(raw.get("retailer_id"), 32),
        "retailer_name": _text(raw.get("retailer_name"), 80),
        "product_title": _text(raw.get("product_title"), 180),
        "brand": _text(raw.get("brand"), 80),
        "price": _money(raw.get("price")),
        "currency": currency,
        "package_label": _text(raw.get("package_label"), 80),
        "unit_price": normalized_unit_price,
        "comparison_unit": comparison_unit,
        "organic_certified": raw.get("organic_certified") is True,
        "dietary_labels": labels,
        "availability": _text(raw.get("availability") or "available", 32),
        "product_url": _https_url(raw.get("product_url")),
        "observed_at": observed.isoformat(),
        "source": _text(raw.get("source") or "retailer_api", 80),
        "image_url": _optional_https_url(raw.get("image_url")),
    }


def _contains(values: list[str], value: str) -> bool:
    folded = _fold(value)
    return any(_fold(candidate) == folded for candidate in values)


def _matches_item(item_name: str, offer_name: str) -> bool:
    item = set(_fold(item_name).split())
    offer = set(_fold(offer_name).split())
    return bool(item and offer and (item <= offer or offer <= item or len(item & offer) >= min(2, len(item))))


def recommend_prices(
    items: list[dict[str, Any]],
    raw_offers: list[dict[str, Any]],
    profile: dict[str, Any],
    *,
    max_age_minutes: int = 180,
) -> dict[str, Any]:
    """Rank real offers deterministically and only calculate comparable savings."""

    normalized: list[dict[str, Any]] = []
    rejected = 0
    for raw in raw_offers:
        if not isinstance(raw, dict):
            rejected += 1
            continue
        try:
            offer = _normalize_offer(raw, max_age_minutes)
        except ValueError:
            rejected += 1
            continue
        if offer is None or offer["availability"].casefold() not in {"available", "in_stock", "instock"}:
            rejected += 1
            continue
        if offer["brand"] and _contains(profile.get("avoided_brands") or [], offer["brand"]):
            rejected += 1
            continue
        normalized.append(offer)

    recommendations: list[dict[str, Any]] = []
    missing: list[str] = []
    organic_required = profile.get("organic_preference") == "required" or profile.get("objective") == "organic"
    favorite_retailers = profile.get("favorite_retailers") or []
    favorite_brands = profile.get("favorite_brands") or []
    objective = str(profile.get("objective") or "balanced")

    for item in items[:40]:
        name = _text(item.get("name"), 120)
        candidates = [offer for offer in normalized if _matches_item(name, offer["item_name"])]
        if organic_required:
            candidates = [offer for offer in candidates if offer["organic_certified"]]
        if not candidates:
            missing.append(name)
            continue

        unit_groups: dict[str, list[dict[str, Any]]] = {}
        for offer in candidates:
            if offer["unit_price"] is not None and offer["comparison_unit"]:
                unit_groups.setdefault(offer["comparison_unit"], []).append(offer)
        comparable_group = max(unit_groups.values(), key=len) if unit_groups else []
        # A price-per-ounce and a price-per-count are different measurements. If
        # at least two offers share a unit, compare only inside that group.
        ranked_candidates = comparable_group if len(comparable_group) >= 2 else candidates

        def score(offer: dict[str, Any]) -> tuple[Any, ...]:
            comparable_price = offer["unit_price"] if offer["unit_price"] is not None else offer["price"]
            favorite_shop = _contains(favorite_retailers, offer["retailer_name"])
            favorite_brand = _contains(favorite_brands, offer["brand"])
            organic_penalty = 0 if offer["organic_certified"] else 1
            if objective == "lowest_price":
                return (comparable_price, not favorite_shop, not favorite_brand, offer["price"])
            if objective == "favorites":
                return (not favorite_shop, not favorite_brand, organic_penalty, comparable_price)
            if objective == "organic":
                return (organic_penalty, comparable_price, not favorite_shop, not favorite_brand)
            return (organic_penalty if profile.get("organic_preference") == "preferred" else 0, not favorite_shop, not favorite_brand, comparable_price)

        selected = min(ranked_candidates, key=score)
        comparable = [
            offer
            for offer in candidates
            if offer is not selected
            and selected["unit_price"] is not None
            and offer["unit_price"] is not None
            and offer["comparison_unit"] == selected["comparison_unit"]
        ]
        second = min(comparable, key=lambda offer: offer["unit_price"]) if comparable else None
        savings = round(second["unit_price"] - selected["unit_price"], 2) if second else 0
        reasons: list[str] = []
        if selected["organic_certified"]:
            reasons.append("Orgánico verificado por la fuente")
        if _contains(favorite_retailers, selected["retailer_name"]):
            reasons.append("Tienda favorita")
        if _contains(favorite_brands, selected["brand"]):
            reasons.append("Marca favorita")
        if savings > 0:
            reasons.append(f"Ahorra ${savings:.2f} por {selected['comparison_unit']} frente a la siguiente oferta comparable")
        if not reasons:
            reasons.append("Mejor opción disponible según tu perfil")
        recommendations.append(
            {
                **selected,
                "shopping_item": name,
                "requested_quantity": float(item.get("quantity") or 1),
                "requested_unit": _text(item.get("unit") or "unidad", 32),
                "reasons": reasons,
                "savings_per_unit": savings if savings > 0 else None,
                "comparison_retailer": second["retailer_name"] if second and savings > 0 else "",
            }
        )

    updated_at = max((row["observed_at"] for row in recommendations), default="")
    return {
        "status": "READY" if recommendations else "NO_VERIFIED_PRICES",
        "recommendations": recommendations,
        "unpriced_items": missing,
        "updated_at": updated_at,
        "rejected_offer_count": rejected,
        "notice": PRICE_NOTICE,
    }
