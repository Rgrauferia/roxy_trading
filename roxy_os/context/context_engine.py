from __future__ import annotations

from typing import Any

from roxy_os.memory.memory_manager import RoxyMemoryManager


class ContextEngine:
    """Builds one compact context object shared by all Roxy OS agents."""

    def __init__(self, memory: RoxyMemoryManager) -> None:
        self.memory = memory

    def build(self, *, user_id: str, raw_context: dict[str, Any] | None = None) -> dict[str, Any]:
        raw_context = dict(raw_context or {})
        user_profile = raw_context.get("user_profile") if isinstance(raw_context.get("user_profile"), dict) else {}
        memories = self.memory.search(
            " ".join(
                str(raw_context.get(key, ""))
                for key in ("page", "module", "symbol", "market", "timeframe", "section")
            ),
            user_id=user_id,
            limit=5,
        )
        return {
            "user_id": user_id,
            "profile": user_profile,
            "surface": raw_context.get("surface", "unknown"),
            "page": raw_context.get("page", "unknown"),
            "module": raw_context.get("module", "home"),
            "symbol": raw_context.get("symbol"),
            "market": raw_context.get("market"),
            "timeframe": raw_context.get("timeframe"),
            "authenticated": bool(raw_context.get("authenticated")),
            "allowed_permissions": list(raw_context.get("allowed_permissions") or []),
            "related_memories": memories,
            "raw": raw_context,
        }
