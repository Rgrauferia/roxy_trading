from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


UI_STATE_SCHEMA_VERSION = 3


def normalize_ui_state_user(value: Any) -> str:
    user = re.sub(r"[^a-zA-Z0-9_.@-]+", "_", str(value or "local_user").strip().lower()).strip("_")
    return user[:96] or "local_user"


def normalize_ui_state(payload: Any) -> dict[str, str]:
    row = payload if isinstance(payload, dict) else {}
    return {
        "symbol": str(row.get("symbol") or "").strip().upper(),
        "market": str(row.get("market") or "").strip().lower(),
        "timeframe": str(row.get("timeframe") or row.get("tf") or "").strip().lower(),
        "page": str(row.get("page") or row.get("view") or "").strip(),
    }


def _ui_state_record(payload: Any) -> dict[str, Any]:
    row = payload if isinstance(payload, dict) else {}
    state = row.get("state") if isinstance(row.get("state"), dict) else row
    return {
        "state": normalize_ui_state(state),
        "revision": max(0, int(row.get("revision") or 0)),
        "updated_at": str(row.get("updated_at") or ""),
    }


class UIStateStore:
    """Small durable store for per-user navigation context.

    Version 1 was a single top-level state. It is retained only for the local
    user during migration so another authenticated user cannot inherit it.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "schema_version": UI_STATE_SCHEMA_VERSION,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "users": {},
        }

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return self._empty()
        if not isinstance(raw, dict):
            return self._empty()
        if isinstance(raw.get("users"), dict):
            raw["schema_version"] = UI_STATE_SCHEMA_VERSION
            return raw
        legacy = normalize_ui_state(raw)
        payload = self._empty()
        if legacy["symbol"]:
            payload["users"]["local_user"] = legacy
        return payload

    def read(self, user_id: Any) -> dict[str, str]:
        payload = self._read_unlocked()
        row = payload.get("users", {}).get(normalize_ui_state_user(user_id), {})
        return _ui_state_record(row)["state"] if isinstance(row, dict) and row else {}

    def snapshot(self, user_id: Any) -> dict[str, Any]:
        payload = self._read_unlocked()
        user_key = normalize_ui_state_user(user_id)
        row = payload.get("users", {}).get(user_key, {})
        record = _ui_state_record(row) if isinstance(row, dict) and row else _ui_state_record({})
        return {"user_id": user_key, **record, "source": str(self.path)}

    def write(self, user_id: Any, state: dict[str, Any]) -> dict[str, str]:
        user_key = normalize_ui_state_user(user_id)
        normalized = normalize_ui_state(state)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            try:
                self.lock_path.chmod(0o600)
            except OSError:
                pass
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._read_unlocked()
                existing = _ui_state_record(payload.setdefault("users", {}).get(user_key, {}))
                revision = existing["revision"] + (1 if existing["state"] != normalized else 0)
                updated_at = (
                    datetime.now(timezone.utc).isoformat()
                    if existing["state"] != normalized
                    else existing["updated_at"]
                )
                payload["users"][user_key] = {
                    "state": normalized,
                    "revision": revision,
                    "updated_at": updated_at,
                }
                payload["schema_version"] = UI_STATE_SCHEMA_VERSION
                payload["updated_at"] = datetime.now(timezone.utc).isoformat()
                self.path.parent.mkdir(parents=True, exist_ok=True)
                handle, temp_name = tempfile.mkstemp(
                    prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent)
                )
                try:
                    with os.fdopen(handle, "w", encoding="utf-8") as stream:
                        json.dump(payload, stream, indent=2, sort_keys=True)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temp_name, self.path)
                finally:
                    try:
                        os.unlink(temp_name)
                    except FileNotFoundError:
                        pass
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        return normalized

    def replace(self, user_id: Any, state: dict[str, Any], *, expected_revision: int) -> dict[str, Any]:
        """Conditionally replace navigation state for optimistic device synchronization."""
        user_key = normalize_ui_state_user(user_id)
        normalized = normalize_ui_state(state)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            try:
                self.lock_path.chmod(0o600)
            except OSError:
                pass
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._read_unlocked()
                existing = _ui_state_record(payload.setdefault("users", {}).get(user_key, {}))
                expected = max(0, int(expected_revision))
                if existing["revision"] != expected:
                    return {
                        "updated": False,
                        "conflict": True,
                        "expected_revision": expected,
                        "current_revision": existing["revision"],
                    }
                revision = existing["revision"] + (1 if existing["state"] != normalized else 0)
                updated_at = (
                    datetime.now(timezone.utc).isoformat()
                    if existing["state"] != normalized
                    else existing["updated_at"]
                )
                payload["users"][user_key] = {
                    "state": normalized,
                    "revision": revision,
                    "updated_at": updated_at,
                }
                payload["schema_version"] = UI_STATE_SCHEMA_VERSION
                payload["updated_at"] = datetime.now(timezone.utc).isoformat()
                self.path.parent.mkdir(parents=True, exist_ok=True)
                handle, temp_name = tempfile.mkstemp(
                    prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent)
                )
                try:
                    with os.fdopen(handle, "w", encoding="utf-8") as stream:
                        json.dump(payload, stream, indent=2, sort_keys=True)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temp_name, self.path)
                finally:
                    try:
                        os.unlink(temp_name)
                    except FileNotFoundError:
                        pass
                return {"updated": True, "conflict": False, "revision": revision, "state": normalized}
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
