"""A fixed, attributed educational selection, never a training approval source.

The JSON data retains its per-resource Creative Commons licences separately
from application code. No runtime provider calls or member data are involved.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "home_fitness_catalog.json"
CATALOG_VERSION = "fitness-open-catalog-20260910-v2"
LICENSES = {
    "CC-BY-SA-3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "CC-BY-SA-4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
}
SOURCE_LICENSE_IDS = {"CC-BY-SA-3.0": 1, "CC-BY-SA-4.0": 2, "CC0-1.0": 3}
STATUS = "education_only_professional_review_pending"
REVIEW_STATUS = "pending_professional_review"


class CatalogValidationError(ValueError):
    """A catalogue resource lacks sufficient bounded, safe source metadata."""


class _ParagraphParser(HTMLParser):
    """Extract source prose without rendering provider markup or active content."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.current = []
        self.blocked = 0

    def flush(self):
        value = " ".join("".join(self.current).split())
        if value:
            self.parts.append(value)
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "iframe", "object", "template", "svg"}:
            self.blocked += 1
        if not self.blocked and tag in {"p", "li", "br", "div", "h1", "h2", "h3"}:
            self.flush()

    def handle_endtag(self, tag):
        if tag in {"script", "style", "iframe", "object", "template", "svg"}:
            self.blocked = max(0, self.blocked - 1)
        elif not self.blocked and tag in {"p", "li", "div", "h1", "h2", "h3"}:
            self.flush()

    def handle_data(self, data):
        if not self.blocked:
            self.current.append(data)


def plain_instruction_paragraphs(source_html: str) -> list[str]:
    """For bounded offline ingestion; retain original words and paragraph order."""
    if not isinstance(source_html, str) or len(source_html) > 24000:
        raise CatalogValidationError("Invalid source instruction length")
    parser = _ParagraphParser()
    parser.feed(source_html)
    parser.close()
    parser.flush()
    for value in parser.parts:
        _plain(value, 12000)
    return parser.parts


def _plain(value, maximum=1000):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or "<" in value or ">" in value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise CatalogValidationError("Invalid plain text")
    return value


def _positive_id(value):
    if type(value) is not int or value <= 0:
        raise CatalogValidationError("Invalid source identifier")
    return value


