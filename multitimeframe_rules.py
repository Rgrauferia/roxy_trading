from __future__ import annotations

from typing import Any


TREND_DURATION = "1-3 meses aprox"

CHANNEL_DURATION_RULES = {
    "ALCISTA": {
        "canal alcista largo plazo": "10-12 dias aprox",
        "canal alcista corto plazo": "5-8 dias aprox",
        "canal bajista": "5-8 dias aprox",
        "canal lateral": "5-8 dias aprox",
    },
    "BAJISTA": {
        "canal bajista largo plazo": "10-12 dias aprox",
        "canal bajista corto plazo": "5-8 dias aprox",
        "canal alcista": "5-8 dias aprox",
        "canal lateral": "5-8 dias aprox",
    },
    "LATERAL": {
        "canal alcista piso a techo": "10-12 dias aprox",
        "canal bajista techo a piso": "10-12 dias aprox",
        "canal alcista": "5-8 dias aprox",
        "canal bajista": "5-8 dias aprox",
        "canal lateral": "5-8 dias aprox",
    },
}

TIMEFRAME_CHAIN = [
    {
        "source_tf": "1w",
        "source_role": "Canal",
        "target_tf": "1d",
        "target_role": "Tendencia",
        "rule": "El canal semanal define la tendencia diaria.",
    },
    {
        "source_tf": "1d",
        "source_role": "Canal largo plazo",
        "target_tf": "1h",
        "target_role": "Tendencia largo plazo",
        "rule": "El canal diario largo define la tendencia de 1h.",
    },
    {
        "source_tf": "1h",
        "source_role": "Canal",
        "target_tf": "15m",
        "target_role": "Tendencia largo plazo",
        "rule": "El canal de 1h define si 15m puede ser gatillo.",
    },
]


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except Exception:
        pass
    return str(value or "").strip()


def normalize_regime(value: Any) -> str:
    text = safe_text(value).upper()
    if any(token in text for token in ("BAJISTA", "DOWNTREND", "BEAR", "AVOID", "NO_TRADE")):
        return "BAJISTA"
    if any(token in text for token in ("LATERAL", "NEUTRAL", "RANGO", "RANGE", "SIDEWAYS")):
        return "LATERAL"
    if any(token in text for token in ("ALCISTA", "UPTREND", "BULL", "BUY", "TREND_CONTINUATION", "PULLBACK")):
        return "ALCISTA"
    return "UNKNOWN"


def infer_trend_regime(row: dict[str, Any]) -> str:
    for key in (
        "trend_regime",
        "higher_tf_trend",
        "learned_strategy_direction",
        "strategy_family",
        "trend_setup",
        "setup",
        "signal",
        "trade_decision",
        "decision",
    ):
        regime = normalize_regime(row.get(key))
        if regime != "UNKNOWN":
            return regime
    return "UNKNOWN"


def infer_channel_type(row: dict[str, Any], trend_regime: str) -> str:
    text = " ".join(
        safe_text(row.get(key))
        for key in (
            "channel_type",
            "strategy_family",
            "learned_strategy",
            "learned_strategy_name",
            "trigger_setup",
            "setup",
            "trend_setup",
        )
    ).lower()
    timeframe = safe_text(row.get("timeframe") or row.get("tf")).lower()
    long_tf = timeframe in {"1d", "d", "day", "daily", "1w", "w", "week", "weekly", "4h", "2h"}

    if "piso a techo" in text:
        return "canal alcista piso a techo"
    if "techo a piso" in text:
        return "canal bajista techo a piso"
    if "lateral" in text or "neutral" in text or "range" in text:
        return "canal lateral"
    if "bajista" in text or "downtrend" in text or trend_regime == "BAJISTA":
        return "canal bajista largo plazo" if long_tf else "canal bajista corto plazo"
    if "alcista" in text or "trend_continuation" in text or "pullback" in text or trend_regime == "ALCISTA":
        return "canal alcista largo plazo" if long_tf else "canal alcista corto plazo"
    return "canal lateral" if trend_regime == "LATERAL" else "unknown"


def channel_duration_for(trend_regime: Any, channel_type: Any) -> dict[str, str]:
    trend = normalize_regime(trend_regime)
    channel = safe_text(channel_type).lower()
    table = CHANNEL_DURATION_RULES.get(trend, {})
    duration = table.get(channel)
    if not duration and channel:
        for known_channel, known_duration in table.items():
            if channel in known_channel or known_channel in channel:
                duration = known_duration
                channel = known_channel
                break
    return {
        "trend_regime": trend,
        "channel_type": channel or "unknown",
        "trend_duration": TREND_DURATION if trend != "UNKNOWN" else "-",
        "estimated_duration": duration or "-",
    }


def multitimeframe_alignment(row: dict[str, Any]) -> str:
    explicit = safe_text(row.get("mtf_alignment")).upper()
    if explicit in {"CONFIRMED", "PARTIAL", "BLOCKED", "UNKNOWN"}:
        return explicit
    htf = safe_text(row.get("higher_tf_bias")).upper()
    if htf in {"CONFIRMED", "PARTIAL", "BLOCKED"}:
        return htf
    confirmations = row.get("higher_tf_confirmations")
    blocks = row.get("higher_tf_blocks")
    try:
        if float(blocks or 0) > 0:
            return "BLOCKED"
        if float(confirmations or 0) >= 2:
            return "CONFIRMED"
        if float(confirmations or 0) == 1:
            return "PARTIAL"
    except (TypeError, ValueError):
        pass
    return "UNKNOWN"


def build_multitimeframe_context(row: dict[str, Any] | None) -> dict[str, Any]:
    row = row or {}
    trend = infer_trend_regime(row)
    channel = infer_channel_type(row, trend)
    duration = channel_duration_for(trend, channel)
    alignment = multitimeframe_alignment(row)
    timeframe = safe_text(row.get("timeframe") or row.get("tf") or "-")

    if alignment == "BLOCKED":
        action_bias = "No operar la entrada menor contra el canal/tendencia mayor."
    elif alignment == "CONFIRMED":
        action_bias = "15m puede ser gatillo si entrada, volumen, stop y target confirman."
    elif alignment == "PARTIAL":
        action_bias = "Esperar confirmacion extra antes de subir a BUY."
    else:
        action_bias = "Usar 15m solo como gatillo; primero validar 1h/dia/semana."

    explanation = (
        "Multitemporal: Semana -> Dia -> Hora -> 15m. "
        f"Lectura actual {trend}/{duration['channel_type']} en {timeframe}; "
        f"duracion estimada {duration['estimated_duration']}. {action_bias}"
    )
    return {
        **duration,
        "alignment": alignment,
        "timeframe": timeframe,
        "action_bias": action_bias,
        "explanation": explanation,
        "rules": list(TIMEFRAME_CHAIN),
    }


def multitimeframe_condition_checks(row: dict[str, Any] | None) -> list[dict[str, Any]]:
    context = build_multitimeframe_context(row)
    alignment = context["alignment"]
    return [
        {
            "label": "Canal mayor",
            "passed": alignment != "BLOCKED",
            "detail": f"{context['trend_regime']} / {context['channel_type']}",
        },
        {
            "label": "Duracion canal",
            "passed": context["estimated_duration"] != "-",
            "detail": context["estimated_duration"],
        },
        {
            "label": "15m como gatillo",
            "passed": alignment in {"CONFIRMED", "PARTIAL", "UNKNOWN"},
            "detail": context["action_bias"],
        },
    ]
