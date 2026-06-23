from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from multitimeframe_rules import build_multitimeframe_context, multitimeframe_condition_checks
from natalia_strategy_rules import evaluate_natalia_strategy_rules
from options_strategy import best_option_contract
from salto_strategies import SALTO_STRATEGY_FAMILIES, normalize_salto_family
from trade_enrichment import build_trade_enrichment


TARGET_PCTS = (0.02, 0.05, 0.10)
MIN_REWARD_RISK = 1.0
MIN_MACRO_EVENT_REWARD_RISK = 1.5
MIN_MACRO_EVENT_SCORE = 85
MIN_MACRO_EVENT_VOLUME = 1.1
MAX_SMA20_EXTENSION = 0.08
FED_EVENT_HIGH_KEYWORDS = (
    "FOMC",
    "FED",
    "FEDERAL RESERVE",
    "POWELL",
    "RATE DECISION",
    "RATE HIKE",
    "RATE CUT",
    "FED FUNDS",
    "STATEMENT",
    "PRESS CONFERENCE",
    "DOT PLOT",
    "MINUTES",
)
FED_EVENT_MEDIUM_KEYWORDS = (
    "CPI",
    "PCE",
    "NFP",
    "JOBS",
    "PAYROLL",
    "INFLATION",
    "UNEMPLOYMENT",
    "GDP",
    "YIELD",
    "TREASURY",
)
CORE_STRATEGIES = (
    "Canal alcista",
    "Canal lateral",
    "Pullback",
    "Rebote en media",
    "Cruce de medias",
    "Tendencia bajista",
    *SALTO_STRATEGY_FAMILIES,
)


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


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except Exception:
        pass
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def is_execution_timeframe(value: Any) -> bool:
    text = safe_text(value).lower().replace(" ", "")
    return text in {"1m", "1min", "1minute", "5m", "5min", "5minute"}


def reward_risk_ratio(risk_pct: Any, target_pct: Any) -> float | None:
    risk = safe_float(risk_pct)
    target = safe_float(target_pct)
    if risk is None or target is None or risk <= 0:
        return None
    return target / risk


def macro_event_risk(source: dict[str, Any] | None) -> dict[str, Any]:
    """Detect FED/macro news context learned from the support class videos."""
    if not isinstance(source, dict):
        return {
            "active": False,
            "severity": "NONE",
            "label": "Sin evento macro",
            "detail": "No hay evento FED/macro detectado.",
            "keywords": [],
        }
    keys = (
        "macro_event",
        "fed_event",
        "event_risk",
        "risk_event",
        "news_event",
        "market_event",
        "calendar_event",
        "economic_event",
        "fomc_event",
        "event_label",
        "event_name",
        "headline",
        "headlines",
        "news_headline",
        "news_summary",
        "macro_context",
        "market_context",
        "notes",
    )
    text = " ".join(safe_text(source.get(key)) for key in keys).upper()
    explicit = any(safe_bool(source.get(key)) for key in ("macro_event", "fed_event", "event_risk", "risk_event"))
    high_hits = [keyword for keyword in FED_EVENT_HIGH_KEYWORDS if keyword in text]
    medium_hits = [keyword for keyword in FED_EVENT_MEDIUM_KEYWORDS if keyword in text]
    if explicit or high_hits:
        severity = "HIGH"
        active = True
        hits = high_hits or ["MACRO"]
    elif medium_hits:
        severity = "MEDIUM"
        active = True
        hits = medium_hits
    else:
        severity = "NONE"
        active = False
        hits = []

    if not active:
        detail = "No hay evento FED/macro detectado."
    elif severity == "HIGH":
        detail = (
            "Evento FED/macro fuerte: esperar reaccion inicial y exigir confirmacion limpia "
            "antes de operar."
        )
    else:
        detail = "Evento macro medio: bajar agresividad y confirmar volumen/riesgo antes de operar."
    return {
        "active": active,
        "severity": severity,
        "label": "Evento FED/macro" if active else "Sin evento macro",
        "detail": detail,
        "keywords": hits,
    }


def macro_event_confirmation_ok(
    macro_risk: dict[str, Any],
    *,
    confirmed_buy: bool,
    score: Any,
    reward_r: Any,
    volume: Any,
    higher_tf_ok: bool,
) -> tuple[bool, str]:
    if not bool((macro_risk or {}).get("active")):
        return True, "Sin evento FED/macro."
    score_value = safe_float(score) or 0.0
    reward_value = safe_float(reward_r)
    volume_value = safe_float(volume)
    clean = (
        confirmed_buy
        and higher_tf_ok
        and score_value >= MIN_MACRO_EVENT_SCORE
        and reward_value is not None
        and reward_value >= MIN_MACRO_EVENT_REWARD_RISK
        and volume_value is not None
        and volume_value >= MIN_MACRO_EVENT_VOLUME
    )
    if clean:
        return True, (
            f"Evento macro activo, pero confirmacion limpia: score {score_value:.0f}, "
            f"{reward_value:.2f}R, volumen {volume_value:.2f}x."
        )
    return False, (
        "Evento FED/macro activo: Roxy espera post-noticia o confirmacion mas fuerte "
        f"(score>={MIN_MACRO_EVENT_SCORE}, RR>={MIN_MACRO_EVENT_REWARD_RISK:.1f}R, "
        f"volumen>={MIN_MACRO_EVENT_VOLUME:.1f}x y 2h/4h sin bloqueo)."
    )


def strategy_family_from_setup(setup: str | None, *, trend_setup: str | None = None) -> str:
    setup_text = safe_text(setup).upper()
    trend_text = safe_text(trend_setup).upper()
    salto_family = normalize_salto_family(setup_text) or normalize_salto_family(trend_text)
    if salto_family:
        return salto_family
    if "DOWNTREND" in {setup_text, trend_text}:
        return "Tendencia bajista"
    if setup_text in {"REBOUND", "MEDIA_REBOUND", "SMA_REBOUND"} or "REBOTE" in setup_text:
        return "Rebote en media"
    if setup_text == "PULLBACK":
        return "Pullback"
    if setup_text == "TREND_CONTINUATION":
        return "Canal alcista"
    if setup_text == "EARLY_UPTREND":
        return "Cruce de medias"
    if setup_text == "NEUTRAL":
        return "Canal lateral"
    if setup_text in {"NO_DATA", "ERROR", "INSUFFICIENT_DATA"}:
        return "Sin data suficiente"
    return "Canal lateral"


def memory_note_for_strategy(memory: dict[str, Any] | None, strategy_family: str) -> dict[str, Any]:
    if not memory:
        return {"note": "Sin memoria suficiente para este setup todavia.", "bias": "neutral", "stats": {}}
    stats = (memory.get("strategy_stats") or {}).get(strategy_family, {})
    alerts = int(stats.get("alerts", 0) or 0)
    hit_2pct = int(stats.get("hit_2pct", 0) or 0)
    hit_5pct = int(stats.get("hit_5pct", 0) or 0)
    hit_10pct = int(stats.get("hit_10pct", 0) or 0)
    stops = int(stats.get("stops", 0) or 0)
    if alerts <= 0:
        note = "Sin historial de alertas para esta estrategia."
        bias = "neutral"
    else:
        hit_rate = hit_2pct / alerts
        stop_rate = stops / alerts
        note = (
            f"Memoria {strategy_family}: {alerts} alerta(s), "
            f"{hit_2pct} llegaron a 2%, {hit_5pct} a 5%, {hit_10pct} a 10%, {stops} tocaron stop."
        )
        if alerts >= 3 and stop_rate >= 0.50 and hit_rate < 0.35:
            bias = "negative"
            note += " Este setup queda penalizado hasta que vuelva a demostrar calidad."
        elif alerts >= 3 and hit_rate >= 0.50 and stop_rate <= 0.35:
            bias = "positive"
            note += " La memoria favorece este setup si las condiciones actuales confirman."
        else:
            bias = "neutral"
    return {
        "note": note,
        "bias": bias,
        "stats": {
            "alerts": alerts,
            "hit_2pct": hit_2pct,
            "hit_5pct": hit_5pct,
            "hit_10pct": hit_10pct,
            "stops": stops,
        },
    }


