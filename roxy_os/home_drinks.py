"""A small, checked-in bilingual selection of MIT-licensed Open Drinks recipes.

No provider calls, recipe generation, household writes or invented servings.
The source and translation are bound to a pinned original, not a mutable feed.
Structural checks protect the editorial selection; they are not kitchen tests.
"""
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data/home_open_drinks.json"
REVISION = "f446f0e9356b9b43155d207b4f7c5214d9da91ab"
SOURCE_BASE = f"https://github.com/alfg/opendrinks/blob/{REVISION}/"
IMAGE_BASE = f"https://raw.githubusercontent.com/alfg/opendrinks/{REVISION}/src/assets/recipes/"
CATEGORIES = ("coffee_tea", "juice", "smoothie", "mocktail", "cocktail")
SPIRIT_BASES = ("gin", "vodka", "rum", "agave", "whisky", "wine", "other")
# Navigation labels from literal ingredient names, not ABV or a health assessment.
# Never infer a spirit from a drink title, translated prose, steps or the member.
_BASE_PATTERNS = (
    ("gin", r"\bgin\b"),
    ("vodka", r"\bvodka\b"),
    ("rum", r"\brum\b"),
    ("agave", r"\b(?:tequila|mezcal)\b"),
    ("whisky", r"\b(?:whisky|whiskey|scotch|bourbon(?![ -]+vanilla\b))\b"),
    ("wine", r"\b(?:wine|champagne|prosecco|cava|cr[eé]mant|vermouth|sherry|port|dubonnet|lillet)\b"),
)
_NON_BASE = re.compile(r"\b(?:non[ -]?alcoholic|alcohol[ -]?free|extract|essence|syrup|vinegar)\b", re.I)
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 200


class DrinkCatalogUnavailable(ValueError):
    """A damaged release must not silently become an empty or generated menu."""


class DrinkNotFound(ValueError):
    """An unknown ID never resolves to a similar or generated recipe."""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("non_finite_number")


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non_finite_number")
    return result


def _json(raw):
    return json.loads(raw, object_pairs_hook=_object, parse_constant=_constant, parse_float=_float)


def _text(value, maximum=4096):
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= maximum
            and not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value))


def _lines(values, *, optional=False):
    return (isinstance(values, list) and (bool(values) or optional)
            and len(values) <= 48 and all(_text(line) for line in values))


