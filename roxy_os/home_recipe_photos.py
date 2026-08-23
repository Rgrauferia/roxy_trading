"""Exact, shared recipe artwork for Roxy Home.

Only images created and approved for one exact recipe title are served. The
store intentionally has no web-search fallback: a clean card without a photo
is safer than showing another dish. Generated files are shared by all Home
users and cached once, while personal recipe data remains private.
"""

from __future__ import annotations

import base64
import concurrent.futures
import hashlib
import json
import os
import re
import threading
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


BUILT_IN_ROOT = Path(__file__).resolve().parents[1] / "assets" / "roxy_home" / "recipe_custom"
BUILT_IN_PHOTOS = {
    "affogato": "affogato.jpg",
    "cafe americano": "cafe-americano.jpg",
    "cafe con canela": "cafe-con-canela.jpg",
    "pan cubano": "pan-cubano.jpg",
}

DISH_DIRECTIONS = {
    "pan cubano": (
        "traditional Cuban bread: one long slender golden loaf, thin crisp "
        "crust, shallow lengthwise split and airy crumb; not brioche, not a "
        "soft sandwich loaf and not a French baguette"
    ),
    "affogato": (
        "classic Italian affogato: one scoop of vanilla gelato in a small "
        "dessert glass with dark espresso poured over it; not cake or pancakes"
    ),
    "cafe americano": (
        "one ceramic cup of clear dark black Americano coffee with a light "
        "amber crema ring; not milk coffee, tea or multiple cups"
    ),
    "cafe con canela": (
        "one warm cup of light caramel-brown coffee with milk, delicate foam, "
        "ground cinnamon and a cinnamon stick; unmistakably coffee, not soup"
    ),
}


def _identity(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def recipe_photo_prompt(recipe: dict[str, Any]) -> str:
    """Build a strict prompt from the exact recipe, never just its category."""
    title = re.sub(r"\s+", " ", str(recipe.get("title") or "")).strip()
    if not title:
        raise ValueError("La receta necesita un título")
    ingredients = [
        re.sub(r"\s+", " ", str(row.get("name") or "")).strip()
        for row in (recipe.get("ingredients") or [])
        if isinstance(row, dict) and str(row.get("name") or "").strip()
    ]
    exact = DISH_DIRECTIONS.get(_identity(title), f"the finished prepared dish exactly named {title}")
    ingredient_context = ", ".join(ingredients[:10]) or "the recipe's characteristic ingredients"
    return (
        f'Create one photorealistic editorial food photograph for the Roxy Home recipe "{title}". '
        f"Show only the prepared final result: {exact}. Key recipe ingredients: {ingredient_context}. "
        "The image must be specific to this exact recipe, not a generic category platter and not a different dish. "
        "Warm natural window light, cream stone surface, subtle dark-green linen accent, landscape food-card framing. "
        "No people, no ingredient collage, no packaging, no text, no labels, no logos and no watermark."
    )


def recipe_photo_query(title: str) -> str:
    """Backward-compatible name for callers that previously built a search."""
    return recipe_photo_prompt({"title": title})


@dataclass(frozen=True)
class RecipePhotoGenerationConfig:
    api_key: str
    model: str = "gpt-5.6-luna"
    enabled: bool = False
    daily_limit: int = 600
    quality: str = "low"

    @classmethod
    def from_env(cls) -> "RecipePhotoGenerationConfig":
        api_key = str(os.getenv("ROXY_HOME_OPENAI_API_KEY") or "").strip()
        enabled = str(os.getenv("ROXY_HOME_RECIPE_IMAGE_GENERATION_ENABLED") or "1").strip().lower() in {
            "1", "true", "yes", "on"
        }
        try:
            daily_limit = max(1, min(600, int(os.getenv("ROXY_HOME_RECIPE_IMAGE_DAILY_LIMIT") or 600)))
        except ValueError:
            daily_limit = 600
        quality = str(os.getenv("ROXY_HOME_RECIPE_IMAGE_QUALITY") or "low").strip().lower()
        if quality not in {"low", "medium", "high"}:
            quality = "low"
        return cls(
            api_key=api_key,
            model=str(os.getenv("ROXY_HOME_OPENAI_ROUTINE_MODEL") or "gpt-5.6-luna").strip(),
            enabled=enabled and bool(api_key),
            daily_limit=daily_limit,
            quality=quality,
        )


class RecipePhotoStore:
    def __init__(self, root: str | Path | None = None, *, built_in_root: str | Path | None = None) -> None:
        configured = root or os.getenv("ROXY_HOME_RECIPE_PHOTO_DIR", "data/roxy_home_recipe_photos")
        self.root = Path(configured)
        self.root.mkdir(parents=True, exist_ok=True)
        self.built_in_root = Path(built_in_root) if built_in_root else BUILT_IN_ROOT
        self.manifest_path = self.root / "manifest.json"
        self._lock = threading.Lock()

    @staticmethod
    def _key(title: str) -> str:
        return hashlib.sha256(_identity(title).encode("utf-8")).hexdigest()[:24]

    def _manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"photos": {}}
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {"photos": {}}
        except (OSError, ValueError):
            return {"photos": {}}

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.manifest_path)

    def resolve(self, title: str) -> tuple[Path, dict[str, Any]] | None:
        normalized = _identity(title)
        built_in_name = BUILT_IN_PHOTOS.get(normalized)
        if built_in_name:
            path = self.built_in_root / built_in_name
            if path.is_file():
                return path, {
                    "title": title,
                    "filename": built_in_name,
                    "media_type": "image/jpeg",
                    "provider": "Roxy Home",
                    "approved": True,
                }

        saved = (self._manifest().get("photos") or {}).get(self._key(title))
        if not isinstance(saved, dict) or _identity(saved.get("title") or "") != normalized:
            return None
        path = self.root / str(saved.get("filename") or "")
        if not saved.get("approved") or not path.is_file():
            return None
        return path, saved

    def save_generated(self, title: str, image_base64: str, *, approved: bool = False) -> Path:
        """Persist a generated image once; unapproved work is never public."""
        raw = base64.b64decode(image_base64, validate=True)
        if not raw.startswith(b"\x89PNG\r\n\x1a\n") or len(raw) > 12_000_000:
            raise ValueError("La imagen generada no es un PNG válido")
        key = self._key(title)
        path = self.root / f"{key}.png"
        with self._lock:
            path.write_bytes(raw)
            manifest = self._manifest()
            manifest.setdefault("photos", {})[key] = {
                "title": title,
                "filename": path.name,
                "media_type": "image/png",
                "provider": "Roxy Home · OpenAI",
                "approved": bool(approved),
            }
            self._save_manifest(manifest)
        return path

    def approve(self, title: str) -> bool:
        key = self._key(title)
        with self._lock:
            manifest = self._manifest()
            saved = (manifest.get("photos") or {}).get(key)
            if not isinstance(saved, dict) or not (self.root / str(saved.get("filename") or "")).is_file():
                return False
            saved["approved"] = True
            self._save_manifest(manifest)
        return True