def nearest_option(options_df: pd.DataFrame, symbol: str) -> dict[str, Any]:
    if options_df.empty or "symbol" not in options_df.columns:
        return {}
    rows = options_df[options_df["symbol"].astype(str).str.upper().eq(symbol.upper())].copy()
    if rows.empty:
        return {}
    if "option_score" in rows.columns:
        rows["option_score"] = pd.to_numeric(rows["option_score"], errors="coerce")
    if "spread_pct" in rows.columns:
        rows["spread_pct"] = pd.to_numeric(rows["spread_pct"], errors="coerce")
    sort_cols = [col for col in ["option_decision", "option_score", "spread_pct", "dte"] if col in rows.columns]
    ascending = [True, False, True, True][: len(sort_cols)]
    if sort_cols:
        rows = rows.sort_values(sort_cols, ascending=ascending)
    return rows.iloc[0].to_dict()


def target_ladder(entry: Any, stop: Any) -> list[dict[str, Any]]:
    entry_value = safe_float(entry)
    stop_value = safe_float(stop)
    if entry_value is None or entry_value <= 0:
        return []
    risk_pct = None
    if stop_value is not None and 0 < stop_value < entry_value:
        risk_pct = (entry_value - stop_value) / entry_value
    rows = []
    for target_pct in TARGET_PCTS:
        target_price = entry_value * (1.0 + target_pct)
        reward_r = target_pct / risk_pct if risk_pct and risk_pct > 0 else None
        rows.append(
            {
                "target": f"{int(target_pct * 100)}%",
                "target_pct": target_pct,
                "target_price": target_price,
                "reward_r": reward_r,
            }
        )
    return rows


def price_text(value: Any) -> str:
    number = safe_float(value)
    return f"{number:.2f}" if number is not None else "-"


def non_negotiable_checks(setup: dict[str, Any], confluence: dict[str, Any]) -> list[dict[str, Any]]:
    close = safe_float(setup.get("close") or setup.get("entry") or confluence.get("entry"))
    open_ = safe_float(setup.get("open"))
    high = safe_float(setup.get("high"))
    low = safe_float(setup.get("low"))
    upper = safe_float(setup.get("bb_upper"))
    lower = safe_float(setup.get("bb_lower"))
    sma20 = safe_float(setup.get("sma20") or confluence.get("sma20"))
    sma40 = safe_float(setup.get("sma40") or confluence.get("sma40"))
    signal = safe_text(setup.get("signal") or confluence.get("signal")).upper()
    setup_name = safe_text(setup.get("setup") or confluence.get("trigger_setup")).upper()
    exposed = bool(close is not None and ((upper is not None and close > upper) or (lower is not None and close < lower)))

    candle_range = (high - low) if high is not None and low is not None and high > low else None
    candle_body = abs(close - open_) if close is not None and open_ is not None else None
    body_pct = candle_body / candle_range if candle_range and candle_body is not None else None
    full_candle = bool(body_pct is not None and body_pct >= 0.75)
    sma20_extension = (close - sma20) / sma20 if close is not None and sma20 and sma20 > 0 else None
    overextended = bool(sma20_extension is not None and sma20_extension > MAX_SMA20_EXTENSION)
    bullish_setup = signal != "AVOID" and setup_name not in {"DOWNTREND", "NEUTRAL", "NO_DATA", "ERROR"}
    lost_sma40 = bool(bullish_setup and close is not None and sma40 is not None and close < sma40)

    return [
        {
            "label": "No expuesto Bollinger",
            "passed": not exposed,
            "detail": "Fuera de banda; no perseguir" if exposed else "Dentro de bandas o sin exceso medible",
        },
        {
            "label": "No vela llena",
            "passed": not full_candle,
            "detail": f"Cuerpo {body_pct * 100:.0f}%" if body_pct is not None else "Sin vela completa medible",
        },
        {
            "label": "No perseguir extension",
            "passed": not overextended,
            "detail": (
                f"{sma20_extension * 100:.1f}% sobre SMA20; esperar pullback"
                if sma20_extension is not None
                else "Sin SMA20 medible"
            ),
        },
        {
            "label": "SMA40 sostiene canal",
            "passed": not lost_sma40,
            "detail": f"Precio {price_text(close)} debajo de SMA40 {price_text(sma40)}" if lost_sma40 else "SMA40 no rota o no aplica",
        },
    ]


