from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_compact_json(path: str | Path, payload: Any, *, prefix: str | None = None) -> None:
    """Replace JSON atomically; a full disk must never truncate saved data."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    temp_name: str | None = None
    try:
        handle, temp_name = tempfile.mkstemp(
            prefix=prefix or f".{target.name}.", suffix=".tmp", dir=str(target.parent)
        )
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, target)
        temp_name = None
    finally:
        if temp_name:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
