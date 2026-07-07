from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
from typing import Any

import requests


DEFAULT_ELEVENLABS_AGENT_ID = "agent_6101kwchebzdf91rfk9757wq0mk4"
ELEVENLABS_SIGNED_URL_ENDPOINT = "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"
ELEVENLABS_CONVERSATION_TOKEN_ENDPOINT = "https://api.elevenlabs.io/v1/convai/conversation/token"
ELEVENLABS_ENV_KEYS = {"ELEVENLABS_AGENT_ID", "ELEVENLABS_API_KEY"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_ENV_FILES = (PROJECT_ROOT / ".env.local", PROJECT_ROOT / ".env")

SAFE_PROFILE_FIELDS = (
    "user_name",
    "username",
    "name",
    "preferred_language",
    "language",
    "trading_level",
    "risk_tolerance",
    "preferred_markets",
    "watchlist",
    "learning_progress",
    "completed_lessons",
    "trading_style",
)

SAFE_CONTEXT_FIELDS = (
    "page",
    "module",
    "symbol",
    "market",
    "timeframe",
    "section",
    "lesson",
    "selected_asset",
    "watchlist_count",
)


@dataclass(frozen=True)
class ElevenLabsRoxySession:
    agent_id: str
    signed_url: str = ""
    conversation_token: str = ""
    configured: bool = False
    error: str = ""
    generated_at: str = ""


def _strip_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip()


def load_local_elevenlabs_env() -> None:
    """Load only ElevenLabs keys from local env files without logging secrets."""
    for env_path in LOCAL_ENV_FILES:
        if not env_path.exists() or not env_path.is_file():
            continue
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key in ELEVENLABS_ENV_KEYS and not os.environ.get(key):
                os.environ[key] = _strip_env_value(value)


def elevenlabs_agent_id(env: dict[str, str] | None = None) -> str:
    if env is None:
        load_local_elevenlabs_env()
    source = env or os.environ
    return (source.get("ELEVENLABS_AGENT_ID") or DEFAULT_ELEVENLABS_AGENT_ID).strip()


def elevenlabs_api_key_present(env: dict[str, str] | None = None) -> bool:
    if env is None:
        load_local_elevenlabs_env()
    source = env or os.environ
    return bool((source.get("ELEVENLABS_API_KEY") or "").strip())


def elevenlabs_env_fingerprint(env: dict[str, str] | None = None) -> str:
    """Return a non-secret cache key for the active ElevenLabs configuration."""
    if env is None:
        load_local_elevenlabs_env()
    source = env or os.environ
    agent_id = (source.get("ELEVENLABS_AGENT_ID") or DEFAULT_ELEVENLABS_AGENT_ID).strip()
    api_key = (source.get("ELEVENLABS_API_KEY") or "").strip()
    digest = hashlib.sha256(f"{agent_id}:{api_key}".encode("utf-8")).hexdigest()
    return digest[:16]


def sanitize_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [sanitize_value(item) for item in list(value)[:25]]
    if isinstance(value, dict):
        return {
            str(key)[:80]: sanitize_value(val)
            for key, val in list(value.items())[:40]
            if not str(key).lower().endswith(("key", "secret", "token", "password"))
        }
    return str(value)


def sanitize_mapping(payload: dict[str, Any] | None, allowed_fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    clean: dict[str, Any] = {}
    for field in allowed_fields:
        if field in payload:
            clean[field] = sanitize_value(payload.get(field))
    return clean


def build_roxy_personalization(profile: dict[str, Any] | None, page_context: dict[str, Any] | None) -> dict[str, Any]:
    clean_profile = sanitize_mapping(profile, SAFE_PROFILE_FIELDS)
    clean_context = sanitize_mapping(page_context, SAFE_CONTEXT_FIELDS)
    display_name = (
        clean_profile.get("user_name")
        or clean_profile.get("name")
        or clean_profile.get("username")
        or "Trader"
    )
    language = clean_profile.get("preferred_language") or clean_profile.get("language") or "es"
    return {
        "user": clean_profile,
        "context": clean_context,
        "assistant_rules": {
            "display_name": display_name,
            "preferred_language": language,
            "role": "Roxy Trading, asistente de voz y profesora de trading dentro de la plataforma.",
            "must_do": [
                "Saludar al usuario por su nombre cuando sea natural.",
                "Guiar paso a paso segun la pagina o modulo visible.",
                "Explicar riesgo, stop loss, tamano de posicion y paper trading con claridad.",
                "Usar tono educativo en Classroom y tono operativo prudente en graficas/watchlist.",
            ],
            "must_not_do": [
                "No prometer ganancias.",
                "No presentarse como asesora financiera licenciada.",
                "No ordenar operaciones con dinero real.",
                "No pedir ni revelar API keys, tokens, passwords o secretos.",
            ],
        },
    }


def get_conversation_signed_url(
    *,
    agent_id: str | None = None,
    env: dict[str, str] | None = None,
    timeout_seconds: float = 8.0,
) -> ElevenLabsRoxySession:
    if env is None:
        load_local_elevenlabs_env()
    source = env or os.environ
    resolved_agent_id = (agent_id or elevenlabs_agent_id(source)).strip()
    api_key = (source.get("ELEVENLABS_API_KEY") or "").strip()
    generated_at = datetime.now(timezone.utc).isoformat()
    if not resolved_agent_id:
        return ElevenLabsRoxySession(agent_id="", configured=False, error="Missing ELEVENLABS_AGENT_ID", generated_at=generated_at)
    if not api_key:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error="Missing ELEVENLABS_API_KEY",
            generated_at=generated_at,
        )
    try:
        response = requests.get(
            ELEVENLABS_SIGNED_URL_ENDPOINT,
            params={"agent_id": resolved_agent_id},
            headers={"xi-api-key": api_key},
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error=f"ElevenLabs request failed: {exc}",
            generated_at=generated_at,
        )
    if response.status_code >= 400:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error=f"ElevenLabs signed URL error {response.status_code}",
            generated_at=generated_at,
        )
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    signed_url = str(payload.get("signed_url") or payload.get("signedUrl") or "").strip()
    if not signed_url:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error="ElevenLabs did not return a signed_url",
            generated_at=generated_at,
        )
    return ElevenLabsRoxySession(
        agent_id=resolved_agent_id,
        signed_url=signed_url,
        configured=True,
        generated_at=generated_at,
    )


