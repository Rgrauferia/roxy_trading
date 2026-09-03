from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


COMMERCE_STORE_VERSION = 3
SHOPPING_OBJECTIVES = {"balanced", "lowest_price", "organic", "favorites"}
ORGANIC_PREFERENCES = {"required", "preferred", "no_preference"}
AFFILIATE_DISCLOSURE = (
    "Roxy puede recibir una comisión si completas la compra desde estos enlaces; "
    "esto no aumenta el precio para ti. Revisa precio, etiqueta y disponibilidad antes de pagar."
)
AMAZON_ASSOCIATES_DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases."
AFFILIATE_CONNECTION_STATES = {
    "in_review": ("En revisión", "La solicitud fue enviada y el programa todavía debe aprobarla."),
    "approved_needs_configuration": (
        "Aprobado · falta conectar",
        "La cuenta está aprobada; falta guardar el enlace o identificador oficial en Roxy Home.",
    ),
    "unavailable": ("Sin acceso disponible", "El proveedor no está aceptando esta integración actualmente."),
    "needs_setup": ("Falta solicitar", "Todavía falta solicitar o conectar este programa."),
}

FURNITURE_AFFILIATE_TEMPLATE_ENVS = {
    "ikea": "ROXY_HOME_IKEA_AFFILIATE_LINK_TEMPLATE",
    "wayfair": "ROXY_HOME_WAYFAIR_AFFILIATE_LINK_TEMPLATE",
    "west_elm": "ROXY_HOME_WEST_ELM_AFFILIATE_LINK_TEMPLATE",
    "article": "ROXY_HOME_ARTICLE_AFFILIATE_LINK_TEMPLATE",
}

AMAZON_PRODUCT_TERMS = {
    "aceite": "cooking oil",
    "aceite de oliva": "olive oil",
    "agua": "bottled water",
    "aguacate": "avocado",
    "arroz": "rice",
    "azucar": "sugar",
    "cafe": "ground coffee",
    "cereal": "breakfast cereal",
    "detergente": "laundry detergent",
    "dulce de leche": "dulce de leche",
    "helado de dulce de leche": "dulce de leche ice cream",
    "galletas": "cookies",
    "harina": "all purpose flour",
    "harina de trigo": "all purpose flour",
    "huevos": "eggs",
    "jabon": "soap",
    "leche": "milk",
    "levadura": "active dry yeast",
    "mantequilla": "butter",
    "papel higienico": "toilet paper",
    "papel toalla": "paper towels",
    "pan": "bread",
    "pasta": "pasta",
    "platano": "banana",
    "pollo": "chicken",
    "queso": "cheese",
    "sal": "salt",
    "suavizante": "fabric softener",
    "tomate": "tomato",
    "vainilla": "vanilla extract",
    "yogur": "yogurt",
}

AMAZON_DIETARY_TERMS = {
    "bajo sodio": "low sodium",
    "keto": "keto",
    "organico": "organic",
    "sin azucar": "sugar free",
    "sin gluten": "gluten free",
    "sin lactosa": "lactose free",
    "vegano": "vegan",
    "vegetariano": "vegetarian",
}

AMAZON_UNIT_TERMS = {
    "bolsa": "bag",
    "botella": "bottle",
    "caja": "box",
    "envase": "container",
    "galon": "gallon",
    "litro": "liter",
    "lata": "can",
    "paquete": "pack",
    "rollo": "roll",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int = 160) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _string_list(values: Any, *, limit: int = 30) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for raw in values[:limit]:
        value = _text(raw, 80)
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _safe_https(value: Any) -> str:
    url = _text(value, 2000)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("El proveedor devolvió un enlace de compra no seguro.")
    return url


def _provider_json(request: urllib.request.Request, provider_name: str) -> dict[str, Any]:
    """Read one server-side catalog response without leaking credentials or raw errors."""
    try:
        with urllib.request.urlopen(request, timeout=12) as response:  # nosec B310: fixed HTTPS providers
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise ConnectionError(f"{provider_name} no pudo consultar su catálogo en este momento.") from exc
    if not isinstance(payload, dict):
        raise ConnectionError(f"{provider_name} devolvió una respuesta de catálogo no válida.")
    return payload


def _ebay_catalog_links(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    client_id = _text(os.getenv("ROXY_HOME_EBAY_CLIENT_ID"), 500)
    client_secret = _text(os.getenv("ROXY_HOME_EBAY_CLIENT_SECRET"), 500)
    if not client_id or not client_secret:
        raise RuntimeError("eBay Browse todavía necesita Client ID y Client Secret exclusivos de Home.")
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    token_request = urllib.request.Request(
        "https://api.ebay.com/identity/v1/oauth2/token",
        data=urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        }).encode("utf-8"),
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    token = _text(_provider_json(token_request, "eBay").get("access_token"), 4000)
    if not token:
        raise ConnectionError("eBay no entregó un token de catálogo válido.")
    links: list[dict[str, Any]] = []
    campaign = _text(os.getenv("ROXY_HOME_EBAY_AFFILIATE_CAMPAIGN_ID"), 100)
    for item in items[:20]:
        query = _text(item.get("query") or item.get("name"), 180)
        params = urllib.parse.urlencode({"q": query, "limit": 3, "filter": "buyingOptions:{FIXED_PRICE}"})
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"}
        context = []
        if campaign:
            context.append(f"affiliateCampaignId={campaign}")
        postal_code = _text(item.get("postal_code"), 12)
        if postal_code:
            context.append(f"contextualLocation=country%3DUS%2Czip%3D{urllib.parse.quote(postal_code)}")
        if context:
            headers["X-EBAY-C-ENDUSERCTX"] = ",".join(context)
        request = urllib.request.Request(
            f"https://api.ebay.com/buy/browse/v1/item_summary/search?{params}", headers=headers,
        )
        for product in (_provider_json(request, "eBay").get("itemSummaries") or [])[:3]:
            if not isinstance(product, dict):
                continue
            price = product.get("price") or {}
            destination = product.get("itemAffiliateWebUrl") or product.get("itemWebUrl")
            try:
                url = _safe_https(destination)
                image_url = _safe_https((product.get("image") or {}).get("imageUrl")) if product.get("image") else ""
            except ValueError:
                continue
            links.append({
                "label": _text(product.get("title") or item.get("name"), 180),
                "shopping_item": _text(item.get("name"), 120),
                "quantity": item.get("quantity") or 1, "unit": item.get("unit") or "unidad",
                "category": item.get("category") or "HOUSEHOLD", "reason": item.get("reason") or "Resultado real de eBay.",
                "price": float(price.get("value") or 0), "currency": _text(price.get("currency") or "USD", 3),
                "condition": _text(product.get("condition"), 80), "image_url": image_url, "url": url,
            })
    return links


