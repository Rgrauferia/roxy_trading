from __future__ import annotations

import os
from pathlib import Path


BLOCKED_PATH_PARTS = {
    ".env",
    ".ssh",
    ".gnupg",
    "keychain",
}

BLOCKED_SUFFIXES = {
    ".key",
    ".pem",
    ".p12",
    ".p8",
    ".crt",
    ".cer",
}


def is_safe_read_path(path_value: str) -> tuple[bool, str]:
    path = Path(path_value).expanduser()
    lower_parts = {part.lower() for part in path.parts}
    if lower_parts & BLOCKED_PATH_PARTS:
        return False, "Roxy Desktop Helper bloquea archivos de secretos y credenciales."
    if path.suffix.lower() in BLOCKED_SUFFIXES:
        return False, "Roxy Desktop Helper bloquea llaves privadas y certificados."
    return True, "Ruta permitida para revision segura."


def desktop_capabilities() -> dict[str, bool]:
    def enabled(name: str) -> bool:
        return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}

    return {
        "roxy_os_commands": True,
        "screen_summary": enabled("ROXY_DESKTOP_ALLOW_SCREEN_CAPTURE"),
        "screen_control": False,
        "file_read": enabled("ROXY_DESKTOP_ALLOW_FILE_READ"),
        "browser_control": enabled("ROXY_DESKTOP_ALLOW_BROWSER_OPEN"),
        "system_write": False,
    }
