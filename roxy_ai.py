from __future__ import annotations

import json
import math
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from durable_storage import atomic_write_csv, atomic_write_text, exclusive_file_lock
from options_strategy import best_option_contract

from daily_opportunity_plan import build_daily_opportunity_plan, daily_plan_text_lines
from macro_calendar import apply_macro_context, macro_calendar_status
from market_newsletter import newsletter_context
try:
    from roxy_decision_engine import process_opportunities_with_decisions
except ModuleNotFoundError as exc:  # pragma: no cover - production deploy safety net
    if exc.name not in {"roxy_decision_engine", "roxy_knowledge_brain"}:
        raise

    def process_opportunities_with_decisions(
        opportunities: Any,
        *,
        enrich_knowledge: bool = True,
    ) -> list[dict[str, Any]]:
        return [dict(item) for item in opportunities or [] if isinstance(item, dict)]

try:
    from roxy_knowledge_brain import enrich_opportunities_with_knowledge
except ModuleNotFoundError as exc:  # pragma: no cover - production deploy safety net
    if exc.name != "roxy_knowledge_brain":
        raise

    def enrich_opportunities_with_knowledge(opportunities: Any, *, limit: int = 6) -> list[dict[str, Any]]:
        return [dict(item) for item in opportunities or [] if isinstance(item, dict)]
try:
    from tools.external_market_sources import build_external_market_snapshot
except Exception:  # pragma: no cover - optional external integrations.
    build_external_market_snapshot = None  # type: ignore[assignment]
from smart_alerts import evaluate_smart_alert
from strategy_overrides import apply_strategy_overrides_to_rows, load_strategy_overrides
from trade_brief import CORE_STRATEGIES, strategy_family_from_setup


ALERTS_DIR = Path("alerts")
MEMORY_PATH = ALERTS_DIR / "roxy_ai_memory.json"
BRIEF_JSON_PATH = ALERTS_DIR / "roxy_ai_brief.json"
BRIEF_TEXT_PATH = ALERTS_DIR / "roxy_ai_brief.txt"
STATUS_JSON_PATH = ALERTS_DIR / "roxy_status.json"
STATUS_TEXT_PATH = ALERTS_DIR / "roxy_status.txt"
DAILY_PLAN_JSON_PATH = ALERTS_DIR / "roxy_daily_opportunity_plan.json"
ALERT_QUALITY_JSON_PATH = ALERTS_DIR / "alert_quality.json"
OPPORTUNITY_LIFECYCLE_JSON_PATH = ALERTS_DIR / "opportunity_lifecycle.json"
REALTIME_HEALTH_PATH = Path(
    os.getenv("ROXY_REALTIME_HEALTH_PATH", "").strip()
    or ALERTS_DIR / "roxy_realtime_check.json"
)
CHART_REALTIME_HEALTH_PATH = ALERTS_DIR / "chart_realtime_health.json"
LEARNING_JOURNAL_PATH = ALERTS_DIR / "roxy_learning_journal.csv"
MAX_ALERTS_PER_BRIEF = 3
MAX_SIGNAL_JOURNAL = 200
MAX_EXPERIMENT_REGISTRY = 100
MAX_LEARNING_JOURNAL = 380
DEFAULT_ACCOUNT_EQUITY = float(os.getenv("ROXY_DEFAULT_ACCOUNT_EQUITY", "500") or "500")
DEFAULT_RISK_PER_TRADE_PCT = float(os.getenv("ROXY_RISK_PER_TRADE_PCT", "0.01") or "0.01")
BLOCKED_ALERT_GATES = {"BLOCKED_BY_MEMORY", "BLOCKED_REALTIME_DATA"}
ALERT_OPERABLE_CHART_STATUSES = {"OK"}
ALERT_OPERABLE_CHART_LABELS = {"Viva", "Mercado cerrado"}
PREFERRED_CRYPTO_RESCUE_SYMBOLS = (
    "BTC/USD",
    "ETH/USD",
    "SOL/USD",
    "BNB/USD",
    "ADA/USD",
    "LINK/USD",
    "DOGE/USD",
    "AVAX/USD",
    "LTC/USD",
)
_EXTERNAL_MARKET_CACHE: dict[str, Any] = {"expires_at": 0.0, "rows": []}

ALERT_GATE_LABELS = {
    "ALERT_READY": "Listo para operar manual",
    "WAIT_15M_ENTRY": "Esperar entrada 15m",
    "WAIT_1H_CONFIRM": "Esperar confirmacion 1h",
    "WAIT_HTF_CONFIRM": "Esperar confirmacion 2h/4h",
    "WAIT_VOLUME": "Esperar volumen",
    "NO_TRADE_STRUCTURE": "No operar por estructura",
    "WAIT_FULL_CHECKLIST": "Esperar checklist completo",
    "WAIT_MACRO_CONFIRMATION": "Esperar evento macro",
    "BLOCKED_BY_MEMORY": "Bloqueado por memoria",
    "BLOCKED_REALTIME_DATA": "Bloqueado por datos realtime",
}

LEARNING_ACTION_LABELS = {
    "COLLECT_MORE_DATA": "Recolectar mas datos",
    "PROMOTE_RULE": "Promover regla",
    "TIGHTEN_FILTER": "Endurecer filtro",
    "SHADOW_TEST_NO_TRADE_STRUCTURE": "Probar filtro de estructura",
}

SAFETY_MODE_LABELS = {
    "PAPER_ONLY": "Solo paper",
    "PRODUCTION_RANKING": "Ranking de produccion",
}

