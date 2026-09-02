from __future__ import annotations

import errno
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_compact_json(path: str | Path, payload: Any, *, prefix: str | None = None) -> None:
    """Write compact JSON atomically, with an ENOSPC recovery path.

    The normal path keeps the existing crash-safe temp-file replacement. If a
    full persistent disk cannot allocate that second copy, the compact payload
    is written over the existing pretty-printed file. Truncating the old file
    releases its blocks first, so no user records or media need to be deleted.
    """

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
    except OSError as exc:
        if temp_name:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            temp_name = None
        if exc.errno != errno.ENOSPC:
            raise
        with target.open("w", encoding="utf-8") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if temp_name:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
