from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4

from roxy_os.models import utc_now


TOKEN_RE = re.compile(r"[a-zA-Z0-9ÁÉÍÓÚÜÑáéíóúüñ_-]+")
STOPWORDS = {
    "a",
    "al",
    "and",
    "con",
    "de",
    "del",
    "el",
    "en",
    "for",
    "la",
    "las",
    "los",
    "me",
    "mi",
    "of",
    "or",
    "para",
    "por",
    "que",
    "roxy",
    "the",
    "to",
    "un",
    "una",
    "y",
}


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_RE.findall(text or "")
        if len(token) > 2 and token.lower() not in STOPWORDS
    }


class RoxyMemoryManager:
    """Local durable memory store for the first Roxy OS loop.

    This is intentionally simple and dependency-free. It can be replaced by
    PostgreSQL + pgvector later without changing the orchestrator contract.
    """

    def __init__(self, path: str | Path = "data/roxy_os_memory.json") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._store: dict[str, Any] | None = None

    def remember(
        self,
        *,
        user_id: str,
        memory_type: str,
        title: str,
        content: str,
        source: str,
        tags: list[str] | None = None,
        importance: int = 3,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        store = self._load()
        memory = {
            "id": uuid4().hex,
            "user_id": user_id,
            "type": memory_type,
            "title": title.strip(),
            "content": content.strip(),
            "source": source.strip(),
            "tags": tags or [],
            "importance": max(1, min(5, int(importance))),
            "metadata": metadata or {},
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        store["memories"].append(memory)
        self._save(store)
        return memory

    def search(
        self,
        query: str,
        *,
        user_id: str,
        memory_type: str | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        store = self._load()
        query_tokens = _tokens(query)
        if not query_tokens:
            return []

        scored: list[tuple[float, dict[str, Any]]] = []
        for memory in store["memories"]:
            if memory.get("user_id") != user_id:
                continue
            if memory_type and memory.get("type") != memory_type:
                continue
            text = " ".join(
                [
                    str(memory.get("title", "")),
                    str(memory.get("content", "")),
                    " ".join(memory.get("tags") or []),
                ]
            )
            hits = len(query_tokens & _tokens(text))
            if hits:
                score = hits + float(memory.get("importance", 1)) * 0.1
                scored.append((score, memory))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [dict(item) | {"score": round(score, 2)} for score, item in scored[: max(1, int(limit))]]

    def list_memories(
        self,
        *,
        user_id: str,
        memory_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        store = self._load()
        rows = [
            memory
            for memory in store["memories"]
            if memory.get("user_id") == user_id and (not memory_type or memory.get("type") == memory_type)
        ]
        rows.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return [dict(item) for item in rows[: max(1, int(limit))]]

    def delete_memory(self, *, user_id: str, memory_id: str) -> bool:
        store = self._load()
        before = len(store["memories"])
        store["memories"] = [
            memory
            for memory in store["memories"]
            if not (memory.get("user_id") == user_id and memory.get("id") == memory_id)
        ]
        changed = len(store["memories"]) != before
        if changed:
            self._save(store)
        return changed

    def _load(self) -> dict[str, Any]:
        if self._store is not None:
            return self._store
        if not self.path.exists():
            self._store = {"version": 1, "memories": []}
            self._save(self._store)
            return self._store
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {"version": 1, "memories": []}
        if not isinstance(raw, dict):
            raw = {"version": 1, "memories": []}
        if not isinstance(raw.get("memories"), list):
            raw["memories"] = []
        self._store = raw
        return self._store

    def _save(self, store: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
            json.dump(store, handle, ensure_ascii=False, indent=2)
            temp_path = Path(handle.name)
        temp_path.replace(self.path)
        self._store = store