def get_conversation_token(
    *,
    agent_id: str | None = None,
    env: dict[str, str] | None = None,
    timeout_seconds: float = 8.0,
) -> ElevenLabsRoxySession:
    """Create a short-lived server-side token for ElevenLabs WebRTC clients."""
    if env is None:
        load_local_elevenlabs_env()
    source = env or os.environ
    resolved_agent_id = (agent_id or elevenlabs_agent_id(source)).strip()
    api_key = (source.get("ELEVENLABS_API_KEY") or "").strip()
    generated_at = datetime.now(timezone.utc).isoformat()
    if not resolved_agent_id:
        return ElevenLabsRoxySession(agent_id="", configured=False, error="Missing ELEVENLABS_AGENT_ID", generated_at=generated_at)
    if not api_key:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error="Missing ELEVENLABS_API_KEY",
            generated_at=generated_at,
        )
    try:
        response = requests.get(
            ELEVENLABS_CONVERSATION_TOKEN_ENDPOINT,
            params={"agent_id": resolved_agent_id},
            headers={"xi-api-key": api_key},
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error=f"ElevenLabs token request failed: {exc}",
            generated_at=generated_at,
        )
    if response.status_code >= 400:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error=f"ElevenLabs token error {response.status_code}",
            generated_at=generated_at,
        )
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    token = str(payload.get("token") or payload.get("conversation_token") or payload.get("conversationToken") or "").strip()
    if not token:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error="ElevenLabs did not return a token",
            generated_at=generated_at,
        )
    return ElevenLabsRoxySession(
        agent_id=resolved_agent_id,
        conversation_token=token,
        configured=True,
        generated_at=generated_at,
    )
