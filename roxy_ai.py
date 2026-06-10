from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from smart_alerts import evaluate_smart_alert
from trade_brief import CORE_STRATEGIES, strategy_family_from_setup


ALERTS_DIR = Path("alerts")
MEMORY_PATH = ALERTS_DIR / "roxy_ai_memory.json"
BRIEF_JSON_PATH = ALERTS_DIR / "roxy_ai_brief.json"
BRIEF_TEXT_PATH = ALERTS_DIR / "roxy_ai_brief.txt"
STATUS_JSON_PATH = ALERTS_DIR / "roxy_status.json"
STATUS_TEXT_PATH = ALERTS_DIR / "roxy_status.txt"
REALTIME_HEALTH_PATH = ALERTS_DIR / "roxy_realtime_check.json"
LEARNING_JOURNAL_PATH = ALERTS_DIR / "roxy_learning_journal.csv"
MAX_ALERTS_PER_BRIEF = 3
MAX_SIGNAL_JOURNAL = 200
MAX_EXPERIMENT_REGISTRY = 100
MAX_LEARNING_JOURNAL = 500
DEFAULT_ACCOUNT_EQUITY = float(os.getenv("ROXY_DEFAULT_ACCOUNT_EQUITY", "500") or "500")
DEFAULT_RISK_PER_TRADE_PCT = float(os.getenv("ROXY_RISK_PER_TRADE_PCT", "0.01") or "0.01")

