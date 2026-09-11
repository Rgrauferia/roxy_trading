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
import re
import unicodedata
from urllib.parse import parse_qs, urlsplit

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "home_open_recipes.json"
TRANSLATIONS_PATH = CATALOG_PATH.with_name("home_open_recipes_es.json")
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
MAX_CATALOG_ROWS = 1_000
MAX_CATALOG_BYTES = 8 * 1024 * 1024
MAX_TRANSLATION_BYTES = 4 * 1024 * 1024
MAX_ROW_BYTES = 64 * 1024
MAX_LIST_ITEMS = 256
MAX_LINE_CHARS = 4_096
MAX_PAGE_SIZE = 24
MAX_CURSOR_LENGTH = 129
_INDEX_STATE = None


class OpenRecipeCursorError(ValueError):
    """A bookmark is invalid for this exact query and page size."""


class OpenRecipeVersionChanged(ValueError):
    """The client must restart its view, not combine different editions."""


class OpenRecipeNotFound(LookupError):
    """Unknown and editorially held identities have the same outcome."""


def _bounded_row(row):
    if not isinstance(row, dict):
        return False
    try:
        return len(json.dumps(row, ensure_ascii=False, allow_nan=False,
                              separators=(",", ":")).encode("utf-8")) <= MAX_ROW_BYTES
    except (ValueError, TypeError, RecursionError, OverflowError):
        return False


def _text_list(values, *, required=False):
    return (isinstance(values, list) and len(values) <= MAX_LIST_ITEMS
            and (bool(values) or not required)
            and all(isinstance(value, str) and value.strip() and len(value) <= MAX_LINE_CHARS
                    for value in values))


def _reject_json_constant(_value):
    raise ValueError("non_finite_json")


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _read_json(path, byte_limit):
    # The bounded read also covers a file growing between stat and read.
    with path.open("rb") as stream:
        raw = stream.read(byte_limit + 1)
    if len(raw) > byte_limit:
        raise ValueError("catalog_size_limit")
    return json.loads(raw.decode("utf-8"), parse_constant=_reject_json_constant,
                      object_pairs_hook=_unique_json_object)


def _key(value):
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().casefold()


