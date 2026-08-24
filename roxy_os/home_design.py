"""Private room-renovation projects for Roxy Home.

The module deliberately keeps personal room photos separate from the shared
recipe library.  Photos and generated proposals are only exposed through an
authenticated API endpoint owned by the same household member.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


ROOM_TYPES = {"living_room", "bedroom", "dining_room", "kitchen", "bathroom", "office", "patio", "other"}
STYLES = {"warm_modern", "minimal", "natural", "classic", "bohemian", "industrial", "coastal", "surprise_me"}
IMAGE_TYPES = {
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/webp": (b"RIFF", ".webp"),
}
MAX_IMAGE_BYTES = 6_000_000

ROOM_LABELS = {
    "living_room": "sala",
    "bedroom": "dormitorio",
    "dining_room": "comedor",
    "kitchen": "cocina",
    "bathroom": "baño",
    "office": "oficina en casa",
    "patio": "patio",
    "other": "espacio",
}
STYLE_LABELS = {
    "warm_modern": "moderno cálido",
    "minimal": "minimalista",
    "natural": "natural",
    "classic": "clásico",
    "bohemian": "bohemio",
    "industrial": "industrial",
    "coastal": "costero",
    "surprise_me": "armonioso y funcional",
}

ROOM_PRODUCTS = {
    "living_room": ["alfombra de sala", "lámpara de pie", "cojines decorativos", "mesa auxiliar"],
    "bedroom": ["juego de ropa de cama", "lámparas de noche", "cortinas", "alfombra de dormitorio"],
    "dining_room": ["lámpara colgante de comedor", "camino de mesa", "arte de pared", "centro de mesa"],
    "kitchen": ["lámpara para cocina", "organizadores de encimera", "alfombra lavable", "taburetes de cocina"],
    "bathroom": ["cortina de baño", "juego de toallas", "organizador de baño", "alfombra de baño"],
    "office": ["lámpara de escritorio", "organizador de escritorio", "estantería", "alfombra de oficina"],
    "patio": ["luces para patio", "cojines de exterior", "macetas", "mesa auxiliar de exterior"],
    "other": ["lámpara decorativa", "alfombra", "organizador", "arte de pared"],
}

BUDGET_TIERS = {
    "economy": {"label": "Económica", "multiplier": 0.65},
    "balanced": {"label": "Equilibrada", "multiplier": 1.0},
    "complete": {"label": "Completa", "multiplier": 1.35},
}

ROOM_OBSERVATIONS = {
    "living_room": ["Define una zona de conversación clara.", "Aprovecha la iluminación en capas y deja libres las rutas de paso."],
    "bedroom": ["Prioriza descanso, circulación y almacenamiento accesible.", "Usa luz cálida junto a la cama y evita saturar las superficies."],
    "dining_room": ["Centra la composición alrededor de la mesa.", "Deja espacio suficiente para retirar las sillas con comodidad."],
    "kitchen": ["Mantén despejadas las superficies de trabajo.", "Agrupa almacenamiento, preparación y limpieza en zonas prácticas."],
    "bathroom": ["Favorece materiales resistentes a la humedad.", "Añade almacenamiento cerrado sin bloquear la ventilación."],
    "office": ["Controla reflejos y coloca luz de tarea regulable.", "Mantén cables y almacenamiento fuera de la superficie principal."],
    "patio": ["Elige piezas aptas para exterior y fáciles de mantener.", "Organiza sombra, iluminación y circulación antes de decorar."],
    "other": ["Conserva una circulación clara.", "Introduce primero función e iluminación y después decoración."],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _list(values: Any, *, limit: int = 20) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for raw in values[:limit]:
        value = _text(raw, 120)
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _decode_image(data_url: str) -> tuple[bytes, str, str]:
    match = re.fullmatch(r"data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\s]+)", str(data_url or ""))
    if not match:
        raise ValueError("Selecciona una foto JPEG, PNG o WebP válida.")
    media_type = match.group(1)
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("La foto no pudo leerse.") from exc
    signature, suffix = IMAGE_TYPES[media_type]
    valid = raw.startswith(signature) and (media_type != "image/webp" or raw[8:12] == b"WEBP")
    if not valid or not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("La foto no es válida o supera 6 MB.")
    return raw, media_type, suffix


def _product_plan(room_type: str, style: str, budget: float, tier: str = "balanced") -> list[dict[str, Any]]:
    names = ROOM_PRODUCTS.get(room_type, ROOM_PRODUCTS["other"])
    style_label = STYLE_LABELS.get(style, STYLE_LABELS["surprise_me"])
    tier = tier if tier in BUDGET_TIERS else "balanced"
    available = round(max(0, budget) * float(BUDGET_TIERS[tier]["multiplier"]), 2)
    shares = (0.38, 0.27, 0.20, 0.15)
    return [
        {
            "id": f"product-{index + 1}",
            "name": f"{name} estilo {style_label}",
            "quantity": 1,
            "unit": "unidad",
            "category": "HOUSEHOLD",
            "budget_target": round(available * shares[index], 2),
            "tier": tier,
            "selected": True,
        }
        for index, name in enumerate(names)
    ]


def _budget_tiers(room_type: str, style: str, budget: float) -> list[dict[str, Any]]:
    return [
        {
            "id": tier,
            "label": values["label"],
            "budget": round(max(0, budget) * float(values["multiplier"]), 2),
            "products": _product_plan(room_type, style, budget, tier),
        }
        for tier, values in BUDGET_TIERS.items()
    ]


def _initial_analysis(room_type: str, priorities: list[str], keep_items: list[str]) -> dict[str, Any]:
    opportunities = list(ROOM_OBSERVATIONS.get(room_type, ROOM_OBSERVATIONS["other"]))
    if priorities:
        opportunities.insert(0, f"La prioridad principal será: {priorities[0]}.")
    return {
        "status": "READY_LOCAL",
        "summary": "Roxy preparó una lectura inicial con tus objetivos. Puedes pedir un análisis visual más detallado.",
        "strengths": [f"Conservar: {', '.join(keep_items)}."] if keep_items else ["La propuesta conservará la arquitectura y los elementos fijos del espacio."],
        "opportunities": opportunities,
        "questions": ["Confirma las medidas principales para validar que los productos caben."] if not priorities else [],
    }


def _fit_assessment(values: Any) -> dict[str, Any]:
    constraints = values if isinstance(values, dict) else {}
    clean = {key: round(float(constraints.get(key) or 0), 2) for key in ("wall_width", "passage_width", "max_depth")}
    missing = [key for key, value in clean.items() if value <= 0]
    labels = {"wall_width": "ancho disponible de pared", "passage_width": "ancho del paso o puerta", "max_depth": "profundidad máxima"}
    if missing:
        return {
            "status": "NEEDS_MEASUREMENTS",
            "label": "Faltan medidas",
            "message": "Añade " + ", ".join(labels[key] for key in missing) + ". Roxy no confirmará compatibilidad sin esos datos.",
            "constraints": clean,
        }
    return {
        "status": "READY_TO_COMPARE",
        "label": "Medidas preparadas",
        "message": "Roxy usará estos límites para la propuesta y los comparará con las dimensiones publicadas por cada comercio. La compatibilidad final depende de la ficha real del producto.",
        "constraints": clean,
    }


class HomeDesignStore:
    def __init__(self, path: str | Path = "data/roxy_home_design.json", image_root: str | Path = "data/roxy_home_design") -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.image_root = Path(image_root)

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"schema_version": 1, "projects": {}}

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self._empty()
        if not isinstance(value, dict):
            return self._empty()
        value.setdefault("projects", {})
        return value

    def _write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp_name, 0o600)
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
                value = self._read()
                result = callback(value)
                self._write(value)
                return result
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def projects(self, owner_key: str) -> list[dict[str, Any]]:
        rows = self._read().get("projects", {}).get(owner_key, {})
        return sorted((deepcopy(row) for row in rows.values()), key=lambda row: row.get("updated_at", ""), reverse=True)

    def project(self, owner_key: str, project_id: str) -> dict[str, Any]:
        row = self._read().get("projects", {}).get(owner_key, {}).get(project_id)
        if not isinstance(row, dict):
            raise KeyError(project_id)
        return deepcopy(row)

    def create(self, owner_key: str, household_user: str, values: dict[str, Any]) -> dict[str, Any]:
        room_type = _text(values.get("room_type"), 32)
        style = _text(values.get("style"), 32)
        if room_type not in ROOM_TYPES or style not in STYLES:
            raise ValueError("Selecciona una habitación y un estilo válidos.")
        raw, media_type, suffix = _decode_image(str(values.get("photo_data_url") or ""))
        project_id = uuid4().hex
        owner_hash = hashlib.sha256(owner_key.encode("utf-8")).hexdigest()[:24]
        directory = self.image_root / owner_hash / project_id
        directory.mkdir(parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        photo_path = directory / f"original{suffix}"
        photo_path.write_bytes(raw)
        os.chmod(photo_path, 0o600)
        budget = round(float(values.get("budget") or 0), 2)
        keep_items = _list(values.get("keep_items"))
        priorities = _list(values.get("priorities"))
        now = _now()
        row = {
            "id": project_id,
            "household_user": household_user,
            "name": _text(values.get("name"), 80) or f"Mi {ROOM_LABELS[room_type]}",
            "room_type": room_type,
            "room_label": ROOM_LABELS[room_type],
            "style": style,
            "style_label": STYLE_LABELS[style],
            "budget": budget,
            "currency": "USD",
            "measurements": _text(values.get("measurements"), 500),
            "keep_items": keep_items,
            "priorities": priorities,
            "notes": _text(values.get("notes"), 1200),
            "photo_path": str(photo_path),
            "photo_media_type": media_type,
            "proposal_path": "",
            "proposal_status": "NOT_STARTED",
            "proposal_error": "",
            "selected_tier": "balanced",
            "budget_tiers": _budget_tiers(room_type, style, budget),
            "products": _product_plan(room_type, style, budget),
            "analysis": _initial_analysis(room_type, priorities, keep_items),
            "analysis_status": "READY_LOCAL",
            "revision_notes": [],
            "fit_constraints": {"wall_width": 0, "passage_width": 0, "max_depth": 0},
            "created_at": now,
            "updated_at": now,
        }

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            payload["projects"].setdefault(owner_key, {})[project_id] = row
            return deepcopy(row)

        return self._mutate(apply)

    def update_fit_constraints(self, owner_key: str, project_id: str, values: dict[str, Any]) -> dict[str, Any]:
        constraints: dict[str, float] = {}
        for key in ("wall_width", "passage_width", "max_depth"):
            number = round(float(values.get(key) or 0), 2)
            if number < 0 or number > 2_000:
                raise ValueError("Las medidas deben estar entre 0 y 2,000 pulgadas.")
            constraints[key] = number
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            row = payload.get("projects", {}).get(owner_key, {}).get(project_id)
            if not isinstance(row, dict):
                raise KeyError(project_id)
            row.update({"fit_constraints": constraints, "updated_at": _now()})
            return deepcopy(row)
        return self._mutate(apply)

    def select_tier(self, owner_key: str, project_id: str, tier: str) -> dict[str, Any]:
        if tier not in BUDGET_TIERS:
            raise ValueError("Selecciona un nivel de presupuesto válido.")
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            row = payload.get("projects", {}).get(owner_key, {}).get(project_id)
            if not isinstance(row, dict):
                raise KeyError(project_id)
            variants = row.get("budget_tiers") or _budget_tiers(row["room_type"], row["style"], float(row.get("budget") or 0))
            selected = next(item for item in variants if item["id"] == tier)
            row.update({"budget_tiers": variants, "selected_tier": tier, "products": deepcopy(selected["products"]), "updated_at": _now()})
            return deepcopy(row)
        return self._mutate(apply)

    def save_analysis(self, owner_key: str, project_id: str, analysis: dict[str, Any]) -> dict[str, Any]:
        clean = {
            "status": "READY_AI",
            "summary": _text(analysis.get("summary"), 700),
            "strengths": _list(analysis.get("strengths"), limit=6),
            "opportunities": _list(analysis.get("opportunities"), limit=8),
            "questions": _list(analysis.get("questions"), limit=5),
        }
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            row = payload.get("projects", {}).get(owner_key, {}).get(project_id)
            if not isinstance(row, dict):
                raise KeyError(project_id)
            row.update({"analysis": clean, "analysis_status": "READY_AI", "updated_at": _now()})
            return deepcopy(row)
        return self._mutate(apply)

    def request_revision(self, owner_key: str, project_id: str, instruction: str, tier: str) -> dict[str, Any]:
        instruction = _text(instruction, 500)
        if not instruction:
            raise ValueError("Dile a Roxy qué quieres cambiar.")
        self.select_tier(owner_key, project_id, tier)
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            row = payload.get("projects", {}).get(owner_key, {}).get(project_id)
            if not isinstance(row, dict):
                raise KeyError(project_id)
            notes = list(row.get("revision_notes") or [])[-11:]
            notes.append({"instruction": instruction, "created_at": _now()})
            row.update({"revision_notes": notes, "proposal_status": "NOT_STARTED", "proposal_error": "", "updated_at": _now()})
            return deepcopy(row)
        return self._mutate(apply)

    def mark_generating(self, owner_key: str, project_id: str) -> dict[str, Any]:
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            row = payload.get("projects", {}).get(owner_key, {}).get(project_id)
            if not isinstance(row, dict):
                raise KeyError(project_id)
            row.update({"proposal_status": "GENERATING", "proposal_error": "", "updated_at": _now()})
            return deepcopy(row)
        return self._mutate(apply)

    def save_proposal(self, owner_key: str, project_id: str, png_base64: str) -> dict[str, Any]:
        raw = base64.b64decode(png_base64, validate=True)
        if not raw.startswith(b"\x89PNG\r\n\x1a\n") or len(raw) > 15_000_000:
            raise ValueError("OpenAI no devolvió una propuesta visual válida.")
        row = self.project(owner_key, project_id)
        path = Path(row["photo_path"]).parent / "proposal.png"
        path.write_bytes(raw)
        os.chmod(path, 0o600)
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            target = payload["projects"][owner_key][project_id]
            target.update({"proposal_path": str(path), "proposal_status": "READY", "proposal_tier": target.get("selected_tier") or "balanced", "proposal_error": "", "updated_at": _now()})
            return deepcopy(target)
        return self._mutate(apply)

    def mark_failed(self, owner_key: str, project_id: str) -> None:
        def apply(payload: dict[str, Any]) -> None:
            row = payload.get("projects", {}).get(owner_key, {}).get(project_id)
            if isinstance(row, dict):
                row.update({"proposal_status": "FAILED", "proposal_error": "No se pudo crear la propuesta. Inténtalo de nuevo.", "updated_at": _now()})
        self._mutate(apply)

    def delete(self, owner_key: str, project_id: str) -> bool:
        row = self.project(owner_key, project_id)
        def apply(payload: dict[str, Any]) -> bool:
            return payload.get("projects", {}).get(owner_key, {}).pop(project_id, None) is not None
        removed = self._mutate(apply)
        if removed:
            directory = Path(row["photo_path"]).parent
            for child in directory.iterdir():
                if child.is_file():
                    child.unlink()
            directory.rmdir()
        return removed


class HomeDesignGenerator:
    def __init__(self, api_key: str, model: str, quality: str = "low", client: Any = None) -> None:
        self.api_key = api_key
        self.model = model
        self.quality = quality if quality in {"low", "medium", "high"} else "low"
        self.client = client

    @classmethod
    def from_env(cls) -> "HomeDesignGenerator":
        return cls(
            str(os.getenv("ROXY_HOME_OPENAI_API_KEY") or "").strip(),
            str(os.getenv("ROXY_HOME_OPENAI_DEEP_MODEL") or "gpt-5.6-terra").strip(),
            str(os.getenv("ROXY_HOME_DESIGN_IMAGE_QUALITY") or "low").strip().lower(),
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _openai(self) -> Any:
        if self.client is None:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        return self.client

    @staticmethod
    def _result(response: Any) -> str:
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", "") == "image_generation_call" and getattr(item, "result", None):
                return str(item.result)
        raise RuntimeError("OpenAI no devolvió una propuesta visual.")

    @staticmethod
    def _analysis_result(response: Any) -> dict[str, Any]:
        raw = str(getattr(response, "output_text", "") or "").strip()
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise RuntimeError("OpenAI no devolvió un análisis válido.")
        return value

    def analyze(self, project: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("El análisis visual de Roxy Renueva todavía no está conectado.")
        photo = Path(project["photo_path"]).read_bytes()
        media_type = str(project["photo_media_type"])
        image_url = f"data:{media_type};base64,{base64.b64encode(photo).decode('ascii')}"
        prompt = (
            f"Analyze this real {project['room_label']} for a practical {project['style_label']} refresh within about ${project['budget']:.2f} USD. "
            f"The household wants to keep: {', '.join(project.get('keep_items') or []) or 'fixed architecture and useful existing pieces'}. "
            f"Priorities: {', '.join(project.get('priorities') or []) or 'comfort, order, lighting and circulation'}. "
            "Describe only what is visibly supportable or explicitly provided. Do not invent measurements, damage, brands or prices. "
            "Give concise Spanish advice and ask for missing measurements when product fit cannot be verified."
        )
        response = self._openai().responses.create(
            model=self.model,
            input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}, {"type": "input_image", "image_url": image_url}]}],
            text={"format": {"type": "json_schema", "name": "roxy_home_space_analysis", "strict": True, "schema": {"type": "object", "properties": {"summary": {"type": "string"}, "strengths": {"type": "array", "items": {"type": "string"}}, "opportunities": {"type": "array", "items": {"type": "string"}}, "questions": {"type": "array", "items": {"type": "string"}}}, "required": ["summary", "strengths", "opportunities", "questions"], "additionalProperties": False}}},
            store=False,
        )
        return self._analysis_result(response)

    def generate(self, project: dict[str, Any]) -> str:
        if not self.configured:
            raise RuntimeError("La generación visual de Roxy Renueva todavía no está conectada.")
        photo = Path(project["photo_path"]).read_bytes()
        media_type = str(project["photo_media_type"])
        image_url = f"data:{media_type};base64,{base64.b64encode(photo).decode('ascii')}"
        kept = ", ".join(project.get("keep_items") or []) or "the room architecture and existing fixed elements"
        priorities = ", ".join(project.get("priorities") or []) or "comfort, visual harmony and practical circulation"
        products = ", ".join(row.get("name", "") for row in (project.get("products") or []))
        tier = BUDGET_TIERS.get(str(project.get("selected_tier") or "balanced"), BUDGET_TIERS["balanced"])
        revision_notes = "; ".join(str(row.get("instruction") or "") for row in (project.get("revision_notes") or [])[-4:])
        fit = _fit_assessment(project.get("fit_constraints"))
        dimensions = fit["constraints"]
        prompt = (
            f"Edit this exact photograph of a {project['room_label']} into a realistic {project['style_label']} redesign. "
            f"Preserve the exact architecture, camera angle, windows, doors, floor plan and these requested items: {kept}. "
            f"Prioritize {priorities}. Create the {tier['label']} option and respect a total furnishing budget near ${project['budget'] * float(tier['multiplier']):.2f} USD, so the result must be attainable, not luxury fantasy. "
            f"Use a coherent version of these shoppable decor concepts so the visualization and shopping plan agree: {products}. "
            f"Apply these latest household revision requests exactly when compatible with the room: {revision_notes or 'no additional revisions'}. "
            f"Physical limits in inches, when greater than zero: wall width {dimensions['wall_width']}, passage width {dimensions['passage_width']}, maximum furniture depth {dimensions['max_depth']}. Never depict an item that clearly violates these supplied limits. "
            "Show one photorealistic finished-room visualization. Do not change the room into another property. "
            "No people, text, labels, logos, watermarks, before-and-after split or impossible construction."
        )
        response = self._openai().responses.create(
            model=self.model,
            input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}, {"type": "input_image", "image_url": image_url}]}],
            tools=[{"type": "image_generation", "quality": self.quality, "size": "1536x1024"}],
            store=False,
        )
        return self._result(response)


def public_project(row: dict[str, Any], user_id: str) -> dict[str, Any]:
    result = {key: deepcopy(value) for key, value in row.items() if key not in {"photo_path", "proposal_path", "photo_media_type"}}
    result.setdefault("selected_tier", "balanced")
    result.setdefault("budget_tiers", _budget_tiers(str(row.get("room_type") or "other"), str(row.get("style") or "surprise_me"), float(row.get("budget") or 0)))
    if not result.get("analysis"):
        result["analysis"] = _initial_analysis(str(row.get("room_type") or "other"), list(row.get("priorities") or []), list(row.get("keep_items") or []))
    result.setdefault("analysis_status", str((result.get("analysis") or {}).get("status") or "READY_LOCAL"))
    result.setdefault("revision_notes", [])
    result.setdefault("fit_constraints", {"wall_width": 0, "passage_width": 0, "max_depth": 0})
    result["fit_assessment"] = _fit_assessment(result.get("fit_constraints"))
    project_id = row["id"]
    result["photo_url"] = f"/v1/home-design/{user_id}/projects/{project_id}/image/original"
    result["proposal_url"] = f"/v1/home-design/{user_id}/projects/{project_id}/image/proposal" if row.get("proposal_path") else ""
    return result
