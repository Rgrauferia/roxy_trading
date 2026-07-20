from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from roxy_trader.watchlists import WatchlistStore, normalize_watchlist_user, operational_opportunity_record


OPPORTUNITY_SYNC_CONTRACT = "roxy-opportunity-sync/1.0.0"
LIVE_GATES = {"LIVE_PRICE_OK", "LIVE_DATA_OK", "ANALYSIS_OK"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def market_alerts_allowed(realtime_health: dict[str, Any], market: str) -> bool:
    market_key = _text(market).lower() or "stock"
    realtime = realtime_health if isinstance(realtime_health, dict) else {}
    market_realtime = realtime.get("market_realtime") if isinstance(realtime.get("market_realtime"), dict) else {}
    markets = market_realtime.get("markets") if isinstance(market_realtime.get("markets"), dict) else {}
    contract = markets.get(market_key) if isinstance(markets.get(market_key), dict) else {}
    if "alerts_allowed" in contract:
        return bool(contract.get("alerts_allowed"))
    direct_key = f"{market_key}_alerts_allowed"
    return bool(realtime.get(direct_key, realtime.get("alerts_allowed", False)))


def opportunity_source_contract(row: dict[str, Any], realtime_health: dict[str, Any]) -> dict[str, Any]:
    """Derive the durable data contract from the same chart/realtime evidence used by AI watch."""
    item = dict(row or {})
    chart = item.get("chart_data_contract") if isinstance(item.get("chart_data_contract"), dict) else {}
    gate = _text(item.get("data_gate") or item.get("chart_data_gate") or chart.get("gate")).upper()
    market = _text(item.get("market")).lower() or ("crypto" if "/" in _text(item.get("symbol")) else "stock")
    operable = bool(chart.get("operable", item.get("chart_operable", False)))
    allowed = market_alerts_allowed(realtime_health, market)
    if gate not in LIVE_GATES or not operable or not allowed:
        return {
            **item,
            "data_bucket": "Bloqueadas",
            "data_state": "Datos bloqueados",
            "data_gate": gate or "NO_DATA",
            "data_source": _text(item.get("data_source") or item.get("chart_source_label") or chart.get("source_label")),
        }

    source = _text(item.get("data_source") or item.get("chart_source_label") or chart.get("source_label"))
    if market == "crypto" and (not source or source.upper() == _text(item.get("symbol")).upper()):
        source = "BinanceUS API"
    elif market == "stock" and (not source or source.upper() == _text(item.get("symbol")).upper()):
        source = "Alpaca"
    return {
        **item,
        "data_bucket": "Live real",
        "data_state": "Broker/exchange live",
        "data_gate": gate,
        "data_source": source,
    }


def brief_source_health(brief: dict[str, Any]) -> tuple[bool, str]:
    payload = brief if isinstance(brief, dict) else {}
    freshness = payload.get("source_freshness") if isinstance(payload.get("source_freshness"), dict) else {}
    if _text(freshness.get("status")).upper() != "FRESH":
        return False, _text(freshness.get("detail") or "El scan no esta fresco.")
    source_files = payload.get("source_files") if isinstance(payload.get("source_files"), dict) else {}
    required = [source_files.get("scan"), source_files.get("confluence")]
    if not all(value and Path(str(value)).is_file() for value in required):
        return False, "Faltan artefactos actuales de scan o confluencia."
    realtime = payload.get("realtime_health") if isinstance(payload.get("realtime_health"), dict) else {}
    opportunities = [row for row in payload.get("opportunities", []) if isinstance(row, dict)]
    markets = {_text(row.get("market")).lower() for row in opportunities if _text(row.get("market"))}
    if markets and not any(market_alerts_allowed(realtime, market) for market in markets):
        return False, "Ningun mercado del brief tiene proveedor operativo."
    if not markets and not bool(realtime.get("alerts_allowed")):
        return False, "El diagnostico realtime no permite alertas."
    return True, _text(freshness.get("detail") or "Scan y confluencia frescos.")


def opportunity_sync_users(store: WatchlistStore, configured_user: str | None = None) -> list[str]:
    users = [*store.user_ids(), "local_user"]
    configured = _text(configured_user or os.getenv("ROXY_BACKGROUND_USER_ID"))
    if configured:
        users.append(normalize_watchlist_user(configured))
    return sorted(set(users))


def sync_brief_opportunities(
    brief: dict[str, Any],
    *,
    store: WatchlistStore,
    configured_user: str | None = None,
) -> dict[str, Any]:
    healthy, detail = brief_source_health(brief)
    realtime = brief.get("realtime_health") if isinstance(brief.get("realtime_health"), dict) else {}
    rows = [
        opportunity_source_contract(row, realtime)
        for row in brief.get("opportunities", [])
        if isinstance(row, dict)
    ]
    results: dict[str, dict[str, Any]] = {}
    archive_events = [row for row in brief.get("archived_opportunities", []) if isinstance(row, dict)]
    archived_invalidated = 0
    for user_id in opportunity_sync_users(store, configured_user):
        results[user_id] = store.sync_operational_opportunities(user_id, rows, source_healthy=healthy)
        if healthy and archive_events:
            archived = store.archive_operational_opportunity_events(user_id, archive_events)
            results[user_id]["invalidated_archive"] = archived
            archived_invalidated += int(archived.get("archived") or 0)
    return {
        "contract": OPPORTUNITY_SYNC_CONTRACT,
        "contract_version": OPPORTUNITY_SYNC_CONTRACT,
        "generated_at": _now_iso(),
        "status": "OK" if healthy else "WARNING",
        "detail": detail,
        "source_healthy": healthy,
        "brief_generated_at": _text(brief.get("generated_at")),
        "candidate_count": len(rows),
        "trade_ready_count": sum(operational_opportunity_record(row) is not None for row in rows),
        "invalidated_archive_event_count": len(archive_events),
        "invalidated_archived_count": archived_invalidated,
        "users": results,
    }


def write_opportunity_sync_report(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