def _validate(row):
    if not isinstance(row, dict):
        return False
    if not _text(row.get("id"), 100) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", row["id"]):
        return False
    if row.get("category") not in CATEGORIES or type(row.get("alcoholic")) is not bool:
        return False
    if row["alcoholic"] != (row["category"] == "cocktail"):
        return False
    for field in ("title", "title_es", "original_name", "contributor", "image_credit"):
        if not _text(row.get(field), 300):
            return False
    for field in ("ingredients", "steps", "ingredients_es", "steps_es"):
        if not _lines(row.get(field)):
            return False
    if not _lines(row.get("notes_es", []), optional=True):
        return False
    if len(row["ingredients"]) != len(row["ingredients_es"]) or len(row["steps"]) != len(row["steps_es"]):
        return False
    raw = row.get("raw_source")
    if not _text(raw, 32 * 1024) or hashlib.sha256(raw.encode("utf-8")).hexdigest() != row.get("source_sha256"):
        return False
    original = _json(raw)
    if not isinstance(original, dict) or original.get("source"):
        return False  # Third-party source grants have not been established for this selection.
    if re.search(r"https?://|www\.", raw, re.I):
        return False
    if not (row["title"] == row["original_name"] == original.get("name") and row["steps"] == original.get("directions")):
        return False
    if row["contributor"] != original.get("github"):
        return False
    ingredients = original.get("ingredients")
    if not isinstance(ingredients, list) or not 1 <= len(ingredients) <= 48 or any(not isinstance(part, dict) for part in ingredients):
        return False
    lines = []
    for part in ingredients:
        values = [part.get(key) for key in ("quantity", "measure", "ingredient")]
        if any(value is not None and (isinstance(value, bool) or not isinstance(value, (str, int, float))) for value in values):
            return False
        lines.append(" ".join(str(value).strip() for value in values if value is not None and str(value).strip()))
    if row["ingredients"] != lines:
        return False
    image = original.get("image")
    if not isinstance(image, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*\.(?:jpg|jpeg|png|webp)", image):
        return False
    return (row.get("source_url") == SOURCE_BASE + f"src/recipes/{row['id']}.json"
            and row.get("image_url") == IMAGE_BASE + image)


@lru_cache(maxsize=1)
def _catalog():
    try:
        with CATALOG_PATH.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("too_large")
        data = _json(raw.decode("utf-8"))
        if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
            raise ValueError("wrong_version")
        if data.get("source") != {"name": "Open Drinks", "revision": REVISION,
                                  "license": "MIT", "license_url": SOURCE_BASE + "LICENSE"}:
            raise ValueError("source_mismatch")
        rows = data.get("drinks")
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS or not all(_validate(row) for row in rows):
            raise ValueError("invalid_selection")
        for field in ("id", "title", "title_es", "image_url", "source_sha256"):
            if len({row[field].casefold() for row in rows}) != len(rows):
                raise ValueError("duplicate_selection")
        return rows
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise DrinkCatalogUnavailable("drink_catalog_unavailable") from None


def _metadata():
    return {"audience": "human", "can_scale": False, "can_add_to_shopping": False,
            "source": {"name": "Open Drinks", "revision": REVISION, "license": "MIT",
                       "license_url": "/assets/open-drinks-license.txt"}}


def _spirit_bases(row):
    if not row["alcoholic"]:
        return []
    original = _json(row["raw_source"])
    names = [str(part.get("ingredient", "")).casefold() for part in original["ingredients"]]
    names = [name for name in names if not _NON_BASE.search(name)]
    matches = [key for key, pattern in _BASE_PATTERNS
               if any(re.search(pattern, name) for name in names)]
    return matches or ["other"]


def drink_catalog(*, include_spirit_bases=False):
    """Only lightweight cards; ingredients and instructions load on demand."""
    rows = _catalog()
    fields = ("id", "title", "title_es", "category", "alcoholic", "image_url", "source_sha256")
    summaries = [{**{key: row[key] for key in fields},
                  "ingredient_count": len(row["ingredients"]), "step_count": len(row["steps"]),
                  **({"spirit_bases": _spirit_bases(row)} if include_spirit_bases else {})}
                 for row in rows]
    counts = Counter(row["category"] for row in rows)
    return {"drinks": summaries, "total": len(rows),
            "counts": {key: counts[key] for key in CATEGORIES}, **_metadata()}


def drink_detail(drink_id, *, include_spirit_bases=False):
    """Exact, immutable selection; never fetch, invent, or silently truncate."""
    if not isinstance(drink_id, str) or len(drink_id) > 100 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", drink_id):
        raise DrinkNotFound("drink_not_found")
    row = next((row for row in _catalog() if row["id"] == drink_id), None)
    if row is None:
        raise DrinkNotFound("drink_not_found")
    # Provenance stays in the source distribution; the browser receives bounded,
    # inert recipe text, never the raw third-party JSON or private profile data.
    fields = ("id", "title", "title_es", "original_name", "category", "alcoholic",
              "ingredients", "steps", "ingredients_es", "steps_es", "notes_es",
              "source_url", "contributor", "image_url", "image_credit", "source_sha256")
    public_row = {key: deepcopy(row[key]) for key in fields if key in row}
    if include_spirit_bases:
        public_row["spirit_bases"] = _spirit_bases(row)
    return {"drink": public_row, **_metadata()}


def drink_catalog_legacy():
    """Keep already-open version 189 tabs usable until they load the new shell.

    That client accepts at most 60 complete rows. New clients use all summaries,
    not this compatibility view. This is public editorial content, not user data.
    """
    rows = _catalog()
    selected = rows[:60]
    counts = Counter(row["category"] for row in selected)
    return {"drinks": [drink_detail(row["id"])["drink"] for row in selected],
            "total": len(selected), "available_total": len(rows),
            "counts": {key: counts[key] for key in CATEGORIES}, **_metadata()}
