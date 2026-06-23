from __future__ import annotations

from typing import Any

from natalia_strategy_rules import evaluate_natalia_strategy_rules
from trade_brief import (
    is_execution_timeframe,
    macro_event_confirmation_ok,
    macro_event_risk,
    non_negotiable_checks,
    reward_risk_ratio,
    safe_bool,
    safe_float,
    safe_text,
    strategy_family_from_setup,
)


MAX_RISK_PCT = 0.035
MIN_TARGET_PCT = 0.02
MIN_VOLUME = 0.8
IDEAL_VOLUME = 1.1
MIN_CONFLUENCE_SCORE = 75
MIN_TREND_SCORE = 70
HIGHER_TF_OK = {"CONFIRMED", "PARTIAL"}
OPERABLE_CHART_GATES = {"LIVE_DATA_OK", "ANALYSIS_OK", "LIVE_PRICE_OK"}
BLOCKING_CHART_GATES = {
    "NO_TRADE_FROM_FALLBACK",
    "NO_TRADE_STALE_DATA",
    "NO_TRADE_FROM_PUBLIC_PRICE",
    "NO_TRADE_PRICE_FAIL",
    "NO_TRADE_STALE_PRICE",
    "WAIT_PRICE_CONFIRMATION",
    "WAIT_NEXT_CANDLE",
    "MARKET_CLOSED_RECHECK",
    "EXTERNAL_CONFIRM_REQUIRED",
    "CHART_CONTRACT_MISSING",
}


def _alerts_allowed_from_context(value: Any, *, market: str = "") -> tuple[bool | None, str]:
    if not isinstance(value, dict):
        return None, ""
    market_value = safe_text(market).lower()
    if market_value in {"stock", "stocks", "equity", "option", "options"} and "stock_alerts_allowed" in value:
        allowed = safe_bool(value.get("stock_alerts_allowed"))
        label = safe_text(value.get("label") or value.get("status") or "contexto")
        detail = safe_text(value.get("detail"))
        return allowed, f"{label}: {detail}" if detail else label
    if market_value == "crypto" and "crypto_alerts_allowed" in value:
        allowed = safe_bool(value.get("crypto_alerts_allowed"))
        label = safe_text(value.get("label") or value.get("status") or "contexto")
        detail = safe_text(value.get("detail"))
        return allowed, f"{label}: {detail}" if detail else label
    if "alerts_allowed" not in value:
        return None, ""
    allowed = safe_bool(value.get("alerts_allowed"))
    label = safe_text(value.get("label") or value.get("status") or "contexto")
    detail = safe_text(value.get("detail"))
    return allowed, f"{label}: {detail}" if detail else label


def _realtime_context_is_healthy(row: dict[str, Any]) -> tuple[bool, str]:
    direct_allowed = row.get("alerts_allowed")
    if direct_allowed is not None and not safe_bool(direct_allowed):
        return False, safe_text(row.get("alerts_blocker") or "alertas deshabilitadas por contexto")
    market = safe_text(row.get("market"))

    for key, fallback in (
        ("source_freshness", "fuente no permite alertas"),
        ("realtime_health", "health realtime no permite alertas"),
    ):
        allowed, detail = _alerts_allowed_from_context(row.get(key), market=market)
        if allowed is False:
            return False, detail or fallback

    if safe_bool(row.get("data_stale") or row.get("stale_data")):
        return False, safe_text(row.get("stale_reason") or "datos vencidos")

    return True, "fuente y health permiten alertas"


