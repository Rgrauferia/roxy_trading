from __future__ import annotations

import json
import hashlib
import os
import re
import sqlite3
import threading
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import requests


OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v3/product/{barcode}.json"
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
CPSC_RECALL_URL = "https://www.saferproducts.gov/RestWebServices/Recall"
PRODUCT_SOURCE_NOTICE = (
    "Los datos se muestran con su fuente y fecha. Las etiquetas del empaque y los avisos "
    "oficiales prevalecen; que no aparezca una alerta no garantiza que un producto sea seguro."
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _identity(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _text(value, 240)).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", text).casefold().split())


def normalize_barcode(value: Any) -> str:
    barcode = re.sub(r"\D", "", str(value or ""))
    if not 8 <= len(barcode) <= 14:
        raise ValueError("El código debe tener entre 8 y 14 dígitos.")
    return barcode


def normalize_product_query(value: Any) -> str:
    query = _text(value, 160)
    if len(query) < 2:
        raise ValueError("Escribe el nombre del producto que quieres identificar.")
    return query


class ProductLookupError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProductIntelligenceConfig:
    cache_path: Path
    user_agent: str
    usda_api_key: str = ""
    timeout_seconds: float = 8.0
    cache_hours: int = 24 * 7

    @classmethod
    def from_env(cls) -> "ProductIntelligenceConfig":
        return cls(
            cache_path=Path(os.getenv("ROXY_HOME_PRODUCT_CACHE_PATH", "data/roxy_home_products.sqlite")),
            user_agent=_text(
                os.getenv("ROXY_HOME_PRODUCT_USER_AGENT")
                or "RoxyHome/1.0 (product-support; contact: roxy@grau360.com)",
                240,
            ),
            usda_api_key=_text(os.getenv("ROXY_HOME_USDA_API_KEY"), 256),
            timeout_seconds=max(2.0, min(float(os.getenv("ROXY_HOME_PRODUCT_TIMEOUT_SECONDS", "8")), 20.0)),
            cache_hours=max(1, min(int(os.getenv("ROXY_HOME_PRODUCT_CACHE_HOURS", str(24 * 7))), 24 * 30)),
        )


class ProductIntelligenceStore:
    """Shared cache for public product facts; it never stores household data."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS product_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json, fetched_at, expires_at FROM product_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        try:
            expires = datetime.fromisoformat(str(row["expires_at"]))
            if expires <= _now():
                return None
            payload = json.loads(str(row["payload_json"]))
        except (ValueError, TypeError, json.JSONDecodeError):
            return None
        payload["cache"] = {"hit": True, "fetched_at": str(row["fetched_at"])}
        return payload

    def put(self, key: str, payload: dict[str, Any], *, hours: int) -> None:
        fetched = _now()
        expires = fetched + timedelta(hours=hours)
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO product_cache(cache_key, payload_json, fetched_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    fetched_at = excluded.fetched_at,
                    expires_at = excluded.expires_at
                """,
                (key, json.dumps(payload, ensure_ascii=False), fetched.isoformat(), expires.isoformat()),
            )


