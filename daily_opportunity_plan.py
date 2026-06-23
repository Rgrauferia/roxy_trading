from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from multitimeframe_rules import build_multitimeframe_context


STAGE_LABELS = {
    "OPERAR_AHORA": "Operar ahora",
    "PROXIMA_ENTRADA": "Proxima entrada",
    "VIGILAR": "Vigilar",
    "ESPERAR_DATOS": "Esperar datos",
    "NO_OPERAR": "No operar",
}

STAGE_ORDER = {
    "OPERAR_AHORA": 0,
    "PROXIMA_ENTRADA": 1,
    "VIGILAR": 2,
    "ESPERAR_DATOS": 3,
    "NO_OPERAR": 4,
}

PORTFOLIO_WIN_RATE_TARGET = 0.70
MIN_POSITIVE_EXPECTANCY_R = 0.05


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except Exception:
        pass
    return str(value or "").strip()


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if value != value:
            return None
    except Exception:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = safe_text(value).lower()
    return text in {"1", "true", "yes", "y", "si", "sí", "ok"}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def target_price(entry: float | None, pct: float, row: dict[str, Any], field: str) -> float | None:
    existing = safe_float(row.get(field))
    if existing is not None:
        return existing
    if entry is None or entry <= 0:
        return None
    return entry * (1.0 + pct)


def reward_risk_ratio(risk_pct: Any, target_pct: Any) -> float | None:
    risk = safe_float(risk_pct)
    target = safe_float(target_pct)
    if risk is None or target is None or risk <= 0 or target <= 0:
        return None
    return target / risk


def expectancy_r(probability: Any, reward_r: Any) -> float | None:
    probability_value = safe_float(probability)
    reward_value = safe_float(reward_r)
    if probability_value is None or reward_value is None:
        return None
    probability_fraction = probability_value / 100.0 if probability_value > 1 else probability_value
    probability_fraction = max(0.0, min(1.0, probability_fraction))
    return probability_fraction * reward_value - (1.0 - probability_fraction)


def portfolio_edge_summary(probability: Any, expected_r: Any) -> str:
    probability_value = safe_float(probability)
    expected_value = safe_float(expected_r)
    if probability_value is None or expected_value is None:
        return "Falta probabilidad o R:R para medir el balance de 10 trades."
    wins = int(round(max(0.0, min(100.0, probability_value)) / 10.0))
    losses = max(0, 10 - wins)
    edge = "positivo" if expected_value >= MIN_POSITIVE_EXPECTANCY_R else "negativo"
    return f"Modelo 10 trades: aprox. {wins} ganan / {losses} pierden; EV {expected_value:.2f}R {edge} por trade."


def timing_edge(row: dict[str, Any], stage: str, probability: int) -> dict[str, Any]:
    risk = safe_float(row.get("risk_pct"))
    target = safe_float(row.get("recommended_target_pct") or row.get("target_pct"))
    reward_r = reward_risk_ratio(risk, target)
    expected = expectancy_r(probability, reward_r)
    gate = safe_text(row.get("alert_gate")).upper()
    signal = safe_text(row.get("signal")).upper()
    decision = safe_text(row.get("trade_decision") or row.get("decision")).upper()
    blocked = stage in {"NO_OPERAR", "ESPERAR_DATOS"} or context_is_blocked(row)
    trigger_ready = gate in {"ALERT_READY", "WAIT_15M_ENTRY", ""} and (
        signal == "BUY" or decision.startswith("TRADE_FOR") or safe_text(row.get("ai_action")).upper() == "ALERT"
    )

    if blocked:
        label = "Sin edge operable"
        verdict = "No arriesgar: falta estructura o datos operables."
    elif expected is None:
        label = "Edge sin medir"
        verdict = "No arriesgar todavia: falta stop, target o probabilidad medible."
    elif stage == "OPERAR_AHORA" and trigger_ready and expected >= MIN_POSITIVE_EXPECTANCY_R:
        label = "Entrar si confirma precio"
        verdict = "Roxy puede arriesgar en paper/manual: timing, stop, target y EV son positivos."
    elif expected >= 0.35 and probability >= int(PORTFOLIO_WIN_RATE_TARGET * 100):
        label = "Ventaja 70/30"
        verdict = "Vale la pena vigilar agresivo: el balance esperado favorece al trader."
    elif expected >= MIN_POSITIVE_EXPECTANCY_R:
        label = "Edge positivo"
        verdict = "Puede operar solo si aparece el gatillo exacto; no perseguir precio."
    else:
        label = "Sin edge suficiente"
        verdict = "El riesgo existe, pero el pago esperado todavia no compensa."

    return {
        "reward_risk": None if reward_r is None else round(reward_r, 4),
        "expectancy_r": None if expected is None else round(expected, 4),
        "edge_label": label,
        "timing_verdict": verdict,
        "portfolio_math": portfolio_edge_summary(probability, expected),
    }


