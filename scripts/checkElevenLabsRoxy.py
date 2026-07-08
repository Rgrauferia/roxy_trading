#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.elevenlabs_roxy import (  # noqa: E402
    DEFAULT_ELEVENLABS_AGENT_ID,
    elevenlabs_agent_id,
    elevenlabs_api_key_present,
    get_conversation_signed_url,
    get_conversation_token,
)


def _status_line(label: str, configured: bool, error: str) -> str:
    if configured:
        return f"[OK] {label}: ElevenLabs entrego credencial temporal."
    clean_error = (error or "sin respuesta").replace("API_KEY", "secure key")
    return f"[FAIL] {label}: {clean_error}"


def main() -> int:
    agent_id = elevenlabs_agent_id() or DEFAULT_ELEVENLABS_AGENT_ID
    key_ready = elevenlabs_api_key_present()
    print("Roxy ElevenLabs diagnostic")
    print(f"Agent ID: {agent_id}")
    print(f"Server key configured: {'yes' if key_ready else 'no'}")

    signed = get_conversation_signed_url(agent_id=agent_id, timeout_seconds=10)
    token = get_conversation_token(agent_id=agent_id, timeout_seconds=10)
    print(_status_line("Signed URL", signed.configured, signed.error))
    print(_status_line("Conversation token", token.configured, token.error))

    if signed.configured or token.configured:
        print("Result: server-side ElevenLabs auth is ready.")
        return 0

    combined_error = f"{signed.error} {token.error}".lower()
    if "401" in combined_error:
        print(
            "Result: ElevenLabs rechazo la autenticacion. Revisa que la key no este revocada, "
            "que pertenezca a la misma cuenta/workspace del agente y que Render haya redeployado."
        )
        return 2
    if not key_ready:
        print("Result: falta ELEVENLABS_API_KEY en este entorno.")
        return 3
    print("Result: ElevenLabs no entrego sesion. Revisa red, agente y allowlist del dominio.")
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
