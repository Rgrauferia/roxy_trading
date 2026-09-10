"""Versioned, openly licensed originals. Never normalize through AI recipes.

The checked-in content is a small editorial selection, not an automatic import of
all wiki pages. Plain text, source measures, ordering and attribution are kept.
Reading/filtering does not contact a provider or touch household data.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import unicodedata

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "home_open_recipes.json"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"


def _key(value):
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()


def _publishable(row):
    """Source integrity and a license never override an editorial hold.

    Legacy editorial selections may omit these optional flags. When present,
    only a real boolean True is affirmative: strings, null and numbers must not
    accidentally promote a candidate. Shopping eligibility is independent.
    """
    if not isinstance(row, dict):
        return False
    audit = row.get("audit", {})
    if not isinstance(audit, dict):
        return False
    for scope in (row, audit):
        for flag in ("publishable", "cook_allowed"):
            if flag in scope and scope[flag] is not True:
                return False
    if row.get("language") != "en" or row.get("audience") != "human":
        return False
    if not all(isinstance(row.get(key), str) and row[key].strip()
               for key in ("id", "title", "source_revision_url", "source_url", "original_wikitext")):
        return False
    if not isinstance(row.get("revid"), int) or isinstance(row["revid"], bool) or row["revid"] <= 0:
        return False
    servings = row.get("servings")
    if not isinstance(servings, (int, float)) or isinstance(servings, bool) or not math.isfinite(servings) or servings <= 0:
        return False
    for field in ("ingredients_original", "steps_original"):
        values = row.get(field)
        if not isinstance(values, list) or not values or any(not isinstance(value, str) or not value.strip() for value in values):
            return False
    rights = row.get("rights")
    if not isinstance(rights, dict) or not isinstance(rights.get("attribution"), str) or not rights["attribution"].strip():
        return False
    if rights.get("license") != "CC BY-SA 4.0" or rights.get("license_url") != LICENSE_URL:
        return False
    if not all(rights.get(key) is True for key in ("attribution_required", "share_alike_required", "commercial_use_permitted")):
        return False
    return hashlib.sha256(row["original_wikitext"].encode("utf-8")).hexdigest() == row.get("source_sha256")


@lru_cache(maxsize=1)
def _catalog():
    # Missing/corrupt licensed content must not become generated replacement text.
    try:
        if CATALOG_PATH.stat().st_size > 1_000_000:
            return []
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        rows = data["recipes"]
        if not isinstance(rows, list) or len(rows) > 200:
            return []
        return [row for row in rows if _publishable(row)]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def open_recipe_catalog(query="", cuisine="", *, limit=24):
    rows = deepcopy(_catalog())
    cuisines = sorted({str(row.get("cuisine") or "") for row in rows} - {""})
    selected = []
    for row in rows:
        if cuisine and _key(row.get("cuisine")) != _key(cuisine):
            continue
        text = " ".join([str(row.get("title") or ""), str(row.get("cuisine") or ""), *row.get("ingredients_original", [])])
        if query and _key(query) not in _key(text):
            continue
        # Runtime admission respects editorial holds as well as presence,
        # integrity and license. A readable original is not a tested Roxy guide.
        row.pop("original_wikitext", None)  # Evidence stays in the source manifest, not a UI markup blob.
        selected.append({**row, "attribution": row["rights"]["attribution"], "provider": "wikibooks", "audience": "human",
                         "can_read_original": True, "can_add_to_shopping": False,
                         "license_url": LICENSE_URL,
                         "review_scope": "Original con ingredientes, raciones y pasos. No es una adaptación a alergias ni una receta ensayada por Roxy."})
    return {"provider": "wikibooks", "status": "READY" if rows else "UNAVAILABLE",
            "language": "en", "recipes": selected[:max(1, min(24, int(limit)))],
            "count": min(len(selected), max(1, min(24, int(limit)))), "total": len(rows),
            "cuisines": cuisines, "license": "CC BY-SA 4.0", "license_url": LICENSE_URL,
            "cost": "free_local_catalog", "live_provider_request": False,
            "attribution": "Wikibooks contributors · original y revisión enlazados en cada receta"}