def build_watch_plan(
    *,
    setup: dict[str, Any],
    confluence: dict[str, Any],
    setup_name: str,
    confluence_signal: str,
    trade_decision: str,
    risk_ok: bool,
    volume_ok: bool,
    target_ok: bool,
    backtest_eligible: bool,
    memory_bias: str | None,
) -> dict[str, Any]:
    close = safe_float(setup.get("close") or setup.get("entry") or confluence.get("entry"))
    sma20 = safe_float(setup.get("sma20"))
    sma40 = safe_float(setup.get("sma40"))
    sma100 = safe_float(setup.get("sma100"))
    sma200 = safe_float(setup.get("sma200"))
    rel_vol = safe_float(confluence.get("relative_volume_15m")) or safe_float(setup.get("relative_volume"))
    risk_pct = safe_float(confluence.get("risk_pct"))
    trigger_setup = safe_text(confluence.get("trigger_setup") or setup_name).upper()
    trend_setup = safe_text(confluence.get("trend_setup")).upper()
    salto_family = (
        normalize_salto_family(setup_name)
        or normalize_salto_family(trigger_setup)
        or normalize_salto_family(trend_setup)
        or normalize_salto_family(confluence.get("strategy_family"))
    )

    if salto_family:
        movement = (
            f"Esperar confirmacion de {salto_family}: cierre limpio, 15m/1h alineados, "
            "volumen acompanando y entrada manual cerca del cierre si el stop queda medible."
        )
    elif setup_name == "DOWNTREND" or (close is not None and sma200 is not None and close < sma200):
        movement = (
            f"Esperar recuperacion sobre SMA200 {price_text(sma200)} y luego que SMA20 cruce o se mantenga "
            f"sobre SMA40 {price_text(sma40)}."
        )
    elif setup_name == "PULLBACK" or trigger_setup == "PULLBACK":
        movement = (
            f"Esperar rebote en la zona SMA20/SMA40 ({price_text(sma20)} - {price_text(sma40)}), "
            "con cierre verde sobre SMA20."
        )
    elif setup_name == "TREND_CONTINUATION" or trend_setup == "TREND_CONTINUATION":
        movement = (
            f"Esperar continuacion alcista: cierre sobre SMA20 {price_text(sma20)} y ruptura del maximo reciente "
            "sin perder la estructura 20/40/100/200."
        )
    elif setup_name == "EARLY_UPTREND":
        movement = (
            f"Esperar confirmacion de cruce: SMA20 sobre SMA40 {price_text(sma40)}, precio sobre SMA20 "
            "y 1h manteniendo tendencia."
        )
    elif setup_name == "NEUTRAL":
        movement = (
            f"Esperar salida del canal: cierre sobre SMA20/SMA40 ({price_text(sma20)} - {price_text(sma40)}) "
            "con volumen, o rebote claro en soporte."
        )
    elif close is not None and sma20 is not None and close < sma20:
        movement = f"Esperar que el precio recupere SMA20 {price_text(sma20)} y confirme con cierre encima."
    else:
        movement = "Esperar vela de confirmacion: 15m en BUY, 1h en tendencia, volumen acompanando y stop medible."

    confirmations = []
    if confluence_signal != "BUY" or not trade_decision.startswith("TRADE_FOR"):
        confirmations.append("15m debe dar BUY y 1h debe mantenerse WATCH/BUY.")
    if not volume_ok:
        current = f" actual {rel_vol:.2f}x" if rel_vol is not None else ""
        confirmations.append(f"Volumen relativo debe ser >= 0.8x, ideal >= 1.1x{current}.")
    if not risk_ok:
        current = f" actual {risk_pct * 100:.2f}%" if risk_pct is not None else ""
        confirmations.append(f"Riesgo hasta stop debe quedar <= 3.5%{current}.")
    if not target_ok:
        confirmations.append("Target minimo de 2% debe ser viable antes de operar.")
    if not backtest_eligible:
        confirmations.append("El setup debe pasar el filtro de backtest.")
    if memory_bias == "negative":
        confirmations.append("La memoria debe dejar de penalizar esta estrategia.")
    if not confirmations:
        confirmations.append("Esperar gatillo limpio de entrada antes de perseguir el precio.")

    levels = []
    if close is not None:
        levels.append(f"Precio actual {price_text(close)}")
    if sma20 is not None:
        levels.append(f"SMA20 {price_text(sma20)}")
    if sma40 is not None:
        levels.append(f"SMA40 {price_text(sma40)}")
    if sma100 is not None:
        levels.append(f"SMA100 {price_text(sma100)}")
    if sma200 is not None:
        levels.append(f"SMA200 {price_text(sma200)}")

    return {
        "movement": movement,
        "confirmations": confirmations,
        "levels": levels,
        "summary": f"Movimiento esperado: {movement}",
    }


