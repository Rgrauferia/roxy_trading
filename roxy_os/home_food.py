from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from roxy_os.home_recipe_catalog import CATEGORY_META, infer_recipe_category
from roxy_os.home_pet_catalog import pet_profile_completion

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

from roxy_os.shopping_list import ShoppingListStore, normalize_shopping_user


HOME_FOOD_STORE_VERSION = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cooking_step_timer_seconds(value: Any) -> int:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower()
    seconds = 0.0
    patterns = (
        (r"(\d+(?:[.,]\d+)?)\s*(?:horas?|hrs?|h)\b", 3600),
        (r"(\d+(?:[.,]\d+)?)\s*(?:minutos?|mins?|min)\b", 60),
        (r"(\d+(?:[.,]\d+)?)\s*(?:segundos?|segs?|seg|s)\b", 1),
    )
    for pattern, factor in patterns:
        seconds += sum(float(match.replace(",", ".")) * factor for match in re.findall(pattern, text))
    return max(0, round(seconds))


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
            "meal_planning": {
                "style": "normal",
                "cook_days": 2,
                "meal_scope": "all",
                "people": 2,
                "max_minutes": 25,
                "weekly_budget": 85,
            },
            "pantry": [],
            "pets": [],
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
        for recipe in record.get("recipes", []):
            cls._upgrade_installed_recipe(recipe)
            if isinstance(recipe, dict) and recipe.get("kind") == "drink" and recipe.get("drink_type") not in {
                "alcoholic",
                "non_alcoholic",
            }:
                recipe["drink_type"] = cls._infer_drink_type(recipe)
        return record

    @staticmethod
    def _upgrade_installed_recipe(recipe: Any) -> None:
        """Refresh old catalog copies while preserving user-owned metadata."""
        if not isinstance(recipe, dict):
            return
        steps = [str(step or "") for step in recipe.get("steps") or []]
        searchable = _identity(" ".join(steps))
        incomplete = len(steps) < 5 or any(
            phrase in searchable
            for phrase in (
                "metodo indicado", "segun corresponda", "orden indicado", "punto correcto", "cocina u hornea",
                "proporcion indicada", "guarnicion indicada", "salsa indicada", "cuando corresponda", "segun la receta",
            )
        )
        from roxy_os.home_recipe_fallback import exact_local_recipe

        current = exact_local_recipe(recipe.get("title") or "")
        catalog_owned = str(recipe.get("generation_source") or "") in {"", "local_recipe_catalog"}
        if not current or (not incomplete and not catalog_owned):
            return
        old_servings = float(recipe.get("servings") or current.get("servings") or 1)
        catalog_servings = float(current.get("servings") or 1)
        canonical_verified = str(current.get("editorial_status") or "").startswith("verified")
        if canonical_verified:
            recipe["servings"] = catalog_servings
            factor = 1.0
        else:
            factor = old_servings / catalog_servings if catalog_servings else 1.0
        ingredients = deepcopy(current.get("ingredients") or [])
        if factor != 1.0:
            for ingredient in ingredients:
                quantity = ingredient.get("quantity")
                if isinstance(quantity, (int, float)):
                    ingredient["quantity"] = round(float(quantity) * factor, 2)
        for key in (
            "description", "kind", "drink_type", "category", "subcategory", "steps", "sources",
            "editorial_status", "canonical_variant", "prep_minutes", "cook_minutes",
        ):
            recipe[key] = deepcopy(current.get(key))
        recipe["ingredients"] = ingredients
        recipe["editorial_version"] = 3

    @staticmethod
    def _infer_drink_type(recipe: dict[str, Any]) -> str:
        searchable = _identity(
            f"{recipe.get('title') or ''} {recipe.get('description') or ''} "
            + " ".join(
                str(row.get("name") or "")
                for row in (recipe.get("ingredients") or [])
                if isinstance(row, dict)
            )
        )
        alcoholic = re.search(
            r"\b(alcohol|ron|vodka|tequila|whisky|whiskey|ginebra|gin|vino|cerveza|licor|brandy|champan|champagne)\b",
            searchable,
        )
        return "alcoholic" if alcoholic else "non_alcoholic"

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

    def all_saved_recipes(self) -> list[dict[str, Any]]:
        """Return unique Home recipes for shared artwork generation only."""
        payload = self._read_unlocked()
        recipes: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw_record in payload.get("users", {}).values():
            record = self._normalized_user_record(raw_record)
            for recipe in reversed(record.get("recipes", [])):
                if not isinstance(recipe, dict):
                    continue
                key = _identity(recipe.get("title"))
                if not key or key in seen:
                    continue
                seen.add(key)
                recipes.append(deepcopy(recipe))
        return recipes

    def find_saved_recipe_by_title(self, title: Any) -> dict[str, Any] | None:
        target = _identity(title)
        if not target:
            return None
        return next(
            (recipe for recipe in self.all_saved_recipes() if _identity(recipe.get("title")) == target),
            None,
        )

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

    def upsert_pet(
        self, user_id: Any, *, name: Any, species: Any, exact_species: Any = "", breed: Any = "",
        age_years: Any = None, weight_kg: Any = None, life_stage: Any = "unknown", allergies: Any = None,
        conditions: Any = None, current_food: Any = "", veterinarian_instructions: Any = "",
        habitat_type: Any = "", environment_notes: Any = "", routine_notes: Any = "",
        photo_data_url: Any = "", sex: Any = "unknown", sterilized: Any = "unknown",
        size_class: Any = "unknown", activity_level: Any = "unknown", body_condition: Any = "unknown",
        goals: Any = None, current_food_kind: Any = "unknown", feeding_amount: Any = None,
        feeding_unit: Any = "", feeding_frequency: Any = 0, feeding_times: Any = None,
        feeding_amount_source: Any = "unknown", feeding_notes: Any = "",
    ) -> dict[str, Any]:
        pet_name = _text(name, 40)
        pet_species = _identity(species)
        if not pet_name:
            raise ValueError("La mascota necesita un nombre.")
        if pet_species not in {"dog", "cat", "ferret", "rabbit", "guinea_pig", "hamster", "small_mammal", "bird", "fish", "reptile", "amphibian", "invertebrate", "farm_pet", "other"}:
            raise ValueError("La especie de la mascota no es válida.")
        stage = _identity(life_stage) or "unknown"
        if stage not in {"baby", "young", "adult", "senior", "unknown"}:
            stage = "unknown"
        try:
            normalized_age = None if age_years in {None, ""} else round(float(age_years), 2)
            normalized_weight = None if weight_kg in {None, ""} else round(float(weight_kg), 3)
            normalized_feeding_amount = None if feeding_amount in {None, ""} else round(float(feeding_amount), 3)
            normalized_feeding_frequency = int(feeding_frequency or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("La edad, el peso y la alimentación deben usar valores válidos.") from exc
        if normalized_age is not None and not 0 <= normalized_age <= 200:
            raise ValueError("La edad de la mascota no es válida.")
        if normalized_weight is not None and not 0 < normalized_weight <= 2_000:
            raise ValueError("El peso de la mascota no es válido.")
        if normalized_feeding_amount is not None and not 0 < normalized_feeding_amount <= 100_000:
            raise ValueError("La cantidad de alimento no es válida.")
        if not 0 <= normalized_feeding_frequency <= 24:
            raise ValueError("La frecuencia de alimentación no es válida.")
        photo = str(photo_data_url or "")
        if photo and not re.match(r"^data:image/(?:jpeg|png|webp);base64,", photo):
            raise ValueError("La foto de la mascota debe ser JPEG, PNG o WebP.")
        profile = {
            "name": pet_name, "species": pet_species, "exact_species": _text(exact_species, 100),
            "breed": _text(breed, 100), "age_years": normalized_age, "weight_kg": normalized_weight,
            "life_stage": stage, "allergies": _string_list(allergies), "conditions": _string_list(conditions),
            "sex": _identity(sex) or "unknown", "sterilized": _identity(sterilized) or "unknown",
            "size_class": _identity(size_class) or "unknown",
            "activity_level": _identity(activity_level) or "unknown",
            "body_condition": _identity(body_condition) or "unknown", "goals": _string_list(goals),
            "current_food": _text(current_food, 160),
            "current_food_kind": _identity(current_food_kind) or "unknown",
            "feeding_amount": normalized_feeding_amount,
            "feeding_unit": _text(feeding_unit, 32),
            "feeding_frequency": normalized_feeding_frequency,
            "feeding_times": _string_list(feeding_times, limit=24),
            "feeding_amount_source": _identity(feeding_amount_source) or "unknown",
            "feeding_notes": _text(feeding_notes, 1_000),
            "veterinarian_instructions": _text(veterinarian_instructions, 2_000),
            "habitat_type": _text(habitat_type, 100), "environment_notes": _text(environment_notes, 1_000),
            "routine_notes": _text(routine_notes, 1_000),
        }
        profile["profile_complete"] = pet_profile_completion(profile)["status"] == "complete"
        if photo:
            profile["photo_data_url"] = photo

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = self._user(payload, user_id)
            pets = record.setdefault("pets", [])
            existing = next((row for row in pets if _identity(row.get("name")) == _identity(pet_name)), None)
            if existing is None:
                existing = {"id": uuid4().hex, "created_at": _now_iso(), **profile}
                pets.append(existing)
            else:
                existing.update(**profile, updated_at=_now_iso())
            record["pets"] = pets[-20:]
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(existing)

        return self._mutate(apply)

    def add_pet_medical_record(
        self, user_id: Any, pet_id: Any, *, occurred_on: Any = None, record_type: Any = "note",
        title: Any, provider: Any = "", notes: Any = "", medications: Any = None,
        next_due_on: Any = None, weight_kg: Any = None, attachment_name: Any = "",
        attachment_type: Any = "", attachment_data_url: Any = "",
    ) -> dict[str, Any]:
        pet_key = _text(pet_id, 80)
        clean_title = _text(title, 120)
        if not clean_title:
            raise ValueError("El registro médico necesita un título.")
        clean_type = _identity(record_type) or "note"
        if clean_type not in {"checkup", "vaccine", "diagnosis", "treatment", "surgery", "lab", "allergy", "medication", "weight", "note"}:
            raise ValueError("El tipo de registro médico no es válido.")
        try:
            clean_weight = None if weight_kg in {None, ""} else round(float(weight_kg), 3)
        except (TypeError, ValueError) as exc:
            raise ValueError("El peso del registro no es válido.") from exc
        if clean_weight is not None and not 0 < clean_weight <= 2_000:
            raise ValueError("El peso del registro no es válido.")
        clean_attachment = str(attachment_data_url or "").strip()
        clean_attachment_type = _identity(attachment_type)
        allowed_attachments = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
        if clean_attachment:
            if clean_attachment_type not in allowed_attachments or not clean_attachment.startswith(f"data:{clean_attachment_type};base64,"):
                raise ValueError("El documento debe ser PDF, JPEG, PNG o WebP.")
            if len(clean_attachment) > 1_500_000:
                raise ValueError("El documento es demasiado grande. Usa un archivo de hasta 1 MB.")
        record = {
            "id": uuid4().hex, "occurred_on": str(occurred_on or "")[:10], "record_type": clean_type,
            "title": clean_title, "provider": _text(provider, 120), "notes": _text(notes, 2_000),
            "medications": _string_list(medications), "next_due_on": str(next_due_on or "")[:10],
            "weight_kg": clean_weight, "created_at": _now_iso(),
            "attachment_name": _text(attachment_name, 120) if clean_attachment else "",
            "attachment_type": clean_attachment_type if clean_attachment else "",
            "attachment_data_url": clean_attachment,
        }

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            owner = self._user(payload, user_id)
            pet = next((row for row in owner.setdefault("pets", []) if _text(row.get("id"), 80) == pet_key), None)
            if pet is None:
                raise KeyError(pet_key)
            history = pet.setdefault("medical_history", [])
            history.append(record)
            pet["medical_history"] = history[-100:]
            pet["updated_at"] = _now_iso()
            owner["revision"] = int(owner.get("revision") or 0) + 1
            return deepcopy(record)

        return self._mutate(apply)

    def complete_pet_care_routine(
        self, user_id: Any, pet_id: Any, *, routine_id: Any, title: Any, outcome: Any = "completed", notes: Any = "",
    ) -> dict[str, Any]:
        pet_key = _text(pet_id, 80)
        clean_routine = _identity(routine_id).replace(" ", "_")
        clean_title = _text(title, 120)
        if not re.fullmatch(r"[a-z0-9_\-]{1,80}", clean_routine):
            raise ValueError("La rutina no es válida.")
        if not clean_title:
            raise ValueError("La rutina necesita un título.")
        clean_outcome = _identity(outcome) or "completed"
        if clean_outcome not in {"completed", "all", "partial", "refused"}:
            raise ValueError("El resultado del cuidado no es válido.")
        entry = {
            "id": uuid4().hex,
            "routine_id": clean_routine,
            "title": clean_title,
            "outcome": clean_outcome,
            "notes": _text(notes, 500),
            "completed_at": _now_iso(),
        }

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            owner = self._user(payload, user_id)
            pet = next((row for row in owner.setdefault("pets", []) if _text(row.get("id"), 80) == pet_key), None)
            if pet is None:
                raise KeyError(pet_key)
            log = pet.setdefault("care_log", [])
            log.append(entry)
            pet["care_log"] = log[-500:]
            pet["updated_at"] = _now_iso()
            owner["revision"] = int(owner.get("revision") or 0) + 1
            return deepcopy(entry)

        return self._mutate(apply)

    def upsert_pantry(self, user_id: Any, items: Any) -> list[dict[str, Any]]:
        if not isinstance(items, list):
            raise ValueError("La despensa debe ser una lista.")
        additions = items

        def apply(payload: dict[str, Any]) -> list[dict[str, Any]]:
            record = self._user(payload, user_id)
            pantry = record.setdefault("pantry", [])
            for raw in additions[:100]:
                if not isinstance(raw, dict) or not _text(raw.get("name")):
                    continue
                name = _text(raw.get("name"), 120)
                identity = _identity(name)
                quantity = _positive_number(raw.get("quantity") or 1)
                unit = _text(raw.get("unit") or "unidad", 32) or "unidad"
                existing = next(
                    (row for row in pantry if row.get("identity") == identity and _identity(row.get("unit")) == _identity(unit)),
                    None,
                )
                if existing:
                    existing["quantity"] = round(float(existing.get("quantity") or 0) + quantity, 4)
                    existing["name"] = name
                else:
                    pantry.append({"name": name, "identity": identity, "quantity": quantity, "unit": unit})
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(pantry)

        return self._mutate(apply)

    def remove_pantry(self, user_id: Any, names: Any) -> tuple[list[dict[str, Any]], list[str]]:
        targets = [_identity(name) for name in (names or []) if _text(name)]

        def apply(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
            record = self._user(payload, user_id)
            pantry = record.setdefault("pantry", [])
            removed = [deepcopy(row) for row in pantry if row.get("identity") in targets]
            found = {str(row.get("identity") or "") for row in removed}
            record["pantry"] = [row for row in pantry if row.get("identity") not in targets]
            if removed:
                record["revision"] = int(record.get("revision") or 0) + 1
            missing = [name for name, target in zip(names or [], targets) if target not in found]
            return removed, missing

        return self._mutate(apply)

    def update_meal_planning(
        self,
        user_id: Any,
        *,
        style: str,
        cook_days: Any,
        meal_scope: str,
        people: Any,
        max_minutes: Any,
        weekly_budget: Any,
    ) -> dict[str, Any]:
        if style not in {"fitness", "normal", "quick", "weight_loss"}:
            raise ValueError("El estilo de alimentación no es válido.")
        if meal_scope not in {"all", "lunch_dinner", "dinner_only"}:
            raise ValueError("La cantidad de comidas no es válida.")
        planning = {
            "style": style,
            "cook_days": int(_positive_number(cook_days, maximum=7)),
            "meal_scope": meal_scope,
            "people": int(_positive_number(people, maximum=20)),
            "max_minutes": int(_positive_number(max_minutes, maximum=180)),
            "weekly_budget": round(float(weekly_budget), 2),
        }
        if planning["weekly_budget"] < 0 or planning["weekly_budget"] > 10_000:
            raise ValueError("El presupuesto semanal no es válido.")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = self._user(payload, user_id)
            record["meal_planning"] = planning
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(planning)

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
        drink_type = ""
        if kind == "drink":
            drink_type = _identity(raw.get("drink_type"))
            if drink_type not in {"alcoholic", "non_alcoholic"}:
                drink_type = HomeFoodStore._infer_drink_type(
                    {"title": title, "description": raw.get("description"), "ingredients": ingredients}
                )
        category = _text(raw.get("category"), 40)
        if category not in CATEGORY_META:
            category = infer_recipe_category(title, kind, drink_type)
        return {
            "title": title,
            "description": _text(raw.get("description"), 1000),
            "kind": kind,
            "drink_type": drink_type,
            "category": category,
            "subcategory": _text(raw.get("subcategory"), 80),
            "servings": servings,
            "ingredients": ingredients,
            "steps": steps,
            "allergen_notes": _string_list(raw.get("allergen_notes"), limit=20),
            "audience": "pet" if _identity(raw.get("audience")) == "pet" else "human",
            "pet_species": _text(raw.get("pet_species"), 32),
            "pet_category": _text(raw.get("pet_category"), 40),
            "safety_class": _text(raw.get("safety_class"), 32),
            "veterinary_note": _text(raw.get("veterinary_note"), 1000),
            "photo_asset": _text(raw.get("photo_asset"), 240),
            "sources": [row for row in (raw.get("sources") or [])[:20] if isinstance(row, dict)],
            "shared_recipe_id": _text(raw.get("shared_recipe_id"), 64),
            "generation_source": _text(raw.get("generation_source"), 64),
            "editorial_status": _text(raw.get("editorial_status"), 40),
            "canonical_variant": _text(raw.get("canonical_variant"), 240),
            "prep_minutes": max(0, int(raw.get("prep_minutes") or 0)),
            "cook_minutes": max(0, int(raw.get("cook_minutes") or 0)),
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
                "favorite": False,
                "user_notes": "",
                "photo_data_url": "",
            }
            record.setdefault("recipes", []).append(row)
            record["recipes"] = record["recipes"][-100:]
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(row)

        return self._mutate(apply)

    def personalize_recipe(
        self,
        user_id: Any,
        recipe_id: str,
        *,
        favorite: Any,
        user_notes: Any,
        photo_data_url: Any = None,
    ) -> dict[str, Any]:
        notes = _text(user_notes, 2000)
        photo = None if photo_data_url is None else str(photo_data_url or "").strip()
        if photo and not re.match(r"^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$", photo):
            raise ValueError("La foto debe ser JPEG, PNG o WebP.")
        if photo and len(photo) > 2_100_000:
            raise ValueError("La foto es demasiado grande; usa una imagen menor de 1.5 MB.")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = self._user(payload, user_id)
            recipe = next(
                (row for row in record.get("recipes", []) if str(row.get("id")) == str(recipe_id)),
                None,
            )
            if recipe is None:
                raise KeyError(recipe_id)
            recipe["favorite"] = bool(favorite)
            recipe["user_notes"] = notes
            if photo is not None:
                recipe["photo_data_url"] = photo
            recipe["updated_at"] = _now_iso()
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(recipe)

        return self._mutate(apply)

    def get_recipe(self, user_id: Any, recipe_id: str) -> dict[str, Any]:
        for recipe in self.snapshot(user_id).get("recipes", []):
            if str(recipe.get("id")) == str(recipe_id):
                return recipe
        raise KeyError(recipe_id)

    def delete_recipe(self, user_id: Any, recipe_id: str) -> dict[str, Any]:
        """Delete one recipe and only its associated cooking sessions."""

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = self._user(payload, user_id)
            recipes = record.get("recipes", [])
            recipe = next(
                (row for row in recipes if str(row.get("id")) == str(recipe_id)),
                None,
            )
            if recipe is None:
                raise KeyError(recipe_id)
            record["recipes"] = [
                row for row in recipes if str(row.get("id")) != str(recipe_id)
            ]
            record["cooking_sessions"] = [
                row
                for row in record.get("cooking_sessions", [])
                if str(row.get("recipe_id")) != str(recipe_id)
            ]
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(recipe)

        return self._mutate(apply)

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
                "timers": [],
            }
            record.setdefault("cooking_sessions", []).append(session)
            record["cooking_sessions"] = record["cooking_sessions"][-100:]
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(session)

        return self._mutate(apply)

    def add_cooking_timer(
        self, user_id: Any, session_id: str, *, duration_seconds: Any, label: Any = "Temporizador"
    ) -> dict[str, Any]:
        seconds = int(_positive_number(duration_seconds, maximum=86_400))

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = self._user(payload, user_id)
            session = next(
                (row for row in record.get("cooking_sessions", []) if str(row.get("id")) == str(session_id)),
                None,
            )
            if session is None:
                raise KeyError(session_id)
            started = datetime.now(timezone.utc)
            timer = {
                "id": uuid4().hex,
                "label": _text(label, 120) or "Temporizador",
                "duration_seconds": seconds,
                "started_at": started.isoformat(),
                "ends_at": (started + timedelta(seconds=seconds)).isoformat(),
                "status": "ACTIVE",
            }
            session.setdefault("timers", []).append(timer)
            session["updated_at"] = _now_iso()
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(timer)

        return self._mutate(apply)

    def cancel_cooking_timer(self, user_id: Any, session_id: str, timer_id: str) -> dict[str, Any]:
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = self._user(payload, user_id)
            session = next((row for row in record.get("cooking_sessions", []) if str(row.get("id")) == str(session_id)), None)
            if session is None:
                raise KeyError(session_id)
            timer = next((row for row in session.get("timers", []) if str(row.get("id")) == str(timer_id)), None)
            if timer is None:
                raise KeyError(timer_id)
            timer["status"] = "CANCELLED"
            timer["cancelled_at"] = _now_iso()
            session["updated_at"] = _now_iso()
            record["revision"] = int(record.get("revision") or 0) + 1
            return deepcopy(timer)

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
        enriched_session = deepcopy(session)
        now = datetime.now(timezone.utc)
        for timer in enriched_session.get("timers", []):
            if timer.get("status") != "ACTIVE":
                timer["remaining_seconds"] = 0
                continue
            try:
                remaining = max(0, int((datetime.fromisoformat(str(timer.get("ends_at"))) - now).total_seconds()))
            except (TypeError, ValueError):
                remaining = 0
            timer["remaining_seconds"] = remaining
            if remaining == 0:
                timer["status"] = "FINISHED"
        current_step = (recipe.get("steps") or [""])[index]
        return {
            "session": enriched_session,
            "recipe": recipe,
            "current_step": current_step,
            "step_number": index + 1,
            "suggested_timer_seconds": cooking_step_timer_seconds(current_step),
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

    def get_weekly_plan(self, user_id: Any, plan_id: str) -> dict[str, Any]:
        snapshot = self.snapshot(user_id)
        row = next(
            (plan for plan in snapshot.get("weekly_plans", []) if str(plan.get("id")) == str(plan_id)),
            None,
        )
        if row is None:
            raise KeyError(plan_id)
        return deepcopy(row)

    def replace_weekly_plan(self, user_id: Any, plan_id: str, plan: dict[str, Any]) -> dict[str, Any]:
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            record = self._user(payload, user_id)
            for index, existing in enumerate(record.get("weekly_plans", [])):
                if str(existing.get("id")) == str(plan_id):
                    updated = {**deepcopy(plan), "id": existing["id"], "created_at": existing["created_at"]}
                    record["weekly_plans"][index] = updated
                    record["revision"] = int(record.get("revision") or 0) + 1
                    return deepcopy(updated)
            raise KeyError(plan_id)

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
