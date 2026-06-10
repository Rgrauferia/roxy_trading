from __future__ import annotations

import math
from typing import Any

import pandas as pd


PLATFORM_PROFILES: dict[str, dict[str, Any]] = {
    "crypto_com": {
        "name": "Crypto.com",
        "assets": ["crypto"],
        "api_status": "API disponible despues de configurar key/secret",
        "auth": "Exchange API key/secret con permiso de trading",
        "best_for": "Crypto spot y ejecucion crypto 24h",
        "manual_steps": [
            "Abre Crypto.com Exchange.",
            "Busca el par que muestra Roxy.",
            "Previsualiza una orden limit en la entrada o mejor.",
            "Coloca stop/target manualmente o con orden avanzada si la plataforma lo permite.",
            "Registra fill y resultado en la memoria de Roxy.",
        ],
    },
    "schwab": {
        "name": "Charles Schwab",
        "assets": ["stock", "option"],
        "api_status": "Trader API requiere cuenta developer, OAuth y aprobacion",
        "auth": "Schwab Developer app + tokens OAuth",
        "best_for": "Acciones, ETFs y opciones listadas",
        "manual_steps": [
            "Abre Schwab o thinkorswim.",
            "Escribe la accion o contrato de opcion que muestra Roxy.",
            "Previsualiza la orden primero.",
            "Usa orden limit; agrega stop/target despues del fill si la plataforma exige legs separadas.",
            "Registra fill, stop y salida en la memoria de Roxy.",
        ],
    },
    "webull": {
        "name": "Webull",
        "assets": ["stock", "option", "crypto"],
        "api_status": "OpenAPI disponible para clientes elegibles",
        "auth": "Webull OpenAPI app/token setup",
        "best_for": "Acciones, opciones y crypto si tu cuenta es elegible",
        "manual_steps": [
            "Abre Webull.",
            "Busca el simbolo o contrato de opcion que muestra Roxy.",
            "Previsualiza la orden y confirma buying power.",
            "Usa orden limit; verifica horario extendido/24h antes de enviar.",
            "Registra el resultado en la memoria de Roxy.",
        ],
    },
}

DEFAULT_PLATFORM_BY_ASSET = {
    "crypto": "crypto_com",
    "stock": "schwab",
    "option": "schwab",
}


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value or "").strip()


def platform_profile(platform_id: str) -> dict[str, Any]:
    return PLATFORM_PROFILES.get(platform_id, PLATFORM_PROFILES["schwab"])


def is_trade_ready(row: dict[str, Any]) -> bool:
    action = safe_text(row.get("action") or row.get("ai_action")).upper()
    signal = safe_text(row.get("signal")).upper()
    decision = safe_text(row.get("decision") or row.get("trade_decision")).upper()
    return action == "ALERT" or (signal == "BUY" and decision.startswith("TRADE_FOR"))


def infer_asset_type(row: dict[str, Any], preferred_product: str | None = None) -> str:
    preferred = safe_text(preferred_product).lower()
    if preferred in {"stock", "option", "crypto"}:
        return preferred
    market = safe_text(row.get("market")).lower()
    symbol = safe_text(row.get("symbol")).upper()
    if "crypto" in market or "/" in symbol:
        return "crypto"
    if safe_text(row.get("option") or row.get("contractSymbol")):
        return "option"
    return "stock"


def route_platform(
    row: dict[str, Any],
    *,
    preferred_product: str | None = None,
    preferred_crypto: str = "crypto_com",
    preferred_stock: str = "schwab",
    preferred_option: str = "schwab",
) -> str:
    asset_type = infer_asset_type(row, preferred_product=preferred_product)
    requested = {
        "crypto": preferred_crypto,
        "stock": preferred_stock,
        "option": preferred_option,
    }.get(asset_type) or DEFAULT_PLATFORM_BY_ASSET.get(asset_type, "schwab")
    profile = platform_profile(requested)
    if asset_type in profile["assets"]:
        return requested
    return DEFAULT_PLATFORM_BY_ASSET.get(asset_type, "schwab")


def position_size_from_risk(entry: Any, stop: Any, risk_dollars: float, *, allow_fractional: bool) -> float | None:
    entry_value = safe_float(entry)
    stop_value = safe_float(stop)
    if entry_value is None or stop_value is None or entry_value <= 0 or stop_value <= 0:
        return None
    unit_risk = abs(entry_value - stop_value)
    if unit_risk <= 0:
        return None
    qty = risk_dollars / unit_risk
    if allow_fractional:
        return round(max(qty, 0.0), 6)
    return float(max(math.floor(qty), 0))


def ticket_status(row: dict[str, Any]) -> tuple[str, str]:
    signal = safe_text(row.get("signal")).upper()
    decision = safe_text(row.get("decision") or row.get("trade_decision")).upper()
    if is_trade_ready(row):
        return "READY_TO_PREVIEW", "Roxy permite preparar el ticket despues de confirmar buying power en la plataforma."
    if signal == "AVOID" or decision.startswith("NO_TRADE"):
        return "NO_TRADE", "No coloques esta orden. Espera que Roxy vuelva a WATCH o BUY."
    return "WAIT_FOR_CONFIRMATION", "Prepara el ticket solamente; falta entrada 15m y confirmacion 1h."


