"""Shared, real-photo resolver for Roxy Home recipes.

Photos come from Openverse's openly licensed catalog.  A result is accepted only
when its title/tags overlap the translated recipe name; otherwise the caller
gets no image instead of an unrelated or synthetic one.  Accepted photos and
their attribution are cached once for every household using the deployment.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


OPENVERSE_SEARCH_URL = "https://api.openverse.org/v1/images/"
ALLOWED_IMAGE_HOSTS = {"api.openverse.org"}
USER_AGENT = "RoxyHome/1.0 (recipe photo resolver)"
RESOLVER_VERSION = 3


PHRASES = {
    "huevos revueltos": "scrambled eggs",
    "huevos fritos": "fried eggs",
    "huevos hervidos": "boiled eggs",
    "tortilla espanola": "spanish potato omelette",
    "mantequilla de mani": "peanut butter",
    "arroz con leche": "rice pudding",
    "tres leches": "tres leches cake",
    "ropa vieja": "cuban shredded beef ropa vieja",
    "picadillo cubano": "cuban beef picadillo",
    "bistec encebollado": "beef steak with onions",
    "moros y cristianos": "cuban black beans and rice",
    "arroz congri": "cuban rice and beans congri",
    "pollo al ajo": "garlic chicken",
    "camarones al ajillo": "garlic shrimp",
    "pure de papas": "mashed potatoes",
    "platanos maduros": "fried sweet plantains",
    "yuca con mojo": "cassava with garlic sauce",
    "avena nocturna": "overnight oats",
    "pan de banana": "banana bread",
    "jugo verde": "green juice",
    "cafe cubano": "cuban espresso coffee",
    "cafe con leche": "coffee with milk",
    "cafe helado": "iced coffee",
}

WORDS = {
    "huevo": "egg", "huevos": "eggs", "avena": "oats", "yogur": "yogurt",
    "fruta": "fruit", "frutas": "fruit", "manzana": "apple", "banana": "banana",
    "fresa": "strawberry", "mango": "mango", "pina": "pineapple", "papaya": "papaya",
    "sandia": "watermelon", "melon": "melon", "naranja": "orange", "limon": "lemon",
    "pollo": "chicken", "alitas": "chicken wings", "carne": "beef", "res": "beef",
    "bistec": "beef steak", "cerdo": "pork", "lechon": "roast pork", "chuletas": "pork chops",
    "costillas": "ribs", "salmon": "salmon", "pescado": "fish", "tilapia": "tilapia",
    "atun": "tuna", "camarones": "shrimp", "mariscos": "seafood", "arroz": "rice",
    "pasta": "pasta", "espaguetis": "spaghetti", "fideos": "noodles", "sopa": "soup",
    "crema": "cream soup", "guiso": "stew", "ensalada": "salad", "bowl": "bowl",
    "vegetales": "vegetables", "garbanzos": "chickpeas", "lentejas": "lentils",
    "frijoles": "beans", "pizza": "pizza", "pan": "bread", "queso": "cheese",
    "jamon": "ham", "papas": "potatoes", "tomate": "tomato", "ajo": "garlic",
    "cebolla": "onion", "chocolate": "chocolate", "vainilla": "vanilla", "cafe": "coffee",
    "batido": "milkshake", "smoothie": "smoothie", "jugo": "juice", "limonada": "lemonade",
    "asado": "roasted", "asada": "grilled", "horno": "baked", "plancha": "grilled",
    "frito": "fried", "frita": "fried", "fritos": "fried", "fritas": "fried",
    "empanizado": "breaded", "empanizados": "breaded", "rellenos": "stuffed",
    "verde": "green", "vegetariano": "vegetarian", "vegetariana": "vegetarian",
}

PROTEIN_GROUPS = {
    "chicken": {"chicken", "wing", "wings"},
    "beef": {"beef", "steak", "meatball", "burger"},
    "pork": {"pork", "ham", "bacon", "ribs", "sausage"},
    "shrimp": {"shrimp", "prawn", "prawns"},
    "fish": {"fish", "salmon", "tilapia", "tuna", "seafood", "crab", "mackerel"},
}

# When the recipe names a recognizable dish format, the photo title must name
# that format too.  This prevents ingredient-adjacent but incorrect matches
# such as a banana muffin for banana oatmeal or apple crumble for apple oats.
DISH_FORMS = {
    "oats": {"oat", "oats", "oatmeal"},
    "bowl": {"bowl"},
    "crepe": {"crepe", "crepes"},
    "pancake": {"pancake", "pancakes"},
    "waffle": {"waffle", "waffles"},
    "omelette": {"omelet", "omelette", "tortilla"},
    "pizza": {"pizza"},
    "bread": {"bread", "loaf", "roll", "rolls"},
    "rice": {"rice", "risotto", "paella"},
    "pasta": {"pasta", "spaghetti", "lasagna", "noodle", "noodles", "ravioli"},
    "soup": {"soup", "stew", "chowder", "broth"},
    "salad": {"salad"},
    "smoothie": {"smoothie"},
    "juice": {"juice", "lemonade"},
    "coffee": {"coffee", "espresso", "latte", "cappuccino", "mocha"},
}

STRICT_MODIFIERS = {
    "garlic", "onion", "lemon", "lime", "mustard", "honey", "teriyaki",
    "curry", "avocado", "chickpeas", "mushroom", "mushrooms", "pepperoni",
    "pineapple", "coconut", "strawberry", "caramel", "vanilla",
}


def _identity(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def recipe_photo_query(title: str) -> str:
    text = _identity(title)
    for source, target in sorted(PHRASES.items(), key=lambda row: len(row[0]), reverse=True):
        text = re.sub(rf"\b{re.escape(source)}\b", target, text)
    ignored = {"a", "al", "con", "de", "del", "la", "las", "los", "y"}
    translated = [WORDS.get(token, token) for token in text.split() if token not in ignored]
    return " ".join(translated + ["food"])


def _tokens(value: str) -> set[str]:
    ignored = {"a", "al", "and", "con", "de", "del", "dish", "food", "la", "the", "with", "y"}
    return {token for token in _identity(value).split() if len(token) > 2 and token not in ignored}


def _candidate_text(row: dict[str, Any]) -> str:
    tags = " ".join(str(tag.get("name") or "") for tag in row.get("tags") or [] if isinstance(tag, dict))
    return f"{row.get('title') or ''} {tags}"


def _conflicting_protein(query_tokens: set[str], candidate_tokens: set[str]) -> bool:
    requested = {name for name, tokens in PROTEIN_GROUPS.items() if query_tokens & tokens}
    found = {name for name, tokens in PROTEIN_GROUPS.items() if candidate_tokens & tokens}
    return bool(requested and found and requested.isdisjoint(found))


def _missing_dish_form(query_tokens: set[str], candidate_title_tokens: set[str]) -> bool:
    requested = [forms for forms in DISH_FORMS.values() if query_tokens & forms]
    return any(not (forms & candidate_title_tokens) for forms in requested)


def _missing_strict_modifier(query_tokens: set[str], candidate_title_tokens: set[str]) -> bool:
    return bool((query_tokens & STRICT_MODIFIERS) - candidate_title_tokens)


class RecipePhotoStore:
    def __init__(self, root: str | Path | None = None) -> None:
        configured = root or os.getenv("ROXY_HOME_RECIPE_PHOTO_DIR", "data/roxy_home_recipe_photos")
        self.root = Path(configured)
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "manifest.json"
        self._lock = threading.Lock()

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

    @staticmethod
    def _key(title: str) -> str:
        return hashlib.sha256(_identity(title).encode("utf-8")).hexdigest()[:24]

    def resolve(self, title: str) -> tuple[Path, dict[str, Any]] | None:
        key = self._key(title)
        with self._lock:
            manifest = self._manifest()
            saved = (manifest.get("photos") or {}).get(key)
            if isinstance(saved, dict):
                current = int(saved.get("resolver_version") or 0) == RESOLVER_VERSION
                if current and saved.get("missing") and time.time() - float(saved.get("checked_at") or 0) < 7 * 24 * 60 * 60:
                    return None
                path = self.root / str(saved.get("filename") or "")
                if current and path.is_file():
                    return path, saved

            translated_query = recipe_photo_query(title)
            searches = [title]
            if _identity(translated_query) != _identity(title):
                searches.append(translated_query)
            search_rows: list[tuple[dict[str, Any], str]] = []
            for query in searches:
                response = requests.get(
                    OPENVERSE_SEARCH_URL,
                    params={"q": query, "page_size": 20, "license_type": "commercial", "mature": "false"},
                    headers={"User-Agent": USER_AGENT},
                    timeout=12,
                )
                response.raise_for_status()
                search_rows.extend((row, query) for row in (response.json().get("results") or []) if isinstance(row, dict))
            used_ids = {str(row.get("openverse_id") or "") for row in (manifest.get("photos") or {}).values() if isinstance(row, dict)}
            ranked: list[tuple[int, dict[str, Any], str]] = []
            recipe_identity = _identity(title)
            seen_ids: set[str] = set()
            for row, query in search_rows:
                if not isinstance(row, dict) or not row.get("thumbnail") or str(row.get("id") or "") in used_ids:
                    continue
                row_id = str(row.get("id") or "")
                if row_id in seen_ids:
                    continue
                candidate_title = _identity(str(row.get("title") or ""))
                exact_name = len(recipe_identity) >= 5 and recipe_identity in candidate_title
                query_tokens = _tokens(query)
                candidate_title_tokens = _tokens(str(row.get("title") or ""))
                candidate_tokens = _tokens(_candidate_text(row))
                overlap = query_tokens & candidate_tokens
                title_overlap = query_tokens & candidate_title_tokens
                required_title_overlap = 2 if len(query_tokens) >= 2 else 1
                if not exact_name:
                    if len(title_overlap) < required_title_overlap:
                        continue
                    if (
                        _conflicting_protein(query_tokens, candidate_tokens)
                        or _missing_dish_form(query_tokens, candidate_title_tokens)
                        or _missing_strict_modifier(query_tokens, candidate_title_tokens)
                    ):
                        continue
                # A result rejected for the Spanish query may still be an exact
                # semantic match for the translated culinary query.  Deduplicate
                # only after it has passed validation.
                seen_ids.add(row_id)
                dimensions_ok = int(row.get("width") or 0) >= 500 and int(row.get("height") or 0) >= 400
                score = (200 if exact_name else 0) + len(overlap) * 10 + (4 if dimensions_ok else 0)
                ranked.append((score, row, query))
            if not ranked:
                manifest.setdefault("photos", {})[key] = {"missing": True, "checked_at": time.time(), "resolver_version": RESOLVER_VERSION}
                self._save_manifest(manifest)
                return None
            for _, selected, selected_query in sorted(ranked, key=lambda item: item[0], reverse=True):
                thumbnail = str(selected["thumbnail"])
                if urlparse(thumbnail).hostname not in ALLOWED_IMAGE_HOSTS:
                    continue
                try:
                    image = requests.get(thumbnail, headers={"User-Agent": USER_AGENT}, timeout=15)
                    image.raise_for_status()
                except requests.RequestException:
                    continue
                media_type = str(image.headers.get("content-type") or "").split(";", 1)[0]
                if media_type not in {"image/jpeg", "image/png", "image/webp"} or len(image.content) > 8_000_000:
                    continue
                extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[media_type]
                path = self.root / f"{key}{extension}"
                path.write_bytes(image.content)
                metadata = {
                    "filename": path.name,
                    "media_type": media_type,
                    "title": str(selected.get("title") or title),
                    "creator": str(selected.get("creator") or ""),
                    "license": str(selected.get("license") or ""),
                    "license_url": str(selected.get("license_url") or ""),
                    "source_url": str(selected.get("foreign_landing_url") or ""),
                    "openverse_id": str(selected.get("id") or ""),
                    "query": selected_query,
                    "resolver_version": RESOLVER_VERSION,
                }
                manifest.setdefault("photos", {})[key] = metadata
                self._save_manifest(manifest)
                return path, metadata
            manifest.setdefault("photos", {})[key] = {"missing": True, "checked_at": time.time(), "resolver_version": RESOLVER_VERSION}
            self._save_manifest(manifest)
            return None
