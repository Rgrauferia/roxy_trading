from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from roxy_os.home_food import HomeFoodStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _identity(value: Any) -> str:
    compact = " ".join(str(value or "").strip().split())
    normalized = unicodedata.normalize("NFKD", compact)
    return " ".join(normalized.encode("ascii", "ignore").decode("ascii").lower().split())


_QUERY_STOPWORDS = {
    "a", "al", "algo", "como", "con", "cocinar", "crea", "crear", "dame", "de", "del",
    "el", "en", "ensename", "facil", "hacer", "hazme", "la", "las", "los", "me", "para",
    "prepara", "preparame", "preparar", "quiero", "quisiera", "receta", "una", "un", "unos",
    "persona", "personas", "porcion", "porciones", "rinde",
}


def _query_tokens(prompt: Any) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", _identity(prompt))
        if token not in _QUERY_STOPWORDS and not token.isdigit()
    ]


def canonical_recipe_query(prompt: Any, recipe_type: str = "general") -> str:
    """Hash a normalized request so the library never stores the user's words."""

    tokens = _query_tokens(prompt)
    semantic = " ".join(sorted(set(tokens))) or _identity(prompt)
    material = f"{_identity(recipe_type) or 'general'}|{semantic}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _recipe_fingerprint(recipe: dict[str, Any]) -> str:
    servings = float(recipe.get("servings") or 1)
    normalized_ingredients = []
    for row in recipe.get("ingredients") or []:
        normalized_ingredients.append(
            {
                "name": _identity(row.get("name")),
                "quantity_per_serving": round(float(row.get("quantity") or 0) / servings, 6),
                "unit": _identity(row.get("unit")),
                "notes": _identity(row.get("notes")),
            }
        )
    canonical = {
        "title": _identity(recipe.get("title")),
        "kind": _identity(recipe.get("kind")),
        "drink_type": _identity(recipe.get("drink_type")),
        "ingredients": normalized_ingredients,
        "steps": [_identity(step) for step in recipe.get("steps") or []],
    }
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def requested_servings(prompt: Any) -> float | None:
    match = re.search(
        r"\b(?:para|rinde(?:\s+para)?)\s+(\d{1,2}(?:[.,]\d+)?)\s*(?:personas?|porciones?)?\b",
        _identity(prompt),
    )
    if not match:
        return None
    value = float(match.group(1).replace(",", "."))
    return value if 0 < value <= 100 else None


def scale_recipe_payload(recipe: dict[str, Any], servings: float | None) -> dict[str, Any]:
    if servings is None:
        return deepcopy(recipe)
    current = float(recipe.get("servings") or 1)
    factor = servings / current
    scaled = deepcopy(recipe)
    scaled["servings"] = servings
    scaled["ingredients"] = [
        {**row, "quantity": round(float(row.get("quantity") or 0) * factor, 4)}
        for row in recipe.get("ingredients") or []
    ]
    return scaled


def recipe_is_compatible(recipe: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    profile = snapshot.get("profile") or {}
    ingredients = " ".join(_identity(row.get("name")) for row in recipe.get("ingredients") or [])
    # If a cached base visibly contains an allergy or a disliked ingredient,
    # let Roxy create a private-compatible variation instead of reusing it.
    blocked = list(profile.get("allergies") or []) + list(profile.get("dislikes") or [])
    return not any(_identity(value) and _identity(value) in ingredients for value in blocked)


def _relevant(recipe: dict[str, Any], prompt: Any) -> bool:
    tokens = _query_tokens(prompt)
    if not tokens:
        return False
    searchable = _identity(
        f"{recipe.get('title') or ''} {recipe.get('description') or ''} "
        + " ".join(str(row.get("name") or "") for row in recipe.get("ingredients") or [])
    )
    return any(len(token) >= 3 and token in searchable for token in tokens)


class HomeRecipeLibraryStore:
    """Global canonical recipe database with no household or user records."""

    def __init__(self, path: str | Path = "data/roxy_home_recipe_library.sqlite") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS recipes (
                    id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL UNIQUE,
                    recipe_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    reuse_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT
                );
                CREATE TABLE IF NOT EXISTS recipe_queries (
                    query_key TEXT PRIMARY KEY,
                    recipe_id TEXT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_recipe_queries_recipe ON recipe_queries(recipe_id);
                """
            )

    @staticmethod
    def _canonical_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
        normalized = HomeFoodStore._normalize_recipe(recipe)
        # Sources and safety notes are content metadata, but household photos,
        # favorites and notes never enter this method or database.
        return normalized

    def find(
        self,
        prompt: Any,
        snapshot: dict[str, Any],
        *,
        recipe_type: str = "general",
    ) -> dict[str, Any] | None:
        key = canonical_recipe_query(prompt, recipe_type)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT recipes.* FROM recipe_queries
                JOIN recipes ON recipes.id = recipe_queries.recipe_id
                WHERE recipe_queries.query_key = ?
                """,
                (key,),
            ).fetchone()
            if row is None:
                return None
            recipe = json.loads(row["recipe_json"])
            if not recipe_is_compatible(recipe, snapshot) or not _relevant(recipe, prompt):
                return None
            connection.execute(
                "UPDATE recipes SET reuse_count = reuse_count + 1, last_used_at = ? WHERE id = ?",
                (_now_iso(), row["id"]),
            )
        result = scale_recipe_payload(recipe, requested_servings(prompt))
        result["generation_source"] = "shared_recipe_library"
        result["shared_recipe_id"] = row["id"]
        return result

    def publish(
        self,
        prompt: Any,
        recipe: dict[str, Any],
        *,
        source: str,
        recipe_type: str = "general",
    ) -> dict[str, Any]:
        canonical = self._canonical_recipe(recipe)
        fingerprint = _recipe_fingerprint(canonical)
        query_key = canonical_recipe_query(prompt, recipe_type)
        if not _relevant(canonical, prompt):
            return {"id": "", "fingerprint": fingerprint, "source": source, "published": False}
        timestamp = _now_iso()
        encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True)
        with self._connect() as connection:
            row = connection.execute("SELECT id FROM recipes WHERE fingerprint = ?", (fingerprint,)).fetchone()
            recipe_id = str(row["id"]) if row else uuid4().hex
            if row is None:
                connection.execute(
                    "INSERT INTO recipes(id,fingerprint,recipe_json,source,created_at) VALUES(?,?,?,?,?)",
                    (recipe_id, fingerprint, encoded, str(source or "unknown")[:64], timestamp),
                )
            connection.execute(
                "INSERT OR REPLACE INTO recipe_queries(query_key,recipe_id) VALUES(?,?)",
                (query_key, recipe_id),
            )
        return {"id": recipe_id, "fingerprint": fingerprint, "source": source, "published": True}

    def summary(self) -> dict[str, int]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS recipes, COALESCE(SUM(reuse_count),0) AS reuses FROM recipes"
            ).fetchone()
        return {"recipes": int(row["recipes"]), "reuses": int(row["reuses"])}
