from __future__ import annotations

import json
import os
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


_SECRET_PATTERN = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{12,}|bearer\s+[a-z0-9._-]{12,}|(?:api[_ -]?key|password|contrase(?:n|ñ)a)\s*[:=]\s*\S+)"
)


def _clean(value: Any, limit: int = 1200) -> str:
    text = " ".join(str(value or "").split())[:limit]
    return _SECRET_PATTERN.sub("[dato privado omitido]", text)


class HomeConversationStore:
    """Small, private multi-turn memory used only inside Roxy Home."""

    def __init__(self, path: str | Path, *, max_turns: int = 12, max_people: int = 100) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.max_turns = max(2, int(max_turns))
        self.max_people = max(2, int(max_people))

    def _read(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            payload = {}
        return payload if isinstance(payload, dict) else {}

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def _mutate(self, callback: Callable[[dict[str, Any]], Any]) -> Any:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                payload = self._read()
                result = callback(payload)
                self._write(payload)
                return result
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def turns(self, owner_key: Any) -> list[dict[str, str]]:
        owner = _clean(owner_key, 160)
        rows = self._read().get("people", {}).get(owner, {}).get("turns", [])
        return deepcopy(rows[-self.max_turns :]) if isinstance(rows, list) else []

    def remember(self, owner_key: Any, *, user: str, assistant: str, topic: str = "home") -> list[dict[str, str]]:
        owner = _clean(owner_key, 160)
        if not owner:
            raise ValueError("Falta la identidad de la conversación.")

        def apply(payload: dict[str, Any]) -> list[dict[str, str]]:
            people = payload.setdefault("people", {})
            record = people.setdefault(owner, {"turns": []})
            turns = record.setdefault("turns", [])
            stamp = datetime.now(timezone.utc).isoformat()
            turns.extend(
                [
                    {"role": "user", "content": _clean(user), "topic": _clean(topic, 80), "at": stamp},
                    {"role": "assistant", "content": _clean(assistant), "topic": _clean(topic, 80), "at": stamp},
                ]
            )
            record["turns"] = turns[-self.max_turns :]
            record["updated_at"] = stamp
            if len(people) > self.max_people:
                oldest = sorted(people, key=lambda key: str(people[key].get("updated_at") or ""))
                for key in oldest[: len(people) - self.max_people]:
                    people.pop(key, None)
            return deepcopy(record["turns"])

        return self._mutate(apply)

    def pending_clarification(self, owner_key: Any) -> dict[str, Any] | None:
        """Return the unresolved Home clarification for one signed-in person."""
        owner = _clean(owner_key, 160)
        row = self._read().get("people", {}).get(owner, {}).get("pending_clarification")
        return deepcopy(row) if isinstance(row, dict) else None

    def save_clarification(self, owner_key: Any, clarification: dict[str, Any]) -> dict[str, Any]:
        owner = _clean(owner_key, 160)
        if not owner:
            raise ValueError("Falta la identidad de la conversación.")

        def apply(payload: dict[str, Any]) -> dict[str, Any]:
            people = payload.setdefault("people", {})
            record = people.setdefault(owner, {"turns": []})
            cleaned = {
                "kind": _clean(clarification.get("kind"), 80),
                "original": _clean(clarification.get("original"), 500),
                "question": _clean(clarification.get("question"), 500),
                "options": [
                    {
                        "name": _clean(option.get("name"), 120),
                        "unit": _clean(option.get("unit"), 32),
                        "aliases": [_clean(alias, 80) for alias in option.get("aliases", [])[:20]],
                    }
                    for option in clarification.get("options", [])[:8]
                    if isinstance(option, dict)
                ],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            record["pending_clarification"] = cleaned
            record["updated_at"] = cleaned["created_at"]
            return deepcopy(cleaned)

        return self._mutate(apply)

    def clear_clarification(self, owner_key: Any) -> None:
        owner = _clean(owner_key, 160)

        def apply(payload: dict[str, Any]) -> None:
            record = payload.get("people", {}).get(owner)
            if isinstance(record, dict):
                record.pop("pending_clarification", None)
                record["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._mutate(apply)
