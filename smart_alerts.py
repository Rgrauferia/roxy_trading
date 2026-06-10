from __future__ import annotations

from typing import Any

from trade_brief import safe_bool, safe_float, safe_text, strategy_family_from_setup


MAX_RISK_PCT = 0.035
MIN_TARGET_PCT = 0.02
MIN_VOLUME = 0.8
IDEAL_VOLUME = 1.1
MIN_CONFLUENCE_SCORE = 75
MIN_TREND_SCORE = 70
HIGHER_TF_OK = {"CONFIRMED", "PARTIAL"}


def _alerts_allowed_from_context(value: Any) -> tuple[bool | None, str]:
    if not isinstance(value, dict):
        return None, ""
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

    for key, fallback in (
        ("source_freshness", "fuente no permite alertas"),
        ("realtime_health", "health realtime no permite alertas"),
    ):
        allowed, detail = _alerts_allowed_from_context(row.get(key))
        if allowed is False:
            return False, detail or fallback

    if safe_bool(row.get("data_stale") or row.get("stale_data")):
        return False, safe_text(row.get("stale_reason") or "datos vencidos")

    return True, "fuente y health permiten alertas"


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
    score = safe_float(row.get("confluence_score")) or safe_float(row.get("ai_score")) or 0.0
    trend_score = safe_float(row.get("trend_score"))
    trigger_score = safe_float(row.get("trigger_score"))
    risk = safe_float(row.get("risk_pct"))
    target = safe_float(row.get("recommended_target_pct"))
    volume = safe_float(row.get("relative_volume_15m") or row.get("relative_volume"))
    backtest_ok = safe_bool(row.get("backtest_eligible"))
    memory_ok, memory_detail = _memory_is_healthy(row, memory)
    context_ok, context_detail = _realtime_context_is_healthy(row)
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
    volume_ok = volume is not None and volume >= MIN_VOLUME
    risk_ok = risk is not None and risk <= MAX_RISK_PCT
    target_ok = target is not None and target >= MIN_TARGET_PCT
    score_ok = score >= MIN_CONFLUENCE_SCORE
    structure_ok = signal != "AVOID" and "DOWNTREND" not in {trigger_setup, trend_setup}

    checks = [
        {
            "rule": "Datos realtime",
            "passed": context_ok,
            "detail": context_detail,
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
            "rule": "2h/4h validan",
            "passed": higher_tf_ok,
            "detail": higher_tf_detail,
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
    elif one_hour_ok and not fifteen_ok and structure_ok:
        gate = "WAIT_15M_ENTRY"
        movement = "Esperar gatillo BUY en 15m mientras 1h sigue valido."
    elif fifteen_ok and not one_hour_ok and structure_ok:
        gate = "WAIT_1H_CONFIRM"
        movement = "Esperar confirmacion en 1h antes de alertar."
    elif fifteen_ok and one_hour_ok and not higher_tf_ok and structure_ok:
        gate = "WAIT_HTF_CONFIRM"
        movement = "Esperar que 2h/4h confirmen o dejen de bloquear el gatillo."
    elif not context_ok:
        gate = "BLOCKED_REALTIME_DATA"
        movement = "No alertar hasta que la fuente live, confluencia y health realtime vuelvan a estar frescos."
    elif not volume_ok and structure_ok:
        gate = "WAIT_VOLUME"
        movement = f"Esperar volumen relativo >= {MIN_VOLUME:.1f}x; ideal >= {IDEAL_VOLUME:.1f}x."
    elif not structure_ok:
        gate = "NO_TRADE_STRUCTURE"
        movement = "Evitar hasta que la estructura deje de estar bajista o en AVOID."
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