def _checked_on(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise CatalogValidationError("Missing verification date")
    date.fromisoformat(value)
    return value


def _license(attribution):
    if not isinstance(attribution, dict):
        raise CatalogValidationError("Missing attribution")
    identifier = attribution.get("license")
    if identifier not in LICENSES or attribution.get("license_url") != LICENSES[identifier]:
        raise CatalogValidationError("Unreviewed resource licence")
    expected_source_id = SOURCE_LICENSE_IDS[identifier]
    if attribution.get("source_license_id") != expected_source_id:
        raise CatalogValidationError("Mismatched source licence identifier")
    return identifier


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise CatalogValidationError("Missing source digest")
    return value


def safe_catalog_image_url(value: str) -> bool:
    """Exact HTTPS provider origin, image directory and raster extension only."""
    if (not isinstance(value, str) or len(value) > 800 or value != value.strip()
            or any(ord(char) < 33 or ord(char) == 127 for char in value)):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (parsed.scheme == "https" and parsed.netloc == "wger.de"
            and not parsed.query and not parsed.fragment
            and bool(re.fullmatch(r"/media/exercise-images/[1-9][0-9]*/[A-Za-z0-9_-]+\.(?:png|jpg|jpeg|webp)", parsed.path)))


def _validate_entry(entry):
    if not isinstance(entry, dict):
        raise CatalogValidationError("Invalid catalogue entry")
    source_id = _positive_id(entry.get("source_exercise_id"))
    if entry.get("id") != f"wger-{source_id}":
        raise CatalogValidationError("Mismatched exercise identifier")
    if (entry.get("clinical_approval") is not False
            or entry.get("can_activate_training") is not False
            or entry.get("review_status") != REVIEW_STATUS):
        raise CatalogValidationError("Educational data cannot grant approval")
    if entry.get("language") not in {"en", "es"}:
        raise CatalogValidationError("Unreviewed language")
    _plain(entry.get("name"), 240)
    _plain(entry.get("category"), 100)
    _positive_id(entry.get("source_translation_id"))
    _checked_on(entry.get("checked_on"))
    if entry.get("source_api_url") != f"https://wger.de/api/v2/exerciseinfo/{source_id}/":
        raise CatalogValidationError("Mismatched source endpoint")
    if entry.get("source_url") != f"https://wger.de/en/exercise/{source_id}/view":
        raise CatalogValidationError("Mismatched source page")
    instructions = entry.get("instructions")
    if not isinstance(instructions, list) or not 1 <= len(instructions) <= 40:
        raise CatalogValidationError("Missing original instructions")
    for paragraph in instructions:
        _plain(paragraph, 12000)
    digest = sha256("\n\n".join(instructions).encode("utf-8")).hexdigest()
    if digest != _sha(entry.get("instructions_sha256")):
        raise CatalogValidationError("Instruction snapshot changed")
    _sha(entry.get("source_description_sha256"))
    attribution = entry.get("attribution")
    _license(attribution)
    authors = attribution.get("authors")
    if not isinstance(authors, list) or not 1 <= len(authors) <= 25:
        raise CatalogValidationError("Missing text authors")
    for author in authors:
        _plain(author, 3500)
    _plain(attribution.get("changes"), 1000)
    base = entry.get("base_attribution")
    _license(base)
    _plain(base.get("author"), 3500)
    _plain(entry.get("source_last_update"), 100)
    equipment = entry.get("equipment")
    if not isinstance(equipment, list) or len(equipment) > 15:
        raise CatalogValidationError("Invalid source equipment")
    for item in equipment:
        _positive_id(item.get("id"))
        _plain(item.get("name"), 100)
    images = entry.get("images")
    if not isinstance(images, list) or not 1 <= len(images) <= 4:
        raise CatalogValidationError("Missing reviewed visual")
    seen = set()
    for media in images:
        media_id = _positive_id(media.get("source_id"))
        if media_id in seen or media.get("source_exercise_id") != source_id:
            raise CatalogValidationError("Mismatched or duplicate media")
        seen.add(media_id)
        if not safe_catalog_image_url(media.get("url")):
            raise CatalogValidationError("Unapproved image origin or path")
        if media.get("source_url") != f"https://wger.de/api/v2/exerciseimage/{media_id}/":
            raise CatalogValidationError("Mismatched media source")
        if (media.get("kind") != "illustration" or media.get("author") != "Everkinetic"
                or media.get("visual_review") != "exact_variant_verified"
                or media.get("is_ai_generated") is not False):
            raise CatalogValidationError("Unreviewed media content")
        _license(media)
        _checked_on(media.get("checked_on"))
        _sha(media.get("sha256"))
        _plain(media.get("changes"), 1000)
    # Explicit response projection: provider extensions, raw HTML, arbitrary
    # author URLs and claims such as "active" never enter the UI contract.
    public = {key: deepcopy(entry[key]) for key in (
        "id", "name", "language", "category", "equipment", "instructions",
        "source_url", "source_api_url", "source_exercise_id", "source_translation_id",
        "source_last_update", "checked_on", "instructions_sha256", "source_description_sha256",
        "review_status", "clinical_approval", "can_activate_training",
    )}
    public["metadata_language"] = "en"
    public["equipment"] = [{"id": item["id"], "name": item["name"]} for item in equipment]
    public["equipment_metadata_complete"] = bool(equipment)
    public["attribution"] = {key: deepcopy(attribution[key]) for key in (
        "authors", "license", "license_url", "source_license_id", "changes",
    )}
    public["base_attribution"] = {key: deepcopy(base[key]) for key in (
        "author", "license", "license_url", "source_license_id",
    )}
    public["images"] = [{key: deepcopy(media[key]) for key in (
        "source_id", "source_exercise_id", "url", "source_url", "kind", "author",
        "license", "license_url", "source_license_id", "checked_on", "visual_review",
        "is_ai_generated", "sha256", "changes",
    )} for media in images]
    return public


def fitness_catalog() -> dict:
    """Read the fixed selection; corrupt/unreviewed content fails closed."""
    result = {
        "version": CATALOG_VERSION,
        "checked_on": "2026-09-10",
        "status": STATUS,
        "clinical_approval": False,
        "can_activate_training": False,
        "review_status": REVIEW_STATUS,
        "notice": "Catálogo educativo de fuentes originales. Revisión profesional pendiente; no es un plan personal ni autoriza entrenar.",
        "media_notice": "Ilustraciones originales; no son fotografías ni una evaluación de tu técnica.",
        "count": 0,
        "entries": [],
    }
    try:
        if CATALOG_PATH.stat().st_size > 500000:
            raise CatalogValidationError("Catalogue exceeds reviewed bounds")
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        if data.get("version") != CATALOG_VERSION or data.get("product") != "roxy-home":
            raise CatalogValidationError("Unreviewed catalogue version")
        entries = data.get("entries")
        if not isinstance(entries, list) or not 1 <= len(entries) <= 32:
            raise CatalogValidationError("Invalid catalogue coverage")
        validated = [_validate_entry(entry) for entry in entries]
        if len({entry["id"] for entry in validated}) != len(validated):
            raise CatalogValidationError("Duplicate catalogue identifiers")
        license_notice = _plain(data["data_license_notice"], 1500)
        result["entries"] = validated
        result["count"] = len(validated)
        result["data_license_notice"] = license_notice
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        result["status"] = "catalogue_unavailable"
    return result


def fitness_catalog_entry(exercise_id: str) -> dict | None:
    """Exact fixed identifier lookup; no network/path construction from input."""
    if not isinstance(exercise_id, str) or not re.fullmatch(r"wger-[1-9][0-9]{0,7}", exercise_id):
        return None
    return next((entry for entry in fitness_catalog()["entries"] if entry["id"] == exercise_id), None)