def execution_context_gate(
    asset_type: str,
    *,
    source_freshness: dict[str, Any] | None = None,
    market_session: dict[str, Any] | None = None,
) -> tuple[str, str]:
    freshness = source_freshness or {}
    if freshness and not freshness.get("alerts_allowed", True):
        return "BLOCKED_STALE_DATA", "Refresca datos live/confluencia antes de preparar cualquier preview."

    session = market_session or {}
    if asset_type in {"stock", "option"} and session and not session.get("stock_alerts_allowed", True):
        stock_session = safe_text(session.get("stock_session")) or "closed"
        return "BLOCKED_MARKET_CLOSED", f"Acciones/opciones estan en {stock_session}; usa Roxy para estudio hasta que reabra."

    return "OK", "Contexto aceptable para preparar ticket manual; no envia orden real."


def build_platform_ticket(
    row: dict[str, Any],
    *,
    account_equity: float = 500.0,
    risk_per_trade_pct: float = 0.01,
    preferred_product: str | None = None,
    preferred_crypto: str = "crypto_com",
    preferred_stock: str = "schwab",
    preferred_option: str = "schwab",
    source_freshness: dict[str, Any] | None = None,
    market_session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    asset_type = infer_asset_type(row, preferred_product=preferred_product)
    platform_id = route_platform(
        row,
        preferred_product=asset_type,
        preferred_crypto=preferred_crypto,
        preferred_stock=preferred_stock,
        preferred_option=preferred_option,
    )
    profile = platform_profile(platform_id)
    status, status_reason = ticket_status(row)
    gate_status, gate_reason = execution_context_gate(
        asset_type,
        source_freshness=source_freshness,
        market_session=market_session,
    )
    if status == "READY_TO_PREVIEW" and gate_status != "OK":
        status = gate_status
        status_reason = gate_reason
    entry = safe_float(row.get("entry"))
    stop = safe_float(row.get("stop"))
    target_pct = safe_float(row.get("target_pct") or row.get("recommended_target_pct"))
    target_price = safe_float(row.get("target_price") or row.get("recommended_target_price"))
    if target_price is None and entry is not None and target_pct is not None:
        target_price = entry * (1.0 + target_pct)
    risk_dollars = max(0.0, float(account_equity or 0.0) * float(risk_per_trade_pct or 0.0))
    allow_fractional = asset_type == "crypto"
    qty = position_size_from_risk(entry, stop, risk_dollars, allow_fractional=allow_fractional)

    symbol = safe_text(row.get("symbol"))
    contract = safe_text(row.get("option") or row.get("contractSymbol"))
    order_symbol = contract if asset_type == "option" and contract else symbol
    order_type = "LIMIT"
    time_in_force = "GTC" if asset_type == "crypto" else "DAY"
    execution_enabled = status == "READY_TO_PREVIEW"

    checklist = [
        "Confirma que Roxy este en Listo para preparar.",
        "Confirma spread, buying power y sesion de plataforma antes de enviar.",
        "Usa orden limit; no persigas precio por encima de entrada.",
        "Coloca o prepara stop y targets antes o justo despues del fill.",
        "Registra fill y resultado en la memoria de Roxy.",
    ]
    if asset_type == "option":
        checklist.insert(1, "Confirma DTE, delta, spread, volumen, open interest y perdida maxima.")
    if asset_type == "crypto":
        checklist.insert(1, "Confirma liquidez 24h y que el par soporte stop/target.")

    return {
        "platform_id": platform_id,
        "platform": profile["name"],
        "asset_type": asset_type,
        "symbol": symbol,
        "order_symbol": order_symbol,
        "side": "BUY",
        "order_type": order_type,
        "time_in_force": time_in_force,
        "entry": entry,
        "stop": stop,
        "target_price": target_price,
        "target_pct": target_pct,
        "risk_dollars": risk_dollars,
        "quantity": qty,
        "status": status,
        "status_reason": status_reason,
        "execution_gate": gate_status,
        "execution_gate_reason": gate_reason,
        "execution_enabled": execution_enabled,
        "api_status": profile["api_status"],
        "auth": profile["auth"],
        "best_for": profile["best_for"],
        "manual_steps": profile["manual_steps"],
        "checklist": checklist,
    }


def build_platform_route_rows(
    opportunities: list[dict[str, Any]],
    *,
    account_equity: float = 500.0,
    risk_per_trade_pct: float = 0.01,
    preferred_crypto: str = "crypto_com",
    preferred_stock: str = "schwab",
    preferred_option: str = "schwab",
    source_freshness: dict[str, Any] | None = None,
    market_session: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for opportunity in opportunities:
        ticket = build_platform_ticket(
            opportunity,
            account_equity=account_equity,
            risk_per_trade_pct=risk_per_trade_pct,
            preferred_crypto=preferred_crypto,
            preferred_stock=preferred_stock,
            preferred_option=preferred_option,
            source_freshness=source_freshness,
            market_session=market_session,
        )
        rows.append(
            {
                "symbol": ticket["symbol"],
                "asset_type": ticket["asset_type"],
                "platform": ticket["platform"],
                "status": ticket["status"],
                "execution_gate": ticket["execution_gate"],
                "order_symbol": ticket["order_symbol"],
                "entry": ticket["entry"],
                "stop": ticket["stop"],
                "target_price": ticket["target_price"],
                "risk_dollars": ticket["risk_dollars"],
                "quantity": ticket["quantity"],
                "api_status": ticket["api_status"],
            }
        )
    return rows


__all__ = [
    "DEFAULT_PLATFORM_BY_ASSET",
    "PLATFORM_PROFILES",
    "build_platform_route_rows",
    "build_platform_ticket",
    "execution_context_gate",
    "infer_asset_type",
    "is_trade_ready",
    "platform_profile",
    "position_size_from_risk",
    "route_platform",
]