class HomeProductIntelligence:
    def __init__(
        self,
        config: ProductIntelligenceConfig | None = None,
        *,
        store: ProductIntelligenceStore | None = None,
        request: Callable[..., requests.Response] | None = None,
    ):
        self.config = config or ProductIntelligenceConfig.from_env()
        self.store = store or ProductIntelligenceStore(self.config.cache_path)
        self.request = request or requests.request

    def status(self) -> dict[str, Any]:
        return {
            "open_food_facts": {"enabled": True, "label": "Open Food Facts"},
            "usda": {"enabled": bool(self.config.usda_api_key), "label": "USDA FoodData Central"},
            "cpsc": {"enabled": True, "label": "CPSC Recalls"},
            "notice": PRODUCT_SOURCE_NOTICE,
        }

    def lookup(self, *, barcode: str = "", query: str = "") -> dict[str, Any]:
        normalized_barcode = normalize_barcode(barcode) if barcode else ""
        normalized_query = normalize_product_query(query) if query else ""
        if not normalized_barcode and not normalized_query:
            raise ValueError("Escanea un código o escribe un producto.")
        key_material = f"v1:{normalized_barcode}:{_identity(normalized_query)}"
        key = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
        cached = self.store.get(key)
        if cached:
            return cached

        source_errors: list[dict[str, str]] = []
        product: dict[str, Any] | None = None
        if normalized_barcode:
            try:
                product = self._open_food_facts(normalized_barcode)
            except ProductLookupError as exc:
                source_errors.append({"source": "open_food_facts", "message": str(exc)})
        search_query = normalized_query or _text((product or {}).get("name"), 160)
        nutrition: dict[str, Any] | None = None
        if search_query and self.config.usda_api_key:
            try:
                nutrition = self._usda(search_query, normalized_barcode)
            except ProductLookupError as exc:
                source_errors.append({"source": "usda", "message": str(exc)})
        recalls: list[dict[str, Any]] = []
        cpsc_checked = False
        if search_query:
            try:
                recalls = self._cpsc(search_query)
                cpsc_checked = True
            except ProductLookupError as exc:
                source_errors.append({"source": "cpsc", "message": str(exc)})

        result = {
            "status": "FOUND" if product or nutrition else "NO_MATCH",
            "capabilities": {
                "barcode_lookup": True,
                "name_lookup": bool(self.config.usda_api_key),
            },
            "query": search_query,
            "barcode": normalized_barcode,
            "product": product,
            "nutrition_reference": nutrition,
            "recalls": recalls,
            "recall_summary": {
                "status": "POTENTIAL_MATCHES" if recalls else "NO_MATCHES_FOUND",
                "message": (
                    f"Se encontraron {len(recalls)} avisos potencialmente relacionados; revisa los detalles."
                    if recalls
                    else "No encontramos coincidencias en esta consulta. Esto no garantiza ausencia de retiros."
                ),
            },
            "sources": [
                source
                for source in [
                    (product or {}).get("source"),
                    (nutrition or {}).get("source"),
                    (
                        {
                            "id": "cpsc",
                            "label": "U.S. Consumer Product Safety Commission",
                            "url": "https://www.cpsc.gov/Recalls",
                        }
                        if cpsc_checked
                        else None
                    ),
                ]
                if source
            ],
            "source_errors": source_errors,
            "notice": PRODUCT_SOURCE_NOTICE,
            "cache": {"hit": False, "fetched_at": _now().isoformat()},
        }
        self.store.put(key, result, hours=self.config.cache_hours)
        return result

    def _json_request(self, method: str, url: str, **kwargs: Any) -> Any:
        headers = {"User-Agent": self.config.user_agent, "Accept": "application/json"}
        headers.update(kwargs.pop("headers", {}) or {})
        try:
            response = self.request(method, url, headers=headers, timeout=self.config.timeout_seconds, **kwargs)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise ProductLookupError("La fuente no respondió correctamente; inténtalo nuevamente.") from exc

    def _open_food_facts(self, barcode: str) -> dict[str, Any] | None:
        fields = ",".join(
            [
                "code", "product_name", "product_name_es", "brands", "quantity", "image_front_url",
                "categories", "categories_tags", "allergens", "allergens_tags", "ingredients_text",
                "ingredients_text_es", "nutriscore_grade", "nova_group", "nutriments",
            ]
        )
        payload = self._json_request(
            "GET", OPEN_FOOD_FACTS_URL.format(barcode=quote(barcode)), params={"fields": fields}
        )
        # API v3 returns `product` plus an `errors` array. Keep accepting the
        # old `status=1` shape in tests/cache migrations while v2 ages out.
        if not isinstance(payload, dict) or not isinstance(payload.get("product"), dict):
            return None
        row = payload["product"]
        name = _text(row.get("product_name_es") or row.get("product_name"), 160)
        if not name:
            return None
        nutrients = row.get("nutriments") if isinstance(row.get("nutriments"), dict) else {}
        per_100g = {}
        for source_key, label, unit in (
            ("energy-kcal_100g", "Energía", "kcal"),
            ("fat_100g", "Grasas", "g"),
            ("saturated-fat_100g", "Grasas saturadas", "g"),
            ("carbohydrates_100g", "Carbohidratos", "g"),
            ("sugars_100g", "Azúcares", "g"),
            ("fiber_100g", "Fibra", "g"),
            ("proteins_100g", "Proteína", "g"),
            ("salt_100g", "Sal", "g"),
        ):
            if nutrients.get(source_key) is not None:
                per_100g[label] = {"value": nutrients[source_key], "unit": unit}
        return {
            "name": name,
            "brand": _text(row.get("brands"), 120),
            "quantity": _text(row.get("quantity"), 80),
            "image_url": _text(row.get("image_front_url"), 1000),
            "categories": [_text(value, 100) for value in (row.get("categories_tags") or [])[:10]],
            "allergens": [_text(value, 100) for value in (row.get("allergens_tags") or [])[:20]],
            "ingredients": _text(row.get("ingredients_text_es") or row.get("ingredients_text"), 2000),
            "nutriscore": _text(row.get("nutriscore_grade"), 4).upper(),
            "nova_group": row.get("nova_group"),
            "nutrition_per_100g": per_100g,
            "source": {
                "id": "open_food_facts",
                "label": "Open Food Facts",
                "url": f"https://world.openfoodfacts.org/product/{barcode}",
                "kind": "community_database",
            },
        }

    def _usda(self, query: str, barcode: str) -> dict[str, Any] | None:
        payload = self._json_request(
            "POST",
            USDA_SEARCH_URL,
            params={"api_key": self.config.usda_api_key},
            json={"query": barcode or query, "pageSize": 5, "dataType": ["Branded", "Foundation", "SR Legacy"]},
        )
        foods = payload.get("foods") if isinstance(payload, dict) else None
        if not isinstance(foods, list) or not foods:
            return None
        query_id = _identity(query)
        row = max(
            (food for food in foods if isinstance(food, dict)),
            key=lambda food: self._match_score(query_id, food, barcode),
            default=None,
        )
        if not row or self._match_score(query_id, row, barcode) < 0.25:
            return None
        nutrients = []
        for nutrient in (row.get("foodNutrients") or [])[:30]:
            if not isinstance(nutrient, dict) or nutrient.get("value") is None:
                continue
            nutrients.append(
                {
                    "name": _text(nutrient.get("nutrientName"), 100),
                    "value": nutrient.get("value"),
                    "unit": _text(nutrient.get("unitName"), 20),
                }
            )
        fdc_id = str(row.get("fdcId") or "")
        return {
            "name": _text(row.get("description"), 180),
            "brand": _text(row.get("brandOwner") or row.get("brandName"), 120),
            "ingredients": _text(row.get("ingredients"), 2000),
            "serving_size": row.get("servingSize"),
            "serving_unit": _text(row.get("servingSizeUnit"), 24),
            "nutrients": nutrients,
            "source": {
                "id": "usda",
                "label": "USDA FoodData Central",
                "url": f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients" if fdc_id else "https://fdc.nal.usda.gov/",
                "kind": "government_database",
            },
        }

    @staticmethod
    def _match_score(query_id: str, row: dict[str, Any], barcode: str = "") -> float:
        gtin = re.sub(r"\D", "", str(row.get("gtinUpc") or ""))
        if barcode and gtin and (gtin == barcode or gtin.lstrip("0") == barcode.lstrip("0")):
            return 1.0
        title = _identity(row.get("description"))
        query_terms = set(query_id.split())
        if not query_terms:
            return 0.0
        return len(query_terms & set(title.split())) / len(query_terms)

    def _cpsc(self, query: str) -> list[dict[str, Any]]:
        payload = self._json_request("GET", CPSC_RECALL_URL, params={"ProductName": query, "format": "json"})
        rows = payload if isinstance(payload, list) else []
        query_terms = {term for term in _identity(query).split() if len(term) > 2}
        matches: list[dict[str, Any]] = []
        for row in rows[:25]:
            if not isinstance(row, dict):
                continue
            title = _text(row.get("Title") or row.get("RecallTitle"), 240)
            description = _text(row.get("Description") or row.get("Hazards"), 800)
            identity = _identity(f"{title} {description}")
            overlap = query_terms & set(identity.split())
            if query_terms and not overlap:
                continue
            recall_id = _text(row.get("RecallID") or row.get("RecallNumber"), 40)
            url = _text(row.get("URL") or row.get("RecallURL"), 1000)
            matches.append(
                {
                    "title": title,
                    "date": _text(row.get("RecallDate") or row.get("Date"), 40),
                    "description": description,
                    "url": url or (f"https://www.cpsc.gov/Recalls/{recall_id}" if recall_id else "https://www.cpsc.gov/Recalls"),
                    "match_terms": sorted(overlap),
                    "match_type": "potential_text_match",
                }
            )
        return matches[:5]