def _best_buy_catalog_links(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    api_key = _text(os.getenv("ROXY_HOME_BEST_BUY_API_KEY"), 500)
    if not api_key:
        raise RuntimeError("Best Buy todavía necesita una API key exclusiva de Home.")
    links: list[dict[str, Any]] = []
    for item in items[:20]:
        query = _text(item.get("query") or item.get("name"), 120)
        search = urllib.parse.quote(query, safe="")
        params = urllib.parse.urlencode({
            "apiKey": api_key, "format": "json", "pageSize": 3, "sort": "salePrice.asc",
            "show": "sku,name,salePrice,regularPrice,url,image,onlineAvailability,manufacturer",
        })
        request = urllib.request.Request(f"https://api.bestbuy.com/v1/products(search={search})?{params}", headers={"Accept": "application/json"})
        for product in (_provider_json(request, "Best Buy").get("products") or [])[:3]:
            if not isinstance(product, dict):
                continue
            try:
                url = _safe_https(product.get("url"))
                image_url = _safe_https(product.get("image")) if product.get("image") else ""
            except ValueError:
                continue
            links.append({
                "label": _text(product.get("name") or item.get("name"), 180),
                "shopping_item": _text(item.get("name"), 120),
                "quantity": item.get("quantity") or 1, "unit": item.get("unit") or "unidad",
                "category": item.get("category") or "HOUSEHOLD", "reason": item.get("reason") or "Resultado real de Best Buy.",
                "price": float(product.get("salePrice") or 0), "regular_price": float(product.get("regularPrice") or 0),
                "currency": "USD", "available": product.get("onlineAvailability") is True,
                "brand": _text(product.get("manufacturer"), 80), "image_url": image_url, "url": url,
            })
    return links


def _impact_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: Any = payload.get("Items", payload.get("items"))
    if isinstance(rows, dict):
        rows = rows.get("Item", rows.get("item", []))
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list) and payload.get("Name"):
        rows = [payload]
    return [row for row in (rows or []) if isinstance(row, dict)]


def _impact_catalog_links(items: list[dict[str, Any]], tracking_id: str) -> list[dict[str, Any]]:
    account_sid = _text(os.getenv("ROXY_HOME_IMPACT_ACCOUNT_SID"), 500)
    auth_token = _text(os.getenv("ROXY_HOME_IMPACT_AUTH_TOKEN"), 500)
    if not account_sid or not auth_token:
        raise RuntimeError("Impact.com todavía necesita Account SID y Auth Token exclusivos de Home.")
    basic = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    auth_headers = {"Authorization": f"Basic {basic}", "Accept": "application/json"}
    links: list[dict[str, Any]] = []
    for item in items[:10]:
        query = _text(item.get("query") or item.get("name"), 180)
        params = urllib.parse.urlencode({"Keyword": query, "PageSize": 3})
        request = urllib.request.Request(
            f"https://api.impact.com/Mediapartners/{urllib.parse.quote(account_sid, safe='')}/Catalogs/ItemSearch?{params}",
            headers=auth_headers,
        )
        for product in _impact_items(_provider_json(request, "Impact.com"))[:3]:
            try:
                destination = _safe_https(product.get("Url"))
                image_url = _safe_https(product.get("ImageUrl")) if product.get("ImageUrl") else ""
            except ValueError:
                continue
            product_url = destination
            affiliate_connected = False
            campaign_id = _text(product.get("CampaignId"), 80)
            if campaign_id:
                link_params = {
                    "Type": "Regular", "DeepLink": destination,
                    "subId1": _text(tracking_id, 64),
                }
                media_property = _text(os.getenv("ROXY_HOME_IMPACT_MEDIA_PROPERTY_ID"), 80)
                if media_property:
                    link_params["MediaPartnerPropertyId"] = media_property
                link_request = urllib.request.Request(
                    f"https://api.impact.com/Mediapartners/{urllib.parse.quote(account_sid, safe='')}/Programs/{urllib.parse.quote(campaign_id, safe='')}/TrackingLinks?{urllib.parse.urlencode(link_params)}",
                    headers=auth_headers, method="POST",
                )
                try:
                    tracked = _provider_json(link_request, "Impact.com").get("TrackingURL")
                    if tracked:
                        product_url = _safe_https(tracked)
                        affiliate_connected = True
                except (ConnectionError, ValueError):
                    product_url = destination
            links.append({
                "label": _text(product.get("Name") or item.get("name"), 180),
                "shopping_item": _text(item.get("name"), 120),
                "quantity": item.get("quantity") or 1, "unit": item.get("unit") or "unidad",
                "category": item.get("category") or "HOUSEHOLD", "reason": item.get("reason") or "Resultado real de Impact.com.",
                "price": float(product.get("CurrentPrice") or 0), "regular_price": float(product.get("OriginalPrice") or 0),
                "currency": _text(product.get("Currency") or "USD", 3),
                "available": _text(product.get("StockAvailability"), 40) not in {"OutofStock", "OutOfStock"},
                "brand": _text(product.get("Manufacturer") or product.get("CampaignName"), 80),
                "image_url": image_url, "url": product_url, "affiliate_connected": affiliate_connected,
            })
    return links


