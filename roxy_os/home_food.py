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

from roxy_os.shopping_list import ShoppingListStore, normalize_shopping_user


HOME_FOOD_STORE_VERSION = 2


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int = 160) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _identity(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", _text(value))
    return " ".join(normalized.encode("ascii", "ignore").decode("ascii").lower().split())


def _positive_number(value: Any, *, maximum: float = 100_000) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("La cantidad debe ser numérica.") from exc
    if not 0 < number <= maximum:
        raise ValueError("La cantidad debe ser mayor que cero y razonable.")
    return round(number, 4)


def _string_list(values: Any, *, limit: int = 50) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values[:limit]:
        item = _text(value)
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            result.append(item)
    return result


class HomeFoodStore:
    """Private, per-user memory for Roxy Home food features.

    This store is intentionally independent from Study and Trading memory. Only
    an explicitly confirmed conversion writes into ``ShoppingListStore``.
    """

    def __init__(self, path: str | Path = "data/roxy_home_food.json") -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"schema_version": HOME_FOOD_STORE_VERSION, "updated_at": _now_iso(), "users": {}}

    @staticmethod
    def _new_user() -> dict[str, Any]:
        return {
            "profile": {"preferences": [], "allergies": [], "dislikes": [], "household_size": 1},
            "pantry": [],
            "recipes": [],
            "cooking_sessions": [],
            "weekly_plans": [],
            "revision": 0,
        }

    @classmethod
    def _normalized_user_record(cls, raw: Any) -> dict[str, Any]:
        record = deepcopy(raw) if isinstance(raw, dict) else {}
        defaults = cls._new_user()
        for key, value in defaults.items():
            record.setdefault(key, deepcopy(value))
        return record

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return self._empty()
        if not isinstance(payload, dict) or not isinstance(payload.get("users"), dict):
            return self._empty()
        payload["schema_version"] = HOME_FOOD_STORE_VERSION
        return payload

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload["schema_version"] = HOME_FOOD_STORE_VERSION
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

    @classmethod
    def _user(cls, payload: dict[str, Any], user_id: Any) -> dict[str, Any]:
        user = normalize_shopping_user(user_id)
        record = cls._normalized_user_record(payload.setdefault("users", {}).get(user))
        payload["users"][user] = record
        return record

    def snapshot(self, user_id: Any) -> dict[str, Any]:
        user = normalize_shopping_user(user_id)
        record = self._normalized_user_record(self._read_unlocked().get("users", {}).get(user))
        return {"user_id": user, **record}

    def update_profile(
        self,
        user_id: Any,
        *,
        preferences: Any,
        allergies: Any,
        dislikes: Any,
        household_size: Any,
    ) -> dict[str, Any]:
        household = int(_positive_number(household_size, maximum=50))

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = self._user(payload, user_id)
            record["profile"] = {
                "preferences": _string_list(preferences),
                "allergies": _string_list(allergies),
                "dislikes": _string_list(dislikes),
                "household_size": household,
            }
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(record["profile"])

        return self._mutate(apply)

    def replace_pantry(self, user_id: Any, items: Any) -> list[dict[str, Any]]:
        if not isinstance(items, list):
            raise ValueError("La despensa debe ser una lista.")
        pantry: list[dict[str, Any]] = []
        for raw in items[:500]:
            if not isinstance(raw, dict) or not _text(raw.get("name")):
                continue
            pantry.append(
                {
                    "name": _text(raw.get("name"), 120),
                    "identity": _identity(raw.get("name")),
                    "quantity": _positive_number(raw.get("quantity") or 1),
                    "unit": _text(raw.get("unit") or "unidad", 32) or "unidad",
                }
            )

        def apply(payload: dict[str, Any]) -> list[dict[str, Any]]:
            record = self._user(payload, user_id)
            record["pantry"] = pantry
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(pantry)

        return self._mutate(apply)

    @staticmethod
    def _normalize_recipe(raw: dict[str, Any]) -> dict[str, Any]:
        title = _text(raw.get("title"), 180)
        if not title:
            raise ValueError("La receta necesita un título.")
        servings = _positive_number(raw.get("servings") or 1, maximum=100)
        ingredients: list[dict[str, Any]] = []
        for row in raw.get("ingredients") or []:
            if not isinstance(row, dict) or not _text(row.get("name")):
                continue
            ingredients.append(
                {
                    "name": _text(row.get("name"), 120),
                    "quantity": _positive_number(row.get("quantity") or 1),
                    "unit": _text(row.get("unit") or "unidad", 32) or "unidad",
                    "notes": _text(row.get("notes"), 240),
                }
            )
        if not ingredients:
            raise ValueError("La receta necesita ingredientes.")
        steps = _string_list(raw.get("steps"), limit=40)
        if not steps:
            raise ValueError("La receta necesita pasos de preparación.")
        kind = _identity(raw.get("kind") or raw.get("category"))
        if kind not in {"meal", "bread", "dessert", "drink", "other"}:
            searchable = _identity(f"{title} {raw.get('description') or ''}")
            if re.search(r"\b(bebida|batido|coctel|cocktail|jugo|zumo|limonada|cafe|te|smoothie)\b", searchable):
                kind = "drink"
            elif re.search(r"\b(pan|baguette|focaccia|brioche|masa)\b", searchable):
                kind = "bread"
            elif re.search(r"\b(postre|pastel|tarta|galleta|flan|helado)\b", searchable):
                kind = "dessert"
            else:
                kind = "meal"
        return {
            "title": title,
            "description": _text(raw.get("description"), 1000),
            "kind": kind,
            "servings": servings,
            "ingredients": ingredients,
            "steps": steps,
            "allergen_notes": _string_list(raw.get("allergen_notes"), limit=20),
            "sources": [row for row in (raw.get("sources") or [])[:20] if isinstance(row, dict)],
        }

    def save_recipe(self, user_id: Any, recipe: dict[str, Any], *, mode: str = "routine") -> dict[str, Any]:
        normalized = self._normalize_recipe(recipe)

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = self._user(payload, user_id)
            row = {
                "id": uuid4().hex,
                **normalized,
                "mode": "deep" if mode == "deep" else "routine",
                "created_at": _now_iso(),
                "shopping_converted_at": None,
            }
            record.setdefault("recipes", []).append(row)
            record["recipes"] = record["recipes"][-100:]
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(row)

        return self._mutate(apply)

    def get_recipe(self, user_id: Any, recipe_id: str) -> dict[str, Any]:
        for recipe in self.snapshot(user_id).get("recipes", []):
            if str(recipe.get("id")) == str(recipe_id):
                return recipe
        raise KeyError(recipe_id)

    def start_cooking_session(self, user_id: Any, recipe_id: str) -> dict[str, Any]:
        recipe = self.get_recipe(user_id, recipe_id)

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = self._user(payload, user_id)
            timestamp = _now_iso()
            for existing in record.get("cooking_sessions", []):
                if existing.get("status") == "ACTIVE":
                    existing["status"] = "PAUSED"
                    existing["updated_at"] = timestamp
            session = {
                "id": uuid4().hex,
                "recipe_id": recipe_id,
                "recipe_title": recipe.get("title"),
                "step_index": 0,
                "step_count": len(recipe.get("steps") or []),
                "status": "ACTIVE",
                "created_at": timestamp,
                "updated_at": timestamp,
                "completed_at": None,
            }
            record.setdefault("cooking_sessions", []).append(session)
            record["cooking_sessions"] = record["cooking_sessions"][-100:]
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(session)

        return self._mutate(apply)

    def update_cooking_session(self, user_id: Any, session_id: str, action: str) -> dict[str, Any]:
        normalized_action = _identity(action).replace(" ", "_")
        if normalized_action not in {"next", "previous", "restart", "complete"}:
            raise ValueError("Acción de cocina no válida.")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = self._user(payload, user_id)
            session = next(
                (row for row in record.get("cooking_sessions", []) if str(row.get("id")) == str(session_id)),
                None,
            )
            if session is None:
                raise KeyError(session_id)
            recipe = next(
                (row for row in record.get("recipes", []) if str(row.get("id")) == str(session.get("recipe_id"))),
                None,
            )
            if recipe is None:
                raise KeyError(session.get("recipe_id"))
            last_index = max(0, len(recipe.get("steps") or []) - 1)
            current = max(0, min(int(session.get("step_index") or 0), last_index))
            if normalized_action == "next":
                if current >= last_index:
                    session["status"] = "COMPLETED"
                    session["completed_at"] = _now_iso()
                else:
                    session["step_index"] = current + 1
                    session["status"] = "ACTIVE"
            elif normalized_action == "previous":
                session["step_index"] = max(0, current - 1)
                session["status"] = "ACTIVE"
                session["completed_at"] = None
            elif normalized_action == "restart":
                session["step_index"] = 0
                session["status"] = "ACTIVE"
                session["completed_at"] = None
            else:
                session["status"] = "COMPLETED"
                session["completed_at"] = _now_iso()
            session["updated_at"] = _now_iso()
            session["step_count"] = len(recipe.get("steps") or [])
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(session)

        return self._mutate(apply)

    def cooking_session_detail(self, user_id: Any, session_id: str) -> dict[str, Any]:
        snapshot = self.snapshot(user_id)
        session = next(
            (row for row in snapshot.get("cooking_sessions", []) if str(row.get("id")) == str(session_id)),
            None,
        )
        if session is None:
            raise KeyError(session_id)
        recipe = next(
            (row for row in snapshot.get("recipes", []) if str(row.get("id")) == str(session.get("recipe_id"))),
            None,
        )
        if recipe is None:
            raise KeyError(session.get("recipe_id"))
        index = max(0, min(int(session.get("step_index") or 0), len(recipe.get("steps") or []) - 1))
        return {
            "session": session,
            "recipe": recipe,
            "current_step": (recipe.get("steps") or [""])[index],
            "step_number": index + 1,
        }

    def scale_recipe(self, user_id: Any, recipe_id: str, servings: Any) -> dict[str, Any]:
        recipe = self.get_recipe(user_id, recipe_id)
        target = _positive_number(servings, maximum=100)
        factor = target / _positive_number(recipe.get("servings") or 1, maximum=100)
        scaled = deepcopy(recipe)
        scaled["servings"] = target
        scaled["ingredients"] = [
            {**row, "quantity": round(_positive_number(row.get("quantity") or 1) * factor, 4)}
            for row in recipe.get("ingredients", [])
        ]
        scaled["scaled_from_servings"] = recipe.get("servings")
        return scaled

    def shopping_preview(self, user_id: Any, recipe_id: str, *, servings: Any | None = None) -> dict[str, Any]:
        recipe = self.scale_recipe(user_id, recipe_id, servings) if servings is not None else self.get_recipe(user_id, recipe_id)
        pantry = self.snapshot(user_id).get("pantry", [])
        available: dict[tuple[str, str], float] = {}
        for row in pantry:
            key = (_identity(row.get("name")), _text(row.get("unit") or "unidad", 32).casefold())
            available[key] = available.get(key, 0) + float(row.get("quantity") or 0)
        missing: list[dict[str, Any]] = []
        for row in recipe.get("ingredients", []):
            key = (_identity(row.get("name")), _text(row.get("unit") or "unidad", 32).casefold())
            needed = float(row.get("quantity") or 0)
            shortfall = max(0.0, needed - available.get(key, 0.0))
            if shortfall > 0:
                missing.append({**row, "quantity": round(shortfall, 4)})
        return {
            "recipe_id": recipe_id,
            "title": recipe.get("title"),
            "servings": recipe.get("servings"),
            "items": missing,
            "requires_confirmation": True,
        }

    def commit_recipe_to_shopping(
        self,
        user_id: Any,
        recipe_id: str,
        shopping: ShoppingListStore,
        *,
        confirmed: bool,
        servings: Any | None = None,
    ) -> dict[str, Any]:
        preview = self.shopping_preview(user_id, recipe_id, servings=servings)
        if confirmed is not True:
            return {"status": "CONFIRMATION_REQUIRED", **preview}
        added = [
            shopping.add(
                user_id,
                row["name"],
                quantity=row["quantity"],
                unit=row.get("unit") or "unidad",
                category="FOOD",
                notes=f"Receta: {preview['title']}",
                source="roxy_home_recipe",
            )
            for row in preview["items"]
        ]

        def apply(payload: dict[str, Any]) -> None:
            record = self._user(payload, user_id)
            for recipe in record.get("recipes", []):
                if str(recipe.get("id")) == str(recipe_id):
                    recipe["shopping_converted_at"] = _now_iso()
                    break
            record["revision"] = int(record.get("revision") or 0) + 1

        self._mutate(apply)
        return {"status": "ADDED", "recipe_id": recipe_id, "items": added}

    def save_weekly_plan(self, user_id: Any, plan: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(plan, dict) or not isinstance(plan.get("days"), list):
            raise ValueError("El plan semanal no es válido.")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = self._user(payload, user_id)
            row = {"id": uuid4().hex, "created_at": _now_iso(), **deepcopy(plan)}
            record.setdefault("weekly_plans", []).append(row)
            record["weekly_plans"] = record["weekly_plans"][-20:]
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(row)

        return self._mutate(apply)


class HomePermissionPolicy:
    """Explicitly denies purchases and sensitive device control."""

    SAFE_ACTIONS = {"recipe", "substitute", "scale", "weekly_plan", "profile", "pantry", "food_safety"}

    @classmethod
    def decision(cls, action: str, *, confirmed: bool = False) -> str:
        normalized = re.sub(r"[^a-z_]", "", str(action or "").lower())
        if normalized in cls.SAFE_ACTIONS:
            return "ALLOW"
        if normalized == "recipe_to_shopping":
            return "ALLOW" if confirmed else "CONFIRMATION_REQUIRED"
        if normalized in {"purchase", "buy", "device_control", "appliance_control"}:
            return "DENY"
        return "DENY"
