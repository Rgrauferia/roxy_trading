"""Simple on-disk toggle to enable/disable a Grok-like model for clients.

This module stores a single JSON settings file `./.grok_settings.json` with
an `enabled` boolean. It exposes helpers to read and write the setting and
provides a placeholder `apply_enable_for_all()` that is where integration
with an external provider or admin API would be implemented.
"""
from __future__ import annotations

import json
from pathlib import Path

SETTINGS_PATH = Path(".grok_settings.json")


def _read_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {"enabled": False}
    try:
        return json.loads(SETTINGS_PATH.read_text())
    except Exception:
        return {"enabled": False}


def is_enabled() -> bool:
    return bool(_read_settings().get("enabled", False))


def set_enabled(enabled: bool) -> None:
    SETTINGS_PATH.write_text(json.dumps({"enabled": bool(enabled)}))


def apply_enable_for_all(enabled: bool) -> None:
    """Placeholder: here you would call provider/admin APIs to enable the model.

    Currently this writes the settings file that `is_enabled()` reads. To
    actually enable an external model for clients, add API calls here.
    """
    set_enabled(enabled)
