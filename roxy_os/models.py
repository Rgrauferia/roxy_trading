from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RoxyRequest:
    text: str
    user_id: str = "local_user"
    context: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    mode: str
    risk_level: str
    confirmation_required: bool = False
    reason: str = ""


@dataclass(frozen=True)
class AgentResult:
    agent: str
    intent: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    actions: list[dict[str, Any]] = field(default_factory=list)
    memory_writes: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class RoxyResponse:
    request_id: str
    user_id: str
    intent: str
    agent: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    actions: list[dict[str, Any]] = field(default_factory=list)
    permission: PermissionDecision | None = None
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        permission = None
        if self.permission:
            permission = {
                "allowed": self.permission.allowed,
                "mode": self.permission.mode,
                "risk_level": self.permission.risk_level,
                "confirmation_required": self.permission.confirmation_required,
                "reason": self.permission.reason,
            }
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "intent": self.intent,
            "agent": self.agent,
            "message": self.message,
            "data": self.data,
            "actions": self.actions,
            "permission": permission,
            "created_at": self.created_at,
        }