def _chart_contract_is_healthy(row: dict[str, Any]) -> tuple[bool, str]:
    contract = row.get("chart_data_contract")
    if not isinstance(contract, dict):
        contract = row.get("chart_contract") if isinstance(row.get("chart_contract"), dict) else {}
    if not isinstance(contract, dict) or not contract:
        for key in ("live_price_contract", "price_data_contract", "price_contract"):
            if isinstance(row.get(key), dict):
                contract = row[key]
                break
    gate = safe_text(
        contract.get("gate")
        or row.get("chart_data_gate")
        or row.get("live_price_gate")
        or row.get("price_data_gate")
        or row.get("chart_contract_gate")
        or row.get("data_contract_gate")
    ).upper()
    operable_value = (
        contract.get("operable")
        if "operable" in contract
        else row.get("chart_operable")
        if "chart_operable" in row
        else row.get("chart_data_operable")
        if "chart_data_operable" in row
        else None
    )
    source = safe_text(
        contract.get("source_label")
        or contract.get("source")
        or row.get("price_source_label")
        or row.get("price_source")
        or row.get("chart_source_label")
        or row.get("chart_source")
    )
    phase = safe_text(
        contract.get("candle_phase_label")
        or row.get("chart_candle_phase_label")
        or row.get("candle_phase_label")
    )
    detail_parts = []
    if gate:
        detail_parts.append(gate)
    if source:
        detail_parts.append(source)
    if phase:
        detail_parts.append(phase)
    detail = " | ".join(detail_parts) if detail_parts else "contrato de grafica no enviado"

    if operable_value is not None and not safe_bool(operable_value):
        return False, detail or "grafica marcada como no operable"
    if gate in BLOCKING_CHART_GATES:
        return False, detail
    if gate and gate not in OPERABLE_CHART_GATES:
        return False, detail
    if gate in OPERABLE_CHART_GATES or safe_bool(operable_value):
        return True, detail or "grafica operable"
    return True, detail


def _memory_is_healthy(row: dict[str, Any], memory: dict[str, Any] | None) -> tuple[bool, str]:
    if not memory:
        return True, "No negative memory yet"
    family = safe_text(row.get("strategy_family")) or strategy_family_from_setup(
        safe_text(row.get("trigger_setup") or row.get("setup")),
        trend_setup=safe_text(row.get("trend_setup")),
    )
    stats = (memory.get("strategy_stats") or {}).get(family, {})
    alerts = int(stats.get("alerts", 0) or 0)
    hit_2 = int(stats.get("hit_2pct", 0) or 0)
    stops = int(stats.get("stops", 0) or 0)
    if alerts < 3:
        shadow_observed = int(stats.get("shadow_observed", 0) or 0)
        shadow_near_2 = int(stats.get("shadow_near_2pct", 0) or 0)
        shadow_hit_2 = int(stats.get("shadow_hit_2pct", 0) or 0)
        shadow_near_stop = int(stats.get("shadow_near_stop", 0) or 0)
        shadow_target_rate = max(shadow_near_2, shadow_hit_2) / shadow_observed if shadow_observed else 0.0
        shadow_stop_pressure = shadow_near_stop / shadow_observed if shadow_observed else 0.0
        if shadow_observed >= 3 and shadow_stop_pressure >= 0.50 and shadow_target_rate < 0.35:
            detail = (
                f"{family}: shadow target {shadow_target_rate * 100:.0f}% / "
                f"shadow stop {shadow_stop_pressure * 100:.0f}%"
            )
            return False, detail
        return True, f"{family}: collecting data"
    hit_rate = hit_2 / alerts if alerts else 0.0
    stop_rate = stops / alerts if alerts else 0.0
    healthy = not (stop_rate >= 0.50 and hit_rate < 0.35)
    detail = f"{family}: hit2 {hit_rate * 100:.0f}% / stop {stop_rate * 100:.0f}%"
    return healthy, detail