def context_is_blocked(row: dict[str, Any]) -> bool:
    for key in ("source_freshness", "realtime_health"):
        payload = row.get(key)
        if isinstance(payload, dict) and payload.get("alerts_allowed") is not None and not safe_bool(payload.get("alerts_allowed")):
            return True
    if row.get("alerts_allowed") is not None and not safe_bool(row.get("alerts_allowed")):
        return True
    return False


def classify_stage(row: dict[str, Any]) -> str:
    action = safe_text(row.get("ai_action")).upper()
    signal = safe_text(row.get("signal")).upper()
    decision = safe_text(row.get("trade_decision") or row.get("decision")).upper()
    gate = safe_text(row.get("alert_gate")).upper()
    readiness = safe_float(row.get("alert_readiness_score")) or 0.0

    if context_is_blocked(row) or gate == "BLOCKED_REALTIME_DATA":
        return "ESPERAR_DATOS"
    if action == "ALERT" and gate in {"ALERT_READY", ""}:
        return "OPERAR_AHORA"
    if signal == "AVOID" or decision.startswith("NO_TRADE") or gate in {"NO_TRADE_STRUCTURE", "BLOCKED_BY_MEMORY"}:
        return "NO_OPERAR"
    if gate in {"WAIT_15M_ENTRY", "WAIT_1H_CONFIRM", "WAIT_HTF_CONFIRM", "WAIT_VOLUME"} or readiness >= 75:
        return "PROXIMA_ENTRADA"
    if signal in {"BUY", "WATCH"} or readiness >= 55:
        return "VIGILAR"
    return "NO_OPERAR"


def probability_score(row: dict[str, Any], stage: str | None = None) -> int:
    stage = stage or classify_stage(row)
    ai_score = safe_float(row.get("ai_score") or row.get("confluence_score")) or 0.0
    readiness = safe_float(row.get("alert_readiness_score")) or 0.0
    trend_score = safe_float(row.get("trend_score")) or 0.0
    trigger_score = safe_float(row.get("trigger_score")) or 0.0
    risk = safe_float(row.get("risk_pct"))
    target = safe_float(row.get("recommended_target_pct") or row.get("target_pct"))
    volume = safe_float(row.get("relative_volume_15m") or row.get("relative_volume"))
    learning_bias = safe_text(row.get("learning_bias")).lower()
    learned_status = safe_text(row.get("learned_strategy_status")).upper()
    backtest_ok = safe_bool(row.get("backtest_eligible"))
    mtf_context = build_multitimeframe_context(row)
    mtf_alignment = safe_text(mtf_context.get("alignment")).upper()

    points = 8.0
    points += min(ai_score, 100.0) * 0.32
    points += min(readiness, 100.0) * 0.34
    points += min(trend_score, 100.0) * 0.08
    points += min(trigger_score, 100.0) * 0.06

    if risk is not None:
        if risk <= 0.015:
            points += 8
        elif risk <= 0.025:
            points += 5
        elif risk <= 0.035:
            points += 2
        else:
            points -= 14
    else:
        points -= 5

    if target is not None:
        if target >= 0.10:
            points += 6
        elif target >= 0.05:
            points += 4
        elif target >= 0.02:
            points += 2
        else:
            points -= 8
    else:
        points -= 4

    if volume is not None:
        if volume >= 1.1:
            points += 6
        elif volume >= 0.8:
            points += 3
        else:
            points -= 7

    if backtest_ok:
        points += 4
    if learning_bias in {"positive", "shadow_positive"}:
        points += 5
    elif learning_bias in {"negative", "shadow_negative"}:
        points -= 10
    if learned_status == "ACTIVE":
        points += 5
    elif learned_status == "WATCH":
        points += 3
    elif learned_status == "BLOCKED":
        points -= 8
    if mtf_alignment == "CONFIRMED":
        points += 5
    elif mtf_alignment == "PARTIAL":
        points += 2
    elif mtf_alignment == "BLOCKED":
        points -= 12

    if stage == "OPERAR_AHORA":
        points += 10
    elif stage == "PROXIMA_ENTRADA":
        points += 3
    elif stage == "NO_OPERAR":
        points = min(points, 35)
    elif stage == "ESPERAR_DATOS":
        points = min(points, 45)

    return int(round(clamp(points)))


