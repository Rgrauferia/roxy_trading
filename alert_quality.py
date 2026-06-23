from __future__ import annotations

import argparse
from collections import Counter
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALERTS_DIR = Path("alerts")
DEFAULT_BRIEF_PATH = ALERTS_DIR / "roxy_ai_brief.json"
DEFAULT_REPORT_PATH = ALERTS_DIR / "alert_quality.json"
DEFAULT_HISTORY_PATH = ALERTS_DIR / "alert_quality_history.jsonl"
DEFAULT_HISTORY_LIMIT = 500
DEFAULT_HISTORY_MAX_BYTES = 2_000_000
DEFAULT_HISTORY_MIN_ENTRIES = 120
DEFAULT_HISTORY_BUDGET_WARN_RATIO = 0.85
DEFAULT_HISTORY_BUDGET_WATCH_MARGIN_RATIO = 0.02
DEFAULT_HISTORY_BUDGET_NEXT_APPEND_GUARD_MULTIPLIER = 3.0
DEFAULT_HISTORY_BUDGET_MIN_APPENDS_UNTIL_WARN = 8
DEFAULT_HISTORY_CAP_TARGET_RATIO = 0.80
HISTORY_STORAGE_REMOVED_KEY_SAMPLE_LIMIT = 12
HISTORY_STORAGE_REDUNDANT_PLAN_KEYS = (
    "missed_trigger_plan",
    "confirmation_wait_plan",
)
HISTORY_STORAGE_REDUNDANT_SNAPSHOT_KEYS = (
    "top_setup",
    "setup_watchlist",
)
HISTORY_STORAGE_ACTION_ALIAS_KEYS = (
    "recommended_action",
    "operational_focus_reason",
    "missed_trigger_plan_handoff_confirmed_action",
    "missed_trigger_plan_review_action",
    "missed_trigger_plan_decision_action",
    "confirmation_wait_plan_review_action",
    "confirmation_wait_plan_decision_action",
)
HISTORY_STORAGE_DUPLICATE_KEY_ALIASES = (
    ("missed_trigger_plan_review_action", "missed_trigger_plan_decision_action"),
    ("confirmation_wait_plan_review_action", "confirmation_wait_plan_decision_action"),
)
HISTORY_STORAGE_DUPLICATE_SCALAR_ALIASES = (
    ("latest_top_blocker", "top_blocker"),
    ("recurrent_blocker", "top_blocker"),
    ("persistent_blocker", "top_blocker"),
    ("diagnostic_detail", "top_blocker"),
    ("latest_top_gate", "top_gate"),
    ("recurrent_gate", "top_gate"),
    ("missed_opportunity_reason", "silence_reason"),
)
HISTORY_STORAGE_INACTIVE_PLAN_PREFIXES = (
    ("confirmation_wait_plan_active", "confirmation_wait_plan_"),
    ("missed_trigger_plan_discard_guard_active", "missed_trigger_plan_discard_"),
)
PREMIUM_PROVIDER_RECOVERY_ACTION = (
    "Configurar POLYGON_API_KEY/POLYGON_API_TOKEN o corregir credenciales Alpaca para recuperar velas premium."
)
CHART_OPERABLE_GATES = {"LIVE_DATA_OK", "ANALYSIS_OK", "LIVE_PRICE_OK"}
CHART_BLOCKING_GATES = {
    "CHART_CONTRACT_MISSING",
    "NO_TRADE_FROM_FALLBACK",
    "NO_TRADE_STALE_DATA",
    "NO_TRADE_FROM_PUBLIC_PRICE",
    "NO_TRADE_PRICE_FAIL",
    "NO_TRADE_STALE_PRICE",
    "WAIT_PRICE_CONFIRMATION",
    "WAIT_NEXT_CANDLE",
    "MARKET_CLOSED_RECHECK",
    "EXTERNAL_CONFIRM_REQUIRED",
}
MISSED_TRIGGER_WATCH_MIN_STREAK = 24
MISSED_TRIGGER_REVIEW_STREAK = 48
MISSED_TRIGGER_NEAR_READY_REVIEW_THRESHOLD = 70.0
MISSED_TRIGGER_READY_WATCH_THRESHOLD = 75.0
MISSED_TRIGGER_ROTATION_COOLDOWN_CYCLES = 12
MISSED_TRIGGER_ESCALATION_OVERDUE_CYCLES = MISSED_TRIGGER_ROTATION_COOLDOWN_CYCLES
CONFIRMATION_WAIT_REVIEW_STREAK = 48
DAILY_PLAN_ROTATION_BLOCKED_STAGES = {"ESPERAR_DATOS", "NO_OPERAR"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def safe_text(value: Any) -> str:
    return "" if value is None else str(value)


def safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def confirmation_wait_review_requires_attention(
    plan: dict[str, Any],
    *,
    false_negative_risk: str = "",
) -> bool:
    if not plan or not bool(plan.get("review_due")):
        return False
    pressure = safe_text(plan.get("review_pressure") or "").upper()
    risk = safe_text(plan.get("risk") or false_negative_risk or "").upper()
    return bool(plan.get("rotation_guard_active")) or pressure in {
        "OVERDUE_ESCALATED",
    } or risk == "HIGH"


def premium_recovery_action_from_blocker(blocker: str) -> str:
    text = safe_text(blocker).strip()
    lower = text.lower()
    marker = "| accion "
    if marker in lower:
        idx = lower.index(marker) + len(marker)
        action = text[idx:].strip()
        if action:
            return action
    if "polygon" in lower or "alpaca" in lower or "premium" in lower:
        return PREMIUM_PROVIDER_RECOVERY_ACTION
    return ""


def parse_utc_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def read_history(path: Path = DEFAULT_HISTORY_PATH, *, limit: int = DEFAULT_HISTORY_LIMIT) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(errors="replace").splitlines()[-max(1, int(limit)) :]:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def compact_history_entry_for_storage(entry: dict[str, Any]) -> dict[str, Any]:
    compacted = dict(entry)
    legacy_removed_keys = compacted.pop("storage_removed_keys", [])
    if not isinstance(legacy_removed_keys, list):
        legacy_removed_keys = []
    removed_keys = [
        key
        for key in HISTORY_STORAGE_REDUNDANT_PLAN_KEYS
        if isinstance(compacted.get(key), dict) and compacted.get(f"{key}_active") is not None
    ]
    for key in HISTORY_STORAGE_REDUNDANT_SNAPSHOT_KEYS:
        if key == "top_setup" and isinstance(compacted.get(key), dict) and all(
            compacted.get(alias) is not None
            for alias in (
                "top_symbol",
                "top_readiness",
                "top_quality",
                "top_gate",
                "top_blocker",
                "top_next_action",
            )
        ):
            removed_keys.append(key)
        elif key == "setup_watchlist" and isinstance(compacted.get(key), list) and all(
            compacted.get(alias) is not None
            for alias in ("top_symbol", "top_readiness", "top_gate", "top_blocker", "watch_count")
        ):
            removed_keys.append(key)
    action = str(compacted.get("action") or "").strip()
    if action:
        for key in HISTORY_STORAGE_ACTION_ALIAS_KEYS:
            if str(compacted.get(key) or "").strip() == action:
                removed_keys.append(key)
    for alias_key, canonical_key in HISTORY_STORAGE_DUPLICATE_KEY_ALIASES:
        if (
            alias_key in compacted
            and canonical_key in compacted
            and str(compacted.get(alias_key) or "").strip()
            == str(compacted.get(canonical_key) or "").strip()
        ):
            removed_keys.append(alias_key)
    for active_key, prefix in HISTORY_STORAGE_INACTIVE_PLAN_PREFIXES:
        if compacted.get(active_key) is False:
            removed_keys.extend(key for key in compacted if key.startswith(prefix))
    for alias_key, canonical_key in HISTORY_STORAGE_DUPLICATE_SCALAR_ALIASES:
        if (
            alias_key in compacted
            and canonical_key in compacted
            and str(compacted.get(alias_key) or "").strip()
            == str(compacted.get(canonical_key) or "").strip()
        ):
            removed_keys.append(alias_key)
    if legacy_removed_keys:
        removed_keys = [*legacy_removed_keys, *removed_keys]
    removed_keys = list(dict.fromkeys(str(key) for key in removed_keys))
    for key in removed_keys:
        compacted.pop(key, None)
    if removed_keys:
        compacted["storage_compacted"] = True
        compacted["storage_removed_key_count"] = len(removed_keys)
        compacted["storage_removed_key_sample"] = removed_keys[:HISTORY_STORAGE_REMOVED_KEY_SAMPLE_LIMIT]
    return compacted


def append_history(
    path: Path,
    entry: dict[str, Any],
    *,
    limit: int = DEFAULT_HISTORY_LIMIT,
    max_bytes: int | None = DEFAULT_HISTORY_MAX_BYTES,
    min_entries: int = DEFAULT_HISTORY_MIN_ENTRIES,
    warn_ratio: float = DEFAULT_HISTORY_BUDGET_WARN_RATIO,
    watch_margin_ratio: float = DEFAULT_HISTORY_BUDGET_WATCH_MARGIN_RATIO,
    next_append_guard_multiplier: float = DEFAULT_HISTORY_BUDGET_NEXT_APPEND_GUARD_MULTIPLIER,
    min_appends_until_warn: int = DEFAULT_HISTORY_BUDGET_MIN_APPENDS_UNTIL_WARN,
    cap_target_ratio: float = DEFAULT_HISTORY_CAP_TARGET_RATIO,
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    limit = max(1, int(limit))
    max_bytes = max(0, int(max_bytes)) if max_bytes is not None else 0
    min_entries = max(1, min(int(min_entries), limit))
    warn_ratio = max(0.0, float(warn_ratio))
    watch_margin_ratio = max(0.0, float(watch_margin_ratio))
    next_append_guard_multiplier = max(0.0, float(next_append_guard_multiplier))
    min_appends_until_warn = max(0, int(min_appends_until_warn))
    cap_target_ratio = max(0.0, min(float(cap_target_ratio), 1.0))
    rows = read_history(path, limit=limit)
    rows.append(entry)
    rows = rows[-limit:]
    lines = [json.dumps(compact_history_entry_for_storage(row), sort_keys=True) for row in rows]
    if max_bytes:
        current_bytes = len(("\n".join(lines) + "\n").encode()) if lines else 0
        average_line_bytes = (
            int(round(sum(len(line.encode("utf-8")) + 1 for line in lines) / len(lines)))
            if lines
            else 0
        )
        warn_bytes = int(max_bytes * warn_ratio) if warn_ratio else 0
        budget_ratio = current_bytes / max_bytes if max_bytes > 0 else 0.0
        bytes_until_warn = warn_bytes - current_bytes if warn_bytes else None
        estimated_appends_until_warn = (
            int(bytes_until_warn // average_line_bytes)
            if bytes_until_warn is not None and average_line_bytes > 0
            else None
        )
        next_append_guard_due = bool(
            cap_target_ratio
            and cap_target_ratio < 1.0
            and warn_bytes
            and budget_ratio >= max(0.0, warn_ratio - watch_margin_ratio)
            and current_bytes + int(round(average_line_bytes * next_append_guard_multiplier))
            >= warn_bytes
        )
        min_append_guard_due = bool(
            cap_target_ratio
            and cap_target_ratio < 1.0
            and min_appends_until_warn
            and estimated_appends_until_warn is not None
            and 0 <= estimated_appends_until_warn <= min_appends_until_warn
            and budget_ratio > cap_target_ratio
        )
        effective_max_bytes = max_bytes
        if (
            cap_target_ratio
            and cap_target_ratio < 1.0
            and warn_ratio
            and (current_bytes >= warn_bytes or next_append_guard_due or min_append_guard_due)
        ):
            effective_max_bytes = max(1, int(max_bytes * cap_target_ratio))
        kept: list[str] = []
        total_bytes = 1
        for line in reversed(lines):
            line_bytes = len(line.encode()) + 1
            if kept and len(kept) >= min_entries and total_bytes + line_bytes > effective_max_bytes:
                break
            kept.append(line)
            total_bytes += line_bytes
        lines = list(reversed(kept))
    path.write_text("\n".join(lines) + "\n")
    return len(lines)


def top_opportunity_snapshot(brief: dict[str, Any]) -> dict[str, Any]:
    opportunities = brief.get("top_opportunities")
    if not isinstance(opportunities, list) or not opportunities:
        opportunities = brief.get("opportunities")
    if not isinstance(opportunities, list) or not opportunities:
        return {}
    top = opportunities[0] if isinstance(opportunities[0], dict) else {}
    if not top:
        return {}
    smart_alert = top.get("smart_alert") if isinstance(top.get("smart_alert"), dict) else {}
    blockers = top.get("alert_blockers")
    if not isinstance(blockers, list):
        blockers = smart_alert.get("blockers") if isinstance(smart_alert.get("blockers"), list) else []
    return {
        "symbol": safe_text(top.get("symbol") or "-"),
        "market": safe_text(top.get("market") or "-"),
        "action": safe_text(top.get("ai_action") or top.get("action") or "-"),
        "trade_decision": safe_text(top.get("trade_decision") or "-"),
        "gate": safe_text(top.get("alert_gate") or smart_alert.get("gate") or "-"),
        "readiness": safe_float(top.get("alert_readiness_score") or top.get("readiness") or smart_alert.get("readiness_score")),
        "quality": safe_text(top.get("alert_quality") or smart_alert.get("quality") or "-"),
        "primary_blocker": safe_text(
            top.get("alert_primary_blocker") or top.get("blocker") or smart_alert.get("primary_blocker") or "-"
        ),
        "next_action": safe_text(top.get("alert_next_action") or smart_alert.get("next_action") or "-"),
        "blockers": [safe_text(item) for item in blockers[:5]],
    }


def opportunity_watchlist_snapshot(brief: dict[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
    opportunities = brief.get("top_opportunities")
    if not isinstance(opportunities, list) or not opportunities:
        opportunities = brief.get("opportunities")
    if not isinstance(opportunities, list):
        return []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in opportunities:
        if not isinstance(item, dict):
            continue
        symbol = safe_text(item.get("symbol") or "").upper()
        if not symbol or symbol in seen:
            continue
        smart_alert = item.get("smart_alert") if isinstance(item.get("smart_alert"), dict) else {}
        readiness = safe_float(item.get("alert_readiness_score") or item.get("readiness") or smart_alert.get("readiness_score"))
        rows.append(
            {
                "symbol": symbol,
                "market": safe_text(item.get("market") or "-"),
                "action": safe_text(item.get("ai_action") or item.get("action") or "-"),
                "gate": safe_text(item.get("alert_gate") or smart_alert.get("gate") or "-"),
                "readiness": readiness,
                "quality": safe_text(item.get("alert_quality") or smart_alert.get("quality") or "-"),
                "blocker": safe_text(
                    item.get("alert_primary_blocker") or item.get("blocker") or smart_alert.get("primary_blocker") or "-"
                ),
            }
        )
        seen.add(symbol)
        if len(rows) >= max(1, int(limit)):
            break
    return rows


def normalize_market_label(value: Any, symbol: Any = "") -> str:
    text = safe_text(value).strip().lower()
    if text in {"crypto", "cryptocurrency", "coin"}:
        return "crypto"
    if text in {"option", "options"}:
        return "options"
    if text in {"stock", "stocks", "equity", "equities"}:
        return "stock"
    if "/" in safe_text(symbol):
        return "crypto"
    return text or "unknown"


def market_alert_coverage_snapshot(
    brief: dict[str, Any],
    *,
    realtime_stock_allowed: bool = True,
    realtime_crypto_allowed: bool = True,
    blocked_markets: list[str] | None = None,
) -> dict[str, Any]:
    opportunities = brief.get("top_opportunities")
    if not isinstance(opportunities, list) or not opportunities:
        opportunities = brief.get("opportunities")
    if not isinstance(opportunities, list):
        opportunities = []
    counts: Counter[str] = Counter()
    actionable_counts: Counter[str] = Counter()
    for item in opportunities:
        if not isinstance(item, dict):
            continue
        market = normalize_market_label(item.get("market"), item.get("symbol"))
        counts[market] += 1
        action = safe_text(item.get("ai_action") or item.get("action") or "").upper()
        gate = safe_text(item.get("alert_gate") or "").upper()
        if action in {"BUY", "ALERT", "WATCH"} or gate in {"ALERT_READY", "WAIT_15M_ENTRY", "BLOCKED_REALTIME_DATA"}:
            actionable_counts[market] += 1
    blocked = sorted({normalize_market_label(item) for item in (blocked_markets or []) if safe_text(item)})
    allowed_markets: list[str] = []
    if realtime_stock_allowed:
        allowed_markets.append("stock")
        allowed_markets.append("options")
    if realtime_crypto_allowed:
        allowed_markets.append("crypto")
    allowed_markets = sorted(dict.fromkeys(allowed_markets))
    missing_allowed = [market for market in allowed_markets if counts.get(market, 0) <= 0]
    operable_count = sum(int(counts.get(market, 0)) for market in allowed_markets)
    blocked_count = sum(int(counts.get(market, 0)) for market in blocked)
    if realtime_crypto_allowed and counts.get("crypto", 0) <= 0 and not realtime_stock_allowed:
        label = "Cripto permitido sin candidatos"
        action = "Mantener scan crypto activo; no forzar alertas si no hay setup cripto."
    elif realtime_crypto_allowed and counts.get("crypto", 0) > 0 and not realtime_stock_allowed:
        label = "Cripto operable"
        action = "Priorizar candidatos cripto mientras stock/opciones recuperan proveedor premium."
    elif allowed_markets and operable_count > 0:
        label = "Cobertura operable"
        action = "Seguir escaneando mercados permitidos."
    elif blocked_count > 0:
        label = "Cobertura bloqueada"
        action = premium_recovery_action_from_blocker("premium")
    else:
        label = "Sin cobertura"
        action = "Esperar nuevos setups del scanner."
    return {
        "market_counts": dict(sorted(counts.items())),
        "actionable_market_counts": dict(sorted(actionable_counts.items())),
        "allowed_markets": allowed_markets,
        "blocked_markets": blocked,
        "missing_allowed_markets": missing_allowed,
        "operable_market_count": operable_count,
        "blocked_market_count": blocked_count,
        "market_coverage_label": label,
        "market_coverage_action": action,
    }


def chart_contract_coverage_snapshot(brief: dict[str, Any], *, limit: int = 5) -> dict[str, Any]:
    opportunities = brief.get("top_opportunities")
    if not isinstance(opportunities, list) or not opportunities:
        opportunities = brief.get("opportunities")
    if not isinstance(opportunities, list):
        opportunities = []
    total = 0
    checked = 0
    operable = 0
    blocked = 0
    missing = 0
    gate_counts: Counter[str] = Counter()
    market_counts: Counter[str] = Counter()
    market_operable_counts: Counter[str] = Counter()
    market_blocked_counts: Counter[str] = Counter()
    blocked_symbols: list[str] = []
    operable_symbols: list[str] = []
    for item in opportunities:
        if not isinstance(item, dict):
            continue
        total += 1
        symbol = safe_text(item.get("symbol") or "-").upper()
        market = normalize_market_label(item.get("market"), item.get("symbol"))
        market_counts[market] += 1
        gate = safe_text(item.get("chart_data_gate") or "").upper()
        chart_operable = item.get("chart_operable")
        has_contract = bool(gate) or isinstance(chart_operable, bool)
        if has_contract:
            checked += 1
        if not gate:
            gate = "CHART_CONTRACT_MISSING"
        gate_counts[gate] += 1
        is_missing = gate == "CHART_CONTRACT_MISSING" or not has_contract
        is_operable = chart_operable is True or gate in CHART_OPERABLE_GATES
        is_blocked = is_missing or chart_operable is False or gate in CHART_BLOCKING_GATES or not is_operable
        if is_operable:
            operable += 1
            market_operable_counts[market] += 1
            if len(operable_symbols) < max(1, int(limit)):
                operable_symbols.append(symbol)
        if is_missing:
            missing += 1
        if is_blocked:
            blocked += 1
            market_blocked_counts[market] += 1
            if len(blocked_symbols) < max(1, int(limit)):
                blocked_symbols.append(f"{symbol}: {gate}")
    blocked_markets: set[str] = set()
    for market, count in market_counts.items():
        if market_blocked_counts.get(market, 0) <= 0:
            continue
        if market_operable_counts.get(market, 0) > 0:
            continue
        if market == "stock":
            blocked_markets.update({"stock", "options"})
        elif market:
            blocked_markets.add(market)
    if total <= 0:
        label = "Sin oportunidades"
        action = "Seguir escaneando; no hay oportunidades para validar grafica."
    elif operable == total:
        label = "Graficas operables"
        action = "Mantener alertas solo con grafica realtime operable."
    elif operable > 0:
        label = "Graficas parciales"
        action = "Priorizar oportunidades con LIVE_DATA_OK; bloquear las que no tengan contrato de grafica."
    else:
        label = "Graficas bloqueadas"
        action = "No emitir alertas hasta recuperar contrato realtime de grafica."
    return {
        "chart_contract_total_count": total,
        "chart_contract_checked_count": checked,
        "chart_contract_operable_count": operable,
        "chart_contract_blocked_count": blocked,
        "chart_contract_missing_count": missing,
        "chart_contract_blocked_markets": sorted(blocked_markets),
        "chart_contract_market_counts": dict(sorted(market_counts.items())),
        "chart_contract_market_operable_counts": dict(sorted(market_operable_counts.items())),
        "chart_contract_market_blocked_counts": dict(sorted(market_blocked_counts.items())),
        "chart_contract_gate_counts": dict(sorted(gate_counts.items())),
        "chart_contract_operable_symbols": operable_symbols,
        "chart_contract_blocked_symbols": blocked_symbols,
        "chart_contract_label": label,
        "chart_contract_action": action,
    }


def rotation_candidate_summary(rows: list[dict[str, Any]], *, limit: int = 3) -> list[str]:
    candidates = []
    for row in rows[: max(1, int(limit))]:
        symbol = safe_text(row.get("symbol") or "-")
        readiness = safe_float(row.get("readiness"))
        quality = safe_text(row.get("quality") or "-")
        if readiness is None:
            candidates.append(f"{symbol} {quality}")
        else:
            candidates.append(f"{symbol} {readiness:.1f}% {quality}")
    return candidates


def rotation_candidate_symbol(candidate: str) -> str:
    return safe_text(candidate).split(" ", 1)[0].upper()


def daily_plan_rotation_blocked_symbols(daily_plan: dict[str, Any]) -> list[str]:
    rows = daily_plan.get("rows") if isinstance(daily_plan.get("rows"), list) else []
    blocked: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        stage = safe_text(row.get("stage")).upper()
        symbol = safe_text(row.get("symbol")).upper()
        if stage in DAILY_PLAN_ROTATION_BLOCKED_STAGES and symbol:
            blocked.add(symbol)
    return sorted(blocked)


def rotation_alternates_for_candidates(
    rotation_candidates: list[str],
    *,
    primary_symbol_key: str,
    blocked_symbols: list[str] | set[str] | None = None,
) -> list[str]:
    blocked = {safe_text(symbol).upper() for symbol in blocked_symbols or [] if safe_text(symbol)}
    return [
        candidate
        for candidate in rotation_candidates[:3]
        if rotation_candidate_symbol(candidate) != primary_symbol_key
        and rotation_candidate_symbol(candidate) not in blocked
    ]


def setup_value(row: dict[str, Any], *keys: str) -> Any:
    smart_alert = row.get("smart_alert") if isinstance(row.get("smart_alert"), dict) else {}
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
        value = smart_alert.get(key)
        if value not in (None, ""):
            return value
    return None


def setup_readiness(row: dict[str, Any]) -> float | None:
    return safe_float(
        setup_value(
            row,
            "readiness",
            "alert_readiness_score",
            "readiness_score",
            "score",
            "readiness_pct",
        )
    )


def trigger_review_readiness(latest: dict[str, Any]) -> float | None:
    candidates: list[float] = []
    for key in ("top_readiness", "avg_readiness"):
        readiness = safe_float(latest.get(key))
        if readiness is not None:
            candidates.append(readiness)
    top_setup = latest.get("top_setup") if isinstance(latest.get("top_setup"), dict) else {}
    top_setup_readiness = setup_readiness(top_setup)
    if top_setup_readiness is not None:
        candidates.append(top_setup_readiness)
    watchlist = latest.get("setup_watchlist") if isinstance(latest.get("setup_watchlist"), list) else []
    for item in watchlist[:3]:
        if not isinstance(item, dict):
            continue
        readiness = setup_readiness(item)
        if readiness is not None:
            candidates.append(readiness)
    return max(candidates) if candidates else None


def missed_trigger_watch_plan(
    *,
    active: bool,
    latest: dict[str, Any],
    rotation_candidates: list[str],
    waiting_streak: int,
    blocker_streak: int,
    persistent_minutes: float | None,
    review_cycle_minutes: float | None,
    readiness_delta: float | None = None,
    risk: str,
    reason: str,
    action: str,
    rotation_blocked_symbols: list[str] | set[str] | None = None,
) -> dict[str, Any]:
    if not active:
        return {"active": False}
    waiting_cycles = int(waiting_streak)
    review_due = waiting_cycles >= MISSED_TRIGGER_REVIEW_STREAK or safe_text(risk).upper() == "HIGH"
    review_overdue_cycles = max(0, waiting_cycles - MISSED_TRIGGER_REVIEW_STREAK)
    review_cycles_remaining = max(0, MISSED_TRIGGER_REVIEW_STREAK - waiting_cycles)
    review_status = "OVERDUE" if review_overdue_cycles else "DUE" if review_due else "PENDING"
    review_progress = round(
        waiting_cycles / MISSED_TRIGGER_REVIEW_STREAK,
        3,
    )
    review_eta_minutes = None
    review_overdue_minutes = None
    if review_cycle_minutes is not None:
        cycle_minutes = max(0.0, float(review_cycle_minutes))
        review_eta_minutes = 0.0 if review_due else round(review_cycles_remaining * cycle_minutes, 1)
        review_overdue_minutes = round(review_overdue_cycles * cycle_minutes, 1)
    watchlist = latest.get("setup_watchlist") if isinstance(latest.get("setup_watchlist"), list) else []
    top_setup = latest.get("top_setup") if isinstance(latest.get("top_setup"), dict) else {}
    primary = watchlist[0] if watchlist and isinstance(watchlist[0], dict) else top_setup
    primary_symbol = safe_text(primary.get("symbol") or latest.get("top_symbol") or "-") if isinstance(primary, dict) else "-"
    primary_readiness = setup_readiness(primary) if isinstance(primary, dict) else None
    primary_quality = (
        safe_text(setup_value(primary, "quality", "alert_quality") or "-") if isinstance(primary, dict) else "-"
    )
    primary_blocker = (
        safe_text(setup_value(primary, "blocker", "primary_blocker", "alert_primary_blocker") or latest.get("top_blocker") or "-")
        if isinstance(primary, dict)
        else "-"
    )
    primary_symbol_key = safe_text(primary_symbol).upper()
    rotation_alternates = rotation_alternates_for_candidates(
        rotation_candidates,
        primary_symbol_key=primary_symbol_key,
        blocked_symbols=rotation_blocked_symbols,
    )
    rotation_next_symbol = rotation_candidate_symbol(rotation_alternates[0]) if rotation_alternates else ""
    risk_text = safe_text(risk or "MEDIUM").upper()
    flat_or_fading = readiness_delta is not None and float(readiness_delta) <= 0.0
    near_ready_not_triggered = primary_readiness is not None and primary_readiness < MISSED_TRIGGER_READY_WATCH_THRESHOLD
    stale_candidate = bool(
        review_overdue_cycles
        and (near_ready_not_triggered or (flat_or_fading and risk_text != "HIGH"))
    )
    if not review_due:
        review_pressure = "PENDING"
        auto_review_decision = "WAIT_FOR_TRIGGER"
        decision_reason = "Review window still open."
        decision_action = "Mantener watchlist; esperar confirmacion 15m."
    elif (
        stale_candidate
        and rotation_alternates
        and review_overdue_cycles >= MISSED_TRIGGER_ESCALATION_OVERDUE_CYCLES
    ):
        review_pressure = "STALE_OVERDUE_ESCALATED"
        auto_review_decision = "ESCALATE_ROTATION"
        decision_reason = "Stale review remained overdue beyond the rotation cooldown while alternates are operable."
        decision_action = (
            "Escalar rotacion: mantener bloqueado el candidato stale y "
            f"rotar foco operativo a {rotation_next_symbol}."
        )
    elif stale_candidate and rotation_alternates:
        review_pressure = "STALE_OVERDUE"
        auto_review_decision = "ROTATE_OR_DISCARD"
        decision_reason = "Review overdue with flat/fading readiness or near-ready stall."
        decision_action = "Rotar o descartar el candidato; mantener solo si 15m confirma en la proxima revision."
    elif stale_candidate:
        review_pressure = "STALE_SINGLE"
        auto_review_decision = "DISCARD_STALE_SINGLE"
        decision_reason = "Review overdue on the only visible candidate; no alternate rotation candidate is available."
        decision_action = "Pausar o descartar el candidato unico; esperar nuevo candidato o confirmacion 15m antes de reactivarlo."
    elif review_overdue_cycles >= MISSED_TRIGGER_ESCALATION_OVERDUE_CYCLES and rotation_alternates:
        review_pressure = "OVERDUE_ESCALATED"
        auto_review_decision = "ESCALATE_ROTATION"
        decision_reason = "Review remained overdue beyond the rotation cooldown while alternates are operable."
        decision_action = (
            "Escalar rotacion: revalidar 15m/1h ahora; si no confirma en la proxima revision, "
            f"rotar foco a {rotation_next_symbol}."
        )
    elif review_overdue_cycles:
        review_pressure = "OVERDUE"
        auto_review_decision = "REVALIDATE_NOW"
        decision_reason = "Review overdue while the setup remains close to trigger."
        decision_action = "Revalidar ahora 15m/1h; si no confirma, rotar foco."
    else:
        review_pressure = "DUE"
        auto_review_decision = "REVALIDATE_NOW" if risk_text == "HIGH" else "REVIEW_ON_CADENCE"
        decision_reason = "Manual review threshold reached."
        decision_action = "Revalidar el setup en 15m/1h antes de mantenerlo en foco."
    rotation_guard_active = auto_review_decision in {"ROTATE_OR_DISCARD", "ESCALATE_ROTATION"}
    discard_guard_active = auto_review_decision == "DISCARD_STALE_SINGLE"
    rotation_cooldown_eta_minutes = None
    discard_cooldown_eta_minutes = None
    if rotation_guard_active and review_cycle_minutes is not None:
        rotation_cooldown_eta_minutes = round(
            max(0.0, float(review_cycle_minutes)) * MISSED_TRIGGER_ROTATION_COOLDOWN_CYCLES,
            1,
        )
    if discard_guard_active and review_cycle_minutes is not None:
        discard_cooldown_eta_minutes = round(
            max(0.0, float(review_cycle_minutes)) * MISSED_TRIGGER_ROTATION_COOLDOWN_CYCLES,
            1,
        )
    return {
        "active": True,
        "mode": "MISSED_TRIGGER_WATCH",
        "risk": safe_text(risk or "MEDIUM"),
        "severity": "ATTENTION" if review_due else "WATCH",
        "review_due": review_due,
        "review_status": review_status,
        "review_pressure": review_pressure,
        "review_progress": review_progress,
        "review_overdue_cycles": review_overdue_cycles,
        "review_cycles_remaining": review_cycles_remaining,
        "review_cycle_minutes": review_cycle_minutes,
        "review_eta_minutes": review_eta_minutes,
        "review_overdue_minutes": review_overdue_minutes,
        "review_cadence": "manual_15m_1h_revalidation",
        "readiness_delta": readiness_delta,
        "stale_candidate": stale_candidate,
        "auto_review_decision": auto_review_decision,
        "decision_reason": decision_reason,
        "decision_action": decision_action,
        "rotation_guard_active": rotation_guard_active,
        "rotation_blocked_symbol": primary_symbol if rotation_guard_active else "",
        "rotation_alternates": rotation_alternates if rotation_guard_active else [],
        "rotation_next_symbol": rotation_next_symbol if rotation_guard_active else "",
        "rotation_cooldown_cycles": MISSED_TRIGGER_ROTATION_COOLDOWN_CYCLES if rotation_guard_active else 0,
        "rotation_cooldown_eta_minutes": rotation_cooldown_eta_minutes,
        "rotation_resume_condition": (
            "Rehabilitar el simbolo solo si 15m confirma entrada o mejora readiness por encima de 75%."
            if rotation_guard_active
            else ""
        ),
        "discard_guard_active": discard_guard_active,
        "discard_symbol": primary_symbol if discard_guard_active else "",
        "discard_reason": decision_reason if discard_guard_active else "",
        "discard_cooldown_cycles": MISSED_TRIGGER_ROTATION_COOLDOWN_CYCLES if discard_guard_active else 0,
        "discard_cooldown_eta_minutes": discard_cooldown_eta_minutes,
        "discard_resume_condition": (
            "Rehabilitar el candidato unico solo si 15m confirma entrada o aparece un alterno operable."
            if discard_guard_active
            else ""
        ),
        "max_watch_cycles": MISSED_TRIGGER_REVIEW_STREAK,
        "reason": safe_text(reason),
        "action": safe_text(action),
        "primary_symbol": primary_symbol,
        "primary_readiness": primary_readiness,
        "primary_quality": primary_quality,
        "primary_blocker": primary_blocker,
        "waiting_streak": waiting_cycles,
        "blocker_streak": int(blocker_streak),
        "persistent_minutes": persistent_minutes,
        "rotation_candidates": rotation_candidates[:3],
        "rotation_blocked_by_daily_plan": [
            safe_text(symbol).upper()
            for symbol in rotation_blocked_symbols or []
            if safe_text(symbol)
        ],
        "exit_condition": "No alertar hasta que 15m confirme entrada y la grafica realtime siga operable.",
        "review_action": (
            decision_action
            if review_due
            else ""
        ),
    }


def confirmation_wait_review_plan(
    *,
    active: bool,
    latest: dict[str, Any],
    rotation_candidates: list[str],
    waiting_streak: int,
    blocker_streak: int,
    persistent_minutes: float | None,
    review_cycle_minutes: float | None,
    reason: str,
    action: str,
    rotation_blocked_symbols: list[str] | set[str] | None = None,
) -> dict[str, Any]:
    if not active:
        return {"active": False}
    waiting_cycles = int(waiting_streak)
    review_due = waiting_cycles >= CONFIRMATION_WAIT_REVIEW_STREAK
    review_overdue_cycles = max(0, waiting_cycles - CONFIRMATION_WAIT_REVIEW_STREAK)
    review_cycles_remaining = max(0, CONFIRMATION_WAIT_REVIEW_STREAK - waiting_cycles)
    review_status = "OVERDUE" if review_overdue_cycles else "DUE" if review_due else "PENDING"
    review_progress = round(waiting_cycles / CONFIRMATION_WAIT_REVIEW_STREAK, 3)
    review_eta_minutes = None
    review_overdue_minutes = None
    if review_cycle_minutes is not None:
        cycle_minutes = max(0.0, float(review_cycle_minutes))
        review_eta_minutes = 0.0 if review_due else round(review_cycles_remaining * cycle_minutes, 1)
        review_overdue_minutes = round(review_overdue_cycles * cycle_minutes, 1)
    watchlist = latest.get("setup_watchlist") if isinstance(latest.get("setup_watchlist"), list) else []
    top_setup = latest.get("top_setup") if isinstance(latest.get("top_setup"), dict) else {}
    primary = watchlist[0] if watchlist and isinstance(watchlist[0], dict) else top_setup
    primary_symbol = safe_text(primary.get("symbol") or latest.get("top_symbol") or "-") if isinstance(primary, dict) else "-"
    primary_readiness = setup_readiness(primary) if isinstance(primary, dict) else None
    primary_quality = (
        safe_text(setup_value(primary, "quality", "alert_quality") or "-") if isinstance(primary, dict) else "-"
    )
    primary_blocker = (
        safe_text(setup_value(primary, "blocker", "primary_blocker", "alert_primary_blocker") or latest.get("top_blocker") or "-")
        if isinstance(primary, dict)
        else "-"
    )
    primary_symbol_key = safe_text(primary_symbol).upper()
    rotation_alternates = rotation_alternates_for_candidates(
        rotation_candidates,
        primary_symbol_key=primary_symbol_key,
        blocked_symbols=rotation_blocked_symbols,
    )
    rotation_next_symbol = rotation_candidate_symbol(rotation_alternates[0]) if rotation_alternates else ""
    if not review_due:
        review_pressure = "PENDING"
    elif review_overdue_cycles >= MISSED_TRIGGER_ESCALATION_OVERDUE_CYCLES and rotation_alternates:
        review_pressure = "OVERDUE_ESCALATED"
    elif review_overdue_cycles:
        review_pressure = "OVERDUE"
    else:
        review_pressure = "DUE"
    rotation_guard_active = review_pressure == "OVERDUE_ESCALATED" and bool(rotation_alternates)
    rotation_cooldown_eta_minutes = None
    if rotation_guard_active and review_cycle_minutes is not None:
        rotation_cooldown_eta_minutes = round(
            max(0.0, float(review_cycle_minutes)) * MISSED_TRIGGER_ROTATION_COOLDOWN_CYCLES,
            1,
        )
    decision_action = (
        "Escalar rotacion de confirmacion: revalidar 2h/4h, volumen y target ahora; "
        f"si no mejora, rotar foco a {rotation_next_symbol}."
        if rotation_guard_active
        else "Revalidar manualmente 2h/4h, volumen y target; si la confirmacion no mejora, rotar foco."
        if review_due
        else ""
    )
    confirmation_requires_attention = rotation_guard_active or review_pressure == "OVERDUE_ESCALATED"
    return {
        "active": True,
        "mode": "CONFIRMATION_WAIT_REVIEW",
        "risk": "LOW",
        "severity": "ATTENTION" if confirmation_requires_attention else "WATCH",
        "review_due": review_due,
        "review_status": review_status,
        "review_pressure": review_pressure,
        "review_progress": review_progress,
        "review_overdue_cycles": review_overdue_cycles,
        "review_cycles_remaining": review_cycles_remaining,
        "review_cycle_minutes": review_cycle_minutes,
        "review_eta_minutes": review_eta_minutes,
        "review_overdue_minutes": review_overdue_minutes,
        "review_cadence": "manual_htf_volume_target_revalidation",
        "decision_action": decision_action,
        "rotation_guard_active": rotation_guard_active,
        "rotation_blocked_symbol": primary_symbol if rotation_guard_active else "",
        "rotation_alternates": rotation_alternates if rotation_guard_active else [],
        "rotation_next_symbol": rotation_next_symbol if rotation_guard_active else "",
        "rotation_cooldown_cycles": MISSED_TRIGGER_ROTATION_COOLDOWN_CYCLES if rotation_guard_active else 0,
        "rotation_cooldown_eta_minutes": rotation_cooldown_eta_minutes,
        "rotation_resume_condition": (
            "Rehabilitar el simbolo solo si 2h/4h, volumen/target y grafica realtime confirman."
            if rotation_guard_active
            else ""
        ),
        "max_watch_cycles": CONFIRMATION_WAIT_REVIEW_STREAK,
        "reason": safe_text(reason),
        "action": safe_text(action),
        "primary_symbol": primary_symbol,
        "primary_readiness": primary_readiness,
        "primary_quality": primary_quality,
        "primary_blocker": primary_blocker,
        "waiting_streak": waiting_cycles,
        "blocker_streak": int(blocker_streak),
        "persistent_minutes": persistent_minutes,
        "rotation_candidates": rotation_candidates[:3],
        "rotation_blocked_by_daily_plan": [
            safe_text(symbol).upper()
            for symbol in rotation_blocked_symbols or []
            if safe_text(symbol)
        ],
        "exit_condition": "No alertar hasta que 2h/4h, volumen/target y grafica realtime confirmen.",
        "review_action": decision_action,
    }


def alert_quality_entry(brief: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    current = now or utc_now()
    generated_at = safe_text(brief.get("generated_at")) or current.isoformat()
    gate_summary = brief.get("alert_gate_summary") if isinstance(brief.get("alert_gate_summary"), dict) else {}
    freshness = brief.get("source_freshness") if isinstance(brief.get("source_freshness"), dict) else {}
    realtime = brief.get("realtime_health") if isinstance(brief.get("realtime_health"), dict) else {}
    session = brief.get("market_session") if isinstance(brief.get("market_session"), dict) else {}
    total = int(gate_summary.get("total_opportunities") or len(brief.get("opportunities") or []) or 0)
    ready = int(gate_summary.get("notifications_ready") or 0)
    alert_count = int(gate_summary.get("alert_count") or brief.get("alert_count") or 0)
    watch_count = int(gate_summary.get("watch_count") or brief.get("watch_count") or 0)
    avg_readiness = safe_float(gate_summary.get("avg_readiness"))
    data_allowed = bool(freshness.get("alerts_allowed", True))
    realtime_allowed = bool(realtime.get("alerts_allowed", True))
    realtime_stock_allowed = bool(realtime.get("stock_alerts_allowed", True))
    realtime_crypto_allowed = bool(realtime.get("crypto_alerts_allowed", True))
    market_realtime = realtime.get("market_realtime") if isinstance(realtime.get("market_realtime"), dict) else {}
    realtime_blocked_markets = [
        safe_text(item).lower()
        for item in (market_realtime.get("blocked_markets") if isinstance(market_realtime.get("blocked_markets"), list) else [])
        if safe_text(item)
    ]
    chart_coverage = chart_contract_coverage_snapshot(brief)
    chart_blocked_markets = [
        safe_text(item).lower()
        for item in (
            chart_coverage.get("chart_contract_blocked_markets")
            if isinstance(chart_coverage.get("chart_contract_blocked_markets"), list)
            else []
        )
        if safe_text(item)
    ]
    for market in chart_blocked_markets:
        if market not in realtime_blocked_markets:
            realtime_blocked_markets.append(market)
    session_stock_allowed = bool(session.get("stock_alerts_allowed", True))
    stock_realtime_unblocked = "stock" not in set(realtime_blocked_markets)
    crypto_realtime_unblocked = "crypto" not in set(realtime_blocked_markets)
    options_realtime_unblocked = "options" not in set(realtime_blocked_markets)
    stock_allowed = bool(data_allowed and realtime_allowed and session_stock_allowed and realtime_stock_allowed and stock_realtime_unblocked)
    crypto_allowed = bool(data_allowed and realtime_allowed and realtime_crypto_allowed and crypto_realtime_unblocked)
    options_allowed = bool(stock_allowed and options_realtime_unblocked)
    blocked_realtime = int(gate_summary.get("blocked_realtime_count") or 0)
    top_setup = top_opportunity_snapshot(brief)
    watchlist = opportunity_watchlist_snapshot(brief)
    stock_context_blocked = (
        realtime_allowed
        and not realtime_stock_allowed
        and any(safe_text(row.get("market")).lower() == "stock" for row in watchlist)
    )
    effective_blocked_realtime = max(blocked_realtime, 1 if stock_context_blocked else 0)
    if stock_context_blocked and not realtime_blocked_markets:
        realtime_blocked_markets = ["stock", "options"]
    market_coverage = market_alert_coverage_snapshot(
        brief,
        realtime_stock_allowed=bool(realtime_stock_allowed and stock_realtime_unblocked),
        realtime_crypto_allowed=bool(realtime_crypto_allowed and crypto_realtime_unblocked),
        blocked_markets=realtime_blocked_markets,
    )
    daily_plan = brief.get("daily_opportunity_plan") if isinstance(brief.get("daily_opportunity_plan"), dict) else {}
    daily_rotation_blocked_symbols = daily_plan_rotation_blocked_symbols(daily_plan)

    if ready > 0:
        state = "READY"
    elif total <= 0:
        state = "NO_SETUPS"
    elif not data_allowed or not realtime_allowed:
        state = "BLOCKED_DATA"
    elif effective_blocked_realtime:
        state = "BLOCKED_REALTIME"
    else:
        state = "WAITING"

    return {
        "generated_at": generated_at,
        "recorded_at": current.isoformat(),
        "state": state,
        "total_opportunities": total,
        "alert_count": alert_count,
        "watch_count": watch_count,
        "notifications_ready": ready,
        "ready_ratio": float(gate_summary.get("ready_ratio") or 0.0),
        "avg_readiness": avg_readiness,
        "top_gate": safe_text(gate_summary.get("top_gate") or "-"),
        "top_gate_label": safe_text(gate_summary.get("top_gate_label") or "-"),
        "top_blocker": safe_text(gate_summary.get("top_blocker") or "-"),
        "top_quality": safe_text(gate_summary.get("top_quality") or "-"),
        "top_readiness": safe_float(gate_summary.get("top_readiness")),
        "blocked_realtime_count": effective_blocked_realtime,
        "data_alerts_allowed": data_allowed,
        "realtime_alerts_allowed": realtime_allowed,
        "realtime_stock_alerts_allowed": realtime_stock_allowed,
        "realtime_crypto_alerts_allowed": realtime_crypto_allowed,
        "realtime_blocked_markets": realtime_blocked_markets,
        "stock_alerts_allowed": stock_allowed,
        "crypto_alerts_allowed": crypto_allowed,
        "options_alerts_allowed": options_allowed,
        "session_stock_alerts_allowed": session_stock_allowed,
        "data_label": safe_text(freshness.get("label") or "-"),
        "health_label": safe_text(realtime.get("label") or "-"),
        "stock_session": safe_text(session.get("stock_session") or "-"),
        "top_setup": top_setup,
        "setup_watchlist": watchlist,
        "daily_plan_rotation_blocked_symbols": daily_rotation_blocked_symbols,
        "daily_plan_rotation_blocked_symbol_count": len(daily_rotation_blocked_symbols),
        **market_coverage,
        **chart_coverage,
        "top_symbol": safe_text(top_setup.get("symbol") or "-") if top_setup else "-",
        "top_next_action": safe_text(top_setup.get("next_action") or "-") if top_setup else "-",
    }


def waiting_diagnostic_category(latest: dict[str, Any], blocker: str, gate: str, *, blocker_streak: int) -> dict[str, str]:
    state = safe_text(latest.get("state") or "").upper()
    if state != "WAITING":
        return {"category": "OTHER", "severity": "OK", "label": "Normal", "detail": blocker or state}
    if not bool(latest.get("data_alerts_allowed", True)) or not bool(latest.get("realtime_alerts_allowed", True)):
        return {"category": "DATA_BLOCK", "severity": "ATTENTION", "label": "Datos bloquean", "detail": blocker or "Datos no listos"}
    blocked_realtime = int(latest.get("blocked_realtime_count") or 0)
    if blocked_realtime:
        return {
            "category": "REALTIME_BLOCK",
            "severity": "ATTENTION",
            "label": "Realtime bloquea",
            "detail": blocker or f"{blocked_realtime} setups bloqueados por datos",
        }
    top_setup = latest.get("top_setup") if isinstance(latest.get("top_setup"), dict) else {}
    setup_market = safe_text(top_setup.get("market") or "").lower()
    stock_session = safe_text(latest.get("stock_session") or "").lower()
    stock_closed = bool(latest.get("stock_alerts_allowed") is False) and (
        "cerr" in stock_session or "closed" in stock_session or not stock_session
    )
    stock_setup = setup_market in {"stock", "stocks", "equity", "option", "options", "-"}
    if stock_closed and stock_setup:
        return {
            "category": "MARKET_CLOSED_WAIT",
            "severity": "WATCH",
            "label": "Mercado cerrado",
            "detail": "La entrada 15m debe revalidarse cuando abra la sesion",
        }
    gate_value = safe_text(latest.get("top_gate") or "").upper()
    gate_label = safe_text(gate or "")
    blocker_value = safe_text(blocker or "")
    gate_label_lower = gate_label.lower()
    blocker_lower = blocker_value.lower()
    if gate_value == "WAIT_15M_ENTRY" or "15M" in gate_label.upper() or "15m da entrada" in blocker_value.lower():
        label = "Esperando gatillo 15m"
        if blocker_streak >= 12:
            label = f"Esperando gatillo x{blocker_streak}"
        return {
            "category": "MARKET_TRIGGER_WAIT",
            "severity": "WATCH",
            "label": label,
            "detail": blocker_value or gate_label or "Entrada 15m aun no confirma",
        }
    if (
        gate_value == "WAIT_VOLUME"
        or "volumen" in blocker_lower
        or "volumen" in gate_label_lower
        or "1h confirma" in blocker_lower
        or "2h/4h" in blocker_lower
        or "confirm" in blocker_lower
        or "target" in blocker_lower
        or "reward/risk" in blocker_lower
        or "riesgo" in blocker_lower
    ):
        if gate_value == "WAIT_VOLUME" or "volumen" in blocker_lower or "volumen" in gate_label_lower:
            label_base = "Esperando volumen"
        elif "target" in blocker_lower or "reward/risk" in blocker_lower or "riesgo" in blocker_lower:
            label_base = "Esperando riesgo/target"
        else:
            label_base = "Esperando confirmacion"
        return {
            "category": "MARKET_CONFIRMATION_WAIT",
            "severity": "WATCH" if blocker_streak >= 3 else "OK",
            "label": f"{label_base} x{blocker_streak}" if blocker_streak >= 3 else label_base,
            "detail": blocker_value or gate_label or "Falta confirmacion de volumen, tendencia o riesgo/target",
        }
    severity = "ATTENTION" if blocker_streak >= 12 else "WATCH" if blocker_streak >= 3 else "OK"
    label = f"Bloqueador x{blocker_streak}" if blocker_streak >= 3 else "Esperando"
    return {
        "category": "UNCLASSIFIED_WAIT",
        "severity": severity,
        "label": label,
        "detail": blocker_value or gate_label or "Esperando condicion de alerta",
    }


def alert_silence_diagnostic(
    latest: dict[str, Any],
    *,
    latest_state: str,
    latest_ready: int,
    latest_total: int,
    waiting_streak: int,
    blocker_category: str,
    diagnostic_severity: str,
) -> dict[str, Any]:
    data_allowed = bool(latest.get("data_alerts_allowed", True))
    realtime_allowed = bool(latest.get("realtime_alerts_allowed", True))
    stock_allowed = bool(latest.get("stock_alerts_allowed", True))
    realtime_stock_allowed = bool(latest.get("realtime_stock_alerts_allowed", True))
    realtime_crypto_allowed = bool(latest.get("realtime_crypto_alerts_allowed", True))
    blocked_markets = [
        safe_text(item).lower()
        for item in (latest.get("realtime_blocked_markets") if isinstance(latest.get("realtime_blocked_markets"), list) else [])
        if safe_text(item)
    ]
    latest_readiness = trigger_review_readiness(latest)
    chart_operable_count = int(latest.get("chart_contract_operable_count") or 0)
    chart_blocked_count = int(latest.get("chart_contract_blocked_count") or 0)
    charts_operable = chart_operable_count > 0 and chart_blocked_count == 0
    if latest_ready > 0 or latest_state == "READY":
        return {
            "silence_mode": "ACTIONABLE_READY",
            "silence_severity": "OK",
            "silence_reason": f"{latest_ready} alerta(s) listas",
            "false_positive_guard": True,
            "false_negative_risk": "LOW",
        }
    if not data_allowed or not realtime_allowed:
        return {
            "silence_mode": "SYSTEM_BLOCKED",
            "silence_severity": "ATTENTION",
            "silence_reason": "Datos o realtime bloquean la emision de alertas",
            "false_positive_guard": True,
            "false_negative_risk": "HIGH",
        }
    if (
        latest_state == "BLOCKED_REALTIME"
        and not realtime_stock_allowed
        and realtime_crypto_allowed
        and "crypto" not in set(blocked_markets)
    ):
        markets = ", ".join(blocked_markets) if blocked_markets else "stock/options"
        return {
            "silence_mode": "MARKET_PARTIAL_BLOCK",
            "silence_severity": "ATTENTION",
            "silence_reason": f"{markets} bloqueado por proveedor premium; cripto sigue permitido",
            "false_positive_guard": True,
            "false_negative_risk": "MEDIUM",
            "blocked_markets": blocked_markets,
        }
    if latest_state == "BLOCKED_REALTIME" and int(latest.get("chart_contract_blocked_count") or 0) > 0:
        chart_blocked_markets = [
            safe_text(item).lower()
            for item in (
                latest.get("chart_contract_blocked_markets")
                if isinstance(latest.get("chart_contract_blocked_markets"), list)
                else blocked_markets
            )
            if safe_text(item)
        ]
        markets = ", ".join(chart_blocked_markets) if chart_blocked_markets else "mercado actual"
        return {
            "silence_mode": "CHART_CONTRACT_BLOCK",
            "silence_severity": "ATTENTION",
            "silence_reason": f"Graficas sin contrato realtime: {markets}",
            "false_positive_guard": True,
            "false_negative_risk": "HIGH",
            "blocked_markets": chart_blocked_markets,
        }
    if latest_state in {"BLOCKED_DATA", "BLOCKED_REALTIME"}:
        return {
            "silence_mode": "SYSTEM_BLOCKED",
            "silence_severity": "ATTENTION",
            "silence_reason": "Datos o realtime bloquean la emision de alertas",
            "false_positive_guard": True,
            "false_negative_risk": "HIGH",
        }
    if blocker_category in {"MARKET_CLOSED_WAIT", "MARKET_TRIGGER_WAIT", "MARKET_CONFIRMATION_WAIT"}:
        trigger_ready_for_watch = latest_readiness is not None and latest_readiness >= MISSED_TRIGGER_READY_WATCH_THRESHOLD
        trigger_near_ready_review = (
            latest_readiness is not None
            and latest_readiness >= MISSED_TRIGGER_NEAR_READY_REVIEW_THRESHOLD
            and waiting_streak >= MISSED_TRIGGER_REVIEW_STREAK
        )
        if (
            blocker_category == "MARKET_TRIGGER_WAIT"
            and waiting_streak >= MISSED_TRIGGER_WATCH_MIN_STREAK
            and latest_total > 0
            and latest_ready == 0
            and (trigger_ready_for_watch or trigger_near_ready_review)
            and charts_operable
        ):
            reason = (
                f"Setup listo, pero gatillo 15m lleva {waiting_streak} ciclos pendiente"
                if trigger_ready_for_watch
                else f"Setup casi listo, pero gatillo 15m lleva {waiting_streak} ciclos pendiente"
            )
            review_due = waiting_streak >= MISSED_TRIGGER_REVIEW_STREAK
            risk = "HIGH" if review_due and trigger_ready_for_watch else "MEDIUM"
            severity = "ATTENTION" if review_due else "WATCH"
            action = (
                "Revalidar manualmente candidatos rotados en 15m/1h; si el gatillo no confirma, rotar o descartar."
                if review_due
                else (
                    "Revisar manualmente candidatos rotados en 15m/1h; "
                    "mantener alerta bloqueada hasta confirmacion 15m"
                )
            )
            return {
                "silence_mode": "MISSED_TRIGGER_WATCH",
                "silence_severity": severity,
                "silence_reason": reason,
                "false_positive_guard": True,
                "false_negative_risk": risk,
                "missed_opportunity_watch": True,
                "missed_opportunity_risk": risk,
                "missed_opportunity_reason": reason,
                "missed_opportunity_action": action,
                "missed_opportunity_review_due": review_due,
                "missed_opportunity_max_watch_cycles": MISSED_TRIGGER_REVIEW_STREAK,
            }
        reason = {
            "MARKET_CLOSED_WAIT": "Mercado cerrado; la entrada debe revalidarse en apertura",
            "MARKET_TRIGGER_WAIT": "Hay setups, pero falta gatillo 15m",
            "MARKET_CONFIRMATION_WAIT": "Hay setups, pero falta confirmacion de volumen/target",
        }[blocker_category]
        return {
            "silence_mode": "HEALTHY_WAIT",
            "silence_severity": "WATCH",
            "silence_reason": reason,
            "false_positive_guard": True,
            "false_negative_risk": "LOW" if blocker_category == "MARKET_CLOSED_WAIT" or not stock_allowed else "MEDIUM",
            "missed_opportunity_watch": False,
            "missed_opportunity_risk": "LOW",
            "missed_opportunity_reason": "",
            "missed_opportunity_action": "",
        }
    if latest_state == "NO_SETUPS" or latest_total <= 0:
        severity = "WATCH" if waiting_streak >= 12 else "OK"
        return {
            "silence_mode": "NO_SETUP_SILENCE",
            "silence_severity": severity,
            "silence_reason": "Scanner sin oportunidades actuales",
            "false_positive_guard": True,
            "false_negative_risk": "MEDIUM" if waiting_streak >= 12 else "LOW",
        }
    if latest_state == "WAITING" and diagnostic_severity == "ATTENTION":
        return {
            "silence_mode": "SUSPICIOUS_SILENCE",
            "silence_severity": "ATTENTION",
            "silence_reason": "Bloqueador persistente sin clasificacion operativa",
            "false_positive_guard": False,
            "false_negative_risk": "HIGH",
        }
    return {
        "silence_mode": "UNCLASSIFIED_SILENCE",
        "silence_severity": "WATCH",
        "silence_reason": "Sin alertas listas; revisar contexto operativo",
        "false_positive_guard": False,
        "false_negative_risk": "MEDIUM",
        "missed_opportunity_watch": False,
        "missed_opportunity_risk": "LOW",
        "missed_opportunity_reason": "",
        "missed_opportunity_action": "",
    }


def summarize_quality_history(rows: list[dict[str, Any]], *, limit: int = 50) -> dict[str, Any]:
    history_rows = list(rows)
    sample = history_rows[-max(1, int(limit)) :]
    if not sample:
        return {
            "sample_size": 0,
            "state": "UNKNOWN",
            "ready_rate": None,
            "waiting_streak": 0,
            "current_streak_state": "UNKNOWN",
            "current_streak_count": 0,
        }
    state_counts: dict[str, int] = {}
    ready_count = 0
    readiness_values: list[float] = []
    readiness_timeline: list[float] = []
    blocker_counts: Counter[str] = Counter()
    gate_counts: Counter[str] = Counter()
    for row in sample:
        state = safe_text(row.get("state") or "UNKNOWN").upper()
        state_counts[state] = state_counts.get(state, 0) + 1
        if int(row.get("notifications_ready") or 0) > 0 or state == "READY":
            ready_count += 1
        readiness = safe_float(row.get("avg_readiness"))
        if readiness is not None:
            readiness_values.append(readiness)
            readiness_timeline.append(readiness)
        blocker = safe_text(row.get("top_blocker") or "-")
        if blocker and blocker != "-":
            blocker_counts[blocker] += 1
        gate = safe_text(row.get("top_gate_label") or row.get("top_gate") or "-")
        if gate and gate != "-":
            gate_counts[gate] += 1
    latest = sample[-1]
    latest_state = safe_text(latest.get("state") or "UNKNOWN").upper()
    latest_blocker = safe_text(latest.get("top_blocker") or "-")
    latest_gate = safe_text(latest.get("top_gate_label") or latest.get("top_gate") or "-")
    streak = 0
    for row in reversed(history_rows):
        if safe_text(row.get("state") or "UNKNOWN").upper() == latest_state:
            streak += 1
        else:
            break
    blocker_streak = 0
    blocker_streak_started_at = None
    if latest_blocker and latest_blocker != "-":
        for row in reversed(history_rows):
            if safe_text(row.get("top_blocker") or "-") == latest_blocker:
                blocker_streak += 1
                blocker_streak_started_at = safe_text(row.get("recorded_at") or row.get("generated_at") or "")
            else:
                break
    gate_streak = 0
    if latest_gate and latest_gate != "-":
        for row in reversed(history_rows):
            gate = safe_text(row.get("top_gate_label") or row.get("top_gate") or "-")
            if gate == latest_gate:
                gate_streak += 1
            else:
                break
    blocked_minutes = None
    started_at = parse_utc_datetime(blocker_streak_started_at)
    latest_recorded_at = parse_utc_datetime(latest.get("recorded_at") or latest.get("generated_at"))
    if started_at is not None and latest_recorded_at is not None:
        blocked_minutes = round(max(0.0, (latest_recorded_at - started_at).total_seconds() / 60.0), 1)
    review_cycle_minutes = None
    if blocked_minutes is not None and blocker_streak > 1:
        review_cycle_minutes = round(blocked_minutes / max(1, blocker_streak - 1), 1)
    waiting_streak = streak if latest_state in {"WAITING", "NO_SETUPS"} else 0
    daily_rotation_blocked_symbols = (
        latest.get("daily_plan_rotation_blocked_symbols")
        if isinstance(latest.get("daily_plan_rotation_blocked_symbols"), list)
        else []
    )
    severity = "OK"
    diagnostic_label = "Normal"
    diagnostic_detail = "Alert quality operating normally"
    latest_ready = int(latest.get("notifications_ready") or 0)
    latest_total = int(latest.get("total_opportunities") or 0)
    blocker_category = ""
    recommended_action = ""
    rotation_candidates = []
    latest_watchlist: list[Any] = []
    if latest_state in {"BLOCKED_DATA", "BLOCKED_REALTIME"}:
        severity = "ATTENTION"
        chart_blocked_markets = [
            safe_text(item).lower()
            for item in (
                latest.get("chart_contract_blocked_markets")
                if isinstance(latest.get("chart_contract_blocked_markets"), list)
                else []
            )
            if safe_text(item)
        ]
        chart_blocked_count = int(latest.get("chart_contract_blocked_count") or 0)
        effective_blocked_markets = [
            safe_text(item).lower()
            for item in (
                latest.get("realtime_blocked_markets")
                if isinstance(latest.get("realtime_blocked_markets"), list)
                else []
            )
            if safe_text(item)
        ]
        partial_market_block = (
            latest_state == "BLOCKED_REALTIME"
            and latest.get("realtime_stock_alerts_allowed") is False
            and latest.get("realtime_crypto_alerts_allowed") is True
            and "crypto" not in set(effective_blocked_markets)
        )
        if partial_market_block:
            markets = ", ".join(effective_blocked_markets) if effective_blocked_markets else "stock/options"
            diagnostic_label = "Bloqueo parcial"
            diagnostic_detail = f"{markets} bloqueado por proveedor premium; cripto sigue permitido"
            blocker_category = "MARKET_PARTIAL_BLOCK"
            recommended_action = premium_recovery_action_from_blocker(latest_blocker) or PREMIUM_PROVIDER_RECOVERY_ACTION
        elif latest_state == "BLOCKED_REALTIME" and chart_blocked_count > 0:
            markets = ", ".join(chart_blocked_markets) if chart_blocked_markets else "mercado actual"
            diagnostic_label = "Graficas bloquean"
            diagnostic_detail = f"Graficas sin contrato realtime: {markets}"
            blocker_category = "CHART_CONTRACT_BLOCK"
            recommended_action = (
                safe_text(latest.get("chart_contract_action"))
                or "No emitir alertas hasta recuperar contrato realtime de grafica."
            )
        else:
            diagnostic_label = "Datos bloquean"
            diagnostic_detail = latest_blocker if latest_blocker != "-" else latest_state
    elif latest_ready > 0 or latest_state == "READY":
        diagnostic_label = "Lista"
        diagnostic_detail = f"{latest_ready}/{latest_total} opportunities ready"
    elif latest_state == "WAITING" and latest_total > 0:
        category = waiting_diagnostic_category(latest, latest_blocker, latest_gate, blocker_streak=blocker_streak)
        blocker_category = category["category"]
        severity = category["severity"]
        diagnostic_label = category["label"]
        diagnostic_detail = category["detail"]
        latest_watchlist = latest.get("setup_watchlist") if isinstance(latest.get("setup_watchlist"), list) else []
        rotation_candidates = rotation_candidate_summary(
            [row for row in latest_watchlist if isinstance(row, dict)]
        )
        if blocker_category == "MARKET_CLOSED_WAIT":
            blocker_streak = 0
            blocked_minutes = None
            rotation_candidates = []
            recommended_action = "Mercado cerrado; mantener watchlist y revalidar entrada en la apertura"
        elif blocker_category == "MARKET_TRIGGER_WAIT":
            recommended_action = "Mantener watchlist; no alertar hasta que 15m confirme entrada"
            if blocker_streak >= 24 and rotation_candidates:
                if len(rotation_candidates) > 1:
                    recommended_action = (
                        "Rotar foco: "
                        + ", ".join(rotation_candidates)
                        + "; no alertar hasta que 15m confirme entrada"
                    )
                else:
                    recommended_action = (
                        "Pausar foco: "
                        + rotation_candidates[0]
                        + "; esperar nuevo candidato o confirmacion 15m"
                    )
        elif blocker_category == "MARKET_CONFIRMATION_WAIT":
            recommended_action = "Esperar confirmacion de volumen/target antes de alertar"
    elif latest_state == "NO_SETUPS":
        diagnostic_label = "Sin setups"
        diagnostic_detail = "No opportunities in current brief"
        recommended_action = "Seguir escaneando; no hay oportunidades actuales"
    dominant_blocker_name = ""
    dominant_blocker_count = 0
    if blocker_counts:
        dominant_blocker_name, dominant_blocker_count = blocker_counts.most_common(1)[0]
    dominant_gate_name = ""
    dominant_gate_count = 0
    if gate_counts:
        dominant_gate_name, dominant_gate_count = gate_counts.most_common(1)[0]
    if blocker_category == "MARKET_CLOSED_WAIT":
        dominant_blocker_name = ""
        dominant_blocker_count = 0
    readiness_delta = None
    if len(readiness_timeline) >= 2:
        readiness_delta = round(readiness_timeline[-1] - readiness_timeline[0], 1)
    silence_waiting_streak = waiting_streak
    if (
        latest_state == "WAITING"
        and blocker_category == "MARKET_TRIGGER_WAIT"
        and dominant_blocker_name
        and dominant_blocker_name == latest_blocker
    ):
        silence_waiting_streak = max(waiting_streak, blocker_streak, dominant_blocker_count)
    silence = alert_silence_diagnostic(
        latest,
        latest_state=latest_state,
        latest_ready=latest_ready,
        latest_total=latest_total,
        waiting_streak=silence_waiting_streak,
        blocker_category=blocker_category,
        diagnostic_severity=severity,
    )
    missed_trigger_plan = missed_trigger_watch_plan(
        active=bool(silence.get("missed_opportunity_watch") or silence.get("silence_mode") == "MISSED_TRIGGER_WATCH"),
        latest=latest,
        rotation_candidates=rotation_candidates,
        waiting_streak=silence_waiting_streak,
        blocker_streak=blocker_streak,
        persistent_minutes=blocked_minutes,
        review_cycle_minutes=review_cycle_minutes,
        readiness_delta=readiness_delta,
        risk=safe_text(silence.get("missed_opportunity_risk") or silence.get("false_negative_risk") or ""),
        reason=safe_text(silence.get("missed_opportunity_reason") or silence.get("silence_reason") or ""),
        action=safe_text(silence.get("missed_opportunity_action") or recommended_action or ""),
        rotation_blocked_symbols=daily_rotation_blocked_symbols,
    )
    confirmation_wait_plan = confirmation_wait_review_plan(
        active=bool(
            latest_state == "WAITING"
            and blocker_category == "MARKET_CONFIRMATION_WAIT"
            and latest_total > 0
            and latest_ready == 0
        ),
        latest=latest,
        rotation_candidates=rotation_candidates,
        waiting_streak=max(waiting_streak, blocker_streak, dominant_blocker_count),
        blocker_streak=blocker_streak,
        persistent_minutes=blocked_minutes,
        review_cycle_minutes=review_cycle_minutes,
        reason=safe_text(silence.get("silence_reason") or diagnostic_detail),
        action=recommended_action,
        rotation_blocked_symbols=daily_rotation_blocked_symbols,
    )
    plan_review_action = ""
    if isinstance(missed_trigger_plan, dict) and missed_trigger_plan.get("active") and missed_trigger_plan.get("review_due"):
        plan_review_action = safe_text(
            missed_trigger_plan.get("review_action") or missed_trigger_plan.get("decision_action") or ""
        )
    elif (
        isinstance(confirmation_wait_plan, dict)
        and confirmation_wait_plan.get("active")
        and confirmation_wait_plan.get("review_due")
    ):
        plan_review_action = safe_text(confirmation_wait_plan.get("review_action") or "")
    if plan_review_action:
        recommended_action = plan_review_action
    blocked_route_markets = (
        latest.get("realtime_blocked_markets")
        if isinstance(latest.get("realtime_blocked_markets"), list)
        else []
    )
    blocked_route_markets = [
        safe_text(item).lower()
        for item in blocked_route_markets
        if safe_text(item)
    ]
    blocked_route_market_count = len(set(blocked_route_markets))
    blocked_opportunity_market_count = int(latest.get("blocked_market_count") or 0)
    return {
        "sample_size": len(sample),
        "state": latest_state,
        "state_counts": dict(sorted(state_counts.items(), key=lambda item: (-item[1], item[0]))),
        "ready_count": ready_count,
        "ready_rate": round(ready_count / len(sample), 4),
        "avg_readiness": round(sum(readiness_values) / len(readiness_values), 1) if readiness_values else None,
        "latest_readiness": readiness_timeline[-1] if readiness_timeline else None,
        "readiness_delta": readiness_delta,
        "waiting_streak": waiting_streak,
        "current_streak_state": latest_state,
        "current_streak_count": streak,
        "latest_top_gate": latest_gate,
        "latest_top_blocker": latest_blocker,
        "latest_top_blocker_streak": blocker_streak,
        "latest_top_gate_streak": gate_streak,
        "persistent_blocker": latest_blocker if blocker_streak >= 3 and latest_blocker != "-" else "",
        "persistent_blocker_minutes": blocked_minutes,
        "persistent_blocker_cycle_minutes": review_cycle_minutes,
        "dominant_blocker": {"name": dominant_blocker_name, "count": dominant_blocker_count} if dominant_blocker_name else {},
        "dominant_gate": {"name": dominant_gate_name, "count": dominant_gate_count} if dominant_gate_name else {},
        "diagnostic_severity": severity,
        "diagnostic_label": diagnostic_label,
        "diagnostic_detail": diagnostic_detail,
        "blocker_category": blocker_category,
        "recommended_action": recommended_action,
        "rotation_candidates": rotation_candidates,
        "missed_trigger_plan": missed_trigger_plan,
        "confirmation_wait_plan": confirmation_wait_plan,
        **silence,
        "latest_notifications_ready": latest_ready,
        "latest_total_opportunities": latest_total,
        "market_counts": latest.get("market_counts") if isinstance(latest.get("market_counts"), dict) else {},
        "actionable_market_counts": (
            latest.get("actionable_market_counts") if isinstance(latest.get("actionable_market_counts"), dict) else {}
        ),
        "allowed_markets": latest.get("allowed_markets") if isinstance(latest.get("allowed_markets"), list) else [],
        "missing_allowed_markets": (
            latest.get("missing_allowed_markets") if isinstance(latest.get("missing_allowed_markets"), list) else []
        ),
        "operable_market_count": int(latest.get("operable_market_count") or 0),
        "blocked_market_count": int(latest.get("blocked_market_count") or 0),
        "blocked_route_markets": blocked_route_markets,
        "blocked_route_market_count": blocked_route_market_count,
        "blocked_opportunity_market_count": blocked_opportunity_market_count,
        "market_coverage_label": safe_text(latest.get("market_coverage_label") or ""),
        "market_coverage_action": safe_text(latest.get("market_coverage_action") or ""),
        "chart_contract_total_count": int(latest.get("chart_contract_total_count") or 0),
        "chart_contract_checked_count": int(latest.get("chart_contract_checked_count") or 0),
        "chart_contract_operable_count": int(latest.get("chart_contract_operable_count") or 0),
        "chart_contract_blocked_count": int(latest.get("chart_contract_blocked_count") or 0),
        "chart_contract_missing_count": int(latest.get("chart_contract_missing_count") or 0),
        "chart_contract_blocked_markets": (
            latest.get("chart_contract_blocked_markets")
            if isinstance(latest.get("chart_contract_blocked_markets"), list)
            else []
        ),
        "chart_contract_market_counts": (
            latest.get("chart_contract_market_counts")
            if isinstance(latest.get("chart_contract_market_counts"), dict)
            else {}
        ),
        "chart_contract_market_operable_counts": (
            latest.get("chart_contract_market_operable_counts")
            if isinstance(latest.get("chart_contract_market_operable_counts"), dict)
            else {}
        ),
        "chart_contract_market_blocked_counts": (
            latest.get("chart_contract_market_blocked_counts")
            if isinstance(latest.get("chart_contract_market_blocked_counts"), dict)
            else {}
        ),
        "chart_contract_gate_counts": (
            latest.get("chart_contract_gate_counts")
            if isinstance(latest.get("chart_contract_gate_counts"), dict)
            else {}
        ),
        "chart_contract_operable_symbols": (
            latest.get("chart_contract_operable_symbols")
            if isinstance(latest.get("chart_contract_operable_symbols"), list)
            else []
        ),
        "chart_contract_blocked_symbols": (
            latest.get("chart_contract_blocked_symbols")
            if isinstance(latest.get("chart_contract_blocked_symbols"), list)
            else []
        ),
        "chart_contract_label": safe_text(latest.get("chart_contract_label") or ""),
        "chart_contract_action": safe_text(latest.get("chart_contract_action") or ""),
    }


def alert_quality_label_tone(summary: dict[str, Any], entry: dict[str, Any]) -> dict[str, str]:
    label = safe_text(summary.get("diagnostic_label") or entry.get("state") or "Normal")
    severity = safe_text(summary.get("diagnostic_severity") or summary.get("silence_severity") or "OK").upper()
    state = safe_text(summary.get("state") or entry.get("state") or "").upper()
    if state == "READY":
        tone = "buy"
    elif severity in {"ATTENTION", "HIGH", "FAIL", "ERROR"}:
        tone = "avoid"
    elif severity in {"WATCH", "MEDIUM", "WARN"}:
        tone = "watch"
    elif state in {"WAITING", "NO_SETUPS"}:
        tone = "watch"
    elif state in {"BLOCKED_DATA", "BLOCKED_REALTIME"}:
        tone = "avoid"
    else:
        tone = "buy"
    return {"label": label or "Normal", "tone": tone}


def alert_quality_report_status(summary: dict[str, Any]) -> dict[str, str]:
    diagnostic_severity = safe_text(summary.get("diagnostic_severity") or "").upper()
    silence_severity = safe_text(summary.get("silence_severity") or "").upper()
    false_negative_risk = safe_text(summary.get("false_negative_risk") or "").upper()
    missed_trigger_plan = summary.get("missed_trigger_plan") if isinstance(summary.get("missed_trigger_plan"), dict) else {}
    confirmation_wait_plan = (
        summary.get("confirmation_wait_plan") if isinstance(summary.get("confirmation_wait_plan"), dict) else {}
    )
    partial_block_has_operable_coverage = (
        safe_text(summary.get("blocker_category")).upper() == "MARKET_PARTIAL_BLOCK"
        and safe_text(summary.get("silence_mode")).upper() == "MARKET_PARTIAL_BLOCK"
        and int(summary.get("operable_market_count") or 0) > 0
        and not summary.get("missing_allowed_markets")
        and "operable" in safe_text(summary.get("market_coverage_label")).lower()
    )
    if diagnostic_severity in {"FAIL", "ERROR"} or silence_severity in {"FAIL", "ERROR"}:
        return {"status": "FAIL", "status_reason": "Alert quality failure severity active."}
    missed_trigger_handoff_confirmed = bool(
        missed_trigger_plan.get("rotation_handoff_confirmed")
        and missed_trigger_plan.get("rotation_guard_active")
        and missed_trigger_plan.get("rotation_handoff_status") == "CONFIRMED"
    )
    attention_unexplained = (
        diagnostic_severity in {"ATTENTION", "HIGH"}
        or silence_severity in {"ATTENTION", "HIGH"}
        or false_negative_risk == "HIGH"
    ) and not partial_block_has_operable_coverage and not missed_trigger_handoff_confirmed
    missed_trigger_review_due = bool(summary.get("missed_opportunity_review_due")) or bool(
        missed_trigger_plan.get("review_due")
    )
    if missed_trigger_handoff_confirmed:
        missed_trigger_review_due = False
    confirmation_wait_attention = confirmation_wait_review_requires_attention(
        confirmation_wait_plan,
        false_negative_risk=false_negative_risk,
    )
    if attention_unexplained or missed_trigger_review_due or confirmation_wait_attention:
        return {"status": "WARN", "status_reason": "Alert quality requires manual review or attention."}
    return {"status": "OK", "status_reason": "Alert quality operating within current guardrails."}


def alert_quality_alias_text(*values: Any) -> str:
    for value in values:
        text = safe_text(value).strip()
        if text and text != "-":
            return text
    return ""


def primary_alert_quality_focus(summary: dict[str, Any], entry: dict[str, Any]) -> dict[str, str]:
    top_setup = entry.get("top_setup") if isinstance(entry.get("top_setup"), dict) else {}
    missed_trigger_plan = summary.get("missed_trigger_plan") if isinstance(summary.get("missed_trigger_plan"), dict) else {}
    confirmation_wait_plan = (
        summary.get("confirmation_wait_plan") if isinstance(summary.get("confirmation_wait_plan"), dict) else {}
    )
    rotation_next_symbol = safe_text(missed_trigger_plan.get("rotation_next_symbol") or "")
    if missed_trigger_plan.get("rotation_guard_active") and rotation_next_symbol:
        return {
            "symbol": rotation_next_symbol,
            "source": "ALERT_QUALITY_ROTATION",
            "reason": safe_text(missed_trigger_plan.get("decision_action") or "Rotar foco operativo."),
        }
    discard_symbol = safe_text(missed_trigger_plan.get("discard_symbol") or missed_trigger_plan.get("primary_symbol") or "")
    if missed_trigger_plan.get("discard_guard_active") and discard_symbol:
        return {
            "symbol": discard_symbol,
            "source": "ALERT_QUALITY_DISCARD",
            "reason": safe_text(missed_trigger_plan.get("decision_action") or "Pausar o descartar candidato stale."),
        }
    missed_symbol = safe_text(missed_trigger_plan.get("primary_symbol") or "")
    if missed_trigger_plan.get("active") and missed_symbol:
        return {
            "symbol": missed_symbol,
            "source": "MISSED_TRIGGER_PLAN",
            "reason": safe_text(missed_trigger_plan.get("review_action") or missed_trigger_plan.get("reason") or ""),
        }
    confirmation_symbol = safe_text(confirmation_wait_plan.get("primary_symbol") or "")
    confirmation_rotation_next_symbol = safe_text(confirmation_wait_plan.get("rotation_next_symbol") or "")
    if confirmation_wait_plan.get("rotation_guard_active") and confirmation_rotation_next_symbol:
        return {
            "symbol": confirmation_rotation_next_symbol,
            "source": "ALERT_QUALITY_CONFIRMATION_ROTATION",
            "reason": safe_text(confirmation_wait_plan.get("decision_action") or "Rotar foco por confirmacion vencida."),
        }
    if confirmation_wait_plan.get("active") and confirmation_symbol:
        return {
            "symbol": confirmation_symbol,
            "source": "CONFIRMATION_WAIT_PLAN",
            "reason": safe_text(confirmation_wait_plan.get("review_action") or confirmation_wait_plan.get("reason") or ""),
        }
    top_symbol = alert_quality_alias_text(entry.get("top_symbol"), top_setup.get("symbol"))
    if top_symbol:
        return {
            "symbol": top_symbol,
            "source": "TOP_SETUP",
            "reason": safe_text(entry.get("top_next_action") or top_setup.get("next_action") or ""),
        }
    return {"symbol": "", "source": "", "reason": ""}


def alert_quality_rotation_handoff(
    plan: dict[str, Any],
    focus: dict[str, str],
    *,
    source: str,
) -> dict[str, Any]:
    expected_symbol = safe_text(plan.get("rotation_next_symbol") or "")
    focus_symbol = safe_text(focus.get("symbol") or "")
    focus_source = safe_text(focus.get("source") or "")
    if not plan.get("rotation_guard_active"):
        status = "NOT_REQUESTED"
    elif not expected_symbol:
        status = "MISSING_TARGET"
    elif focus_symbol.upper() != expected_symbol.upper():
        status = "MISMATCH"
    elif focus_source != source:
        status = "PENDING"
    else:
        status = "CONFIRMED"
    return {
        "status": status,
        "expected_symbol": expected_symbol,
        "focus_symbol": focus_symbol,
        "source": focus_source,
        "confirmed": status == "CONFIRMED",
    }


def confirmed_rotation_handoff_action(plan: dict[str, Any]) -> str:
    focus_symbol = safe_text(plan.get("rotation_handoff_focus_symbol") or plan.get("rotation_next_symbol") or "")
    blocked_symbol = safe_text(plan.get("rotation_blocked_symbol") or plan.get("primary_symbol") or "")
    if not focus_symbol:
        return ""
    blocked_detail = f"; mantener {blocked_symbol} bloqueado" if blocked_symbol else ""
    return (
        f"Rotacion confirmada: mantener foco operativo en {focus_symbol}{blocked_detail} "
        "hasta que 15m confirme entrada o cambie la readiness."
    )


def alert_quality_top_level_contract(summary: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    blocked_markets = summary.get("blocked_markets") if isinstance(summary.get("blocked_markets"), list) else []
    if not blocked_markets and isinstance(entry.get("realtime_blocked_markets"), list):
        blocked_markets = entry.get("realtime_blocked_markets") or []
    blocked_route_markets = (
        summary.get("blocked_route_markets")
        if isinstance(summary.get("blocked_route_markets"), list)
        else blocked_markets
    )
    blocked_route_market_count = int(
        summary.get("blocked_route_market_count")
        or len({safe_text(item).lower() for item in blocked_route_markets if safe_text(item)})
        or 0
    )
    blocked_opportunity_market_count = int(
        summary.get("blocked_opportunity_market_count")
        or summary.get("blocked_market_count")
        or 0
    )
    label_tone = alert_quality_label_tone(summary, entry)
    missed_trigger_plan = (
        dict(summary.get("missed_trigger_plan")) if isinstance(summary.get("missed_trigger_plan"), dict) else {}
    )
    confirmation_wait_plan = (
        summary.get("confirmation_wait_plan") if isinstance(summary.get("confirmation_wait_plan"), dict) else {}
    )
    dominant_blocker = summary.get("dominant_blocker") if isinstance(summary.get("dominant_blocker"), dict) else {}
    dominant_gate = summary.get("dominant_gate") if isinstance(summary.get("dominant_gate"), dict) else {}
    top_setup = entry.get("top_setup") if isinstance(entry.get("top_setup"), dict) else {}
    top_symbol = alert_quality_alias_text(entry.get("top_symbol"), top_setup.get("symbol"))
    top_gate = alert_quality_alias_text(summary.get("latest_top_gate"), entry.get("top_gate_label"), entry.get("top_gate"), top_setup.get("gate"))
    top_blocker = alert_quality_alias_text(
        summary.get("latest_top_blocker"),
        entry.get("top_blocker"),
        top_setup.get("primary_blocker"),
    )
    recurrent_blocker = alert_quality_alias_text(summary.get("recurrent_blocker"), dominant_blocker.get("name"))
    recurrent_blocker_count = int(summary.get("recurrent_blocker_count") or dominant_blocker.get("count") or 0)
    recurrent_gate = alert_quality_alias_text(summary.get("recurrent_gate"), dominant_gate.get("name"))
    recurrent_gate_count = int(summary.get("recurrent_gate_count") or dominant_gate.get("count") or 0)
    focus = primary_alert_quality_focus(summary, entry)
    missed_rotation_handoff = alert_quality_rotation_handoff(
        missed_trigger_plan,
        focus,
        source="ALERT_QUALITY_ROTATION",
    )
    missed_trigger_plan.update(
        {
            "rotation_handoff_status": missed_rotation_handoff["status"],
            "rotation_handoff_expected_symbol": missed_rotation_handoff["expected_symbol"],
            "rotation_handoff_focus_symbol": missed_rotation_handoff["focus_symbol"],
            "rotation_handoff_source": missed_rotation_handoff["source"],
            "rotation_handoff_confirmed": missed_rotation_handoff["confirmed"],
        }
    )
    effective_action = safe_text(summary.get("recommended_action") or "")
    effective_focus_reason = focus["reason"]
    if missed_trigger_plan.get("rotation_handoff_confirmed"):
        handoff_action = confirmed_rotation_handoff_action(missed_trigger_plan)
        if handoff_action:
            effective_action = handoff_action
            effective_focus_reason = handoff_action
            missed_trigger_plan["handoff_confirmed_action"] = handoff_action
    primary_symbol = alert_quality_alias_text(entry.get("symbol"), top_symbol, focus["symbol"])
    return {
        "contract_version": 3,
        **label_tone,
        "state": safe_text(summary.get("state") or entry.get("state") or "UNKNOWN"),
        "symbol": primary_symbol,
        "top_symbol": top_symbol,
        "top_gate": top_gate,
        "top_blocker": top_blocker,
        "top_quality": safe_text(entry.get("top_quality") or top_setup.get("quality") or ""),
        "top_readiness": entry.get("top_readiness", top_setup.get("readiness")),
        "top_next_action": safe_text(entry.get("top_next_action") or top_setup.get("next_action") or ""),
        "recurrent_blocker": recurrent_blocker,
        "recurrent_blocker_count": recurrent_blocker_count,
        "recurrent_gate": recurrent_gate,
        "recurrent_gate_count": recurrent_gate_count,
        "persistent_blocker": safe_text(summary.get("persistent_blocker") or ""),
        "persistent_blocker_minutes": summary.get("persistent_blocker_minutes"),
        "latest_top_blocker_streak": int(summary.get("latest_top_blocker_streak") or 0),
        "latest_top_gate_streak": int(summary.get("latest_top_gate_streak") or 0),
        "operational_focus_symbol": focus["symbol"],
        "operational_focus_source": focus["source"],
        "operational_focus_reason": effective_focus_reason,
        "diagnostic_label": safe_text(summary.get("diagnostic_label") or "Normal"),
        "diagnostic_severity": safe_text(summary.get("diagnostic_severity") or "OK"),
        "diagnostic_detail": safe_text(summary.get("diagnostic_detail") or ""),
        "blocker_category": safe_text(summary.get("blocker_category") or ""),
        "diagnostic_category": safe_text(summary.get("blocker_category") or ""),
        "recommended_action": effective_action,
        "action": effective_action,
        "silence_mode": safe_text(summary.get("silence_mode") or ""),
        "silence_reason": safe_text(summary.get("silence_reason") or ""),
        "silence_severity": safe_text(summary.get("silence_severity") or ""),
        "false_negative_risk": safe_text(summary.get("false_negative_risk") or ""),
        "false_positive_guard": bool(summary.get("false_positive_guard", True)),
        "missed_opportunity_watch": bool(summary.get("missed_opportunity_watch", False)),
        "missed_opportunity_risk": safe_text(summary.get("missed_opportunity_risk") or ""),
        "missed_opportunity_reason": safe_text(summary.get("missed_opportunity_reason") or ""),
        "missed_opportunity_action": safe_text(summary.get("missed_opportunity_action") or ""),
        "missed_opportunity_review_due": bool(summary.get("missed_opportunity_review_due", False)),
        "missed_opportunity_max_watch_cycles": int(summary.get("missed_opportunity_max_watch_cycles") or 0),
        "missed_trigger_plan": missed_trigger_plan,
        "missed_trigger_plan_active": bool(missed_trigger_plan.get("active", False)),
        "missed_trigger_plan_symbol": safe_text(missed_trigger_plan.get("primary_symbol") or ""),
        "missed_trigger_plan_readiness": missed_trigger_plan.get("primary_readiness"),
        "missed_trigger_plan_risk": safe_text(missed_trigger_plan.get("risk") or ""),
        "missed_trigger_plan_review_due": bool(missed_trigger_plan.get("review_due", False)),
        "missed_trigger_plan_review_status": safe_text(missed_trigger_plan.get("review_status") or ""),
        "missed_trigger_plan_review_pressure": safe_text(missed_trigger_plan.get("review_pressure") or ""),
        "missed_trigger_plan_review_overdue_cycles": int(
            missed_trigger_plan.get("review_overdue_cycles") or 0
        ),
        "missed_trigger_plan_review_cycles_remaining": int(
            missed_trigger_plan.get("review_cycles_remaining") or 0
        ),
        "missed_trigger_plan_review_progress": missed_trigger_plan.get("review_progress"),
        "missed_trigger_plan_review_cycle_minutes": missed_trigger_plan.get("review_cycle_minutes"),
        "missed_trigger_plan_review_eta_minutes": missed_trigger_plan.get("review_eta_minutes"),
        "missed_trigger_plan_review_overdue_minutes": missed_trigger_plan.get("review_overdue_minutes"),
        "missed_trigger_plan_severity": safe_text(missed_trigger_plan.get("severity") or ""),
        "missed_trigger_plan_stale_candidate": bool(missed_trigger_plan.get("stale_candidate", False)),
        "missed_trigger_plan_auto_review_decision": safe_text(
            missed_trigger_plan.get("auto_review_decision") or ""
        ),
        "missed_trigger_plan_decision_reason": safe_text(missed_trigger_plan.get("decision_reason") or ""),
        "missed_trigger_plan_decision_action": safe_text(missed_trigger_plan.get("decision_action") or ""),
        "missed_trigger_plan_readiness_delta": missed_trigger_plan.get("readiness_delta"),
        "missed_trigger_plan_rotation_guard_active": bool(
            missed_trigger_plan.get("rotation_guard_active", False)
        ),
        "missed_trigger_plan_rotation_blocked_symbol": safe_text(
            missed_trigger_plan.get("rotation_blocked_symbol") or ""
        ),
        "missed_trigger_plan_rotation_alternates": (
            missed_trigger_plan.get("rotation_alternates")
            if isinstance(missed_trigger_plan.get("rotation_alternates"), list)
            else []
        ),
        "missed_trigger_plan_rotation_blocked_by_daily_plan": (
            missed_trigger_plan.get("rotation_blocked_by_daily_plan")
            if isinstance(missed_trigger_plan.get("rotation_blocked_by_daily_plan"), list)
            else []
        ),
        "missed_trigger_plan_rotation_daily_blocked_count": len(
            missed_trigger_plan.get("rotation_blocked_by_daily_plan")
            if isinstance(missed_trigger_plan.get("rotation_blocked_by_daily_plan"), list)
            else []
        ),
        "missed_trigger_plan_rotation_next_symbol": safe_text(
            missed_trigger_plan.get("rotation_next_symbol") or ""
        ),
        "missed_trigger_plan_rotation_cooldown_cycles": int(
            missed_trigger_plan.get("rotation_cooldown_cycles") or 0
        ),
        "missed_trigger_plan_rotation_cooldown_eta_minutes": missed_trigger_plan.get(
            "rotation_cooldown_eta_minutes"
        ),
        "missed_trigger_plan_rotation_resume_condition": safe_text(
            missed_trigger_plan.get("rotation_resume_condition") or ""
        ),
        "missed_trigger_plan_rotation_handoff_confirmed": bool(
            missed_trigger_plan.get("rotation_handoff_confirmed", False)
        ),
        "missed_trigger_plan_rotation_handoff_status": safe_text(
            missed_trigger_plan.get("rotation_handoff_status") or ""
        ),
        "missed_trigger_plan_rotation_handoff_expected_symbol": safe_text(
            missed_trigger_plan.get("rotation_handoff_expected_symbol") or ""
        ),
        "missed_trigger_plan_rotation_handoff_focus_symbol": safe_text(
            missed_trigger_plan.get("rotation_handoff_focus_symbol") or ""
        ),
        "missed_trigger_plan_rotation_handoff_source": safe_text(
            missed_trigger_plan.get("rotation_handoff_source") or ""
        ),
        "missed_trigger_plan_rotation_handoff_symbol": safe_text(
            missed_trigger_plan.get("rotation_handoff_focus_symbol") or ""
        ),
        "missed_trigger_plan_handoff_confirmed_action": safe_text(
            missed_trigger_plan.get("handoff_confirmed_action") or ""
        ),
        "missed_trigger_plan_discard_guard_active": bool(
            missed_trigger_plan.get("discard_guard_active", False)
        ),
        "missed_trigger_plan_discard_symbol": safe_text(missed_trigger_plan.get("discard_symbol") or ""),
        "missed_trigger_plan_discard_reason": safe_text(missed_trigger_plan.get("discard_reason") or ""),
        "missed_trigger_plan_discard_cooldown_cycles": int(
            missed_trigger_plan.get("discard_cooldown_cycles") or 0
        ),
        "missed_trigger_plan_discard_cooldown_eta_minutes": missed_trigger_plan.get(
            "discard_cooldown_eta_minutes"
        ),
        "missed_trigger_plan_discard_resume_condition": safe_text(
            missed_trigger_plan.get("discard_resume_condition") or ""
        ),
        "missed_trigger_plan_max_watch_cycles": int(missed_trigger_plan.get("max_watch_cycles") or 0),
        "missed_trigger_plan_review_action": safe_text(missed_trigger_plan.get("review_action") or ""),
        "missed_trigger_plan_exit": safe_text(missed_trigger_plan.get("exit_condition") or ""),
        "confirmation_wait_plan": confirmation_wait_plan,
        "confirmation_wait_plan_active": bool(confirmation_wait_plan.get("active", False)),
        "confirmation_wait_plan_symbol": safe_text(confirmation_wait_plan.get("primary_symbol") or ""),
        "confirmation_wait_plan_readiness": confirmation_wait_plan.get("primary_readiness"),
        "confirmation_wait_plan_risk": safe_text(confirmation_wait_plan.get("risk") or ""),
        "confirmation_wait_plan_review_due": bool(confirmation_wait_plan.get("review_due", False)),
        "confirmation_wait_plan_review_status": safe_text(confirmation_wait_plan.get("review_status") or ""),
        "confirmation_wait_plan_review_pressure": safe_text(confirmation_wait_plan.get("review_pressure") or ""),
        "confirmation_wait_plan_review_overdue_cycles": int(
            confirmation_wait_plan.get("review_overdue_cycles") or 0
        ),
        "confirmation_wait_plan_review_cycles_remaining": int(
            confirmation_wait_plan.get("review_cycles_remaining") or 0
        ),
        "confirmation_wait_plan_review_progress": confirmation_wait_plan.get("review_progress"),
        "confirmation_wait_plan_review_cycle_minutes": confirmation_wait_plan.get("review_cycle_minutes"),
        "confirmation_wait_plan_review_eta_minutes": confirmation_wait_plan.get("review_eta_minutes"),
        "confirmation_wait_plan_review_overdue_minutes": confirmation_wait_plan.get("review_overdue_minutes"),
        "confirmation_wait_plan_severity": safe_text(confirmation_wait_plan.get("severity") or ""),
        "confirmation_wait_plan_decision_action": safe_text(confirmation_wait_plan.get("decision_action") or ""),
        "confirmation_wait_plan_rotation_guard_active": bool(
            confirmation_wait_plan.get("rotation_guard_active", False)
        ),
        "confirmation_wait_plan_rotation_blocked_symbol": safe_text(
            confirmation_wait_plan.get("rotation_blocked_symbol") or ""
        ),
        "confirmation_wait_plan_rotation_alternates": (
            confirmation_wait_plan.get("rotation_alternates")
            if isinstance(confirmation_wait_plan.get("rotation_alternates"), list)
            else []
        ),
        "confirmation_wait_plan_rotation_blocked_by_daily_plan": (
            confirmation_wait_plan.get("rotation_blocked_by_daily_plan")
            if isinstance(confirmation_wait_plan.get("rotation_blocked_by_daily_plan"), list)
            else []
        ),
        "confirmation_wait_plan_rotation_daily_blocked_count": len(
            confirmation_wait_plan.get("rotation_blocked_by_daily_plan")
            if isinstance(confirmation_wait_plan.get("rotation_blocked_by_daily_plan"), list)
            else []
        ),
        "confirmation_wait_plan_rotation_candidates": (
            confirmation_wait_plan.get("rotation_candidates")
            if isinstance(confirmation_wait_plan.get("rotation_candidates"), list)
            else []
        ),
        "confirmation_wait_plan_rotation_candidate_count": len(
            confirmation_wait_plan.get("rotation_candidates")
            if isinstance(confirmation_wait_plan.get("rotation_candidates"), list)
            else []
        ),
        "confirmation_wait_plan_rotation_next_symbol": safe_text(
            confirmation_wait_plan.get("rotation_next_symbol") or ""
        ),
        "confirmation_wait_plan_next_symbol": safe_text(
            confirmation_wait_plan.get("rotation_next_symbol") or ""
        ),
        "confirmation_wait_plan_rotation_cooldown_cycles": int(
            confirmation_wait_plan.get("rotation_cooldown_cycles") or 0
        ),
        "confirmation_wait_plan_rotation_cooldown_eta_minutes": confirmation_wait_plan.get(
            "rotation_cooldown_eta_minutes"
        ),
        "confirmation_wait_plan_rotation_resume_condition": safe_text(
            confirmation_wait_plan.get("rotation_resume_condition") or ""
        ),
        "confirmation_wait_plan_max_watch_cycles": int(confirmation_wait_plan.get("max_watch_cycles") or 0),
        "confirmation_wait_plan_review_action": safe_text(confirmation_wait_plan.get("review_action") or ""),
        "confirmation_wait_plan_exit": safe_text(confirmation_wait_plan.get("exit_condition") or ""),
        "stock_alerts_allowed": bool(entry.get("stock_alerts_allowed", True)),
        "crypto_alerts_allowed": bool(entry.get("crypto_alerts_allowed", True)),
        "options_alerts_allowed": bool(entry.get("options_alerts_allowed", True)),
        "session_stock_alerts_allowed": bool(entry.get("session_stock_alerts_allowed", True)),
        "realtime_stock_alerts_allowed": bool(entry.get("realtime_stock_alerts_allowed", True)),
        "realtime_crypto_alerts_allowed": bool(entry.get("realtime_crypto_alerts_allowed", True)),
        "blocked_markets": blocked_markets,
        "blocked_route_markets": blocked_route_markets,
        "blocked_route_market_count": blocked_route_market_count,
        "market_counts": summary.get("market_counts") if isinstance(summary.get("market_counts"), dict) else {},
        "actionable_market_counts": (
            summary.get("actionable_market_counts") if isinstance(summary.get("actionable_market_counts"), dict) else {}
        ),
        "allowed_markets": summary.get("allowed_markets") if isinstance(summary.get("allowed_markets"), list) else [],
        "missing_allowed_markets": (
            summary.get("missing_allowed_markets") if isinstance(summary.get("missing_allowed_markets"), list) else []
        ),
        "operable_market_count": int(summary.get("operable_market_count") or 0),
        "blocked_market_count": int(summary.get("blocked_market_count") or 0),
        "blocked_opportunity_market_count": blocked_opportunity_market_count,
        "market_coverage_label": safe_text(summary.get("market_coverage_label") or ""),
        "market_coverage_action": safe_text(summary.get("market_coverage_action") or ""),
        "chart_contract_total_count": int(summary.get("chart_contract_total_count") or 0),
        "chart_contract_checked_count": int(summary.get("chart_contract_checked_count") or 0),
        "chart_contract_operable_count": int(summary.get("chart_contract_operable_count") or 0),
        "chart_contract_blocked_count": int(summary.get("chart_contract_blocked_count") or 0),
        "chart_contract_missing_count": int(summary.get("chart_contract_missing_count") or 0),
        "chart_contract_blocked_markets": (
            summary.get("chart_contract_blocked_markets")
            if isinstance(summary.get("chart_contract_blocked_markets"), list)
            else []
        ),
        "chart_contract_market_counts": (
            summary.get("chart_contract_market_counts")
            if isinstance(summary.get("chart_contract_market_counts"), dict)
            else {}
        ),
        "chart_contract_market_operable_counts": (
            summary.get("chart_contract_market_operable_counts")
            if isinstance(summary.get("chart_contract_market_operable_counts"), dict)
            else {}
        ),
        "chart_contract_market_blocked_counts": (
            summary.get("chart_contract_market_blocked_counts")
            if isinstance(summary.get("chart_contract_market_blocked_counts"), dict)
            else {}
        ),
        "chart_contract_gate_counts": (
            summary.get("chart_contract_gate_counts")
            if isinstance(summary.get("chart_contract_gate_counts"), dict)
            else {}
        ),
        "chart_contract_operable_symbols": (
            summary.get("chart_contract_operable_symbols")
            if isinstance(summary.get("chart_contract_operable_symbols"), list)
            else []
        ),
        "chart_contract_blocked_symbols": (
            summary.get("chart_contract_blocked_symbols")
            if isinstance(summary.get("chart_contract_blocked_symbols"), list)
            else []
        ),
        "chart_contract_label": safe_text(summary.get("chart_contract_label") or ""),
        "chart_contract_action": safe_text(summary.get("chart_contract_action") or ""),
        "latest_notifications_ready": int(summary.get("latest_notifications_ready") or entry.get("notifications_ready") or 0),
        "latest_total_opportunities": int(summary.get("latest_total_opportunities") or entry.get("total_opportunities") or 0),
        "notifications_ready": int(summary.get("latest_notifications_ready") or entry.get("notifications_ready") or 0),
        "total_opportunities": int(summary.get("latest_total_opportunities") or entry.get("total_opportunities") or 0),
        "alert_count": int(entry.get("alert_count") or 0),
        "watch_count": int(entry.get("watch_count") or 0),
        "latest_top_gate": safe_text(summary.get("latest_top_gate") or entry.get("top_gate_label") or entry.get("top_gate") or ""),
        "latest_top_blocker": safe_text(summary.get("latest_top_blocker") or entry.get("top_blocker") or ""),
        "waiting_streak": int(summary.get("waiting_streak") or 0),
        "blocker_streak": int(summary.get("latest_top_blocker_streak") or 0),
        "readiness_delta": summary.get("readiness_delta"),
        "readiness_trend": summary.get("readiness_delta"),
        "avg_readiness": summary.get("avg_readiness"),
        "ready_count": summary.get("ready_count"),
        "ready_rate": summary.get("ready_rate"),
        "rotation_candidates": (
            summary.get("rotation_candidates") if isinstance(summary.get("rotation_candidates"), list) else []
        ),
    }


def build_alert_quality_report(
    brief: dict[str, Any],
    *,
    history_path: Path = DEFAULT_HISTORY_PATH,
    now: datetime | None = None,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
) -> dict[str, Any]:
    entry = alert_quality_entry(brief, now=now)
    previous = read_history(history_path, limit=history_limit)
    summary = summarize_quality_history([*previous, entry])
    contract = alert_quality_top_level_contract(summary, entry)
    status_summary = {
        **summary,
        "missed_trigger_plan": contract.get("missed_trigger_plan"),
    }
    report_status = alert_quality_report_status(status_summary)
    summary_contract = {
        key: contract.get(key)
        for key in (
            "symbol",
            "top_symbol",
            "operational_focus_symbol",
            "operational_focus_source",
            "operational_focus_reason",
            "recommended_action",
            "action",
            "missed_trigger_plan",
            "missed_trigger_plan_active",
            "missed_trigger_plan_symbol",
            "missed_trigger_plan_readiness",
            "missed_trigger_plan_risk",
            "missed_trigger_plan_review_due",
            "missed_trigger_plan_review_status",
            "missed_trigger_plan_review_pressure",
            "missed_trigger_plan_auto_review_decision",
            "missed_trigger_plan_rotation_handoff_confirmed",
            "missed_trigger_plan_rotation_handoff_status",
            "missed_trigger_plan_rotation_handoff_expected_symbol",
            "missed_trigger_plan_rotation_handoff_focus_symbol",
            "missed_trigger_plan_rotation_handoff_source",
            "missed_trigger_plan_rotation_handoff_symbol",
            "missed_trigger_plan_handoff_confirmed_action",
        )
        if key in contract
    }
    summary = {**summary, **summary_contract}
    history_entry = {**entry, **contract, **report_status}
    return {
        "generated_at": history_entry["recorded_at"],
        "brief_generated_at": entry["generated_at"],
        **report_status,
        "entry": history_entry,
        "latest_entry": history_entry,
        "summary": summary,
        "history_path": str(history_path),
        **contract,
    }


def write_alert_quality_report(
    brief: dict[str, Any],
    *,
    report_path: Path = DEFAULT_REPORT_PATH,
    history_path: Path = DEFAULT_HISTORY_PATH,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    history_max_bytes: int | None = DEFAULT_HISTORY_MAX_BYTES,
    history_min_entries: int = DEFAULT_HISTORY_MIN_ENTRIES,
    now: datetime | None = None,
) -> dict[str, Any]:
    report = build_alert_quality_report(brief, history_path=history_path, now=now, history_limit=history_limit)
    count = append_history(
        history_path,
        report["entry"],
        limit=history_limit,
        max_bytes=history_max_bytes,
        min_entries=history_min_entries,
    )
    report["history_count"] = count
    report["history_size_bytes"] = history_path.stat().st_size if history_path.exists() else 0
    report["history_max_bytes"] = history_max_bytes
    report["history_min_entries"] = history_min_entries
    history_size_bytes = int(report["history_size_bytes"] or 0)
    history_max_value = int(history_max_bytes or 0) if history_max_bytes is not None else 0
    history_budget_ratio = (
        round(history_size_bytes / history_max_value, 4)
        if history_max_value > 0
        else None
    )
    history_budget_margin_bytes = history_max_value - history_size_bytes if history_max_value > 0 else None
    history_average_entry_bytes = None
    if history_path.exists():
        history_lines = [line for line in history_path.read_text(errors="replace").splitlines() if line.strip()]
        if history_lines:
            sample = history_lines[-min(len(history_lines), max(1, int(history_limit))) :]
            history_average_entry_bytes = int(
                round(sum(len(line.encode("utf-8")) + 1 for line in sample) / max(1, len(sample)))
            )
    history_budget_projected_next_ratio = (
        round((history_size_bytes + int(history_average_entry_bytes or 0)) / history_max_value, 4)
        if history_max_value > 0 and history_average_entry_bytes is not None
        else None
    )
    history_estimated_appends_until_warn = None
    if history_max_value > 0 and history_average_entry_bytes:
        warn_threshold_bytes = int(history_max_value * DEFAULT_HISTORY_BUDGET_WARN_RATIO)
        history_estimated_appends_until_warn = max(
            0,
            (warn_threshold_bytes - history_size_bytes) // max(1, int(history_average_entry_bytes)),
        )
    history_budget_projected_pressure = (
        "OVER_LIMIT"
        if history_budget_projected_next_ratio is not None and history_budget_projected_next_ratio > 1.0
        else "NEAR_LIMIT"
        if history_budget_projected_next_ratio is not None
        and history_budget_projected_next_ratio >= DEFAULT_HISTORY_BUDGET_WARN_RATIO
        else "CLEAR"
    )
    history_budget_watch = bool(
        history_budget_ratio is not None
        and history_budget_ratio < DEFAULT_HISTORY_BUDGET_WARN_RATIO
        and history_budget_ratio
        >= max(0.0, DEFAULT_HISTORY_BUDGET_WARN_RATIO - DEFAULT_HISTORY_BUDGET_WATCH_MARGIN_RATIO)
    )
    report["history_budget_status"] = (
        "WARN"
        if history_budget_ratio is not None and history_budget_ratio >= DEFAULT_HISTORY_BUDGET_WARN_RATIO
        else "OK"
    )
    history_budget_pressure = (
        "OVER_LIMIT"
        if history_budget_ratio is not None and history_budget_ratio > 1.0
        else "NEAR_LIMIT"
        if history_budget_ratio is not None and history_budget_ratio >= DEFAULT_HISTORY_BUDGET_WARN_RATIO
        else "CLEAR"
    )
    if (
        history_budget_pressure == "CLEAR"
        and history_estimated_appends_until_warn is not None
        and history_estimated_appends_until_warn <= DEFAULT_HISTORY_BUDGET_MIN_APPENDS_UNTIL_WARN
    ):
        history_budget_pressure = "NEAR_LIMIT"
    report["history_budget_pressure"] = history_budget_pressure
    report["history_budget_warn_ratio"] = DEFAULT_HISTORY_BUDGET_WARN_RATIO
    report["history_budget_min_appends_until_warn"] = DEFAULT_HISTORY_BUDGET_MIN_APPENDS_UNTIL_WARN
    report["history_budget_watch"] = history_budget_watch
    report["history_budget_watch_margin_ratio"] = DEFAULT_HISTORY_BUDGET_WATCH_MARGIN_RATIO
    report["history_budget_ratio"] = history_budget_ratio
    report["history_budget_margin_bytes"] = history_budget_margin_bytes
    report["history_average_entry_bytes"] = history_average_entry_bytes
    report["history_estimated_appends_until_warn"] = history_estimated_appends_until_warn
    report["history_budget_projected_next_ratio"] = history_budget_projected_next_ratio
    report["history_budget_projected_pressure"] = history_budget_projected_pressure
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    summary.update(
        {
            "history_count": count,
            "history_entries": count,
            "history_size_bytes": history_size_bytes,
            "history_max_bytes": history_max_bytes,
            "history_min_entries": history_min_entries,
            "history_budget_status": report["history_budget_status"],
            "history_budget_pressure": report["history_budget_pressure"],
            "history_budget_warn_ratio": report["history_budget_warn_ratio"],
            "history_budget_min_appends_until_warn": report["history_budget_min_appends_until_warn"],
            "history_budget_watch": history_budget_watch,
            "history_budget_watch_margin_ratio": report["history_budget_watch_margin_ratio"],
            "history_budget_ratio": history_budget_ratio,
            "history_budget_margin_bytes": history_budget_margin_bytes,
            "history_average_entry_bytes": history_average_entry_bytes,
            "history_estimated_appends_until_warn": history_estimated_appends_until_warn,
            "history_budget_projected_next_ratio": history_budget_projected_next_ratio,
            "history_budget_projected_pressure": history_budget_projected_pressure,
        }
    )
    report["summary"] = summary
    write_json(report_path, report)
    return report


def update_from_brief_file(
    *,
    brief_path: Path = DEFAULT_BRIEF_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
    history_path: Path = DEFAULT_HISTORY_PATH,
    history_max_bytes: int | None = DEFAULT_HISTORY_MAX_BYTES,
    history_min_entries: int = DEFAULT_HISTORY_MIN_ENTRIES,
) -> dict[str, Any]:
    brief = read_json(brief_path)
    if not brief:
        report = {
            "generated_at": utc_now().isoformat(),
            "status": "WARN",
            "detail": "Brief not found or unreadable",
            "brief_path": str(brief_path),
        }
        write_json(report_path, report)
        return report
    report = write_alert_quality_report(
        brief,
        report_path=report_path,
        history_path=history_path,
        history_max_bytes=history_max_bytes,
        history_min_entries=history_min_entries,
    )
    if brief_path.resolve() == DEFAULT_BRIEF_PATH.resolve() and report_path.resolve() == DEFAULT_REPORT_PATH.resolve():
        try:
            from roxy_ai import write_status_snapshot

            write_status_snapshot(brief, alert_quality_report=report)
        except Exception:
            pass
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Roxy alert quality report and history from the current AI brief.")
    parser.add_argument("--brief-path", default=str(DEFAULT_BRIEF_PATH))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--history-path", default=str(DEFAULT_HISTORY_PATH))
    parser.add_argument("--history-max-bytes", type=int, default=DEFAULT_HISTORY_MAX_BYTES)
    parser.add_argument("--history-min-entries", type=int, default=DEFAULT_HISTORY_MIN_ENTRIES)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = update_from_brief_file(
        brief_path=Path(args.brief_path),
        report_path=Path(args.report_path),
        history_path=Path(args.history_path),
        history_max_bytes=args.history_max_bytes,
        history_min_entries=args.history_min_entries,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
