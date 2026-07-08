#!/usr/bin/env python3
from __future__ import annotations

import getpass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env.local"
AGENT_ID = "agent_6101kwchebzdf91rfk9757wq0mk4"
MANAGED_KEYS = {"ELEVENLABS_AGENT_ID", "ELEVENLABS_API_KEY"}


def read_existing_lines() -> list[str]:
    if not ENV_PATH.exists():
        return []
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def without_managed_keys(lines: list[str]) -> list[str]:
    clean: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key not in MANAGED_KEYS:
            clean.append(line)
    return clean


def main() -> int:
    print("Configurar ElevenLabs para Roxy Trading localmente.")
    print("La clave se guardara en .env.local, que no debe subirse a Git.")
    api_key = getpass.getpass("ELEVENLABS_API_KEY: ").strip()
    if not api_key:
        print("Cancelado: no se recibio ELEVENLABS_API_KEY.")
        return 1

    lines = without_managed_keys(read_existing_lines())
    if lines and lines[-1].strip():
        lines.append("")
    lines.extend(
        [
            "# ElevenLabs Roxy Trading voice/chat assistant",
            f"ELEVENLABS_AGENT_ID={AGENT_ID}",
            f"ELEVENLABS_API_KEY={api_key}",
        ]
    )
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        ENV_PATH.chmod(0o600)
    except OSError:
        pass
    print("Listo: ElevenLabs quedo configurado localmente para Roxy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