EXPERIMENT_STATUS_LABELS = {
    "COLLECTING_DATA": "Recolectando datos",
    "SHADOW_TEST": "Prueba en laboratorio",
    "PROMOTED": "Promovido",
    "TIGHTEN_FILTER": "Filtro endurecido",
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


def alert_gate_label(gate: Any) -> str:
    raw = safe_text(gate).upper()
    if not raw:
        return "-"
    return ALERT_GATE_LABELS.get(raw, raw.replace("_", " ").title())


def learning_action_label(action: Any) -> str:
    raw = safe_text(action).upper()
    if not raw:
        return "-"
    return LEARNING_ACTION_LABELS.get(raw, raw.replace("_", " ").title())


def safety_mode_label(mode: Any) -> str:
    raw = safe_text(mode).upper()
    if not raw:
        return "-"
    return SAFETY_MODE_LABELS.get(raw, raw.replace("_", " ").title())


def experiment_status_label(status: Any) -> str:
    raw = safe_text(status).upper()
    if not raw:
        return "-"
    return EXPERIMENT_STATUS_LABELS.get(raw, raw.replace("_", " ").title())


def human_trade_action(row: dict[str, Any]) -> str:
    action = safe_text(row.get("ai_action") or row.get("action")).upper()
    signal = safe_text(row.get("signal")).upper()
    decision = safe_text(row.get("trade_decision") or row.get("decision")).upper()
    if action == "ALERT" or (signal == "BUY" and decision.startswith("TRADE_FOR")):
        return "Operar"
    if signal == "AVOID" or decision.startswith("NO_TRADE"):
        return "No operar"
    return "Esperar"


def human_alert_reason(row: dict[str, Any]) -> str:
    action = human_trade_action(row)
    gate = safe_text(row.get("alert_gate")).upper()
    quality_reason = safe_text(row.get("alert_quality_reason") or (row.get("smart_alert") or {}).get("quality_reason"))
    next_action = safe_text(row.get("alert_next_action") or row.get("alert_movement"))
    blockers = row.get("alert_blockers") or []
    if isinstance(blockers, str):
        blockers = [blockers]
    blocker_text = "; ".join(safe_text(item) for item in blockers[:2] if safe_text(item))

    if action == "Operar":
        risk = safe_float(row.get("risk_pct"))
        target = safe_float(row.get("recommended_target_pct") or row.get("target_pct"))
        parts = ["BUY confirmado por 15m/1h, riesgo medido y target minimo viable."]
        if risk is not None:
            parts.append(f"Riesgo {risk * 100:.2f}%.")
        if target is not None:
            parts.append(f"Target {target * 100:.0f}%.")
        base = " ".join(parts)
    elif gate == "WAIT_15M_ENTRY":
        base = "Esperar gatillo BUY en 15m; la entrada todavia no esta confirmada."
    elif gate == "WAIT_1H_CONFIRM":
        base = "Esperar que 1h confirme tendencia antes de preparar entrada."
    elif gate == "WAIT_VOLUME":
        base = "Esperar volumen relativo; sin volumen la senal puede fallar."
    elif gate == "NO_TRADE_STRUCTURE":
        base = "No operar: estructura bajista o AVOID hasta recuperar medias."
    elif gate == "BLOCKED_BY_MEMORY":
        base = "No operar: la memoria historica exige filtro extra."
    elif action == "No operar":
        base = "No operar: falta confluencia entre tendencia, entrada y riesgo."
    else:
        base = next_action or "Esperar a que el checklist este completo."

    if quality_reason and quality_reason not in base:
        return f"{base} {quality_reason}"
    if blocker_text and action != "Operar":
        return f"{base} Falta: {blocker_text}."
    return base


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_file_age_minutes(path: str | Path | None, *, now: datetime | None = None) -> float | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        return None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    modified_at = datetime.fromtimestamp(file_path.stat().st_mtime, timezone.utc)
    age_seconds = (now - modified_at).total_seconds()
    return max(0.0, age_seconds / 60.0)


def source_freshness_status(
    source_files: dict[str, str | None] | list[str | None],
    *,
    max_age_minutes: float = 10.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    if isinstance(source_files, dict):
        paths = [source_files.get("scan"), source_files.get("confluence")]
    else:
        paths = source_files
    ages = [source_file_age_minutes(path, now=now) for path in paths if path]
    ages = [age for age in ages if age is not None]
    if not ages:
        return {
            "status": "NO_DATA",
            "label": "Sin datos",
            "age_minutes": None,
            "detail": "No hay archivos live/confluencia para validar.",
            "alerts_allowed": False,
        }

    age = max(ages)
    if age <= max_age_minutes:
        status = "FRESH"
        label = "Frescos"
        alerts_allowed = True
        detail = f"live/confluencia actualizados hace {age:.0f} min."
    elif age <= max_age_minutes * 3:
        status = "REVIEW"
        label = "Revisar"
        alerts_allowed = True
        detail = f"live/confluencia llevan {age:.0f} min sin refrescar."
    else:
        status = "STALE"
        label = "Estancados"
        alerts_allowed = False
        detail = f"live/confluencia llevan {age:.0f} min sin refrescar."

    return {
        "status": status,
        "label": label,
        "age_minutes": age,
        "detail": detail,
        "alerts_allowed": alerts_allowed,
    }


def realtime_health_status(
    path: str | Path | None = None,
    *,
    max_age_minutes: float = 15.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    health_path = Path(path or REALTIME_HEALTH_PATH)
    report = load_json(health_path, {})
    age = source_file_age_minutes(health_path, now=now)
    if not report:
        return {
            "status": "UNKNOWN",
            "label": "Sin health",
            "detail": "No hay reporte realtime reciente.",
            "age_minutes": age,
            "alerts_allowed": True,
            "path": str(health_path),
        }

    report_status = safe_text(report.get("status")).upper() or "UNKNOWN"
    provider_recovery = report.get("provider_recovery") if isinstance(report.get("provider_recovery"), dict) else {}
    market_realtime = report.get("market_realtime") if isinstance(report.get("market_realtime"), dict) else {}

    def market_route_fields() -> dict[str, Any]:
        allowed = (
            market_realtime.get("allowed_markets")
            if isinstance(market_realtime.get("allowed_markets"), list)
            else []
        )
        blocked = (
            market_realtime.get("blocked_markets")
            if isinstance(market_realtime.get("blocked_markets"), list)
            else []
        )
        if bool(provider_recovery.get("premium_blocked")):
            impacted = (
                provider_recovery.get("impacted_markets")
                if isinstance(provider_recovery.get("impacted_markets"), list)
                else ["stock", "options"]
            )
            blocked_set = {safe_text(item).lower() for item in [*blocked, *impacted] if safe_text(item)}
            allowed_source = [safe_text(item).lower() for item in allowed if safe_text(item)]
            if not allowed_source:
                allowed_source = ["stock", "crypto", "options"]
            allowed = [market for market in allowed_source if market not in blocked_set]
            blocked = [market for market in ["stock", "crypto", "options"] if market in blocked_set]
            if allowed and blocked:
                return {
                    "active_route": "PARTIAL_MARKET_ROUTE",
                    "active_route_label": "Operar solo " + ", ".join(item.upper() for item in allowed),
                    "active_route_detail": (
                        "Operable "
                        + ", ".join(item.upper() for item in allowed)
                        + "; bloqueado "
                        + ", ".join(item.upper() for item in blocked)
                        + "."
                    ),
                    "allowed_markets": allowed,
                    "blocked_markets": blocked,
                }
            if blocked:
                return {
                    "active_route": "NO_MARKET_ROUTE",
                    "active_route_label": "No operar realtime",
                    "active_route_detail": "Bloqueado " + ", ".join(item.upper() for item in blocked) + ".",
                    "allowed_markets": [],
                    "blocked_markets": blocked,
                }
        return {
            "active_route": safe_text(market_realtime.get("active_route")),
            "active_route_label": safe_text(market_realtime.get("active_route_label")),
            "active_route_detail": safe_text(market_realtime.get("active_route_detail")),
            "allowed_markets": allowed,
            "blocked_markets": blocked,
        }

    def route_prefix() -> str:
        route = market_route_fields()
        label = safe_text(route.get("active_route_label"))
        detail = safe_text(route.get("active_route_detail"))
        if label and detail:
            return f"{label}: {detail}"
        return label or detail

    route_fields = market_route_fields()
    if age is not None and age > max_age_minutes * 2:
        return {
            "status": "STALE",
            "label": "Health viejo",
            "detail": f"Reporte realtime lleva {age:.0f} min sin actualizar.",
            "age_minutes": age,
            "alerts_allowed": False,
            "path": str(health_path),
        }

    if report_status == "FAIL":
        failed = [
            item
            for item in report.get("checks", [])
            if safe_text(item.get("status")).upper() == "FAIL"
        ]
        failed_names = {safe_text(item.get("name")) for item in failed}
        auxiliary_infrastructure_failures = {
            "external_disk",
            "runtime_backup_report",
            "runtime_backup_service",
            "health_stability_slo",
        }
        unavailable_render_probes = {
            safe_text(item.get("name"))
            for item in failed
            if safe_text(item.get("name")) in {"dashboard_render_probe", "dashboard_search_render_probe"}
            and "executable doesn't exist" in safe_text(item.get("detail")).lower()
        }
        auxiliary_infrastructure_failures.update(unavailable_render_probes)
        allowed_markets = [safe_text(item).lower() for item in route_fields.get("allowed_markets", []) if safe_text(item)]
        concrete_auxiliary_failures = auxiliary_infrastructure_failures - {"health_stability_slo"}
        if (
            failed
            and failed_names <= auxiliary_infrastructure_failures
            and bool(failed_names & concrete_auxiliary_failures)
            and allowed_markets
        ):
            detail = "; ".join(
                f"{safe_text(item.get('name'))}: {safe_text(item.get('detail'))}"
                for item in failed[:3]
                if safe_text(item.get("name")) or safe_text(item.get("detail"))
            )
            route_text = route_prefix()
            return {
                "status": "WARN",
                "label": "Mercado operativo; infraestructura degradada",
                "detail": " | ".join(part for part in [route_text, detail] if part),
                "age_minutes": age,
                "alerts_allowed": True,
                "stock_alerts_allowed": "stock" in allowed_markets and not bool(provider_recovery.get("premium_blocked")),
                "crypto_alerts_allowed": "crypto" in allowed_markets,
                "auxiliary_failures": sorted(failed_names),
                "provider_recovery": provider_recovery,
                "market_realtime": market_realtime,
                **route_fields,
                "path": str(health_path),
            }
        recoverable_brief_failures = {"ai_brief", "operational_summary_contract", "health_stability_slo"}
        brief_cycle_failures = {"ai_brief", "operational_summary_contract"}
        if (
            failed
            and failed_names <= recoverable_brief_failures
            and bool(failed_names & brief_cycle_failures)
            and "crypto" in route_fields.get("allowed_markets", [])
        ):
            detail = "; ".join(
                f"{safe_text(item.get('name'))}: {safe_text(item.get('detail'))}"
                for item in failed[:3]
                if safe_text(item.get("name")) or safe_text(item.get("detail"))
            )
            route_text = route_prefix()
            parts = [part for part in [route_text, detail or "Health recuperable al reconstruir brief."] if part]
            return {
                "status": "WARN",
                "label": "Health recuperando",
                "detail": " | ".join(parts),
                "age_minutes": age,
                "alerts_allowed": True,
                "stock_alerts_allowed": False,
                "crypto_alerts_allowed": True,
                "provider_recovery": provider_recovery,
                "market_realtime": market_realtime,
                **route_fields,
                "path": str(health_path),
            }
        if failed and failed_names <= {"health_stability_slo"}:
            first = failed[0]
            detail = safe_text(first.get("detail")) or "SLO historico de health bajo."
            if bool(provider_recovery.get("premium_blocked")):
                recovery_detail = safe_text(provider_recovery.get("detail"))
                recovery_action = safe_text(provider_recovery.get("action"))
                parts = [f"health_stability_slo: {detail}"]
                if recovery_detail:
                    parts.append(f"provider_recovery: {recovery_detail}")
                if recovery_action:
                    parts.append(f"accion {recovery_action}")
                return {
                    "status": "WARN",
                    "label": safe_text(provider_recovery.get("label")) or "Premium bloqueado",
                    "detail": " | ".join(parts),
                    "age_minutes": age,
                    "alerts_allowed": True,
                    "stock_alerts_allowed": bool(provider_recovery.get("stock_alerts_allowed", True)),
                    "crypto_alerts_allowed": True,
                    "premium_recovery_action": recovery_action,
                    "provider_recovery": provider_recovery,
                    "market_realtime": market_realtime,
                    **route_fields,
                    "path": str(health_path),
                }
            return {
                "status": "WARN",
                "label": "Health historico",
                "detail": f"health_stability_slo: {detail}",
                "age_minutes": age,
                "alerts_allowed": True,
                "stock_alerts_allowed": True,
                "crypto_alerts_allowed": True,
                "provider_recovery": provider_recovery,
                "market_realtime": market_realtime,
                **route_fields,
                "path": str(health_path),
            }
        first = failed[0] if failed else {}
        name = safe_text(first.get("name")) or "realtime"
        detail = safe_text(first.get("detail")) or "Health realtime fallo."
        return {
            "status": "FAIL",
            "label": "Health fallo",
            "detail": f"{name}: {detail}",
            "age_minutes": age,
            "alerts_allowed": False,
            "path": str(health_path),
        }

    if report_status == "WARN":
        warning = [
            item
            for item in report.get("checks", [])
            if safe_text(item.get("status")).upper() == "WARN"
        ]
        provider_warning = next(
            (
                item
                for item in warning
                if safe_text(item.get("name")) == "chart_provider_effective"
                and (
                    int(item.get("auth_fallback_count") or 0) > 0
                    or any(
                        key in {"alpaca_auth", "alpaca_feed_permission"}
                        for key in ((item.get("fallback_reason_counts") or {}) if isinstance(item.get("fallback_reason_counts"), dict) else {})
                    )
                )
            ),
            {},
        )
        if provider_warning:
            provider_detail = safe_text(provider_warning.get("detail")) or "Proveedor premium cayo a fallback."
            recovery_action = safe_text(provider_warning.get("premium_recovery_action"))
            if recovery_action:
                provider_detail = f"{provider_detail} | accion {recovery_action}"
            route_text = route_prefix()
            if route_text:
                detail = f"{route_text} | chart_provider_effective: {provider_detail}"
            else:
                detail = f"chart_provider_effective: {provider_detail}"
            return {
                "status": "WARN",
                "label": "Premium bloqueado",
                "detail": detail,
                "age_minutes": age,
                "alerts_allowed": True,
                "stock_alerts_allowed": False,
                "crypto_alerts_allowed": True,
                "premium_recovery_action": recovery_action,
                "provider_recovery": provider_recovery,
                "market_realtime": market_realtime,
                **route_fields,
                "path": str(health_path),
            }
        if bool(provider_recovery.get("premium_blocked")):
            recovery_detail = safe_text(provider_recovery.get("detail"))
            recovery_action = safe_text(provider_recovery.get("action"))
            parts = []
            route_text = route_prefix()
            if route_text:
                parts.append(route_text)
            if recovery_detail:
                parts.append(f"provider_recovery: {recovery_detail}")
            if recovery_action:
                parts.append(f"accion {recovery_action}")
            return {
                "status": "WARN",
                "label": safe_text(provider_recovery.get("label")) or "Premium bloqueado",
                "detail": " | ".join(parts) or "Proveedor premium bloqueado.",
                "age_minutes": age,
                "alerts_allowed": True,
                "stock_alerts_allowed": bool(provider_recovery.get("stock_alerts_allowed", False)),
                "crypto_alerts_allowed": True,
                "premium_recovery_action": recovery_action,
                "provider_recovery": provider_recovery,
                "market_realtime": market_realtime,
                **route_fields,
                "path": str(health_path),
            }
        first = warning[0] if warning else {}
        name = safe_text(first.get("name")) or "realtime"
        detail = safe_text(first.get("detail")) or "Health realtime con advertencias."
        return {
            "status": "WARN",
            "label": "Health revisar",
            "detail": f"{name}: {detail}",
            "age_minutes": age,
            "alerts_allowed": True,
            "stock_alerts_allowed": True,
            "crypto_alerts_allowed": True,
            "market_realtime": market_realtime,
            **route_fields,
            "path": str(health_path),
        }

    if report_status == "OK":
        label = "Health OK"
        alerts_allowed = True
    else:
        label = report_status or "Health desconocido"
        alerts_allowed = True
    return {
        "status": report_status,
        "label": label,
        "detail": f"Reporte realtime {report_status.lower()}",
        "age_minutes": age,
        "alerts_allowed": alerts_allowed,
        "market_realtime": market_realtime,
        **route_fields,
        "path": str(health_path),
    }


def market_session_status(*, now: datetime | None = None) -> dict[str, Any]:
    eastern = ZoneInfo("America/New_York")
    current = now or datetime.now(eastern)
    if current.tzinfo is None:
        current = current.replace(tzinfo=eastern)
    current = current.astimezone(eastern)
    minutes = current.hour * 60 + current.minute
    weekday = current.weekday()

    if weekday >= 5:
        stock_session = "Cerrado"
        stock_detail = "Fin de semana; acciones/opciones solo para estudio."
        alerts_allowed = False
    elif 4 * 60 <= minutes < 9 * 60 + 30:
        stock_session = "Premarket"
        stock_detail = "Confirmar volumen y spreads antes de entrar."
        alerts_allowed = True
    elif 9 * 60 + 30 <= minutes < 16 * 60:
        stock_session = "Mercado abierto"
        stock_detail = "Acciones/opciones con liquidez regular."
        alerts_allowed = True
    elif 16 * 60 <= minutes < 20 * 60:
        stock_session = "After-hours"
        stock_detail = "Solo setups muy claros; spreads pueden abrirse."
        alerts_allowed = True
    else:
        stock_session = "Cerrado"
        stock_detail = "Fuera de horario extendido; esperar siguiente sesion."
        alerts_allowed = False

    return {
        "timezone": "America/New_York",
        "local_time": current.strftime("%Y-%m-%d %H:%M"),
        "stock_session": stock_session,
        "stock_detail": stock_detail,
        "stock_alerts_allowed": alerts_allowed,
        "crypto_session": "24h",
        "crypto_detail": "Crypto sigue disponible 24h; vigilar liquidez y volatilidad.",
    }


def load_json(path: str | Path, default: Any) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def normalize_alert_chart_symbol(value: Any) -> str:
    symbol = safe_text(value).upper().replace("$", "")
    if symbol in {"", "-", "N/A", "NA", "NONE", "NULL"}:
        return ""
    if "/" in symbol:
        parts = [part for part in symbol.split("/") if part]
        if len(parts) == 2 and all(part.replace("-", "").isalnum() for part in parts):
            return "/".join(parts)
        return ""
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
    return symbol[:16] if symbol and symbol[0].isalpha() and all(char in allowed for char in symbol) else ""


def chart_health_contract_from_row(row: dict[str, Any]) -> dict[str, Any]:
    status = safe_text(row.get("status")).upper()
    label = safe_text(row.get("label"))
    tone = safe_text(row.get("tone"))
    source_label = safe_text(row.get("source_label") or row.get("source") or row.get("symbol"))
    if status in ALERT_OPERABLE_CHART_STATUSES and label in ALERT_OPERABLE_CHART_LABELS:
        gate = "LIVE_DATA_OK"
        operable = True
    elif status == "WARN":
        gate = "WAIT_NEXT_CANDLE"
        operable = False
    else:
        gate = "NO_TRADE_STALE_DATA"
        operable = False
    return {
        "gate": gate,
        "operable": operable,
        "source_label": source_label,
        "source": source_label,
        "chart_status": status,
        "chart_label": label,
        "chart_tone": tone,
        "latest": safe_text(row.get("latest")),
        "age_minutes": safe_float(row.get("age_minutes")),
        "timeframe": safe_text(row.get("timeframe")),
        "candle_phase": safe_text(row.get("candle_phase")),
        "candle_phase_label": safe_text(row.get("candle_phase_label")),
        "candle_progress_pct": safe_float(row.get("candle_progress_pct")),
        "detail": safe_text(row.get("detail")),
    }


def chart_health_contract_index(path: str | Path | None = None) -> dict[tuple[str, str], dict[str, Any]]:
    payload = load_json(path or CHART_REALTIME_HEALTH_PATH, {})
    charts = payload.get("charts") if isinstance(payload, dict) else []
    if not isinstance(charts, list):
        return {}
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for item in charts:
        if not isinstance(item, dict):
            continue
        symbol = normalize_alert_chart_symbol(item.get("symbol"))
        timeframe = safe_text(item.get("timeframe") or "1h").lower()
        if not symbol or not timeframe:
            continue
        index[(symbol, timeframe)] = chart_health_contract_from_row(item)
    return index


def resolve_live_chart_contract(symbol: str, market: str, timeframe: str) -> dict[str, Any]:
    try:
        from chart_health import chart_health_row
        from symbol_detail import fetch_symbol_history, prepare_symbol_chart_data

        history = fetch_symbol_history(symbol, market=market, timeframe=timeframe)
        chart_df = prepare_symbol_chart_data(history)
        row = chart_health_row(symbol=symbol, market=market, timeframe=timeframe, chart_df=chart_df)
        return chart_health_contract_from_row(row)
    except Exception:
        return {}


def attach_chart_contract_to_opportunity(
    row: dict[str, Any],
    chart_contracts: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    item = dict(row)
    symbol = normalize_alert_chart_symbol(item.get("symbol"))
    market = safe_text(item.get("market") or "stock").lower()
    raw_tf = safe_text(item.get("timeframe") or item.get("tf") or "1h").lower()
    candidate_timeframes = [raw_tf] if raw_tf else []
    if "1h" not in candidate_timeframes:
        candidate_timeframes.append("1h")
    if "15m" not in candidate_timeframes:
        candidate_timeframes.append("15m")
    contract = {}
    for timeframe in candidate_timeframes:
        contract = chart_contracts.get((symbol, timeframe), {})
        if not contract and symbol and market == "crypto":
            contract = resolve_live_chart_contract(symbol, market, timeframe)
            if contract:
                chart_contracts[(symbol, timeframe)] = contract
        if contract:
            break
    if contract:
        item["chart_data_contract"] = dict(contract)
        item["chart_data_gate"] = contract.get("gate")
        item["chart_operable"] = contract.get("operable")
        item["chart_source_label"] = contract.get("source_label")
        item["chart_candle_phase_label"] = contract.get("candle_phase_label")
        item["chart_timeframe"] = contract.get("timeframe")
        item["chart_age_minutes"] = contract.get("age_minutes")
    elif symbol:
        item["chart_data_gate"] = "CHART_CONTRACT_MISSING"
        item["chart_operable"] = None
        item["chart_source_label"] = "-"
        item["chart_candle_phase_label"] = "-"
    return item


def attach_chart_contracts_to_opportunities(
    opportunities: list[dict[str, Any]],
    chart_contracts: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    contracts = chart_contracts if chart_contracts is not None else chart_health_contract_index()
    return [attach_chart_contract_to_opportunity(row, contracts) for row in opportunities]


def write_json(path: str | Path, payload: Any) -> None:
    atomic_write_text(json.dumps(payload, indent=2, sort_keys=True), path)


def load_memory(path: str | Path = MEMORY_PATH) -> dict[str, Any]:
    memory = load_json(
        path,
        {
            "created_at": now_iso(),
            "updated_at": None,
            "symbols": {},
            "strategy_stats": {},
            "lessons": [],
            "alert_history": [],
            "signal_journal": [],
            "experiment_registry": [],
        },
    )
    memory.setdefault("symbols", {})
    memory.setdefault("strategy_stats", {})
    memory.setdefault("lessons", [])
    memory.setdefault("alert_history", [])
    memory.setdefault("signal_journal", [])
    memory.setdefault("experiment_registry", [])
    return memory


def save_memory(memory: dict[str, Any], path: str | Path = MEMORY_PATH) -> None:
    memory["updated_at"] = now_iso()
    write_json(path, memory)


def _is_trade_candidate(row: dict[str, Any]) -> bool:
    return bool(evaluate_smart_alert(row).get("notification_ok"))


def strategy_family_for_row(row: dict[str, Any]) -> str:
    explicit = safe_text(row.get("strategy_family") or row.get("salto_family"))
    if explicit:
        return strategy_family_from_setup(explicit)
    setup = safe_text(row.get("trigger_setup") or row.get("setup"))
    trend_setup = safe_text(row.get("trend_setup"))
    return strategy_family_from_setup(setup, trend_setup=trend_setup)


def _strategy_stats(memory: dict[str, Any], family: str) -> dict[str, Any]:
    stats_by_family = memory.setdefault("strategy_stats", {})
    return stats_by_family.setdefault(
        family,
        {
            "seen": 0,
            "alerts": 0,
            "hit_2pct": 0,
            "hit_5pct": 0,
            "hit_10pct": 0,
            "stops": 0,
            "last_seen_at": None,
            "last_outcome_at": None,
        },
    )


def _rate(numerator: Any, denominator: Any) -> float:
    total = int(denominator or 0)
    if total <= 0:
        return 0.0
    return int(numerator or 0) / total


def _has_target_milestone(row: dict[str, Any], target: str) -> bool:
    status = safe_text(row.get("status")).upper()
    milestones = {safe_text(value).upper() for value in row.get("milestones", [])}
    target = target.upper()
    if target == "2%":
        return status in {"HIT_2PCT", "HIT_5PCT", "HIT_10PCT"} or target in milestones
    if target == "5%":
        return status in {"HIT_5PCT", "HIT_10PCT"} or target in milestones
    if target == "10%":
        return status == "HIT_10PCT" or target in milestones
    return target in milestones


def _target_hit_from_gain(max_gain_pct: float | None) -> tuple[str | None, float]:
    if max_gain_pct is None:
        return None, 0.0
    if max_gain_pct >= 0.10:
        return "10%", 10.0
    if max_gain_pct >= 0.05:
        return "5%", 5.0
    if max_gain_pct >= 0.02:
        return "2%", 2.0
    return None, 0.0


def outcome_state_for_signal(row: dict[str, Any]) -> str:
    status = safe_text(row.get("status")).upper()
    best_target = safe_text(row.get("best_target_hit"))
    progress_to_stop = safe_float(row.get("progress_to_stop")) or 0.0
    stopped_after_target = bool(row.get("stopped_after_target")) or (
        progress_to_stop >= 1.0 and best_target in {"2%", "5%", "10%"}
    )
    if stopped_after_target:
        if best_target == "10%":
            return "HIT_10PCT_THEN_STOP"
        if best_target == "5%":
            return "HIT_5PCT_THEN_STOP"
        if best_target == "2%":
            return "HIT_2PCT_THEN_STOP"
    if status in {"STOP", "STOPPED", "STOP_HIT", "HIT_STOP"}:
        return "STOP"
    if status in {"HIT_10PCT", "HIT_5PCT", "HIT_2PCT"}:
        return status
    if best_target == "10%":
        return "HIT_10PCT"
    if best_target == "5%":
        return "HIT_5PCT"
    if best_target == "2%":
        return "HIT_2PCT"
    progress_to_2pct = safe_float(row.get("progress_to_2pct")) or 0.0
    if progress_to_stop >= 0.75 and progress_to_2pct < 0.50:
        return "DANGER_STOP"
    if progress_to_2pct >= 0.75:
        return "NEAR_2PCT"
    return status or "OPEN"


def refresh_strategy_shadow_stats(memory: dict[str, Any]) -> dict[str, Any]:
    """Recompute paper-only WATCH evidence without counting it as real alert accuracy."""
    stats_by_family = memory.setdefault("strategy_stats", {})
    counters: dict[str, dict[str, int]] = {}
    for row in memory.get("signal_journal") or []:
        if safe_text(row.get("ai_action")).upper() == "ALERT":
            continue
        family = safe_text(row.get("strategy_family")) or strategy_family_for_row(row)
        stats_by_family.setdefault(family, {})
        item = counters.setdefault(
            family,
            {
                "shadow_tracked": 0,
                "shadow_observed": 0,
                "shadow_hit_2pct": 0,
                "shadow_near_2pct": 0,
                "shadow_near_stop": 0,
                "shadow_stops": 0,
            },
        )
        item["shadow_tracked"] += 1
        progress_to_2pct = safe_float(row.get("progress_to_2pct"))
        progress_to_stop = safe_float(row.get("progress_to_stop"))
        status = safe_text(row.get("status")).upper()
        hit_2 = _has_target_milestone(row, "2%")
        stopped = status in {"STOP", "STOPPED", "STOP_HIT", "HIT_STOP"}
        if progress_to_2pct is not None or progress_to_stop is not None or hit_2 or stopped:
            item["shadow_observed"] += 1
        if hit_2:
            item["shadow_hit_2pct"] += 1
        if hit_2 or (progress_to_2pct is not None and progress_to_2pct >= 0.75):
            item["shadow_near_2pct"] += 1
        if stopped:
            item["shadow_stops"] += 1
        if stopped or (progress_to_stop is not None and progress_to_stop >= 0.75):
            item["shadow_near_stop"] += 1

    for family, stats in stats_by_family.items():
        counts = counters.get(family, {})
        for field in (
            "shadow_tracked",
            "shadow_observed",
            "shadow_hit_2pct",
            "shadow_near_2pct",
            "shadow_near_stop",
            "shadow_stops",
        ):
            stats[field] = int(counts.get(field, 0))
    return memory


def strategy_learning_profile(family: str, stats: dict[str, Any] | None) -> dict[str, Any]:
    stats = stats or {}
    alerts = int(stats.get("alerts", 0) or 0)
    seen = int(stats.get("seen", 0) or 0)
    hit_2pct = int(stats.get("hit_2pct", 0) or 0)
    hit_5pct = int(stats.get("hit_5pct", 0) or 0)
    hit_10pct = int(stats.get("hit_10pct", 0) or 0)
    stops = int(stats.get("stops", 0) or 0)
    hit_2_rate = _rate(hit_2pct, alerts)
    hit_5_rate = _rate(hit_5pct, alerts)
    hit_10_rate = _rate(hit_10pct, alerts)
    stop_rate = _rate(stops, alerts)
    shadow_tracked = int(stats.get("shadow_tracked", 0) or 0)
    shadow_observed = int(stats.get("shadow_observed", 0) or 0)
    shadow_hit_2pct = int(stats.get("shadow_hit_2pct", 0) or 0)
    shadow_near_2pct = int(stats.get("shadow_near_2pct", 0) or 0)
    shadow_near_stop = int(stats.get("shadow_near_stop", 0) or 0)
    shadow_stops = int(stats.get("shadow_stops", 0) or 0)
    shadow_target_rate = _rate(max(shadow_hit_2pct, shadow_near_2pct), shadow_observed)
    shadow_stop_pressure = _rate(shadow_near_stop, shadow_observed)

    if alerts < 3:
        if shadow_observed >= 3 and shadow_target_rate >= 0.55 and shadow_stop_pressure <= 0.35:
            bias = "shadow_positive"
            adjustment = 3
            adaptive_weight = 1.05
            lesson = f"{family}: WATCH de laboratorio se acerca al 2% con poco stop; Roxy sube prioridad pequena."
            recommendation = "Seguir en paper-only y convertir a alerta solo con checklist completo."
        elif shadow_observed >= 3 and shadow_stop_pressure >= 0.50 and shadow_target_rate < 0.35:
            bias = "shadow_negative"
            adjustment = -5
            adaptive_weight = 0.92
            lesson = f"{family}: WATCH de laboratorio se acerca demasiado al stop; Roxy exige mas confirmacion."
            recommendation = "No promover; exigir volumen, 1h fuerte y riesgo menor antes de alertar."
        else:
            bias = "learning"
            adjustment = 0
            adaptive_weight = 1.0
            lesson = f"{family}: todavia no hay suficientes alertas cerradas para subir o bajar peso."
            recommendation = "Seguir observando y exigir confirmacion 1h + entrada 15m."
    elif stop_rate >= 0.50 and hit_2_rate < 0.35:
        bias = "negative"
        adjustment = -12
        adaptive_weight = 0.82
        lesson = f"{family}: demasiados stops frente a pocos targets 2%; Roxy baja prioridad."
        recommendation = "Evitar nuevas entradas de este setup salvo volumen fuerte y riesgo muy bajo."
    elif hit_2_rate >= 0.55 and stop_rate <= 0.35:
        bias = "positive"
        adjustment = 7 if hit_5_rate >= 0.25 else 5
        adaptive_weight = 1.15 if hit_5_rate >= 0.25 else 1.10
        lesson = f"{family}: buen historial llegando a 2%; Roxy puede darle mas prioridad."
        recommendation = "Favorecer este setup cuando 1h confirma, 15m da entrada y el stop queda cercano."
    elif shadow_observed >= 5 and shadow_stop_pressure >= 0.55 and shadow_target_rate < 0.40:
        bias = "shadow_negative"
        adjustment = -4
        adaptive_weight = 0.94
        lesson = f"{family}: las observaciones WATCH muestran presion hacia stop; Roxy baja prioridad suave."
        recommendation = "Mantener solo con checklist fuerte y evitar entradas tardias."
    elif shadow_observed >= 5 and shadow_target_rate >= 0.60 and shadow_stop_pressure <= 0.35:
        bias = "shadow_positive"
        adjustment = 3
        adaptive_weight = 1.05
        lesson = f"{family}: las observaciones WATCH casi llegan al 2%; Roxy sube prioridad suave."
        recommendation = "Probar con tamano minimo paper-only y confirmar 15m/1h."
    else:
        bias = "neutral"
        adjustment = 0
        adaptive_weight = 1.0
        lesson = f"{family}: resultados mixtos; mantener reglas actuales sin aumentar riesgo."
        recommendation = "Operar solo con checklist completo y target minimo 2% viable."

    return {
        "strategy_family": family,
        "seen": seen,
        "alerts": alerts,
        "hit_2pct": hit_2pct,
        "hit_5pct": hit_5pct,
        "hit_10pct": hit_10pct,
        "stops": stops,
        "hit_2_rate": hit_2_rate,
        "hit_5_rate": hit_5_rate,
        "hit_10_rate": hit_10_rate,
        "stop_rate": stop_rate,
        "shadow_tracked": shadow_tracked,
        "shadow_observed": shadow_observed,
        "shadow_hit_2pct": shadow_hit_2pct,
        "shadow_near_2pct": shadow_near_2pct,
        "shadow_near_stop": shadow_near_stop,
        "shadow_stops": shadow_stops,
        "shadow_target_rate": shadow_target_rate,
        "shadow_stop_pressure": shadow_stop_pressure,
        "bias": bias,
        "score_adjustment": adjustment,
        "adaptive_weight": adaptive_weight,
        "lesson": lesson,
        "recommendation": recommendation,
    }


def summarize_strategy_learning(memory: dict[str, Any]) -> list[dict[str, Any]]:
    refresh_strategy_shadow_stats(memory)
    stats_by_family = memory.get("strategy_stats") or {}
    profiles = [strategy_learning_profile(family, stats) for family, stats in stats_by_family.items()]
    profiles.sort(
        key=lambda item: (
            item["bias"] in {"positive", "shadow_positive"},
            item["hit_2_rate"],
            item["shadow_target_rate"],
            -item["stop_rate"],
            item["alerts"],
        ),
        reverse=True,
    )
    return profiles


def learning_research_queue(memory: dict[str, Any]) -> list[dict[str, Any]]:
    profiles = summarize_strategy_learning(memory)
    queue: list[dict[str, Any]] = []
    for profile in profiles:
        alerts = int(profile.get("alerts", 0) or 0)
        if profile["bias"] == "shadow_positive":
            queue.append(
                {
                    "priority": "shadow_promote",
                    "strategy_family": profile["strategy_family"],
                    "idea": "Las senales WATCH estan acercandose al 2% antes de tener muestra real completa.",
                    "rule": "Subir peso pequeno solo en ranking paper; no aumentar tamano real.",
                }
            )
        elif profile["bias"] == "shadow_negative":
            queue.append(
                {
                    "priority": "shadow_tighten",
                    "strategy_family": profile["strategy_family"],
                    "idea": "Las senales WATCH se acercan demasiado al stop.",
                    "rule": "Exigir confirmacion 1h, entrada 15m y riesgo menor antes de alertar.",
                }
            )
        elif alerts < 3:
            queue.append(
                {
                    "priority": "collect_data",
                    "strategy_family": profile["strategy_family"],
                    "idea": "Recolectar mas senales antes de ajustar reglas.",
                    "rule": "No subir tamano hasta tener al menos 3 alertas con resultado.",
                }
            )
        elif profile["bias"] == "positive":
            queue.append(
                {
                    "priority": "promote",
                    "strategy_family": profile["strategy_family"],
                    "idea": "Esta estrategia muestra ventaja relativa en memoria.",
                    "rule": "Probar mayor peso en ranking, manteniendo riesgo maximo 1% por trade.",
                }
            )
        elif profile["bias"] == "negative":
            queue.append(
                {
                    "priority": "tighten_filter",
                    "strategy_family": profile["strategy_family"],
                    "idea": "Esta estrategia necesita filtro extra antes de alertar.",
                    "rule": "Exigir volumen relativo >= 1.1 y riesgo <= 2.5% antes de enviar alerta.",
                }
            )
    return queue[:8]


def gate_research_queue(memory: dict[str, Any]) -> list[dict[str, Any]]:
    journal = memory.get("signal_journal") or []
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in journal:
        family = safe_text(row.get("strategy_family")) or strategy_family_for_row(row)
        gate = safe_text(row.get("alert_gate")) or "UNKNOWN"
        key = (family, gate)
        item = grouped.setdefault(
            key,
            {
                "strategy_family": family,
                "gate": gate,
                "count": 0,
                "blockers": {},
                "last_seen_at": None,
            },
        )
        item["count"] += 1
        item["last_seen_at"] = row.get("last_seen_at") or row.get("opened_at") or item.get("last_seen_at")
        for blocker in row.get("alert_blockers") or []:
            text = safe_text(blocker)
            if text:
                item["blockers"][text] = int(item["blockers"].get(text, 0)) + 1

    rows: list[dict[str, Any]] = []
    for item in grouped.values():
        blockers = sorted(item["blockers"].items(), key=lambda value: value[1], reverse=True)
        top_blocker = blockers[0][0] if blockers else "-"
        gate = safe_text(item["gate"])
        if gate == "WAIT_VOLUME":
            experiment = "Probar umbral de volumen >= 1.1x antes de promover WATCH a alerta."
        elif gate == "WAIT_15M_ENTRY":
            experiment = "Exigir una vela BUY fresca en 15m despues de que 1h siga valido."
        elif gate == "WAIT_1H_CONFIRM":
            experiment = "Retrasar alertas hasta trend_score >= 70 o setup 1h de continuacion."
        elif gate == "NO_TRADE_STRUCTURE":
            experiment = "Mantener bloqueado hasta que la estructura se recupere; no pelear setups bajistas/AVOID."
        else:
            experiment = "Recolectar mas muestras y comparar contra target/stop."
        rows.append(
            {
                "priority": "gate_research",
                "strategy_family": item["strategy_family"],
                "gate": gate,
                "count": item["count"],
                "top_blocker": top_blocker,
                "experiment": experiment,
                "last_seen_at": item.get("last_seen_at"),
            }
        )
    rows.sort(key=lambda row: (row["count"], row["strategy_family"]), reverse=True)
    return rows[:8]


def build_strategy_lab(
    memory: dict[str, Any],
    *,
    backtest_summary: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Build Roxy's strategy lab decisions from memory and backtest evidence."""
    profiles = summarize_strategy_learning(memory)
    research_rows = learning_research_queue(memory)
    research_by_family = {
        safe_text(row.get("strategy_family")): row
        for row in research_rows
        if safe_text(row.get("strategy_family"))
    }
    profile_by_family = {safe_text(row.get("strategy_family")): row for row in profiles}

    backtest_by_family: dict[str, dict[str, Any]] = {}
    if backtest_summary is not None and not backtest_summary.empty and "strategy_family" in backtest_summary.columns:
        for _, item in backtest_summary.iterrows():
            row = item.to_dict()
            family = safe_text(row.get("strategy_family"))
            if family:
                backtest_by_family[family] = row

    families = sorted(set(CORE_STRATEGIES) | set(profile_by_family) | set(backtest_by_family))
    rows: list[dict[str, Any]] = []
    for family in families:
        profile = profile_by_family.get(family) or strategy_learning_profile(
            family,
            (memory.get("strategy_stats") or {}).get(family, {}),
        )
        backtest = backtest_by_family.get(family, {})
        alerts = int(profile.get("alerts", 0) or 0)
        trades = int(safe_float(backtest.get("trades")) or 0)
        hit_2_rate = safe_float(profile.get("hit_2_rate")) or 0.0
        stop_rate = safe_float(profile.get("stop_rate")) or 0.0
        win_rate = safe_float(backtest.get("win_rate"))
        profit_factor = safe_float(backtest.get("profit_factor"))
        pf_score = 0.0
        if profit_factor is not None:
            pf_score = min(profit_factor, 3.0) / 3.0
        backtest_score = ((win_rate or 0.0) + pf_score) / 2.0 if backtest else 0.0
        evidence_score = max(0.0, min(1.0, (hit_2_rate * 0.45) + (backtest_score * 0.40) - (stop_rate * 0.25) + 0.25))

        memory_ready = alerts >= 3
        shadow_ready = int(profile.get("shadow_observed", 0) or 0) >= 3
        backtest_ready = trades >= 10
        bias = safe_text(profile.get("bias")) or "learning"
        if not memory_ready and not backtest_ready and not shadow_ready:
            lab_state = "Collect data"
            lab_decision = "Roxy necesita mas resultados antes de cambiar reglas."
            production_action = "Mantener reglas actuales del scanner."
        elif bias in {"negative", "shadow_negative"} or stop_rate >= 0.50 or (backtest_ready and (win_rate or 0.0) < 0.42):
            lab_state = "Tighten filter"
            lab_decision = "Reducir alertas hasta que mejoren riesgo, volumen y entrada 15m."
            production_action = "Bajar peso del ranking y exigir confirmacion mas fuerte."
        elif bias == "positive" and (not backtest_ready or (win_rate or 0.0) >= 0.48) and stop_rate <= 0.35:
            lab_state = "Promote"
            lab_decision = "Priorizar este setup cuando 1h y entrada 15m esten alineados."
            production_action = "Subir peso del ranking dentro de alertas paper."
        elif bias == "shadow_positive":
            lab_state = "Watch"
            lab_decision = "Evidencia WATCH positiva; subir peso suave, pero esperar muestra real."
            production_action = "Solo ajuste pequeno en ranking paper, sin cambiar tamano."
        else:
            lab_state = "Watch"
            lab_decision = "Seguir probando sin aumentar riesgo."
            production_action = "Usar solo con checklist completo."

        research = research_by_family.get(family, {})
        rows.append(
            {
                "strategy_family": family,
                "lab_state": lab_state,
                "evidence_score": evidence_score,
                "memory_bias": bias,
                "adaptive_weight": profile.get("adaptive_weight", 1.0),
                "alerts": alerts,
                "seen": profile.get("seen", 0),
                "hit_2_rate": hit_2_rate,
                "hit_5_rate": safe_float(profile.get("hit_5_rate")) or 0.0,
                "hit_10_rate": safe_float(profile.get("hit_10_rate")) or 0.0,
                "stop_rate": stop_rate,
                "shadow_tracked": profile.get("shadow_tracked", 0),
                "shadow_observed": profile.get("shadow_observed", 0),
                "shadow_target_rate": profile.get("shadow_target_rate", 0.0),
                "shadow_stop_pressure": profile.get("shadow_stop_pressure", 0.0),
                "backtest_trades": trades,
                "backtest_win_rate": win_rate,
                "backtest_profit_factor": profit_factor,
                "lab_decision": lab_decision,
                "production_action": production_action,
                "experiment_priority": research.get("priority") or lab_state.lower().replace(" ", "_"),
                "experiment_idea": research.get("idea") or profile.get("recommendation"),
                "experiment_rule": research.get("rule") or profile.get("recommendation"),
                "lesson": profile.get("lesson"),
            }
        )
    rows.sort(
        key=lambda item: (
            item["lab_state"] == "Promote",
            int(item.get("shadow_observed", 0) or 0) > 0 or int(item.get("seen", 0) or 0) > 0,
            item["evidence_score"],
            item["alerts"],
            item["shadow_observed"],
            item["seen"],
            item["backtest_trades"],
        ),
        reverse=True,
    )
    return rows


def autonomous_learning_plan(
    memory: dict[str, Any],
    *,
    backtest_summary: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Convert lab evidence into safe, paper-only learning actions."""
    lab_rows = build_strategy_lab(memory, backtest_summary=backtest_summary)
    gate_rows = gate_research_queue(memory)
    actions: list[dict[str, Any]] = []

    for row in lab_rows:
        family = safe_text(row.get("strategy_family"))
        lab_state = safe_text(row.get("lab_state"))
        evidence = safe_float(row.get("evidence_score")) or 0.0
        if lab_state == "Promote":
            action = "PROMOTE_IN_RANKING"
            proposed_rule = "Subir 10% el peso del ranking paper-alert solo cuando el smart gate este completo."
            activation = "Necesita mantener stop_rate <= 35% y tasa de target 2% sobre 50%."
        elif lab_state == "Tighten filter":
            action = "TIGHTEN_FILTER"
            proposed_rule = "Exigir volumen relativo >= 1.10x, riesgo <= 2.5%, y 15m BUY antes de alertar."
            activation = "Correr como filtro paper-only hasta que 10 muestras nuevas confirmen menos stops."
        elif lab_state == "Watch":
            action = "KEEP_IN_SHADOW_TEST"
            proposed_rule = "Mantener estrategia disponible, sin subir ranking ni tamano."
            activation = "Necesita mejor backtest o memoria antes de promover."
        else:
            action = "COLLECT_MORE_DATA"
            proposed_rule = "Registrar cada resultado WATCH/AVOID sin cambiar el ranking de produccion."
            activation = "Necesita al menos 3 alertas cerradas o 10 trades de backtest."

        actions.append(
            {
                "strategy_family": family,
                "source": "strategy_lab",
                "action": action,
                "lab_state": lab_state,
                "evidence_score": round(evidence, 4),
                "proposed_rule": proposed_rule,
                "activation_rule": activation,
                "safety_mode": "PAPER_ONLY",
                "why": row.get("lab_decision"),
            }
        )

    existing = {(row["strategy_family"], row["action"]) for row in actions}
    for gate in gate_rows:
        family = safe_text(gate.get("strategy_family"))
        gate_name = safe_text(gate.get("gate"))
        key = (family, f"SHADOW_TEST_{gate_name}")
        if key in existing:
            continue
        actions.append(
            {
                "strategy_family": family,
                "source": "smart_gate",
                "action": f"SHADOW_TEST_{gate_name}",
                "lab_state": "Shadow test",
                "evidence_score": 0.0,
                "proposed_rule": gate.get("experiment"),
                "activation_rule": "Comparar futuros WATCH contra memoria de stop/target antes de cambiar alertas.",
                "safety_mode": "PAPER_ONLY",
                "why": f"Bloqueado {gate.get('count')} vez/veces; bloqueo principal: {gate.get('top_blocker')}",
            }
        )

    def action_priority(item: dict[str, Any]) -> int:
        action = safe_text(item.get("action")).upper()
        if action == "PROMOTE_IN_RANKING":
            return 5
        if action == "TIGHTEN_FILTER":
            return 4
        if safe_text(item.get("source")) == "smart_gate":
            return 3
        if action == "KEEP_IN_SHADOW_TEST":
            return 2
        return 1

    actions.sort(
        key=lambda item: (
            action_priority(item),
            safe_float(item.get("evidence_score")) or 0.0,
        ),
        reverse=True,
    )
    return actions[:12]


def experiment_status_for_action(action: str, evidence_score: float) -> str:
    action = safe_text(action).upper()
    if action == "PROMOTE_IN_RANKING" and evidence_score >= 0.60:
        return "PAPER_WEIGHT_READY"
    if action == "PROMOTE_IN_RANKING":
        return "PAPER_PROMOTION_WATCH"
    if action == "TIGHTEN_FILTER":
        return "TIGHTEN_IN_SHADOW"
    if action.startswith("SHADOW_TEST_"):
        return "SHADOW_TEST"
    if action == "KEEP_IN_SHADOW_TEST":
        return "SHADOW_TEST"
    return "COLLECTING_DATA"


def experiment_key(item: dict[str, Any]) -> str:
    family = safe_text(item.get("strategy_family")).upper() or "UNKNOWN"
    action = safe_text(item.get("action")).upper() or "UNKNOWN"
    source = safe_text(item.get("source")).upper() or "UNKNOWN"
    return f"{family}:{source}:{action}"


def experiment_outcome_stats(memory: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    """Summarize observed outcomes for the strategy/gate behind a lab experiment."""
    family = safe_text(item.get("strategy_family"))
    action = safe_text(item.get("action")).upper()
    gate_filter = action.removeprefix("SHADOW_TEST_") if action.startswith("SHADOW_TEST_") else ""
    rows: list[dict[str, Any]] = []
    for source, collection in (
        ("alert", memory.get("alert_history") or []),
        ("journal", memory.get("signal_journal") or []),
    ):
        for raw in collection:
            row = dict(raw)
            row_family = safe_text(row.get("strategy_family")) or strategy_family_from_setup(
                safe_text(row.get("trigger_setup")),
                trend_setup=safe_text(row.get("trend_setup")),
            )
            if family and row_family != family:
                continue
            if gate_filter and safe_text(row.get("alert_gate")).upper() != gate_filter:
                continue
            row["_source"] = source
            rows.append(row)

    hit_2 = 0
    hit_5 = 0
    hit_10 = 0
    stops = 0
    measured = 0
    open_count = 0
    last_outcome_at = ""
    for row in rows:
        status = safe_text(row.get("status")).upper()
        milestones = {safe_text(value).upper() for value in row.get("milestones", [])}
        reached_2 = status in {"HIT_2PCT", "HIT_5PCT", "HIT_10PCT"} or "2%" in milestones
        reached_5 = status in {"HIT_5PCT", "HIT_10PCT"} or "5%" in milestones
        reached_10 = status == "HIT_10PCT" or "10%" in milestones
        stopped = status == "STOP"
        if reached_2:
            hit_2 += 1
        if reached_5:
            hit_5 += 1
        if reached_10:
            hit_10 += 1
        if stopped:
            stops += 1
        if reached_2 or reached_5 or reached_10 or stopped:
            measured += 1
            last_outcome_at = safe_text(row.get("closed_at") or row.get("last_checked_at") or row.get("last_seen_at")) or last_outcome_at
        else:
            open_count += 1

    hit_2_rate = _rate(hit_2, measured)
    stop_rate = _rate(stops, measured)
    if measured < 3:
        outcome_state = "INSUFFICIENT_OUTCOMES"
    elif hit_2_rate >= 0.55 and stop_rate <= 0.35:
        outcome_state = "WORKING_SAMPLE"
    elif stop_rate >= 0.50 and hit_2_rate < 0.35:
        outcome_state = "WEAK_SAMPLE"
    else:
        outcome_state = "MIXED_SAMPLE"

    return {
        "sample_count": len(rows),
        "measured_count": measured,
        "open_count": open_count,
        "hit_2_count": hit_2,
        "hit_5_count": hit_5,
        "hit_10_count": hit_10,
        "stop_count": stops,
        "hit_2_rate": hit_2_rate,
        "stop_rate": stop_rate,
        "outcome_state": outcome_state,
        "last_outcome_at": last_outcome_at,
    }


def update_experiment_registry(
    memory: dict[str, Any],
    learning_plan: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Persist paper-only lab experiments so Roxy can compare them across scans."""
    registry = memory.setdefault("experiment_registry", [])
    by_key = {safe_text(item.get("key")): item for item in registry if safe_text(item.get("key"))}
    timestamp = now_iso()
    for item in learning_plan:
        key = experiment_key(item)
        evidence = safe_float(item.get("evidence_score")) or 0.0
        outcome_stats = experiment_outcome_stats(memory, item)
        payload = {
            "key": key,
            "strategy_family": safe_text(item.get("strategy_family")),
            "source": safe_text(item.get("source")),
            "action": safe_text(item.get("action")),
            "status": experiment_status_for_action(safe_text(item.get("action")), evidence),
            "safety_mode": "PAPER_ONLY",
            "evidence_score": round(evidence, 4),
            "proposed_rule": safe_text(item.get("proposed_rule")),
            "activation_rule": safe_text(item.get("activation_rule")),
            "why": safe_text(item.get("why")),
            **outcome_stats,
            "last_seen_at": timestamp,
        }
        if key in by_key:
            existing = by_key[key]
            existing.update(payload)
            existing["seen_count"] = int(existing.get("seen_count", 0) or 0) + 1
            existing["updated_at"] = timestamp
        else:
            payload["created_at"] = timestamp
            payload["updated_at"] = timestamp
            payload["seen_count"] = 1
            payload["promoted_to_live"] = False
            registry.append(payload)
            by_key[key] = payload

    registry.sort(
        key=lambda row: (
            row.get("status") == "PAPER_WEIGHT_READY",
            safe_float(row.get("evidence_score")) or 0.0,
            int(row.get("seen_count", 0) or 0),
        ),
        reverse=True,
    )
    memory["experiment_registry"] = registry[:MAX_EXPERIMENT_REGISTRY]
    return memory["experiment_registry"]


def explain_opportunity(row: dict[str, Any], memory: dict[str, Any]) -> str:
    symbol = safe_text(row.get("symbol")).upper()
    family = strategy_family_for_row(row)
    profile = strategy_learning_profile(family, (memory.get("strategy_stats") or {}).get(family, {}))
    trigger = safe_text(row.get("trigger_setup") or row.get("setup"))
    trend = safe_text(row.get("trend_setup"))
    score = safe_float(row.get("confluence_score")) or safe_float(row.get("ai_score")) or 0.0
    risk = safe_float(row.get("risk_pct"))
    target = safe_float(row.get("recommended_target_pct"))
    rel_vol = safe_float(row.get("relative_volume_15m") or row.get("relative_volume"))

    parts = [f"{symbol}: Roxy lo clasifica como {family}."]
    if trigger or trend:
        parts.append(f"Setup 15m/1h: {trigger or '-'} / {trend or '-'}.")
    parts.append(f"Score {score:.0f}; peso adaptativo {profile['adaptive_weight']:.2f}.")
    if risk is not None:
        parts.append(f"Riesgo medido {risk * 100:.2f}%.")
    if target is not None:
        parts.append(f"Objetivo recomendado {target * 100:.0f}%.")
    if rel_vol is not None:
        parts.append(f"Volumen relativo {rel_vol:.2f}x.")
    parts.append(profile["lesson"])
    roxy_decision = row.get("roxy_decision") if isinstance(row.get("roxy_decision"), dict) else {}
    decision_label = safe_text(roxy_decision.get("label"))
    next_action = safe_text(roxy_decision.get("next_action"))
    priority = safe_float(roxy_decision.get("priority_score"))
    if decision_label:
        decision_part = f"Decision operativa: {decision_label}"
        if priority is not None:
            decision_part += f" ({priority:.0f}/100)"
        if next_action:
            decision_part += f". Siguiente paso: {next_action}"
        parts.append(decision_part)
    knowledge = row.get("knowledge_enrichment") if isinstance(row.get("knowledge_enrichment"), dict) else {}
    knowledge_reasoning = safe_text(knowledge.get("roxy_reasoning"))
    if knowledge_reasoning:
        parts.append(f"Base de estudio: {knowledge_reasoning}")
    return " ".join(parts)


def _memory_note(memory: dict[str, Any], family: str) -> tuple[int, str]:
    profile = strategy_learning_profile(family, (memory.get("strategy_stats") or {}).get(family, {}))
    return int(profile["score_adjustment"]), str(profile["lesson"])


def apply_memory_lessons(opportunities: list[dict[str, Any]], memory: dict[str, Any]) -> list[dict[str, Any]]:
    refresh_strategy_shadow_stats(memory)
    adjusted: list[dict[str, Any]] = []
    for row in opportunities:
        item = dict(row)
        family = strategy_family_for_row(item)
        adjustment, note = _memory_note(memory, family)
        profile = strategy_learning_profile(family, (memory.get("strategy_stats") or {}).get(family, {}))
        item["strategy_family"] = family
        item["memory_note"] = note
        item["adaptive_weight"] = profile["adaptive_weight"]
        item["learning_bias"] = profile["bias"]
        item["ai_score"] = int(max(0, min(100, int(item.get("ai_score", 0) or 0) + adjustment)))
        if adjustment < 0 and item.get("ai_action") == "ALERT":
            item["ai_action"] = "WATCH"
            item["memory_filter"] = "WEAK_STRATEGY_HISTORY"
            item["alert_gate"] = "BLOCKED_BY_MEMORY"
            item["alert_blockers"] = [note]
        smart_alert = evaluate_smart_alert(item, memory)
        if item.get("ai_action") == "ALERT" and not smart_alert["notification_ok"]:
            item["ai_action"] = "WATCH"
        item["smart_alert"] = smart_alert
        item["alert_gate"] = item.get("alert_gate") or smart_alert["gate"]
        item["alert_blockers"] = item.get("alert_blockers") or smart_alert["blockers"]
        item["alert_readiness_score"] = smart_alert["readiness_score"]
        item["alert_movement"] = smart_alert["movement"]
        item["alert_quality"] = smart_alert["quality"]
        item["alert_quality_reason"] = smart_alert["quality_reason"]
        item["alert_primary_blocker"] = smart_alert["primary_blocker"]
        item["alert_next_action"] = smart_alert["next_action"]
        adjusted.append(item)
    try:
        adjusted = process_opportunities_with_decisions(adjusted, enrich_knowledge="knowledge_enrichment" not in adjusted[0] if adjusted else True)
    except Exception:
        pass
    adjusted.sort(
        key=lambda value: (
            value.get("roxy_decision_status") == "OPERATE_NOW",
            value.get("ai_action") == "ALERT",
            value.get("roxy_priority_score", value.get("ai_score", 0)),
        ),
        reverse=True,
    )
    return adjusted


def score_opportunity(row: dict[str, Any]) -> int:
    score = safe_float(row.get("confluence_score"))
    if score is None:
        score = safe_float(row.get("score"))
    score = score or 0.0
    signal = safe_text(row.get("signal")).upper()
    decision = safe_text(row.get("trade_decision") or row.get("decision")).upper()
    risk = safe_float(row.get("risk_pct"))
    target_pct = safe_float(row.get("recommended_target_pct")) or 0.0
    rel_vol = safe_float(row.get("relative_volume_15m"))
    if rel_vol is None:
        rel_vol = safe_float(row.get("relative_volume"))
    trend_score = safe_float(row.get("trend_score"))
    if trend_score is None:
        trend_score = safe_float(row.get("score"))
    trend_score = trend_score or 0.0

    points = score
    if signal == "AVOID":
        points -= 40
    elif signal == "WATCH":
        points -= 8
    if decision and not decision.startswith("TRADE_FOR"):
        points -= 12
    elif not decision:
        points -= 8
    if risk is not None:
        if risk <= 0.015:
            points += 10
        elif risk <= 0.025:
            points += 5
        elif risk > 0.10:
            points -= 35
        elif risk > 0.06:
            points -= 28
        elif risk > 0.035:
            points -= 20
    else:
        points -= 15
    if target_pct >= 0.10:
        points += 8
    elif target_pct >= 0.05:
        points += 5
    elif target_pct >= 0.02:
        points += 2
    else:
        points -= 12
    if rel_vol is not None and rel_vol >= 1.1:
        points += 5
    if trend_score >= 75:
        points += 4
    return int(max(0, min(100, round(points))))


def normalize_opportunity_row(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    entry = safe_float(item.get("entry"))
    stop = safe_float(item.get("stop"))
    signal = safe_text(item.get("signal")).upper()
    if safe_float(item.get("risk_pct")) is None and entry is not None and stop is not None and entry > 0 and 0 < stop < entry:
        item["risk_pct"] = round((entry - stop) / entry, 6)
    target_pct = safe_float(item.get("recommended_target_pct") or item.get("target_pct"))
    explicit_target_price = safe_float(item.get("recommended_target_price") or item.get("target_price"))
    if explicit_target_price is None:
        for field in ("target_2pct_price", "target_5pct_price", "target_10pct_price"):
            explicit_target_price = safe_float(item.get(field))
            if explicit_target_price is not None:
                item["recommended_target_price"] = explicit_target_price
                item["target_basis"] = f"explicit_price_field:{field}"
                break
    if target_pct is None:
        decision = safe_text(item.get("trade_decision") or item.get("decision")).upper()
        explicit_decision_target = re.fullmatch(r"TRADE_FOR_(2|5|10)PCT", decision)
        if explicit_decision_target:
            target_pct = int(explicit_decision_target.group(1)) / 100.0
            item["recommended_target_pct"] = target_pct
            item["target_basis"] = "decision_operativa_explicita"
    if explicit_target_price is not None:
        item["recommended_target_price"] = explicit_target_price
        item["target_contract"] = "EXPLICIT_TARGET"
    elif entry is not None and entry > 0 and target_pct is not None:
        if safe_float(item.get("recommended_target_price")) is None:
            item["recommended_target_price"] = round(entry * (1.0 + target_pct), 6)
        item["target_contract"] = "EXPLICIT_TARGET"
    elif signal != "AVOID":
        item["target_contract"] = "MISSING_EXPLICIT_TARGET"
    return item


def external_market_rows_for_decisions(*, ttl_seconds: int = 45) -> list[dict[str, Any]]:
    """Fetch a short-lived external snapshot only when credentials/config exist.

    This keeps tests and unconfigured local runs offline, while Render can use
    Finviz/Crypto.com when the corresponding environment variables are present.
    """
    if build_external_market_snapshot is None:
        return []
    enabled = str(os.getenv("ROXY_EXTERNAL_CONFIRMATION_ENABLED", "true") or "true").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return []
    remote_requested = str(os.getenv("ROXY_EXTERNAL_CONFIRMATION_REMOTE", "") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    configured = any(
        str(os.getenv(key) or "").strip()
        for key in (
            "ROXY_FINVIZ_EXPORT_URL",
            "FINVIZ_EXPORT_URL",
            "ROXY_FINVIZ_AUTH_TOKEN",
            "FINVIZ_AUTH_TOKEN",
            "FINVIZ_API_KEY",
            "ROXY_CRYPTOCOM_API_KEY",
            "CRYPTO_COM_API_KEY",
            "ROXY_CRYPTOCOM_API_SECRET",
            "CRYPTO_COM_API_SECRET",
        )
    )
    if not configured and not remote_requested:
        return []
    now = time.time()
    if now < float(_EXTERNAL_MARKET_CACHE.get("expires_at") or 0):
        return [dict(row) for row in _EXTERNAL_MARKET_CACHE.get("rows", []) if isinstance(row, dict)]
    try:
        snapshot = build_external_market_snapshot(include_remote=True)
    except Exception:
        return []
    rows = snapshot.get("rows") if isinstance(snapshot, dict) else []
    clean_rows = [dict(row) for row in rows if isinstance(row, dict)]
    _EXTERNAL_MARKET_CACHE["rows"] = clean_rows
    _EXTERNAL_MARKET_CACHE["expires_at"] = now + max(10, ttl_seconds)
    return [dict(row) for row in clean_rows]


def extract_opportunities(confluence_df: pd.DataFrame, *, limit: int = 8) -> list[dict[str, Any]]:
    if confluence_df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, item in confluence_df.iterrows():
        row = normalize_opportunity_row(item.to_dict())
        row["ai_score"] = score_opportunity(row)
        smart_alert = evaluate_smart_alert(row)
        row["smart_alert"] = smart_alert
        row["alert_gate"] = smart_alert["gate"]
        row["alert_blockers"] = smart_alert["blockers"]
        row["alert_readiness_score"] = smart_alert["readiness_score"]
        row["alert_movement"] = smart_alert["movement"]
        row["alert_quality"] = smart_alert["quality"]
        row["alert_quality_reason"] = smart_alert["quality_reason"]
        row["alert_primary_blocker"] = smart_alert["primary_blocker"]
        row["alert_next_action"] = smart_alert["next_action"]
        row["ai_action"] = "ALERT" if _is_trade_candidate(row) else "WATCH"
        if row["ai_action"] == "ALERT" or row["ai_score"] >= 70:
            rows.append(row)
    rows.sort(key=lambda value: (value.get("ai_action") == "ALERT", value.get("ai_score", 0)), reverse=True)
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (safe_text(row.get("market")).lower(), safe_text(row.get("symbol")).upper())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= limit:
            break
    try:
        enriched = enrich_opportunities_with_knowledge(deduped)
    except Exception:
        enriched = deduped
    external_rows = external_market_rows_for_decisions()
    if external_rows:
        enriched = [dict(item, _external_market_rows=external_rows) for item in enriched]
    try:
        return process_opportunities_with_decisions(enriched, enrich_knowledge=False)
    except Exception:
        return enriched



def crypto_scan_candidate_rows(scan_df: pd.DataFrame | None, *, limit: int = 3) -> list[dict[str, Any]]:
    if scan_df is None or scan_df.empty or "symbol" not in scan_df.columns:
        return []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    source = scan_df.copy()
    if "market" in source.columns:
        source = source[source["market"].astype(str).str.lower().eq("crypto")]
    else:
        source = source[source["symbol"].astype(str).str.contains("/", regex=False, na=False)]
    if source.empty:
        return []
    preferred_rank = {symbol: index for index, symbol in enumerate(PREFERRED_CRYPTO_RESCUE_SYMBOLS)}
    source["_normalized_symbol"] = source["symbol"].map(lambda value: safe_text(value).upper())
    source = source[source["_normalized_symbol"].isin(preferred_rank)]
    if source.empty:
        return []
    source["_preferred_rank"] = source["_normalized_symbol"].map(preferred_rank).fillna(len(preferred_rank))
    for column in ["score", "relative_volume"]:
        if column in source.columns:
            source[column] = pd.to_numeric(source[column], errors="coerce")
    if "raw_signal" in source.columns:
        source["_raw_buy"] = source["raw_signal"].astype(str).str.upper().eq("BUY").astype(int)
    else:
        source["_raw_buy"] = 0
    if "signal" in source.columns:
        source["_signal_buy"] = source["signal"].astype(str).str.upper().eq("BUY").astype(int)
    else:
        source["_signal_buy"] = 0
    sort_columns = [
        column
        for column in ["_preferred_rank", "_raw_buy", "_signal_buy", "score", "relative_volume"]
        if column in source.columns
    ]
    if sort_columns:
        source = source.sort_values(
            sort_columns,
            ascending=[True if column == "_preferred_rank" else False for column in sort_columns],
        )
    for _, item in source.iterrows():
        symbol = safe_text(item.get("symbol")).upper()
        if not symbol or symbol in seen:
            continue
        score = safe_float(item.get("score")) or 0.0
        raw_signal = safe_text(item.get("raw_signal") or item.get("signal")).upper()
        signal = "BUY" if raw_signal == "BUY" else safe_text(item.get("signal") or "WATCH").upper() or "WATCH"
        if score < 55 and signal != "BUY":
            continue
        observed_price = safe_float(item.get("current_price") or item.get("last_price") or item.get("price") or item.get("close"))
        entry = safe_float(item.get("entry") or item.get("close"))
        stop = safe_float(item.get("stop") or item.get("risk_anchor"))
        risk_pct = None
        if entry is not None and stop is not None and entry > 0 and stop < entry:
            risk_pct = round((entry - stop) / entry, 6)
        setup = safe_text(item.get("setup") or "CRYPTO_SCAN")
        backtest_text = safe_text(item.get("backtest_eligible")).lower()
        backtest_eligible = item.get("backtest_eligible") is True or backtest_text in {"1", "true", "yes", "y"}
        candidate = {
            "market": "crypto",
            "symbol": symbol,
            "signal": signal,
            "raw_signal": raw_signal or signal,
            "trade_decision": "WAIT_FOR_TRIGGER",
            "action": "CRYPTO_SCAN_WATCH",
            "ai_action": "WATCH",
            "ai_score": int(max(0, min(100, round(score)))),
            "confluence_score": int(max(0, min(100, round(score)))),
            "entry_tf": safe_text(item.get("tf") or "15m"),
            "timeframe": safe_text(item.get("tf") or "15m"),
            "trigger_setup": setup,
            "trend_setup": setup,
            "trigger_score": int(max(0, min(100, round(score)))),
            "trend_score": int(max(0, min(100, round(score)))),
            "entry": entry,
            "current_price": observed_price,
            "price_basis": "ultimo cierre del scan normalizado" if observed_price is not None else "precio no disponible",
            "stop": stop,
            "risk_pct": risk_pct,
            "recommended_target_pct": None,
            "recommended_target_price": None,
            "target_contract": "MISSING_EXPLICIT_TARGET",
            "levels_status": "WATCH_ONLY_INCOMPLETE",
            "levels_source": "normalized_scan",
            "relative_volume_15m": safe_float(item.get("relative_volume")),
            "backtest_eligible": backtest_eligible,
            "backtest_profit_factor": safe_float(item.get("backtest_profit_factor")),
            "backtest_buy_hold_edge_pct": safe_float(item.get("backtest_buy_hold_edge_pct")),
            "backtest_trades": safe_float(item.get("backtest_trades")),
            "crypto_rescue_candidate": True,
            "coverage_reason": "Cripto sigue permitido mientras acciones/opciones estan bloqueadas por proveedor premium.",
            "reasons": safe_text(item.get("reasons")),
        }
        rows.append(candidate)
        seen.add(symbol)
        if len(rows) >= max(1, int(limit)):
            break
    return rows


def alert_key(row: dict[str, Any]) -> str:
    symbol = safe_text(row.get("symbol")).upper()
    decision = safe_text(row.get("trade_decision")).upper()
    entry = safe_float(row.get("entry"))
    entry_text = f"{entry:.2f}" if entry is not None else "-"
    return f"{symbol}:{decision}:{entry_text}"


def signal_journal_key(row: dict[str, Any]) -> str:
    symbol = safe_text(row.get("symbol")).upper()
    market = safe_text(row.get("market")).upper()
    action = safe_text(row.get("ai_action")).upper()
    signal = safe_text(row.get("signal")).upper()
    entry = safe_float(row.get("entry"))
    entry_text = f"{entry:.2f}" if entry is not None else "-"
    family = strategy_family_for_row(row)
    return f"{market}:{symbol}:{action}:{signal}:{family}:{entry_text}"


def should_track_signal(row: dict[str, Any]) -> bool:
    if row.get("ai_action") == "ALERT":
        return True
    score = safe_float(row.get("ai_score")) or 0.0
    signal = safe_text(row.get("signal")).upper()
    decision = safe_text(row.get("trade_decision")).upper()
    return score >= 60 or signal in {"BUY", "WATCH"} or decision.startswith("TRADE_FOR")


def current_prices_by_symbol(scan_df: pd.DataFrame | None, confluence_df: pd.DataFrame | None) -> dict[str, float]:
    prices: dict[str, float] = {}
    price_columns = ("close", "last_price", "price", "entry")
    for frame in (scan_df, confluence_df):
        if frame is None or frame.empty or "symbol" not in frame.columns:
            continue
        for _, item in frame.iterrows():
            symbol = safe_text(item.get("symbol")).upper()
            price = None
            for column in price_columns:
                if column in frame.columns:
                    price = safe_float(item.get(column))
                    if price is not None:
                        break
            if symbol and price is not None:
                prices[symbol] = price
    return prices


def update_trade_progress(row: dict[str, Any], *, current: float, entry: float, stop: float | None) -> None:
    previous_max = safe_float(row.get("max_price")) or entry
    previous_min = safe_float(row.get("min_price")) or entry
    max_price = max(previous_max, current)
    min_price = min(previous_min, current)
    current_gain_pct = (current - entry) / entry
    current_drawdown_pct = max(0.0, (entry - current) / entry)
    max_gain_pct = max(0.0, (max_price - entry) / entry)
    max_drawdown_pct = max(0.0, (entry - min_price) / entry)
    best_target_hit, best_target_pct = _target_hit_from_gain(max_gain_pct)
    row["last_price"] = current
    row["max_price"] = max_price
    row["min_price"] = min_price
    row["current_gain_pct"] = round(current_gain_pct, 6)
    row["current_drawdown_pct"] = round(current_drawdown_pct, 6)
    row["max_gain_pct"] = round(max_gain_pct, 6)
    row["max_drawdown_pct"] = round(max_drawdown_pct, 6)
    row["progress_to_2pct"] = round(min(1.0, max_gain_pct / 0.02), 4)
    row["best_target_hit"] = best_target_hit or "-"
    row["best_target_pct"] = best_target_pct
    if stop is not None and 0 < stop < entry:
        stop_distance_pct = (entry - stop) / entry
        row["progress_to_stop"] = round(min(1.0, max_drawdown_pct / stop_distance_pct), 4)
        stopped = min_price <= stop
        row["stopped_after_target"] = bool(stopped and best_target_hit)
        row["stopped_before_target"] = bool(stopped and not best_target_hit)
        risk_per_share = entry - stop
        row["current_reward_r"] = round((current - entry) / risk_per_share, 4)
        row["best_reward_r"] = round((max_price - entry) / risk_per_share, 4)
    else:
        row["progress_to_stop"] = None
        row["stopped_after_target"] = False
        row["stopped_before_target"] = False
        row["current_reward_r"] = None
        row["best_reward_r"] = None
    row["outcome_state"] = outcome_state_for_signal(row)
    row["last_checked_at"] = now_iso()


def update_alert_outcomes(memory: dict[str, Any], prices: dict[str, float]) -> dict[str, Any]:
    history = memory.setdefault("alert_history", [])
    for alert in history:
        if alert.get("status") in {"STOP", "HIT_10PCT"}:
            continue
        symbol = safe_text(alert.get("symbol")).upper()
        current = prices.get(symbol)
        entry = safe_float(alert.get("entry"))
        stop = safe_float(alert.get("stop"))
        if current is None or entry is None or entry <= 0:
            continue
        update_trade_progress(alert, current=current, entry=entry, stop=stop)
        milestones = set(alert.get("milestones", []))
        max_price = safe_float(alert.get("max_price")) or current
        if max_price >= entry * 1.10:
            milestones.update({"2%", "5%", "10%"})
            alert["status"] = "HIT_10PCT"
            alert["closed_at"] = now_iso()
        elif max_price >= entry * 1.05:
            milestones.update({"2%", "5%"})
            alert["status"] = "HIT_5PCT"
        elif max_price >= entry * 1.02:
            milestones.add("2%")
            alert["status"] = "HIT_2PCT"
        elif stop is not None and current <= stop:
            alert["status"] = "STOP"
            alert["closed_at"] = now_iso()
        else:
            alert.setdefault("status", "OPEN")
        alert["milestones"] = sorted(milestones)
        family = safe_text(alert.get("strategy_family")) or strategy_family_from_setup(
            safe_text(alert.get("trigger_setup")), trend_setup=safe_text(alert.get("trend_setup"))
        )
        stats = _strategy_stats(memory, family)
        recorded = set(alert.get("recorded_milestones", []))
        for milestone, field in (("2%", "hit_2pct"), ("5%", "hit_5pct"), ("10%", "hit_10pct")):
            if milestone in milestones and milestone not in recorded:
                stats[field] = int(stats.get(field, 0)) + 1
                recorded.add(milestone)
        if alert.get("status") == "STOP" and not alert.get("stop_recorded"):
            stats["stops"] = int(stats.get("stops", 0)) + 1
            stats["last_outcome_at"] = now_iso()
            alert["stop_recorded"] = True
        elif milestones:
            stats["last_outcome_at"] = now_iso()
        alert["recorded_milestones"] = sorted(recorded)

    journal = memory.setdefault("signal_journal", [])
    for signal in journal:
        if signal.get("status") in {"STOP", "HIT_10PCT"}:
            continue
        symbol = safe_text(signal.get("symbol")).upper()
        current = prices.get(symbol)
        entry = safe_float(signal.get("entry"))
        stop = safe_float(signal.get("stop"))
        if current is None or entry is None or entry <= 0:
            continue
        update_trade_progress(signal, current=current, entry=entry, stop=stop)
        milestones = set(signal.get("milestones", []))
        max_price = safe_float(signal.get("max_price")) or current
        if max_price >= entry * 1.10:
            milestones.update({"2%", "5%", "10%"})
            signal["status"] = "HIT_10PCT"
            signal["closed_at"] = now_iso()
        elif max_price >= entry * 1.05:
            milestones.update({"2%", "5%"})
            signal["status"] = "HIT_5PCT"
        elif max_price >= entry * 1.02:
            milestones.add("2%")
            signal["status"] = "HIT_2PCT"
        elif stop is not None and current <= stop:
            signal["status"] = "STOP"
            signal["closed_at"] = now_iso()
        else:
            signal.setdefault("status", "WATCHING")
        signal["milestones"] = sorted(milestones)
    return memory


def summarize_options(options_df: pd.DataFrame, symbol: str) -> dict[str, Any]:
    first = best_option_contract(options_df, symbol)
    if not first:
        return {}
    return {
        "contract": first.get("contractSymbol") or first.get("contract"),
        "decision": first.get("option_decision"),
        "professional_decision": first.get("professional_decision"),
        "human_decision": first.get("human_decision"),
        "score": first.get("option_score"),
        "expiry": first.get("expiry"),
        "dte": first.get("dte"),
        "strike": first.get("strike"),
        "bid": first.get("bid"),
        "ask": first.get("ask"),
        "mid": first.get("mid"),
        "spread_pct": first.get("spread_pct"),
        "spread_dollars": first.get("spread_dollars"),
        "volume": first.get("volume"),
        "openInterest": first.get("openInterest"),
        "delta": first.get("delta"),
        "gamma": first.get("gamma"),
        "theta": first.get("theta"),
        "vega": first.get("vega"),
        "breakeven_price": first.get("breakeven_price"),
        "breakeven_pct": first.get("breakeven_pct"),
        "max_loss_per_contract": first.get("max_loss_per_contract"),
        "contracts_by_risk": first.get("contracts_by_risk"),
        "risk_budget": first.get("risk_budget"),
        "quality_label": first.get("quality_label"),
        "blockers": first.get("blockers"),
        "cautions": first.get("cautions"),
        "summary": first.get("summary"),
    }


def update_memory_from_opportunities(
    opportunities: list[dict[str, Any]],
    *,
    memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    memory = memory or load_memory()
    symbols = memory.setdefault("symbols", {})
    history = memory.setdefault("alert_history", [])
    journal = memory.setdefault("signal_journal", [])
    active_keys = {safe_text(item.get("key")) for item in history if item.get("status") not in {"STOP", "HIT_10PCT"}}
    active_journal_keys = {
        safe_text(item.get("key")) for item in journal if item.get("status") not in {"STOP", "HIT_10PCT"}
    }
    journal_by_key = {safe_text(item.get("key")): item for item in journal if safe_text(item.get("key"))}
    for row in opportunities:
        symbol = safe_text(row.get("symbol")).upper()
        if not symbol:
            continue
        stats = symbols.setdefault(
            symbol,
            {
                "seen": 0,
                "alerts": 0,
                "best_ai_score": 0,
                "last_signal": None,
                "last_seen_at": None,
                "setups": {},
            },
        )
        stats["seen"] = int(stats.get("seen", 0)) + 1
        if row.get("ai_action") == "ALERT":
            stats["alerts"] = int(stats.get("alerts", 0)) + 1
        stats["best_ai_score"] = max(int(stats.get("best_ai_score", 0)), int(row.get("ai_score", 0)))
        stats["last_signal"] = safe_text(row.get("signal"))
        stats["last_seen_at"] = now_iso()
        setup = safe_text(row.get("trigger_setup") or row.get("trend_setup") or row.get("setup") or "UNKNOWN")
        setup_counts = stats.setdefault("setups", {})
        setup_counts[setup] = int(setup_counts.get(setup, 0)) + 1
        family = strategy_family_for_row(row)
        strategy_stats = _strategy_stats(memory, family)
        strategy_stats["seen"] = int(strategy_stats.get("seen", 0)) + 1
        strategy_stats["last_seen_at"] = now_iso()
        if row.get("ai_action") == "ALERT":
            key = alert_key(row)
            if key not in active_keys:
                strategy_stats["alerts"] = int(strategy_stats.get("alerts", 0)) + 1
                history.append(
                    {
                        "key": key,
                        "symbol": symbol,
                        "market": safe_text(row.get("market")),
                        "trade_decision": safe_text(row.get("trade_decision")),
                        "entry": safe_float(row.get("entry")),
                        "stop": safe_float(row.get("stop")),
                        "target_pct": safe_float(row.get("recommended_target_pct")),
                        "ai_score": row.get("ai_score"),
                        "strategy_family": family,
                        "trigger_setup": safe_text(row.get("trigger_setup") or row.get("setup")),
                        "trend_setup": safe_text(row.get("trend_setup")),
                        "opened_at": now_iso(),
                        "status": "OPEN",
                        "milestones": [],
                    }
                )
                active_keys.add(key)
        if should_track_signal(row):
            key = signal_journal_key(row)
            journal_payload = {
                "key": key,
                "symbol": symbol,
                "market": safe_text(row.get("market")),
                "ai_action": safe_text(row.get("ai_action")),
                "signal": safe_text(row.get("signal")),
                "trade_decision": safe_text(row.get("trade_decision")),
                "entry": safe_float(row.get("entry")),
                "stop": safe_float(row.get("stop")),
                "target_pct": safe_float(row.get("recommended_target_pct")),
                "ai_score": row.get("ai_score"),
                "strategy_family": family,
                "trigger_setup": safe_text(row.get("trigger_setup") or row.get("setup")),
                "trend_setup": safe_text(row.get("trend_setup")),
                "alert_gate": safe_text(row.get("alert_gate")),
                "alert_readiness_score": safe_float(row.get("alert_readiness_score")),
                "alert_movement": safe_text(row.get("alert_movement")),
                "alert_blockers": row.get("alert_blockers") or [],
                "last_seen_at": now_iso(),
            }
            current_price = (
                safe_float(row.get("close"))
                or safe_float(row.get("close_15m"))
                or safe_float(row.get("close_1h"))
                or safe_float(row.get("entry"))
            )
            if key in journal_by_key:
                existing = journal_by_key[key]
                opened_at = existing.get("opened_at")
                status = existing.get("status")
                milestones = existing.get("milestones", [])
                existing.update(journal_payload)
                existing["opened_at"] = opened_at or now_iso()
                existing["status"] = status or ("OPEN" if row.get("ai_action") == "ALERT" else "WATCHING")
                existing["milestones"] = milestones
                entry = safe_float(existing.get("entry"))
                if current_price is not None and entry is not None and entry > 0:
                    update_trade_progress(existing, current=current_price, entry=entry, stop=safe_float(existing.get("stop")))
            elif key not in active_journal_keys:
                journal_payload["opened_at"] = now_iso()
                journal_payload["status"] = "OPEN" if row.get("ai_action") == "ALERT" else "WATCHING"
                journal_payload["milestones"] = []
                entry = safe_float(journal_payload.get("entry"))
                if current_price is not None and entry is not None and entry > 0:
                    update_trade_progress(
                        journal_payload,
                        current=current_price,
                        entry=entry,
                        stop=safe_float(journal_payload.get("stop")),
                    )
                journal.append(journal_payload)
                active_journal_keys.add(key)
                journal_by_key[key] = journal_payload
        profile = strategy_learning_profile(family, strategy_stats)
        strategy_stats["adaptive_weight"] = profile["adaptive_weight"]
        strategy_stats["learning_bias"] = profile["bias"]
        strategy_stats["learning_note"] = profile["lesson"]

    refresh_strategy_shadow_stats(memory)
    for family, strategy_stats in (memory.get("strategy_stats") or {}).items():
        profile = strategy_learning_profile(family, strategy_stats)
        strategy_stats["adaptive_weight"] = profile["adaptive_weight"]
        strategy_stats["learning_bias"] = profile["bias"]
        strategy_stats["learning_note"] = profile["lesson"]

    lessons = memory.setdefault("lessons", [])
    active_alerts = [row for row in opportunities if row.get("ai_action") == "ALERT"]
    lesson = (
        "Prioridad: solo alertar BUY con confluence 15m/1h, backtest elegible, riesgo <= 3.5% y objetivo >= 2%."
    )
    if lesson not in lessons:
        lessons.append(lesson)
    if active_alerts:
        latest = f"Ultima corrida encontro {len(active_alerts)} oportunidad(es) accionables con confirmacion intradia."
    else:
        latest = "Ultima corrida no encontro entradas accionables; mantener watchlist hasta confirmacion."
    if not lessons or lessons[-1] != latest:
        lessons.append(latest)
    memory["lessons"] = lessons[-12:]
    memory["alert_history"] = history[-100:]
    memory["signal_journal"] = journal[-MAX_SIGNAL_JOURNAL:]
    return memory


def build_brief(
    *,
    confluence_df: pd.DataFrame,
    options_df: pd.DataFrame,
    scan_df: pd.DataFrame | None = None,
    memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    memory = memory or load_memory()
    prices = current_prices_by_symbol(scan_df, confluence_df)
    memory = update_alert_outcomes(memory, prices)
    opportunities = extract_opportunities(confluence_df)
    opportunities = apply_memory_lessons(opportunities, memory)
    strategy_overrides = load_strategy_overrides()
    opportunities = apply_strategy_overrides_to_rows(opportunities, strategy_overrides)
    crypto_scan_candidates = crypto_scan_candidate_rows(scan_df)
    try:
        opportunities = enrich_opportunities_with_knowledge(opportunities)
        crypto_scan_candidates = enrich_opportunities_with_knowledge(crypto_scan_candidates)
    except Exception:
        pass
    for row in opportunities:
        row["option"] = summarize_options(options_df, safe_text(row.get("symbol")))
    memory = update_memory_from_opportunities(opportunities, memory=memory)
    for row in opportunities:
        row["explanation"] = explain_opportunity(row, memory)
    learning_profiles = summarize_strategy_learning(memory)
    research_queue = learning_research_queue(memory)
    gate_research = gate_research_queue(memory)
    strategy_lab = build_strategy_lab(memory)
    learning_plan = autonomous_learning_plan(memory)
    experiment_registry = update_experiment_registry(memory, learning_plan)
    weekly_newsletter = newsletter_context()

    alert_rows = [row for row in opportunities if row.get("ai_action") == "ALERT"]
    watch_rows = [row for row in opportunities if row.get("ai_action") != "ALERT"]
    brief = {
        "generated_at": now_iso(),
        "mode": "AI_WATCH_24H",
        "alert_count": len(alert_rows),
        "watch_count": len(watch_rows),
        "opportunities": opportunities,
        "crypto_scan_candidates": crypto_scan_candidates,
        "lessons": memory.get("lessons", []),
        "learning_profiles": learning_profiles,
        "research_queue": research_queue,
        "gate_research": gate_research,
        "strategy_lab": strategy_lab,
        "learning_plan": learning_plan,
        "experiment_registry": experiment_registry,
        "strategy_overrides": strategy_overrides,
        "memory_symbols": len(memory.get("symbols", {})),
        "signal_journal_count": len(memory.get("signal_journal", [])),
        "scan_rows": int(len(scan_df)) if scan_df is not None and not scan_df.empty else 0,
        "newsletter_context": weekly_newsletter,
        "market_news": weekly_newsletter.get("market_news", []),
        "memory": memory,
    }
    brief["alert_gate_summary"] = summarize_alert_gates(brief)
    brief["daily_opportunity_plan"] = build_daily_opportunity_plan(opportunities)
    return brief


def apply_global_alert_context(brief: dict[str, Any], memory: dict[str, Any] | None = None) -> dict[str, Any]:
    source_freshness = brief.get("source_freshness") or {}
    realtime_health = brief.get("realtime_health") or {}
    macro_context = brief.get("macro_calendar") or {}
    chart_contracts = chart_health_contract_index()
    if not source_freshness and not realtime_health and not macro_context and not chart_contracts:
        return brief

    memory = memory or (brief.get("memory") if isinstance(brief.get("memory"), dict) else {}) or {}
    opportunities = []
    for row in brief.get("opportunities") or []:
        item = attach_chart_contract_to_opportunity(row, chart_contracts)
        if source_freshness:
            item["source_freshness"] = source_freshness
        if realtime_health:
            item["realtime_health"] = realtime_health
        if macro_context:
            item = apply_macro_context(item, macro_context)
        previous_action = safe_text(item.get("ai_action")).upper()
        smart_alert = evaluate_smart_alert(item, memory)
        if previous_action == "ALERT" and not smart_alert["notification_ok"]:
            item["ai_action"] = "WATCH"
        item["smart_alert"] = smart_alert
        item["alert_gate"] = smart_alert["gate"]
        item["alert_blockers"] = smart_alert["blockers"]
        item["alert_readiness_score"] = smart_alert["readiness_score"]
        item["alert_movement"] = smart_alert["movement"]
        item["alert_quality"] = smart_alert["quality"]
        item["alert_quality_reason"] = smart_alert["quality_reason"]
        item["alert_primary_blocker"] = smart_alert["primary_blocker"]
        item["alert_next_action"] = smart_alert["next_action"]
        opportunities.append(item)

    market_realtime = (
        realtime_health.get("market_realtime") if isinstance(realtime_health.get("market_realtime"), dict) else {}
    )
    realtime_stock_allowed = bool(realtime_health.get("stock_alerts_allowed", True))
    realtime_crypto_allowed = bool(realtime_health.get("crypto_alerts_allowed", True))
    if market_realtime:
        markets = market_realtime.get("markets") if isinstance(market_realtime.get("markets"), dict) else {}
        crypto_market = markets.get("crypto") if isinstance(markets.get("crypto"), dict) else {}
        if "alerts_allowed" in crypto_market:
            realtime_crypto_allowed = bool(crypto_market.get("alerts_allowed"))
        stock_market = markets.get("stock") if isinstance(markets.get("stock"), dict) else {}
        if "alerts_allowed" in stock_market:
            realtime_stock_allowed = bool(stock_market.get("alerts_allowed"))
    has_crypto_opportunity = any(safe_text(row.get("market")).lower() == "crypto" for row in opportunities)
    rescue_candidates = brief.get("crypto_scan_candidates") if isinstance(brief.get("crypto_scan_candidates"), list) else []
    rescued_count = 0
    if realtime_crypto_allowed and not realtime_stock_allowed and not has_crypto_opportunity and rescue_candidates:
        existing_symbols = {safe_text(row.get("symbol")).upper() for row in opportunities}
        for raw_candidate in rescue_candidates:
            if not isinstance(raw_candidate, dict):
                continue
            symbol = safe_text(raw_candidate.get("symbol")).upper()
            if not symbol or symbol in existing_symbols:
                continue
            item = attach_chart_contract_to_opportunity(raw_candidate, chart_contracts)
            item["source_freshness"] = source_freshness
            item["realtime_health"] = realtime_health
            if macro_context:
                item = apply_macro_context(item, macro_context)
            smart_alert = evaluate_smart_alert(item, memory)
            item["ai_action"] = "WATCH"
            item["smart_alert"] = smart_alert
            item["alert_gate"] = smart_alert["gate"]
            item["alert_blockers"] = smart_alert["blockers"]
            item["alert_readiness_score"] = smart_alert["readiness_score"]
            item["alert_movement"] = smart_alert["movement"]
            item["alert_quality"] = smart_alert["quality"]
            item["alert_quality_reason"] = smart_alert["quality_reason"]
            item["alert_primary_blocker"] = smart_alert["primary_blocker"]
            item["alert_next_action"] = smart_alert["next_action"]
            item["crypto_rescue_active"] = True
            opportunities.append(item)
            existing_symbols.add(symbol)
            rescued_count += 1
    brief["crypto_rescue"] = {
        "enabled": bool(realtime_crypto_allowed and not realtime_stock_allowed),
        "candidate_count": len(rescue_candidates),
        "rescued_count": rescued_count,
        "reason": "Stock/opciones bloqueados; cripto permitido." if realtime_crypto_allowed and not realtime_stock_allowed else "",
    }

    def operable_sort_key(value: dict[str, Any]) -> tuple[int, int, int, float, float]:
        market = safe_text(value.get("market"))
        gate = safe_text(value.get("alert_gate")).upper()
        action = safe_text(value.get("ai_action")).upper()
        allowed_market = context_allows_market_alerts(realtime_health, market) if realtime_health else True
        readiness = safe_float(value.get("alert_readiness_score")) or 0.0
        score = safe_float(value.get("ai_score")) or 0.0
        return (
            1 if action == "ALERT" else 0,
            1 if allowed_market else 0,
            0 if gate in BLOCKED_ALERT_GATES else 1,
            readiness,
            score,
        )

    opportunities.sort(key=operable_sort_key, reverse=True)
    brief["opportunities"] = opportunities
    alert_rows = [row for row in opportunities if row.get("ai_action") == "ALERT"]
    brief["alert_count"] = len(alert_rows)
    brief["watch_count"] = len(opportunities) - len(alert_rows)
    brief["alert_gate_summary"] = summarize_alert_gates(brief)
    brief["daily_opportunity_plan"] = build_daily_opportunity_plan(
        opportunities,
        source_freshness=source_freshness,
        realtime_health=realtime_health,
        market_session=brief.get("market_session") or {},
    )
    return brief


def format_alert_line(row: dict[str, Any]) -> str:
    target = safe_float(row.get("recommended_target_pct"))
    risk = safe_float(row.get("risk_pct"))
    entry = safe_float(row.get("entry"))
    stop = safe_float(row.get("stop"))
    option = row.get("option") or {}
    option_text = ""
    if option.get("contract"):
        decision = option.get("human_decision") or option.get("professional_decision") or option.get("decision")
        option_text = (
            f" | option {option.get('contract')} {decision} score {option.get('score')} "
            f"DTE {option.get('dte')} delta {option.get('delta')} spread {option.get('spread_pct')}"
        )
    entry_text = f"{entry:.2f}" if entry is not None else "-"
    stop_text = f"{stop:.2f}" if stop is not None else "-"
    risk_text = f"{risk * 100:.2f}%" if risk is not None else "-"
    target_text = f"{target * 100:.0f}%" if target is not None else "-"
    gate = safe_text(row.get("alert_gate"))
    gate_text = f" | filtro {alert_gate_label(gate)}" if gate else ""
    size_text = risk_size_text(entry, stop)
    targets_text = alert_targets_text(row, entry)
    confidence_text = alert_confidence_text(row)
    quality = safe_text(row.get("alert_quality") or (row.get("smart_alert") or {}).get("quality"))
    quality_text = f"calidad {quality} | " if quality else ""
    reason_text = human_alert_reason(row)
    action_text = human_trade_action(row)
    return (
        f"{safe_text(row.get('market')).upper()} {safe_text(row.get('symbol')).upper()} "
        f"{action_text} | {safe_text(row.get('trade_decision'))} | AI {row.get('ai_score')} | "
        f"entry {entry_text} stop {stop_text} | "
        f"risk {risk_text} target {target_text} | {targets_text} | "
        f"{quality_text}confianza {confidence_text} | {size_text} | "
        f"{safe_text(row.get('strategy_family'))}{gate_text} | razon {reason_text}{option_text}"
    )


def _alert_price_text(value: Any) -> str:
    price = safe_float(value)
    return f"{price:.2f}" if price is not None else "-"


def alert_targets_text(row: dict[str, Any], entry: Any = None) -> str:
    entry_value = safe_float(entry) or safe_float(row.get("entry"))
    target_values: list[tuple[str, float | None]] = []
    for label, pct, field in (
        ("2%", 0.02, "target_2pct_price"),
        ("5%", 0.05, "target_5pct_price"),
        ("10%", 0.10, "target_10pct_price"),
    ):
        price = safe_float(row.get(field))
        if price is None and entry_value is not None:
            price = entry_value * (1.0 + pct)
        target_values.append((label, price))
    parts = [f"{label} {_alert_price_text(price)}" for label, price in target_values]
    return "targets " + " / ".join(parts)


def alert_confidence_text(row: dict[str, Any]) -> str:
    bias = safe_text(row.get("learning_bias")).lower()
    readiness = safe_float(row.get("alert_readiness_score"))
    if bias == "positive":
        label = "alta memoria"
    elif bias == "negative":
        label = "baja memoria"
    elif bias == "shadow_positive":
        label = "laboratorio positivo"
    elif bias == "shadow_negative":
        label = "laboratorio debil"
    elif bias == "learning":
        label = "aprendiendo"
    elif bias == "neutral":
        label = "media memoria"
    else:
        label = "sin memoria"
    if readiness is None:
        return label
    return f"{label} / checklist {readiness:.0f}%"


def context_allows_market_alerts(context: dict[str, Any] | None, market: str) -> bool:
    if not isinstance(context, dict):
        return True
    market_value = safe_text(market).lower()
    if market_value in {"stock", "stocks", "equity", "option", "options"} and "stock_alerts_allowed" in context:
        return bool(context.get("stock_alerts_allowed"))
    if market_value == "crypto" and "crypto_alerts_allowed" in context:
        return bool(context.get("crypto_alerts_allowed"))
    return bool(context.get("alerts_allowed", True))


def risk_size_text(
    entry: Any,
    stop: Any,
    *,
    account_equity: float = DEFAULT_ACCOUNT_EQUITY,
    risk_pct: float = DEFAULT_RISK_PER_TRADE_PCT,
) -> str:
    entry_value = safe_float(entry)
    stop_value = safe_float(stop)
    if entry_value is None or stop_value is None or entry_value <= stop_value:
        return "size unavailable"
    risk_dollars = max(0.0, account_equity * risk_pct)
    risk_per_share = entry_value - stop_value
    shares = math.floor(risk_dollars / risk_per_share) if risk_per_share > 0 else 0
    if shares <= 0:
        return f"size $0 risk; per-share risk {risk_per_share:.2f}"
    notional = shares * entry_value
    return f"size {shares} sh for ${risk_dollars:.2f} risk (~${notional:.0f})"


def build_notification_lines(brief: dict[str, Any]) -> list[str]:
    freshness = brief.get("source_freshness") or {}
    if freshness and not freshness.get("alerts_allowed", True):
        return []
    realtime_health = brief.get("realtime_health") or {}
    if realtime_health and not realtime_health.get("alerts_allowed", True):
        return []
    rows = [row for row in brief.get("opportunities", []) if row.get("ai_action") == "ALERT"]
    if realtime_health:
        rows = [
            row
            for row in rows
            if context_allows_market_alerts(realtime_health, safe_text(row.get("market")))
        ]
    session = brief.get("market_session") or {}
    if session and not session.get("stock_alerts_allowed", True):
        rows = [row for row in rows if safe_text(row.get("market")).lower() == "crypto"]
    if not rows:
        return []
    return [format_alert_line(row) for row in rows[:MAX_ALERTS_PER_BRIEF]]


def summarize_alert_gates(brief: dict[str, Any], *, notification_lines: list[str] | None = None) -> dict[str, Any]:
    opportunities = brief.get("opportunities") or []
    gate_counts: dict[str, int] = {}
    quality_counts: dict[str, int] = {}
    blocker_counts: dict[str, int] = {}
    action_counts: dict[str, int] = {}
    readiness_values: list[float] = []
    alert_rows = []

    for row in opportunities:
        gate = safe_text(row.get("alert_gate")).upper() or "UNKNOWN"
        quality = safe_text(row.get("alert_quality") or (row.get("smart_alert") or {}).get("quality")) or "UNKNOWN"
        action = human_trade_action(row)
        gate_counts[gate] = gate_counts.get(gate, 0) + 1
        quality_counts[quality] = quality_counts.get(quality, 0) + 1
        action_counts[action] = action_counts.get(action, 0) + 1
        if safe_text(row.get("ai_action")).upper() == "ALERT":
            alert_rows.append(row)
        readiness = safe_float(row.get("alert_readiness_score"))
        if readiness is not None:
            readiness_values.append(readiness)
        blockers = row.get("alert_blockers") or []
        if isinstance(blockers, str):
            blockers = [blockers]
        for blocker in blockers:
            blocker_text = safe_text(blocker)
            if not blocker_text:
                continue
            blocker_key = blocker_text.split(":", 1)[0].strip() or blocker_text
            blocker_counts[blocker_key] = blocker_counts.get(blocker_key, 0) + 1

    top = opportunities[0] if opportunities else {}
    top_blockers = top.get("alert_blockers") or []
    if isinstance(top_blockers, str):
        top_blockers = [top_blockers]
    notifications_ready = len(notification_lines) if notification_lines is not None else len(build_notification_lines(brief))
    avg_readiness = round(sum(readiness_values) / len(readiness_values), 1) if readiness_values else None
    ready_ratio = round(len(alert_rows) / len(opportunities), 3) if opportunities else 0.0
    top_gate = safe_text(top.get("alert_gate")).upper() if top else ""
    return {
        "total_opportunities": len(opportunities),
        "alert_count": len(alert_rows),
        "watch_count": len(opportunities) - len(alert_rows),
        "notifications_ready": notifications_ready,
        "max_alerts_per_brief": MAX_ALERTS_PER_BRIEF,
        "ready_ratio": ready_ratio,
        "avg_readiness": avg_readiness,
        "gate_counts": dict(sorted(gate_counts.items(), key=lambda item: (-item[1], item[0]))),
        "quality_counts": dict(sorted(quality_counts.items(), key=lambda item: (-item[1], item[0]))),
        "action_counts": dict(sorted(action_counts.items(), key=lambda item: (-item[1], item[0]))),
        "blocker_counts": dict(sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))),
        "blocked_realtime_count": gate_counts.get("BLOCKED_REALTIME_DATA", 0),
        "top_gate": top_gate or "-",
        "top_gate_label": alert_gate_label(top_gate) if top_gate else "-",
        "top_quality": safe_text(top.get("alert_quality")) or "-",
        "top_readiness": safe_float(top.get("alert_readiness_score")),
        "top_blocker": safe_text(top.get("alert_primary_blocker")) or (safe_text(top_blockers[0]) if top_blockers else "-"),
    }


def build_status_snapshot(brief: dict[str, Any], alert_quality_report: dict[str, Any] | None = None) -> dict[str, Any]:
    opportunities = brief.get("opportunities") or []
    top = opportunities[0] if opportunities else {}
    daily_plan = brief.get("daily_opportunity_plan") or {}
    freshness = brief.get("source_freshness") or {}
    realtime_health = brief.get("realtime_health") or {}
    session = brief.get("market_session") or {}
    macro = brief.get("macro_calendar") or {}
    blockers = top.get("alert_blockers") or []
    if isinstance(blockers, str):
        blockers = [blockers]
    notifications = build_notification_lines(brief)
    gate_summary = summarize_alert_gates(brief, notification_lines=notifications)
    alert_quality = dict(alert_quality_report or {}) if isinstance(alert_quality_report, dict) else load_json(ALERT_QUALITY_JSON_PATH, {})
    alert_quality_summary = alert_quality.get("summary") if isinstance(alert_quality.get("summary"), dict) else {}
    alert_quality_entry = alert_quality.get("entry") if isinstance(alert_quality.get("entry"), dict) else {}
    alert_quality_brief_at = safe_text(alert_quality.get("brief_generated_at"))
    brief_generated_at = safe_text(brief.get("generated_at"))
    has_alert_quality_contract = bool(
        alert_quality_summary
        or alert_quality_entry
        or safe_text(alert_quality.get("state"))
        or safe_text(alert_quality.get("diagnostic_label"))
    )
    alert_quality_matches_brief = has_alert_quality_contract and (
        not alert_quality_brief_at or not brief_generated_at or alert_quality_brief_at == brief_generated_at
    )
    if not alert_quality_matches_brief:
        alert_quality_summary = {}
        alert_quality_entry = {}
        alert_quality = {}
    alert_quality_rotation_candidates = (
        alert_quality.get("rotation_candidates")
        if isinstance(alert_quality.get("rotation_candidates"), list)
        else alert_quality_summary.get("rotation_candidates")
    )
    alert_quality_missed_trigger_plan = (
        alert_quality.get("missed_trigger_plan")
        if isinstance(alert_quality.get("missed_trigger_plan"), dict)
        else alert_quality_summary.get("missed_trigger_plan")
        if isinstance(alert_quality_summary.get("missed_trigger_plan"), dict)
        else {}
    )
    alert_quality_confirmation_wait_plan = (
        alert_quality.get("confirmation_wait_plan")
        if isinstance(alert_quality.get("confirmation_wait_plan"), dict)
        else alert_quality_summary.get("confirmation_wait_plan")
        if isinstance(alert_quality_summary.get("confirmation_wait_plan"), dict)
        else {}
    )
    alert_quality_state_value = (
        safe_text(alert_quality.get("state"))
        or safe_text(alert_quality_summary.get("state"))
        or safe_text(alert_quality_entry.get("state"))
        or "-"
    )
    alert_quality_diagnostic_label_value = (
        safe_text(alert_quality.get("diagnostic_label"))
        or safe_text(alert_quality_summary.get("diagnostic_label"))
        or "-"
    )
    alert_quality_diagnostic_severity_value = (
        safe_text(alert_quality.get("diagnostic_severity"))
        or safe_text(alert_quality_summary.get("diagnostic_severity"))
        or "-"
    )
    alert_quality_report_status_value = (
        safe_text(alert_quality.get("report_status"))
        or safe_text(alert_quality.get("status"))
        or safe_text(alert_quality_summary.get("report_status"))
        or safe_text(alert_quality_summary.get("status"))
        or "-"
    )
    alert_quality_status_reason_value = (
        safe_text(alert_quality.get("status_reason"))
        or safe_text(alert_quality.get("report_status_reason"))
        or safe_text(alert_quality_summary.get("status_reason"))
        or safe_text(alert_quality_summary.get("report_status_reason"))
        or "-"
    )
    alert_quality_blocked_markets_value = (
        list(alert_quality.get("blocked_markets") or alert_quality_summary.get("blocked_markets") or [])[:5]
        if isinstance(alert_quality.get("blocked_markets") or alert_quality_summary.get("blocked_markets"), list)
        else []
    )
    alert_quality_blocked_route_markets_value = (
        list(
            alert_quality.get("blocked_route_markets")
            or alert_quality_summary.get("blocked_route_markets")
            or alert_quality_blocked_markets_value
            or []
        )[:5]
        if isinstance(
            alert_quality.get("blocked_route_markets")
            or alert_quality_summary.get("blocked_route_markets")
            or alert_quality_blocked_markets_value,
            list,
        )
        else []
    )
    alert_quality_blocked_route_market_count_value = int(
        alert_quality.get("blocked_route_market_count")
        or alert_quality_summary.get("blocked_route_market_count")
        or len({safe_text(item).lower() for item in alert_quality_blocked_route_markets_value if safe_text(item)})
        or 0
    )
    alert_quality_blocked_opportunity_market_count_value = int(
        alert_quality.get("blocked_opportunity_market_count")
        or alert_quality_summary.get("blocked_opportunity_market_count")
        or alert_quality.get("blocked_market_count")
        or alert_quality_summary.get("blocked_market_count")
        or 0
    )
    alert_quality_chart_blocked_symbols = (
        list(alert_quality.get("chart_contract_blocked_symbols") or alert_quality_summary.get("chart_contract_blocked_symbols") or [])[:5]
        if isinstance(
            alert_quality.get("chart_contract_blocked_symbols")
            or alert_quality_summary.get("chart_contract_blocked_symbols"),
            list,
        )
        else []
    )
    alert_quality_dominant_blocker = (
        alert_quality.get("dominant_blocker")
        if isinstance(alert_quality.get("dominant_blocker"), dict)
        else alert_quality_summary.get("dominant_blocker")
        if isinstance(alert_quality_summary.get("dominant_blocker"), dict)
        else {}
    )
    alert_quality_recurrent_blocker_value = (
        safe_text(alert_quality.get("recurrent_blocker"))
        or safe_text(alert_quality_summary.get("recurrent_blocker"))
        or safe_text(alert_quality_dominant_blocker.get("name"))
        or "-"
    )
    alert_quality_recurrent_blocker_count_value = int(
        alert_quality.get("recurrent_blocker_count")
        or alert_quality_summary.get("recurrent_blocker_count")
        or alert_quality_dominant_blocker.get("count")
        or 0
    )
    alert_quality_persistent_blocker_value = (
        safe_text(alert_quality.get("persistent_blocker"))
        or safe_text(alert_quality_summary.get("persistent_blocker"))
        or "-"
    )
    alert_quality_persistent_blocker_minutes_value = safe_float(
        alert_quality.get("persistent_blocker_minutes")
        if alert_quality.get("persistent_blocker_minutes") is not None
        else alert_quality_summary.get("persistent_blocker_minutes")
    )
    if (
        alert_quality_persistent_blocker_value == "-"
        and alert_quality_persistent_blocker_minutes_value is not None
        and alert_quality_recurrent_blocker_value != "-"
    ):
        alert_quality_persistent_blocker_value = alert_quality_recurrent_blocker_value
    alert_quality_recommended_action_value = (
        safe_text(alert_quality.get("recommended_action"))
        or safe_text(alert_quality_summary.get("recommended_action"))
        or safe_text(alert_quality.get("market_coverage_action"))
        or safe_text(alert_quality_summary.get("market_coverage_action"))
        or safe_text(alert_quality_entry.get("market_coverage_action"))
        or "-"
    )
    alert_quality_market_coverage_action_value = (
        safe_text(alert_quality.get("market_coverage_action"))
        or safe_text(alert_quality_summary.get("market_coverage_action"))
        or safe_text(alert_quality_entry.get("market_coverage_action"))
        or "-"
    )
    alert_quality_stock_allowed_value = (
        alert_quality.get("stock_alerts_allowed")
        if isinstance(alert_quality.get("stock_alerts_allowed"), bool)
        else alert_quality_entry.get("stock_alerts_allowed")
        if isinstance(alert_quality_entry.get("stock_alerts_allowed"), bool)
        else session.get("stock_alerts_allowed", True)
    )
    alert_quality_crypto_allowed_value = (
        alert_quality.get("crypto_alerts_allowed")
        if isinstance(alert_quality.get("crypto_alerts_allowed"), bool)
        else alert_quality_entry.get("crypto_alerts_allowed")
        if isinstance(alert_quality_entry.get("crypto_alerts_allowed"), bool)
        else realtime_health.get("crypto_alerts_allowed", True)
    )
    alert_quality_options_allowed_value = (
        alert_quality.get("options_alerts_allowed")
        if isinstance(alert_quality.get("options_alerts_allowed"), bool)
        else alert_quality_entry.get("options_alerts_allowed")
        if isinstance(alert_quality_entry.get("options_alerts_allowed"), bool)
        else alert_quality_stock_allowed_value
    )
    market_state = alert_quality_state_value if alert_quality_state_value != "-" else (
        "READY" if notifications else "WAITING" if opportunities else "NO_SETUPS"
    )
    if notifications or market_state == "READY":
        system_status = "OK"
    elif market_state in {"BLOCKED_DATA", "BLOCKED_REALTIME", "WAITING", "NO_SETUPS"}:
        system_status = "WARN"
    else:
        system_status = "UNKNOWN"
    alert_quality_blocked_market_set = {str(item).lower() for item in alert_quality_blocked_markets_value}
    if "crypto" in alert_quality_blocked_market_set and (
        "stock" in alert_quality_blocked_market_set or "options" in alert_quality_blocked_market_set
    ):
        safe_mode = "NO_ALERTS_UNTIL_DATA_OK"
    elif any(
        item in {"stock", "options"} for item in alert_quality_blocked_market_set
    ):
        safe_mode = "NO_STOCK_OR_OPTIONS_ALERTS"
    elif market_state in {"BLOCKED_DATA", "BLOCKED_REALTIME"}:
        safe_mode = "NO_ALERTS_UNTIL_DATA_OK"
    elif notifications:
        safe_mode = "ALERTS_ALLOWED"
    elif market_state == "WAITING":
        safe_mode = "WAIT_FOR_CONFIRMATION"
    elif market_state == "NO_SETUPS":
        safe_mode = "NO_SETUPS"
    else:
        safe_mode = "WATCH"
    recommended_action = (
        alert_quality_recommended_action_value
        if alert_quality_recommended_action_value != "-"
        else safe_text(top.get("alert_next_action"))
        or safe_text(top.get("alert_movement"))
        or "-"
    )
    active_route = safe_text(realtime_health.get("active_route"))
    active_route_label = safe_text(realtime_health.get("active_route_label"))
    active_route_detail = safe_text(realtime_health.get("active_route_detail"))
    allowed_markets = (
        realtime_health.get("allowed_markets")
        if isinstance(realtime_health.get("allowed_markets"), list)
        else []
    )
    base_allowed_markets = [safe_text(item).lower() for item in allowed_markets if safe_text(item)]
    if alert_quality_blocked_market_set:
        if not base_allowed_markets:
            base_allowed_markets = ["stock", "crypto", "options"]
        effective_allowed_markets = [
            market for market in base_allowed_markets if market not in alert_quality_blocked_market_set
        ]
        allowed_markets = effective_allowed_markets
        blocked_display = [market for market in ["stock", "crypto", "options"] if market in alert_quality_blocked_market_set]
        if allowed_markets and blocked_display:
            active_route = "PARTIAL_MARKET_ROUTE"
            active_route_label = "Operar solo " + ", ".join(item.upper() for item in allowed_markets)
            active_route_detail = (
                "Operable "
                + ", ".join(item.upper() for item in allowed_markets)
                + "; bloqueado "
                + ", ".join(item.upper() for item in blocked_display)
                + "."
            )
        elif blocked_display:
            active_route = "NO_MARKET_ROUTE"
            active_route_label = "No operar realtime"
            active_route_detail = "Bloqueado " + ", ".join(item.upper() for item in blocked_display) + "."
    effective_allowed_market_set = {safe_text(item).lower() for item in allowed_markets if safe_text(item)}
    stock_alerts_allowed = bool(alert_quality_stock_allowed_value) and "stock" not in alert_quality_blocked_market_set
    crypto_alerts_allowed = bool(alert_quality_crypto_allowed_value) and "crypto" not in alert_quality_blocked_market_set
    options_alerts_allowed = bool(alert_quality_options_allowed_value) and "options" not in alert_quality_blocked_market_set
    if effective_allowed_market_set:
        stock_alerts_allowed = stock_alerts_allowed and "stock" in effective_allowed_market_set
        crypto_alerts_allowed = crypto_alerts_allowed and "crypto" in effective_allowed_market_set
        options_alerts_allowed = options_alerts_allowed and "options" in effective_allowed_market_set
    status_alias = system_status
    state_alias = market_state
    route_alias = active_route_label or active_route or "-"
    label_alias = (
        safe_text(alert_quality.get("label"))
        or (alert_quality_diagnostic_label_value if alert_quality_diagnostic_label_value != "-" else "")
        or safe_text(realtime_health.get("label"))
        or market_state
        or "Roxy status"
    )
    tone_alias = safe_text(alert_quality.get("tone"))
    if tone_alias == "buy" and market_state != "READY":
        tone_alias = ""
    if not tone_alias:
        severity_value = alert_quality_diagnostic_severity_value.upper()
        if market_state == "READY":
            tone_alias = "buy"
        elif severity_value in {"ATTENTION", "HIGH", "FAIL", "ERROR"}:
            tone_alias = "avoid"
        elif severity_value in {"WATCH", "MEDIUM", "WARN"}:
            tone_alias = "watch"
        elif system_status == "OK":
            tone_alias = "buy"
        elif system_status == "WARN":
            tone_alias = "watch"
        else:
            tone_alias = "neutral"

    def missed_trigger_value(alias: str, plan_key: str, default: Any = None) -> Any:
        value = alert_quality.get(alias)
        if value is not None:
            return value
        return alert_quality_missed_trigger_plan.get(plan_key, default)

    def missed_trigger_text(alias: str, plan_key: str) -> str:
        return safe_text(missed_trigger_value(alias, plan_key)) or "-"

    def missed_trigger_bool(alias: str, plan_key: str) -> bool:
        value = missed_trigger_value(alias, plan_key, False)
        return bool(value) if isinstance(value, bool) else safe_text(value).lower() == "true"

    def missed_trigger_int(alias: str, plan_key: str) -> int:
        try:
            return int(missed_trigger_value(alias, plan_key, 0) or 0)
        except (TypeError, ValueError):
            return 0

    def missed_trigger_float(alias: str, plan_key: str) -> float | None:
        value = missed_trigger_value(alias, plan_key)
        return safe_float(value) if value is not None else None

    def missed_trigger_list(alias: str, plan_key: str) -> list[Any]:
        value = missed_trigger_value(alias, plan_key, [])
        return list(value) if isinstance(value, list) else []

    def confirmation_wait_value(alias: str, plan_key: str, default: Any = None) -> Any:
        value = alert_quality.get(alias)
        if value is not None:
            return value
        return alert_quality_confirmation_wait_plan.get(plan_key, default)

    def confirmation_wait_text(alias: str, plan_key: str) -> str:
        return safe_text(confirmation_wait_value(alias, plan_key)) or "-"

    def confirmation_wait_bool(alias: str, plan_key: str) -> bool:
        value = confirmation_wait_value(alias, plan_key, False)
        return bool(value) if isinstance(value, bool) else safe_text(value).lower() == "true"

    def confirmation_wait_int(alias: str, plan_key: str) -> int:
        try:
            return int(confirmation_wait_value(alias, plan_key, 0) or 0)
        except (TypeError, ValueError):
            return 0

    def confirmation_wait_float(alias: str, plan_key: str) -> float | None:
        value = confirmation_wait_value(alias, plan_key)
        return safe_float(value) if value is not None else None

    def confirmation_wait_list(alias: str, plan_key: str) -> list[Any]:
        value = confirmation_wait_value(alias, plan_key, [])
        return list(value) if isinstance(value, list) else []

    def confirmation_wait_review_pressure() -> str:
        value = confirmation_wait_text("confirmation_wait_plan_review_pressure", "review_pressure")
        if value != "-":
            return value
        status = safe_text(
            confirmation_wait_value("confirmation_wait_plan_review_status", "review_status")
        ).upper()
        active = bool(confirmation_wait_value("confirmation_wait_plan_active", "active", False))
        due = bool(confirmation_wait_value("confirmation_wait_plan_review_due", "review_due", False))
        try:
            overdue_cycles = int(
                confirmation_wait_value("confirmation_wait_plan_review_overdue_cycles", "review_overdue_cycles", 0)
                or 0
            )
        except (TypeError, ValueError):
            overdue_cycles = 0
        if status == "OVERDUE" or overdue_cycles:
            return "OVERDUE"
        if status == "DUE" or due:
            return "DUE"
        if status == "PENDING" and active:
            return "PENDING"
        return "CLEAR"

    top_symbol_value = safe_text(top.get("symbol")).upper() if top else "-"
    rotation_guard_active_value = missed_trigger_bool(
        "missed_trigger_plan_rotation_guard_active",
        "rotation_guard_active",
    )
    rotation_next_symbol_value = missed_trigger_text(
        "missed_trigger_plan_rotation_next_symbol",
        "rotation_next_symbol",
    ).upper()
    rotation_blocked_symbol_value = missed_trigger_text(
        "missed_trigger_plan_rotation_blocked_symbol",
        "rotation_blocked_symbol",
    ).upper()
    rotation_handoff_confirmed_value = missed_trigger_bool(
        "missed_trigger_plan_rotation_handoff_confirmed",
        "rotation_handoff_confirmed",
    )
    rotation_handoff_confirmed_action_value = missed_trigger_text(
        "missed_trigger_plan_handoff_confirmed_action",
        "handoff_confirmed_action",
    )
    discard_guard_active_value = missed_trigger_bool(
        "missed_trigger_plan_discard_guard_active",
        "discard_guard_active",
    )
    discard_symbol_value = missed_trigger_text(
        "missed_trigger_plan_discard_symbol",
        "discard_symbol",
    ).upper()
    discard_action_value = missed_trigger_text(
        "missed_trigger_plan_decision_action",
        "decision_action",
    )
    confirmation_rotation_guard_active_value = confirmation_wait_bool(
        "confirmation_wait_plan_rotation_guard_active",
        "rotation_guard_active",
    )
    confirmation_rotation_next_symbol_value = confirmation_wait_text(
        "confirmation_wait_plan_rotation_next_symbol",
        "rotation_next_symbol",
    ).upper()
    confirmation_rotation_blocked_symbol_value = confirmation_wait_text(
        "confirmation_wait_plan_rotation_blocked_symbol",
        "rotation_blocked_symbol",
    ).upper()
    confirmation_decision_action_value = confirmation_wait_text(
        "confirmation_wait_plan_decision_action",
        "decision_action",
    )
    operational_focus_symbol = top_symbol_value
    operational_focus_source = "TOP_SETUP" if top_symbol_value != "-" else "-"
    operational_focus_reason = safe_text(top.get("alert_next_action") or top.get("alert_movement") or "")
    operational_focus_overrides_top = False
    if rotation_guard_active_value and rotation_next_symbol_value not in {"", "-"}:
        operational_focus_symbol = rotation_next_symbol_value
        operational_focus_source = "ALERT_QUALITY_ROTATION"
        operational_focus_overrides_top = rotation_next_symbol_value != top_symbol_value
        operational_focus_reason = (
            rotation_handoff_confirmed_action_value
            if rotation_handoff_confirmed_value and rotation_handoff_confirmed_action_value not in {"", "-"}
            else
            f"Rotacion activa: {rotation_blocked_symbol_value} vencido; siguiente foco {rotation_next_symbol_value}."
            if rotation_blocked_symbol_value not in {"", "-"}
            else f"Rotacion activa: siguiente foco {rotation_next_symbol_value}."
        )
    elif discard_guard_active_value and discard_symbol_value not in {"", "-"}:
        operational_focus_symbol = discard_symbol_value
        operational_focus_source = "ALERT_QUALITY_DISCARD"
        operational_focus_overrides_top = discard_symbol_value != top_symbol_value
        operational_focus_reason = (
            discard_action_value
            if discard_action_value not in {"", "-"}
            else f"Descartar o pausar candidato stale {discard_symbol_value}."
        )
    elif confirmation_rotation_guard_active_value and confirmation_rotation_next_symbol_value not in {"", "-"}:
        operational_focus_symbol = confirmation_rotation_next_symbol_value
        operational_focus_source = "ALERT_QUALITY_CONFIRMATION_ROTATION"
        operational_focus_overrides_top = confirmation_rotation_next_symbol_value != top_symbol_value
        operational_focus_reason = (
            confirmation_decision_action_value
            if confirmation_decision_action_value not in {"", "-"}
            else (
                "Confirmacion vencida: "
                f"{confirmation_rotation_blocked_symbol_value} sigue bloqueado; "
                f"siguiente foco {confirmation_rotation_next_symbol_value}."
            )
            if confirmation_rotation_blocked_symbol_value not in {"", "-"}
            else f"Confirmacion vencida: siguiente foco {confirmation_rotation_next_symbol_value}."
        )

    def alert_quality_handoff_snapshot(
        *,
        requested: bool,
        expected_symbol: str,
        expected_source: str,
    ) -> dict[str, str]:
        expected_key = safe_text(expected_symbol).upper()
        focus_key = safe_text(operational_focus_symbol).upper()
        source_key = safe_text(operational_focus_source).upper()
        if not requested:
            return {
                "status": "NOT_REQUESTED",
                "expected_symbol": "",
                "focus_symbol": "",
                "source": "",
            }
        elif expected_key in {"", "-"}:
            status = "MISSING_TARGET"
        elif focus_key != expected_key:
            status = "MISMATCH"
        elif source_key != expected_source:
            status = "PENDING"
        else:
            status = "CONFIRMED"
        return {
            "status": status,
            "expected_symbol": expected_key if expected_key else "",
            "focus_symbol": focus_key if focus_key else "",
            "source": source_key if source_key else "",
        }

    rotation_handoff = alert_quality_handoff_snapshot(
        requested=bool(rotation_guard_active_value),
        expected_symbol=rotation_next_symbol_value,
        expected_source="ALERT_QUALITY_ROTATION",
    )
    discard_handoff = alert_quality_handoff_snapshot(
        requested=bool(discard_guard_active_value),
        expected_symbol=discard_symbol_value,
        expected_source="ALERT_QUALITY_DISCARD",
    )
    confirmation_rotation_handoff = alert_quality_handoff_snapshot(
        requested=bool(confirmation_rotation_guard_active_value),
        expected_symbol=confirmation_rotation_next_symbol_value,
        expected_source="ALERT_QUALITY_CONFIRMATION_ROTATION",
    )

    def first_present_float(*values: Any) -> float | None:
        for value in values:
            if value is not None:
                parsed = safe_float(value)
                if parsed is not None:
                    return parsed
        return None

    alert_quality_avg_readiness_value = first_present_float(
        alert_quality.get("avg_readiness"),
        alert_quality_summary.get("avg_readiness"),
    )
    alert_quality_latest_readiness_value = first_present_float(
        alert_quality.get("latest_readiness"),
        alert_quality_summary.get("latest_readiness"),
    )
    alert_quality_readiness_delta_value = first_present_float(
        alert_quality.get("readiness_delta"),
        alert_quality_summary.get("readiness_delta"),
    )
    alert_quality_readiness_trend_value = first_present_float(
        alert_quality.get("readiness_trend"),
        alert_quality_readiness_delta_value,
        alert_quality_summary.get("readiness_trend"),
        alert_quality_summary.get("readiness_delta"),
    )
    daily_plan_top_symbol_value = safe_text(daily_plan.get("top_symbol")).upper() or "-"
    daily_plan_matches_top = (
        top_symbol_value not in {"", "-"}
        and daily_plan_top_symbol_value not in {"", "-"}
        and daily_plan_top_symbol_value == top_symbol_value
    )
    operational_focus_active = operational_focus_symbol not in {"", "-"} and (
        operational_focus_overrides_top
        or operational_focus_symbol != top_symbol_value
        or operational_focus_source
        in {"ALERT_QUALITY_DISCARD", "ALERT_QUALITY_ROTATION", "ALERT_QUALITY_CONFIRMATION_ROTATION"}
    )
    daily_plan_rows = daily_plan.get("rows") if isinstance(daily_plan.get("rows"), list) else []
    daily_plan_focus_row = {}
    for item in daily_plan_rows:
        if not isinstance(item, dict):
            continue
        if safe_text(item.get("symbol")).upper() == operational_focus_symbol:
            daily_plan_focus_row = item
            break
    daily_plan_focus_symbol_value = safe_text(daily_plan_focus_row.get("symbol")).upper() or "-"
    daily_plan_focus_stage_value = safe_text(daily_plan_focus_row.get("stage")).upper() or "-"
    daily_plan_focus_probability_value = safe_float(daily_plan_focus_row.get("probability"))
    daily_plan_supports_focus = (
        operational_focus_active
        and daily_plan_focus_symbol_value == operational_focus_symbol
        and daily_plan_focus_stage_value in {"OPERAR_AHORA", "PROXIMA_ENTRADA", "VIGILAR"}
    )
    daily_plan_matches_focus = (
        operational_focus_active
        and daily_plan_top_symbol_value not in {"", "-"}
        and (daily_plan_top_symbol_value == operational_focus_symbol or daily_plan_supports_focus)
    )
    if daily_plan_top_symbol_value in {"", "-"}:
        daily_plan_alignment = "NO_DAILY_PLAN"
    elif operational_focus_active:
        daily_plan_alignment = (
            "FOCUS_ALIGNED"
            if daily_plan_top_symbol_value == operational_focus_symbol
            else "FOCUS_SUPPORTED"
            if daily_plan_supports_focus
            else "FOCUS_MISMATCH"
        )
    elif daily_plan_matches_top:
        daily_plan_alignment = "TOP_ALIGNED"
    else:
        daily_plan_alignment = "TOP_MISMATCH"

    return {
        "generated_at": brief.get("generated_at"),
        "mode": brief.get("mode", "AI_WATCH_24H"),
        "contract_version": 2,
        "status": status_alias,
        "state": state_alias,
        "route": route_alias,
        "label": label_alias,
        "tone": tone_alias,
        "system_status": system_status,
        "market_state": market_state,
        "recommended_action": recommended_action,
        "operational_focus_symbol": operational_focus_symbol,
        "operational_focus_source": operational_focus_source,
        "operational_focus_reason": operational_focus_reason or "-",
        "operational_focus_overrides_top": operational_focus_overrides_top,
        "alert_quality_rotation_handoff_status": rotation_handoff["status"],
        "alert_quality_rotation_handoff_expected_symbol": rotation_handoff["expected_symbol"],
        "alert_quality_rotation_handoff_focus_symbol": rotation_handoff["focus_symbol"],
        "alert_quality_rotation_handoff_source": rotation_handoff["source"],
        "alert_quality_missed_trigger_plan_handoff_confirmed_action": (
            rotation_handoff_confirmed_action_value
            if rotation_handoff_confirmed_action_value not in {"", "-"}
            else "-"
        ),
        "alert_quality_discard_handoff_status": discard_handoff["status"],
        "alert_quality_discard_handoff_expected_symbol": discard_handoff["expected_symbol"],
        "alert_quality_discard_handoff_focus_symbol": discard_handoff["focus_symbol"],
        "alert_quality_discard_handoff_source": discard_handoff["source"],
        "alert_quality_confirmation_rotation_handoff_status": confirmation_rotation_handoff["status"],
        "alert_quality_confirmation_rotation_handoff_expected_symbol": (
            confirmation_rotation_handoff["expected_symbol"]
        ),
        "alert_quality_confirmation_rotation_handoff_focus_symbol": confirmation_rotation_handoff["focus_symbol"],
        "alert_quality_confirmation_rotation_handoff_source": confirmation_rotation_handoff["source"],
        "safe_mode": safe_mode,
        "active_route": active_route,
        "active_route_label": active_route_label,
        "active_route_detail": active_route_detail,
        "allowed_markets": allowed_markets,
        "blocked_markets": alert_quality_blocked_markets_value,
        "blocked_route_markets": alert_quality_blocked_route_markets_value,
        "blocked_route_market_count": alert_quality_blocked_route_market_count_value,
        "blocked_opportunity_market_count": alert_quality_blocked_opportunity_market_count_value,
        "alert_count": int(brief.get("alert_count", 0) or 0),
        "watch_count": int(brief.get("watch_count", 0) or 0),
        "memory_symbols": int(brief.get("memory_symbols", 0) or 0),
        "notifications_ready": len(notifications),
        "data_label": safe_text(freshness.get("label")) or "-",
        "data_detail": safe_text(freshness.get("detail")) or "-",
        "alerts_allowed": bool(freshness.get("alerts_allowed", True)),
        "health_label": safe_text(realtime_health.get("label")) or "-",
        "health_detail": safe_text(realtime_health.get("detail")) or "-",
        "health_alerts_allowed": bool(realtime_health.get("alerts_allowed", True)),
        "stock_session": safe_text(session.get("stock_session")) or "-",
        "crypto_session": safe_text(session.get("crypto_session")) or "-",
        "stock_alerts_allowed": stock_alerts_allowed,
        "crypto_alerts_allowed": crypto_alerts_allowed,
        "options_alerts_allowed": options_alerts_allowed,
        "session_stock_alerts_allowed": bool(session.get("stock_alerts_allowed", True)),
        "macro_label": safe_text(macro.get("label")) or "-",
        "macro_detail": safe_text(macro.get("detail")) or "-",
        "macro_active": bool(macro.get("active")),
        "top_symbol": top_symbol_value,
        "top_market": safe_text(top.get("market")) or "-",
        "top_action": safe_text(top.get("ai_action")) or "-",
        "top_signal": safe_text(top.get("signal")) or "-",
        "top_gate": safe_text(top.get("alert_gate")) or "-",
        "top_gate_label": alert_gate_label(top.get("alert_gate")) if top else "-",
        "top_quality": safe_text(top.get("alert_quality")) or "-",
        "top_readiness": safe_float(top.get("alert_readiness_score")),
        "top_next_action": safe_text(top.get("alert_next_action")) or safe_text(top.get("alert_movement")) or "-",
        "top_human_action": human_trade_action(top) if top else "-",
        "top_human_reason": human_alert_reason(top) if top else "-",
        "top_blockers": [safe_text(item) for item in blockers[:5] if safe_text(item)],
        "alert_gate_summary": gate_summary,
        "alert_quality_state": alert_quality_state_value,
        "alert_quality_diagnostic_label": alert_quality_diagnostic_label_value,
        "alert_quality_diagnostic_severity": alert_quality_diagnostic_severity_value,
        "alert_quality_report_status": alert_quality_report_status_value,
        "alert_quality_status_reason": alert_quality_status_reason_value,
        "alert_quality_blocker_category": safe_text(alert_quality.get("blocker_category"))
        or safe_text(alert_quality_summary.get("blocker_category"))
        or "-",
        "alert_quality_false_negative_risk": safe_text(alert_quality.get("false_negative_risk"))
        or safe_text(alert_quality_summary.get("false_negative_risk"))
        or "-",
        "alert_quality_avg_readiness": alert_quality_avg_readiness_value,
        "alert_quality_latest_readiness": alert_quality_latest_readiness_value,
        "alert_quality_readiness_delta": alert_quality_readiness_delta_value,
        "alert_quality_readiness_trend": alert_quality_readiness_trend_value,
        "alert_quality_silence_mode": safe_text(alert_quality.get("silence_mode"))
        or safe_text(alert_quality_summary.get("silence_mode"))
        or "-",
        "alert_quality_silence_reason": safe_text(alert_quality.get("silence_reason"))
        or safe_text(alert_quality_summary.get("silence_reason"))
        or "-",
        "alert_quality_missed_opportunity_watch": bool(
            alert_quality.get("missed_opportunity_watch")
            if isinstance(alert_quality.get("missed_opportunity_watch"), bool)
            else alert_quality_summary.get("missed_opportunity_watch", False)
        ),
        "alert_quality_missed_opportunity_risk": safe_text(alert_quality.get("missed_opportunity_risk"))
        or safe_text(alert_quality_summary.get("missed_opportunity_risk"))
        or "-",
        "alert_quality_missed_opportunity_reason": safe_text(alert_quality.get("missed_opportunity_reason"))
        or safe_text(alert_quality_summary.get("missed_opportunity_reason"))
        or "-",
        "alert_quality_missed_opportunity_action": safe_text(alert_quality.get("missed_opportunity_action"))
        or safe_text(alert_quality_summary.get("missed_opportunity_action"))
        or "-",
        "alert_quality_missed_trigger_plan_active": bool(
            alert_quality.get("missed_trigger_plan_active")
            if isinstance(alert_quality.get("missed_trigger_plan_active"), bool)
            else alert_quality_missed_trigger_plan.get("active", False)
        ),
        "alert_quality_missed_trigger_plan_symbol": safe_text(alert_quality.get("missed_trigger_plan_symbol"))
        or safe_text(alert_quality_missed_trigger_plan.get("primary_symbol"))
        or "-",
        "alert_quality_missed_trigger_plan_readiness": (
            alert_quality.get("missed_trigger_plan_readiness")
            if alert_quality.get("missed_trigger_plan_readiness") is not None
            else alert_quality_missed_trigger_plan.get("primary_readiness")
        ),
        "alert_quality_missed_trigger_plan_risk": safe_text(alert_quality.get("missed_trigger_plan_risk"))
        or safe_text(alert_quality_missed_trigger_plan.get("risk"))
        or "-",
        "alert_quality_missed_trigger_plan_review_due": bool(
            alert_quality.get("missed_trigger_plan_review_due")
            if isinstance(alert_quality.get("missed_trigger_plan_review_due"), bool)
            else alert_quality_missed_trigger_plan.get("review_due", False)
        ),
        "alert_quality_missed_trigger_plan_review_status": safe_text(
            alert_quality.get("missed_trigger_plan_review_status")
        )
        or safe_text(alert_quality_missed_trigger_plan.get("review_status"))
        or "-",
        "alert_quality_missed_trigger_plan_review_overdue_cycles": int(
            alert_quality.get("missed_trigger_plan_review_overdue_cycles")
            or alert_quality_missed_trigger_plan.get("review_overdue_cycles")
            or 0
        ),
        "alert_quality_missed_trigger_plan_review_cycles_remaining": int(
            alert_quality.get("missed_trigger_plan_review_cycles_remaining")
            or alert_quality_missed_trigger_plan.get("review_cycles_remaining")
            or 0
        ),
        "alert_quality_missed_trigger_plan_review_progress": (
            alert_quality.get("missed_trigger_plan_review_progress")
            if alert_quality.get("missed_trigger_plan_review_progress") is not None
            else alert_quality_missed_trigger_plan.get("review_progress")
        ),
        "alert_quality_missed_trigger_plan_review_cycle_minutes": (
            alert_quality.get("missed_trigger_plan_review_cycle_minutes")
            if alert_quality.get("missed_trigger_plan_review_cycle_minutes") is not None
            else alert_quality_missed_trigger_plan.get("review_cycle_minutes")
        ),
        "alert_quality_missed_trigger_plan_review_eta_minutes": (
            alert_quality.get("missed_trigger_plan_review_eta_minutes")
            if alert_quality.get("missed_trigger_plan_review_eta_minutes") is not None
            else alert_quality_missed_trigger_plan.get("review_eta_minutes")
        ),
        "alert_quality_missed_trigger_plan_review_overdue_minutes": (
            alert_quality.get("missed_trigger_plan_review_overdue_minutes")
            if alert_quality.get("missed_trigger_plan_review_overdue_minutes") is not None
            else alert_quality_missed_trigger_plan.get("review_overdue_minutes")
        ),
        "alert_quality_missed_trigger_plan_review_pressure": missed_trigger_text(
            "missed_trigger_plan_review_pressure",
            "review_pressure",
        ),
        "alert_quality_missed_trigger_plan_stale_candidate": missed_trigger_bool(
            "missed_trigger_plan_stale_candidate",
            "stale_candidate",
        ),
        "alert_quality_missed_trigger_plan_auto_review_decision": missed_trigger_text(
            "missed_trigger_plan_auto_review_decision",
            "auto_review_decision",
        ),
        "alert_quality_missed_trigger_plan_decision_reason": missed_trigger_text(
            "missed_trigger_plan_decision_reason",
            "decision_reason",
        ),
        "alert_quality_missed_trigger_plan_decision_action": missed_trigger_text(
            "missed_trigger_plan_decision_action",
            "decision_action",
        ),
        "alert_quality_missed_trigger_plan_readiness_delta": missed_trigger_float(
            "missed_trigger_plan_readiness_delta",
            "readiness_delta",
        ),
        "alert_quality_missed_trigger_plan_rotation_guard_active": missed_trigger_bool(
            "missed_trigger_plan_rotation_guard_active",
            "rotation_guard_active",
        ),
        "alert_quality_missed_trigger_plan_rotation_blocked_symbol": missed_trigger_text(
            "missed_trigger_plan_rotation_blocked_symbol",
            "rotation_blocked_symbol",
        ),
        "alert_quality_missed_trigger_plan_rotation_alternates": missed_trigger_list(
            "missed_trigger_plan_rotation_alternates",
            "rotation_alternates",
        ),
        "alert_quality_missed_trigger_plan_rotation_blocked_by_daily_plan": missed_trigger_list(
            "missed_trigger_plan_rotation_blocked_by_daily_plan",
            "rotation_blocked_by_daily_plan",
        ),
        "alert_quality_missed_trigger_plan_rotation_daily_blocked_count": missed_trigger_int(
            "missed_trigger_plan_rotation_daily_blocked_count",
            "rotation_daily_blocked_count",
        ),
        "alert_quality_missed_trigger_plan_rotation_next_symbol": missed_trigger_text(
            "missed_trigger_plan_rotation_next_symbol",
            "rotation_next_symbol",
        ),
        "alert_quality_missed_trigger_plan_rotation_cooldown_cycles": missed_trigger_int(
            "missed_trigger_plan_rotation_cooldown_cycles",
            "rotation_cooldown_cycles",
        ),
        "alert_quality_missed_trigger_plan_rotation_cooldown_eta_minutes": missed_trigger_float(
            "missed_trigger_plan_rotation_cooldown_eta_minutes",
            "rotation_cooldown_eta_minutes",
        ),
        "alert_quality_missed_trigger_plan_rotation_resume_condition": missed_trigger_text(
            "missed_trigger_plan_rotation_resume_condition",
            "rotation_resume_condition",
        ),
        "alert_quality_missed_trigger_plan_discard_guard_active": missed_trigger_bool(
            "missed_trigger_plan_discard_guard_active",
            "discard_guard_active",
        ),
        "alert_quality_missed_trigger_plan_discard_symbol": missed_trigger_text(
            "missed_trigger_plan_discard_symbol",
            "discard_symbol",
        ),
        "alert_quality_missed_trigger_plan_discard_reason": missed_trigger_text(
            "missed_trigger_plan_discard_reason",
            "discard_reason",
        ),
        "alert_quality_missed_trigger_plan_discard_cooldown_cycles": missed_trigger_int(
            "missed_trigger_plan_discard_cooldown_cycles",
            "discard_cooldown_cycles",
        ),
        "alert_quality_missed_trigger_plan_discard_cooldown_eta_minutes": missed_trigger_float(
            "missed_trigger_plan_discard_cooldown_eta_minutes",
            "discard_cooldown_eta_minutes",
        ),
        "alert_quality_missed_trigger_plan_discard_resume_condition": missed_trigger_text(
            "missed_trigger_plan_discard_resume_condition",
            "discard_resume_condition",
        ),
        "alert_quality_missed_trigger_plan_severity": safe_text(alert_quality.get("missed_trigger_plan_severity"))
        or safe_text(alert_quality_missed_trigger_plan.get("severity"))
        or "-",
        "alert_quality_missed_trigger_plan_max_watch_cycles": int(
            alert_quality.get("missed_trigger_plan_max_watch_cycles")
            or alert_quality_missed_trigger_plan.get("max_watch_cycles")
            or 0
        ),
        "alert_quality_missed_trigger_plan_review_action": safe_text(
            alert_quality.get("missed_trigger_plan_review_action")
        )
        or safe_text(alert_quality_missed_trigger_plan.get("review_action"))
        or "-",
        "alert_quality_missed_trigger_plan_exit": safe_text(alert_quality.get("missed_trigger_plan_exit"))
        or safe_text(alert_quality_missed_trigger_plan.get("exit_condition"))
        or "-",
        "alert_quality_confirmation_wait_plan_active": bool(
            alert_quality.get("confirmation_wait_plan_active")
            if isinstance(alert_quality.get("confirmation_wait_plan_active"), bool)
            else alert_quality_confirmation_wait_plan.get("active", False)
        ),
        "alert_quality_confirmation_wait_plan_symbol": safe_text(alert_quality.get("confirmation_wait_plan_symbol"))
        or safe_text(alert_quality_confirmation_wait_plan.get("primary_symbol"))
        or "-",
        "alert_quality_confirmation_wait_plan_readiness": (
            alert_quality.get("confirmation_wait_plan_readiness")
            if alert_quality.get("confirmation_wait_plan_readiness") is not None
            else alert_quality_confirmation_wait_plan.get("primary_readiness")
        ),
        "alert_quality_confirmation_wait_plan_risk": safe_text(alert_quality.get("confirmation_wait_plan_risk"))
        or safe_text(alert_quality_confirmation_wait_plan.get("risk"))
        or "-",
        "alert_quality_confirmation_wait_plan_review_due": bool(
            alert_quality.get("confirmation_wait_plan_review_due")
            if isinstance(alert_quality.get("confirmation_wait_plan_review_due"), bool)
            else alert_quality_confirmation_wait_plan.get("review_due", False)
        ),
        "alert_quality_confirmation_wait_plan_review_status": safe_text(
            alert_quality.get("confirmation_wait_plan_review_status")
        )
        or safe_text(alert_quality_confirmation_wait_plan.get("review_status"))
        or "-",
        "alert_quality_confirmation_wait_plan_review_pressure": confirmation_wait_review_pressure(),
        "alert_quality_confirmation_wait_plan_review_overdue_cycles": int(
            alert_quality.get("confirmation_wait_plan_review_overdue_cycles")
            or alert_quality_confirmation_wait_plan.get("review_overdue_cycles")
            or 0
        ),
        "alert_quality_confirmation_wait_plan_review_cycles_remaining": int(
            alert_quality.get("confirmation_wait_plan_review_cycles_remaining")
            or alert_quality_confirmation_wait_plan.get("review_cycles_remaining")
            or 0
        ),
        "alert_quality_confirmation_wait_plan_review_progress": (
            alert_quality.get("confirmation_wait_plan_review_progress")
            if alert_quality.get("confirmation_wait_plan_review_progress") is not None
            else alert_quality_confirmation_wait_plan.get("review_progress")
        ),
        "alert_quality_confirmation_wait_plan_review_cycle_minutes": (
            alert_quality.get("confirmation_wait_plan_review_cycle_minutes")
            if alert_quality.get("confirmation_wait_plan_review_cycle_minutes") is not None
            else alert_quality_confirmation_wait_plan.get("review_cycle_minutes")
        ),
        "alert_quality_confirmation_wait_plan_review_eta_minutes": (
            alert_quality.get("confirmation_wait_plan_review_eta_minutes")
            if alert_quality.get("confirmation_wait_plan_review_eta_minutes") is not None
            else alert_quality_confirmation_wait_plan.get("review_eta_minutes")
        ),
        "alert_quality_confirmation_wait_plan_review_overdue_minutes": (
            alert_quality.get("confirmation_wait_plan_review_overdue_minutes")
            if alert_quality.get("confirmation_wait_plan_review_overdue_minutes") is not None
            else alert_quality_confirmation_wait_plan.get("review_overdue_minutes")
        ),
        "alert_quality_confirmation_wait_plan_severity": safe_text(
            alert_quality.get("confirmation_wait_plan_severity")
        )
        or safe_text(alert_quality_confirmation_wait_plan.get("severity"))
        or "-",
        "alert_quality_confirmation_wait_plan_decision_action": confirmation_wait_text(
            "confirmation_wait_plan_decision_action",
            "decision_action",
        ),
        "alert_quality_confirmation_wait_plan_rotation_guard_active": confirmation_rotation_guard_active_value,
        "alert_quality_confirmation_wait_plan_rotation_blocked_symbol": confirmation_wait_text(
            "confirmation_wait_plan_rotation_blocked_symbol",
            "rotation_blocked_symbol",
        ),
        "alert_quality_confirmation_wait_plan_rotation_alternates": confirmation_wait_list(
            "confirmation_wait_plan_rotation_alternates",
            "rotation_alternates",
        ),
        "alert_quality_confirmation_wait_plan_rotation_blocked_by_daily_plan": confirmation_wait_list(
            "confirmation_wait_plan_rotation_blocked_by_daily_plan",
            "rotation_blocked_by_daily_plan",
        ),
        "alert_quality_confirmation_wait_plan_rotation_daily_blocked_count": confirmation_wait_int(
            "confirmation_wait_plan_rotation_daily_blocked_count",
            "rotation_daily_blocked_count",
        ),
        "alert_quality_confirmation_wait_plan_rotation_next_symbol": confirmation_wait_text(
            "confirmation_wait_plan_rotation_next_symbol",
            "rotation_next_symbol",
        ),
        "alert_quality_confirmation_wait_plan_rotation_cooldown_cycles": confirmation_wait_int(
            "confirmation_wait_plan_rotation_cooldown_cycles",
            "rotation_cooldown_cycles",
        ),
        "alert_quality_confirmation_wait_plan_rotation_cooldown_eta_minutes": confirmation_wait_float(
            "confirmation_wait_plan_rotation_cooldown_eta_minutes",
            "rotation_cooldown_eta_minutes",
        ),
        "alert_quality_confirmation_wait_plan_rotation_resume_condition": confirmation_wait_text(
            "confirmation_wait_plan_rotation_resume_condition",
            "rotation_resume_condition",
        ),
        "alert_quality_confirmation_wait_plan_max_watch_cycles": int(
            alert_quality.get("confirmation_wait_plan_max_watch_cycles")
            or alert_quality_confirmation_wait_plan.get("max_watch_cycles")
            or 0
        ),
        "alert_quality_confirmation_wait_plan_review_action": safe_text(
            alert_quality.get("confirmation_wait_plan_review_action")
        )
        or safe_text(alert_quality_confirmation_wait_plan.get("review_action"))
        or "-",
        "alert_quality_confirmation_wait_plan_exit": safe_text(alert_quality.get("confirmation_wait_plan_exit"))
        or safe_text(alert_quality_confirmation_wait_plan.get("exit_condition"))
        or "-",
        "alert_quality_blocked_markets": alert_quality_blocked_markets_value,
        "alert_quality_blocked_route_markets": alert_quality_blocked_route_markets_value,
        "alert_quality_blocked_route_market_count": alert_quality_blocked_route_market_count_value,
        "alert_quality_blocked_opportunity_market_count": alert_quality_blocked_opportunity_market_count_value,
        "alert_quality_recommended_action": alert_quality_recommended_action_value,
        "alert_quality_market_coverage_action": alert_quality_market_coverage_action_value,
        "alert_quality_chart_contract_label": safe_text(alert_quality.get("chart_contract_label"))
        or safe_text(alert_quality_summary.get("chart_contract_label"))
        or "-",
        "alert_quality_chart_contract_action": safe_text(alert_quality.get("chart_contract_action"))
        or safe_text(alert_quality_summary.get("chart_contract_action"))
        or "-",
        "alert_quality_chart_contract_operable_count": int(
            alert_quality.get("chart_contract_operable_count")
            or alert_quality_summary.get("chart_contract_operable_count")
            or 0
        ),
        "alert_quality_chart_contract_blocked_count": int(
            alert_quality.get("chart_contract_blocked_count")
            or alert_quality_summary.get("chart_contract_blocked_count")
            or 0
        ),
        "alert_quality_chart_contract_missing_count": int(
            alert_quality.get("chart_contract_missing_count")
            or alert_quality_summary.get("chart_contract_missing_count")
            or 0
        ),
        "alert_quality_chart_contract_blocked_symbols": alert_quality_chart_blocked_symbols,
        "alert_quality_rotation_candidates": list(alert_quality_rotation_candidates or [])[:5]
        if isinstance(alert_quality_rotation_candidates, list)
        else [],
        "alert_quality_waiting_streak": int(alert_quality_summary.get("waiting_streak") or 0),
        "alert_quality_recurrent_blocker": alert_quality_recurrent_blocker_value,
        "alert_quality_recurrent_blocker_count": alert_quality_recurrent_blocker_count_value,
        "alert_quality_persistent_blocker": alert_quality_persistent_blocker_value,
        "alert_quality_persistent_blocker_minutes": alert_quality_persistent_blocker_minutes_value,
        "alert_quality_brief_generated_at": alert_quality_brief_at or "-",
        "daily_plan_mode": safe_text(daily_plan.get("mode")) or "-",
        "daily_plan_operar_ahora": int(daily_plan.get("operar_ahora", 0) or 0),
        "daily_plan_proxima_entrada": int(daily_plan.get("proxima_entrada", 0) or 0),
        "daily_plan_vigilar": int(daily_plan.get("vigilar", 0) or 0),
        "daily_plan_top_symbol": daily_plan_top_symbol_value,
        "daily_plan_top_stage": safe_text(daily_plan.get("top_stage")) or "-",
        "daily_plan_top_probability": safe_float(daily_plan.get("top_probability")),
        "daily_plan_focus_symbol": daily_plan_focus_symbol_value,
        "daily_plan_focus_stage": daily_plan_focus_stage_value,
        "daily_plan_focus_probability": daily_plan_focus_probability_value,
        "daily_plan_supports_focus": daily_plan_supports_focus,
        "daily_plan_matches_top": daily_plan_matches_top,
        "daily_plan_matches_focus": daily_plan_matches_focus,
        "daily_plan_alignment": daily_plan_alignment,
        "learning_plan_count": len(brief.get("learning_plan") or []),
        "experiment_count": len(brief.get("experiment_registry") or []),
    }


def _journal_date(generated_at: Any) -> str:
    text = safe_text(generated_at)
    if len(text) >= 10:
        return text[:10]
    return now_iso()[:10]


def _journal_text_list(value: Any, *, limit: int = 5) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return safe_text(value)
    return " | ".join(safe_text(item) for item in value[:limit] if safe_text(item))


def build_learning_journal_row(brief: dict[str, Any]) -> dict[str, Any]:
    opportunities = brief.get("opportunities") or []
    top = opportunities[0] if opportunities else {}
    daily_plan = brief.get("daily_opportunity_plan") or {}
    learning_profiles = brief.get("learning_profiles") or []
    profile = learning_profiles[0] if learning_profiles else {}
    learning_plan = brief.get("learning_plan") or []
    plan_item = learning_plan[0] if learning_plan else {}
    experiments = brief.get("experiment_registry") or []
    top_blockers = top.get("alert_blockers") or []
    return {
        "generated_at": safe_text(brief.get("generated_at")) or now_iso(),
        "date": _journal_date(brief.get("generated_at")),
        "alert_count": int(brief.get("alert_count", 0) or 0),
        "watch_count": int(brief.get("watch_count", 0) or 0),
        "memory_symbols": int(brief.get("memory_symbols", 0) or 0),
        "top_symbol": safe_text(top.get("symbol")).upper() if top else "-",
        "top_market": safe_text(top.get("market")) or "-",
        "top_action": safe_text(top.get("ai_action")) or safe_text(top.get("signal")) or "-",
        "top_signal": safe_text(top.get("signal")) or "-",
        "top_strategy": safe_text(top.get("strategy_family")) or strategy_family_for_row(top) if top else "-",
        "top_gate": safe_text(top.get("alert_gate")) or "-",
        "top_gate_label": alert_gate_label(top.get("alert_gate")) if top else "-",
        "top_quality": safe_text(top.get("alert_quality")) or "-",
        "top_readiness": safe_float(top.get("alert_readiness_score")),
        "top_next_action": safe_text(top.get("alert_next_action")) or safe_text(top.get("alert_movement")) or "-",
        "top_human_action": human_trade_action(top) if top else "-",
        "top_human_reason": human_alert_reason(top) if top else "-",
        "top_blockers": _journal_text_list(top_blockers),
        "learning_bias": safe_text(top.get("learning_bias")) or safe_text(profile.get("bias")) or "-",
        "learning_lesson": safe_text(profile.get("lesson")) or safe_text(top.get("explanation")) or "-",
        "learning_recommendation": safe_text(profile.get("recommendation")) or "-",
        "next_experiment": safe_text(plan_item.get("proposed_rule")) or safe_text(plan_item.get("activation_rule")) or "-",
        "next_experiment_strategy": safe_text(plan_item.get("strategy_family")) or "-",
        "learning_plan_count": len(learning_plan),
        "experiment_count": len(experiments),
        "daily_operar_ahora": int(daily_plan.get("operar_ahora", 0) or 0),
        "daily_proxima_entrada": int(daily_plan.get("proxima_entrada", 0) or 0),
        "daily_top_symbol": safe_text(daily_plan.get("top_symbol")) or "-",
        "daily_top_stage": safe_text(daily_plan.get("top_stage")) or "-",
        "daily_top_probability": safe_float(daily_plan.get("top_probability")),
    }


def _learning_journal_fingerprint(row: dict[str, Any]) -> str:
    fields = [
        "date",
        "alert_count",
        "watch_count",
        "top_symbol",
        "top_action",
        "top_gate",
        "top_quality",
        "top_readiness",
        "learning_bias",
        "learning_plan_count",
        "experiment_count",
    ]
    return "|".join(safe_text(row.get(field)) for field in fields)


def compact_learning_journal_frame(frame: pd.DataFrame, *, max_rows: int = MAX_LEARNING_JOURNAL) -> pd.DataFrame:
    if frame.empty:
        return frame
    compacted = frame.copy()
    compacted["_roxy_row_order"] = range(len(compacted))
    if "fingerprint" in compacted.columns:
        fingerprints = compacted["fingerprint"].map(safe_text)
        keep_first = ~fingerprints.duplicated(keep="first")
        keep_last = ~fingerprints.duplicated(keep="last")
        compacted = compacted[keep_first | keep_last].copy()
    compacted = compacted.sort_values("_roxy_row_order").drop(columns=["_roxy_row_order"])
    if max_rows > 0:
        compacted = compacted.tail(max_rows)
    return compacted.reset_index(drop=True)


def append_learning_journal(
    brief: dict[str, Any],
    path: str | Path | None = None,
    *,
    max_rows: int = MAX_LEARNING_JOURNAL,
) -> dict[str, Any]:
    row = build_learning_journal_row(brief)
    row["fingerprint"] = _learning_journal_fingerprint(row)
    journal_path = Path(path or LEARNING_JOURNAL_PATH)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    with exclusive_file_lock(journal_path):
        if journal_path.exists() and journal_path.stat().st_size > 0:
            existing = pd.read_csv(journal_path)
        else:
            existing = pd.DataFrame()

        if not existing.empty and "fingerprint" in existing.columns:
            latest_fingerprint = safe_text(existing.iloc[-1].get("fingerprint"))
            if latest_fingerprint == row["fingerprint"]:
                compacted = compact_learning_journal_frame(existing, max_rows=max_rows)
                if len(compacted) != len(existing):
                    atomic_write_csv(compacted, journal_path)
                return row

        row_frame = pd.DataFrame([row])
        if existing.empty:
            updated = row_frame
        else:
            columns = list(dict.fromkeys([*existing.columns, *row_frame.columns]))
            records = existing.reindex(columns=columns).to_dict(orient="records")
            records.append({column: row.get(column, pd.NA) for column in columns})
            updated = pd.DataFrame.from_records(records, columns=columns)
        updated = compact_learning_journal_frame(updated, max_rows=max_rows)
        atomic_write_csv(updated, journal_path)
        return row


def write_status_snapshot(brief: dict[str, Any], alert_quality_report: dict[str, Any] | None = None) -> dict[str, Any]:
    status = build_status_snapshot(brief, alert_quality_report=alert_quality_report)
    write_json(STATUS_JSON_PATH, status)
    lines = [
        "ROXY STATUS",
        f"Generated: {status['generated_at']}",
        f"Mode: {status['mode']}",
        f"Alerts ready: {status['notifications_ready']} | Alerts: {status['alert_count']} | Watch: {status['watch_count']}",
        f"Data: {status['data_label']} | {status['data_detail']}",
        f"Health: {status['health_label']} | {status['health_detail']}",
        f"Session: stocks {status['stock_session']} | crypto {status['crypto_session']}",
        f"Macro: {status['macro_label']} | {status['macro_detail']}",
        f"Top: {status['top_market']} {status['top_symbol']} | {status['top_human_action']} | {status['top_gate_label']} | quality {status['top_quality']}",
        f"Next: {status['top_next_action']}",
        f"Why: {status['top_human_reason']}",
        (
            "Daily plan: "
            f"operar {status['daily_plan_operar_ahora']} | "
            f"proximas {status['daily_plan_proxima_entrada']} | "
            f"vigilar {status['daily_plan_vigilar']} | "
            f"top {status['daily_plan_top_symbol']} {status['daily_plan_top_stage']} "
            f"{status['daily_plan_top_probability'] if status['daily_plan_top_probability'] is not None else '-'}%"
        ),
    ]
    if status["top_readiness"] is not None:
        lines.append(f"Readiness: {status['top_readiness']:.1f}%")
    if status.get("operational_focus_overrides_top"):
        lines.append(
            "Operational focus: "
            f"{status.get('operational_focus_symbol', '-')} | "
            f"{status.get('operational_focus_source', '-')} | "
            f"{status.get('operational_focus_reason', '-')}"
        )
    if status.get("active_route_label") not in {"", "-"}:
        route_detail = safe_text(status.get("active_route_detail")) or "-"
        lines.append(f"Route: {status['active_route_label']} | {route_detail}")
    blocked_route = status.get("blocked_route_markets") if isinstance(status.get("blocked_route_markets"), list) else []
    if blocked_route:
        blocked_count = int(status.get("blocked_route_market_count") or len(blocked_route))
        opportunity_count = int(status.get("blocked_opportunity_market_count") or 0)
        lines.append(
            "Blocked route markets: "
            f"{', '.join(safe_text(item).upper() for item in blocked_route)} "
            f"| route {blocked_count} | opportunities {opportunity_count}"
        )
    if status["top_blockers"]:
        lines.append("Blockers: " + " | ".join(status["top_blockers"]))
    if status.get("alert_quality_recommended_action") not in {"", "-"}:
        lines.append(f"Action: {status['alert_quality_recommended_action']}")
    if status.get("alert_quality_diagnostic_label") not in {"", "-"}:
        lines.append(
            "Alert quality: "
            f"{status['alert_quality_diagnostic_label']} | "
            f"{status.get('alert_quality_blocker_category', '-')} | "
            f"risk {status.get('alert_quality_false_negative_risk', '-')}"
        )
    if status.get("alert_quality_silence_mode") not in {"", "-"}:
        lines.append(f"Silence mode: {status['alert_quality_silence_mode']}")
    if status.get("alert_quality_silence_reason") not in {"", "-"}:
        lines.append(f"Silence: {status['alert_quality_silence_reason']}")
    if status.get("alert_quality_missed_opportunity_watch"):
        lines.append(
            "Missed-opportunity watch: "
            f"{status.get('alert_quality_missed_opportunity_risk', '-')} | "
            f"{status.get('alert_quality_missed_opportunity_action', '-')}"
        )
    if status.get("alert_quality_chart_contract_label") not in {"", "-"}:
        lines.append(
            "Chart contract: "
            f"{status['alert_quality_chart_contract_label']} | "
            f"live {status.get('alert_quality_chart_contract_operable_count', 0)} | "
            f"blocked {status.get('alert_quality_chart_contract_blocked_count', 0)}"
        )
    rotation = status.get("alert_quality_rotation_candidates") or []
    if rotation:
        lines.append("Rotation: " + " | ".join(safe_text(item) for item in rotation[:5]))
    gate_summary = status.get("alert_gate_summary") or {}
    if gate_summary:
        lines.append(
            "Gate summary: "
            f"ready {gate_summary.get('notifications_ready', 0)}/{gate_summary.get('total_opportunities', 0)} | "
            f"avg readiness {gate_summary.get('avg_readiness', '-')}"
        )
        gate_counts = gate_summary.get("gate_counts") or {}
        if gate_counts:
            lines.append(
                "Gates: "
                + " | ".join(f"{alert_gate_label(gate)}={count}" for gate, count in list(gate_counts.items())[:5])
            )
    lines.append(f"Lab: {status['learning_plan_count']} plan item(s) | {status['experiment_count']} experiment(s)")
    atomic_write_text("\n".join(lines), STATUS_TEXT_PATH)
    return status


def apply_alert_quality_lifecycle(
    brief: dict[str, Any],
    alert_quality_report: dict[str, Any] | None,
    *,
    prior_archived: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Keep discarded setups off active surfaces until a fresh ALERT_READY trigger."""
    report = alert_quality_report if isinstance(alert_quality_report, dict) else {}
    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    observed_at = observed_at.astimezone(timezone.utc)
    opportunities = [row for row in brief.get("opportunities", []) if isinstance(row, dict)]
    ready_symbols = {
        safe_text(row.get("symbol")).upper()
        for row in opportunities
        if safe_text(row.get("ai_action")).upper() == "ALERT"
        and safe_text(row.get("alert_gate")).upper() == "ALERT_READY"
    }

    events_by_symbol: dict[str, dict[str, Any]] = {}
    for item in prior_archived or []:
        if not isinstance(item, dict):
            continue
        prior_symbol = safe_text(item.get("symbol")).upper()
        if not prior_symbol or prior_symbol in ready_symbols:
            continue
        retained = dict(item)
        retained.setdefault("reactivation_policy", "FRESH_ALERT_READY")
        events_by_symbol[prior_symbol] = retained

    if report.get("missed_trigger_plan_discard_guard_active"):
        symbol = safe_text(report.get("missed_trigger_plan_discard_symbol")).upper()
        discarded = [row for row in opportunities if safe_text(row.get("symbol")).upper() == symbol]
        if symbol and symbol not in ready_symbols and discarded:
            reason = (
                safe_text(report.get("missed_trigger_plan_discard_reason"))
                or "Candidato stale sin confirmacion 15m."
            )
            resume = safe_text(report.get("missed_trigger_plan_discard_resume_condition"))
            archived_at = safe_text(report.get("generated_at")) or observed_at.isoformat()
            cooldown_minutes = max(
                safe_float(report.get("missed_trigger_plan_discard_cooldown_eta_minutes")) or 15.0,
                1.0,
            )
            cooldown_until = (observed_at + timedelta(minutes=cooldown_minutes)).isoformat()
            row = discarded[0]
            events_by_symbol[symbol] = {
                **row,
                "symbol": symbol,
                "market": safe_text(row.get("market")) or ("crypto" if "/" in symbol else "stock"),
                "status": "Invalidada",
                "archived_at": archived_at,
                "cooldown_until": cooldown_until,
                "reactivation_policy": "FRESH_ALERT_READY",
                "archive_reason": reason,
                "resume_condition": resume,
                "lifecycle_source": "ALERT_QUALITY_DISCARD",
            }

    events = list(events_by_symbol.values())
    archived_symbols = set(events_by_symbol)
    remaining = [row for row in opportunities if safe_text(row.get("symbol")).upper() not in archived_symbols]
    brief["opportunities"] = remaining
    brief["archived_opportunities"] = events
    if len(remaining) != len(opportunities):
        brief["alert_count"] = sum(safe_text(row.get("ai_action")).upper() == "ALERT" for row in remaining)
        brief["watch_count"] = len(remaining) - int(brief["alert_count"])
        brief["daily_opportunity_plan"] = build_daily_opportunity_plan(remaining)
    return events


def write_brief(brief: dict[str, Any]) -> dict[str, Any] | None:
    alert_quality_report = None
    try:
        from alert_quality import write_alert_quality_report

        alert_quality_dir = BRIEF_JSON_PATH.parent
        alert_quality_report = write_alert_quality_report(
            {key: value for key, value in brief.items() if key != "memory"},
            report_path=alert_quality_dir / "alert_quality.json",
            history_path=alert_quality_dir / "alert_quality_history.jsonl",
        )
    except Exception:
        pass
    lifecycle_path = BRIEF_JSON_PATH.parent / OPPORTUNITY_LIFECYCLE_JSON_PATH.name
    lifecycle_payload = load_json(lifecycle_path, {})
    prior_archived = (
        lifecycle_payload.get("archived_opportunities", []) if isinstance(lifecycle_payload, dict) else []
    )
    archived_events = apply_alert_quality_lifecycle(
        brief,
        alert_quality_report,
        prior_archived=prior_archived if isinstance(prior_archived, list) else [],
    )
    write_json(
        lifecycle_path,
        {
            "contract": "roxy-opportunity-lifecycle/1.0.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "archived_opportunities": archived_events,
        },
    )
    write_json(BRIEF_JSON_PATH, {key: value for key, value in brief.items() if key != "memory"})
    if brief.get("daily_opportunity_plan"):
        write_json(DAILY_PLAN_JSON_PATH, brief["daily_opportunity_plan"])
    save_memory(brief.get("memory") or load_memory())
    lines = [
        "ROXY AI WATCH",
        f"Generated: {brief.get('generated_at')}",
        f"Alerts: {brief.get('alert_count')} | Watch: {brief.get('watch_count')} | Memory symbols: {brief.get('memory_symbols')}",
        "",
    ]
    freshness = brief.get("source_freshness") or {}
    if freshness:
        lines.append(
            f"Datos: {safe_text(freshness.get('label'))} | {safe_text(freshness.get('detail'))}"
        )
        if not freshness.get("alerts_allowed", True):
            lines.append("Alertas pausadas: refrescar live/confluencia antes de operar.")
        lines.append("")
    realtime_health = brief.get("realtime_health") or {}
    if realtime_health:
        lines.append(
            f"Health realtime: {safe_text(realtime_health.get('label'))} | {safe_text(realtime_health.get('detail'))}"
        )
        if not realtime_health.get("alerts_allowed", True):
            lines.append("Alertas pausadas: resolver health realtime antes de notificar.")
        lines.append("")
    session = brief.get("market_session") or {}
    if session:
        lines.append(
            "Sesion de mercado: "
            f"stocks {safe_text(session.get('stock_session'))} | crypto {safe_text(session.get('crypto_session'))} | "
            f"{safe_text(session.get('stock_detail'))}"
        )
        if not session.get("stock_alerts_allowed", True):
            lines.append("Alertas de acciones/opciones pausadas: mercado cerrado; crypto sigue en vigilancia 24h.")
        lines.append("")
    macro = brief.get("macro_calendar") or {}
    if macro:
        lines.append(
            f"Macro: {safe_text(macro.get('label'))} | {safe_text(macro.get('detail'))}"
        )
        if macro.get("active"):
            lines.append("Roxy baja agresividad: exige score alto, 1.5R, volumen fuerte y 2h/4h sin bloqueo.")
        lines.append("")
    notifications = build_notification_lines(brief)
    if notifications:
        lines.extend(notifications)
    else:
        lines.append("No hay alertas accionables. Roxy espera confirmacion de confluencia.")
        watched = brief.get("opportunities") or []
        if watched:
            lines.extend(["", "Setups en observacion:"])
            for row in watched[:3]:
                blockers = row.get("alert_blockers") or []
                if isinstance(blockers, str):
                    blockers = [blockers]
                blocker_text = "; ".join(str(item) for item in blockers[:3]) if blockers else "Ready"
                lines.append(
                    "- "
                    f"{safe_text(row.get('symbol')).upper()} | {alert_gate_label(row.get('alert_gate')) or 'WATCH'} "
                    f"| calidad {safe_text(row.get('alert_quality')) or safe_text((row.get('smart_alert') or {}).get('quality')) or '-'} "
                    f"| readiness {safe_float(row.get('alert_readiness_score')) or 0:.1f}% "
                    f"| confianza {alert_confidence_text(row)} "
                    f"| proximo: {safe_text(row.get('alert_next_action')) or safe_text(row.get('alert_movement'))} "
                    f"| razon: {human_alert_reason(row)} "
                    f"| falta: {blocker_text}"
                )
    daily_plan = brief.get("daily_opportunity_plan") or {}
    if daily_plan:
        lines.extend(["", "Plan operativo 24h:"])
        lines.extend(daily_plan_text_lines(daily_plan, limit=5))
    learning = brief.get("learning_profiles") or []
    if learning:
        lines.extend(["", "Notas de aprendizaje:"])
        for profile in learning[:3]:
            lines.append(f"- {profile.get('lesson')}")
    learning_plan = brief.get("learning_plan") or []
    if learning_plan:
        lines.extend(["", "Plan autonomo de aprendizaje:"])
        for item in learning_plan[:3]:
            lines.append(
                "- "
                f"{safe_text(item.get('strategy_family'))}: {learning_action_label(item.get('action'))} "
                f"| {safety_mode_label(item.get('safety_mode'))} "
                f"| {safe_text(item.get('proposed_rule'))}"
            )
    experiments = brief.get("experiment_registry") or []
    if experiments:
        lines.extend(["", "Experimentos de Roxy Lab:"])
        for item in experiments[:3]:
            measured = int(item.get("measured_count", 0) or 0)
            hit_2_rate = safe_float(item.get("hit_2_rate")) or 0.0
            stop_rate = safe_float(item.get("stop_rate")) or 0.0
            lines.append(
                "- "
                f"{safe_text(item.get('strategy_family'))}: {experiment_status_label(item.get('status'))} "
                f"| seen {int(item.get('seen_count', 0) or 0)} "
                f"| measured {measured} "
                f"| hit2 {hit_2_rate * 100:.0f}% "
                f"| stop {stop_rate * 100:.0f}% "
                f"| {safe_text(item.get('proposed_rule'))}"
            )
    atomic_write_text("\n".join(lines), BRIEF_TEXT_PATH)
    write_status_snapshot(brief, alert_quality_report=alert_quality_report)
    append_learning_journal(brief)
    return alert_quality_report