def _catalog_search_fallback(provider_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    templates = {
        "ebay": "https://www.ebay.com/sch/i.html?_nkw={query}",
        "best_buy": "https://www.bestbuy.com/site/searchpage.jsp?st={query}",
        "impact": "https://www.google.com/search?tbm=shop&q={query}",
    }
    return [{
        "label": _text(item.get("name"), 180),
        "shopping_item": _text(item.get("name"), 120),
        "quantity": item.get("quantity") or 1, "unit": item.get("unit") or "unidad",
        "category": item.get("category") or "HOUSEHOLD",
        "reason": "Búsqueda oficial de respaldo; el comercio confirmará producto, imagen, precio y disponibilidad.",
        "url": _safe_https(templates[provider_id].replace(
            "{query}", urllib.parse.quote_plus(_text(item.get("query") or item.get("name"), 180))
        )),
    } for item in items[:20]]


def _fold(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", _text(value, 160))
    return normalized.encode("ascii", "ignore").decode("ascii").casefold()


def _amazon_catalog_term(name: Any) -> str:
    folded = _fold(name)
    if folded in AMAZON_PRODUCT_TERMS:
        return AMAZON_PRODUCT_TERMS[folded]
    for source, target in sorted(AMAZON_PRODUCT_TERMS.items(), key=lambda row: len(row[0]), reverse=True):
        if re.search(rf"\b{re.escape(source)}\b", folded):
            remainder = re.sub(rf"\b{re.escape(source)}\b", "", folded).strip()
            return " ".join(part for part in (remainder, target) if part)
    return _text(name, 120)


def _amazon_search_query(row: dict[str, Any]) -> str:
    preferences = row.get("shopping_preferences") or {}
    parts: list[str] = []
    organic = str(preferences.get("organic_preference") or "")
    if organic in {"required", "preferred"}:
        parts.append("organic")
    for label in preferences.get("dietary_labels") or []:
        translated = AMAZON_DIETARY_TERMS.get(_fold(label), _text(label, 50))
        if translated and translated.casefold() not in {part.casefold() for part in parts}:
            parts.append(translated)
    brand = _text(preferences.get("favorite_brand"), 80)
    if brand:
        parts.append(brand)
    parts.append(_amazon_catalog_term(row.get("name")))
    unit_term = AMAZON_UNIT_TERMS.get(_fold(row.get("unit")))
    quantity = float(row.get("quantity") or 1)
    if unit_term:
        parts.append(f"{int(quantity) if quantity.is_integer() else quantity:g} {unit_term}")
    return " ".join(part for part in parts if part)


class HomeCommerceStore:
    """Durable preferences and purchase preparations, isolated from Trading."""

    def __init__(self, path: str | Path = "data/roxy_home_commerce.json") -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "schema_version": COMMERCE_STORE_VERSION,
            "profiles": {},
            "preparations": {},
            "handoffs": {},
            "price_history": {},
            "price_alerts": {},
        }

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            return self._empty()
        if not isinstance(payload, dict):
            return self._empty()
        payload["schema_version"] = COMMERCE_STORE_VERSION
        payload.setdefault("profiles", {})
        payload.setdefault("preparations", {})
        payload.setdefault("handoffs", {})
        payload.setdefault("price_history", {})
        payload.setdefault("price_alerts", {})
        return payload

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload["schema_version"] = COMMERCE_STORE_VERSION
        handle, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, self.path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def _mutate(self, callback: Callable[[dict[str, Any]], Any]) -> Any:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            try:
                self.lock_path.chmod(0o600)
            except OSError:
                pass
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._read_unlocked()
                result = callback(payload)
                self._write_unlocked(payload)
                return result
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def default_profile() -> dict[str, Any]:
        return {
            "objective": "balanced",
            "organic_preference": "no_preference",
            "favorite_retailers": [],
            "favorite_brands": [],
            "avoided_brands": [],
            "dietary_labels": [],
            "allow_substitutions": True,
            "postal_code": "",
            "price_alerts_enabled": True,
            "price_drop_percent": 10,
            "location_enabled": False,
            "latitude": None,
            "longitude": None,
            "location_accuracy_m": None,
            "location_updated_at": "",
        }

    def profile(self, owner_key: str) -> dict[str, Any]:
        stored = self._read_unlocked().get("profiles", {}).get(owner_key)
        return {**self.default_profile(), **(deepcopy(stored) if isinstance(stored, dict) else {})}

    def update_profile(self, owner_key: str, values: dict[str, Any]) -> dict[str, Any]:
        objective = _text(values.get("objective"), 32)
        organic = _text(values.get("organic_preference"), 32)
        if objective not in SHOPPING_OBJECTIVES:
            raise ValueError("Objetivo de compra no válido.")
        if organic not in ORGANIC_PREFERENCES:
            raise ValueError("Preferencia orgánica no válida.")
        postal_code = re.sub(r"[^A-Za-z0-9 -]", "", _text(values.get("postal_code"), 12))
        try:
            price_drop_percent = int(values.get("price_drop_percent", 10))
        except (TypeError, ValueError) as exc:
            raise ValueError("El porcentaje de alerta no es válido.") from exc
        if not 5 <= price_drop_percent <= 50:
            raise ValueError("La alerta de precio debe estar entre 5 % y 50 %.")
        location_enabled = values.get("location_enabled") is True
        latitude = values.get("latitude")
        longitude = values.get("longitude")
        accuracy = values.get("location_accuracy_m")
        if location_enabled:
            try:
                latitude = round(float(latitude), 3)
                longitude = round(float(longitude), 3)
                accuracy = round(max(0.0, float(accuracy or 0)), 0)
            except (TypeError, ValueError) as exc:
                raise ValueError("La ubicación autorizada no es válida.") from exc
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError("La ubicación autorizada no es válida.")
        else:
            latitude = longitude = accuracy = None
        profile = {
            "objective": objective,
            "organic_preference": organic,
            "favorite_retailers": _string_list(values.get("favorite_retailers")),
            "favorite_brands": _string_list(values.get("favorite_brands")),
            "avoided_brands": _string_list(values.get("avoided_brands")),
            "dietary_labels": _string_list(values.get("dietary_labels")),
            "allow_substitutions": values.get("allow_substitutions") is True,
            "postal_code": postal_code,
            "price_alerts_enabled": values.get("price_alerts_enabled", True) is True,
            "price_drop_percent": price_drop_percent,
            "location_enabled": location_enabled,
            "latitude": latitude,
            "longitude": longitude,
            "location_accuracy_m": accuracy,
            "location_updated_at": _now_iso() if location_enabled else "",
            "updated_at": _now_iso(),
        }

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            payload["profiles"][owner_key] = profile
            return deepcopy(profile)

        return self._mutate(apply)

    def record_price_recommendations(
        self,
        owner_key: str,
        recommendations: list[dict[str, Any]],
        *,
        alert_percent: int = 10,
        alerts_enabled: bool = True,
    ) -> dict[str, Any]:
        """Keep a bounded private history and detect comparable price drops."""

        threshold = max(5, min(int(alert_percent), 50))

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            history = payload["price_history"].setdefault(owner_key, [])
            alert_rows = payload["price_alerts"].setdefault(owner_key, [])
            created: list[dict[str, Any]] = []
            for offer in recommendations[:100]:
                item_name = _text(offer.get("shopping_item"), 120)
                retailer_name = _text(offer.get("retailer_name"), 80)
                observed_at = _text(offer.get("observed_at"), 80) or _now_iso()
                unit_price = offer.get("unit_price")
                comparison_unit = _text(offer.get("comparison_unit"), 32)
                price = round(float(offer.get("price") or 0), 2)
                if not item_name or not retailer_name or price <= 0:
                    continue
                metric = round(float(unit_price), 4) if unit_price not in (None, "") and comparison_unit else price
                metric_unit = comparison_unit or _text(offer.get("package_label"), 80)
                previous = (
                    next(
                        (
                            row for row in reversed(history)
                            if _fold(row.get("item_name")) == _fold(item_name)
                            and row.get("metric_unit") == metric_unit
                            and float(row.get("metric") or 0) > 0
                        ),
                        None,
                    )
                    if metric_unit
                    else None
                )
                history_row = {
                    "item_name": item_name,
                    "retailer_name": retailer_name,
                    "product_title": _text(offer.get("product_title"), 180),
                    "package_label": _text(offer.get("package_label"), 80),
                    "price": price,
                    "metric": metric,
                    "metric_unit": metric_unit,
                    "currency": _text(offer.get("currency") or "USD", 3),
                    "observed_at": observed_at,
                    "product_url": _text(offer.get("product_url"), 2000),
                }
                duplicate = next(
                    (
                        row for row in reversed(history[-30:])
                        if row.get("item_name") == item_name
                        and row.get("retailer_name") == retailer_name
                        and row.get("metric") == metric
                        and row.get("observed_at") == observed_at
                    ),
                    None,
                )
                if duplicate is None:
                    history.append(history_row)
                baseline = float(previous.get("metric") or 0) if previous else 0
                drop = round((baseline - metric) / baseline * 100, 1) if baseline > metric > 0 else 0
                if alerts_enabled and drop >= threshold:
                    alert = {
                        "id": uuid4().hex,
                        **history_row,
                        "previous_metric": baseline,
                        "drop_percent": drop,
                        "message": f"{item_name} bajó {drop:g} % y ahora conviene en {retailer_name}.",
                        "created_at": _now_iso(),
                    }
                    already_alerted = any(
                        row.get("item_name") == item_name
                        and row.get("retailer_name") == retailer_name
                        and row.get("metric") == metric
                        for row in alert_rows[-30:]
                    )
                    if not already_alerted:
                        alert_rows.append(alert)
                        created.append(deepcopy(alert))
            payload["price_history"][owner_key] = history[-1500:]
            payload["price_alerts"][owner_key] = alert_rows[-100:]
            return {
                "new_alerts": created,
                "recent_alerts": deepcopy(list(reversed(alert_rows[-10:]))),
                "observation_count": len(payload["price_history"][owner_key]),
            }

        return self._mutate(apply)

    def price_activity(self, owner_key: str) -> dict[str, Any]:
        payload = self._read_unlocked()
        history = payload.get("price_history", {}).get(owner_key, [])
        alerts = payload.get("price_alerts", {}).get(owner_key, [])
        return {
            "observation_count": len(history) if isinstance(history, list) else 0,
            "recent_alerts": deepcopy(list(reversed(alerts[-10:]))) if isinstance(alerts, list) else [],
        }

    def save_preparation(
        self,
        owner_key: str,
        household_user: str,
        *,
        source: str,
        source_title: str,
        items: list[dict[str, Any]],
        providers: list[str],
    ) -> dict[str, Any]:
        row = {
            "id": uuid4().hex,
            "tracking_id": uuid4().hex,
            "owner_key": owner_key,
            "household_user": household_user,
            "source": source,
            "source_title": _text(source_title, 180),
            "items": deepcopy(items),
            "providers": providers,
            "created_at": _now_iso(),
            "disclosure": AFFILIATE_DISCLOSURE,
        }

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            payload["preparations"][row["id"]] = row
            owned = [
                value for value in payload["preparations"].values()
                if isinstance(value, dict) and value.get("owner_key") == owner_key
            ]
            owned.sort(key=lambda value: str(value.get("created_at") or ""), reverse=True)
            for stale in owned[20:]:
                payload["preparations"].pop(str(stale.get("id")), None)
            return deepcopy(row)

        return self._mutate(apply)

    def preparation(self, owner_key: str, preparation_id: str) -> dict[str, Any]:
        row = self._read_unlocked().get("preparations", {}).get(str(preparation_id))
        if not isinstance(row, dict) or row.get("owner_key") != owner_key:
            raise KeyError(preparation_id)
        return deepcopy(row)

    def record_handoff(
        self,
        owner_key: str,
        preparation_id: str,
        *,
        provider_id: str,
        provider_name: str,
        mode: str,
        link_count: int,
    ) -> dict[str, Any]:
        """Record a retailer handoff, never a claimed purchase or conversion."""

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            preparation = payload["preparations"].get(preparation_id)
            if not isinstance(preparation, dict) or preparation.get("owner_key") != owner_key:
                raise KeyError(preparation_id)
            existing = next(
                (
                    value
                    for value in payload["handoffs"].values()
                    if isinstance(value, dict)
                    and value.get("owner_key") == owner_key
                    and value.get("preparation_id") == preparation_id
                    and value.get("provider_id") == provider_id
                ),
                None,
            )
            if existing:
                return deepcopy(existing)
            row = {
                "id": uuid4().hex,
                "owner_key": owner_key,
                "preparation_id": preparation_id,
                "provider_id": _text(provider_id, 32),
                "provider_name": _text(provider_name, 80),
                "mode": _text(mode, 32),
                "source": _text(preparation.get("source"), 32),
                "source_title": _text(preparation.get("source_title"), 180),
                "item_count": len(preparation.get("items") or []),
                "link_count": max(0, int(link_count)),
                "status": "READY_FOR_REVIEW",
                "created_at": _now_iso(),
            }
            payload["handoffs"][row["id"]] = row
            owned = [
                value for value in payload["handoffs"].values()
                if isinstance(value, dict) and value.get("owner_key") == owner_key
            ]
            owned.sort(key=lambda value: str(value.get("created_at") or ""), reverse=True)
            for stale in owned[100:]:
                payload["handoffs"].pop(str(stale.get("id")), None)
            return deepcopy(row)

        return self._mutate(apply)

    def activity(self, owner_key: str, *, limit: int = 10) -> dict[str, Any]:
        rows = [
            deepcopy(value)
            for value in self._read_unlocked().get("handoffs", {}).values()
            if isinstance(value, dict) and value.get("owner_key") == owner_key
        ]
        rows.sort(key=lambda value: str(value.get("created_at") or ""), reverse=True)
        counts: dict[str, int] = {}
        for row in rows:
            provider_id = _text(row.get("provider_id"), 32)
            if provider_id:
                counts[provider_id] = counts.get(provider_id, 0) + 1
            row.pop("owner_key", None)
        return {
            "handoff_count": len(rows),
            "provider_counts": counts,
            "recent": rows[: max(0, min(int(limit), 25))],
            "notice": "Estas son entregas preparadas al comercio, no compras confirmadas.",
        }


def public_providers() -> list[dict[str, Any]]:
    instacart_api_configured = bool(_text(os.getenv("ROXY_HOME_INSTACART_API_KEY")))
    instacart_affiliate_configured = bool(_text(os.getenv("ROXY_HOME_INSTACART_AFFILIATE_URL")))
    def connection(env_name: str, configured: bool) -> tuple[str, str, str]:
        if configured:
            return "ready", "Listo", "La conexión está activa."
        requested = _text(os.getenv(env_name), 48).casefold().replace("-", "_")
        state = requested if requested in AFFILIATE_CONNECTION_STATES else "needs_setup"
        label, next_step = AFFILIATE_CONNECTION_STATES[state]
        return state, label, next_step

    definitions = [
        {
            "id": "instacart",
            "name": "Instacart",
            "mode": "full_list" if instacart_api_configured else "affiliate_link",
            "configured": instacart_api_configured or instacart_affiliate_configured,
            "description": (
                "Convierte toda la lista en una compra revisable dentro de Instacart."
                if instacart_api_configured
                else "Abre Instacart con el enlace afiliado aprobado; la lista completa requiere la API."
            ),
        },
        {
            "id": "kroger",
            "name": "Kroger",
            "mode": "product_links",
            "configured": bool(
                _text(os.getenv("ROXY_HOME_KROGER_CLIENT_ID"))
                and _text(os.getenv("ROXY_HOME_KROGER_CLIENT_SECRET"))
            ),
            "description": "Consulta catálogo y precios reales de la tienda Kroger más cercana y abre el producto para revisarlo.",
        },
        {
            "id": "amazon",
            "name": "Amazon",
            "mode": "product_links",
            "configured": bool(_text(os.getenv("ROXY_HOME_AMAZON_ASSOCIATE_TAG"))),
            "description": "Busca despensa, limpieza y productos recurrentes mediante enlaces de asociado.",
            "disclosure": AMAZON_ASSOCIATES_DISCLOSURE,
        },
        {
            "id": "walmart",
            "name": "Walmart",
            "mode": "product_links",
            "configured": "{destination}" in str(os.getenv("ROXY_HOME_WALMART_AFFILIATE_LINK_TEMPLATE") or ""),
            "description": "Abre productos en Walmart mediante el enlace aprobado de Impact.",
        },
        {
            "id": "target",
            "name": "Target",
            "mode": "product_links",
            "configured": "{destination}" in str(os.getenv("ROXY_HOME_TARGET_AFFILIATE_LINK_TEMPLATE") or ""),
            "description": "Abre productos de Target mediante el enlace aprobado del programa.",
        },
        {
            "id": "thrive",
            "name": "Thrive Market",
            "mode": "product_links",
            "configured": "{destination}" in str(os.getenv("ROXY_HOME_THRIVE_AFFILIATE_LINK_TEMPLATE") or ""),
            "description": "Alternativa especializada para productos orgánicos y dietas específicas.",
        },
        {
            "id": "ikea",
            "name": "IKEA",
            "mode": "product_links",
            "configured": True,
            "affiliate_connected": "{destination}" in str(os.getenv(FURNITURE_AFFILIATE_TEMPLATE_ENVS["ikea"]) or ""),
            "design_only": True,
            "description": "Busca muebles y accesorios en el catálogo oficial de IKEA.",
        },
        {
            "id": "wayfair",
            "name": "Wayfair",
            "mode": "product_links",
            "configured": True,
            "affiliate_connected": "{destination}" in str(os.getenv(FURNITURE_AFFILIATE_TEMPLATE_ENVS["wayfair"]) or ""),
            "design_only": True,
            "description": "Compara una selección amplia de muebles y decoración en Wayfair.",
        },
        {
            "id": "west_elm",
            "name": "West Elm",
            "mode": "product_links",
            "configured": True,
            "affiliate_connected": "{destination}" in str(os.getenv(FURNITURE_AFFILIATE_TEMPLATE_ENVS["west_elm"]) or ""),
            "design_only": True,
            "description": "Explora muebles contemporáneos en el catálogo oficial de West Elm.",
        },
        {
            "id": "article",
            "name": "Article",
            "mode": "product_links",
            "configured": True,
            "affiliate_connected": "{destination}" in str(os.getenv(FURNITURE_AFFILIATE_TEMPLATE_ENVS["article"]) or ""),
            "design_only": True,
            "description": "Busca muebles contemporáneos y modernos en Article.",
        },
        {
            "id": "ebay",
            "name": "eBay",
            "mode": "product_links",
            "configured": bool(_text(os.getenv("ROXY_HOME_EBAY_CLIENT_ID")) and _text(os.getenv("ROXY_HOME_EBAY_CLIENT_SECRET"))),
            "requires_credentials": True,
            "design_only": True,
            "description": "Consulta eBay Browse para piezas nuevas, usadas y vintage con precio e imagen reales.",
        },
        {
            "id": "best_buy",
            "name": "Best Buy",
            "mode": "product_links",
            "configured": bool(_text(os.getenv("ROXY_HOME_BEST_BUY_API_KEY"))),
            "requires_credentials": True,
            "design_only": True,
            "description": "Consulta el catálogo de Best Buy para tecnología, electrodomésticos e iluminación inteligente.",
        },
        {
            "id": "impact",
            "name": "Impact.com",
            "mode": "product_links",
            "configured": bool(_text(os.getenv("ROXY_HOME_IMPACT_ACCOUNT_SID")) and _text(os.getenv("ROXY_HOME_IMPACT_AUTH_TOKEN"))),
            "requires_credentials": True,
            "design_only": True,
            "description": "Consulta catálogos de las marcas aprobadas y crea enlaces de seguimiento solo al confirmarlos.",
        },
    ]
    status_env = {
        "instacart": "ROXY_HOME_INSTACART_AFFILIATE_STATUS",
        "kroger": "ROXY_HOME_KROGER_STATUS",
        "amazon": "ROXY_HOME_AMAZON_AFFILIATE_STATUS",
        "walmart": "ROXY_HOME_WALMART_AFFILIATE_STATUS",
        "target": "ROXY_HOME_TARGET_AFFILIATE_STATUS",
        "thrive": "ROXY_HOME_THRIVE_AFFILIATE_STATUS",
        "ikea": "ROXY_HOME_IKEA_STATUS",
        "wayfair": "ROXY_HOME_WAYFAIR_STATUS",
        "west_elm": "ROXY_HOME_WEST_ELM_STATUS",
        "article": "ROXY_HOME_ARTICLE_STATUS",
        "ebay": "ROXY_HOME_EBAY_STATUS",
        "best_buy": "ROXY_HOME_BEST_BUY_STATUS",
        "impact": "ROXY_HOME_IMPACT_STATUS",
    }
    for provider in definitions:
        if provider.get("design_only"):
            if provider.get("requires_credentials"):
                state, label, next_step = connection(status_env[provider["id"]], bool(provider.get("configured")))
                provider["connection_status"] = state
                provider["status_label"] = label
                provider["next_step"] = next_step
                continue
            if provider.get("affiliate_connected"):
                provider["connection_status"] = "affiliate_ready"
                provider["status_label"] = "Afiliado listo"
                provider["next_step"] = "El catálogo oficial y el seguimiento afiliado están activos."
            else:
                provider["connection_status"] = "catalog_ready"
                provider["status_label"] = "Catálogo listo"
                provider["next_step"] = (
                    "La búsqueda oficial funciona. Falta una plantilla afiliada aprobada para atribuir comisiones."
                )
            continue
        state, label, next_step = connection(
            status_env[provider["id"]], bool(provider.get("configured"))
        )
        provider["connection_status"] = state
        provider["status_label"] = label
        provider["next_step"] = next_step
    return definitions


def public_design_connections() -> list[dict[str, str]]:
    """Describe Renueva integrations without exposing secrets or claiming live data."""
    definitions = [
        ("walmart_affiliate", "Walmart Affiliate API", "Productos, imágenes, categorías, promociones, precio y disponibilidad por código postal", "Decoración, lámparas, muebles económicos y artículos del hogar", bool(_text(os.getenv("ROXY_HOME_WALMART_AFFILIATE_API_KEY"))), "Configurar y validar el catálogo afiliado de Walmart."),
        ("ebay_browse", "eBay Browse API", "Productos nuevos, usados y vintage; búsqueda por texto, categoría, GTIN e imagen", "Piezas únicas, muebles usados y alternativas económicas", bool(_text(os.getenv("ROXY_HOME_EBAY_CLIENT_ID")) and _text(os.getenv("ROXY_HOME_EBAY_CLIENT_SECRET"))), "Registrar Home y autorizar Browse API."),
        ("best_buy_products", "Best Buy Products API", "Precios, disponibilidad, especificaciones e imágenes actualizadas", "Televisores, electrodomésticos, iluminación y hogar inteligente", bool(_text(os.getenv("ROXY_HOME_BEST_BUY_API_KEY"))), "Añadir la clave exclusiva de Best Buy para Home."),
        ("impact", "Impact.com", "Catálogos de marcas, promociones y enlaces de afiliado", "Conectar varias tiendas desde una sola plataforma", bool(_text(os.getenv("ROXY_HOME_IMPACT_ACCOUNT_SID")) and _text(os.getenv("ROXY_HOME_IMPACT_AUTH_TOKEN"))), "Conectar la cuenta aprobada de Impact.com."),
        ("cj_affiliate", "CJ Affiliate", "Búsqueda por precio, país, UPC y comercio", "Ampliar marcas de muebles y decoración", bool(_text(os.getenv("ROXY_HOME_CJ_API_KEY"))), "Solicitar acceso a anunciantes y su catálogo."),
        ("awin", "Awin", "Catálogos y feeds de anunciantes aprobados", "Productos, promociones y monetización", bool(_text(os.getenv("ROXY_HOME_AWIN_API_TOKEN"))), "Conectar anunciantes aprobados de Awin."),
        ("amazon_creators", "Amazon Creators API", "Catálogo, imágenes, variaciones, ofertas y enlaces de afiliado", "Decoración, accesorios y alternativas de amplia variedad", bool(_text(os.getenv("ROXY_HOME_AMAZON_CREATORS_CLIENT_ID")) and _text(os.getenv("ROXY_HOME_AMAZON_CREATORS_CLIENT_SECRET"))), "Completar la conexión de catálogo; un enlace afiliado no confirma precio."),
        ("pinterest_trends", "Pinterest Trends API", "Palabras, estilos y temas con interés creciente", "Detectar colores, estilos y temas en tendencia", bool(_text(os.getenv("ROXY_HOME_PINTEREST_ACCESS_TOKEN"))), "Solicitar acceso autorizado a tendencias de Pinterest."),
        ("dataforseo_merchant", "DataForSEO Merchant API", "Resultados, vendedores, precios y reseñas de Google Shopping", "Comparar un producto entre diferentes tiendas", bool(_text(os.getenv("ROXY_HOME_DATAFORSEO_LOGIN")) and _text(os.getenv("ROXY_HOME_DATAFORSEO_PASSWORD"))), "Conectar Merchant API y definir presupuesto de consultas."),
    ]
    return [{
        "id": key, "name": name, "capabilities": capabilities, "use": use,
        "connection_status": "ready" if configured else "needs_setup",
        "status_label": "Conectada" if configured else "Requiere conexión",
        "next_step": "Disponible para consultas verificadas." if configured else next_step,
    } for key, name, capabilities, use, configured, next_step in definitions]


def personalize_items(raw_items: list[dict[str, Any]], profile: dict[str, Any], allergies: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    organic = profile.get("organic_preference")
    objective = profile.get("objective")
    brand = next(iter(profile.get("favorite_brands") or []), "")
    for raw in raw_items[:100]:
        name = _text(raw.get("name"), 120)
        if not name:
            continue
        query_parts = []
        if organic in {"required", "preferred"} or objective == "organic":
            query_parts.append("orgánico")
        query_parts.append(name)
        query_parts.extend((profile.get("dietary_labels") or [])[:3])
        if objective == "favorites" and brand:
            query_parts.append(brand)
        reasons = {
            "lowest_price": "Prioriza comparar el menor precio por unidad en la tienda.",
            "organic": "Prioriza una opción orgánica disponible.",
            "favorites": "Prioriza tus marcas y productos habituales.",
            "balanced": "Equilibra tus preferencias, disponibilidad y valor.",
        }
        rows.append(
            {
                "name": name,
                "quantity": float(raw.get("quantity") or 1),
                "unit": _text(raw.get("unit") or "unidad", 32) or "unidad",
                "category": _text(raw.get("category") or "GENERAL", 32) or "GENERAL",
                "query": " ".join(query_parts),
                "reason": reasons.get(str(objective), reasons["balanced"]),
                "allergen_review_required": bool(allergies),
                "avoided_brands": list(profile.get("avoided_brands") or []),
                "shopping_preferences": {
                    "organic_preference": organic,
                    "dietary_labels": list(profile.get("dietary_labels") or [])[:3],
                    "favorite_brand": brand if objective == "favorites" else "",
                },
                "postal_code": _text(profile.get("postal_code"), 12),
                # Design proposals use these fields to keep an honest estimated
                # budget visible until a retailer supplies the real price.
                "source_id": _text(raw.get("id"), 64),
                "budget_target": round(float(raw.get("budget_target") or 0), 2),
                "priority": _text(raw.get("priority"), 24),
            }
        )
    return rows


def _affiliate_template_link(template: str, destination: str, query: str, tracking_id: str = "") -> str:
    if "{destination}" not in template:
        raise ValueError("El enlace afiliado de este proveedor no está configurado.")
    value = template.replace("{destination}", urllib.parse.quote(destination, safe=""))
    value = value.replace("{query}", urllib.parse.quote_plus(query))
    value = value.replace("{sub_id}", urllib.parse.quote_plus(_text(tracking_id, 64)))
    return _safe_https(value)


def create_purchase_links(provider_id: str, preparation: dict[str, Any]) -> dict[str, Any]:
    providers = {row["id"]: row for row in public_providers()}
    provider = providers.get(provider_id)
    if not provider or provider_id not in preparation.get("providers", []):
        raise ValueError("Proveedor no permitido para esta preparación.")
    if not provider["configured"]:
        raise RuntimeError("Este proveedor todavía necesita su cuenta de afiliación o clave aprobada.")
    items = preparation.get("items") or []
    if provider_id in {"ebay", "best_buy", "impact"}:
        catalog_error = False
        try:
            if provider_id == "ebay":
                links = _ebay_catalog_links(items)
            elif provider_id == "best_buy":
                links = _best_buy_catalog_links(items)
            else:
                links = _impact_catalog_links(items, str(preparation.get("tracking_id") or ""))
        except ConnectionError:
            links = []
            catalog_error = True
        if not links:
            links = _catalog_search_fallback(provider_id, items)
        return {
            "provider": provider,
            "mode": "product_links",
            "links": links,
            "provider_disclosure": (
                "Resultados consultados directamente en el catálogo del comercio. "
                "Confirma medidas, condición, disponibilidad, envío y precio final antes de comprar."
            ),
            "guidance": (
                f"Roxy encontró opciones reales en {provider['name']} para comparar con tu propuesta."
                if not catalog_error and any(float(row.get("price") or 0) > 0 for row in links)
                else f"El catálogo en vivo de {provider['name']} no respondió o no encontró coincidencias; Roxy conservó búsquedas oficiales de respaldo sin inventar precios."
            ),
        }
    if provider_id == "instacart":
        api_key = _text(os.getenv("ROXY_HOME_INSTACART_API_KEY"), 1000)
        if not api_key:
            affiliate_url = _safe_https(os.getenv("ROXY_HOME_INSTACART_AFFILIATE_URL"))
            return {
                "provider": provider,
                "mode": "affiliate_link",
                "links": [{"label": "Abrir Instacart", "url": affiliate_url}],
                "provider_disclosure": provider.get("disclosure", ""),
            }
        endpoint = _safe_https(
            os.getenv("ROXY_HOME_INSTACART_API_URL")
            or "https://connect.instacart.com/idp/v1/products/products_link"
        )
        payload = {
            "title": preparation.get("source_title") or "Compra preparada por Roxy",
            "line_items": [
                {
                    "name": row["query"],
                    "line_item_measurements": [{"quantity": row["quantity"], "unit": row["unit"]}],
                }
                for row in items
            ],
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=12) as response:  # nosec B310: HTTPS validated above
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise ConnectionError("Instacart no pudo preparar la compra en este momento.") from exc
        url = _safe_https(result.get("products_link_url"))
        return {"provider": provider, "mode": "full_list", "links": [{"label": "Revisar compra en Instacart", "url": url}], "provider_disclosure": provider.get("disclosure", "")}

    if provider_id == "amazon":
        tag = _text(os.getenv("ROXY_HOME_AMAZON_ASSOCIATE_TAG"), 80)
        if not re.fullmatch(r"[A-Za-z0-9_-]{2,80}", tag):
            raise RuntimeError("El identificador de Amazon Associates no es válido.")
        links = []
        for row in items:
            query = _amazon_search_query(row)
            links.append(
                {
                    "label": row["name"],
                    "quantity": row.get("quantity") or 1,
                    "unit": row.get("unit") or "unidad",
                    "category": row.get("category") or "GENERAL",
                    "query": query,
                    "reason": row.get("reason") or "Búsqueda adaptada a tu perfil de compra.",
                    "allergen_review_required": bool(row.get("allergen_review_required")),
                    "avoided_brands": list(row.get("avoided_brands") or []),
                    "url": _safe_https(
                        "https://www.amazon.com/s?" + urllib.parse.urlencode({"k": query, "tag": tag})
                    ),
                }
            )
        return {
            "provider": provider,
            "mode": "product_links",
            "links": links,
            "provider_disclosure": provider.get("disclosure", ""),
            "guidance": (
                "Roxy convirtió cada artículo en una búsqueda específica para Amazon.com. "
                "Amazon confirmará marca, tamaño, disponibilidad y precio final."
            ),
        }

    if provider_id == "kroger":
        links = [
            {
                "label": row["name"],
                "url": _safe_https(
                    "https://www.kroger.com/search?" + urllib.parse.urlencode({"query": row["query"]})
                ),
            }
            for row in items
        ]
        return {"provider": provider, "mode": "product_links", "links": links, "provider_disclosure": ""}

    furniture_searches = {
        "ikea": "https://www.ikea.com/us/en/search/?q={query}",
        "wayfair": "https://www.wayfair.com/keyword.php?keyword={query}",
        "west_elm": "https://www.westelm.com/search/results.html?words={query}",
        "article": "https://www.article.com/search?q={query}",
    }
    if provider_id in furniture_searches:
        affiliate_template = str(
            os.getenv(FURNITURE_AFFILIATE_TEMPLATE_ENVS[provider_id]) or ""
        )
        links = []
        for row in items:
            query = _text(row.get("query") or row.get("name"), 180)
            destination = _safe_https(
                furniture_searches[provider_id].replace("{query}", urllib.parse.quote_plus(query))
            )
            url = (
                _affiliate_template_link(
                    affiliate_template,
                    destination,
                    query,
                    str(preparation.get("tracking_id") or ""),
                )
                if provider.get("affiliate_connected")
                else destination
            )
            links.append({
                "label": row["name"],
                "quantity": row.get("quantity") or 1,
                "unit": row.get("unit") or "unidad",
                "category": row.get("category") or "HOUSEHOLD",
                "reason": row.get("reason") or "Compara materiales, medidas y precio en el comercio.",
                "url": url,
            })
        return {
            "provider": provider,
            "mode": "product_links",
            "links": links,
            "provider_disclosure": (
                f"{AFFILIATE_DISCLOSURE} Roxy no afirma disponibilidad ni precio: revisa la ficha oficial del comercio."
                if provider.get("affiliate_connected")
                else "Roxy no afirma disponibilidad ni precio: revisa la ficha oficial del comercio."
            ),
            "guidance": (
                f"Roxy preparó búsquedas específicas en el catálogo oficial de {provider['name']}"
                + (" con seguimiento afiliado activo." if provider.get("affiliate_connected") else ".")
            ),
        }

    configs = {
        "walmart": ("ROXY_HOME_WALMART_AFFILIATE_LINK_TEMPLATE", "https://www.walmart.com/search?q={query}"),
        "target": ("ROXY_HOME_TARGET_AFFILIATE_LINK_TEMPLATE", "https://www.target.com/s?searchTerm={query}"),
        "thrive": ("ROXY_HOME_THRIVE_AFFILIATE_LINK_TEMPLATE", "https://thrivemarket.com/search/results?filter%5Bsearch%5D={query}"),
    }
    env_name, destination_template = configs[provider_id]
    template = str(os.getenv(env_name) or "")
    links = []
    for row in items:
        destination = destination_template.replace("{query}", urllib.parse.quote_plus(row["query"]))
        links.append(
            {
                "label": row["name"],
                "url": _affiliate_template_link(
                    template,
                    destination,
                    row["query"],
                    str(preparation.get("tracking_id") or ""),
                ),
            }
        )
    return {"provider": provider, "mode": "product_links", "links": links, "provider_disclosure": provider.get("disclosure", "")}
