from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

import requests

from roxy_trader.api_budget import ApiBudgetBlockedError, observe_api_call


DEFAULT_ELEVENLABS_AGENT_ID = "agent_6101kwchebzdf91rfk9757wq0mk4"
ELEVENLABS_SIGNED_URL_ENDPOINT = "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"
ELEVENLABS_CONVERSATION_TOKEN_ENDPOINT = "https://api.elevenlabs.io/v1/convai/conversation/token"
ELEVENLABS_ENV_KEYS = {
    "ELEVENLABS_AGENT_ID",
    "ELEVENLABS_API_KEY",
    "ROXY_ELEVENLABS_AUTH_CIRCUIT_PATH",
    "ROXY_ELEVENLABS_AUTH_RETRY_SECONDS",
}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_ENV_FILES = (PROJECT_ROOT / ".env.local", PROJECT_ROOT / ".env")
DEFAULT_ELEVENLABS_AUTH_CIRCUIT_PATH = PROJECT_ROOT / "alerts" / "elevenlabs_auth_circuit.json"
DEFAULT_ELEVENLABS_AUTH_RETRY_SECONDS = 6 * 60 * 60

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
    state: str = "UNKNOWN"
    http_status: int | None = None


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


def _auth_circuit_path(source: Mapping[str, str]) -> Path:
    configured = str(source.get("ROXY_ELEVENLABS_AUTH_CIRCUIT_PATH") or "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_ELEVENLABS_AUTH_CIRCUIT_PATH


def _auth_retry_seconds(source: Mapping[str, str]) -> int:
    try:
        configured = int(float(str(source.get("ROXY_ELEVENLABS_AUTH_RETRY_SECONDS") or "")))
    except (TypeError, ValueError):
        configured = DEFAULT_ELEVENLABS_AUTH_RETRY_SECONDS
    return max(60, min(configured, 24 * 60 * 60))


def _read_auth_circuit(
    source: Mapping[str, str],
    *,
    agent_id: str,
    generated_at: str,
) -> ElevenLabsRoxySession | None:
    path = _auth_circuit_path(source)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    if str(payload.get("state") or "").upper() != "AUTH_INVALID":
        return None
    if str(payload.get("fingerprint") or "") != elevenlabs_env_fingerprint(dict(source)):
        return None
    try:
        failed_at = datetime.fromisoformat(str(payload.get("failed_at") or "").replace("Z", "+00:00"))
        if failed_at.tzinfo is None:
            failed_at = failed_at.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    age_seconds = max(0, int((datetime.now(timezone.utc) - failed_at.astimezone(timezone.utc)).total_seconds()))
    remaining = _auth_retry_seconds(source) - age_seconds
    if remaining <= 0:
        return None
    http_status = payload.get("http_status")
    return ElevenLabsRoxySession(
        agent_id=agent_id,
        configured=False,
        error=(
            "ElevenLabs authentication circuit active; rotate credentials or retry in "
            f"{remaining}s"
        ),
        generated_at=generated_at,
        state="AUTH_INVALID",
        http_status=int(http_status) if isinstance(http_status, int) else 401,
    )


def _write_auth_circuit(
    source: Mapping[str, str],
    *,
    state: str,
    http_status: int | None,
) -> None:
    path = _auth_circuit_path(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": str(state or "UNKNOWN").upper(),
        "http_status": http_status,
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": elevenlabs_env_fingerprint(dict(source)),
        "retry_seconds": _auth_retry_seconds(source),
    }
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


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
                "Actuar siempre como Roxy Trading dentro de la plataforma de trading, classroom, graficas, watchlist y carpetas operativas.",
                "Saludar al usuario por su nombre cuando sea natural.",
                "Guiar paso a paso segun la pagina o modulo visible.",
                "Si el usuario pide mejores oportunidades, pedir o usar el modulo visible y resumir activo, direccion, entrada, stop, target, confianza, riesgo y razon.",
                "Si el usuario esta en acciones, crypto 20min, crypto 2H, crypto daily o classroom, responder con contexto de esa carpeta.",
                "Explicar indicadores, velas, precio, volumen, momentum, temporalidad y estrategia de forma practica.",
                "Explicar riesgo, stop loss, tamano de posicion y paper trading con claridad.",
                "Usar tono educativo en Classroom y tono operativo prudente en graficas/watchlist.",
            ],
            "must_not_do": [
                "No hablar de taxes, notaria, DMV, seguros ni servicios externos salvo que el usuario lo pida explicitamente.",
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
        return ElevenLabsRoxySession(agent_id="", configured=False, error="Missing ELEVENLABS_AGENT_ID", generated_at=generated_at, state="NOT_CONFIGURED")
    if not api_key:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error="Missing ELEVENLABS_API_KEY",
            generated_at=generated_at,
            state="NOT_CONFIGURED",
        )
    circuit = _read_auth_circuit(source, agent_id=resolved_agent_id, generated_at=generated_at)
    if circuit is not None:
        return circuit
    try:
        with observe_api_call("elevenlabs", "signed_url") as observation:
            response = requests.get(
                ELEVENLABS_SIGNED_URL_ENDPOINT,
                params={"agent_id": resolved_agent_id},
                headers={"xi-api-key": api_key},
                timeout=timeout_seconds,
            )
            observation.set_http_status(response.status_code)
    except requests.RequestException as exc:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error=f"ElevenLabs request failed: {exc}",
            generated_at=generated_at,
            state="PROVIDER_UNAVAILABLE",
        )
    except ApiBudgetBlockedError as exc:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error=f"ElevenLabs cooldown activo; reintentar en {exc.retry_after_seconds}s",
            generated_at=generated_at,
            state="RATE_LIMITED",
        )
    if response.status_code >= 400:
        state = "AUTH_INVALID" if response.status_code in {401, 403} else "RATE_LIMITED" if response.status_code == 429 else "PROVIDER_ERROR"
        if state == "AUTH_INVALID":
            _write_auth_circuit(source, state=state, http_status=response.status_code)
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error=f"ElevenLabs signed URL error {response.status_code}",
            generated_at=generated_at,
            state=state,
            http_status=response.status_code,
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
            state="INVALID_RESPONSE",
        )
    return ElevenLabsRoxySession(
        agent_id=resolved_agent_id,
        signed_url=signed_url,
        configured=True,
        generated_at=generated_at,
        state="CONNECTED",
        http_status=response.status_code,
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
        return ElevenLabsRoxySession(agent_id="", configured=False, error="Missing ELEVENLABS_AGENT_ID", generated_at=generated_at, state="NOT_CONFIGURED")
    if not api_key:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error="Missing ELEVENLABS_API_KEY",
            generated_at=generated_at,
            state="NOT_CONFIGURED",
        )
    circuit = _read_auth_circuit(source, agent_id=resolved_agent_id, generated_at=generated_at)
    if circuit is not None:
        return circuit
    try:
        with observe_api_call("elevenlabs", "conversation_token") as observation:
            response = requests.get(
                ELEVENLABS_CONVERSATION_TOKEN_ENDPOINT,
                params={"agent_id": resolved_agent_id},
                headers={"xi-api-key": api_key},
                timeout=timeout_seconds,
            )
            observation.set_http_status(response.status_code)
    except requests.RequestException as exc:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error=f"ElevenLabs token request failed: {exc}",
            generated_at=generated_at,
            state="PROVIDER_UNAVAILABLE",
        )
    except ApiBudgetBlockedError as exc:
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error=f"ElevenLabs cooldown activo; reintentar en {exc.retry_after_seconds}s",
            generated_at=generated_at,
            state="RATE_LIMITED",
        )
    if response.status_code >= 400:
        state = "AUTH_INVALID" if response.status_code in {401, 403} else "RATE_LIMITED" if response.status_code == 429 else "PROVIDER_ERROR"
        if state == "AUTH_INVALID":
            _write_auth_circuit(source, state=state, http_status=response.status_code)
        return ElevenLabsRoxySession(
            agent_id=resolved_agent_id,
            configured=False,
            error=f"ElevenLabs token error {response.status_code}",
            generated_at=generated_at,
            state=state,
            http_status=response.status_code,
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
            state="INVALID_RESPONSE",
        )
    return ElevenLabsRoxySession(
        agent_id=resolved_agent_id,
        conversation_token=token,
        configured=True,
        generated_at=generated_at,
        state="CONNECTED",
        http_status=response.status_code,
    )