def _positive_servings(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _valid_servings(row):
    """Keep a source range as a range, never select an endpoint or midpoint.

    Only an explicit, simple numeric range is supported. Textual yields, units,
    alternatives and unknown yields still need editorial representation. The
    structured bounds must agree with the unchanged source label; a range is not
    permission to scale ingredients or claim one exact nutritional portion.
    """
    scalar = row.get("servings")
    if "servings_range" not in row:
        return _positive_servings(scalar)
    bounds = row["servings_range"]
    if scalar is not None or not isinstance(bounds, dict) or set(bounds) != {"min", "max"}:
        return False
    low, high = bounds["min"], bounds["max"]
    if not all(_positive_servings(value) for value in (low, high)) or low >= high:
        return False
    original = row.get("servings_original")
    if not isinstance(original, str) or len(original) > 64:
        return False
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*[–—-]\s*([0-9]+(?:\.[0-9]+)?)\s*", original)
    return bool(match and float(match[1]) == low and float(match[2]) == high)


def _publishable(row):
    """Source integrity and a license never override an editorial hold.

    Legacy editorial selections may omit these optional flags. When present,
    only a real boolean True is affirmative: strings, null and numbers must not
    accidentally promote a candidate. Shopping eligibility is independent.
    """
    if not _bounded_row(row):
        return False
    audit = row.get("audit", {})
    if not isinstance(audit, dict):
        return False
    for scope in (row, audit):
        for flag in ("publishable", "cook_allowed"):
            if flag in scope and scope[flag] is not True:
                return False
    if not isinstance(row.get("language"), str) or row["language"] not in {"en", "es"} or row.get("audience") != "human":
        return False
    if not all(isinstance(row.get(key), str) and row[key].strip()
               for key in ("id", "title", "source_revision_url", "source_url", "original_wikitext")):
        return False
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", row["id"]) or len(row["title"]) > 300:
        return False
    # Relabelling an original is not a translation or a new-language admission.
    try:
        for field in ("source_url", "source_revision_url"):
            source = urlsplit(row[field])
            if (source.scheme != "https" or source.hostname != f'{row["language"]}.wikibooks.org'
                    or source.username or source.password or source.port):
                return False
    except ValueError:
        return False
    for field, maximum in (("servings_original", 64), ("time_original", 300), ("cuisine", 100)):
        value = row.get(field, "")
        if not isinstance(value, str) or len(value) > maximum or (field == "servings_original" and not value.strip()):
            return False
    if not isinstance(row.get("revid"), int) or isinstance(row["revid"], bool) or row["revid"] <= 0:
        return False
    revision = urlsplit(row["source_revision_url"])
    if revision.path != "/w/index.php" or parse_qs(revision.query).get("oldid") != [str(row["revid"])]:
        return False
    if "servings" not in row or not _valid_servings(row):
        return False
    for field in ("ingredients_original", "steps_original"):
        if not _text_list(row.get(field), required=True):
            return False
    for field in ("equipment_original", "notes_original"):
        if not _text_list(row.get(field, [])):
            return False
    rights = row.get("rights")
    if not isinstance(rights, dict) or not isinstance(rights.get("attribution"), str) or not rights["attribution"].strip():
        return False
    if rights.get("license") != "CC BY-SA 4.0" or rights.get("license_url") != LICENSE_URL:
        return False
    if not all(rights.get(key) is True for key in ("attribution_required", "share_alike_required", "commercial_use_permitted")):
        return False
    for key in ("attribution", "changes"):
        if key in rights and (not isinstance(rights[key], str) or len(rights[key]) > MAX_LINE_CHARS):
            return False
    if not _text_list(rights.get("additional_attribution_urls", [])):
        return False
    if "attribution_url" in rights and not isinstance(rights["attribution_url"], str):
        return False
    return hashlib.sha256(row["original_wikitext"].encode("utf-8")).hexdigest() == row.get("source_sha256")


@lru_cache(maxsize=1)
def _catalog():
    # Missing/corrupt licensed content must not become generated replacement text.
    try:
        data = _read_json(CATALOG_PATH, MAX_CATALOG_BYTES)
        rows = data["recipes"]
        if not isinstance(rows, list) or len(rows) > MAX_CATALOG_ROWS:
            return []
        identities = [row.get("id") for row in rows if isinstance(row, dict)
                      and isinstance(row.get("id"), str) and row["id"]]
        if len(set(identities)) != len(identities):
            return []  # An ambiguous ID, even on a held row, must never choose a winner.
        return [row for row in rows if _publishable(row)]
    except (OSError, ValueError, KeyError, TypeError, RecursionError, OverflowError):
        return []


@lru_cache(maxsize=1)
def _translations():
    """Editorial translations never promote a held or changed source revision."""
    try:
        data = _read_json(TRANSLATIONS_PATH, MAX_TRANSLATION_BYTES)
        rows = data["translations"]
        if type(data.get("schema_version")) is not int or data["schema_version"] != 1 or not isinstance(rows, list) or len(rows) > MAX_CATALOG_ROWS:
            return []
        _canonical(rows)  # Reject unencodable JSON strings before version hashing.
        return rows
    except (OSError, ValueError, KeyError, TypeError, RecursionError, OverflowError):
        return []


def _translation(row, *, candidates=None):
    if row.get("language") != "en":
        return None  # A Spanish original is not its own invented translation.
    matches = (candidates if candidates is not None else
               [value for value in _translations() if isinstance(value, dict) and value.get("source_id") == row["id"]])
    if len(matches) != 1:
        return None
    value = matches[0]
    if not _bounded_row(value):
        return None
    if (value.get("language") != "es" or type(value.get("source_revid")) is not int or value["source_revid"] != row["revid"]
            or value.get("source_sha256") != row["source_sha256"]
            or value.get("license") != "CC BY-SA 4.0" or value.get("license_url") != LICENSE_URL):
        return None
    for field, maximum in (("title", 300), ("attribution", MAX_LINE_CHARS), ("changes", MAX_LINE_CHARS)):
        if not isinstance(value.get(field), str) or not value[field].strip() or len(value[field]) > maximum:
            return None
    if not isinstance(value.get("time"), str) or len(value["time"]) > 300:
        return None
    if not _text_list(value.get("editorial_notes", [])):
        return None
    for field, source in (("ingredients", "ingredients_original"), ("steps", "steps_original"),
                          ("equipment", "equipment_original"), ("notes", "notes_original")):
        translated = value.get(field)
        if not _text_list(translated) or len(translated) != len(row.get(source, [])):
            return None
    # Explicit projection: a translation cannot introduce shopping/cooking grants
    # or replace the source's quantities, license, identity or source evidence.
    result = deepcopy({key: value[key] for key in (
        "source_id", "source_revid", "source_sha256", "language", "title", "ingredients",
        "steps", "equipment", "notes", "time", "attribution", "license", "license_url", "changes")})
    result["editorial_notes"] = deepcopy(value.get("editorial_notes", []))
    return result


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def _catalog_index():
    """One immutable-by-convention index per cached pair of local manifests.

    Identity comparison respects existing cache_clear/test replacement hooks;
    public projections never return these cached dictionaries. No per-request
    copying or translation scans across the complete catalog are necessary.
    """
    global _INDEX_STATE
    rows, translations = _catalog(), _translations()
    previous = _INDEX_STATE
    if previous is not None and previous[0] is rows and previous[1] is translations:
        return previous[2]
    grouped = {}
    for value in translations:
        if isinstance(value, dict) and isinstance(value.get("source_id"), str):
            grouped.setdefault(value["source_id"], []).append(value)
    entries = []
    for row in rows:
        translated = _translation(row, candidates=grouped.get(row["id"], []))
        text = " ".join([row["title"], row.get("cuisine", ""), *row["ingredients_original"]])
        if translated:
            text += " " + " ".join([translated["title"], *translated["ingredients"]])
        entries.append({"row": row, "translation": translated, "search": _key(text),
                        "cuisine_key": _key(row.get("cuisine")), "order": (_key(row["title"]), row["id"])})
    digest = hashlib.sha256(b"roxy-open-recipes-page-v2\0")
    # Include all source metadata and translations, including a newly invalid
    # translation. A client must never combine two different reader editions.
    digest.update(_canonical(rows))
    digest.update(b"\0")
    digest.update(_canonical(translations))
    index = {"entries": entries, "ordered": sorted(entries, key=lambda entry: entry["order"]),
             "by_id": {entry["row"]["id"]: entry for entry in entries},
             "version": digest.hexdigest(),
             "cuisines": sorted({entry["row"].get("cuisine", "") for entry in entries} - {""}),
             "languages": sorted({entry["row"]["language"] for entry in entries}
                                 | ({"es"} if any(entry["translation"] for entry in entries) else set()))}
    _INDEX_STATE = (rows, translations, index)
    return index


_DETAIL_FIELDS = frozenset({
    "id", "provider_id", "title", "language", "cuisine", "servings", "servings_original",
    "servings_range", "time_original", "ingredients_original", "steps_original",
    "equipment_original", "notes_original", "source_url", "source_revision_url", "source_history_url",
    "source_title", "pageid", "revid", "source_modified_at", "retrieved_on", "source_sha256",
    "image_url", "image_source_url", "image_source_revision", "image_author", "image_license",
    "image_license_url", "image_commercial_use_permitted", "image_dimensions", "image_mime",
    "image_sha1", "image_changes", "photo_scope", "image_status",
})
_RIGHTS_FIELDS = frozenset({"license", "license_url", "attribution", "attribution_url", "changes",
                          "attribution_required", "share_alike_required", "commercial_use_permitted",
                          "additional_attribution_urls"})


def _valid_source_photo(row):
    """A text license cannot supply the separate photo's rights or provenance."""
    if (row.get("image_status") != "source_linked_individual_license_checked"
            or row.get("image_commercial_use_permitted") is not True
            or row.get("image_mime") != "image/jpeg"
            or not isinstance(row.get("image_author"), str) or not row["image_author"].strip()):
        return False
    try:
        image, source, license = [urlsplit(row.get(key, "")) for key in
                                  ("image_url", "image_source_url", "image_license_url")]
        if any(url.scheme != "https" or url.username or url.password or url.port or url.query or url.fragment
               for url in (image, source, license)):
            return False
        return bool(image.hostname == "upload.wikimedia.org"
                    and re.fullmatch(r"/wikipedia/commons/[a-f0-9]/[a-f0-9]{2}/[^/]+\.jpe?g", image.path, re.I)
                    and source.hostname == "commons.wikimedia.org" and source.path.startswith("/wiki/File:")
                    and license.hostname == "creativecommons.org"
                    and re.fullmatch(r"/licenses/by-sa/(?:2\.0|2\.5|3\.0|4\.0)/", license.path)
                    and row.get("image_license") == f"CC BY-SA {license.path.split('/')[3]}")
    except (ValueError, TypeError, AttributeError):
        return False


def _public_recipe(entry, *, legacy=False):
    row = entry["row"]
    if legacy:
        result = {key: value for key, value in row.items() if key != "original_wikitext"}
    else:
        result = {key: value for key, value in row.items() if key in _DETAIL_FIELDS}
        result["rights"] = {key: value for key, value in row["rights"].items() if key in _RIGHTS_FIELDS}
        # The only public object-valued metadata has a fixed inner schema.
        for key in tuple(result):
            if isinstance(result[key], (dict, list)) and key not in {
                    "rights", "servings_range", "image_dimensions", "ingredients_original",
                    "steps_original", "equipment_original", "notes_original"}:
                result.pop(key)
        dimensions = row.get("image_dimensions")
        result["image_dimensions"] = ({key: dimensions[key] for key in ("width", "height")}
                                      if isinstance(dimensions, dict)
                                      and all(type(dimensions.get(key)) is int and dimensions[key] > 0
                                              for key in ("width", "height")) else {})
        if not _valid_source_photo(row):
            for key in tuple(result):
                if key.startswith("image_"):
                    result.pop(key)
            result.update(image_url="", image_status="unavailable", image_commercial_use_permitted=False)
        # These are product capabilities, not assertions imported from a source.
        result.update(automatic_scaling_verified=False, dietary_claims_imported=False)
    for field in ("equipment_original", "notes_original"):
        result.setdefault(field, [])
    result.update(translation=entry["translation"], attribution=row["rights"]["attribution"],
                  provider="wikibooks", audience="human", can_read_original=True,
                  can_cook_with_roxy=False, can_add_to_shopping=False, license_url=LICENSE_URL,
                  review_scope="Original con ingredientes, raciones y pasos. No es una adaptación a alergias ni una receta ensayada por Roxy.")
    return deepcopy(result)


def _catalog_metadata(index):
    return {"provider": "wikibooks", "status": "READY" if index["entries"] else "UNAVAILABLE",
            "cuisines": list(index["cuisines"]), "license": "CC BY-SA 4.0", "license_url": LICENSE_URL,
            "cost": "free_local_catalog", "live_provider_request": False,
            "attribution": "Wikibooks contributors · original y revisión enlazados en cada receta"}


def open_recipe_catalog(query="", cuisine="", *, limit=24):
    """Compatibility route: the old bounded full-detail response and file order."""
    index = _catalog_index()
    query_key, cuisine_key = _key(query), _key(cuisine)
    page = max(1, min(MAX_PAGE_SIZE, int(limit)))
    selected = [entry for entry in index["entries"]
                if (not cuisine_key or entry["cuisine_key"] == cuisine_key)
                and (not query_key or query_key in entry["search"])][:page]
    return {**_catalog_metadata(index), "language": "en",
            "recipes": [_public_recipe(entry, legacy=True) for entry in selected],
            "count": len(selected), "total": len(index["entries"])}


def _filter_text(value, name):
    if not isinstance(value, str) or len(value) > 100 or any(ord(char) < 32 for char in value):
        raise ValueError(f"invalid_{name}")
    return _key(value.strip())


def _bookmark(version, filters, last_id):
    """Opaque, deterministic navigation token, not an authentication token.

    A token is accepted only if it matches a real page boundary for this
    filtered, ordered, versioned selection. No secret or extra server session
    is required, and changing the token cannot expose an unadmitted detail.
    """
    digest = hashlib.sha256(_canonical([version, filters, last_id])).hexdigest()
    return f"{version}.{digest}"


def _summary(entry):
    row, translated = entry["row"], entry["translation"]
    result = {key: row[key] for key in ("id", "title", "language", "servings", "servings_original",
                                      "revid", "source_sha256")}
    result.update(title_es=translated["title"] if translated else None,
                  available_languages=sorted({row["language"]} | ({"es"} if translated else set())),
                  cuisine=row.get("cuisine", ""), time_original=row.get("time_original", ""),
                  time_es=translated["time"] if translated else None,
                  ingredient_count=len(row["ingredients_original"]), step_count=len(row["steps_original"]),
                  image_status="source_linked_individual_license_checked" if _valid_source_photo(row) else "unavailable",
                  has_source_photo=_valid_source_photo(row),
                  can_read_original=True, can_cook_with_roxy=False, can_add_to_shopping=False)
    if "servings_range" in row:
        result["servings_range"] = row["servings_range"]
    return deepcopy(result)


def open_recipe_summaries(query="", cuisine="", *, language="all", limit=24, cursor=""):
    query_key, cuisine_key = _filter_text(query, "query"), _filter_text(cuisine, "cuisine")
    if not isinstance(language, str) or language not in {"all", "en", "es"}:
        raise ValueError("invalid_language")
    if type(limit) is not int or not 1 <= limit <= MAX_PAGE_SIZE:
        raise ValueError("invalid_limit")
    if not isinstance(cursor, str) or len(cursor) > MAX_CURSOR_LENGTH:
        raise OpenRecipeCursorError("invalid_cursor")
    if cursor and not re.fullmatch(r"[a-f0-9]{64}\.[a-f0-9]{64}", cursor):
        raise OpenRecipeCursorError("invalid_cursor")
    index = _catalog_index()
    if cursor and cursor.split(".", 1)[0] != index["version"]:
        raise OpenRecipeVersionChanged("catalog_version_changed")
    filters = [query_key, cuisine_key, language, limit]
    selected = [entry for entry in index["ordered"]
                if (not query_key or query_key in entry["search"])
                and (not cuisine_key or cuisine_key == entry["cuisine_key"])
                and (language == "all" or entry["row"]["language"] == language
                     or (language == "es" and entry["translation"] is not None))]
    start = 0
    if cursor:
        for boundary in range(limit, len(selected), limit):
            if cursor == _bookmark(index["version"], filters, selected[boundary - 1]["row"]["id"]):
                start = boundary
                break
        else:
            raise OpenRecipeCursorError("invalid_cursor_for_selection")
    page = selected[start:start + limit]
    next_cursor = (_bookmark(index["version"], filters, page[-1]["row"]["id"])
                   if start + len(page) < len(selected) else None)
    return {**_catalog_metadata(index), "schema_version": 2, "catalog_version": index["version"],
            "recipes": [_summary(entry) for entry in page], "count": len(page),
            "matched_total": len(selected), "catalog_total": len(index["entries"]),
            "next_cursor": next_cursor, "languages": list(index["languages"])}


def open_recipe_detail(recipe_id, *, catalog_version=""):
    if not isinstance(recipe_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", recipe_id):
        raise OpenRecipeNotFound("recipe_not_found")
    if not isinstance(catalog_version, str) or (catalog_version and not re.fullmatch(r"[a-f0-9]{64}", catalog_version)):
        raise ValueError("invalid_catalog_version")
    index = _catalog_index()
    if catalog_version and catalog_version != index["version"]:
        raise OpenRecipeVersionChanged("catalog_version_changed")
    entry = index["by_id"].get(recipe_id)
    if entry is None:
        raise OpenRecipeNotFound("recipe_not_found")
    return {"schema_version": 2, "catalog_version": index["version"], "recipe": _public_recipe(entry)}
