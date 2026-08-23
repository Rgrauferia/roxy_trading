"""Exact, shared recipe artwork for Roxy Home.

Only images created and approved for one exact recipe title are served. The
store intentionally has no web-search fallback: a clean card without a photo
is safer than showing another dish. Generated files are shared by all Home
users and cached once, while personal recipe data remains private.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import threading
import unicodedata
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
