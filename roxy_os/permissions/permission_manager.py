from __future__ import annotations

import re
from typing import Any

from roxy_os.models import PermissionDecision


HIGH_RISK_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bsudo\b",
    r"\bgit\s+push\b",
    r"\bdeploy\b",
    r"\bcomprar\b.*\b(real|dinero)\b",
    r"\boper(a|ar|e)\b.*\b(real|dinero)\b",
    r"\btrade\b.*\breal\b",
    r"\benviar\b.*\b(dinero|email|correo)\b",
    r"\bfirmar\b",
    r"\bborrar\b.*\b(archivo|todo|documento)\b",
    r"\bdelete\b",
]


MEDIUM_RISK_INTENTS = {
    "screen_control",
    "browser_action",
    "home_control",
    "taxes_assist",
    "code_task",
    "reader_request",
}

SAFE_INTENTS = {
    "general",
    "memory_recall",
    "shopping_add",
    "shopping_query",
    "calendar_query",
    "trading_scan",
    "academy_query",
    "screen_summary",
    "weather_query",
    "documents_query",
    "email_query",
}


class PermissionManager:
    def decide(self, *, intent: str, text: str, context: dict[str, Any] | None = None) -> PermissionDecision:
        normalized = text.lower()
        for pattern in HIGH_RISK_PATTERNS:
            if re.search(pattern, normalized):
                return PermissionDecision(
                    allowed=False,
                    mode="blocked",
                    risk_level="high",
                    confirmation_required=True,
                    reason="La solicitud parece sensible o destructiva y requiere aprobacion explicita fuera del modo autonomo.",
                )

        context = context or {}
        allowed_permissions = set(context.get("allowed_permissions") or [])

        if intent in MEDIUM_RISK_INTENTS:
            permission_name = self.required_permission(intent)
            if permission_name and permission_name in allowed_permissions:
                return PermissionDecision(
                    allowed=True,
                    mode="autopilot_safe",
                    risk_level="medium",
                    confirmation_required=False,
                    reason=f"Permiso {permission_name} ya autorizado para esta sesion.",
                )
            return PermissionDecision(
                allowed=True,
                mode="ask_before_action",
                risk_level="medium",
                confirmation_required=True,
                reason=f"Roxy puede preparar la accion, pero debe pedir permiso antes de ejecutar {permission_name}.",
            )

        if intent in SAFE_INTENTS:
            return PermissionDecision(
                allowed=True,
                mode="autopilot_safe",
                risk_level="low",
                confirmation_required=False,
                reason="Accion segura permitida.",
            )

        return PermissionDecision(
            allowed=True,
            mode="ask_before_action",
            risk_level="medium",
            confirmation_required=True,
            reason="Intento no clasificado; Roxy debe pedir confirmacion antes de actuar.",
        )

    def required_permission(self, intent: str) -> str | None:
        return {
            "screen_summary": "screen_read",
            "screen_control": "screen_control",
            "browser_action": "browser",
            "home_control": "smart_home",
            "code_task": "terminal",
            "taxes_assist": "tax_documents",
            "reader_request": "file_read",
        }.get(intent)
