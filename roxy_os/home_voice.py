from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

import requests
from roxy_os.home_private_storage import HomePrivateStorageError, read_private_json, write_private_json

import fcntl

_VOICE_LOCK = RLock()


class HomeVoiceError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def voice_failure(exc: Exception) -> HomeVoiceError:
    response = getattr(exc, "response", None)
    code = ""
    if response is not None:
        try:
            detail = response.json().get("detail", {})
            code = detail.get("status", "") if isinstance(detail, dict) else ""
        except (ValueError, AttributeError):
            pass
    if code == "payment_issue":
        return HomeVoiceError("payment_issue", "La voz oficial está pausada por un pago pendiente en ElevenLabs. El saldo de OpenAI es independiente.")
    if code in {"quota_exceeded", "insufficient_credits"}:
        return HomeVoiceError("quota_exceeded", "La voz oficial agotó su cupo de ElevenLabs. Puedes usar la voz del dispositivo.")
    if code in {"missing_permissions", "invalid_api_key"}:
        return HomeVoiceError("access_denied", "Hay que revisar el acceso de la voz oficial en ElevenLabs.")
    return HomeVoiceError("unavailable", "No se pudo reproducir la voz oficial. Puedes reintentar o usar la voz del dispositivo.")


def _valid_usage(value: Any) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("date"), str):
        return False
    try:
        if datetime.strptime(value["date"], "%Y-%m-%d").date().isoformat() != value["date"]:
            return False
    except ValueError:
        return False
    return all(type(value.get(key)) is int and value[key] >= 0 for key in ("requests", "characters"))


ELEVENLABS_API = "https://api.elevenlabs.io/v1"


@dataclass(frozen=True)
class HomeVoiceConfig:
    api_key: str
    agent_id: str
    voice_id: str
    model_id: str
    cache_dir: Path
    daily_characters: int = 20_000
    daily_requests: int = 200

    @classmethod
    def from_env(cls) -> "HomeVoiceConfig":
        return cls(
            api_key=str(os.getenv("ROXY_HOME_ELEVENLABS_API_KEY", "")).strip(),
            agent_id=str(os.getenv("ROXY_HOME_ELEVENLABS_AGENT_ID", "")).strip(),
            voice_id=str(os.getenv("ROXY_HOME_ELEVENLABS_VOICE_ID", "")).strip(),
            model_id=str(os.getenv("ROXY_HOME_ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")).strip(),
            cache_dir=Path(os.getenv("ROXY_HOME_ELEVENLABS_CACHE_DIR", "data/roxy_home_voice")),
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key and (self.agent_id or self.voice_id))

    def public_status(self) -> dict[str, Any]:
        return {"enabled": self.configured, "status": "CONFIGURED" if self.configured else "UNCONFIGURED", "provider_health_verified": False, "provider": "ElevenLabs" if self.configured else "", "voice": "Roxy oficial" if self.configured else ""}


class ElevenLabsHomeVoice:
    """Server-only TTS using the same voice profile as Roxy's official agent."""

    def __init__(self, config: HomeVoiceConfig, *, session: Any = requests) -> None:
        self.config = config
        self.session = session
        self._profile: dict[str, Any] | None = None

    @property
    def headers(self) -> dict[str, str]:
        return {"xi-api-key": self.config.api_key, "Content-Type": "application/json"}

    def voice_profile(self) -> dict[str, Any]:
        if self._profile is not None:
            return self._profile
        if not self.config.configured:
            raise RuntimeError("La voz oficial de Roxy Home no está configurada.")
        if self.config.voice_id:
            self._profile = {"voice_id": self.config.voice_id, "model_id": self.config.model_id}
            return self._profile
        response = self.session.get(f"{ELEVENLABS_API}/convai/agents/{self.config.agent_id}", headers=self.headers, timeout=20)
        response.raise_for_status()
        tts = ((response.json().get("conversation_config") or {}).get("tts") or {})
        voice_id = str(tts.get("voice_id") or "").strip()
        if not voice_id:
            raise RuntimeError("El agente oficial de Roxy no tiene una voz configurada.")
        self._profile = {"voice_id": voice_id, "model_id": str(tts.get("model_id") or self.config.model_id).strip(), "voice_settings": tts.get("voice_settings") if isinstance(tts.get("voice_settings"), dict) else None}
        return self._profile

    def synthesize(self, text: str, *, user_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", user_id):
            raise ValueError("Identidad de voz inválida.")
        # Serialize cache creation and admission across Home workers. No keys,
        # transcript, recipes or other products are written to the usage ledger.
        with _VOICE_LOCK:
            self.config.cache_dir.mkdir(parents=True, exist_ok=True)
            with (self.config.cache_dir / ".voice.lock").open("a") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                try:
                    return self._synthesize(text, user_id=user_id)
                finally:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _synthesize(self, text: str, *, user_id: str) -> Path:
        clean = " ".join(str(text or "").strip().split())
        if not clean:
            raise ValueError("No hay texto para leer.")
        if len(clean) > 1_200:
            raise ValueError("El paso supera el límite de voz oficial; usa la voz del dispositivo para escucharlo completo.")
        profile = self.voice_profile()
        identity = f"{user_id}:{profile['voice_id']}:{profile['model_id']}:{clean}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        destination = self.config.cache_dir / user_id / f"{digest}.mp3"
        if destination.is_file() and destination.stat().st_size > 1_024:
            return destination
        ledger = self.config.cache_dir / "usage.json"
        today = datetime.now(timezone.utc).date().isoformat()
        empty = lambda: {"date": today, "requests": 0, "characters": 0}
        usage, _ = read_private_json(ledger, empty, _valid_usage, HomePrivateStorageError)
        if usage["date"] > today:
            raise HomePrivateStorageError("future_voice_usage")
        if usage["date"] != today:
            usage = empty()
        if usage["requests"] >= self.config.daily_requests or usage["characters"] + len(clean) > self.config.daily_characters:
            raise HomeVoiceError("home_voice_limit", "La voz oficial alcanzó el límite diario de Home. Puedes usar la voz del dispositivo.")
        # Reserve before sending. A failed/uncertain call keeps its reservation;
        # this is a conservative request/character cap, not a provider invoice.
        usage["requests"] += 1
        usage["characters"] += len(clean)
        write_private_json(ledger, usage, _valid_usage, HomePrivateStorageError)
        payload: dict[str, Any] = {"text": clean, "model_id": profile["model_id"]}
        if profile.get("voice_settings"):
            payload["voice_settings"] = profile["voice_settings"]
        try:
            response = self.session.post(f"{ELEVENLABS_API}/text-to-speech/{profile['voice_id']}?output_format=mp3_44100_128", headers={**self.headers, "Accept": "audio/mpeg"}, json=payload, timeout=(8, 20))
            response.raise_for_status()
        except requests.RequestException as exc:
            raise voice_failure(exc) from None
        content = bytes(response.content)
        if len(content) < 1_024 or len(content) > 10 * 1024 * 1024:
            raise RuntimeError("ElevenLabs devolvió un audio inválido.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=".roxy-voice-", suffix=".mp3", dir=str(destination.parent))
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(content); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            try: os.unlink(temporary)
            except FileNotFoundError: pass
        return destination
