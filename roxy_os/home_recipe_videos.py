from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from uuid import uuid4

import requests

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

from roxy_os.shopping_list import normalize_shopping_user


VIDEO_STORE_VERSION = 1
VIDEO_PROMPT_VERSION = 2
VIDEO_STATUSES = {"QUEUED", "PROCESSING", "REVIEW", "READY", "FAILED", "REJECTED"}
VIDEO_VISIBILITIES = {"shared", "household"}
FAL_MODEL = "fal-ai/minimax/hailuo-02/standard/text-to-video"
FAL_QUEUE_URL = f"https://queue.fal.run/{FAL_MODEL}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _identity(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", _text(value, 2_000))
    return " ".join(normalized.encode("ascii", "ignore").decode("ascii").lower().split())


def recipe_fingerprint(recipe: dict[str, Any]) -> str:
    """Return a stable identity for reusable recipe media.

    Personal notes, photos, favorites and user identifiers are deliberately
    excluded, so a reviewed shared video never leaks household data.
    """

    ingredients = []
    for row in recipe.get("ingredients") or []:
        if not isinstance(row, dict):
            continue
        ingredients.append(
            {
                "name": _identity(row.get("name")),
                "quantity": round(float(row.get("quantity") or 0), 4),
                "unit": _identity(row.get("unit")),
                "notes": _identity(row.get("notes")),
            }
        )
    canonical = {
        "title": _identity(recipe.get("title")),
        "kind": _identity(recipe.get("kind")),
        "drink_type": _identity(recipe.get("drink_type")),
        "servings": round(float(recipe.get("servings") or 1), 4),
        "ingredients": ingredients,
        "steps": [_identity(step) for step in (recipe.get("steps") or [])],
    }
    encoded = json.dumps(canonical, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class HomeRecipeVideoConfig:
    enabled: bool
    api_key: str
    clip_count: int
    clip_seconds: int
    price_per_second_usd: float
    monthly_budget_usd: float
    max_recipe_cost_usd: float
    media_dir: Path
    admin_key: str

    @classmethod
    def from_env(cls) -> "HomeRecipeVideoConfig":
        clip_count = max(1, min(3, int(os.getenv("ROXY_HOME_VIDEO_CLIP_COUNT", "3") or 3)))
        # Hailuo's current standard endpoint supports six- or ten-second clips;
        # six seconds keeps the first Roxy Home implementation economical.
        clip_seconds = 6
        return cls(
            enabled=str(os.getenv("ROXY_HOME_VIDEO_ENABLED", "0")).strip().lower() in {"1", "true", "yes"},
            api_key=str(os.getenv("ROXY_HOME_VIDEO_FAL_KEY", "")).strip(),
            clip_count=clip_count,
            clip_seconds=clip_seconds,
            price_per_second_usd=max(
                0.001, float(os.getenv("ROXY_HOME_VIDEO_PRICE_PER_SECOND_USD", "0.045") or 0.045)
            ),
            monthly_budget_usd=max(
                0.0, float(os.getenv("ROXY_HOME_VIDEO_MONTHLY_BUDGET_USD", "0") or 0)
            ),
            max_recipe_cost_usd=max(
                0.0, float(os.getenv("ROXY_HOME_VIDEO_MAX_RECIPE_COST_USD", "1.00") or 1)
            ),
            media_dir=Path(os.getenv("ROXY_HOME_VIDEO_MEDIA_DIR", "data/roxy_home_recipe_videos")),
            admin_key=str(os.getenv("ROXY_HOME_VIDEO_ADMIN_KEY", "")).strip(),
        )

    @property
    def estimated_recipe_cost_usd(self) -> float:
        return round(self.clip_count * self.clip_seconds * self.price_per_second_usd, 2)

    @property
    def configured(self) -> bool:
        return bool(
            self.enabled
            and self.api_key
            and self.monthly_budget_usd > 0
            and self.max_recipe_cost_usd >= self.estimated_recipe_cost_usd
        )

    @property
    def state(self) -> str:
        if not self.enabled:
            return "disabled"
        if not self.api_key:
            return "missing_key"
        if self.monthly_budget_usd <= 0:
            return "missing_budget"
        if self.max_recipe_cost_usd < self.estimated_recipe_cost_usd:
            return "cost_limit"
        return "ready"

    def public_status(self) -> dict[str, Any]:
        messages = {
            "disabled": "La generación de videos está desactivada en Roxy Home.",
            "missing_key": "Falta conectar la clave exclusiva del proveedor de videos de Roxy Home.",
            "missing_budget": "Falta definir un presupuesto mensual de videos mayor que cero.",
            "cost_limit": "El límite por receta es menor que el costo estimado de sus clips.",
            "ready": "La generación automática de videos está lista.",
        }
        return {
            "enabled": self.configured,
            "state": self.state,
            "message": messages[self.state],
            "provider": "fal.ai · Hailuo 02" if self.configured else "",
            "clip_count": self.clip_count,
            "clip_seconds": self.clip_seconds,
            "estimated_recipe_cost_usd": self.estimated_recipe_cost_usd,
            "requires_confirmation": True,
            "requires_review": True,
            "reusable": True,
        }


class FalHailuoVideoProvider:
    def __init__(self, config: HomeRecipeVideoConfig, *, session: Any = requests) -> None:
        self.config = config
        self.session = session

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Key {self.config.api_key}", "Content-Type": "application/json"}

    @staticmethod
    def _trusted_queue_url(url: str) -> str:
        parsed = urlparse(str(url or ""))
        if parsed.scheme != "https" or parsed.hostname != "queue.fal.run":
            raise ValueError("El proveedor devolvió una URL de seguimiento no permitida.")
        return url

    @staticmethod
    def _trusted_media_url(url: str) -> str:
        parsed = urlparse(str(url or ""))
        host = str(parsed.hostname or "").lower()
        if parsed.scheme != "https" or not (host == "fal.media" or host.endswith(".fal.media")):
            raise ValueError("El proveedor devolvió un archivo en un dominio no permitido.")
        return url

    def submit(self, prompt: str) -> dict[str, str]:
        response = self.session.post(
            FAL_QUEUE_URL,
            headers=self.headers,
            # Keep Roxy's instructional choreography intact. The provider's
            # cinematic optimizer can turn a demonstration into decorative
            # food B-roll, which is not useful while somebody is cooking.
            json={"prompt": prompt, "duration": str(self.config.clip_seconds), "prompt_optimizer": False},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        request_id = _text(payload.get("request_id"), 160)
        if not request_id:
            raise ValueError("El proveedor no devolvió un identificador de generación.")
        status_url = self._trusted_queue_url(payload.get("status_url") or f"{FAL_QUEUE_URL}/requests/{request_id}/status")
        response_url = self._trusted_queue_url(payload.get("response_url") or f"{FAL_QUEUE_URL}/requests/{request_id}")
        return {"request_id": request_id, "status_url": status_url, "response_url": response_url}

    def poll(self, job: dict[str, Any]) -> dict[str, Any]:
        status_url = self._trusted_queue_url(str(job.get("status_url") or ""))
        response = self.session.get(status_url, headers=self.headers, timeout=30)
        response.raise_for_status()
        payload = response.json()
        status = str(payload.get("status") or "").upper()
        if status in {"IN_QUEUE", "QUEUED"}:
            return {"status": "QUEUED"}
        if status in {"IN_PROGRESS", "PROCESSING"}:
            return {"status": "PROCESSING"}
        if status not in {"COMPLETED", "READY"}:
            return {"status": "FAILED", "error": "La generación de este clip no terminó correctamente."}
        result_response = self.session.get(
            self._trusted_queue_url(str(job.get("response_url") or "")), headers=self.headers, timeout=30
        )
        result_response.raise_for_status()
        result = result_response.json()
        video = result.get("video") or (result.get("data") or {}).get("video") or {}
        return {"status": "COMPLETED", "media_url": self._trusted_media_url(str(video.get("url") or ""))}

    def download(self, media_url: str, destination: Path) -> int:
        destination.parent.mkdir(parents=True, exist_ok=True)
        response = self.session.get(self._trusted_media_url(media_url), stream=True, timeout=(15, 120))
        response.raise_for_status()
        self._trusted_media_url(str(getattr(response, "url", media_url)))
        content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
        if content_type not in {"video/mp4", "application/octet-stream"}:
            raise ValueError("El proveedor no devolvió un video MP4 válido.")
        maximum = 100 * 1024 * 1024
        total = 0
        handle, temporary = tempfile.mkstemp(prefix=".roxy-video-", suffix=".mp4", dir=str(destination.parent))
        try:
            with os.fdopen(handle, "wb") as stream:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > maximum:
                        raise ValueError("El video supera el límite de 100 MB.")
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if total < 1_024:
                raise ValueError("El archivo de video recibido está vacío o incompleto.")
            os.replace(temporary, destination)
            return total
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


class HomeRecipeVideoStore:
    """Reusable media catalog separated from private Home food memory."""

    def __init__(self, path: str | Path = "data/roxy_home_recipe_video_library.json") -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"schema_version": VIDEO_STORE_VERSION, "updated_at": _now_iso(), "videos": []}

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            return self._empty()
        if not isinstance(payload, dict) or not isinstance(payload.get("videos"), list):
            return self._empty()
        payload["schema_version"] = VIDEO_STORE_VERSION
        return payload

    def _write_unlocked(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload["schema_version"] = VIDEO_STORE_VERSION
        payload["updated_at"] = _now_iso()
        handle, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def _mutate(self, callback: Callable[[dict[str, Any]], Any]) -> Any:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._read_unlocked()
                result = callback(payload)
                self._write_unlocked(payload)
                return result
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _public(record: dict[str, Any], user_id: Any) -> dict[str, Any]:
        user = normalize_shopping_user(user_id)
        clips = []
        for index, clip in enumerate(record.get("clips") or []):
            clips.append(
                {
                    "index": index,
                    "status": clip.get("status"),
                    "step_label": clip.get("step_label"),
                    "playback_url": (
                        f"/v1/home-food/{user}/recipe-videos/{record['id']}/clips/{index}"
                        if clip.get("media_path") and record.get("status") in {"REVIEW", "READY"}
                        else ""
                    ),
                }
            )
        return {
            "id": record.get("id"),
            "recipe_title": record.get("recipe_title"),
            "visibility": record.get("visibility"),
            "status": record.get("status"),
            "provider": record.get("provider"),
            "clip_count": len(clips),
            "clips": clips,
            "estimated_cost_usd": record.get("estimated_cost_usd"),
            "ai_generated": True,
            "reused": bool(record.get("reused")),
            "created_at": record.get("created_at"),
            "reviewed_at": record.get("reviewed_at"),
            "can_preview": user == record.get("owner_user_id") or record.get("status") == "READY",
        }

    def find_for_recipe(self, user_id: Any, recipe: dict[str, Any]) -> dict[str, Any] | None:
        user = normalize_shopping_user(user_id)
        fingerprint = recipe_fingerprint(recipe)
        rows = [
            row
            for row in self._read_unlocked().get("videos", [])
            if row.get("recipe_fingerprint") == fingerprint
            and int(row.get("prompt_version") or 0) == VIDEO_PROMPT_VERSION
        ]
        accessible = [
            row
            for row in rows
            if row.get("owner_user_id") == user or (row.get("visibility") == "shared" and row.get("status") == "READY")
        ]
        if not accessible:
            return None
        accessible.sort(
            key=lambda row: (
                row.get("status") == "READY",
                row.get("visibility") == "shared",
                str(row.get("created_at") or ""),
            ),
            reverse=True,
        )
        return self._public(accessible[0], user)

    def monthly_reserved_usd(self) -> float:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        return round(
            sum(
                float(row.get("estimated_cost_usd") or 0)
                for row in self._read_unlocked().get("videos", [])
                if str(row.get("created_at") or "").startswith(month)
                and row.get("status") not in {"FAILED", "REJECTED"}
            ),
            2,
        )

    @staticmethod
    def _action_direction(step: str) -> str:
        normalized = _identity(step)
        if any(word in normalized for word in ("mezcla", "mezclar", "bate", "batir", "revuelve", "revolver")):
            return (
                "Show the named ingredients being poured one by one into the bowl, then show the utensil actively "
                "stirring them until they are visibly combined and the texture changes."
            )
        if any(word in normalized for word in ("amasa", "amasar")):
            return (
                "Show both hands repeatedly folding, pressing, and turning the dough on the work surface until it "
                "becomes smoother and more elastic."
            )
        if any(word in normalized for word in ("anade", "agrega", "incorpora", "vierte", "verter")):
            return (
                "Show a hand visibly adding the named ingredient to the correct container, followed by the exact "
                "mixing or combining movement required by the instruction."
            )
        if any(word in normalized for word in ("repos", "crecer", "ferment", "duplica", "leva")):
            return (
                "Show hands covering the prepared mixture correctly, then use a brief coherent time-lapse that "
                "clearly demonstrates its rise or resting change."
            )
        if any(word in normalized for word in ("hornea", "hornear", "h horno", "oven")):
            return (
                "Show oven-mitted hands placing the prepared tray into the oven and a brief time transition to the "
                "properly baked result; keep the action physically plausible and safe."
            )
        if any(word in normalized for word in ("corta", "pica", "rebana", "trocea")):
            return (
                "Show hands using a cutting board and a controlled safe grip while visibly making the cuts described; "
                "fingers remain behind the blade."
            )
        if any(word in normalized for word in ("licua", "procesa", "tritura")):
            return (
                "Show the ingredients entering the appliance, the lid being secured, and the mixture visibly changing "
                "consistency while blending."
            )
        if any(word in normalized for word in ("agita", "shake", "coctelera", "sirve", "cuela")):
            return (
                "Show hands performing the beverage technique continuously, including the real shaking, straining, "
                "or pouring movement and the liquid entering the serving glass."
            )
        if any(word in normalized for word in ("cocina", "sofrie", "frie", "hierve", "saltea")):
            return (
                "Show the food being added to the correct pan or pot and actively stirred while heat produces a visible, "
                "realistic cooking change."
            )
        return (
            "Show adult hands performing the instruction continuously and visibly, including the tool touching the food "
            "and an observable change from the beginning to the end of the step."
        )

    @staticmethod
    def _prompt_segments(recipe: dict[str, Any], count: int) -> list[tuple[str, str]]:
        steps = [_text(row, 400) for row in (recipe.get("steps") or []) if _text(row)]
        if not steps:
            raise ValueError("La receta no tiene pasos para visualizar.")
        ingredient_names = [
            _text(row.get("name"), 80)
            for row in (recipe.get("ingredients") or [])
            if isinstance(row, dict) and _text(row.get("name"))
        ]
        ingredient_context = ", ".join(ingredient_names[:12]) or "the ingredients named in the instruction"
        indices = sorted({min(len(steps) - 1, round(index * (len(steps) - 1) / max(1, count - 1))) for index in range(count)})
        while len(indices) < count:
            indices.append(indices[-1])
        result = []
        for position, step_index in enumerate(indices[:count], start=1):
            step = steps[step_index]
            action_direction = HomeRecipeVideoStore._action_direction(step)
            prompt = (
                f"Vertical 9:16 hands-only step-by-step cooking demonstration for the recipe "
                f"'{_text(recipe.get('title'), 160)}'. The clip must visibly teach this exact instruction, not merely "
                f"show ingredients or finished food: '{step}'. {action_direction} Relevant recipe ingredients: "
                f"{ingredient_context}. Start with the action already beginning; use one coherent close-up sequence and "
                "keep the hands, utensil, container, and changing food centered and fully visible. Realistic quantities, "
                "realistic motion, clean warm home kitchen, steady camera. No static hero shot, no still life, no decorative "
                "B-roll, no unrelated finished dish, no faces, no logos, no captions, no text, no brand packaging. "
                "Accuracy of the demonstrated cooking action is more important than cinematic styling."
            )
            result.append((f"Paso visual {position}: {step[:90]}", prompt))
        return result

    def create_or_reuse(
        self,
        user_id: Any,
        recipe: dict[str, Any],
        config: HomeRecipeVideoConfig,
        *,
        visibility: str,
    ) -> tuple[dict[str, Any], bool]:
        user = normalize_shopping_user(user_id)
        if visibility not in VIDEO_VISIBILITIES:
            raise ValueError("La privacidad del video no es válida.")
        fingerprint = recipe_fingerprint(recipe)

        def apply(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
            rows = payload.setdefault("videos", [])
            for row in rows:
                same_scope = row.get("visibility") == "shared" if visibility == "shared" else row.get("owner_user_id") == user
                if (
                    row.get("recipe_fingerprint") == fingerprint
                    and int(row.get("prompt_version") or 0) == VIDEO_PROMPT_VERSION
                    and same_scope
                    and row.get("status") not in {"FAILED", "REJECTED"}
                ):
                    reused = deepcopy(row)
                    reused["reused"] = True
                    return reused, True
            segments = self._prompt_segments(recipe, config.clip_count)
            row = {
                "id": uuid4().hex,
                "recipe_fingerprint": fingerprint,
                "prompt_version": VIDEO_PROMPT_VERSION,
                "recipe_title": _text(recipe.get("title"), 180),
                "visibility": visibility,
                "owner_user_id": user,
                "status": "QUEUED",
                "provider": "fal_hailuo_02",
                "model": FAL_MODEL,
                "estimated_cost_usd": config.estimated_recipe_cost_usd,
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "reviewed_at": None,
                "review_notes": "",
                "clips": [
                    {
                        "status": "QUEUED",
                        "step_label": label,
                        "prompt": prompt,
                        "provider_request_id": "",
                        "status_url": "",
                        "response_url": "",
                        "media_path": "",
                        "bytes": 0,
                        "error": "",
                    }
                    for label, prompt in segments
                ],
            }
            rows.append(row)
            rows[:] = rows[-1_000:]
            return deepcopy(row), False

        return self._mutate(apply)

    def get_internal(self, video_id: str) -> dict[str, Any]:
        row = next((row for row in self._read_unlocked().get("videos", []) if str(row.get("id")) == str(video_id)), None)
        if row is None:
            raise KeyError(video_id)
        return row

    def update(self, video_id: str, callback: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            row = next((row for row in payload.get("videos", []) if str(row.get("id")) == str(video_id)), None)
            if row is None:
                raise KeyError(video_id)
            callback(row)
            if row.get("status") not in VIDEO_STATUSES:
                raise ValueError("Estado de video no válido.")
            row["updated_at"] = _now_iso()
            return deepcopy(row)

        return self._mutate(apply)

    def accessible_internal(self, user_id: Any, video_id: str, *, allow_review: bool = True) -> dict[str, Any]:
        user = normalize_shopping_user(user_id)
        row = self.get_internal(video_id)
        if row.get("owner_user_id") == user and allow_review:
            return row
        if row.get("visibility") == "shared" and row.get("status") == "READY":
            return row
        raise KeyError(video_id)

    def public(self, user_id: Any, video_id: str) -> dict[str, Any]:
        return self._public(self.accessible_internal(user_id, video_id), user_id)

    def approve(self, video_id: str, *, approved: bool, notes: str = "") -> dict[str, Any]:
        def apply(row: dict[str, Any]) -> None:
            if row.get("status") != "REVIEW":
                raise ValueError("El video todavía no está listo para revisión.")
            row["status"] = "READY" if approved else "REJECTED"
            row["reviewed_at"] = _now_iso()
            row["review_notes"] = _text(notes, 1_000)

        return self.update(video_id, apply)


def submit_recipe_video(
    store: HomeRecipeVideoStore,
    provider: FalHailuoVideoProvider,
    video_id: str,
) -> dict[str, Any]:
    record = store.get_internal(video_id)
    if any(clip.get("provider_request_id") for clip in record.get("clips") or []):
        return record
    try:
        submitted = [provider.submit(str(clip.get("prompt") or "")) for clip in record.get("clips") or []]
    except Exception as exc:
        store.update(video_id, lambda row: row.update(status="FAILED", review_notes="No se pudo iniciar la generación."))
        raise ConnectionError("No se pudo iniciar la generación de video.") from exc

    def apply(row: dict[str, Any]) -> None:
        row["status"] = "PROCESSING"
        for clip, job in zip(row.get("clips") or [], submitted):
            clip.update(job)
            clip["status"] = "PROCESSING"

    return store.update(video_id, apply)


def sync_recipe_video(
    store: HomeRecipeVideoStore,
    provider: FalHailuoVideoProvider,
    config: HomeRecipeVideoConfig,
    video_id: str,
) -> dict[str, Any]:
    record = store.get_internal(video_id)
    if record.get("status") in {"REVIEW", "READY", "REJECTED", "FAILED"}:
        return record
    results: list[dict[str, Any]] = []
    for clip in record.get("clips") or []:
        if clip.get("media_path"):
            results.append({"status": "COMPLETED"})
            continue
        try:
            result = provider.poll(clip)
            if result.get("status") == "COMPLETED":
                index = len(results)
                destination = config.media_dir / video_id / f"clip-{index + 1}.mp4"
                byte_count = provider.download(str(result["media_url"]), destination)
                result.update(media_path=str(destination.resolve()), bytes=byte_count)
            results.append(result)
        except Exception:
            results.append({"status": "FAILED", "error": "No se pudo recuperar este clip."})

    def apply(row: dict[str, Any]) -> None:
        for clip, result in zip(row.get("clips") or [], results):
            if result.get("status") == "COMPLETED":
                clip.update(
                    status="COMPLETED",
                    media_path=result.get("media_path") or clip.get("media_path"),
                    bytes=result.get("bytes") or clip.get("bytes") or 0,
                    error="",
                )
            else:
                clip["status"] = result.get("status") or "PROCESSING"
                clip["error"] = result.get("error") or ""
        statuses = {clip.get("status") for clip in row.get("clips") or []}
        if statuses == {"COMPLETED"}:
            row["status"] = "REVIEW"
        elif "FAILED" in statuses:
            row["status"] = "FAILED"
        elif "PROCESSING" in statuses:
            row["status"] = "PROCESSING"
        else:
            row["status"] = "QUEUED"

    return store.update(video_id, apply)