class RecipePhotoGenerationQueue:
    """Small bounded queue that creates each missing catalog image only once."""

    def __init__(self, store: RecipePhotoStore, config: RecipePhotoGenerationConfig, *, client: Any | None = None) -> None:
        self.store = store
        self.config = config
        self._client = client
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="roxy-recipe-image")
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self.budget_path = store.root / "image-generation-budget.json"
        self.failures_path = store.root / "image-generation-failures.json"

    def public_status(self) -> dict[str, Any]:
        budget = self._budget()
        with self._lock:
            pending = len(self._pending)
        return {
            "enabled": self.config.enabled,
            "pending": pending,
            "generated_today": int(budget.get("count") or 0),
            "daily_limit": self.config.daily_limit,
        }

    def _budget(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.budget_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
        today = date.today().isoformat()
        return payload if payload.get("date") == today else {"date": today, "count": 0}

    def _reserve(self) -> bool:
        payload = self._budget()
        if int(payload.get("count") or 0) >= self.config.daily_limit:
            return False
        payload["count"] = int(payload.get("count") or 0) + 1
        temporary = self.budget_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload), encoding="utf-8")
        temporary.replace(self.budget_path)
        return True

    def schedule(self, recipe: dict[str, Any]) -> str:
        title = re.sub(r"\s+", " ", str(recipe.get("title") or "")).strip()
        if not title or not self.config.enabled:
            return "DISABLED"
        if self.store.resolve(title) is not None:
            return "READY"
        key = self.store._key(title)
        with self._lock:
            if key in self._pending:
                return "PENDING"
            if not self._reserve():
                return "LIMIT_REACHED"
            self._pending.add(key)
        self._executor.submit(self._generate, key, dict(recipe))
        return "PENDING"

    def populate(self, recipes: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for recipe in recipes:
            state = self.schedule(recipe)
            counts[state] = counts.get(state, 0) + 1
        return counts

    def _openai(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.config.api_key)
        return self._client

    @staticmethod
    def _image_result(response: Any) -> str:
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", "") == "image_generation_call" and getattr(item, "result", None):
                return str(item.result)
        raise RuntimeError("OpenAI no devolvió una imagen")

    def _record_failure(self, title: str, error: Exception) -> None:
        try:
            payload = json.loads(self.failures_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {"failures": {}}
        payload.setdefault("failures", {})[self.store._key(title)] = {
            "title": title,
            "at": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
        }
        temporary = self.failures_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.failures_path)

    def _generate(self, key: str, recipe: dict[str, Any]) -> None:
        title = str(recipe.get("title") or "")
        try:
            response = self._openai().responses.create(
                model=self.config.model,
                input=recipe_photo_prompt(recipe),
                tools=[{"type": "image_generation", "quality": self.config.quality, "size": "1024x1024"}],
                store=False,
            )
            self.store.save_generated(title, self._image_result(response), approved=True)
        except Exception as exc:  # Failure metadata intentionally excludes secret/provider text.
            self._record_failure(title, exc)
        finally:
            with self._lock:
                self._pending.discard(key)
