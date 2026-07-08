from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from roxy_os.models import utc_now


EventHandler = Callable[[dict[str, Any]], None]


class EventBus:
    """Small in-process event bus used for auditability and future automation hooks."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {"type": event_type, "payload": payload or {}, "created_at": utc_now()}
        self._events.append(event)
        for handler in self._handlers.get(event_type, []):
            handler(event)
        for handler in self._handlers.get("*", []):
            handler(event)
        return event

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        return list(reversed(self._events[-limit:]))