def direct_decision(row: dict[str, Any], stage: str) -> str:
    market = safe_text(row.get("market")).lower()
    option = row.get("option") if isinstance(row.get("option"), dict) else {}
    if stage == "OPERAR_AHORA":
        if market == "stock" and (option.get("contract") or safe_text(option.get("decision")).upper() in {"WATCH_CALL", "BUY_CALL"}):
            return "Mirar call"
        return "Operar"
    if stage in {"PROXIMA_ENTRADA", "VIGILAR"}:
        return "Esperar"
    return "No operar"


def expected_move_text(row: dict[str, Any], entry: float | None) -> str:
    gate_next = safe_text(row.get("alert_next_action") or row.get("alert_movement"))
    if gate_next:
        return gate_next
    gate = safe_text(row.get("alert_gate")).upper()
    if gate == "WAIT_MACRO_CONFIRMATION":
        return "Esperar que pase el evento macro o que llegue confirmacion fuerte post-noticia."
    if gate == "WAIT_15M_ENTRY":
        return "Esperar gatillo BUY en 15m mientras 1h sigue valido."
    if gate == "WAIT_1H_CONFIRM":
        return "Esperar que 1h confirme tendencia antes de alertar."
    if gate == "WAIT_HTF_CONFIRM":
        return "Esperar que 2h/4h confirmen o dejen de bloquear el gatillo."
    if gate == "WAIT_VOLUME":
        return "Esperar volumen relativo acompanando la entrada."
    if gate == "NO_TRADE_STRUCTURE":
        return "Evitar hasta que la estructura deje de estar bajista o en AVOID."
    if entry is None:
        return "Esperar precio de entrada medible antes de estimar movimiento."
    target_2 = target_price(entry, 0.02, row, "target_2pct_price")
    return f"Primer escenario: buscar 2% hacia {target_2:.2f} y proteger bajo el stop." if target_2 else "Buscar 2% solo si se confirma entrada y stop."


def blocker_text(row: dict[str, Any]) -> str:
    blockers = row.get("alert_blockers") or []
    if isinstance(blockers, str):
        blockers = [blockers]
    items = [safe_text(item) for item in blockers if safe_text(item)]
    return " | ".join(items[:3]) if items else "Checklist completo"


