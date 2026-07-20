from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from roxy_trader.watchlists import (
    PRICE_ALERT_TYPES,
    TECHNICAL_ALERT_TYPES,
    WatchlistStore,
    normalize_watchlist_market,
    normalize_watchlist_symbol,
)


ALERT_MONITOR_CONTRACT_VERSION = "roxy-durable-alert-monitor/2.0.0"
QuoteFetcher = Callable[[str, str], dict[str, Any]]
TechnicalFetcher = Callable[[str, str, str, int, int], dict[str, Any]]
Notifier = Callable[[str], dict[str, Any]]


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def alert_quote_gate(quote: dict[str, Any] | None, *, market: str, max_age_seconds: int = 120) -> dict[str, Any]:
    payload = dict(quote or {})
    price = _number(payload.get("price"))
    freshness = str(payload.get("freshness") or "").upper()
    source_mode = str(payload.get("source_mode") or "").upper()
    provider = str(payload.get("provider") or "").strip()
    source = str(payload.get("source") or "").strip()
    try:
        age_seconds = int(payload.get("age_seconds"))
    except (TypeError, ValueError):
        age_seconds = None
    if price is None:
        return {"accepted": False, "status": "SIN_DATOS", "detail": "El proveedor no entrego un precio positivo."}
    if freshness not in {"LIVE", "FRESH"} or age_seconds is None or age_seconds > max(1, int(max_age_seconds)):
        return {
            "accepted": False,
            "status": "DATO_RETRASADO",
            "detail": f"Precio no apto para disparar: freshness={freshness or '-'}, age={age_seconds} s.",
            "source": source,
            "freshness": freshness,
        }
    if market == "crypto":
        if source_mode != "EXCHANGE_TICKER" or not provider:
            return {
                "accepted": False,
                "status": "FUENTE_NO_VERIFICADA",
                "detail": f"Cripto requiere ticker de exchange; mode={source_mode or '-'}, provider={provider or '-'}.",
                "source": source,
                "freshness": freshness,
            }
    else:
        if source_mode != "BROKER_DATA" or provider.lower() != "alpaca":
            return {
                "accepted": False,
                "status": "PROVEEDOR_PREMIUM_BLOQUEADO",
                "detail": "La alerta bursatil no dispara con fallback publico o retrasado; requiere dato broker Alpaca.",
                "source": source,
                "freshness": freshness,
            }
        if payload.get("market_open") is not True:
            return {
                "accepted": False,
                "status": "MERCADO_CERRADO",
                "detail": "El mercado bursatil esta cerrado; la regla conserva su estado.",
                "source": source,
                "freshness": freshness,
            }
    return {
        "accepted": True,
        "status": "EVALUABLE",
        "detail": "Precio verificado y apto para evaluar la regla.",
        "price": price,
        "source": source or provider,
        "freshness": freshness,
    }


def _timeframe_seconds(value: Any) -> int:
    clean = str(value or "15m").strip().lower()
    try:
        if clean.endswith("m"):
            return max(60, int(clean[:-1]) * 60)
        if clean.endswith("h"):
            return max(3600, int(clean[:-1]) * 3600)
        if clean.endswith("d"):
            return max(86400, int(clean[:-1]) * 86400)
        if clean.endswith("w"):
            return max(604800, int(clean[:-1]) * 604800)
    except ValueError:
        pass
    return 900


def alert_technical_gate(
    snapshot: dict[str, Any] | None,
    *,
    alert_type: str,
    market: str,
    timeframe: str,
) -> dict[str, Any]:
    payload = dict(snapshot or {})
    source_mode = str(payload.get("source_mode") or "").upper()
    provider = str(payload.get("provider") or "").strip()
    source = str(payload.get("source") or provider).strip()
    engine = str(payload.get("indicator_engine") or "")
    freshness = str(payload.get("freshness") or "").upper()
    try:
        age_seconds = int(payload.get("age_seconds"))
    except (TypeError, ValueError):
        age_seconds = None
    max_age = max(120, _timeframe_seconds(timeframe) * 2)
    if engine != "roxy-indicators/1.1.0":
        return {
            "accepted": False,
            "status": "INDICATOR_ENGINE_INVALID",
            "detail": f"Motor técnico no verificable: {engine or '-'}.",
            "source": source,
        }
    if freshness not in {"LIVE", "FRESH"} or age_seconds is None or age_seconds > max_age:
        return {
            "accepted": False,
            "status": "VELAS_RETRASADAS",
            "detail": f"Velas no aptas: freshness={freshness or '-'}, age={age_seconds} s, max={max_age} s.",
            "source": source,
            "freshness": freshness,
        }
    if market == "crypto":
        if source_mode != "EXCHANGE_API" or not provider:
            return {
                "accepted": False,
                "status": "VELAS_NO_VERIFICADAS",
                "detail": "Alertas técnicas cripto requieren velas de exchange.",
                "source": source,
            }
    elif source_mode not in {"BROKER_DATA", "PREMIUM_DATA"} or not provider:
        return {
            "accepted": False,
            "status": "VELAS_PREMIUM_BLOQUEADAS",
            "detail": "Alertas técnicas bursátiles requieren velas Alpaca o Polygon, no fallback público.",
            "source": source,
        }

    required = (
        ("previous_fast", "previous_slow", "current_fast", "current_slow")
        if alert_type in {"ema_cross_above", "ema_cross_below"}
        else ("relative_volume",)
    )
    try:
        values = {key: float(payload.get(key)) for key in required}
    except (TypeError, ValueError):
        return {
            "accepted": False,
            "status": "INDICADORES_INCOMPLETOS",
            "detail": "Las velas no produjeron todos los indicadores requeridos.",
            "source": source,
        }
    return {
        "accepted": True,
        "status": "EVALUABLE",
        "detail": "Velas e indicadores centrales aptos para evaluar la regla.",
        **values,
        "indicator_engine": engine,
        "source": source,
        "freshness": freshness,
    }


