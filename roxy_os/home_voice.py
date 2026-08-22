from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


ELEVENLABS_API = "https://api.elevenlabs.io/v1"
DEFAULT_ROXY_AGENT_ID = "agent_6101kwchebzdf91rfk9757wq0mk4"


@dataclass(frozen=True)
class HomeVoiceConfig:
    api_key: str
    agent_id: str
    voice_id: str
    model_id: str
    cache_dir: Path

    @classmethod
    def from_env(cls) -> "HomeVoiceConfig":
        return cls(
            api_key=str(os.getenv("ROXY_HOME_ELEVENLABS_API_KEY", "")).strip(),
            agent_id=str(os.getenv("ROXY_HOME_ELEVENLABS_AGENT_ID", DEFAULT_ROXY_AGENT_ID)).strip(),
            voice_id=str(os.getenv("ROXY_HOME_ELEVENLABS_VOICE_ID", "")).strip(),
            model_id=str(os.getenv("ROXY_HOME_ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")).strip(),
            cache_dir=Path(os.getenv("ROXY_HOME_ELEVENLABS_CACHE_DIR", "data/roxy_home_voice")),
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.agent_id)

    def public_status(self) -> dict[str, Any]:
        return {"enabled": self.configured, "provider": "ElevenLabs" if self.configured else "", "voice": "Roxy oficial" if self.configured else ""}


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
        clean = " ".join(str(text or "").strip().split())[:1_200]
        if not clean:
            raise ValueError("No hay texto para leer.")
        profile = self.voice_profile()
        identity = f"{user_id}:{profile['voice_id']}:{profile['model_id']}:{clean}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        destination = self.config.cache_dir / user_id / f"{digest}.mp3"
        if destination.is_file() and destination.stat().st_size > 1_024:
            return destination
        payload: dict[str, Any] = {"text": clean, "model_id": profile["model_id"]}
        if profile.get("voice_settings"):
            payload["voice_settings"] = profile["voice_settings"]
        response = self.session.post(f"{ELEVENLABS_API}/text-to-speech/{profile['voice_id']}?output_format=mp3_44100_128", headers={**self.headers, "Accept": "audio/mpeg"}, json=payload, timeout=(15, 90))
        response.raise_for_status()
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
