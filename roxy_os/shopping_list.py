from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


SHOPPING_STORE_VERSION = 5
SHOPPING_STATUSES = {"PENDING", "PURCHASED", "ARCHIVED"}
SHOPPING_CATEGORIES = {
    "GENERAL", "PRODUCE", "DAIRY_EGGS", "MEAT_SEAFOOD", "BAKERY", "PANTRY",
    "BEVERAGES", "FROZEN", "FOOD", "CLEANING", "PERSONAL", "HEALTH",
    "HOUSEHOLD", "BABY", "PETS", "OTHER",
}

# Classification stays deterministic and local so adding an item also works
# offline and never depends on an AI call. Specific categories come first:
# "jabón de platos" is cleaning, while an unqualified "jabón" is personal.
_SHOPPING_CATEGORY_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("FROZEN", (
        "helado", "pizza congelada", "vegetales congelados", "fruta congelada", "comida congelada",
        "papas congeladas", "nuggets congelados", "ice cream", "frozen pizza", "frozen food",
    )),
    ("CLEANING", (
        "detergente", "suavizante", "lavaplatos", "lavavajillas", "jabon de platos",
        "jabon para platos", "limpiador", "desinfectante", "cloro", "lejia", "bleach",
        "oxiclean", "oxi clean", "esponja", "estropajo", "trapeador", "mopa", "escoba",
        "recogedor", "guantes de limpieza", "bolsa de basura", "bolsas de basura",
        "papel toalla", "papel de cocina", "toalla de papel", "ambientador", "aromatizante",
        "bolsitas de olor", "sachet", "insecticida", "limpia vidrios", "limpiavidrios",
        "laundry", "dish soap", "dishwasher", "cleaner", "disinfectant", "trash bag",
    )),
    ("PERSONAL", (
        "papel higienico", "jabon", "champu", "shampoo", "acondicionador", "desodorante",
        "pasta dental", "crema dental", "cepillo dental", "hilo dental", "enjuague bucal",
        "gel de bano", "gel de ducha", "toalla sanitaria", "tampon", "tampones",
        "afeitadora", "rasuradora", "crema de afeitar", "locion", "protector solar",
        "crema corporal", "gel de cejas", "maquillaje", "algodon", "hisopo", "toallitas humedas",
        "body wash", "toothpaste", "toothbrush", "deodorant", "toilet paper", "skincare",
    )),
    ("HEALTH", (
        "medicamento", "medicina", "pastilla", "analgesico", "ibuprofeno", "acetaminofen",
        "paracetamol", "aspirina", "vitamina", "suplemento", "jarabe", "curita", "vendaje",
        "termometro", "alcohol isopropilico", "agua oxigenada", "farmacia", "antialergico",
        "antibiotico", "pain relief", "medicine", "vitamin", "supplement", "bandage",
    )),
    ("PETS", (
        "comida de perro", "comida para perro", "comida de gato", "comida para gato",
        "alimento de perro", "alimento para perro", "alimento de gato", "alimento para gato",
        "arena de gato", "arena para gato", "premio de perro", "premio para perro",
        "premio de gato", "premio para gato", "croquetas de perro", "croquetas de gato",
        "correa de perro", "mascota", "dog food", "cat food", "pet food", "cat litter",
    )),
    ("BABY", (
        "panal", "panales", "toallitas de bebe", "toallitas para bebe", "champu de bebe",
        "jabon de bebe", "baby wipes", "diaper", "diapers",
    )),
    ("HOUSEHOLD", (
        "papel aluminio", "papel encerado", "papel pergamino", "film plastico", "envoltura plastica",
        "servilleta", "vaso desechable", "plato desechable", "cubierto desechable", "bombillo",
        "bombilla", "bateria", "pilas", "vela", "fosforo", "encendedor", "filtro de cafe",
        "bolsa ziploc", "bolsas ziploc", "recipiente", "percha", "gancho de ropa", "storage bag",
        "organizador", "cargador", "cable usb", "extension electrica", "adaptador", "regleta",
        "martillo", "destornillador", "tornillo", "clavo", "taladro", "cinta metrica", "utensilio",
        "espatula", "abrelatas", "aluminum foil", "light bulb", "battery", "napkin", "paper plate",
        "charger", "usb cable", "extension cord", "tool",
    )),
    ("DAIRY_EGGS", (
        "leche", "huevo", "queso", "yogur", "yogurt", "mantequilla", "crema de leche",
        "half and half", "nata", "formula de bebe", "formula infantil", "baby formula",
        "milk", "egg", "cheese", "butter", "yogurt",
    )),
    ("MEAT_SEAFOOD", (
        "pollo", "carne", "res", "cerdo", "pescado", "salmon", "atun", "camaron", "marisco",
        "bistec", "jamon", "tocino", "pavo", "chicken", "beef", "pork", "fish", "steak",
        "shrimp", "turkey", "ham", "bacon",
    )),
    ("PRODUCE", (
        "tomate", "aguacate", "platano", "banana", "mandarina", "naranja", "manzana", "fruta",
        "vegetal", "verdura", "cebolla", "ajo", "papa", "patata", "zanahoria", "lechuga",
        "pepino", "pimiento", "brocoli", "coliflor", "espinaca", "cilantro", "perejil", "limon",
        "lima", "fresa", "uva", "mango", "pina", "vegetable", "fruit", "apple", "orange",
    )),
    ("BAKERY", (
        "pan", "bagel", "croissant", "tortilla", "arepa", "panecillo", "bollo", "pastelito",
        "bread", "bun", "roll", "bakery",
    )),
    ("BEVERAGES", (
        "cafe", "te", "matcha", "agua", "jugo", "zumo", "refresco", "soda", "bebida",
        "leche de almendra", "leche de avena", "agua de coco", "bebida energetica", "coffee",
        "water", "juice", "drink", "beverage",
    )),
    ("PANTRY", (
        "arroz", "pasta", "espagueti", "macarron", "fideo", "harina", "avena", "cereal",
        "aceite", "sal", "azucar", "levadura", "vainilla", "canela", "especia", "salsa",
        "frijol", "garbanzo", "lenteja", "maiz", "maicena", "dulce de leche", "conserva", "lata", "comida de bebe",
        "galleta", "chocolate", "miel", "mermelada", "mayonesa", "ketchup", "mostaza",
        "rice", "flour", "sugar", "salt", "oil", "pasta", "oat", "cereal", "spice", "sauce",
    )),
    ("FOOD", (
        "alimento", "comida", "snack", "aperitivo", "ingrediente", "food", "grocery",
    )),
)