def monitor_price_alerts(
    store: WatchlistStore,
    quote_fetcher: QuoteFetcher,
    *,
    notifier: Notifier | None = None,
    technical_fetcher: TechnicalFetcher | None = None,
    max_age_seconds: int = 120,
    now: datetime | None = None,
) -> dict[str, Any]:
    generated_at = (now or datetime.now(timezone.utc)).isoformat()
    expired = store.expire_due_alerts(now=now)
    inventory = store.active_alert_inventory()
    retry_rows = store.pending_notification_inventory()
    delivery_counts = store.alert_notification_status_counts()
    permanent_delivery_failures = int(delivery_counts.get("DELIVERY_FAILED", 0))
    if not inventory and not retry_rows:
        return {
            "contract_version": ALERT_MONITOR_CONTRACT_VERSION,
            "status": "WARNING" if permanent_delivery_failures else "NO_DATA",
            "generated_at": generated_at,
            "active_alerts": 0,
            "symbols": 0,
            "evaluated": 0,
            "blocked": 0,
            "triggered": 0,
            "expired": expired,
            "notifications": 0,
            "notification_pending": 0,
            "notification_failures": 0,
            "permanent_delivery_failures": permanent_delivery_failures,
            "notification_states": delivery_counts,
            "provider_states": {},
            "detail": (
                f"Hay {permanent_delivery_failures} alertas con entrega fallida que requieren revisión o archivo."
                if permanent_delivery_failures
                else
                f"No hay alertas activas para monitorear; expiradas en este ciclo {expired}."
                if expired
                else "No hay alertas activas para monitorear."
            ),
        }

    quotes: dict[tuple[str, str], dict[str, Any]] = {}
    gates: dict[tuple[str, str], dict[str, Any]] = {}
    for alert in inventory:
        symbol = normalize_watchlist_symbol(alert.get("symbol"))
        market = normalize_watchlist_market(alert.get("market"), symbol)
        key = (market, symbol)
        if key in quotes:
            continue
        try:
            quote = dict(quote_fetcher(symbol, market) or {})
        except Exception as exc:
            quote = {"error": f"{type(exc).__name__}: {exc}"}
        quotes[key] = quote
        gates[key] = alert_quote_gate(quote, market=market, max_age_seconds=max_age_seconds)

    technical_gates: dict[str, dict[str, Any]] = {}
    for alert in inventory:
        alert_type = str(alert.get("type") or "")
        if alert_type not in TECHNICAL_ALERT_TYPES:
            continue
        alert_id = str(alert.get("id") or "")
        symbol = normalize_watchlist_symbol(alert.get("symbol"))
        market = normalize_watchlist_market(alert.get("market"), symbol)
        timeframe = str(alert.get("timeframe") or "15m")
        if technical_fetcher is None:
            technical_gates[alert_id] = {
                "accepted": False,
                "status": "TECHNICAL_FETCHER_NOT_CONFIGURED",
                "detail": "El monitor no tiene cargador de velas técnicas configurado.",
            }
            continue
        try:
            snapshot = technical_fetcher(
                symbol,
                market,
                timeframe,
                int(alert.get("fast_period") or 9),
                int(alert.get("slow_period") or 21),
            )
        except Exception as exc:
            snapshot = {"error": f"{type(exc).__name__}: {exc}"}
        technical_gates[alert_id] = alert_technical_gate(
            snapshot, alert_type=alert_type, market=market, timeframe=timeframe
        )

    evaluated = 0
    blocked = 0
    triggered_rows: list[dict[str, Any]] = []
    provider_states: dict[str, int] = {}
    by_user: dict[str, list[dict[str, Any]]] = {}
    for alert in inventory:
        by_user.setdefault(str(alert.get("user_id") or "local_user"), []).append(alert)

    for user_id, alerts in by_user.items():
        accepted_observations: dict[str, dict[str, Any]] = {}
        for alert in alerts:
            symbol = normalize_watchlist_symbol(alert.get("symbol"))
            market = normalize_watchlist_market(alert.get("market"), symbol)
            gate = gates[(market, symbol)]
            alert_type = str(alert.get("type") or "")
            alert_id = str(alert.get("id") or "")
            technical_gate = technical_gates.get(alert_id) if alert_type in TECHNICAL_ALERT_TYPES else None
            final_gate = technical_gate if gate.get("accepted") and technical_gate is not None else gate
            provider_states[final_gate["status"]] = provider_states.get(final_gate["status"], 0) + 1
            if gate.get("accepted") and (technical_gate is None or technical_gate.get("accepted")):
                observation = {
                    "price": gate["price"],
                    "source": gate.get("source") or "",
                    "freshness": gate.get("freshness") or "",
                }
                if technical_gate:
                    observation.update(technical_gate)
                accepted_observations[alert_id if alert_type in TECHNICAL_ALERT_TYPES else symbol] = observation
            else:
                blocked += 1
                store.record_alert_monitor_state(
                    user_id,
                    symbol=symbol,
                    market=market,
                    status=str(final_gate.get("status") or "BLOQUEADA"),
                    detail=str(final_gate.get("detail") or "Dato no verificable."),
                    source=str(final_gate.get("source") or gate.get("source") or ""),
                    freshness=str(final_gate.get("freshness") or gate.get("freshness") or ""),
                    alert_id=alert_id,
                )
        if not accepted_observations:
            continue
        before = {str(alert.get("id")): dict(alert) for alert in alerts}
        updated = store.evaluate_alerts(user_id, accepted_observations)
        evaluated += sum(1 for row in updated if row.get("last_evaluated_at"))
        for row in updated:
            alert_id = str(row.get("id") or "")
            if row.get("status") == "Activada" and before.get(alert_id, {}).get("status") == "Activa":
                triggered_rows.append({**dict(row), "user_id": user_id})

    notification_count = 0
    notification_failures = 0
    notification_results: list[dict[str, Any]] = []
    notification_candidates: dict[str, dict[str, Any]] = {
        str(row.get("id") or ""): dict(row) for row in [*retry_rows, *triggered_rows] if row.get("id")
    }
    if notifier is not None:
        for row in notification_candidates.values():
            alert_type = str(row.get("type") or "")
            if alert_type == "price_above":
                condition = f"superó {row.get('threshold')}"
            elif alert_type == "price_below":
                condition = f"perdió {row.get('threshold')}"
            elif alert_type == "ema_cross_above":
                condition = f"EMA{row.get('fast_period')} cruzó sobre EMA{row.get('slow_period')}"
            elif alert_type == "ema_cross_below":
                condition = f"EMA{row.get('fast_period')} cruzó debajo de EMA{row.get('slow_period')}"
            else:
                condition = f"volumen relativo alcanzó {row.get('last_relative_volume')}x"
            message = (
                f"{row.get('symbol')} {condition} en {row.get('timeframe')}. "
                f"Fuente {row.get('last_source') or 'no indicada'}; regla técnica verificable."
            )
            try:
                result = dict(notifier(message) or {})
            except Exception as exc:
                result = {"sent": False, "reason": f"{type(exc).__name__}: {exc}"}
            notification_results.append(result)
            delivered = bool(result.get("sent") or result.get("reason") == "recorded_local")
            notification_count += int(delivered)
            notification_failures += int(not delivered)
            store.record_alert_notification_state(
                row.get("user_id") or "local_user",
                row.get("id"),
                delivered=delivered,
                detail=str(result.get("reason") or "delivered"),
                channels=list(result.get("channels") or []),
            )

    notification_pending = len(store.pending_notification_inventory())
    delivery_counts = store.alert_notification_status_counts()
    permanent_delivery_failures = int(delivery_counts.get("DELIVERY_FAILED", 0))
    status = (
        "OK"
        if blocked == 0 and notification_failures == 0 and notification_pending == 0 and permanent_delivery_failures == 0
        else "WARNING"
    )
    return {
        "contract_version": ALERT_MONITOR_CONTRACT_VERSION,
        "status": status,
        "generated_at": generated_at,
        "active_alerts": len(inventory),
        "symbols": len(quotes),
        "evaluated": evaluated,
        "blocked": blocked,
        "triggered": len(triggered_rows),
        "expired": expired,
        "notifications": notification_count,
        "notification_pending": notification_pending,
        "notification_failures": notification_failures,
        "permanent_delivery_failures": permanent_delivery_failures,
        "notification_states": delivery_counts,
        "provider_states": provider_states,
        "triggered_symbols": sorted({str(row.get("symbol") or "") for row in triggered_rows}),
        "notification_results": notification_results,
        "detail": (
            f"Evaluadas {evaluated}; bloqueadas por contrato de datos {blocked}; "
            f"activadas {len(triggered_rows)}; expiradas {expired}; notificaciones registradas {notification_count}; "
            f"entregas pendientes {notification_pending}; fallos de entrega {notification_failures}."
        ),
    }
