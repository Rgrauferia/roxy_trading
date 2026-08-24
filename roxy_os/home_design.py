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


def _product_plan(room_type: str, style: str, budget: float) -> list[dict[str, Any]]:
    names = ROOM_PRODUCTS.get(room_type, ROOM_PRODUCTS["other"])
    style_label = STYLE_LABELS.get(style, STYLE_LABELS["surprise_me"])
    shares = (0.38, 0.27, 0.20, 0.15)
    return [
        {
            "id": f"product-{index + 1}",
            "name": f"{name} estilo {style_label}",
            "quantity": 1,
            "unit": "unidad",
            "category": "HOUSEHOLD",
            "budget_target": round(max(0, budget) * shares[index], 2),
            "selected": True,
        }
        for index, name in enumerate(names)
    ]


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
            "keep_items": _list(values.get("keep_items")),
            "priorities": _list(values.get("priorities")),
            "notes": _text(values.get("notes"), 1200),
            "photo_path": str(photo_path),
            "photo_media_type": media_type,
            "proposal_path": "",
            "proposal_status": "NOT_STARTED",
            "proposal_error": "",
            "products": _product_plan(room_type, style, budget),
            "created_at": now,
            "updated_at": now,
        }

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            payload["projects"].setdefault(owner_key, {})[project_id] = row
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
            target.update({"proposal_path": str(path), "proposal_status": "READY", "proposal_error": "", "updated_at": _now()})
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

    def generate(self, project: dict[str, Any]) -> str:
        if not self.configured:
            raise RuntimeError("La generación visual de Roxy Renueva todavía no está conectada.")
        photo = Path(project["photo_path"]).read_bytes()
        media_type = str(project["photo_media_type"])
        image_url = f"data:{media_type};base64,{base64.b64encode(photo).decode('ascii')}"
        kept = ", ".join(project.get("keep_items") or []) or "the room architecture and existing fixed elements"
        priorities = ", ".join(project.get("priorities") or []) or "comfort, visual harmony and practical circulation"
        products = ", ".join(row.get("name", "") for row in (project.get("products") or []))
        prompt = (
            f"Edit this exact photograph of a {project['room_label']} into a realistic {project['style_label']} redesign. "
            f"Preserve the exact architecture, camera angle, windows, doors, floor plan and these requested items: {kept}. "
            f"Prioritize {priorities}. Respect a total furnishing budget near ${project['budget']:.2f} USD, so the result must be attainable, not luxury fantasy. "
            f"Use a coherent version of these shoppable decor concepts so the visualization and shopping plan agree: {products}. "
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
    project_id = row["id"]
    result["photo_url"] = f"/v1/home-design/{user_id}/projects/{project_id}/image/original"
    result["proposal_url"] = f"/v1/home-design/{user_id}/projects/{project_id}/image/proposal" if row.get("proposal_path") else ""
    return result