_SHOPPING_NUMBER_WORDS = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
    "diez": 10, "once": 11, "doce": 12,
}
_SHOPPING_UNIT_ALIASES = {
    "botella": "botella", "botellas": "botella", "bolsa": "bolsa", "bolsas": "bolsa",
    "caja": "caja", "cajas": "caja", "docena": "docena", "docenas": "docena",
    "galon": "galón", "galones": "galón", "galón": "galón",
    "gramo": "gramo", "gramos": "gramo", "g": "gramo",
    "kilogramo": "kilogramo", "kilogramos": "kilogramo", "kg": "kilogramo",
    "lata": "lata", "latas": "lata", "libra": "libra", "libras": "libra", "lb": "libra",
    "litro": "litro", "litros": "litro", "l": "litro",
    "mililitro": "mililitro", "mililitros": "mililitro", "ml": "mililitro",
    "onza": "onza", "onzas": "onza", "oz": "onza",
    "paquete": "paquete", "paquetes": "paquete", "pomo": "pomo", "pomos": "pomo",
    "unidad": "unidad", "unidades": "unidad",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_shopping_user(value: Any) -> str:
    user = re.sub(r"[^a-zA-Z0-9_.@-]+", "_", str(value or "local_user").strip().lower()).strip("_")
    return user[:96] or "local_user"


def normalize_shopping_name(value: Any) -> str:
    name = " ".join(str(value or "").strip().split())
    # Voice agents may pass the destination together with the tool argument
    # (for example, "a la lista de compras detergente"). Keep only the
    # product so the shared list, product memory and image resolver all use
    # the same stable identity.
    wrappers = (
        r"(?i)^(?:por favor\s+)?(?:agrega(?:r)?|añade|anade|pon|apunta|anota|incluye|mete|echa|échame|echame|suma|súmale|sumale|trae)\s+",
        r"(?i)^(?:a|en)\s+(?:mi|la)\s+lista(?:\s+de\s+compras?)?\s+",
        r"(?i)^(?:mi|la)\s+lista(?:\s+de\s+compras?)?\s+",
        r"(?i)^lista\s+de\s+compras?\s+",
        r"(?i)\s+(?:a|en)\s+(?:mi|la)\s+lista(?:\s+de\s+compras?)?$",
        r"(?i)\s+(?:a|en)\s+lista(?:\s+de\s+compras?)?$",
        r"(?i)\s+para\s+(?:mi|la)\s+lista(?:\s+de\s+compras?)?$",
        r"(?i)\s+por\s+favor$",
    )
    previous = None
    while name and name != previous:
        previous = name
        for pattern in wrappers:
            name = re.sub(pattern, "", name).strip(" .,:;-")
    if not name:
        raise ValueError("El articulo necesita un nombre.")
    return name[:120]


def normalize_shopping_item(
    name: Any,
    *,
    quantity: Any = 1,
    unit: Any = "unidad",
) -> tuple[str, float, str]:
    """Structure conservative voice measurements without changing recipe data."""

    display_name = normalize_shopping_name(name)
    amount = normalize_quantity(quantity)
    raw_unit = " ".join(str(unit or "unidad").strip().split())[:32] or "unidad"
    normalized_unit = _SHOPPING_UNIT_ALIASES.get(raw_unit.casefold(), raw_unit)
    if amount != 1 or normalized_unit.casefold() != "unidad":
        return display_name, amount, normalized_unit

    number_pattern = r"\d+(?:[.,]\d+)?|" + "|".join(_SHOPPING_NUMBER_WORDS)
    unit_pattern = "|".join(sorted((re.escape(value) for value in _SHOPPING_UNIT_ALIASES), key=len, reverse=True))
    match = re.match(
        rf"(?i)^\s*(?P<number>{number_pattern})\s+(?P<unit>{unit_pattern})\s+(?:de\s+)?(?P<product>.+?)\s*$",
        display_name,
    )
    if not match:
        return display_name, amount, normalized_unit
    raw_number = match.group("number").casefold().replace(",", ".")
    parsed_amount = _SHOPPING_NUMBER_WORDS.get(raw_number)
    if parsed_amount is None:
        try:
            parsed_amount = float(raw_number)
        except ValueError:
            return display_name, amount, normalized_unit
    return (
        normalize_shopping_name(match.group("product")),
        normalize_quantity(parsed_amount),
        _SHOPPING_UNIT_ALIASES.get(match.group("unit").casefold(), match.group("unit").casefold()),
    )


def _identity(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", normalize_shopping_name(value))
    return " ".join(normalized.encode("ascii", "ignore").decode("ascii").lower().split())


def _classification_identity(value: Any) -> str:
    words = _identity(value).split()
    return " ".join(word[:-1] if len(word) > 4 and word.endswith("s") else word for word in words)


def classify_shopping_category(name: Any, requested: Any = "GENERAL") -> str:
    """Infer a stable aisle while preserving explicit categories for unknown products."""

    identity = _classification_identity(name)
    padded = f" {identity} "
    matches: list[tuple[int, str]] = []
    for category, terms in _SHOPPING_CATEGORY_TERMS:
        for term in terms:
            normalized_term = _classification_identity(term)
            if f" {normalized_term} " in padded:
                matches.append((len(normalized_term), category))
    if matches:
        return max(matches, key=lambda row: row[0])[1]
    explicit = str(requested or "GENERAL").strip().upper()
    if explicit in SHOPPING_CATEGORIES and explicit != "GENERAL":
        return explicit
    return "OTHER"


def normalize_quantity(value: Any) -> float:
    try:
        quantity = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("La cantidad debe ser numerica.") from exc
    if not 0 < quantity <= 100_000:
        raise ValueError("La cantidad debe ser mayor que cero y razonable.")
    return round(quantity, 4)


class ShoppingListStore:
    """Atomic local household list shared by UI, voice and text."""

    def __init__(self, path: str | Path = "data/roxy_shopping_list.json") -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    def _empty(self) -> dict[str, Any]:
        return {
            "schema_version": SHOPPING_STORE_VERSION,
            "updated_at": _now_iso(),
            "items": [],
            "trips": [],
            "product_memory": {},
            "user_revisions": {},
        }

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return self._empty()
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            return self._empty()
        payload["schema_version"] = SHOPPING_STORE_VERSION
        payload["items"] = [item for item in payload["items"] if isinstance(item, dict)]
        for item in payload["items"]:
            try:
                cleaned_name = normalize_shopping_name(item.get("name"))
            except ValueError:
                continue
            item["name"] = cleaned_name
            item["identity"] = _identity(cleaned_name)
            item["category"] = classify_shopping_category(cleaned_name, item.get("category"))
        if not isinstance(payload.get("trips"), list):
            payload["trips"] = []
        payload["trips"] = [trip for trip in payload["trips"] if isinstance(trip, dict)]
        if not isinstance(payload.get("product_memory"), dict):
            payload["product_memory"] = {}
        if not isinstance(payload.get("user_revisions"), dict):
            payload["user_revisions"] = {}
        return payload

    def user_ids(self) -> list[str]:
        """Return normalized owners without exposing shopping item contents."""
        payload = self._read_unlocked()
        users = {
            normalize_shopping_user(item.get("user_id"))
            for item in payload.get("items", [])
            if isinstance(item, dict) and item.get("user_id")
        }
        users.update(
            normalize_shopping_user(user)
            for user in (payload.get("user_revisions") or {})
            if str(user or "").strip()
        )
        return sorted(users)

    @staticmethod
    def _revision(payload: dict[str, Any], user: str) -> int:
        revisions = payload.setdefault("user_revisions", {})
        try:
            return max(0, int(revisions.get(user) or 0))
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _bump_revision(cls, payload: dict[str, Any], user: str) -> int:
        revision = cls._revision(payload, user) + 1
        payload.setdefault("user_revisions", {})[user] = revision
        return revision

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload["schema_version"] = SHOPPING_STORE_VERSION
        payload["updated_at"] = _now_iso()
        handle, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
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

    def add(
        self,
        user_id: Any,
        name: Any,
        *,
        quantity: Any = 1,
        unit: Any = "unidad",
        category: Any = "GENERAL",
        notes: Any = "",
        source: Any = "ui",
    ) -> dict[str, Any]:
        user = normalize_shopping_user(user_id)
        display_name, amount, normalized_unit = normalize_shopping_item(
            name,
            quantity=quantity,
            unit=unit,
        )
        item_identity = _identity(display_name)
        requested_category = str(category or "GENERAL").strip().upper()
        if requested_category not in SHOPPING_CATEGORIES:
            raise ValueError("Categoria de compra no valida.")
        normalized_category = classify_shopping_category(display_name, requested_category)

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            now = _now_iso()
            user_memory = payload.setdefault("product_memory", {}).setdefault(user, {})
            remembered = user_memory.setdefault(item_identity, {})
            remembered.update(
                {
                    "identity": item_identity,
                    "name": display_name,
                    "unit": normalized_unit,
                    "category": normalized_category,
                    "last_added_at": now,
                }
            )
            remembered["times_added"] = max(0, int(remembered.get("times_added") or 0)) + 1
            for item in payload["items"]:
                if (
                    normalize_shopping_user(item.get("user_id")) == user
                    and str(item.get("identity") or _identity(item.get("name"))) == item_identity
                    and str(item.get("unit") or "unidad").casefold() == normalized_unit.casefold()
                    and str(item.get("status") or "PENDING") == "PENDING"
                ):
                    item["quantity"] = round(float(item.get("quantity") or 0) + amount, 4)
                    item["updated_at"] = now
                    item["source"] = str(source or "ui")[:64]
                    item["category"] = normalized_category
                    if str(notes or "").strip():
                        item["notes"] = str(notes).strip()[:1000]
                    self._bump_revision(payload, user)
                    return deepcopy(item)
            item = {
                "id": uuid4().hex,
                "user_id": user,
                "name": display_name,
                "identity": item_identity,
                "quantity": amount,
                "unit": normalized_unit,
                "category": normalized_category,
                "notes": str(notes or "").strip()[:1000],
                "status": "PENDING",
                "source": str(source or "ui").strip()[:64] or "ui",
                "created_at": now,
                "updated_at": now,
                "purchased_at": None,
            }
            payload["items"].append(item)
            self._bump_revision(payload, user)
            return deepcopy(item)

        return self._mutate(apply)

    def list_items(
        self,
        user_id: Any,
        *,
        statuses: set[str] | None = None,
        include_archived: bool = False,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        user = normalize_shopping_user(user_id)
        allowed = {str(value).upper() for value in statuses} if statuses else None
        if allowed is not None and not allowed <= SHOPPING_STATUSES:
            raise ValueError("Filtro de compras no valido.")
        rows = []
        for raw in self._read_unlocked().get("items", []):
            if normalize_shopping_user(raw.get("user_id")) != user:
                continue
            status = str(raw.get("status") or "PENDING").upper()
            if allowed is not None and status not in allowed:
                continue
            if not include_archived and status == "ARCHIVED":
                continue
            rows.append(deepcopy(raw))
        rows.sort(
            key=lambda item: (
                str(item.get("status")) != "PENDING",
                str(item.get("category") or "GENERAL"),
                str(item.get("name") or "").casefold(),
            )
        )
        return rows[: max(1, min(int(limit), 1000))]

    def transition(self, user_id: Any, item_id: Any, status: Any) -> dict[str, Any]:
        user = normalize_shopping_user(user_id)
        target_id = str(item_id or "").strip()
        target = str(status or "").strip().upper()
        if target not in SHOPPING_STATUSES:
            raise ValueError("Estado de compra no valido.")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            for item in payload["items"]:
                if item.get("id") != target_id or normalize_shopping_user(item.get("user_id")) != user:
                    continue
                current = str(item.get("status") or "PENDING").upper()
                allowed = {
                    "PENDING": {"PURCHASED", "ARCHIVED"},
                    "PURCHASED": {"PENDING", "ARCHIVED"},
                    "ARCHIVED": {"PENDING"},
                }
                if target != current and target not in allowed.get(current, set()):
                    raise ValueError(f"Transicion de {current} a {target} no permitida.")
                now = _now_iso()
                item["status"] = target
                item["updated_at"] = now
                item["purchased_at"] = now if target == "PURCHASED" else None
                if target != current:
                    self._bump_revision(payload, user)
                return deepcopy(item)
            raise KeyError("Articulo no encontrado para este usuario.")

        return self._mutate(apply)

    def set_quantity(self, user_id: Any, item_id: Any, quantity: Any) -> dict[str, Any]:
        """Set one item's quantity without allowing cross-user mutation."""

        user = normalize_shopping_user(user_id)
        target_id = str(item_id or "").strip()
        amount = normalize_quantity(quantity)

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            for item in payload["items"]:
                if item.get("id") != target_id or normalize_shopping_user(item.get("user_id")) != user:
                    continue
                previous = float(item.get("quantity") or 0)
                item["quantity"] = amount
                item["updated_at"] = _now_iso()
                if previous != amount:
                    self._bump_revision(payload, user)
                return deepcopy(item)
            raise KeyError("Articulo no encontrado para este usuario.")

        return self._mutate(apply)

    def delete(self, user_id: Any, item_id: Any) -> dict[str, Any]:
        """Delete one active row. Completed trip history remains immutable."""

        user = normalize_shopping_user(user_id)
        target_id = str(item_id or "").strip()

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            for index, item in enumerate(payload["items"]):
                if item.get("id") != target_id or normalize_shopping_user(item.get("user_id")) != user:
                    continue
                removed = payload["items"].pop(index)
                self._bump_revision(payload, user)
                return deepcopy(removed)
            raise KeyError("Articulo no encontrado para este usuario.")

        return self._mutate(apply)

    def delete_named(self, user_id: Any, name: Any) -> dict[str, Any]:
        user = normalize_shopping_user(user_id)
        target_identity = _identity(name)
        for item in self.list_items(user, statuses={"PENDING"}, limit=1000):
            if str(item.get("identity") or _identity(item.get("name"))) == target_identity:
                return self.delete(user, item.get("id"))
        raise KeyError("Articulo no encontrado para este usuario.")

    def complete_purchase(self, user_id: Any) -> dict[str, Any]:
        """Archive every pending item and append one recoverable purchase trip."""

        user = normalize_shopping_user(user_id)

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            pending = [
                item
                for item in payload["items"]
                if normalize_shopping_user(item.get("user_id")) == user
                and str(item.get("status") or "PENDING").upper() in {"PENDING", "PURCHASED"}
            ]
            if not pending:
                return {"completed": False, "trip": None, "count": 0, "total_quantity": 0.0}
            now = _now_iso()
            trip_id = uuid4().hex
            trip_items: list[dict[str, Any]] = []
            for item in pending:
                item["status"] = "ARCHIVED"
                item["purchased_at"] = now
                item["updated_at"] = now
                item["trip_id"] = trip_id
                trip_items.append(
                    {
                        key: deepcopy(item.get(key))
                        for key in ("id", "name", "quantity", "unit", "category", "notes")
                    }
                )
            trip = {
                "id": trip_id,
                "user_id": user,
                "completed_at": now,
                "item_count": len(trip_items),
                "total_quantity": round(sum(float(item.get("quantity") or 0) for item in trip_items), 4),
                "items": trip_items,
            }
            payload.setdefault("trips", []).append(trip)
            self._bump_revision(payload, user)
            return {
                "completed": True,
                "trip": deepcopy(trip),
                "count": trip["item_count"],
                "total_quantity": trip["total_quantity"],
            }

        return self._mutate(apply)

    def history(self, user_id: Any, *, limit: int = 12) -> list[dict[str, Any]]:
        user = normalize_shopping_user(user_id)
        trips = [
            deepcopy(trip)
            for trip in self._read_unlocked().get("trips", [])
            if normalize_shopping_user(trip.get("user_id")) == user
        ]
        trips.sort(key=lambda trip: str(trip.get("completed_at") or ""), reverse=True)
        return trips[: max(1, min(int(limit), 100))]

    def habitual_products(self, user_id: Any, *, limit: int = 20) -> list[dict[str, Any]]:
        """Learn private product suggestions from this user's real list and trip history."""
        user = normalize_shopping_user(user_id)
        payload = self._read_unlocked()
        learned: dict[str, dict[str, Any]] = {}
        user_memory = payload.get("product_memory", {}).get(user, {})
        if isinstance(user_memory, dict):
            for identity, raw in user_memory.items():
                row = raw if isinstance(raw, dict) else {}
                try:
                    name = normalize_shopping_name(row.get("name") or identity)
                except ValueError:
                    continue
                category = classify_shopping_category(name, row.get("category"))
                learned[str(identity)] = {
                    "identity": str(identity),
                    "name": name,
                    "unit": " ".join(str(row.get("unit") or "unidad").strip().split())[:32] or "unidad",
                    "category": category,
                    "times_used": max(0, int(row.get("times_added") or 0)),
                    "purchase_count": 0,
                    "last_used_at": str(row.get("last_added_at") or "")[:64],
                }
        identities_with_memory = set(learned)

        def remember(raw: Any, *, used_at: Any, purchased: bool, count_use: bool = True) -> None:
            row = raw if isinstance(raw, dict) else {}
            try:
                name = normalize_shopping_name(row.get("name"))
                identity = str(row.get("identity") or _identity(name))
            except ValueError:
                return
            if not identity:
                return
            entry = learned.setdefault(
                identity,
                {
                    "identity": identity,
                    "name": name,
                    "unit": "unidad",
                    "category": "GENERAL",
                    "times_used": 0,
                    "purchase_count": 0,
                    "last_used_at": "",
                },
            )
            timestamp = str(used_at or "")[:64]
            if count_use:
                entry["times_used"] += 1
            if purchased:
                entry["purchase_count"] += 1
            if timestamp >= str(entry.get("last_used_at") or ""):
                entry["name"] = name
                entry["unit"] = " ".join(str(row.get("unit") or "unidad").strip().split())[:32] or "unidad"
                entry["category"] = classify_shopping_category(name, row.get("category"))
                entry["last_used_at"] = timestamp

        for trip in payload.get("trips", []):
            if normalize_shopping_user(trip.get("user_id")) != user:
                continue
            completed_at = trip.get("completed_at")
            for raw in trip.get("items", []) if isinstance(trip.get("items"), list) else []:
                try:
                    identity = str(raw.get("identity") or _identity(raw.get("name")))
                except (AttributeError, ValueError):
                    identity = ""
                remember(raw, used_at=completed_at, purchased=True, count_use=identity not in identities_with_memory)

        rows = [
            row
            for row in learned.values()
            if int(row.get("times_used") or 0) >= 2 or int(row.get("purchase_count") or 0) >= 1
        ]
        rows.sort(key=lambda row: str(row.get("name") or "").casefold())
        rows.sort(key=lambda row: str(row.get("last_used_at") or ""), reverse=True)
        rows.sort(key=lambda row: int(row.get("times_used") or 0), reverse=True)
        rows.sort(key=lambda row: int(row.get("purchase_count") or 0), reverse=True)
        return rows[: max(1, min(int(limit), 100))]

    @staticmethod
    def _normalize_sync_item(raw: Any, user: str) -> dict[str, Any] | None:
        row = raw if isinstance(raw, dict) else {}
        try:
            name = normalize_shopping_name(row.get("name"))
            quantity = normalize_quantity(row.get("quantity") or 1)
        except ValueError:
            return None
        status = str(row.get("status") or "PENDING").upper()
        category = classify_shopping_category(name, row.get("category"))
        if status not in SHOPPING_STATUSES or category not in SHOPPING_CATEGORIES:
            return None
        item_id = str(row.get("id") or "").lower()
        if not re.fullmatch(r"[a-f0-9]{32}", item_id):
            item_id = uuid4().hex
        unit = " ".join(str(row.get("unit") or "unidad").strip().split())[:32] or "unidad"
        return {
            "id": item_id,
            "user_id": user,
            "name": name,
            "identity": _identity(name),
            "quantity": quantity,
            "unit": unit,
            "category": category,
            "notes": str(row.get("notes") or "")[:1000],
            "status": status,
            "source": str(row.get("source") or "device_sync")[:64],
            "created_at": str(row.get("created_at") or _now_iso())[:64],
            "updated_at": str(row.get("updated_at") or _now_iso())[:64],
            "purchased_at": str(row.get("purchased_at") or "")[:64] or None,
        }

    def replace_user_snapshot(self, user_id: Any, snapshot: Any, *, expected_revision: int) -> dict[str, Any]:
        user = normalize_shopping_user(user_id)
        incoming = snapshot if isinstance(snapshot, dict) else {}
        raw_items = incoming.get("items") if isinstance(incoming.get("items"), list) else []
        normalized = [item for raw in raw_items[:1000] if (item := self._normalize_sync_item(raw, user)) is not None]

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            current_revision = self._revision(payload, user)
            expected = max(0, int(expected_revision))
            if current_revision != expected:
                return {
                    "updated": False,
                    "conflict": True,
                    "expected_revision": expected,
                    "current_revision": current_revision,
                }
            current = [row for row in payload["items"] if normalize_shopping_user(row.get("user_id")) == user]
            changed = current != normalized
            if changed:
                payload["items"] = [
                    row for row in payload["items"] if normalize_shopping_user(row.get("user_id")) != user
                ] + normalized
                current_revision = self._bump_revision(payload, user)
            return {
                "updated": True,
                "conflict": False,
                "revision": current_revision,
                "items": deepcopy(normalized),
            }

        return self._mutate(apply)

    def snapshot(self, user_id: Any, *, limit: int = 100) -> dict[str, Any]:
        payload = self._read_unlocked()
        items = self.list_items(user_id, include_archived=False, limit=limit)
        return {
            "source": "local_durable",
            "sync_state": "LOCAL_ONLY",
            "updated_at": payload.get("updated_at"),
            "revision": self._revision(payload, normalize_shopping_user(user_id)),
            "pending_count": sum(item.get("status") == "PENDING" for item in items),
            "purchased_count": sum(item.get("status") == "PURCHASED" for item in items),
            "history": self.history(user_id, limit=12),
            "habitual_products": self.habitual_products(user_id, limit=20),
            "items": items,
        }