def build_daily_plan_row(row: dict[str, Any]) -> dict[str, Any]:
    stage = classify_stage(row)
    probability = probability_score(row, stage)
    mtf_context = build_multitimeframe_context(row)
    macro_active = safe_bool(row.get("macro_event") or row.get("event_risk"))
    macro_context = safe_text(row.get("macro_context") or row.get("news_event") or row.get("macro_event_severity"))
    entry = safe_float(row.get("entry"))
    stop = safe_float(row.get("stop"))
    risk = safe_float(row.get("risk_pct"))
    target = safe_float(row.get("recommended_target_pct") or row.get("target_pct"))
    learned = row.get("learned_strategy") if isinstance(row.get("learned_strategy"), dict) else {}
    strategy = (
        safe_text(row.get("learned_strategy_name"))
        or safe_text(learned.get("name"))
        or safe_text(row.get("strategy_family"))
        or safe_text(row.get("trigger_setup") or row.get("setup"))
    )
    stage_label = STAGE_LABELS.get(stage, stage)
    decision = direct_decision(row, stage)
    edge = timing_edge(row, stage, probability)
    trigger = expected_move_text(row, entry)
    why = safe_text(row.get("alert_quality_reason") or row.get("explanation") or row.get("memory_note"))
    if not why:
        why = "Roxy compara 1h, 15m, volumen, riesgo, target y memoria antes de operar."

    return {
        "symbol": safe_text(row.get("symbol")).upper(),
        "market": safe_text(row.get("market")) or "-",
        "stage": stage,
        "stage_label": stage_label,
        "decision": decision,
        "probability": probability,
        "quality": safe_text(row.get("alert_quality")) or "-",
        "readiness": safe_float(row.get("alert_readiness_score")),
        "ai_score": safe_float(row.get("ai_score")),
        "strategy": strategy or "-",
        "signal": safe_text(row.get("signal")) or "-",
        "trade_decision": safe_text(row.get("trade_decision") or row.get("decision")) or "-",
        "entry": entry,
        "stop": stop,
        "target_2": target_price(entry, 0.02, row, "target_2pct_price"),
        "target_5": target_price(entry, 0.05, row, "target_5pct_price"),
        "target_10": target_price(entry, 0.10, row, "target_10pct_price"),
        "risk_pct": risk,
        "target_pct": target,
        "reward_risk": edge["reward_risk"],
        "expectancy_r": edge["expectancy_r"],
        "edge_label": edge["edge_label"],
        "timing_verdict": edge["timing_verdict"],
        "portfolio_math": edge["portfolio_math"],
        "volume": safe_float(row.get("relative_volume_15m") or row.get("relative_volume")),
        "gate": safe_text(row.get("alert_gate")) or "-",
        "entry_trigger": trigger,
        "mtf_alignment": safe_text(mtf_context.get("alignment")) or "-",
        "mtf_channel": safe_text(mtf_context.get("channel_type")) or "-",
        "mtf_duration": safe_text(mtf_context.get("estimated_duration")) or "-",
        "mtf_explanation": safe_text(mtf_context.get("explanation")) or "-",
        "macro_active": macro_active,
        "macro_context": macro_context or "-",
        "invalidation": f"Invalidar si pierde {stop:.2f}." if stop is not None else "No operar sin stop medible.",
        "what_is_missing": blocker_text(row),
        "why": why,
        "prediction_note": "Probabilidad operativa basada en checklist, R:R, EV y memoria; no es garantia.",
        "platform_mode": "Manual/preview only",
    }


