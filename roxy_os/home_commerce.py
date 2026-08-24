from __future__ import annotations

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


COMMERCE_STORE_VERSION = 2
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
    "galon": "gallon",
    "litro": "liter",
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
        profile = {
            "objective": objective,
            "organic_preference": organic,
            "favorite_retailers": _string_list(values.get("favorite_retailers")),
            "favorite_brands": _string_list(values.get("favorite_brands")),
            "avoided_brands": _string_list(values.get("avoided_brands")),
            "dietary_labels": _string_list(values.get("dietary_labels")),
            "allow_substitutions": values.get("allow_substitutions") is True,
            "postal_code": postal_code,
            "updated_at": _now_iso(),
        }

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            payload["profiles"][owner_key] = profile
            return deepcopy(profile)

        return self._mutate(apply)

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
    ]
    status_env = {
        "instacart": "ROXY_HOME_INSTACART_AFFILIATE_STATUS",
        "kroger": "ROXY_HOME_KROGER_STATUS",
        "amazon": "ROXY_HOME_AMAZON_AFFILIATE_STATUS",
        "walmart": "ROXY_HOME_WALMART_AFFILIATE_STATUS",
        "target": "ROXY_HOME_TARGET_AFFILIATE_STATUS",
        "thrive": "ROXY_HOME_THRIVE_AFFILIATE_STATUS",
    }
    for provider in definitions:
        state, label, next_step = connection(
            status_env[provider["id"]], bool(provider.get("configured"))
        )
        provider["connection_status"] = state
        provider["status_label"] = label
        provider["next_step"] = next_step
    return definitions


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
