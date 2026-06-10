from __future__ import annotations

import os
from typing import Any, Mapping

from platform_router import PLATFORM_PROFILES, safe_float, safe_text


LIVE_EXECUTION_FLAG = "ROXY_ENABLE_LIVE_BROKER_EXECUTION"

BROKER_ADAPTERS_IMPLEMENTED: dict[str, bool] = {
    "crypto_com": False,
    "schwab": False,
    "webull": False,
}

BROKER_ENV_KEYS: dict[str, tuple[str, ...]] = {
    "crypto_com": (
        "CRYPTO_COM_API_KEY",
        "CRYPTO_COM_API_SECRET",
    ),
    "schwab": (
        "SCHWAB_CLIENT_ID",
        "SCHWAB_CLIENT_SECRET",
        "SCHWAB_REDIRECT_URI",
        "SCHWAB_ACCESS_TOKEN",
        "SCHWAB_ACCOUNT_HASH",
    ),
    "webull": (
        "WEBULL_APP_KEY",
        "WEBULL_APP_SECRET",
        "WEBULL_ACCESS_TOKEN",
        "WEBULL_ACCOUNT_ID",
    ),
}


def _env_value(env: Mapping[str, str] | None, key: str) -> str:
    source = env if env is not None else os.environ
    return safe_text(source.get(key))


def live_execution_requested(env: Mapping[str, str] | None = None) -> bool:
    value = _env_value(env, LIVE_EXECUTION_FLAG).lower()
    return value in {"1", "true", "yes", "on", "enabled"}


def platform_connection_status(platform_id: str, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    profile = PLATFORM_PROFILES.get(platform_id, PLATFORM_PROFILES["schwab"])
    required = BROKER_ENV_KEYS.get(platform_id, ())
    present = [key for key in required if _env_value(env, key)]
    missing = [key for key in required if key not in present]
    configured = not missing and bool(required)
    live_enabled = live_execution_requested(env)
    if not configured:
        mode = "NEEDS_CREDENTIALS"
    elif not live_enabled:
        mode = "PREVIEW_ONLY"
    else:
        mode = "LIVE_ARMED"
    return {
        "platform_id": platform_id,
        "platform": profile["name"],
        "required_keys": list(required),
        "present_keys": present,
        "missing_keys": missing,
        "configured": configured,
        "live_enabled": live_enabled,
        "mode": mode,
    }


def broker_adapter_status(platform_id: str) -> dict[str, Any]:
    profile = PLATFORM_PROFILES.get(platform_id, PLATFORM_PROFILES["schwab"])
    implemented = BROKER_ADAPTERS_IMPLEMENTED.get(platform_id, False)
    return {
        "platform_id": platform_id,
        "platform": profile["name"],
        "implemented": implemented,
        "status": "IMPLEMENTED" if implemented else "PREVIEW_ONLY",
        "reason": (
            "Live broker adapter is implemented behind the execution gate."
            if implemented
            else "No live broker adapter is implemented yet; Roxy prepares manual and preview payloads only."
        ),
    }


def required_credentials_table(env: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    rows = []
    for platform_id in PLATFORM_PROFILES:
        status = platform_connection_status(platform_id, env=env)
        rows.append(
            {
                "platform": status["platform"],
                "mode": status["mode"],
                "configured": status["configured"],
                "live_enabled": status["live_enabled"],
                "missing": ", ".join(status["missing_keys"]) if status["missing_keys"] else "-",
            }
        )
    return rows


def build_manual_order(ticket: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform": ticket.get("platform"),
        "asset_type": ticket.get("asset_type"),
        "symbol": ticket.get("order_symbol") or ticket.get("symbol"),
        "side": ticket.get("side", "BUY"),
        "order_type": ticket.get("order_type", "LIMIT"),
        "time_in_force": ticket.get("time_in_force", "DAY"),
        "limit_price": safe_float(ticket.get("entry")),
        "stop_price": safe_float(ticket.get("stop")),
        "target_price": safe_float(ticket.get("target_price")),
        "quantity": safe_float(ticket.get("quantity")),
        "max_risk_dollars": safe_float(ticket.get("risk_dollars")),
    }


def execution_blockers(ticket: dict[str, Any], status: dict[str, Any]) -> list[str]:
    blockers = []
    if ticket.get("status") != "READY_TO_PREVIEW":
        blockers.append(f"Roxy status is {ticket.get('status')}; only READY_TO_PREVIEW can be armed.")
    if not status["configured"]:
        blockers.append("Platform credentials are missing.")
    if not status["live_enabled"]:
        blockers.append(f"{LIVE_EXECUTION_FLAG}=1 is not set.")
    if (safe_float(ticket.get("quantity")) or 0) <= 0:
        blockers.append("Quantity is zero or unavailable.")
    if safe_float(ticket.get("entry")) is None:
        blockers.append("Entry price is unavailable.")
    return blockers


def preview_payload_ready(ticket: dict[str, Any]) -> bool:
    return (
        ticket.get("status") == "READY_TO_PREVIEW"
        and (safe_float(ticket.get("quantity")) or 0) > 0
        and safe_float(ticket.get("entry")) is not None
    )


def preview_readiness_score(ticket: dict[str, Any], status: dict[str, Any]) -> int:
    score = 0
    if ticket.get("status") == "READY_TO_PREVIEW":
        score += 25
    elif ticket.get("status") == "WAIT_FOR_CONFIRMATION":
        score += 10
    if safe_float(ticket.get("entry")) is not None:
        score += 20
    if (safe_float(ticket.get("quantity")) or 0) > 0:
        score += 20
    if status["configured"]:
        score += 25
    if status["live_enabled"]:
        score += 10
    return int(max(0, min(100, score)))


def build_order_preview(
    ticket: dict[str, Any],
    env: Mapping[str, str] | None = None,
    connection_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    platform_id = safe_text(ticket.get("platform_id")) or "schwab"
    status = connection_status or platform_connection_status(platform_id, env=env)
    manual_order = build_manual_order(ticket)
    blockers = execution_blockers(ticket, status)
    adapter = broker_adapter_status(platform_id)
    credential_gate_ready = not blockers
    api_send_allowed = credential_gate_ready and adapter["implemented"]
    return {
        "preview_only": True,
        "platform": status["platform"],
        "platform_id": platform_id,
        "mode": status["mode"],
        "manual_order": manual_order,
        "preview_payload_ready": preview_payload_ready(ticket),
        "credential_gate_ready": credential_gate_ready,
        "api_send_allowed": api_send_allowed,
        "live_send_ready": api_send_allowed,
        "readiness_score": preview_readiness_score(ticket, status),
        "adapter_status": adapter,
        "send_blockers": blockers,
        "credential_status": {
            "configured": status["configured"],
            "live_enabled": status["live_enabled"],
            "missing_keys": status["missing_keys"],
        },
        "guardrail": "Roxy does not send live broker orders from this screen. This preview is for manual review and future adapter wiring.",
    }


__all__ = [
    "BROKER_ENV_KEYS",
    "BROKER_ADAPTERS_IMPLEMENTED",
    "LIVE_EXECUTION_FLAG",
    "broker_adapter_status",
    "build_manual_order",
    "build_order_preview",
    "execution_blockers",
    "live_execution_requested",
    "platform_connection_status",
    "preview_payload_ready",
    "preview_readiness_score",
    "required_credentials_table",
]
