from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from roxy_knowledge_brain import enrich_opportunity_with_knowledge
from smart_alerts import evaluate_smart_alert
from trade_brief import reward_risk_ratio, safe_bool, safe_float, safe_text

try:
    from tools.external_market_sources import apply_external_market_context
except Exception:  # pragma: no cover - keeps the decision engine usable without optional connectors.
    apply_external_market_context = None  # type: ignore[assignment]


UP_SIGNALS = {"BUY", "WATCH", "PRE-BUY", "CALL", "LONG"}
DOWN_SIGNALS = {"SELL", "SHORT", "PUT"}
CRITICAL_GATES = {
    "BLOCKED_REALTIME_DATA",
    "BLOCKED_BY_MEMORY",
    "NO_TRADE_STRUCTURE",
}
OPERATE_GATES = {"ALERT_READY"}
WAIT_GATES = {
    "WAIT_15M_ENTRY",
    "WAIT_1H_CONFIRM",
    "WAIT_HTF_CONFIRM",
    "WAIT_VOLUME",
    "WAIT_FULL_CHECKLIST",
    "WAIT_MACRO_CONFIRMATION",
}


def _first_present(row: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", "-"):
            return value
    return None


def _metric(row: dict[str, Any], *keys: str) -> float | None:
    return safe_float(_first_present(row, keys))


def _direction(row: dict[str, Any]) -> str:
    signal = safe_text(row.get("signal")).upper()
    decision = safe_text(row.get("trade_decision") or row.get("decision")).upper()
    setup = safe_text(row.get("setup") or row.get("trigger_setup") or row.get("strategy_family")).upper()
    option_side = safe_text(row.get("option_side") or row.get("contract_type")).upper()
    if signal in DOWN_SIGNALS or "PUT" in decision or option_side == "PUT" or "SHORT" in setup:
        return "ABAJO"
    if signal in UP_SIGNALS or "CALL" in decision or option_side == "CALL":
        return "ARRIBA"
    return "SIN_DIRECCION"


def _target_price(row: dict[str, Any], entry: float | None) -> float | None:
    target = _metric(
        row,
        "recommended_target_price",
        "target",
        "target_1",
        "target_2",
        "target_2pct_price",
        "tp1",
    )
    if target is not None:
        return target
    target_pct = _metric(row, "recommended_target_pct", "target_pct")
    if entry is not None and target_pct is not None:
        return round(entry * (1 + target_pct), 6)
    return None


def _live_contract_ok(row: dict[str, Any]) -> tuple[bool, str]:
    if safe_bool(row.get("data_stale") or row.get("stale_data")):
        return False, safe_text(row.get("stale_reason") or "datos vencidos")
    for key in ("realtime_health", "source_freshness"):
        value = row.get(key)
        if isinstance(value, dict):
            allowed = value.get("alerts_allowed")
            if allowed is False:
                return False, safe_text(value.get("detail") or value.get("label") or key)
    smart = row.get("smart_alert") if isinstance(row.get("smart_alert"), dict) else {}
    gate = safe_text(row.get("alert_gate") or smart.get("gate")).upper()
    if gate == "BLOCKED_REALTIME_DATA":
        return False, safe_text(row.get("alert_primary_blocker") or smart.get("primary_blocker") or "realtime bloqueado")
    return True, "datos realtime habilitados para evaluar"


def _missing_operational_fields(row: dict[str, Any], *, entry: float | None, stop: float | None, target: float | None) -> list[str]:
    missing: list[str] = []
    if entry is None:
        missing.append("entrada")
    if stop is None:
        missing.append("stop")
    if target is None:
        missing.append("target")
    risk_pct = _metric(row, "risk_pct")
    if risk_pct is None:
        missing.append("riesgo")
    return missing


def _condition_summary(row: dict[str, Any]) -> list[dict[str, Any]]:
    smart = row.get("smart_alert") if isinstance(row.get("smart_alert"), dict) else {}
    checks = smart.get("checks") if isinstance(smart.get("checks"), list) else []
    if checks:
        return [
            {
                "label": safe_text(item.get("rule") or item.get("label")),
                "passed": bool(item.get("passed")),
                "detail": safe_text(item.get("detail")),
            }
            for item in checks[:10]
            if isinstance(item, dict)
        ]
    knowledge = row.get("knowledge_enrichment") if isinstance(row.get("knowledge_enrichment"), dict) else {}
    checklist = knowledge.get("confirmation_checklist") if isinstance(knowledge.get("confirmation_checklist"), list) else []
    return [
        {
            "label": safe_text(item.get("label")),
            "passed": safe_text(item.get("status")).lower() == "ok",
            "detail": safe_text(item.get("detail")),
        }
        for item in checklist[:10]
        if isinstance(item, dict)
    ]


def _decision_label(status: str) -> str:
    return {
        "OPERATE_NOW": "OPERAR AHORA",
        "WAIT_CONFIRMATION": "ESPERAR CONFIRMACION",
        "NO_TRADE": "NO OPERAR",
        "REVIEW_ONLY": "SOLO ESTUDIO",
    }.get(status, status)


class RoxyDecisionEngine:
    """Turns strategy rows into actionable, auditable operating decisions.

    This layer does not invent market data. It consumes existing live fields, smart
    alert gates, memory, and local knowledge to decide what Roxy should tell the
    trader to do next.
    """

    def process_opportunity(self, opportunity: dict[str, Any], *, enrich_knowledge: bool = True) -> dict[str, Any]:
        row = dict(opportunity)
        if apply_external_market_context is not None and "external_confirmation" not in row:
            try:
                row = apply_external_market_context(row)
            except Exception:
                row = dict(opportunity)
        if enrich_knowledge and "knowledge_enrichment" not in row:
            try:
                row = enrich_opportunity_with_knowledge(row)
            except Exception:
                row = dict(opportunity)

        smart = row.get("smart_alert") if isinstance(row.get("smart_alert"), dict) else evaluate_smart_alert(row)
        row["smart_alert"] = smart
        row["alert_gate"] = row.get("alert_gate") or smart.get("gate")
        row["alert_blockers"] = row.get("alert_blockers") or smart.get("blockers") or []
        row["alert_readiness_score"] = row.get("alert_readiness_score") or smart.get("readiness_score")
        row["alert_movement"] = row.get("alert_movement") or smart.get("movement")
        row["alert_quality"] = row.get("alert_quality") or smart.get("quality")
        row["alert_quality_reason"] = row.get("alert_quality_reason") or smart.get("quality_reason")
        row["alert_next_action"] = row.get("alert_next_action") or smart.get("next_action")

        entry = _metric(row, "entry", "entrada", "suggested_entry", "close", "last_price", "price")
        stop = _metric(row, "stop", "stop_loss", "stopLoss")
        target = _target_price(row, entry)
        risk_pct = _metric(row, "risk_pct")
        target_pct = _metric(row, "recommended_target_pct", "target_pct")
        if target_pct is None and entry and target:
            direction = _direction(row)
            if direction == "ABAJO":
                target_pct = (entry - target) / entry
            else:
                target_pct = (target - entry) / entry
        rr = _metric(row, "reward_r", "rr", "rr_tp1", "rr_tp2")
        if rr is None:
            rr = reward_risk_ratio(risk_pct, target_pct)
        volume = _metric(row, "relative_volume_15m", "relative_volume", "volume_ratio")
        score = _metric(row, "ai_score", "confluence_score", "score") or 0.0
        readiness = safe_float(row.get("alert_readiness_score") or smart.get("readiness_score")) or 0.0
        gate = safe_text(row.get("alert_gate") or smart.get("gate")).upper()
        notification_ok = safe_bool(smart.get("notification_ok"))
        direction = _direction(row)
        live_ok, live_detail = _live_contract_ok(row)
        missing = _missing_operational_fields(row, entry=entry, stop=stop, target=target)

        knowledge = row.get("knowledge_enrichment") if isinstance(row.get("knowledge_enrichment"), dict) else {}
        source_count = int(knowledge.get("source_count") or 0)
        conditions = _condition_summary(row)
        passed_conditions = sum(1 for item in conditions if item.get("passed"))
        condition_ratio = passed_conditions / len(conditions) if conditions else 0.0

        priority = score * 0.42 + readiness * 0.28 + condition_ratio * 20.0
        if rr is not None:
            priority += min(max(rr, 0.0), 3.0) * 4.0
        if volume is not None:
            priority += min(max(volume - 0.8, 0.0), 1.2) * 4.0
        if source_count:
            priority += min(source_count, 6) * 1.0
        external_confirmation = row.get("external_confirmation") if isinstance(row.get("external_confirmation"), dict) else {}
        external_adjustment = safe_float(external_confirmation.get("score_adjustment")) or 0.0
        if external_adjustment:
            priority += external_adjustment
        if missing:
            priority -= 18.0
        if not live_ok:
            priority -= 25.0
        priority = int(max(0, min(100, round(priority))))

        if not live_ok or gate in CRITICAL_GATES:
            status = "NO_TRADE"
            next_action = f"No operar hasta recuperar datos/health: {live_detail}."
        elif direction == "SIN_DIRECCION":
            status = "REVIEW_ONLY"
            next_action = "Roxy no tiene direccion clara; usar solo como estudio hasta que la estrategia defina arriba o abajo."
        elif missing:
            status = "WAIT_CONFIRMATION"
            next_action = "Completar antes de operar: " + ", ".join(missing) + "."
        elif notification_ok and gate in OPERATE_GATES and priority >= 72:
            status = "OPERATE_NOW"
            next_action = "Ejecutar solo con orden limite, stop activo y tamano calculado; registrar resultado."
        elif gate in WAIT_GATES or readiness >= 55:
            status = "WAIT_CONFIRMATION"
            next_action = safe_text(row.get("alert_next_action") or smart.get("next_action")) or "Esperar confirmacion de la estrategia."
        else:
            status = "NO_TRADE"
            next_action = safe_text(row.get("alert_next_action") or smart.get("next_action")) or "No operar: la confluencia no alcanza calidad profesional."

        if status != "OPERATE_NOW":
            priority = min(priority, 79)

        reasons: list[str] = []
        if direction != "SIN_DIRECCION":
            reasons.append(f"Direccion detectada: {direction}.")
        if rr is not None:
            reasons.append(f"Relacion riesgo/recompensa {rr:.2f}R.")
        if volume is not None:
            reasons.append(f"Volumen relativo {volume:.2f}x.")
        if source_count:
            reasons.append(f"Validado contra {source_count} fragmentos de conocimiento local.")
        if external_confirmation.get("confirmed"):
            sources = external_confirmation.get("sources") if isinstance(external_confirmation.get("sources"), list) else []
            source_text = ", ".join(str(source) for source in sources[:2] if source) or "fuente externa"
            reasons.append(
                f"Confirmacion externa {source_text}: ajuste {external_confirmation.get('score_adjustment', 0)} puntos."
            )
        elif external_confirmation.get("reasons"):
            reasons.append(safe_text(external_confirmation.get("reasons", [""])[0]))
        if missing:
            reasons.append("Faltan campos operativos: " + ", ".join(missing) + ".")
        blockers = [safe_text(item) for item in row.get("alert_blockers", []) if safe_text(item)]
        if blockers:
            reasons.append("Bloqueos: " + "; ".join(blockers[:3]) + ".")

        row["roxy_decision"] = {
            "version": "roxy-decision-engine-v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "label": _decision_label(status),
            "direction": direction,
            "priority_score": priority,
            "confidence": priority,
            "readiness_score": round(readiness, 1),
            "gate": gate or "UNKNOWN",
            "entry": entry,
            "stop": stop,
            "target": target,
            "risk_pct": risk_pct,
            "target_pct": target_pct,
            "reward_r": rr,
            "relative_volume": volume,
            "live_ok": live_ok,
            "live_detail": live_detail,
            "missing_fields": missing,
            "conditions_passed": passed_conditions,
            "conditions_total": len(conditions),
            "conditions": conditions,
            "knowledge_sources": source_count,
            "external_confirmation": external_confirmation,
            "next_action": next_action,
            "reasons": reasons,
            "execution_rules": [
                "No operar dinero real si faltan entrada, stop o target.",
                "Usar orden limite y cancelar si el precio se aleja del plan.",
                "Registrar resultado para que la memoria ajuste el peso de la estrategia.",
                "Si el mercado cambia antes de entrar, recalcular en vez de perseguir precio.",
            ],
        }
        row["roxy_decision_status"] = status
        row["roxy_decision_label"] = _decision_label(status)
        row["roxy_priority_score"] = priority
        row["roxy_next_action"] = next_action
        return row

    def process_opportunities(self, opportunities: Iterable[dict[str, Any]], *, enrich_knowledge: bool = True) -> list[dict[str, Any]]:
        processed = [self.process_opportunity(item, enrich_knowledge=enrich_knowledge) for item in opportunities]
        processed.sort(
            key=lambda item: (
                item.get("roxy_decision_status") == "OPERATE_NOW",
                item.get("roxy_decision_status") == "WAIT_CONFIRMATION",
                int(item.get("roxy_priority_score") or 0),
                int(item.get("ai_score") or 0),
            ),
            reverse=True,
        )
        return processed


def process_opportunity_with_decision(opportunity: dict[str, Any], *, enrich_knowledge: bool = True) -> dict[str, Any]:
    return RoxyDecisionEngine().process_opportunity(opportunity, enrich_knowledge=enrich_knowledge)


def process_opportunities_with_decisions(
    opportunities: Iterable[dict[str, Any]],
    *,
    enrich_knowledge: bool = True,
) -> list[dict[str, Any]]:
    return RoxyDecisionEngine().process_opportunities(opportunities, enrich_knowledge=enrich_knowledge)