def build_daily_opportunity_plan(
    opportunities: list[dict[str, Any]],
    *,
    source_freshness: dict[str, Any] | None = None,
    realtime_health: dict[str, Any] | None = None,
    market_session: dict[str, Any] | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    enriched: list[dict[str, Any]] = []
    for raw in opportunities or []:
        row = dict(raw)
        if source_freshness and "source_freshness" not in row:
            row["source_freshness"] = source_freshness
        if realtime_health and "realtime_health" not in row:
            row["realtime_health"] = realtime_health
        if market_session and "market_session" not in row:
            row["market_session"] = market_session
        enriched.append(build_daily_plan_row(row))

    enriched.sort(
        key=lambda item: (
            STAGE_ORDER.get(item["stage"], 99),
            -(item.get("probability") or 0),
            -(item.get("expectancy_r") or -999),
            -(item.get("readiness") or 0),
            item.get("symbol") or "",
        )
    )
    rows = enriched[:limit]
    counts: dict[str, int] = {}
    for item in rows:
        counts[item["stage"]] = counts.get(item["stage"], 0) + 1
    market_counts: dict[str, int] = {}
    for item in rows:
        market = safe_text(item.get("market")).lower() or "unknown"
        market_counts[market] = market_counts.get(market, 0) + 1
    top = rows[0] if rows else {}
    stage_counts = {stage: counts.get(stage, 0) for stage in STAGE_ORDER}
    summary = {
        "mode": "DAILY_OPPORTUNITY_PLAN_24H",
        "status": "OK",
        "status_reason": "Plan 24h generado con contrato completo.",
        "total": len(rows),
        "stage_counts": stage_counts,
        "market_counts": market_counts,
        "top": {
            "symbol": top.get("symbol", "-") if top else "-",
            "market": top.get("market", "-") if top else "-",
            "stage": top.get("stage", "-") if top else "-",
            "stage_label": top.get("stage_label", "-") if top else "-",
            "probability": top.get("probability") if top else None,
            "expectancy_r": top.get("expectancy_r") if top else None,
            "edge_label": top.get("edge_label", "-") if top else "-",
            "decision": top.get("decision", "-") if top else "-",
            "timing_verdict": top.get("timing_verdict", "-") if top else "-",
            "entry_trigger": top.get("entry_trigger", "-") if top else "-",
            "what_is_missing": top.get("what_is_missing", "-") if top else "-",
        },
        "next_action": (
            "Revisar tickets manuales en plataforma"
            if counts.get("OPERAR_AHORA", 0)
            else "Vigilar gatillos 15m de proximas entradas"
            if counts.get("PROXIMA_ENTRADA", 0)
            else "Mantener watchlist y esperar mejor estructura"
            if counts.get("VIGILAR", 0)
            else "Esperar datos realtime operables"
            if counts.get("ESPERAR_DATOS", 0)
            else "No operar hasta que cambie la estructura"
        ),
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "DAILY_OPPORTUNITY_PLAN_24H",
        "status": "OK",
        "status_reason": "Plan 24h generado con contrato completo.",
        "total": len(rows),
        "operar_ahora": counts.get("OPERAR_AHORA", 0),
        "proxima_entrada": counts.get("PROXIMA_ENTRADA", 0),
        "vigilar": counts.get("VIGILAR", 0),
        "esperar_datos": counts.get("ESPERAR_DATOS", 0),
        "no_operar": counts.get("NO_OPERAR", 0),
        "top_symbol": top.get("symbol", "-") if top else "-",
        "top_stage": top.get("stage", "-") if top else "-",
        "top_probability": top.get("probability") if top else None,
        "top_expectancy_r": top.get("expectancy_r") if top else None,
        "top_edge_label": top.get("edge_label", "-") if top else "-",
        "summary": summary,
        "stage_counts": stage_counts,
        "market_counts": market_counts,
        "source_freshness": source_freshness or {},
        "realtime_health": realtime_health or {},
        "market_session": market_session or {},
        "alert_policy": "Solo alertar cuando 1h confirma, 15m da entrada, volumen acompana, stop/target son medibles y el EV es positivo.",
        "prediction_policy": "Roxy busca un balance tipo cartera: aceptar riesgo cuando probabilidad y R:R dan expectativa positiva; la compra real sigue manual/paper.",
        "opportunities": rows,
        "rows": rows,
    }


def daily_plan_text_lines(plan: dict[str, Any], *, limit: int = 5) -> list[str]:
    rows = plan.get("rows") or []
    if not rows:
        return ["Plan 24h: sin oportunidades medibles; Roxy sigue observando."]
    lines = [
        (
            "Plan 24h: "
            f"operar {plan.get('operar_ahora', 0)} | "
            f"proximas {plan.get('proxima_entrada', 0)} | "
            f"vigilar {plan.get('vigilar', 0)} | "
            f"no operar {plan.get('no_operar', 0)}"
        )
    ]
    for row in rows[:limit]:
        probability = row.get("probability")
        entry = safe_float(row.get("entry"))
        stop = safe_float(row.get("stop"))
        entry_text = f"{entry:.2f}" if entry is not None else "-"
        stop_text = f"{stop:.2f}" if stop is not None else "-"
        lines.append(
            "- "
            f"{row.get('market')} {row.get('symbol')} | {row.get('stage_label')} | "
            f"{row.get('decision')} | prob {probability}% | EV {row.get('expectancy_r')}R | entry {entry_text} stop {stop_text} | "
            f"{row.get('strategy')} | espera: {row.get('entry_trigger')}"
        )
    return lines