def alert_quality_label(
    *,
    notification_ok: bool,
    gate: str,
    readiness_score: float,
    risk: float | None,
    target: float | None,
    volume: float | None,
    memory_ok: bool,
) -> tuple[str, str]:
    if not memory_ok:
        return "C", "Memoria negativa: Roxy baja prioridad hasta ver mejores resultados."
    if notification_ok:
        if (
            risk is not None
            and risk <= 0.025
            and target is not None
            and target >= 0.05
            and volume is not None
            and volume >= IDEAL_VOLUME
        ):
            return "A+", "Setup completo: tendencia, entrada, volumen, riesgo y target estan alineados."
        return "A", "Setup accionable: checklist completo, pero no esta en calidad maxima."
    if readiness_score >= 75 and gate in {"WAIT_15M_ENTRY", "WAIT_1H_CONFIRM", "WAIT_HTF_CONFIRM", "WAIT_VOLUME"}:
        return "B", "Casi listo: falta una confirmacion antes de avisar como operable."
    return "C", "No operar todavia: faltan condiciones importantes del checklist."


def evaluate_smart_alert(row: dict[str, Any], memory: dict[str, Any] | None = None) -> dict[str, Any]:
    signal = safe_text(row.get("signal")).upper()
    decision = safe_text(row.get("trade_decision")).upper()
    trigger_setup = safe_text(row.get("trigger_setup") or row.get("setup")).upper()
    trend_setup = safe_text(row.get("trend_setup")).upper()
    timeframe = safe_text(row.get("timeframe") or row.get("tf"))
    score = safe_float(row.get("confluence_score")) or safe_float(row.get("ai_score")) or 0.0
    trend_score = safe_float(row.get("trend_score"))
    trigger_score = safe_float(row.get("trigger_score"))
    risk = safe_float(row.get("risk_pct"))
    target = safe_float(row.get("recommended_target_pct"))
    reward_r = reward_risk_ratio(risk, target)
    volume = safe_float(row.get("relative_volume_15m") or row.get("relative_volume"))
    backtest_ok = safe_bool(row.get("backtest_eligible"))
    memory_ok, memory_detail = _memory_is_healthy(row, memory)
    context_ok, context_detail = _realtime_context_is_healthy(row)
    chart_contract_ok, chart_contract_detail = _chart_contract_is_healthy(row)
    higher_tf_bias = safe_text(row.get("higher_tf_bias")).upper()
    higher_tf_present = any(
        key in row
        for key in (
            "higher_tf_bias",
            "higher_tf_confirmations",
            "higher_tf_blocks",
            "htf_2h_signal",
            "htf_4h_signal",
        )
    )
    higher_tf_ok = not higher_tf_present or higher_tf_bias in HIGHER_TF_OK
    if not higher_tf_present:
        higher_tf_detail = "no disponible en este scan"
    elif higher_tf_bias == "CONFIRMED":
        higher_tf_detail = "2h/4h confirmadas"
    elif higher_tf_bias == "PARTIAL":
        higher_tf_detail = "2h/4h parcial"
    elif higher_tf_bias == "BLOCKED":
        higher_tf_detail = "2h/4h contradicen el gatillo"
    else:
        higher_tf_detail = "falta contexto 2h/4h"

    one_hour_ok = (trend_score is not None and trend_score >= MIN_TREND_SCORE) or trend_setup in {
        "TREND_CONTINUATION",
        "EARLY_UPTREND",
        "PULLBACK",
    }
    fifteen_ok = signal == "BUY" and decision.startswith("TRADE_FOR")
    if trigger_score is not None:
        fifteen_ok = fifteen_ok and trigger_score >= 65
    execution_tf = is_execution_timeframe(timeframe)
    execution_timing_ok = not execution_tf or (fifteen_ok and one_hour_ok and higher_tf_ok)
    volume_ok = volume is not None and volume >= MIN_VOLUME
    risk_ok = risk is not None and risk <= MAX_RISK_PCT
    target_ok = target is not None and target >= MIN_TARGET_PCT
    reward_r_ok = reward_r is not None and reward_r >= 1.0
    score_ok = score >= MIN_CONFLUENCE_SCORE
    structure_ok = signal != "AVOID" and "DOWNTREND" not in {trigger_setup, trend_setup}
    no_negotiables = non_negotiable_checks(row, row)
    no_negotiables_ok = all(bool(item.get("passed")) for item in no_negotiables)
    macro_risk = macro_event_risk(row)
    macro_ok, macro_detail = macro_event_confirmation_ok(
        macro_risk,
        confirmed_buy=fifteen_ok,
        score=score,
        reward_r=reward_r,
        volume=volume,
        higher_tf_ok=higher_tf_ok,
    )
    natalia_rules = evaluate_natalia_strategy_rules(row, row)
    natalia_ok = not bool(natalia_rules.get("hard_block") or natalia_rules.get("wait_block"))

    checks = [
        {
            "rule": "Datos realtime",
            "passed": context_ok,
            "detail": context_detail,
        },
        {
            "rule": "Grafica operable",
            "passed": chart_contract_ok,
            "detail": chart_contract_detail,
        },
        {
            "rule": "1h confirma",
            "passed": one_hour_ok,
            "detail": f"Score tendencia {trend_score:.0f}" if trend_score is not None else (trend_setup or "falta tendencia"),
        },
        {
            "rule": "15m da entrada",
            "passed": fifteen_ok,
            "detail": decision or signal or "falta gatillo de entrada",
        },
        {
            "rule": "1m/5m solo timing",
            "passed": execution_timing_ok,
            "detail": (
                "usar solo para afinar entrada; 15m/1h/2h/4h validan"
                if execution_tf and execution_timing_ok
                else "no usar micro-timeframe como gatillo principal"
                if execution_tf
                else "no aplica"
            ),
        },
        {
            "rule": "2h/4h validan",
            "passed": higher_tf_ok,
            "detail": higher_tf_detail,
        },
        {
            "rule": "Evento FED/macro",
            "passed": macro_ok,
            "detail": macro_detail,
        },
        {
            "rule": "Volumen acompana",
            "passed": volume_ok,
            "detail": f"{volume:.2f}x" if volume is not None else "falta volumen",
        },
        {
            "rule": "Riesgo bajo",
            "passed": risk_ok,
            "detail": f"{risk * 100:.2f}%" if risk is not None else "falta stop/riesgo",
        },
        {
            "rule": "Target 2% viable",
            "passed": target_ok,
            "detail": f"{target * 100:.0f}%" if target is not None else "falta target",
        },
        {
            "rule": "Reward/Risk viable",
            "passed": reward_r_ok,
            "detail": f"{reward_r:.2f}R" if reward_r is not None else "falta riesgo/target",
        },
        {
            "rule": "Filtro historico",
            "passed": backtest_ok,
            "detail": "elegible" if backtest_ok else "no elegible",
        },
        {
            "rule": "Score confluencia",
            "passed": score_ok,
            "detail": f"{score:.0f}/{MIN_CONFLUENCE_SCORE}",
        },
        {
            "rule": "Estructura mercado",
            "passed": structure_ok,
            "detail": f"{trigger_setup or '-'} / {trend_setup or '-'}",
        },
        {
            "rule": "Reglas Natalia",
            "passed": natalia_ok,
            "detail": safe_text(natalia_rules.get("summary")) or "filtro aprendido sin bloqueos",
        },
        *[
            {
                "rule": f"No negociable: {safe_text(item.get('label'))}",
                "passed": bool(item.get("passed")),
                "detail": safe_text(item.get("detail")),
            }
            for item in no_negotiables
        ],
        {
            "rule": "Filtro memoria",
            "passed": memory_ok,
            "detail": memory_detail,
        },
    ]
    passed_count = sum(1 for item in checks if item["passed"])
    total_checks = len(checks)
    blockers = [f"{item['rule']}: {item['detail']}" for item in checks if not item["passed"]]
    notification_ok = passed_count == total_checks
    readiness_score = round(passed_count / total_checks * 100, 1)

    if notification_ok:
        gate = "ALERT_READY"
        movement = "Operar solo con entrada, stop y targets planificados."
    elif not context_ok or not chart_contract_ok:
        gate = "BLOCKED_REALTIME_DATA"
        movement = "No alertar hasta que la fuente live, confluencia, health realtime y grafica operable vuelvan a estar confirmados."
        realtime_health = row.get("realtime_health") if isinstance(row.get("realtime_health"), dict) else {}
        provider_recovery = (
            realtime_health.get("provider_recovery")
            if isinstance(realtime_health.get("provider_recovery"), dict)
            else {}
        )
        recovery_action = safe_text(
            realtime_health.get("premium_recovery_action") or provider_recovery.get("action")
        )
        if recovery_action:
            movement = recovery_action
        elif not chart_contract_ok:
            movement = f"No alertar: grafica no operable ({chart_contract_detail})."
    elif one_hour_ok and not fifteen_ok and structure_ok:
        gate = "WAIT_15M_ENTRY"
        movement = "Esperar gatillo BUY en 15m mientras 1h sigue valido."
    elif fifteen_ok and not one_hour_ok and structure_ok:
        gate = "WAIT_1H_CONFIRM"
        movement = "Esperar confirmacion en 1h antes de alertar."
    elif fifteen_ok and one_hour_ok and not higher_tf_ok and structure_ok:
        gate = "WAIT_HTF_CONFIRM"
        movement = "Esperar que 2h/4h confirmen o dejen de bloquear el gatillo."
    elif not execution_timing_ok:
        gate = "WAIT_PARENT_TIMEFRAME"
        movement = "Usar 1m/5m solo para precision; esperar confirmacion 15m/1h/2h/4h antes de alertar."
    elif not macro_ok:
        gate = "WAIT_MACRO_CONFIRMATION"
        movement = "Evento FED/macro activo: esperar post-noticia o una confirmacion mas fuerte antes de alertar."
    elif not volume_ok and structure_ok:
        gate = "WAIT_VOLUME"
        movement = f"Esperar volumen relativo >= {MIN_VOLUME:.1f}x; ideal >= {IDEAL_VOLUME:.1f}x."
    elif not reward_r_ok and risk_ok and target_ok:
        gate = "WAIT_REWARD_RISK"
        movement = "Esperar mejor entrada o stop mas cercano: el objetivo minimo debe pagar al menos 1R."
    elif natalia_rules.get("hard_block"):
        gate = "NO_TRADE_NATALIA_RULES"
        movement = safe_text(natalia_rules.get("movement")) or "Evitar hasta que las reglas aprendidas de estructura vuelvan a pasar."
    elif not structure_ok:
        gate = "NO_TRADE_STRUCTURE"
        movement = "Evitar hasta que la estructura deje de estar bajista o en AVOID."
    elif not no_negotiables_ok:
        gate = "WAIT_FULL_CHECKLIST"
        movement = "Esperar entrada limpia: no perseguir vela llena y no entrar expuesto fuera de Bollinger."
    elif natalia_rules.get("wait_block"):
        gate = "WAIT_NATALIA_CONFIRMATION"
        movement = safe_text(natalia_rules.get("movement")) or "Esperar confirmacion de reglas aprendidas antes de alertar."
    else:
        gate = "WAIT_FULL_CHECKLIST"
        movement = "Esperar hasta que riesgo, target, volumen y confirmacion esten alineados."
    quality, quality_reason = alert_quality_label(
        notification_ok=notification_ok,
        gate=gate,
        readiness_score=readiness_score,
        risk=risk,
        target=target,
        volume=volume,
        memory_ok=memory_ok,
    )
    primary_blocker = blockers[0] if blockers else "Listo para preview manual"
    next_action = movement if not notification_ok else "Preparar plan manual: entrada, stop, targets y tamano."

    return {
        "notification_ok": notification_ok,
        "gate": gate,
        "passed_count": passed_count,
        "total_checks": total_checks,
        "readiness_score": readiness_score,
        "quality": quality,
        "quality_reason": quality_reason,
        "primary_blocker": primary_blocker,
        "next_action": next_action,
        "checks": checks,
        "blockers": blockers,
        "movement": movement,
        "summary": f"{gate}: {passed_count}/{total_checks} checks passed.",
    }
