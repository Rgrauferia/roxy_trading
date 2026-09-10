"""Import openly licensed *candidates*, never automatically publish recipes.

Uses the official MediaWiki Action API, one request/second and maxlag. No AI,
provider key, household data or network call at module import. The generated
manifest is an editorial inbox, not the public catalogue. Wikimedia text is
CC BY-SA 4.0; linked media have independent rights and require visual review.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import quote, urlencode

import requests

ROOT = Path(__file__).resolve().parents[1]
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
POLICY_URL = "https://en.wikibooks.org/w/index.php?title=Wikibooks:Copyrights&oldid=4622060"
VERSION = "wikibooks-candidate-import-5"
MAX_SOURCE_CHARS = 250_000
MAX_MEDIA_REFERENCES = 128
MAX_EDITORIAL_BLOCKS = 64
MAX_FILE_NAME_BYTES = 255


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def top_split(text, delimiter="|"):
    """Split only at the top template level; nested links/templates keep pipes."""
    result, start, depth, links, i = [], 0, 0, 0, 0
    while i < len(text):
        pair = text[i:i + 2]
        if pair == "{{": depth += 1; i += 2; continue
        if pair == "}}": depth -= 1; i += 2; continue
        if pair == "[[": links += 1; i += 2; continue
        if pair == "]]": links -= 1; i += 2; continue
        if text[i] == delimiter and not depth and not links:
            result.append(text[start:i]); start = i + 1
        i += 1
    return result + [text[start:]]


def templates(text):
    """Return outer templates with offsets, without evaluating wiki code."""
    depth, start, i = 0, 0, 0
    while i < len(text) - 1:
        pair = text[i:i + 2]
        if pair == "{{":
            if not depth: start = i
            depth += 1; i += 2
        elif pair == "}}" and depth:
            depth -= 1; i += 2
            if not depth: yield start, i, text[start + 2:i - 2]
        else: i += 1


def plain(text, issues):
    """Conservative display conversion, preserving source measures verbatim."""
    for start, end, raw in reversed(list(templates(text))):
        parts = top_split(raw)
        name, args = parts[0].strip().casefold(), parts[1:]
        positional = [x.strip() for x in args if "=" not in x]
        if name in {"ing", "coc"} and positional:
            replacement = positional[-1]
        elif name in {"frac", "fraction"} and len(positional) in {1, 2, 3}:
            replacement = ({1: lambda: "1/" + positional[0],
                            2: lambda: "/".join(positional),
                            3: lambda: positional[0] + " " + "/".join(positional[1:])}[len(positional)])()
        elif name in {"convert", "cvt"} and len(positional) >= 2:
            # The first quantity/unit is original; do not invent a calculated conversion.
            if len(positional) > 2 and positional[1] in {"to", "-", "–", "and"}:
                issues.add("complex_conversion_template"); replacement = "{{" + raw + "}}"
            else: replacement = positional[0] + " " + positional[1]
        elif name in {"nowrap", "nobr", "small", "big"} and len(positional) == 1:
            replacement = positional[0]
        else:
            issues.add("unresolved_template"); replacement = "{{" + raw + "}}"
        text = text[:start] + replacement + text[end:]
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<ref\b[^>]*>.*?</ref>|<ref\b[^>]*/>", "", text, flags=re.S | re.I)
    def link(match):
        bits = match.group(1).split("|")
        if re.match(r"(?:image|file|archivo|imagen|category|categoría):", bits[0], re.I):
            return ""
        return bits[-1] if len(bits) > 1 else bits[0].split(":", 1)[-1]
    text = re.sub(r"\[\[([^\[\]]+)\]\]", link, text)
    text = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", text)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"'{2,5}", "", text)
    text = re.sub(r"[ \t]+", " ", html.unescape(text)).strip()
    if any(token in text for token in ("{{", "}}", "[[", "]]", "{|", "|}")):
        issues.add("unresolved_markup")
    return text


def fields(wiki):
    for _, _, raw in templates(wiki):
        parts = top_split(raw)
        if parts[0].strip().casefold() not in {"recipesummary", "artes culinarias/datos de receta"}:
            continue
        return {x.split("=", 1)[0].strip().casefold(): x.split("=", 1)[1].strip()
                for x in parts[1:] if "=" in x}
    return {}


def section(wiki, heading_pattern):
    parts = re.split(r"(?m)^==([^=\n].*?)==\s*$", wiki)
    return "\n".join(parts[i + 1] for i in range(1, len(parts) - 1, 2)
                     if re.search(heading_pattern, parts[i].strip(), re.I))


def _discovery_text(wiki):
    """Mask non-rendering examples/comments, retaining source character offsets.

    This is not an HTML renderer or sanitizer. Raw source is always untrusted;
    discovered context is for editorial inspection, never safe HTML or AI rules.
    """
    if len(wiki) > MAX_SOURCE_CHARS:
        raise ValueError("Source exceeds bounded parser size; no partial recipe produced")
    pattern = (r"<!--.*?(?:-->|\Z)|<nowiki\b[^>]*/\s*>|"
               r"<(nowiki|pre|code|source|syntaxhighlight|script|style)"
               r"\b(?![^>]*?/\s*>)[^>]*>.*?(?:</\1\s*>|\Z)")
    return re.sub(pattern, lambda m: re.sub(r"[^\n]", " ", m[0]), wiki, flags=re.I | re.S)


def _recipe_fields_with_spans(wiki, *, primary_only=False):
    """Yield fields without evaluating templates; spans point to original text."""
    masked = _discovery_text(wiki)
    for start, _, raw in templates(masked):
        parts = top_split(raw)
        if parts[0].strip().casefold() not in {"recipesummary", "artes culinarias/datos de receta"}:
            continue
        offset = len(parts[0]) + 1
        for part in parts[1:]:
            if "=" in part:
                key, _ = part.split("=", 1)
                left = start + 2 + offset + part.index("=") + 1
                right = start + 2 + offset + len(part)
                yield key.strip().casefold(), left, right
            offset += len(part) + 1
        if primary_only: return


def _original_section(wiki, heading_pattern):
    """Locate real section boundaries in masked text, copy unaltered source body."""
    headings = list(re.finditer(r"(?m)^==([^=\n].*?)==\s*$", _discovery_text(wiki)))
    return "\n".join(wiki[heading.end():headings[index + 1].start() if index + 1 < len(headings) else len(wiki)]
                     for index, heading in enumerate(headings)
                     if re.search(heading_pattern, heading[1].strip(), re.I))


def _media_name(raw):
    """Accept a file title, not a URL/path/API parameter. Never guess a filename."""
    name = html.unescape(raw).strip()
    if (not name or len(name.encode("utf-8")) > MAX_FILE_NAME_BYTES
            or name.startswith(".") or re.search(r"[/:\\#<>\[\]|{}%]", name)
            or any(unicodedata.category(char).startswith("C") for char in name)
            or not re.search(r"\.(?:jpe?g|png|webp|gif|svg|tiff?)$", name, re.I)):
        return None
    return name


def source_media_references(wiki, issues):
    """Find source-associated files in fields, body links and gallery lines.

    A reference does not prove its licence, media type, or exact recipe match.
    Invalid/over-limit input never becomes a provider request or silent success.
    """
    masked = _discovery_text(wiki)
    references = []
    fields_with_spans = list(_recipe_fields_with_spans(wiki))

    def add(raw_name, kind, start, end):
        name = _media_name(raw_name)
        if not name:
            issues.add("invalid_source_media_reference")
            return
        if len(references) >= MAX_MEDIA_REFERENCES:
            raise ValueError("Too many source media references; no partial recipe produced")
        references.append({"name": name, "kind": kind, "source_start": start,
                           "source_end": end, "source_wikitext": wiki[start:end],
                           "display_enabled": False, "exact_recipe_match": "not_reviewed"})

    link_pattern = r"\[\[\s*:?\s*(?:Image|File|Archivo|Imagen):([^\]|\r\n]+)(?:\|[^\n]*?)?\]\]"
    for match in re.finditer(link_pattern, masked, re.I):
        kind = "template_field" if any(a <= match.start() < b and key in {"image", "imagen"}
                                       for key, a, b in fields_with_spans) else "body_link"
        add(match[1], kind, match.start(), match.end())
    for key, start, end in fields_with_spans:
        value = masked[start:end].strip()
        if key in {"image", "imagen"} and value and "[[" not in value:
            # Bare MediaWiki file values are supported; external URLs are not.
            value = re.sub(r"^(?:Image|File|Archivo|Imagen):", "", value, flags=re.I)
            add(value, "template_field", start, end)
    for gallery in re.finditer(r"<gallery\b[^>]*>(.*?)</gallery\s*>", masked, re.I | re.S):
        offset = gallery.start(1)
        for line in gallery[1].splitlines(keepends=True):
            if line.strip():
                name = re.sub(r"^\s*(?:Image|File|Archivo|Imagen):", "", line.split("|", 1)[0], flags=re.I)
                add(name, "gallery_line", offset, offset + len(line))
            offset += len(line)
    references.sort(key=lambda ref: (ref["source_start"], ref["source_end"]))
    names, seen = [], set()
    for ref in references:
        key = ref["name"].replace("_", " ")
        key = key[:1].upper() + key[1:]
        if key not in seen:
            names.append(ref["name"]); seen.add(key)
    return names, references


def editorial_context_blocks(wiki, issues):
    """Keep notes and alternative sections separate from the main recipe steps.

    Every block is an exact source slice. Supplemental headings are deliberately
    broad: an unknown method must be reviewed, not silently lost or merged.
    """
    masked = _discovery_text(wiki)
    blocks = []

    def add(kind, label, start, end):
        if not wiki[start:end].strip(): return
        if len(blocks) >= MAX_EDITORIAL_BLOCKS:
            raise ValueError("Too many editorial context blocks; no partial recipe produced")
        blocks.append({"kind": kind, "label": label, "source_start": start,
                       "source_end": end, "source_wikitext": wiki[start:end],
                       "source_sha256": digest(wiki[start:end]), "untrusted_source": True,
                       "review_status": "not_reviewed"})

    context_keys = {"notes", "notas", "tips", "trucos", "variations", "variantes", "advertencias"}
    for key, start, end in _recipe_fields_with_spans(wiki):
        if key in context_keys:
            add("notes_field", key, start, end)
    recipe_templates_seen = 0
    for start, end, raw in templates(masked):
        name = top_split(raw)[0].strip()
        if name.casefold() in {"artes culinarias/" + key for key in context_keys}:
            add("notes_template", name, start, end)
        if name.casefold() in {"recipesummary", "artes culinarias/datos de receta"}:
            recipe_templates_seen += 1
            if recipe_templates_seen > 1:
                add("alternative_recipe_template", name, start, end)

    headings = list(re.finditer(r"(?m)^(={1,6})[ \t]*([^=\n].*?)[ \t]*\1[ \t]*$", masked))
    core = r"^(?:ingredients?|ingredientes?|procedure|preparation|directions|method|instructions|procedimiento|preparación|elaboración)$"
    for index, heading in enumerate(headings):
        title, depth = heading[2].strip(), len(heading[1])
        if re.fullmatch(core, title, re.I): continue
        # Already retained by its supplemental parent, including nested methods.
        if any(a["source_start"] <= heading.start() < a["source_end"] for a in blocks): continue
        end = next((h.start() for h in headings[index + 1:] if len(h[1]) <= depth), len(wiki))
        kind = ("alternative_section" if re.search(r"variaci|variant|alternativ|otro\s+m[eé]todo|another\s+method", title, re.I)
                else "notes_section" if re.search(r"not[ae]s?|tips|trucos|consejos|advertencias", title, re.I)
                else "supplemental_section")
        # A heading can contain markup: keep it plain text only, with review flags.
        add(kind, plain(title, issues), heading.start(), end)
    kept = []
    for block in sorted(blocks, key=lambda item: (item["source_start"], -item["source_end"])):
        if not any(old["source_start"] <= block["source_start"] and block["source_end"] <= old["source_end"]
                   for old in kept):
            kept.append(block)
    return kept


def source_lines(raw, marker, issues):
    lines = []
    for line in raw.splitlines():
        match = re.match(r"\s*([*#]+)\s*(.*)", line)
        if match and match[1].startswith(marker):
            if len(match[1]) > 1: issues.add("nested_instruction_or_ingredient_group")
            rendered = plain(match[2], issues)
            if rendered: lines.append(rendered)
        elif line.strip() and not re.match(r"\s*(?:<!--|\[\[(?:Category|Categoría):)", line, re.I):
            # Headings and narrative may contain important ordering/conditions.
            issues.add("non_list_content_in_recipe_section")
    return lines


def measured(line):
    """Presence check only: never claim nutritional precision or unit normalization."""
    # E.g. "1/4 de pasas": the source omitted what the fraction measures.
    # Do not silently interpret it as kg, cups, a package or a piece.
    if re.match(r"^(?:\d+\s*/\s*\d+|[¼½¾⅓⅔⅛⅜⅝⅞])\s+de\s+", line, re.I):
        return False
    return bool(re.match(r"^(?:\d|[¼½¾⅓⅔⅛⅜⅝⅞]|one\b|two\b|a\s+(?:pinch|dash|handful|sprig|few)\b|una?\b|pizca\b)", line, re.I)
                or re.search(r"\b(?:to taste|as needed|as required|al gusto|cantidad necesaria|optional|opcional)\b", line, re.I))


def editorial_flags(ingredients, steps, notes):
    """Triage signals, not food-safety clearance. Absence never means safe.

    Narrow deterministic rules identify some review priorities. They neither
    prescribe a repair nor normalize ingredient/temperature quantities.
    """
    flags = set()
    ingredient_text = " ".join(ingredients).casefold()
    procedure_text = " ".join(steps).casefold()
    combined = ingredient_text + " " + procedure_text + " " + plain(notes, set()).casefold()
    if re.search(r"\b(?:egg|eggs|yolk|yolks|huevo|huevos|yemas?)\b", ingredient_text):
        flags.add("egg_cooking_or_pasteurization_review")
    if re.search(r"\b(?:chicken|turkey|duck|poultry|pollo|gallina|pavo|pato)\b", ingredient_text):
        flags.add("poultry_cooking_and_storage_review")
    if re.search(r"\b(?:pork|beef|lamb|veal|cerdo|ternera|vacuno|cordero|carne)\b", ingredient_text):
        flags.add("meat_cooking_and_storage_review")
    if re.search(r"\b(?:germinar|germinación|sprout|sprouts|germinat|deshidrat|dehydrat)", combined):
        flags.add("sprouting_or_dehydration_review")
    if re.search(r"(?:room temperature|temperatura ambiente|overnight|toda la noche)", procedure_text):
        flags.add("time_temperature_storage_review")
    if re.search(r"(?:see notes?|véase|ver notas?)", combined) and not notes.strip():
        flags.add("referenced_notes_missing_from_extraction")
    if re.search(r"\S\s+#\w", procedure_text):
        flags.add("inline_instruction_marker")
    if re.search(r"(?:ignore (?:all |the )?(?:previous|system)|ignora (?:las )?instrucciones|system prompt|api[_ -]?key)", combined):
        flags.add("prompt_like_untrusted_content")
    # Only explicit animal ingredient tokens; this intentionally misses many
    # possible mismatches and may flag optional serving suggestions for review.
    for ingredient in ("chicken", "pork", "turkey", "pollo", "cerdo", "pavo", "salt", "water", "vanilla", "cinnamon",
                       "vainilla", "canela", "maicena", "caramelo", "azúcar", "sal"):
        if re.search(r"\b" + ingredient + r"\b", procedure_text) and not re.search(r"\b" + ingredient + r"\b", ingredient_text):
            flags.add("possible_unlisted_ingredient:" + ingredient)
    return sorted(flags)


def candidate(page, language, retrieved_at):
    revisions = page.get("revisions") or []
    if not revisions or page.get("redirect") is not None:
        return None
    revision = revisions[0]
    wiki = revision.get("slots", {}).get("main", {}).get("*", "")
    if not wiki or re.match(r"\s*#(?:redirect|redirección)", wiki, re.I): return None
    _discovery_text(wiki)  # Explicit size gate before parsing any source content.
    issues = set()
    info = {key: wiki[start:end].strip() for key, start, end in _recipe_fields_with_spans(wiki, primary_only=True)}
    ingredient_raw = info.get("ingredientes") or _original_section(wiki, r"^ingredients?$")
    step_raw = info.get("procedimiento") or _original_section(wiki, r"^(?:procedure|preparation|directions|method|instructions)$")
    ingredients = source_lines(ingredient_raw, "*", issues)
    steps = source_lines(step_raw, "#", issues)
    if len(ingredients) < 2: issues.add("missing_ingredient_list")
    if len(steps) < 2: issues.add("missing_ordered_steps")
    portions = plain(info.get("servings") or info.get("cantidad para") or info.get("comensales") or "", issues)
    if not portions or not re.search(r"\d", portions): issues.add("missing_original_yield")
    unmeasured = [i for i, line in enumerate(ingredients) if not measured(line)]
    if unmeasured: issues.add("ingredient_measure_review_required")
    if re.search(r"\{\{\s*(?:cookwork|stub|copyvio|delete|cleanup|incomplete|sinreferencias|destruir)\b", wiki, re.I):
        issues.add("source_maintenance_or_rights_warning")
    if re.search(r"\[\[Category:Duplicate recipes(?:\||\]\])", wiki, re.I):
        issues.add("source_marked_possible_duplicate")
    if re.search(r"\b(?:canning|canned in jars|preserving|raw (?:chicken|meat|egg|fish)|sous.vide|ferment|curar|curad[oa]s?|conservas?|sosa cáustica)\b", wiki, re.I):
        issues.add("special_food_safety_review_required")
    if re.search(r"\b(?:source|adapted|copyright|copied|reprinted|reproduc|fuente|autor)\b\s*[:=]", wiki, re.I):
        issues.add("additional_attribution_review_required")
    if re.search(r"<\s*(?:script|iframe|object|embed|svg)\b|\bon\w+\s*=", html.unescape(wiki), re.I):
        issues.add("active_markup_requires_review")
    title = page["title"]
    base = f"https://{language}.wikibooks.org"
    source_url = base + "/wiki/" + quote(title.replace(" ", "_"), safe=":/")
    categories = re.findall(r"\[\[(?:Category|Categoría):([^\]|]+)", wiki, re.I)
    images, media_references = source_media_references(wiki, issues)
    context_blocks = editorial_context_blocks(wiki, issues)
    notes_raw = "\n\n".join(block["source_wikitext"] for block in context_blocks)
    triage = editorial_flags(ingredients, steps, notes_raw)
    if context_blocks: triage.append("supplemental_context_requires_editorial_review")
    if any(block["kind"].startswith("alternative_") for block in context_blocks):
        triage.append("alternative_method_not_merged")
    status = "source_structure_complete_pending_editorial_review" if not issues else "needs_source_review"
    return {"id": f"wikibooks-{language}-{page['pageid']}", "provider": "wikibooks", "language": language,
            "title": title.rsplit("/", 1)[-1].removeprefix("Cookbook:"), "audience": "human",
            "source_title": title, "source_url": source_url,
            "source_revision_url": base + "/w/index.php?" + urlencode({"title": title, "oldid": revision["revid"]}),
            "source_history_url": base + "/w/index.php?" + urlencode({"title": title, "action": "history"}),
            "pageid": page["pageid"], "revid": revision["revid"], "source_modified_at": revision["timestamp"],
            "retrieved_at": retrieved_at, "source_sha256": digest(wiki), "original_wikitext": wiki,
            "ingredients_original": ingredients, "steps_original": steps,
            "notes_source_wikitext": notes_raw,
            "editorial_context_source": context_blocks,
            "editorial_context_scope": "Untrusted source slices for review only; not HTML, approved advice, or additional recipe steps.",
            "servings_original": portions, "time_original": plain(info.get("time") or info.get("tiempo") or "", set()),
            "origin_categories_original": categories, "source_image_names": images,
            "source_image_references": media_references,
            "image_status": "individual_rights_and_visual_review_required" if images else "source_image_not_identified",
            "rights": {"license": "CC BY-SA 4.0", "license_url": LICENSE_URL,
                       "attribution": f"Wikibooks contributors — {title}", "attribution_url": source_url,
                       "policy_url": POLICY_URL, "share_alike_required": True, "commercial_use_permitted": True,
                       "changes": "Mechanical display extraction only; source units and ordering preserved. No translation, new quantities, steps or media."},
            "content_fingerprint": digest(json.dumps([ingredients, steps], ensure_ascii=False)),
            "audit": {"parser_version": VERSION, "status": status, "issues": sorted(issues),
                      "unmeasured_ingredient_indexes": unmeasured, "culinary_review": "not_performed",
                      "editorial_triage_flags": sorted(set(triage)),
                      "triage_scope": "Heuristic review priorities only; not exhaustive and never safety clearance.",
                      "allergy_review": "not_performed", "visual_review": "not_performed",
                      "translation_review": "not_applicable_original_language", "publishable": False,
                      "can_cook_with_roxy": False, "can_add_to_shopping": False}}


class WikiClient:
    def __init__(self, language, cache_dir):
        if language not in {"es", "en"}: raise ValueError("Unsupported source language")
        self.url = f"https://{language}.wikibooks.org/w/api.php"
        self.language, self.cache_dir, self.last_request = language, cache_dir, 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "RoxyHomeRecipeReview/1.0 (https://github.com/Rgrauferia/roxy_trading; source audit)"

    def get(self, **params):
        params.update(format="json", maxlag="5")
        key = digest(self.url + json.dumps(params, sort_keys=True))
        path = self.cache_dir / (key + ".json")
        if path.exists(): return json.loads(path.read_text())
        for attempt in range(4):
            time.sleep(max(0, 1.0 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            response = self.session.get(self.url, params=params, timeout=40, allow_redirects=False)
            if 300 <= response.status_code < 400:
                raise RuntimeError("Official API redirected; review destination before continuing")
            if response.status_code in {429, 503}:
                time.sleep(min(30, 3 * 2 ** attempt)); continue
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                if data["error"].get("code") == "maxlag": time.sleep(5); continue
                raise RuntimeError(str(data["error"]))
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        raise RuntimeError("Provider busy; stopped without inventing content")

    def page_ids(self):
        params = ({"list": "categorymembers", "cmtitle": "Category:Recipes", "cmtype": "page", "cmlimit": 500}
                  if self.language == "en" else {"list": "allpages", "apprefix": "Artes culinarias/Recetas/", "aplimit": 500, "apfilterredir": "nonredirects"})
        result = []
        while True:
            data = self.get(action="query", **params)
            result += [p["pageid"] for p in data["query"]["categorymembers" if self.language == "en" else "allpages"]]
            if "continue" not in data: break
            params.update(data["continue"])
        # Deterministic distribution, not only the alphabet's first cuisines/dishes.
        return sorted(set(result), key=lambda n: digest(str(n)))


def audit_rows(rows):
    fingerprints, duplicates = {}, []
    for row in rows:
        fingerprint = row["content_fingerprint"]
        if fingerprint in fingerprints and row["ingredients_original"] and row["steps_original"]:
            row["audit"]["issues"] = sorted(set(row["audit"]["issues"] + ["duplicate_content"]))
            row["audit"]["status"] = "needs_source_review"
            row["audit"]["duplicate_of"] = fingerprints[fingerprint]
            duplicates.append(row["id"])
        else: fingerprints[fingerprint] = row["id"]
    return {"candidates": len(rows), "by_language": dict(Counter(r["language"] for r in rows)),
            "source_structure_complete": sum(not r["audit"]["issues"] for r in rows),
            "with_source_image_reference": sum(bool(r["source_image_names"]) for r in rows),
            "issues": dict(Counter(i for r in rows for i in r["audit"]["issues"])),
            "editorial_triage_flags": dict(Counter(i for r in rows for i in r["audit"].get("editorial_triage_flags", []))),
            "duplicate_ids": duplicates, "culinary_approved": 0, "publishable": 0,
            "scope": "Presence/integrity checks are not a recipe test, safety approval, photograph review, or error-free guarantee."}


def inspect_source_media(rows, cache_dir):
    """Fetch metadata only. Never grant visual approval or copy pixels."""
    client = WikiClient("en", cache_dir)
    client.url = "https://commons.wikimedia.org/w/api.php"
    raw_names = [name for row in rows for name in row["source_image_names"]]
    if any(not isinstance(name, str) or _media_name(name) != name for name in raw_names):
        raise ValueError("Invalid source file title; no metadata requests made")
    names = sorted({"File:" + name for name in raw_names})
    metadata = {}
    for start in range(0, len(names), 25):
        response = client.get(action="query", titles="|".join(names[start:start + 25]),
                              prop="imageinfo|revisions", iiprop="url|sha1|size|extmetadata",
                              rvprop="ids|timestamp", redirects=1)
        aliases = {v["from"]: v["to"] for key in ("normalized", "redirects") for v in response["query"].get(key, [])}
        for page in response["query"]["pages"].values():
            infos = page.get("imageinfo") or []
            if not infos: continue
            info = infos[0]
            ext = info.get("extmetadata", {})
            get = lambda key: plain(ext.get(key, {}).get("value", ""), set())
            license_name = get("LicenseShortName")
            allowed = bool(re.fullmatch(r"CC (?:BY|BY-SA) (?:[1-4]\.0|2\.5)|CC0|Public domain", license_name))
            if get("NonFree").casefold() == "true": allowed = False
            media = {"source_title": page["title"], "source_description_url": info.get("descriptionurl"),
                     "source_file_url": info.get("url"), "source_file_sha1": info.get("sha1"),
                     "source_description_revision": (page.get("revisions") or [{}])[0].get("revid"),
                     "source_description_modified_at": (page.get("revisions") or [{}])[0].get("timestamp"),
                     "author_original": get("Artist"), "license_original": license_name,
                     "license_url_original": get("LicenseUrl"), "usage_terms_original": get("UsageTerms"),
                     "description_original": get("ImageDescription"), "credit_original": get("Credit"),
                     "attribution_original": get("Attribution"), "restrictions_original": get("Restrictions"),
                     "width": info.get("width"), "height": info.get("height"),
                     "open_license_metadata_present": allowed,
                     "visual_review": "not_performed", "display_enabled": False,
                     "scope": "Metadata from file embedded by recipe source; no visual match, photograph type or third-party rights adjudication."}
            metadata[page["title"]] = media
        for alias, canonical in aliases.items():
            if canonical in metadata: metadata[alias] = metadata[canonical]
    for row in rows:
        row["source_media_candidates"] = [metadata.get("File:" + name.strip(), {"source_title": "File:" + name,
                                           "display_enabled": False, "status": "metadata_unavailable"})
                                           for name in row["source_image_names"]]
    image_owners = {}
    for row in rows:
        for media in row["source_media_candidates"]:
            if media.get("source_file_sha1"):
                image_owners.setdefault(media["source_file_sha1"], []).append(row["id"])
    for row in rows:
        for media in row["source_media_candidates"]:
            owners = image_owners.get(media.get("source_file_sha1"), [])
            if len(owners) > 1:
                media["shared_source_image_recipe_ids"] = owners
                row["audit"]["editorial_triage_flags"] = sorted(set(row["audit"]["editorial_triage_flags"]
                                                                   + ["same_source_image_used_for_multiple_recipes"]))
    return {"source_file_names": len(names), "records_with_metadata": sum(bool(r.get("source_media_candidates")) for r in rows),
            "open_license_metadata": sum(any(m.get("open_license_metadata_present") for m in r.get("source_media_candidates", [])) for r in rows),
            "shared_source_file_hashes": sum(len(owners) > 1 for owners in image_owners.values()),
            "visually_reviewed": 0, "display_enabled": 0, "images_downloaded": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--target", type=int, default=500, help="Source-structure-complete target; never a publication target")
    parser.add_argument("--max-pages", type=int, default=5200)
    parser.add_argument("--languages", nargs="+", choices=["es", "en"], default=["es", "en"])
    parser.add_argument("--retain-complete-only", action="store_true", help="Keep other pages as a compact rejection index")
    parser.add_argument("--inspect-media", action="store_true", help="Read independent Commons metadata; never visual approval")
    parser.add_argument("--replace-generated", action="store_true", help="Mechanically regenerate only an importer-owned candidate manifest")
    args = parser.parse_args()
    if args.output.resolve() == ROOT / "data/home_open_recipes.json": raise SystemExit("Public catalogue is never an importer target")
    if args.output.exists():
        previous = json.loads(args.output.read_text()) if args.replace_generated else {}
        if not (previous.get("product") == "roxy-home" and previous.get("public_enabled") is False
                and previous.get("kind") == "editorial_candidates_not_runtime_catalogue"):
            raise SystemExit("Refusing to overwrite non-importer data; choose a new output")
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(timezone.utc).isoformat()
    rows, seen, complete = [], 0, 0
    for language in args.languages:
        client = WikiClient(language, args.cache_dir)
        ids = client.page_ids()
        print(json.dumps({"language": language, "discovered": len(ids)}), flush=True)
        for start in range(0, len(ids), 50):
            if seen >= args.max_pages or complete >= args.target: break
            data = client.get(action="query", prop="revisions", rvprop="ids|timestamp|content", rvslots="main", pageids="|".join(map(str, ids[start:start + 50])))
            for page in data["query"]["pages"].values():
                seen += 1
                row = candidate(page, language, retrieved)
                if row:
                    rows.append(row)
                    complete += not row["audit"]["issues"]
            if start % 250 == 0: print(json.dumps({"inspected": seen, "structure_complete_before_dedup": complete}), flush=True)
        if seen >= args.max_pages or complete >= args.target: break
    summary = audit_rows(rows)
    rejected = []
    if args.retain_complete_only:
        rejected = [{key: row[key] for key in ("id", "source_revision_url", "source_sha256", "language", "title")}
                    | {"issues": row["audit"]["issues"]} for row in rows if row["audit"]["issues"]]
        rows = [row for row in rows if not row["audit"]["issues"]]
    media_summary = inspect_source_media(rows, args.cache_dir) if args.inspect_media else {"inspected": False}
    manifest = {"schema_version": 1, "product": "roxy-home", "kind": "editorial_candidates_not_runtime_catalogue",
                "generated_at": retrieved, "parser_version": VERSION, "license": "CC BY-SA 4.0", "license_url": LICENSE_URL,
                "license_scope": "Wikibooks recipe text and this derived recipe compilation; media separately licensed. Not a relicensing of Roxy software.",
                "public_enabled": False, "target_requested": args.target, "target_structure_reached": summary["source_structure_complete"] >= args.target,
                "summary_all_inspected": summary, "summary_retained": audit_rows(rows),
                "media_summary": media_summary, "rejected_index": rejected, "recipes": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__": main()
