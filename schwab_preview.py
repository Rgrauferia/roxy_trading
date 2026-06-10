from __future__ import annotations

import math
from typing import Any

from platform_router import safe_float, safe_text


SCHWAB_TRADER_BASE_URL = "https://api.schwabapi.com/trader/v1"
SCHWAB_PREVIEW_ENDPOINT_TEMPLATE = f"{SCHWAB_TRADER_BASE_URL}/accounts/{{accountHash}}/previewOrder"
SCHWAB_PLACE_ORDER_ENDPOINT_TEMPLATE = f"{SCHWAB_TRADER_BASE_URL}/accounts/{{accountHash}}/orders"


def format_schwab_price(value: Any) -> str:
    price = safe_float(value)
    if price is None or price <= 0:
        raise ValueError("Schwab order requires a positive limit price")
    return f"{price:.2f}"


def schwab_asset_type(asset_type: str) -> str:
    normalized = safe_text(asset_type).lower()
    if normalized == "stock":
        return "EQUITY"
    if normalized == "option":
        return "OPTION"
    raise ValueError(f"Schwab preview only supports stock/option, not {asset_type!r}")


def schwab_instruction(side: str) -> str:
    normalized = safe_text(side).upper()
    if normalized in {"BUY", "SELL", "BUY_TO_OPEN", "SELL_TO_CLOSE", "SELL_SHORT", "BUY_TO_COVER"}:
        return normalized
    return "BUY"


def schwab_whole_quantity(value: Any) -> int:
    qty = safe_float(value)
    if qty is None:
        raise ValueError("Schwab order requires quantity")
    whole_qty = math.floor(qty)
    if whole_qty <= 0:
        raise ValueError("Schwab order quantity rounds below 1")
    return whole_qty


def build_schwab_limit_order_payload(ticket: dict[str, Any]) -> dict[str, Any]:
    asset_type = schwab_asset_type(safe_text(ticket.get("asset_type")))
    symbol = safe_text(ticket.get("order_symbol") or ticket.get("symbol")).upper()
    if not symbol:
        raise ValueError("Schwab order requires symbol")
    quantity = schwab_whole_quantity(ticket.get("quantity"))
    payload = {
        "session": "NORMAL",
        "duration": "DAY",
        "orderType": "LIMIT",
        "price": format_schwab_price(ticket.get("entry")),
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {
                "instruction": schwab_instruction(ticket.get("side", "BUY")),
                "quantity": quantity,
                "instrument": {
                    "symbol": symbol,
                    "assetType": asset_type,
                },
            }
        ],
    }
    return payload


def build_schwab_preview(ticket: dict[str, Any], order_preview: dict[str, Any] | None = None) -> dict[str, Any]:
    platform_id = safe_text(ticket.get("platform_id"))
    asset_type = safe_text(ticket.get("asset_type")).lower()
    if platform_id != "schwab" or asset_type not in {"stock", "option"}:
        return {
            "applicable": False,
            "reason": "Schwab preview applies only to stock/option tickets routed to Charles Schwab.",
        }

    raw_qty = safe_float(ticket.get("quantity"))
    try:
        payload = build_schwab_limit_order_payload(ticket)
        builder_errors: list[str] = []
    except ValueError as exc:
        payload = {}
        builder_errors = [str(exc)]

    blockers = list((order_preview or {}).get("send_blockers") or [])
    blockers.extend(builder_errors)
    whole_qty = None
    if payload:
        whole_qty = payload["orderLegCollection"][0]["quantity"]
        if raw_qty is not None and raw_qty != whole_qty:
            blockers.append(f"Schwab quantity is whole shares/contracts only; Roxy rounded {raw_qty:.6f} to {whole_qty}.")

    return {
        "applicable": True,
        "preview_only": True,
        "http_method": "POST",
        "preview_endpoint": SCHWAB_PREVIEW_ENDPOINT_TEMPLATE,
        "future_place_order_endpoint": SCHWAB_PLACE_ORDER_ENDPOINT_TEMPLATE,
        "headers_required": [
            "Authorization: Bearer <SCHWAB_ACCESS_TOKEN>",
            "Content-Type: application/json",
            "Accept: application/json",
        ],
        "payload": payload,
        "api_preview_ready": bool(payload) and not blockers,
        "blockers": blockers,
        "guardrail": "This prepares the Schwab previewOrder request body only. Roxy does not call Schwab or place a live order from this screen.",
    }


__all__ = [
    "SCHWAB_PLACE_ORDER_ENDPOINT_TEMPLATE",
    "SCHWAB_PREVIEW_ENDPOINT_TEMPLATE",
    "SCHWAB_TRADER_BASE_URL",
    "build_schwab_limit_order_payload",
    "build_schwab_preview",
    "format_schwab_price",
    "schwab_asset_type",
    "schwab_instruction",
    "schwab_whole_quantity",
]