def build_decision_reason(
    *,
    action: str,
    decision: str,
    setup: dict[str, Any],
    confluence: dict[str, Any],
    setup_name: str,
    signal: str,
    confluence_signal: str,
    trade_decision: str,
    strategy_family: str,
    risk_ok: bool,
    volume_ok: bool,
    target_ok: bool,
    backtest_eligible: bool,
    memory_bias: str | None,
    watch_plan: dict[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    close = safe_float(setup.get("close") or setup.get("entry") or confluence.get("entry"))
    sma20 = safe_float(setup.get("sma20"))
    sma40 = safe_float(setup.get("sma40"))
    sma100 = safe_float(setup.get("sma100"))
    sma200 = safe_float(setup.get("sma200"))
    risk_pct = safe_float(confluence.get("risk_pct"))
    target_pct = safe_float(confluence.get("recommended_target_pct"))
    reward_r = reward_risk_ratio(risk_pct, target_pct)
    rel_vol = safe_float(confluence.get("relative_volume_15m")) or safe_float(setup.get("relative_volume"))

    structure = "Estructura de medias mixta."
    if None not in (close, sma20, sma40, sma100, sma200):
        if sma20 > sma40 > sma100 > sma200 and close > max(sma20, sma40, sma100, sma200):
            structure = "SMA20 > SMA40 > SMA100 > SMA200 y precio sobre todas las medias."
        elif close < sma200:
            structure = f"Precio {price_text(close)} debajo de SMA200 {price_text(sma200)}."
        elif sma20 > sma100 and close > sma200:
            structure = f"SMA20 {price_text(sma20)} sobre SMA100 {price_text(sma100)} y precio sobre SMA200."

    risk_line = f"Riesgo a stop {risk_pct * 100:.2f}%." if risk_pct is not None else "Riesgo no medible porque falta stop valido."
    target_line = f"Target minimo {target_pct * 100:.0f}% viable." if target_pct is not None else "Target minimo 2% no confirmado."
    rr_line = f"Reward/risk {reward_r:.2f}R." if reward_r is not None else "Reward/risk no medible por falta de riesgo u objetivo."
    volume_line = f"Volumen relativo {rel_vol:.2f}x." if rel_vol is not None else "Volumen relativo no disponible."

    if action in {"BUY_STOCK", "WATCH_CALL"}:
        title = "Por que BUY" if action == "BUY_STOCK" else "Por que mirar CALL"
        summary = (
            f"Roxy acepta {decision.lower()} porque la confluencia esta en {trade_decision or 'BUY'}, "
            "el riesgo esta medido y el objetivo minimo es viable."
        )
        bullets = [
            structure,
            "15m y 1h estan alineados para entrada." if confluence_signal == "BUY" else "La tendencia principal permite buscar entrada.",
            risk_line,
            target_line,
            rr_line,
            volume_line,
            "Backtest elegible." if backtest_eligible else "Backtest no confirmado; bajar tamano si se opera.",
        ]
        next_steps = [
            "No perseguir precio extendido; entrar cerca del plan.",
            "Invalidar si pierde el stop o si 15m deja de confirmar.",
            "Tomar parciales en 2%, 5% y 10% segun fuerza del movimiento.",
        ]
        tone = "buy"
    elif (
        action == "NO_TRADE"
        or signal == "AVOID"
        or confluence_signal == "AVOID"
        or trade_decision.startswith("NO_TRADE")
        or setup_name == "DOWNTREND"
    ):
        title = "Por que AVOID"
        missing = blockers[:4]
        if not missing:
            if not risk_ok:
                missing.append("Riesgo no pasa el filtro.")
            if not volume_ok:
                missing.append("Volumen no acompana.")
            if not target_ok:
                missing.append("Target minimo 2% no viable.")
            if not backtest_eligible:
                missing.append("Backtest no valida el setup.")
            if memory_bias == "negative":
                missing.append("La memoria de Roxy penaliza esta estrategia.")
        summary = f"Roxy evita operar porque {missing[0].lower() if missing else 'la entrada no esta limpia'}"
        bullets = [structure, risk_line, target_line, rr_line, volume_line] + missing
        next_steps = list(watch_plan.get("confirmations") or [])[:4]
        tone = "avoid"
    else:
        title = "Por que WATCH"
        summary = safe_text(watch_plan.get("summary")) or "Roxy espera una confirmacion mas limpia."
        bullets = [structure, risk_line, target_line, rr_line, volume_line]
        bullets.extend(list(watch_plan.get("confirmations") or [])[:4])
        next_steps = list(watch_plan.get("confirmations") or [])[:4]
        tone = "watch"

    return {
        "title": title,
        "summary": summary,
        "bullets": [item for item in bullets if safe_text(item)],
        "next_steps": [item for item in next_steps if safe_text(item)],
        "tone": tone,
    }


def build_decision_transition(
    *,
    action: str,
    signal: str,
    confluence_signal: str,
    trade_decision: str,
    condition_checks: list[dict[str, Any]],
    watch_plan: dict[str, Any],
    entry: Any,
    stop: Any,
) -> dict[str, Any]:
    failed = [item for item in condition_checks if not bool(item.get("passed"))]
    if action in {"BUY_STOCK", "WATCH_CALL"}:
        invalidation = [
            f"Pierde el stop {price_text(stop)} o cierra debajo del nivel de riesgo.",
            "15m deja de estar en BUY o 1h pierde la tendencia.",
            "Volumen se apaga antes de romper o continuar.",
            "El precio se extiende lejos de la entrada y baja el reward/risk.",
        ]
        return {
            "title": "Que invalidaria BUY",
            "status": "Entrada valida mientras estas condiciones sigan vivas.",
            "items": invalidation,
            "tone": "buy",
        }

    items = []
    for item in failed:
        label = safe_text(item.get("label"))
        detail = safe_text(item.get("detail"))
        if label:
            items.append(f"{label}: {detail or 'pendiente'}")
    if not items:
        items = list(watch_plan.get("confirmations") or [])
    if not items:
        items = ["Necesita gatillo limpio antes de cambiar a BUY."]

    target_signal = "BUY" if signal != "AVOID" and confluence_signal != "AVOID" else "WATCH/BUY"
    return {
        "title": "Que falta para BUY",
        "status": f"Roxy cambia cuando 15m/1h pasen a {target_signal} y el plan de riesgo/target sea valido.",
        "items": items[:5],
        "tone": "avoid" if signal == "AVOID" or confluence_signal == "AVOID" or trade_decision.startswith("NO_TRADE") else "watch",
    }


def strategy_explanation_lines(
    *,
    symbol: str,
    setup: dict[str, Any],
    confluence: dict[str, Any],
    strategy_family: str,
    memory_context: dict[str, Any],
) -> list[str]:
    close = safe_float(setup.get("close") or setup.get("entry"))
    sma20 = safe_float(setup.get("sma20"))
    sma40 = safe_float(setup.get("sma40"))
    sma100 = safe_float(setup.get("sma100"))
    sma200 = safe_float(setup.get("sma200"))
    risk_pct = safe_float(confluence.get("risk_pct"))
    rel_vol = safe_float(confluence.get("relative_volume_15m")) or safe_float(setup.get("relative_volume"))
    trigger_setup = safe_text(confluence.get("trigger_setup") or setup.get("setup")).upper()
    trend_setup = safe_text(confluence.get("trend_setup")).upper()
    trade_decision = safe_text(confluence.get("trade_decision")).upper()
    target_pct = safe_float(confluence.get("recommended_target_pct"))
    learned_strategy = safe_text(setup.get("learned_strategy"))
    learned_status = safe_text(setup.get("learned_strategy_status"))
    learned_trigger = safe_text(setup.get("learned_strategy_trigger"))
    learned_action = safe_text(setup.get("learned_strategy_action"))
    learned_reason = safe_text(setup.get("learned_strategy_reason"))

    lines = [f"Roxy esta leyendo {symbol.upper()} como {strategy_family}."]
    if learned_strategy:
        lines.append(
            f"Cerebro aprendido: {learned_strategy} esta en estado {learned_status or 'NO_MATCH'}; "
            f"gatillo observado: {learned_trigger or '-'}."
        )
        if learned_reason:
            lines.append(f"Razon de clase: {learned_reason}")
        if learned_action:
            lines.append(f"Movimiento que espera Roxy: {learned_action}")
    if None not in (close, sma20, sma40, sma100, sma200):
        if sma20 > sma40 > sma100 > sma200 and close > max(sma20, sma40, sma100, sma200):
            lines.append(
                "La estructura principal es alcista: SMA20 > SMA40 > SMA100 > SMA200 y el precio esta sobre todas las medias."
            )
        elif sma20 > sma100 and close > sma200:
            lines.append(
                "La media rapida de 20 esta sobre la media 100 y el precio se mantiene sobre SMA200; eso favorece busqueda de compra."
            )
        elif close < sma200:
            lines.append("El precio esta debajo de SMA200; Roxy bloquea compras hasta recuperar tendencia.")
        else:
            lines.append("Las medias no estan perfectamente alineadas; Roxy lo trata como espera o canal lateral.")
    if trigger_setup or trend_setup:
        lines.append(f"Confluencia: 15m={trigger_setup or '-'} y 1h={trend_setup or '-'}; decision={trade_decision or '-'}.")
    if strategy_family.startswith("Salto"):
        lines.append(
            "Regla de salto: no anticipar; validar cerca del cierre con stop medible, volumen y confirmacion multi-timeframe."
        )
    if rel_vol is not None:
        lines.append(f"Volumen relativo: {rel_vol:.2f}x contra su promedio; debe acompanar la entrada.")
    if risk_pct is not None:
        lines.append(f"Riesgo hasta stop: {risk_pct * 100:.2f}%; Roxy prefiere <= 3.50%.")
    if target_pct is not None:
        lines.append(f"Objetivo minimo viable del plan: {target_pct * 100:.0f}%.")
    note = safe_text(memory_context.get("note"))
    if note:
        lines.append(f"Aprendizaje: {note}")
    return lines


def risk_sizing(
    *,
    account_equity: float,
    account_risk_pct: float,
    entry: Any,
    stop: Any,
    option: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry_value = safe_float(entry)
    stop_value = safe_float(stop)
    risk_dollars = max(0.0, float(account_equity) * float(account_risk_pct))
    per_share_risk = None
    shares = 0
    notional = 0.0
    if entry_value is not None and stop_value is not None and 0 < stop_value < entry_value:
        per_share_risk = entry_value - stop_value
        shares = int(math.floor(risk_dollars / per_share_risk)) if per_share_risk > 0 else 0
        notional = shares * entry_value

    max_loss_per_contract = safe_float((option or {}).get("max_loss_per_contract"))
    contracts = 0
    option_max_loss = 0.0
    if max_loss_per_contract and max_loss_per_contract > 0:
        contracts = int(math.floor(risk_dollars / max_loss_per_contract))
        option_max_loss = contracts * max_loss_per_contract

    return {
        "account_equity": float(account_equity),
        "account_risk_pct": float(account_risk_pct),
        "risk_dollars": risk_dollars,
        "per_share_risk": per_share_risk,
        "shares": shares,
        "stock_notional": notional,
        "stock_position_pct": notional / account_equity if account_equity > 0 else None,
        "contracts": contracts,
        "option_max_loss": option_max_loss,
        "max_loss_per_contract": max_loss_per_contract,
    }


def operation_gate_status(condition_checks: list[dict[str, Any]], *, hard_block: bool = False) -> str:
    if hard_block:
        return "No operar"
    if condition_checks and all(bool(item.get("passed")) for item in condition_checks):
        return "Operar"
    return "Esperar"


def direct_trade_plan(
    *,
    action: str,
    decision: str,
    symbol: str,
    strategy_family: str,
    risk_pct: float | None,
    target_pct: float | None,
    option: dict[str, Any],
    watch_plan: dict[str, Any],
    blockers: list[str],
    condition_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    option_symbol = safe_text((option or {}).get("contractSymbol"))
    reward_r = reward_risk_ratio(risk_pct, target_pct)
    if action == "WATCH_CALL":
        status = "Mirar Call"
        product = "Call"
        tone = "buy"
        summary = safe_text(option.get("summary")) or (
            f"{symbol} califica como accion base; valida contrato, delta, spread, DTE, volumen, "
            "open interest y perdida maxima antes de entrar."
        )
        next_step = "Usar solo el contrato validado; si spread, liquidez o riesgo cambian, volver a Esperar."
    elif action == "BUY_STOCK":
        status = "Operar"
        product = "Accion"
        tone = "buy"
        summary = "Setup accionable: tendencia, entrada, stop y target minimo estan alineados."
        next_step = "Preparar orden manual cerca de entrada y colocar stop/targets inmediatamente."
    elif action == "NO_TRADE":
        status = "No operar"
        product = "Ninguno"
        tone = "avoid"
        summary = blockers[0] if blockers else "Roxy no ve estructura limpia para operar."
        next_step = safe_text(watch_plan.get("movement")) or "Esperar nuevo setup."
    else:
        status = "Esperar"
        product = "Observacion"
        tone = "watch"
        summary = safe_text(watch_plan.get("movement")) or "Falta confirmacion antes de operar."
        failed = [item for item in condition_checks if not bool(item.get("passed"))]
        next_step = safe_text(failed[0].get("detail")) if failed else "Esperar gatillo limpio."

    return {
        "status": status,
        "product": product,
        "tone": tone,
        "summary": summary,
        "next_step": next_step,
        "strategy": strategy_family,
        "risk_pct": risk_pct,
        "target_pct": target_pct,
        "reward_r": reward_r,
        "option_symbol": option_symbol,
        "option_professional_decision": option.get("professional_decision"),
        "option_contracts_by_risk": option.get("contracts_by_risk"),
        "option_risk_budget": option.get("risk_budget"),
        "option_max_loss_per_contract": option.get("max_loss_per_contract"),
        "display_decision": decision,
    }


def build_symbol_trade_brief(
    *,
    symbol: str,
    market: str,
    timeframe: str,
    setup: dict[str, Any],
    confluence: dict[str, Any] | None = None,
    options_df: pd.DataFrame | None = None,
    account_equity: float = 10000.0,
    account_risk_pct: float = 0.01,
    memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    confluence = confluence or {}
    options_df = options_df if options_df is not None else pd.DataFrame()
    signal = safe_text(setup.get("signal")).upper()
    setup_name = safe_text(setup.get("setup")).upper()
    confluence_signal = safe_text(confluence.get("signal")).upper()
    trade_decision = safe_text(confluence.get("trade_decision")).upper()
    entry = safe_float(confluence.get("entry")) or safe_float(setup.get("entry") or setup.get("close"))
    stop = safe_float(confluence.get("stop")) or safe_float(setup.get("stop"))
    risk_pct = safe_float(confluence.get("risk_pct"))
    if risk_pct is None and entry and stop and 0 < stop < entry:
        risk_pct = (entry - stop) / entry
    score = safe_float(confluence.get("confluence_score")) or safe_float(setup.get("score")) or 0.0
    relative_volume = safe_float(confluence.get("relative_volume_15m")) or safe_float(setup.get("relative_volume"))
    backtest_eligible = safe_bool(confluence.get("backtest_eligible") if confluence else setup.get("backtest_eligible"))
    target_pct = safe_float(confluence.get("recommended_target_pct"))
    option = (
        best_option_contract(
            options_df,
            symbol,
            account_equity=account_equity,
            risk_pct=account_risk_pct,
            target_pct=target_pct,
        )
        if market == "stock"
        else {}
    )
    option_score = safe_float(option.get("option_score"))
    option_decision = safe_text(option.get("option_decision")).upper()
    professional_option_decision = safe_text(option.get("professional_decision")).upper()
    learned_strategy = safe_text(setup.get("learned_strategy"))
    learned_status = safe_text(setup.get("learned_strategy_status")).upper()
    learned_action = safe_text(setup.get("learned_strategy_action"))
    learned_reason = safe_text(setup.get("learned_strategy_reason"))
    learned_trigger = safe_text(setup.get("learned_strategy_trigger"))

    confirmed_buy = confluence_signal == "BUY" and trade_decision.startswith("TRADE_FOR")
    setup_buy = signal == "BUY"
    risk_ok = risk_pct is not None and risk_pct <= 0.035
    volume_ok = relative_volume is None or relative_volume >= 0.8
    target_ok = target_pct is not None and target_pct >= 0.02
    reward_r = reward_risk_ratio(risk_pct, target_pct)
    reward_r_ok = reward_r is not None and reward_r >= MIN_REWARD_RISK
    confluence = {
        **confluence,
        "risk_pct": risk_pct,
        "recommended_target_pct": target_pct,
        "reward_r": reward_r,
    }
    option_ok = professional_option_decision == "MIRAR_CALL" and (option_score or 0) >= 70
    strategy_family = (
        normalize_salto_family(setup.get("strategy_family"))
        or normalize_salto_family(setup.get("salto_family"))
        or normalize_salto_family(confluence.get("strategy_family"))
        or normalize_salto_family(confluence.get("salto_family"))
        or strategy_family_from_setup(setup_name, trend_setup=confluence.get("trend_setup"))
    )
    memory_context = memory_note_for_strategy(memory, strategy_family)
    memory_bias = memory_context.get("bias")
    trend_score = safe_float(confluence.get("trend_score"))
    trigger_score = safe_float(confluence.get("trigger_score"))
    one_hour_ok = confirmed_buy or (trend_score is not None and trend_score >= 70)
    fifteen_ok = confirmed_buy or (confluence_signal == "BUY" and (trigger_score is None or trigger_score >= 65))
    execution_tf = is_execution_timeframe(timeframe)
    htf_bias = safe_text(confluence.get("higher_tf_bias")).upper()
    htf_present = any(
        key in confluence
        for key in (
            "higher_tf_bias",
            "higher_tf_confirmations",
            "higher_tf_blocks",
            "htf_2h_signal",
            "htf_4h_signal",
        )
    )
    htf_ok = not htf_present or htf_bias in {"CONFIRMED", "PARTIAL"}
    htf_detail = "Sin bloqueo 2h/4h"
    if htf_present:
        confirmations = safe_float(confluence.get("higher_tf_confirmations"))
        blocks = safe_float(confluence.get("higher_tf_blocks"))
        if htf_bias == "CONFIRMED":
            htf_detail = f"Confirmado {int(confirmations or 0)}/2"
        elif htf_bias == "PARTIAL":
            htf_detail = f"Parcial {int(confirmations or 0)}/2"
        elif htf_bias == "BLOCKED":
            htf_detail = f"Bloqueado {int(blocks or 0)}/2"
        else:
            htf_detail = "Falta data 2h/4h"
    mtf_source = {
        **setup,
        **confluence,
        "symbol": symbol,
        "market": market,
        "timeframe": timeframe,
        "strategy_family": strategy_family,
    }
    mtf_context = build_multitimeframe_context(mtf_source)
    mtf_alignment = safe_text(mtf_context.get("alignment")).upper()
    execution_timing_ok = not execution_tf or (confirmed_buy and one_hour_ok and htf_ok)
    macro_risk = macro_event_risk(mtf_source)
    macro_ok, macro_detail = macro_event_confirmation_ok(
        macro_risk,
        confirmed_buy=confirmed_buy,
        score=score,
        reward_r=reward_r,
        volume=relative_volume,
        higher_tf_ok=htf_ok,
    )
    natalia_rules = evaluate_natalia_strategy_rules(setup, confluence)

    blockers: list[str] = []
    if setup_name == "DOWNTREND" or signal == "AVOID":
        blockers.append("La estructura esta bajista o debajo del filtro de medias.")
    if not confirmed_buy:
        blockers.append("La confluencia 15m/1h todavia no confirma una entrada.")
    if htf_present and not htf_ok:
        if htf_bias == "BLOCKED":
            blockers.append("Las temporalidades 2h/4h contradicen el gatillo actual.")
        else:
            blockers.append("Falta confirmacion 2h/4h para validar el salto.")
    if mtf_alignment == "BLOCKED":
        blockers.append("El mapa multitemporal indica que 15m no debe operar contra el canal mayor.")
    if not execution_timing_ok:
        blockers.append("1m/5m solo sirve para afinar entrada; no autoriza comprar sin 15m/1h/2h/4h alineados.")
    if not macro_ok:
        blockers.append(macro_detail)
    if risk_pct is None:
        blockers.append("No hay stop valido para medir riesgo.")
    elif not risk_ok:
        blockers.append("El stop queda demasiado lejos para una entrada limpia.")
    if not volume_ok:
        blockers.append("El volumen relativo no acompana la entrada.")
    if risk_pct is not None and target_pct is not None and not reward_r_ok:
        blockers.append(
            f"Reward/risk no compensa: el objetivo paga {reward_r:.2f}R y Roxy exige minimo {MIN_REWARD_RISK:.1f}R."
        )
    no_negotiables = non_negotiable_checks(setup, confluence)
    no_negotiables_ok = all(bool(item.get("passed")) for item in no_negotiables)
    for item in no_negotiables:
        if not bool(item.get("passed")):
            blockers.append(f"No negociable: {item.get('label')} ({item.get('detail')}).")
    if not backtest_eligible:
        blockers.append("El filtro historico todavia no valida este setup.")
    if memory_bias == "negative":
        blockers.append("La memoria de Roxy penaliza esta estrategia por resultados debiles recientes.")
    if learned_status == "BLOCKED":
        blockers.append("La estrategia aprendida de las clases esta bloqueada en esta grafica.")
    if natalia_rules.get("hard_block"):
        blockers.append(f"Reglas Natalia: {safe_text(natalia_rules.get('summary'))}")
    elif natalia_rules.get("wait_block"):
        blockers.append(f"Reglas Natalia piden espera: {safe_text(natalia_rules.get('summary'))}")

    condition_checks = [
        {
            "label": "1h confirma",
            "passed": one_hour_ok,
            "detail": f"Score tendencia {trend_score:.0f}" if trend_score is not None else "Esperando confirmacion 1h",
        },
        {
            "label": "15m da entrada",
            "passed": fifteen_ok,
            "detail": trade_decision or confluence_signal or "Sin gatillo intradia",
        },
        {
            "label": "1m/5m solo timing",
            "passed": execution_timing_ok,
            "detail": (
                "Marco mayor ya valida; usar 1m/5m solo para precision"
                if execution_tf and execution_timing_ok
                else "No usar 1m/5m como gatillo principal"
                if execution_tf
                else "No aplica"
            ),
        },
        {
            "label": "2h/4h validan",
            "passed": htf_ok,
            "detail": htf_detail,
        },
        {
            "label": "Evento FED/macro",
            "passed": macro_ok,
            "detail": macro_detail,
        },
        {
            "label": "Volumen acompana",
            "passed": volume_ok,
            "detail": f"{relative_volume:.2f}x" if relative_volume is not None else "No disponible",
        },
        {
            "label": "Riesgo bajo",
            "passed": risk_ok,
            "detail": f"{risk_pct * 100:.2f}%" if risk_pct is not None else "Sin stop valido",
        },
        {
            "label": "Target 2% viable",
            "passed": target_ok,
            "detail": f"{target_pct * 100:.0f}%" if target_pct is not None else "Sin objetivo confirmado",
        },
        {
            "label": "Reward/Risk viable",
            "passed": reward_r_ok,
            "detail": f"{reward_r:.2f}R" if reward_r is not None else "Falta riesgo/target",
        },
        {
            "label": "Filtro historico",
            "passed": backtest_eligible,
            "detail": "Backtest elegible" if backtest_eligible else "No validado por backtest",
        },
        {
            "label": "Memoria sana",
            "passed": memory_bias != "negative",
            "detail": safe_text(memory_context.get("note")),
        },
    ]
    if market == "stock" and option:
        condition_checks.append(
            {
                "label": "Call profesional",
                "passed": option_ok,
                "detail": safe_text(option.get("summary"))
                or safe_text(option.get("human_decision"))
                or "Contrato de opcion no validado",
            }
        )
    condition_checks.extend(no_negotiables)
    condition_checks.extend(multitimeframe_condition_checks(mtf_source))
    if learned_strategy:
        condition_checks.append(
            {
                "label": "Clase/estrategia",
                "passed": learned_status in {"ACTIVE", "WATCH", ""},
                "detail": f"{learned_strategy} · {learned_status or 'NO_MATCH'}",
            }
        )
    condition_checks.append(
        {
            "label": "Reglas Natalia",
            "passed": not bool(natalia_rules.get("hard_block") or natalia_rules.get("wait_block")),
            "detail": safe_text(natalia_rules.get("summary")) or "Filtro aprendido sin bloqueos",
        }
    )
    operation_status = operation_gate_status(
        condition_checks,
        hard_block=setup_name == "DOWNTREND"
        or signal == "AVOID"
        or htf_bias == "BLOCKED"
        or mtf_alignment == "BLOCKED"
        or not macro_ok
        or not no_negotiables_ok
        or bool(natalia_rules.get("hard_block"))
        or memory_bias == "negative",
    )
    watch_plan = build_watch_plan(
        setup=setup,
        confluence=confluence,
        setup_name=setup_name,
        confluence_signal=confluence_signal,
        trade_decision=trade_decision,
        risk_ok=risk_ok,
        volume_ok=volume_ok,
        target_ok=target_ok,
        backtest_eligible=backtest_eligible,
        memory_bias=memory_bias,
    )
    if execution_tf:
        timing_note = "1m/5m solo afina el precio de entrada; la decision real depende de 15m, 1h, 2h/4h, volumen, riesgo y target."
        watch_plan["confirmations"] = [timing_note] + list(watch_plan.get("confirmations") or [])
        if not execution_timing_ok:
            watch_plan["movement"] = timing_note
            watch_plan["summary"] = f"Movimiento esperado: {timing_note}"
    if natalia_rules.get("hard_block"):
        watch_plan["movement"] = safe_text(natalia_rules.get("movement")) or watch_plan["movement"]
        watch_plan["summary"] = f"Movimiento esperado: {watch_plan['movement']}"
        watch_plan["confirmations"] = list(natalia_rules.get("reasons") or []) + list(watch_plan.get("confirmations") or [])
    elif natalia_rules.get("wait_block"):
        watch_plan["confirmations"] = list(natalia_rules.get("reasons") or []) + list(watch_plan.get("confirmations") or [])

    if (
        market == "stock"
        and confirmed_buy
        and execution_timing_ok
        and htf_ok
        and macro_ok
        and risk_ok
        and volume_ok
        and backtest_eligible
        and target_ok
        and reward_r_ok
        and no_negotiables_ok
        and not natalia_rules.get("hard_block")
        and not natalia_rules.get("wait_block")
        and option_ok
        and memory_bias != "negative"
    ):
        decision = "Mirar call"
        action = "WATCH_CALL"
    elif (
        confirmed_buy
        and execution_timing_ok
        and htf_ok
        and macro_ok
        and risk_ok
        and volume_ok
        and backtest_eligible
        and target_ok
        and reward_r_ok
        and no_negotiables_ok
        and not natalia_rules.get("hard_block")
        and not natalia_rules.get("wait_block")
        and memory_bias != "negative"
    ):
        decision = "Comprar accion"
        action = "BUY_STOCK"
    elif natalia_rules.get("hard_block"):
        decision = "No operar"
        action = "NO_TRADE"
    elif setup_buy or confluence_signal == "WATCH" or score >= 55:
        decision = "Esperar"
        action = "WAIT"
    else:
        decision = "No operar"
        action = "NO_TRADE"

    enrichment = build_trade_enrichment(
        symbol=symbol,
        market=market,
        timeframe=timeframe,
        setup=setup,
        confluence=confluence,
        option=option,
        memory_context=memory_context,
        strategy_family=strategy_family,
        decision=decision,
        action=action,
        risk_pct=risk_pct,
        target_pct=target_pct,
        reward_r=reward_r,
        relative_volume=relative_volume,
    )
    enrichment_summary = safe_text(enrichment.get("summary"))

    if action in {"BUY_STOCK", "WATCH_CALL"}:
        reasons = [
            "1h y 15m estan alineados para una posible entrada.",
            "El stop permite medir riesgo antes de operar.",
            "El objetivo minimo de 2% es viable segun el plan.",
            f"El reward/risk paga {reward_r:.2f}R o mejor.",
        ]
        if htf_present:
            reasons.append(f"Contexto 2h/4h: {htf_detail}.")
        if bool(macro_risk.get("active")):
            reasons.append(macro_detail)
        reasons.append(safe_text(mtf_context.get("explanation")))
        if relative_volume is not None:
            reasons.append(f"Volumen relativo actual: {relative_volume:.2f}x.")
    else:
        reasons = [watch_plan["summary"]] + (blockers[:4] or ["Esperar una confirmacion mas limpia antes de operar."])
        reasons.append(safe_text(mtf_context.get("explanation")))
    if learned_strategy:
        reasons.append(
            f"Estrategia aprendida: {learned_strategy}. "
            f"{learned_reason or learned_action or learned_trigger or 'Roxy la usa como contexto de decision.'}"
        )
    reasons.append(f"Reglas Natalia: {safe_text(natalia_rules.get('summary'))}")
    if execution_tf:
        reasons.append(
            "Timing aprendido: 1m/5m no decide la operacion; solo ayuda a entrar fino cuando 15m/1h/2h/4h ya validaron."
        )
    if enrichment_summary:
        reasons.append(f"Capa enriquecida: {enrichment_summary}")
    reasons.append(str(memory_context.get("note")))

    sizing = risk_sizing(
        account_equity=account_equity,
        account_risk_pct=account_risk_pct,
        entry=entry,
        stop=stop,
        option=option,
    )
    explanation_lines = strategy_explanation_lines(
        symbol=symbol,
        setup=setup,
        confluence=confluence,
        strategy_family=strategy_family,
        memory_context=memory_context,
    )
    mtf_explanation = safe_text(mtf_context.get("explanation"))
    if mtf_explanation and mtf_explanation not in explanation_lines:
        explanation_lines.insert(1, mtf_explanation)
    if enrichment_summary:
        explanation_lines.append(f"Enriquecimiento aprendido: {enrichment_summary}")
    explanation_lines.append(f"Reglas Natalia activas: {safe_text(natalia_rules.get('movement'))}")
    decision_reason = build_decision_reason(
        action=action,
        decision=decision,
        setup=setup,
        confluence=confluence,
        setup_name=setup_name,
        signal=signal,
        confluence_signal=confluence_signal,
        trade_decision=trade_decision,
        strategy_family=strategy_family,
        risk_ok=risk_ok,
        volume_ok=volume_ok,
        target_ok=target_ok,
        backtest_eligible=backtest_eligible,
        memory_bias=memory_bias,
        watch_plan=watch_plan,
        blockers=blockers,
    )
    decision_transition = build_decision_transition(
        action=action,
        signal=signal,
        confluence_signal=confluence_signal,
        trade_decision=trade_decision,
        condition_checks=condition_checks,
        watch_plan=watch_plan,
        entry=entry,
        stop=stop,
    )
    direct_plan = direct_trade_plan(
        action=action,
        decision=decision,
        symbol=symbol,
        strategy_family=strategy_family,
        risk_pct=risk_pct,
        target_pct=target_pct,
        option=option,
        watch_plan=watch_plan,
        blockers=blockers,
        condition_checks=condition_checks,
    )
    direct_plan = {
        **direct_plan,
        "enrichment_summary": enrichment_summary,
        "execution_rule": (enrichment.get("operator_rules") or [""])[0],
    }

    return {
        "symbol": symbol,
        "market": market,
        "timeframe": timeframe,
        "decision": decision,
        "action": action,
        "strategy_family": strategy_family,
        "core_strategies": list(CORE_STRATEGIES),
        "signal": signal,
        "setup": setup_name,
        "confluence_signal": confluence_signal or "-",
        "trade_decision": trade_decision or "-",
        "score": max(0.0, score - 8.0) if memory_bias == "negative" else score,
        "entry": entry,
        "stop": stop,
        "risk_pct": risk_pct,
        "relative_volume": relative_volume,
        "backtest_eligible": backtest_eligible,
        "higher_tf_bias": htf_bias or "-",
        "higher_tf_detail": htf_detail,
        "macro_event_risk": macro_risk,
        "multitimeframe": mtf_context,
        "target_ladder": target_ladder(entry, stop),
        "recommended_target_pct": target_pct,
        "recommended_target_price": safe_float(confluence.get("recommended_target_price")),
        "option": option,
        "sizing": sizing,
        "reasons": reasons,
        "watch_plan": watch_plan,
        "direct_plan": direct_plan,
        "decision_reason": decision_reason,
        "decision_transition": decision_transition,
        "strategy_explanation": explanation_lines,
        "teaching_note": " ".join(explanation_lines[:4]),
        "blockers": blockers,
        "memory": memory_context,
        "enrichment": enrichment,
        "enrichment_checks": enrichment.get("checks", []),
        "natalia_rules": natalia_rules,
        "condition_checks": condition_checks,
        "operation_status": operation_status,
        "learned_strategy": {
            "name": learned_strategy or "-",
            "status": learned_status or "-",
            "trigger": learned_trigger or "-",
            "action": learned_action or "-",
            "reason": learned_reason or "-",
            "score": safe_float(setup.get("learned_strategy_score")),
            "requirements": setup.get("learned_strategy_requirements") or [],
            "timeframes": setup.get("learned_strategy_timeframes") or [],
        },
    }


def summarize_backtest_by_strategy(trades_df: pd.DataFrame) -> pd.DataFrame:
    if trades_df.empty or "entry_setup" not in trades_df.columns:
        return pd.DataFrame(
            columns=[
                "strategy_family",
                "trades",
                "win_rate",
                "hit_2pct_rate",
                "hit_5pct_rate",
                "hit_10pct_rate",
                "stop_rate",
                "total_pnl",
                "avg_return_pct",
                "profit_factor",
            ]
        )
    data = trades_df.copy()
    data["strategy_family"] = data["entry_setup"].apply(strategy_family_from_setup)
    if "pnl" not in data.columns:
        data["pnl"] = 0.0
    if "return_pct" not in data.columns:
        data["return_pct"] = 0.0
    data["pnl"] = pd.to_numeric(data["pnl"], errors="coerce").fillna(0.0)
    data["return_pct"] = pd.to_numeric(data["return_pct"], errors="coerce").fillna(0.0)
    rows = []
    for family, group in data.groupby("strategy_family"):
        wins = group[group["pnl"] > 0]
        losses = group[group["pnl"] <= 0]
        gross_profit = float(wins["pnl"].sum())
        gross_loss = abs(float(losses["pnl"].sum()))
        hit_2pct = group[group["return_pct"] >= 0.02]
        hit_5pct = group[group["return_pct"] >= 0.05]
        hit_10pct = group[group["return_pct"] >= 0.10]
        if "exit_reason" in group.columns:
            stops = group[group["exit_reason"].astype(str).str.upper().str.contains("STOP", na=False)]
        else:
            stops = pd.DataFrame()
        if gross_loss == 0:
            profit_factor = float("inf") if gross_profit > 0 else 0.0
        else:
            profit_factor = gross_profit / gross_loss
        rows.append(
            {
                "strategy_family": family,
                "trades": int(len(group)),
                "win_rate": len(wins) / len(group) if len(group) else 0.0,
                "hit_2pct": int(len(hit_2pct)),
                "hit_5pct": int(len(hit_5pct)),
                "hit_10pct": int(len(hit_10pct)),
                "stops": int(len(stops)),
                "hit_2pct_rate": len(hit_2pct) / len(group) if len(group) else 0.0,
                "hit_5pct_rate": len(hit_5pct) / len(group) if len(group) else 0.0,
                "hit_10pct_rate": len(hit_10pct) / len(group) if len(group) else 0.0,
                "stop_rate": len(stops) / len(group) if len(group) else 0.0,
                "total_pnl": float(group["pnl"].sum()),
                "avg_return_pct": float(group["return_pct"].mean()) if len(group) else 0.0,
                "profit_factor": profit_factor,
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["profit_factor", "total_pnl", "trades"], ascending=[False, False, False]).reset_index(drop=True)


def summarize_backtest_performance(
    trades_df: pd.DataFrame,
    *,
    group_cols: list[str] | None = None,
    starting_equity: float = 10_000.0,
) -> pd.DataFrame:
    columns = [
        "strategy_family",
        "timeframe",
        "symbol",
        "source",
        "trades",
        "wins",
        "losses",
        "win_rate",
        "profit_factor",
        "max_drawdown",
        "max_drawdown_pct",
        "avg_r",
        "total_r",
        "avg_return_pct",
        "total_pnl",
        "expectancy",
        "tone",
    ]
    if trades_df.empty:
        return pd.DataFrame(columns=columns)
    data = trades_df.copy()
    if "strategy_family" not in data.columns:
        if "entry_setup" in data.columns:
            data["strategy_family"] = data["entry_setup"].apply(strategy_family_from_setup)
        elif "setup" in data.columns:
            data["strategy_family"] = data["setup"].apply(strategy_family_from_setup)
        else:
            data["strategy_family"] = "Sin clasificar"
    if "timeframe" not in data.columns:
        data["timeframe"] = data.get("tf", "-")
    if "symbol" not in data.columns:
        data["symbol"] = "-"
    if "source" not in data.columns:
        data["source"] = data.get("data_source", "-")
    if "pnl" not in data.columns:
        data["pnl"] = 0.0
    if "return_pct" not in data.columns:
        data["return_pct"] = 0.0
    data["pnl"] = pd.to_numeric(data["pnl"], errors="coerce").fillna(0.0)
    data["return_pct"] = pd.to_numeric(data["return_pct"], errors="coerce").fillna(0.0)
    if "r_multiple" in data.columns:
        data["r_multiple"] = pd.to_numeric(data["r_multiple"], errors="coerce")
    elif "risk_dollars" in data.columns:
        risk = pd.to_numeric(data["risk_dollars"], errors="coerce").replace(0, pd.NA)
        data["r_multiple"] = data["pnl"] / risk
    else:
        data["r_multiple"] = pd.NA

    groups = group_cols or ["strategy_family", "timeframe"]
    for column in groups:
        if column not in data.columns:
            data[column] = "-"
    rows: list[dict[str, Any]] = []
    for key, group in data.groupby(groups, dropna=False):
        key_values = key if isinstance(key, tuple) else (key,)
        group_info = {column: safe_text(value) or "-" for column, value in zip(groups, key_values)}
        wins = group[group["pnl"] > 0]
        losses = group[group["pnl"] <= 0]
        gross_profit = float(wins["pnl"].sum())
        gross_loss = abs(float(losses["pnl"].sum()))
        profit_factor = float("inf") if gross_loss == 0 and gross_profit > 0 else 0.0 if gross_loss == 0 else gross_profit / gross_loss
        equity_curve = float(starting_equity) + group["pnl"].cumsum()
        peak = equity_curve.cummax()
        drawdown = (peak - equity_curve).fillna(0.0)
        max_drawdown = float(drawdown.max()) if not drawdown.empty else 0.0
        max_drawdown_pct = max_drawdown / float(starting_equity) if starting_equity else 0.0
        r_values = pd.to_numeric(group["r_multiple"], errors="coerce").dropna()
        avg_r = float(r_values.mean()) if not r_values.empty else 0.0
        total_r = float(r_values.sum()) if not r_values.empty else 0.0
        win_rate = len(wins) / len(group) if len(group) else 0.0
        expectancy = float(group["pnl"].mean()) if len(group) else 0.0
        tone = "buy" if len(group) >= 10 and win_rate >= 0.48 and profit_factor >= 1.2 and avg_r > 0 else "avoid" if profit_factor < 1.0 or avg_r < 0 else "watch"
        row = {
            "strategy_family": "-",
            "timeframe": "-",
            "symbol": "-",
            "source": "-",
            **group_info,
            "trades": int(len(group)),
            "wins": int(len(wins)),
            "losses": int(len(losses)),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else profit_factor,
            "max_drawdown": round(max_drawdown, 4),
            "max_drawdown_pct": round(max_drawdown_pct, 6),
            "avg_r": round(avg_r, 4),
            "total_r": round(total_r, 4),
            "avg_return_pct": round(float(group["return_pct"].mean()) if len(group) else 0.0, 6),
            "total_pnl": round(float(group["pnl"].sum()), 4),
            "expectancy": round(expectancy, 4),
            "tone": tone,
        }
        rows.append(row)
    out = pd.DataFrame(rows, columns=columns)
    if out.empty:
        return out
    tone_rank = {"buy": 0, "watch": 1, "avoid": 2}
    out["_tone_rank"] = out["tone"].map(tone_rank).fillna(1)
    return (
        out.sort_values(["_tone_rank", "profit_factor", "avg_r", "trades"], ascending=[True, False, False, False])
        .drop(columns=["_tone_rank"])
        .reset_index(drop=True)
    )


def latest_backtest_trades(pattern: str = "output/ma_backtest_trades_*.csv") -> tuple[str | None, pd.DataFrame]:
    files = sorted(Path().glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        return None, pd.DataFrame()
    path = files[0]
    try:
        return str(path), pd.read_csv(path)
    except Exception:
        return str(path), pd.DataFrame()