ALERT_GATE_LABELS = {
    "ALERT_READY": "Listo para operar manual",
    "WAIT_15M_ENTRY": "Esperar entrada 15m",
    "WAIT_1H_CONFIRM": "Esperar confirmacion 1h",
    "WAIT_HTF_CONFIRM": "Esperar confirmacion 2h/4h",
    "WAIT_VOLUME": "Esperar volumen",
    "NO_TRADE_STRUCTURE": "No operar por estructura",
    "WAIT_FULL_CHECKLIST": "Esperar checklist completo",
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
        first = warning[0] if warning else {}
        name = safe_text(first.get("name")) or "realtime"
        detail = safe_text(first.get("detail")) or "Health realtime con advertencias."
        return {
            "status": "WARN",
            "label": "Health revisar",
            "detail": f"{name}: {detail}",
            "age_minutes": age,
            "alerts_allowed": True,
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


def write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, sort_keys=True))


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

    actions.sort(
        key=lambda item: (
            item.get("action") == "PROMOTE_IN_RANKING",
            safe_float(item.get("evidence_score")) or 0.0,
            item.get("source") == "smart_gate",
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
    adjusted.sort(key=lambda value: (value.get("ai_action") == "ALERT", value.get("ai_score", 0)), reverse=True)
    return adjusted


def score_opportunity(row: dict[str, Any]) -> int:
    score = safe_float(row.get("confluence_score")) or 0.0
    risk = safe_float(row.get("risk_pct"))
    target_pct = safe_float(row.get("recommended_target_pct")) or 0.0
    rel_vol = safe_float(row.get("relative_volume_15m"))
    trend_score = safe_float(row.get("trend_score")) or 0.0

    points = score
    if risk is not None:
        if risk <= 0.015:
            points += 10
        elif risk <= 0.025:
            points += 5
        elif risk > 0.035:
            points -= 20
    if target_pct >= 0.10:
        points += 8
    elif target_pct >= 0.05:
        points += 5
    elif target_pct >= 0.02:
        points += 2
    if rel_vol is not None and rel_vol >= 1.1:
        points += 5
    if trend_score >= 75:
        points += 4
    return int(max(0, min(100, round(points))))


def extract_opportunities(confluence_df: pd.DataFrame, *, limit: int = 8) -> list[dict[str, Any]]:
    if confluence_df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for _, item in confluence_df.iterrows():
        row = item.to_dict()
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
    return rows[:limit]


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
    max_gain_pct = max(0.0, (max_price - entry) / entry)
    max_drawdown_pct = max(0.0, (entry - min_price) / entry)
    row["last_price"] = current
    row["max_price"] = max_price
    row["min_price"] = min_price
    row["max_gain_pct"] = round(max_gain_pct, 6)
    row["max_drawdown_pct"] = round(max_drawdown_pct, 6)
    row["progress_to_2pct"] = round(min(1.0, max_gain_pct / 0.02), 4)
    if stop is not None and 0 < stop < entry:
        stop_distance_pct = (entry - stop) / entry
        row["progress_to_stop"] = round(min(1.0, max_drawdown_pct / stop_distance_pct), 4)
    else:
        row["progress_to_stop"] = None
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
        if stop is not None and current <= stop:
            alert["status"] = "STOP"
            alert["closed_at"] = now_iso()
        elif current >= entry * 1.10:
            milestones.update({"2%", "5%", "10%"})
            alert["status"] = "HIT_10PCT"
            alert["closed_at"] = now_iso()
        elif current >= entry * 1.05:
            milestones.update({"2%", "5%"})
            alert["status"] = "HIT_5PCT"
        elif current >= entry * 1.02:
            milestones.add("2%")
            alert["status"] = "HIT_2PCT"
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
        if stop is not None and current <= stop:
            signal["status"] = "STOP"
            signal["closed_at"] = now_iso()
        elif current >= entry * 1.10:
            milestones.update({"2%", "5%", "10%"})
            signal["status"] = "HIT_10PCT"
            signal["closed_at"] = now_iso()
        elif current >= entry * 1.05:
            milestones.update({"2%", "5%"})
            signal["status"] = "HIT_5PCT"
        elif current >= entry * 1.02:
            milestones.add("2%")
            signal["status"] = "HIT_2PCT"
        else:
            signal.setdefault("status", "WATCHING")
        signal["milestones"] = sorted(milestones)
    return memory


def summarize_options(options_df: pd.DataFrame, symbol: str) -> dict[str, Any]:
    if options_df.empty or "symbol" not in options_df.columns:
        return {}
    rows = options_df[options_df["symbol"].astype(str).str.upper().eq(symbol.upper())].copy()
    if rows.empty:
        return {}
    if "option_score" in rows.columns:
        rows["option_score"] = pd.to_numeric(rows["option_score"], errors="coerce")
        rows = rows.sort_values("option_score", ascending=False)
    first = rows.iloc[0].to_dict()
    return {
        "contract": first.get("contractSymbol"),
        "decision": first.get("option_decision"),
        "score": first.get("option_score"),
        "expiry": first.get("expiry"),
        "dte": first.get("dte"),
        "strike": first.get("strike"),
        "spread_pct": first.get("spread_pct"),
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

    alert_rows = [row for row in opportunities if row.get("ai_action") == "ALERT"]
    watch_rows = [row for row in opportunities if row.get("ai_action") != "ALERT"]
    brief = {
        "generated_at": now_iso(),
        "mode": "AI_WATCH_24H",
        "alert_count": len(alert_rows),
        "watch_count": len(watch_rows),
        "opportunities": opportunities,
        "lessons": memory.get("lessons", []),
        "learning_profiles": learning_profiles,
        "research_queue": research_queue,
        "gate_research": gate_research,
        "strategy_lab": strategy_lab,
        "learning_plan": learning_plan,
        "experiment_registry": experiment_registry,
        "memory_symbols": len(memory.get("symbols", {})),
        "signal_journal_count": len(memory.get("signal_journal", [])),
        "scan_rows": int(len(scan_df)) if scan_df is not None and not scan_df.empty else 0,
        "memory": memory,
    }
    brief["alert_gate_summary"] = summarize_alert_gates(brief)
    return brief


def apply_global_alert_context(brief: dict[str, Any], memory: dict[str, Any] | None = None) -> dict[str, Any]:
    source_freshness = brief.get("source_freshness") or {}
    realtime_health = brief.get("realtime_health") or {}
    if not source_freshness and not realtime_health:
        return brief

    memory = memory or (brief.get("memory") if isinstance(brief.get("memory"), dict) else {}) or {}
    opportunities = []
    for row in brief.get("opportunities") or []:
        item = dict(row)
        if source_freshness:
            item["source_freshness"] = source_freshness
        if realtime_health:
            item["realtime_health"] = realtime_health
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

    opportunities.sort(key=lambda value: (value.get("ai_action") == "ALERT", value.get("ai_score", 0)), reverse=True)
    brief["opportunities"] = opportunities
    alert_rows = [row for row in opportunities if row.get("ai_action") == "ALERT"]
    brief["alert_count"] = len(alert_rows)
    brief["watch_count"] = len(opportunities) - len(alert_rows)
    brief["alert_gate_summary"] = summarize_alert_gates(brief)
    return brief


def format_alert_line(row: dict[str, Any]) -> str:
    target = safe_float(row.get("recommended_target_pct"))
    risk = safe_float(row.get("risk_pct"))
    entry = safe_float(row.get("entry"))
    stop = safe_float(row.get("stop"))
    option = row.get("option") or {}
    option_text = ""
    if option.get("contract"):
        option_text = f" | option {option.get('contract')} score {option.get('score')}"
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


def build_status_snapshot(brief: dict[str, Any]) -> dict[str, Any]:
    opportunities = brief.get("opportunities") or []
    top = opportunities[0] if opportunities else {}
    freshness = brief.get("source_freshness") or {}
    realtime_health = brief.get("realtime_health") or {}
    session = brief.get("market_session") or {}
    blockers = top.get("alert_blockers") or []
    if isinstance(blockers, str):
        blockers = [blockers]
    notifications = build_notification_lines(brief)
    gate_summary = summarize_alert_gates(brief, notification_lines=notifications)
    return {
        "generated_at": brief.get("generated_at"),
        "mode": brief.get("mode", "AI_WATCH_24H"),
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
        "stock_alerts_allowed": bool(session.get("stock_alerts_allowed", True)),
        "top_symbol": safe_text(top.get("symbol")).upper() if top else "-",
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
    if journal_path.exists():
        try:
            existing = pd.read_csv(journal_path)
        except Exception:
            existing = pd.DataFrame()
    else:
        existing = pd.DataFrame()

    if not existing.empty and "fingerprint" in existing.columns:
        latest_fingerprint = safe_text(existing.iloc[-1].get("fingerprint"))
        if latest_fingerprint == row["fingerprint"]:
            return row

    updated = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
    if max_rows > 0:
        updated = updated.tail(max_rows)
    updated.to_csv(journal_path, index=False)
    return row


def write_status_snapshot(brief: dict[str, Any]) -> dict[str, Any]:
    status = build_status_snapshot(brief)
    write_json(STATUS_JSON_PATH, status)
    lines = [
        "ROXY STATUS",
        f"Generated: {status['generated_at']}",
        f"Mode: {status['mode']}",
        f"Alerts ready: {status['notifications_ready']} | Alerts: {status['alert_count']} | Watch: {status['watch_count']}",
        f"Data: {status['data_label']} | {status['data_detail']}",
        f"Health: {status['health_label']} | {status['health_detail']}",
        f"Session: stocks {status['stock_session']} | crypto {status['crypto_session']}",
        f"Top: {status['top_market']} {status['top_symbol']} | {status['top_human_action']} | {status['top_gate_label']} | quality {status['top_quality']}",
        f"Next: {status['top_next_action']}",
        f"Why: {status['top_human_reason']}",
    ]
    if status["top_readiness"] is not None:
        lines.append(f"Readiness: {status['top_readiness']:.1f}%")
    if status["top_blockers"]:
        lines.append("Blockers: " + " | ".join(status["top_blockers"]))
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
    STATUS_TEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_TEXT_PATH.write_text("\n".join(lines))
    return status


def write_brief(brief: dict[str, Any]) -> None:
    write_json(BRIEF_JSON_PATH, {key: value for key, value in brief.items() if key != "memory"})
    try:
        from alert_quality import write_alert_quality_report

        alert_quality_dir = BRIEF_JSON_PATH.parent
        write_alert_quality_report(
            {key: value for key, value in brief.items() if key != "memory"},
            report_path=alert_quality_dir / "alert_quality.json",
            history_path=alert_quality_dir / "alert_quality_history.jsonl",
        )
    except Exception:
        pass
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
    BRIEF_TEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BRIEF_TEXT_PATH.write_text("\n".join(lines))
    write_status_snapshot(brief)
    append_learning_journal(brief)
