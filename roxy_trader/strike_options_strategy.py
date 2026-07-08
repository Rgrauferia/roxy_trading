from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


SIGNAL_YES = "YES"
SIGNAL_NO = "NO"
SIGNAL_NO_TRADE = "NO TRADE"

COLOR_GREEN = "green"
COLOR_YELLOW = "yellow"
COLOR_RED = "red"

CLOSED_RESULTS = {"WIN", "LOSS"}


@dataclass(frozen=True)
class StrikeTimeframeProfile:
    key: str
    label: str
    expiration_seconds: int
    min_confidence: int
    min_edge: float
    min_risk_reward: float
    close_strike_threshold: float
    min_seconds: int
    hard_floor_seconds: int
    rank_ready_score: int
    rank_ready_confidence: int
    amount_multiplier: float
    strategy_note: str


STRIKE_TIMEFRAME_PROFILES = {
    "20m": StrikeTimeframeProfile(
        key="20m",
        label="20 minutos",
        expiration_seconds=20 * 60,
        min_confidence=64,
        min_edge=0.03,
        min_risk_reward=0.55,
        close_strike_threshold=0.00035,
        min_seconds=60,
        hard_floor_seconds=25,
        rank_ready_score=68,
        rank_ready_confidence=64,
        amount_multiplier=0.75,
        strategy_note="lectura rapida con momentum 1/3/5m, strike cercano y confirmacion de volumen.",
    ),
    "2h": StrikeTimeframeProfile(
        key="2h",
        label="2 horas",
        expiration_seconds=2 * 60 * 60,
        min_confidence=70,
        min_edge=0.04,
        min_risk_reward=0.62,
        close_strike_threshold=0.00055,
        min_seconds=5 * 60,
        hard_floor_seconds=2 * 60,
        rank_ready_score=72,
        rank_ready_confidence=68,
        amount_multiplier=0.60,
        strategy_note="confirmacion mas limpia de tendencia, pullback y estructura antes de entrar.",
    ),
    "daily": StrikeTimeframeProfile(
        key="daily",
        label="daily",
        expiration_seconds=24 * 60 * 60,
        min_confidence=72,
        min_edge=0.05,
        min_risk_reward=0.68,
        close_strike_threshold=0.0009,
        min_seconds=30 * 60,
        hard_floor_seconds=10 * 60,
        rank_ready_score=74,
        rank_ready_confidence=70,
        amount_multiplier=0.50,
        strategy_note="solo toma setups macro con estructura clara, volatilidad aceptable y mayor margen al strike.",
    ),
}


def normalize_strike_timeframe(value: str | None) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "20m"
    compact = text.replace(" ", "").replace("_", "").replace("-", "")
    if compact in {"20", "20m", "20min", "20mins", "20minute", "20minutes", "20minutos"}:
        return "20m"
    if compact in {"2h", "2hr", "2hrs", "2hour", "2hours", "2hora", "2horas", "120m", "120min"}:
        return "2h"
    if compact in {"d", "1d", "day", "daily", "diario", "dia", "24h", "24hr", "24hours"}:
        return "daily"
    if "daily" in compact or "diari" in compact:
        return "daily"
    if "2h" in compact or "2hora" in compact or "2hour" in compact:
        return "2h"
    if "20" in compact:
        return "20m"
    return "20m"


def strike_timeframe_profile(value: str | None) -> StrikeTimeframeProfile:
    return STRIKE_TIMEFRAME_PROFILES[normalize_strike_timeframe(value)]


@dataclass(frozen=True)
class StrikeOptionInput:
    asset: str
    current_price: float
    strike: float
    time_remaining_seconds: int
    expiration_label: str = ""
    candles: Sequence[Mapping[str, Any]] = field(default_factory=list)
    yes_cost: float | None = None
    no_cost: float | None = None
    payout: float | None = None
    stake: float = 1.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class StrikeOptionSignal:
    timestamp: str
    asset: str
    price: float
    strike: float
    expiration: str
    time_remaining_seconds: int
    signal: str
    color: str
    confidence: int
    probability_roxy: float
    implied_probability: float | None
    edge: float | None
    risk_reward: float | None
    max_loss: float | None
    recommended_entry: str
    max_recommended_amount: float
    risk: str
    reasons: list[str]
    warning_flags: list[str]
    deriv_contract: dict[str, Any]
    indicators: dict[str, Any]
    decision_state: str = ""
    data_quality: str = ""
    market_regime: str = ""
    entry_window: str = ""
    score_breakdown: dict[str, Any] = field(default_factory=dict)
    checklist: list[dict[str, Any]] = field(default_factory=list)
    result: str | None = None
    profit_loss: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrikeContractComparison:
    timestamp: str
    asset: str
    expiration: str
    status: str
    signal: str
    color: str
    confidence: int
    best_contract: dict[str, Any] | None
    contracts_ranked: list[dict[str, Any]]
    reason: str
    data_quality: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _extract_closes(candles: Sequence[Mapping[str, Any]]) -> list[float]:
    closes: list[float] = []
    for candle in candles or []:
        close = _safe_float(
            candle.get("close")
            or candle.get("c")
            or candle.get("price")
            or candle.get("last")
        )
        if close is not None:
            closes.append(close)
    return closes


def _extract_volumes(candles: Sequence[Mapping[str, Any]]) -> list[float]:
    volumes: list[float] = []
    for candle in candles or []:
        volume = _safe_float(candle.get("volume") or candle.get("v"))
        if volume is not None:
            volumes.append(volume)
    return volumes


def _ema(values: Sequence[float], period: int) -> float | None:
    if not values:
        return None
    alpha = 2.0 / (period + 1.0)
    ema_value = float(values[0])
    for value in values[1:]:
        ema_value = (float(value) * alpha) + (ema_value * (1.0 - alpha))
    return ema_value


def _rsi(values: Sequence[float], period: int = 14) -> float | None:
    if len(values) < 2:
        return None
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    recent = deltas[-period:]
    gains = [delta for delta in recent if delta > 0]
    losses = [-delta for delta in recent if delta < 0]
    avg_gain = sum(gains) / max(1, len(recent))
    avg_loss = sum(losses) / max(1, len(recent))
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _macd(values: Sequence[float]) -> tuple[float | None, float | None, float | None]:
    if len(values) < 3:
        return None, None, None
    fast = _ema(values, 12)
    slow = _ema(values, 26)
    if fast is None or slow is None:
        return None, None, None
    macd_line = fast - slow
    macd_series: list[float] = []
    for index in range(2, len(values) + 1):
        sample = values[:index]
        sample_fast = _ema(sample, 12)
        sample_slow = _ema(sample, 26)
        if sample_fast is not None and sample_slow is not None:
            macd_series.append(sample_fast - sample_slow)
    signal_line = _ema(macd_series, 9) if macd_series else None
    histogram = macd_line - signal_line if signal_line is not None else None
    return macd_line, signal_line, histogram


def _momentum(values: Sequence[float], lookback: int) -> float | None:
    if len(values) <= lookback:
        return None
    base = values[-lookback - 1]
    if base == 0:
        return None
    return (values[-1] - base) / base


def _last_candle_pressure(candles: Sequence[Mapping[str, Any]]) -> tuple[str, float]:
    if not candles:
        return "neutral", 0.0
    candle = candles[-1]
    open_price = _safe_float(candle.get("open") or candle.get("o"))
    high = _safe_float(candle.get("high") or candle.get("h"))
    low = _safe_float(candle.get("low") or candle.get("l"))
    close = _safe_float(candle.get("close") or candle.get("c") or candle.get("price"))
    if None in (open_price, high, low, close) or high == low:
        return "neutral", 0.0
    assert open_price is not None and high is not None and low is not None and close is not None
    body = abs(close - open_price) / (high - low)
    upper_wick = (high - max(open_price, close)) / (high - low)
    lower_wick = (min(open_price, close) - low) / (high - low)
    if close > open_price and body >= 0.45:
        return "bullish", body
    if close < open_price and body >= 0.45:
        return "bearish", body
    if lower_wick >= 0.45:
        return "bullish_rejection", lower_wick
    if upper_wick >= 0.45:
        return "bearish_rejection", upper_wick
    return "neutral", body


def _volume_bias(volumes: Sequence[float]) -> str:
    if len(volumes) < 6:
        return "unknown"
    recent = sum(volumes[-3:]) / 3.0
    prior = sum(volumes[-8:-3]) / max(1, len(volumes[-8:-3]))
    if prior <= 0:
        return "unknown"
    if recent >= prior * 1.18:
        return "rising"
    if recent <= prior * 0.82:
        return "falling"
    return "flat"


def _data_quality_label(
    *,
    candles: Sequence[Mapping[str, Any]],
    closes: Sequence[float],
    volumes: Sequence[float],
) -> str:
    if len(closes) >= 35 and len(volumes) >= 8:
        return "live_ready"
    if len(closes) >= 20:
        return "price_history_only"
    if len(closes) >= 8:
        return "thin_history"
    if candles or closes:
        return "insufficient_history"
    return "missing_history"


def _market_regime_label(
    *,
    ema9: float | None,
    ema21: float | None,
    rsi: float | None,
    macd_histogram: float | None,
    momentum_values: Sequence[float],
) -> str:
    bullish = 0
    bearish = 0
    if ema9 is not None and ema21 is not None:
        if ema9 > ema21:
            bullish += 1
        elif ema9 < ema21:
            bearish += 1
    if rsi is not None:
        if rsi >= 53:
            bullish += 1
        elif rsi <= 47:
            bearish += 1
    if macd_histogram is not None:
        if macd_histogram > 0:
            bullish += 1
        elif macd_histogram < 0:
            bearish += 1
    if momentum_values:
        net_momentum = sum(momentum_values)
        if net_momentum > 0:
            bullish += 1
        elif net_momentum < 0:
            bearish += 1
    if bullish >= bearish + 2:
        return "tendencia_alcista"
    if bearish >= bullish + 2:
        return "tendencia_bajista"
    if bullish or bearish:
        return "lateral_mixto"
    return "sin_confirmacion"


def _entry_window_label(seconds: int) -> str:
    if seconds < 60:
        return "Cierre menor de 1 minuto: no entrar salvo ventaja extrema."
    if seconds <= 10 * 60:
        return "Ventana rapida: priorizar momentum, rechazo y distancia al strike."
    if seconds <= 2 * 60 * 60:
        return "Ventana 2H: exigir tendencia limpia y confirmacion multi-indicador."
    return "Ventana daily: priorizar estructura macro, niveles clave y eventos."


def _selected_signal_bias(signal: str, *, yes_value: Any, no_value: Any, neutral_value: Any = None) -> Any:
    if signal == SIGNAL_YES:
        return yes_value
    if signal == SIGNAL_NO:
        return no_value
    return neutral_value


def _check_status_for_bias(signal: str, bias: str) -> str:
    if signal == SIGNAL_NO_TRADE:
        return "watch" if bias in {"neutral", "unknown"} else "blocked"
    if signal == SIGNAL_YES:
        if bias == "yes":
            return "pass"
        if bias == "no":
            return "blocked"
        return "watch"
    if signal == SIGNAL_NO:
        if bias == "no":
            return "pass"
        if bias == "yes":
            return "blocked"
        return "watch"
    return "watch"


def _build_strike_checklist(
    *,
    signal: str,
    ema9: float | None,
    ema21: float | None,
    rsi: float | None,
    macd_histogram: float | None,
    momentum_values: Sequence[float],
    candle_bias: str,
    volume_bias: str,
    abs_distance_pct: float,
    close_strike_threshold: float,
    time_remaining_seconds: int,
    edge: float | None,
    risk_reward: float | None,
) -> list[dict[str, Any]]:
    ema_bias = "unknown"
    ema_detail = "Sin EMA suficiente."
    if ema9 is not None and ema21 is not None:
        ema_bias = "yes" if ema9 > ema21 else "no" if ema9 < ema21 else "neutral"
        ema_detail = f"EMA9 {ema9:.4f} vs EMA21 {ema21:.4f}."

    rsi_bias = "unknown"
    rsi_detail = "RSI pendiente."
    if rsi is not None:
        rsi_bias = "yes" if 50 <= rsi <= 70 else "no" if rsi < 50 else "neutral"
        rsi_detail = f"RSI {rsi:.1f}."

    macd_bias = "unknown"
    macd_detail = "MACD pendiente."
    if macd_histogram is not None:
        macd_bias = "yes" if macd_histogram > 0 else "no" if macd_histogram < 0 else "neutral"
        macd_detail = f"Histograma MACD {macd_histogram:.6f}."

    momentum_bias = "unknown"
    momentum_detail = "Momentum pendiente."
    if momentum_values:
        net_momentum = sum(momentum_values)
        momentum_bias = "yes" if net_momentum > 0 else "no" if net_momentum < 0 else "neutral"
        momentum_detail = f"Momentum neto {net_momentum * 100:.3f}%."

    candle_signal_bias = "unknown"
    if candle_bias in {"bullish", "bullish_rejection"}:
        candle_signal_bias = "yes"
    elif candle_bias in {"bearish", "bearish_rejection"}:
        candle_signal_bias = "no"

    strike_ok = abs_distance_pct > close_strike_threshold
    timer_ok = time_remaining_seconds >= 60
    edge_ok = edge is None or edge >= 0.03
    rr_ok = risk_reward is None or risk_reward >= 0.55

    checks = [
        {
            "id": "ema",
            "label": "EMA 9/21",
            "status": _check_status_for_bias(signal, ema_bias),
            "detail": ema_detail,
        },
        {
            "id": "rsi",
            "label": "RSI",
            "status": _check_status_for_bias(signal, rsi_bias),
            "detail": rsi_detail,
        },
        {
            "id": "macd",
            "label": "MACD",
            "status": _check_status_for_bias(signal, macd_bias),
            "detail": macd_detail,
        },
        {
            "id": "momentum",
            "label": "Momentum 1/3/5",
            "status": _check_status_for_bias(signal, momentum_bias),
            "detail": momentum_detail,
        },
        {
            "id": "vela",
            "label": "Ultima vela",
            "status": _check_status_for_bias(signal, candle_signal_bias),
            "detail": f"Presion {candle_bias}.",
        },
        {
            "id": "volumen",
            "label": "Volumen",
            "status": "pass" if volume_bias == "rising" else "watch" if volume_bias in {"flat", "unknown"} else "blocked",
            "detail": f"Volumen {volume_bias}.",
        },
        {
            "id": "strike",
            "label": "Distancia al strike",
            "status": "pass" if strike_ok else "blocked",
            "detail": f"Distancia {abs_distance_pct * 100:.3f}%.",
        },
        {
            "id": "timer",
            "label": "Tiempo restante",
            "status": "pass" if timer_ok else "blocked",
            "detail": _entry_window_label(time_remaining_seconds),
        },
        {
            "id": "edge",
            "label": "Edge / payout",
            "status": "pass" if edge_ok and rr_ok else "blocked",
            "detail": f"Edge {edge if edge is not None else 'sin costo'} · R/R {risk_reward if risk_reward is not None else 'sin payout'}.",
        },
    ]
    return checks


def _implied_probability(
    side: str,
    *,
    yes_cost: float | None,
    no_cost: float | None,
    payout: float | None,
) -> float | None:
    selected_cost = yes_cost if side == SIGNAL_YES else no_cost if side == SIGNAL_NO else None
    if selected_cost is None:
        return None
    if yes_cost is not None and no_cost is not None and (yes_cost + no_cost) > 0:
        return selected_cost / (yes_cost + no_cost)
    if payout is not None and payout > 0:
        return selected_cost / payout
    return None


def _risk_reward(side: str, yes_cost: float | None, no_cost: float | None, payout: float | None) -> tuple[float | None, float | None]:
    cost = yes_cost if side == SIGNAL_YES else no_cost if side == SIGNAL_NO else None
    if cost is None or cost <= 0:
        return None, None
    reward = (payout - cost) if payout is not None and payout > cost else (1.0 - cost if cost < 1 else None)
    if reward is None or reward <= 0:
        return None, cost
    return reward / cost, cost


def _candidate_strikes_from_contract(contract: Mapping[str, Any]) -> list[float]:
    values: list[float] = []
    for key in ("strike", "barrier", "barrier1", "barrier2", "barrier_value", "target"):
        value = _safe_float(contract.get(key))
        if value is not None:
            values.append(value)
    for key in ("strikes", "barrier_range", "barriers_range", "strike_range"):
        value = contract.get(key)
        if isinstance(value, Mapping):
            iterable = value.values()
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            iterable = value
        else:
            continue
        for item in iterable:
            numeric = _safe_float(item)
            if numeric is not None:
                values.append(numeric)
    return list(dict.fromkeys(values))


def _contract_costs(contract: Mapping[str, Any]) -> dict[str, float | None]:
    yes_cost = _safe_float(
        contract.get("yes_cost")
        or contract.get("yes_price")
        or contract.get("yes")
        or contract.get("ask_price")
        or contract.get("buy_price")
        or contract.get("display_value")
    )
    no_cost = _safe_float(
        contract.get("no_cost")
        or contract.get("no_price")
        or contract.get("no")
        or contract.get("bid_price")
        or contract.get("sell_price")
    )
    payout = _safe_float(contract.get("payout") or contract.get("max_payout") or contract.get("barrier_payout"))
    return {"yes_cost": yes_cost, "no_cost": no_cost, "payout": payout}


def _contract_bias(contract: Mapping[str, Any], fallback: str) -> str:
    contract_type = str(contract.get("contract_type") or contract.get("type") or "").upper()
    sentiment = str(contract.get("sentiment") or contract.get("direction") or "").lower()
    if contract_type.startswith("CALL") or sentiment in {"up", "above", "yes", "bullish"}:
        return SIGNAL_YES
    if contract_type.startswith("PUT") or sentiment in {"down", "below", "no", "bearish"}:
        return SIGNAL_NO
    return fallback


def _normalize_option_input(option: StrikeOptionInput | Mapping[str, Any] | None, kwargs: dict[str, Any]) -> StrikeOptionInput:
    if isinstance(option, StrikeOptionInput):
        if kwargs:
            data = asdict(option)
            data.update(kwargs)
            return StrikeOptionInput(**data)
        return option
    data = dict(option or {})
    data.update(kwargs)
    price = data.get("current_price", data.get("price"))
    remaining = data.get("time_remaining_seconds", data.get("seconds_remaining", data.get("time_left")))
    return StrikeOptionInput(
        asset=str(data.get("asset", "BTC")).upper(),
        current_price=float(price or 0.0),
        strike=float(data.get("strike") or 0.0),
        time_remaining_seconds=int(remaining or 0),
        expiration_label=str(data.get("expiration_label") or data.get("expiration") or ""),
        candles=data.get("candles") or [],
        yes_cost=_safe_float(data.get("yes_cost")),
        no_cost=_safe_float(data.get("no_cost")),
        payout=_safe_float(data.get("payout")),
        stake=float(data.get("stake") or 1.0),
        timestamp=str(data.get("timestamp") or datetime.now(timezone.utc).isoformat()),
    )


def analyze_strike_option(
    option: StrikeOptionInput | Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> StrikeOptionSignal:
    """Analyze a short-duration strike option and return YES/NO/NO TRADE.

    This module never executes orders. It produces an auditable signal that the UI
    can show beside a Deriv-style "BTC will be above $X" contract.
    """
    request = _normalize_option_input(option, kwargs)
    profile = strike_timeframe_profile(
        kwargs.get("timeframe_profile")
        or kwargs.get("timeframe")
        or kwargs.get("horizon")
        or request.expiration_label
    )
    candles = list(request.candles or [])
    closes = _extract_closes(candles)
    volumes = _extract_volumes(candles)
    current_price = request.current_price or (closes[-1] if closes else 0.0)
    strike = request.strike
    distance_pct = ((current_price - strike) / current_price) if current_price else 0.0
    abs_distance_pct = abs(distance_pct)

    ema9 = _ema(closes or [current_price], 9)
    ema21 = _ema(closes or [current_price], 21)
    rsi = _rsi(closes)
    macd_line, macd_signal, macd_histogram = _macd(closes)
    momentum_1 = _momentum(closes, 1)
    momentum_3 = _momentum(closes, 3)
    momentum_5 = _momentum(closes, 5)
    candle_bias, candle_strength = _last_candle_pressure(candles)
    volume_bias = _volume_bias(volumes)
    data_quality = _data_quality_label(candles=candles, closes=closes, volumes=volumes)
    momentum_values = [value for value in (momentum_1, momentum_3, momentum_5) if value is not None]
    market_regime = _market_regime_label(
        ema9=ema9,
        ema21=ema21,
        rsi=rsi,
        macd_histogram=macd_histogram,
        momentum_values=momentum_values,
    )
    entry_window = _entry_window_label(request.time_remaining_seconds)

    yes_score = 0.0
    no_score = 0.0
    reasons: list[str] = []
    warning_flags: list[str] = []

    if ema9 is not None and ema21 is not None:
        if ema9 > ema21:
            yes_score += 18
            reasons.append("EMA9 esta sobre EMA21: sesgo alcista.")
        elif ema9 < ema21:
            no_score += 18
            reasons.append("EMA9 esta debajo de EMA21: sesgo bajista.")

    if rsi is not None:
        if 50 <= rsi <= 70:
            yes_score += 12
            reasons.append(f"RSI {rsi:.1f}: fuerza alcista sin estar extremo.")
        elif 30 <= rsi < 50:
            no_score += 12
            reasons.append(f"RSI {rsi:.1f}: fuerza debajo de 50.")
        elif rsi > 75:
            warning_flags.append("RSI muy extendido; puede haber retroceso.")
        elif rsi < 25:
            warning_flags.append("RSI muy bajo; puede haber rebote.")

    if macd_histogram is not None:
        if macd_histogram > 0:
            yes_score += 12
            reasons.append("MACD confirma momentum positivo.")
        elif macd_histogram < 0:
            no_score += 12
            reasons.append("MACD confirma momentum negativo.")

    if momentum_values:
        positive = sum(1 for value in momentum_values if value > 0)
        negative = sum(1 for value in momentum_values if value < 0)
        magnitude = min(20.0, sum(abs(value) for value in momentum_values) * 12000.0)
        if positive > negative:
            yes_score += 10 + (magnitude / 2.0)
            reasons.append("Momentum 1/3/5 minutos favorece ARRIBA.")
        elif negative > positive:
            no_score += 10 + (magnitude / 2.0)
            reasons.append("Momentum 1/3/5 minutos favorece ABAJO.")

    if candle_bias in {"bullish", "bullish_rejection"}:
        yes_score += 8 + (candle_strength * 8)
        reasons.append("Ultima vela muestra compra o rechazo alcista.")
    elif candle_bias in {"bearish", "bearish_rejection"}:
        no_score += 8 + (candle_strength * 8)
        reasons.append("Ultima vela muestra venta o rechazo bajista.")

    if volume_bias == "rising":
        yes_score += 6 if yes_score >= no_score else 0
        no_score += 6 if no_score > yes_score else 0
        reasons.append("Volumen reciente esta aumentando.")
    elif volume_bias == "falling":
        warning_flags.append("Volumen reciente esta bajando.")

    if market_regime in {"lateral_mixto", "sin_confirmacion"}:
        warning_flags.append("Regimen lateral o mixto; Roxy exige mas confirmacion.")
        if abs(yes_score - no_score) < 14:
            yes_score -= 4
            no_score -= 4

    close_strike_threshold = profile.close_strike_threshold
    if abs_distance_pct <= close_strike_threshold:
        warning_flags.append("Strike demasiado cerca del precio actual.")
        yes_score -= 8
        no_score -= 8
    elif distance_pct > 0:
        yes_score += min(14.0, abs_distance_pct * 12000.0)
        reasons.append("Precio actual esta encima del strike.")
    else:
        no_score += min(14.0, abs_distance_pct * 12000.0)
        reasons.append("Precio actual esta debajo del strike.")

    if request.time_remaining_seconds < profile.hard_floor_seconds:
        warning_flags.append(f"{profile.label}: timer demasiado cerca del cierre.")
        yes_score -= 24
        no_score -= 24
    elif request.time_remaining_seconds < profile.min_seconds:
        warning_flags.append(f"{profile.label}: queda poco tiempo para validar el setup.")
        yes_score -= 18
        no_score -= 18
    elif request.time_remaining_seconds <= 10 * 60:
        yes_score += 5
        no_score += 5
        reasons.append("Ventana rapida: la decision depende del momentum actual.")
    else:
        if abs(yes_score - no_score) < 12:
            warning_flags.append("Para expiracion mas larga la tendencia no esta suficientemente limpia.")
        else:
            yes_score += 5 if yes_score > no_score else 0
            no_score += 5 if no_score > yes_score else 0

    raw_gap = yes_score - no_score
    probability_yes = _clamp(50.0 + raw_gap * 0.45, 5.0, 95.0)
    probability_no = 100.0 - probability_yes

    candidate = SIGNAL_YES if yes_score > no_score else SIGNAL_NO
    selected_probability = probability_yes if candidate == SIGNAL_YES else probability_no
    implied = _implied_probability(
        candidate,
        yes_cost=request.yes_cost,
        no_cost=request.no_cost,
        payout=request.payout,
    )
    edge = (selected_probability / 100.0 - implied) if implied is not None else None
    risk_reward, max_loss = _risk_reward(candidate, request.yes_cost, request.no_cost, request.payout)

    mixed_signals = abs(raw_gap) < 10
    weak_confidence = selected_probability < 62
    profile_confidence = profile.key != "20m" and selected_probability < profile.min_confidence
    bad_edge = edge is not None and edge < profile.min_edge
    bad_rr = risk_reward is not None and risk_reward < profile.min_risk_reward
    too_short = request.time_remaining_seconds < profile.min_seconds and selected_probability < max(88, profile.min_confidence + 12)
    too_close = abs_distance_pct <= close_strike_threshold and selected_probability < 78
    thin_data = data_quality in {"missing_history", "insufficient_history"} and selected_probability < 82
    lateral_weak = market_regime in {"lateral_mixto", "sin_confirmacion"} and selected_probability < 72

    blockers = []
    if mixed_signals:
        blockers.append("senales mezcladas")
    if weak_confidence:
        blockers.append("confianza insuficiente")
    if profile_confidence:
        blockers.append(f"{profile.label}: confianza debajo de {profile.min_confidence}%")
    if bad_edge:
        blockers.append(f"edge insuficiente contra el costo del contrato (min {profile.min_edge:.0%})")
    if bad_rr:
        blockers.append(f"payout no compensa el riesgo (R/R min {profile.min_risk_reward:.2f})")
    if too_short:
        blockers.append("tiempo restante demasiado corto")
    if too_close:
        blockers.append("strike demasiado cerca sin ventaja clara")
    if thin_data:
        blockers.append("historial insuficiente para confirmar")
    if lateral_weak:
        blockers.append("mercado lateral sin ventaja clara")

    if blockers:
        signal = SIGNAL_NO_TRADE
        probability = max(probability_yes, probability_no)
        confidence = int(round(_clamp(probability - 10, 0, 100)))
        color = COLOR_RED if too_short or bad_edge or bad_rr else COLOR_YELLOW
        risk = "Alto" if color == COLOR_RED else "Medio"
        recommended_entry = "Esperar; no abrir contrato ahora."
        max_recommended_amount = 0.0
        warning_flags.extend(blockers)
    else:
        signal = candidate
        probability = selected_probability
        confidence = int(round(_clamp(probability, 0, 100)))
        color = COLOR_GREEN if confidence >= 70 else COLOR_YELLOW
        risk = "Bajo" if confidence >= 78 and (edge is None or edge >= 0.08) else "Medio"
        recommended_entry = (
            f"Buscar contrato {request.asset} will be above ${strike:,.2f} y elegir YES."
            if signal == SIGNAL_YES
            else f"Buscar contrato {request.asset} will be above ${strike:,.2f} y elegir NO."
        )
        max_recommended_amount = round(
            (max_loss or request.stake) * profile.amount_multiplier * (0.5 if risk == "Medio" else 1.0),
            2,
        )

    if not reasons:
        reasons.append("No hay suficientes datos de velas para confirmar una ventaja.")
    reasons.append(f"Perfil {profile.label}: {profile.strategy_note}")

    decision_state = "OPERAR AHORA" if signal in {SIGNAL_YES, SIGNAL_NO} and color == COLOR_GREEN else (
        "ESPERAR CONFIRMACION" if color == COLOR_YELLOW else "NO OPERAR"
    )
    score_breakdown = {
        "yes_score": round(yes_score, 4),
        "no_score": round(no_score, 4),
        "score_gap": round(raw_gap, 4),
        "probability_yes": round(probability_yes, 2),
        "probability_no": round(probability_no, 2),
        "selected_probability": round(probability, 2),
        "distance_pct": round(distance_pct, 6),
        "abs_distance_pct": round(abs_distance_pct, 6),
        "time_remaining_seconds": request.time_remaining_seconds,
        "timeframe_profile": profile.key,
        "profile_label": profile.label,
        "profile_min_confidence": profile.min_confidence,
        "profile_min_edge": profile.min_edge,
        "profile_min_risk_reward": profile.min_risk_reward,
        "profile_min_seconds": profile.min_seconds,
        "blockers": blockers,
        "edge": round(edge, 4) if edge is not None else None,
        "risk_reward": round(risk_reward, 4) if risk_reward is not None else None,
    }
    checklist = _build_strike_checklist(
        signal=signal,
        ema9=ema9,
        ema21=ema21,
        rsi=rsi,
        macd_histogram=macd_histogram,
        momentum_values=momentum_values,
        candle_bias=candle_bias,
        volume_bias=volume_bias,
        abs_distance_pct=abs_distance_pct,
        close_strike_threshold=close_strike_threshold,
        time_remaining_seconds=request.time_remaining_seconds,
        edge=edge,
        risk_reward=risk_reward,
    )

    deriv_contract = {
        "asset": request.asset,
        "contract": f"{request.asset} will be above ${strike:,.2f}",
        "direction": signal if signal in {SIGNAL_YES, SIGNAL_NO} else "WAIT",
        "strike": strike,
        "expiration": request.expiration_label or f"{request.time_remaining_seconds}s",
        "timeframe_profile": profile.key,
        "profile_label": profile.label,
        "status": "READY" if signal in {SIGNAL_YES, SIGNAL_NO} and color == COLOR_GREEN else "WAIT",
        "decision_state": decision_state,
        "contract_instruction": (
            f"En Strike Options busca {request.asset}, periodo {profile.label}, strike ${strike:,.2f}, "
            f"y elige {signal if signal in {SIGNAL_YES, SIGNAL_NO} else 'esperar'} solo si precio, timer y payout siguen alineados."
        ),
    }
    indicators = {
        "ema9": ema9,
        "ema21": ema21,
        "rsi": rsi,
        "macd": macd_line,
        "macd_signal": macd_signal,
        "macd_histogram": macd_histogram,
        "momentum_1m": momentum_1,
        "momentum_3m": momentum_3,
        "momentum_5m": momentum_5,
        "candle_bias": candle_bias,
        "candle_strength": candle_strength,
        "volume_bias": volume_bias,
        "distance_pct": distance_pct,
        "market_regime": market_regime,
        "data_quality": data_quality,
        "yes_score": yes_score,
        "no_score": no_score,
    }

    return StrikeOptionSignal(
        timestamp=request.timestamp,
        asset=request.asset,
        price=round(current_price, 8),
        strike=round(strike, 8),
        expiration=request.expiration_label or f"{request.time_remaining_seconds}s",
        time_remaining_seconds=request.time_remaining_seconds,
        signal=signal,
        color=color,
        confidence=confidence,
        probability_roxy=round(probability, 2),
        implied_probability=round(implied, 4) if implied is not None else None,
        edge=round(edge, 4) if edge is not None else None,
        risk_reward=round(risk_reward, 4) if risk_reward is not None else None,
        max_loss=round(max_loss, 4) if max_loss is not None else None,
        recommended_entry=recommended_entry,
        max_recommended_amount=max_recommended_amount,
        risk=risk,
        reasons=reasons[:8],
        warning_flags=warning_flags,
        deriv_contract=deriv_contract,
        indicators=indicators,
        decision_state=decision_state,
        data_quality=data_quality,
        market_regime=market_regime,
        entry_window=entry_window,
        score_breakdown=score_breakdown,
        checklist=checklist,
    )


def compare_deriv_strike_contracts(
    *,
    asset: str,
    current_price: float,
    contracts: Sequence[Mapping[str, Any]],
    time_remaining_seconds: int,
    expiration_label: str,
    candles: Sequence[Mapping[str, Any]] = (),
    target_price: float | None = None,
    preferred_signal: str | None = None,
    timeframe_profile: str | None = None,
    stake: float = 1.0,
    timestamp: str | None = None,
    log_path: str | Path | None = None,
) -> StrikeContractComparison:
    """Rank Deriv-style strike contracts and select the best actionable one.

    The function evaluates every visible strike with the same signal engine used
    by the UI. It does not trade and it refuses to mark a "best" contract when
    data is missing, the payout has no edge, or signals are mixed.
    """
    now = timestamp or datetime.now(timezone.utc).isoformat()
    profile = strike_timeframe_profile(timeframe_profile or expiration_label)
    normalized_preference = str(preferred_signal or "").upper()
    ranked: list[dict[str, Any]] = []
    has_live_costs = False

    for index, contract in enumerate(contracts or []):
        if not isinstance(contract, Mapping):
            continue
        strikes = _candidate_strikes_from_contract(contract)
        costs = _contract_costs(contract)
        if costs.get("yes_cost") is not None or costs.get("no_cost") is not None:
            has_live_costs = True
        if not strikes and target_price is not None:
            strikes = [target_price]
        for strike in strikes:
            signal = analyze_strike_option(
                asset=asset,
                current_price=current_price,
                strike=strike,
                time_remaining_seconds=time_remaining_seconds,
                expiration_label=expiration_label,
                candles=candles,
                yes_cost=costs.get("yes_cost"),
                no_cost=costs.get("no_cost"),
                payout=costs.get("payout"),
                timeframe_profile=profile.key,
                stake=stake,
                timestamp=now,
            )
            signal_dict = signal.to_dict()
            decision = signal.signal
            bias = _contract_bias(contract, decision)
            if decision == SIGNAL_NO_TRADE:
                action_bonus = -24.0
            else:
                action_bonus = 12.0
            if normalized_preference in {SIGNAL_YES, SIGNAL_NO} and decision == normalized_preference:
                action_bonus += 8.0
            if bias in {SIGNAL_YES, SIGNAL_NO} and decision in {SIGNAL_YES, SIGNAL_NO} and bias != decision:
                action_bonus -= 18.0

            distance_basis = target_price if target_price is not None else current_price
            distance = abs(strike - distance_basis)
            distance_pct = distance / max(abs(distance_basis), 1.0)
            distance_score = max(0.0, 14.0 - (distance_pct * 9000.0))
            edge = signal.edge if signal.edge is not None else 0.0
            edge_score = _clamp(edge * 120.0, -18.0, 22.0)
            risk_reward = signal.risk_reward or 0.0
            rr_score = _clamp((risk_reward - 0.65) * 18.0, -10.0, 12.0) if signal.risk_reward is not None else 0.0
            warning_penalty = min(18.0, len(signal.warning_flags) * 4.0)
            score = _clamp(signal.confidence + action_bonus + distance_score + edge_score + rr_score - warning_penalty, 0.0, 100.0)
            ranked.append(
                {
                    "rank": 0,
                    "contract_index": index,
                    "contract": dict(contract),
                    "asset": signal.asset,
                    "strike": signal.strike,
                    "side": decision,
                    "contract_bias": bias,
                    "score": round(score, 4),
                    "confidence": signal.confidence,
                    "probability_roxy": signal.probability_roxy,
                    "edge": signal.edge,
                    "risk_reward": signal.risk_reward,
                    "color": signal.color,
                    "risk": signal.risk,
                    "decision_state": signal.decision_state,
                    "market_regime": signal.market_regime,
                    "data_quality": signal.data_quality,
                    "entry_window": signal.entry_window,
                    "timeframe_profile": profile.key,
                    "profile_label": profile.label,
                    "recommended_entry": signal.recommended_entry,
                    "reasons": signal.reasons,
                    "warning_flags": signal.warning_flags,
                    "checklist": signal.checklist,
                    "score_breakdown": signal.score_breakdown,
                    "roxy_signal": signal_dict,
                }
            )

    ranked.sort(key=lambda row: (_safe_float(row.get("score"), 0.0) or 0.0), reverse=True)
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index

    if not ranked:
        return StrikeContractComparison(
            timestamp=now,
            asset=asset.upper(),
            expiration=expiration_label,
            status="not_ready",
            signal=SIGNAL_NO_TRADE,
            color=COLOR_RED,
            confidence=0,
            best_contract=None,
            contracts_ranked=[],
            reason="No hay contratos/strikes reales para comparar.",
            data_quality="missing_contracts",
        )

    best = ranked[0]
    best_signal = best.get("roxy_signal") if isinstance(best.get("roxy_signal"), Mapping) else {}
    best_side = str(best.get("side") or SIGNAL_NO_TRADE)
    best_score = _safe_float(best.get("score"), 0.0) or 0.0
    best_confidence = int(_safe_float(best.get("confidence"), 0.0) or 0)
    best_edge = _safe_float(best.get("edge"))
    data_quality = "live_costs" if has_live_costs else "missing_costs_estimated"
    actionable = (
        best_side in {SIGNAL_YES, SIGNAL_NO}
        and best_score >= profile.rank_ready_score
        and best_confidence >= profile.rank_ready_confidence
        and (best_edge is None or best_edge >= profile.min_edge)
        and not (time_remaining_seconds < profile.min_seconds and best_confidence < max(88, profile.min_confidence + 12))
        and data_quality == "live_costs"
    )

    if actionable:
        comparison = StrikeContractComparison(
            timestamp=now,
            asset=asset.upper(),
            expiration=expiration_label,
            status="ready",
            signal=best_side,
            color=str(best.get("color") or COLOR_GREEN),
            confidence=best_confidence,
            best_contract=best,
            contracts_ranked=ranked,
            reason=f"Roxy comparo {len(ranked)} strikes con perfil {profile.label} y encontro mayor edge/riesgo en {best_side} {best.get('strike')}.",
            data_quality=data_quality,
        )
        if log_path is not None and isinstance(best_signal, Mapping):
            log_strike_signal(StrikeOptionSignal(**best_signal), log_path)
        return comparison

    reason_parts = []
    if data_quality != "live_costs":
        reason_parts.append("faltan costos/payout reales")
    if best_side == SIGNAL_NO_TRADE:
        reason_parts.append("la mejor opcion sigue siendo NO TRADE")
    if best_score < profile.rank_ready_score or best_confidence < profile.rank_ready_confidence:
        reason_parts.append(f"score o confianza insuficiente para {profile.label}")
    if best_edge is not None and best_edge < profile.min_edge:
        reason_parts.append(f"edge insuficiente para {profile.label}")
    if time_remaining_seconds < profile.min_seconds and best_confidence < max(88, profile.min_confidence + 12):
        reason_parts.append("queda muy poco tiempo")
    return StrikeContractComparison(
        timestamp=now,
        asset=asset.upper(),
        expiration=expiration_label,
        status="blocked",
        signal=SIGNAL_NO_TRADE,
        color=COLOR_YELLOW,
        confidence=best_confidence,
        best_contract=best,
        contracts_ranked=ranked,
        reason="; ".join(reason_parts) or "Roxy no encontro ventaja suficiente.",
        data_quality=data_quality,
    )


def format_roxy_strike_response(signal: StrikeOptionSignal) -> str:
    reason_text = "\n".join(f"- {reason}" for reason in signal.reasons)
    warning_text = "\n".join(f"- {warning}" for warning in signal.warning_flags) or "- Sin bloqueos criticos."
    checklist_text = "\n".join(
        f"- {item.get('label')}: {item.get('status')} ({item.get('detail')})"
        for item in signal.checklist[:6]
    ) or "- Checklist pendiente."
    return (
        f"Activo: {signal.asset}\n"
        f"Precio actual: {signal.price:,.2f}\n"
        f"Strike: {signal.strike:,.2f}\n"
        f"Tiempo restante: {signal.time_remaining_seconds}s\n"
        f"Senal: {signal.signal}\n"
        f"Decision: {signal.decision_state}\n"
        f"Confianza: {signal.confidence}%\n"
        f"Regimen: {signal.market_regime}\n"
        f"Calidad de datos: {signal.data_quality}\n"
        f"Razon:\n{reason_text}\n"
        f"Checklist:\n{checklist_text}\n"
        f"Riesgo: {signal.risk}\n"
        f"Entrada recomendada: {signal.recommended_entry}\n"
        f"Monto maximo recomendado: {signal.max_recommended_amount}\n"
        f"Alertas:\n{warning_text}\n"
        f"Comentario de Roxy: {'Operar solo en paper o con riesgo controlado; no hay garantias.' if signal.signal != SIGNAL_NO_TRADE else 'No fuerces la entrada. Espero una ventaja mas clara.'}"
    )


def _history_fit_for_signal(
    history_summary: Mapping[str, Any],
    signal_data: Mapping[str, Any],
    *,
    expiration: str,
    current_signal: str,
) -> dict[str, Any]:
    """Return the most relevant historical bucket for the current setup."""
    condition_key = _condition_key_from_signal(signal_data)
    candidates: list[tuple[str, Mapping[str, Any], int]] = []
    by_condition = history_summary.get("by_condition") if isinstance(history_summary.get("by_condition"), Mapping) else {}
    by_expiration = history_summary.get("by_expiration") if isinstance(history_summary.get("by_expiration"), Mapping) else {}
    by_signal = history_summary.get("by_signal") if isinstance(history_summary.get("by_signal"), Mapping) else {}
    if isinstance(by_condition.get(condition_key), Mapping):
        candidates.append((f"condicion:{condition_key}", by_condition[condition_key], 3))
    if expiration and isinstance(by_expiration.get(expiration), Mapping):
        candidates.append((f"expiracion:{expiration}", by_expiration[expiration], 5))
    if current_signal and isinstance(by_signal.get(current_signal), Mapping):
        candidates.append((f"senal:{current_signal}", by_signal[current_signal], 8))

    selected_label = "sin_muestra"
    selected_bucket: Mapping[str, Any] = {}
    minimum = 0
    for label, bucket, min_samples in candidates:
        samples = int(_safe_float(bucket.get("signals"), 0.0) or 0)
        if samples >= min_samples:
            selected_label = label
            selected_bucket = bucket
            minimum = min_samples
            break

    samples = int(_safe_float(selected_bucket.get("signals"), 0.0) or 0)
    win_rate = _safe_float(selected_bucket.get("win_rate"))
    expectancy = _safe_float(selected_bucket.get("expectancy"))
    if not selected_bucket:
        verdict = "sin_muestra"
    elif samples < minimum:
        verdict = "muestra_pequena"
    elif (win_rate is not None and win_rate < 0.45) or (expectancy is not None and expectancy < 0):
        verdict = "debil"
    elif (win_rate is not None and win_rate >= 0.58) and (expectancy is not None and expectancy > 0):
        verdict = "validado"
    else:
        verdict = "neutral"
    return {
        "label": selected_label,
        "condition_key": condition_key,
        "samples": samples,
        "minimum_samples": minimum,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "expectancy": round(expectancy, 4) if expectancy is not None else None,
        "verdict": verdict,
    }


def build_strike_dashboard_model(
    *,
    signal: StrikeOptionSignal | Mapping[str, Any] | None = None,
    comparison: StrikeContractComparison | Mapping[str, Any] | None = None,
    history: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a compact, UI-ready model for Strike Options screens.

    The dashboard should not re-interpret trading logic. It should display this
    model, which is produced by the same YES/NO/NO TRADE engine used for logs and
    Deriv contract comparison.
    """
    comparison_data = comparison.to_dict() if isinstance(comparison, StrikeContractComparison) else dict(comparison or {})
    signal_data = signal.to_dict() if isinstance(signal, StrikeOptionSignal) else dict(signal or {})
    best_contract = comparison_data.get("best_contract") if isinstance(comparison_data.get("best_contract"), Mapping) else None
    if best_contract and isinstance(best_contract.get("roxy_signal"), Mapping):
        signal_data = dict(best_contract["roxy_signal"])

    history_rows = list(history or [])
    history_summary = summarize_strike_signal_history(history_rows)
    ranked = comparison_data.get("contracts_ranked") if isinstance(comparison_data.get("contracts_ranked"), list) else []
    current_signal = str(comparison_data.get("signal") or signal_data.get("signal") or SIGNAL_NO_TRADE)
    current_color = str(comparison_data.get("color") or signal_data.get("color") or COLOR_YELLOW)
    status = str(comparison_data.get("status") or ("ready" if current_signal in {SIGNAL_YES, SIGNAL_NO} else "not_ready"))
    confidence = int(_safe_float(comparison_data.get("confidence") or signal_data.get("confidence"), 0.0) or 0)
    strike = _safe_float((best_contract or {}).get("strike") if best_contract else signal_data.get("strike"))
    price = _safe_float(signal_data.get("price"))
    probability_roxy = _safe_float((best_contract or {}).get("probability_roxy") if best_contract else signal_data.get("probability_roxy"))
    edge = _safe_float((best_contract or {}).get("edge") if best_contract else signal_data.get("edge"))
    risk_reward = _safe_float((best_contract or {}).get("risk_reward") if best_contract else signal_data.get("risk_reward"))
    indicators = signal_data.get("indicators") if isinstance(signal_data.get("indicators"), Mapping) else {}
    reasons = list(signal_data.get("reasons")) if isinstance(signal_data.get("reasons"), list) else []
    warnings = list(signal_data.get("warning_flags")) if isinstance(signal_data.get("warning_flags"), list) else []
    checklist = list(signal_data.get("checklist")) if isinstance(signal_data.get("checklist"), list) else []
    score_breakdown = signal_data.get("score_breakdown") if isinstance(signal_data.get("score_breakdown"), Mapping) else {}
    market_regime = str(signal_data.get("market_regime") or indicators.get("market_regime") or "")
    data_quality = str(signal_data.get("data_quality") or indicators.get("data_quality") or "")
    entry_window = str(signal_data.get("entry_window") or "")

    condition_parts: list[str] = []
    ema9 = _safe_float(indicators.get("ema9"))
    ema21 = _safe_float(indicators.get("ema21"))
    if ema9 is not None and ema21 is not None:
        condition_parts.append("EMA9>EMA21" if ema9 > ema21 else "EMA9<EMA21" if ema9 < ema21 else "EMA neutral")
    rsi = _safe_float(indicators.get("rsi"))
    if rsi is not None:
        condition_parts.append(f"RSI {rsi:.1f}")
    volume_bias = indicators.get("volume_bias")
    if volume_bias:
        condition_parts.append(f"volumen {volume_bias}")
    candle_bias = indicators.get("candle_bias")
    if candle_bias:
        condition_parts.append(f"vela {candle_bias}")
    best_condition = " · ".join(condition_parts[:4]) or "Sin condicion dominante validada"

    history_fit = _history_fit_for_signal(
        history_summary,
        signal_data,
        expiration=str(comparison_data.get("expiration") or signal_data.get("expiration") or ""),
        current_signal=current_signal,
    )
    recent = history_summary.get("recent_20") if isinstance(history_summary.get("recent_20"), Mapping) else {}
    recent_win_rate = _safe_float(recent.get("win_rate"))
    recent_expectancy = _safe_float(recent.get("expectancy"))
    recent_samples = int(_safe_float(recent.get("signals"), 0.0) or 0)
    recent_verdict = "sin_muestra"
    if recent_samples >= 8 and ((recent_win_rate is not None and recent_win_rate < 0.45) or (recent_expectancy is not None and recent_expectancy < 0)):
        recent_verdict = "debil"
    elif recent_samples >= 8 and recent_win_rate is not None and recent_win_rate >= 0.58 and recent_expectancy is not None and recent_expectancy > 0:
        recent_verdict = "validado"
    elif recent_samples > 0:
        recent_verdict = "neutral"
    if status == "ready" and current_signal in {SIGNAL_YES, SIGNAL_NO} and history_fit.get("verdict") == "debil":
        current_color = COLOR_YELLOW
        warnings.append("Memoria operativa debil para esta familia de senales; esperar confirmacion adicional.")
    if status == "ready" and current_signal in {SIGNAL_YES, SIGNAL_NO} and recent_verdict == "debil":
        current_color = COLOR_YELLOW
        warnings.append("Memoria reciente debil en las ultimas senales; bajar tamano o esperar confirmacion.")

    decision = "OPERAR AHORA" if status == "ready" and current_signal in {SIGNAL_YES, SIGNAL_NO} else (
        "ESPERAR CONFIRMACION" if current_color == COLOR_YELLOW else "NO OPERAR"
    )
    if (history_fit.get("verdict") == "debil" or recent_verdict == "debil") and decision == "OPERAR AHORA":
        decision = "ESPERAR CONFIRMACION"
    deriv_plan = {
        "asset": comparison_data.get("asset") or signal_data.get("asset"),
        "expiration": comparison_data.get("expiration") or signal_data.get("expiration"),
        "contract": signal_data.get("deriv_contract", {}).get("contract") if isinstance(signal_data.get("deriv_contract"), Mapping) else None,
        "side": current_signal if current_signal in {SIGNAL_YES, SIGNAL_NO} else "WAIT",
        "strike": strike,
        "best_contract": best_contract,
        "contracts_compared": len(ranked),
        "data_quality": comparison_data.get("data_quality") or "signal_only",
    }

    return {
        "status": status,
        "decision": decision,
        "signal": current_signal,
        "color": current_color,
        "asset": comparison_data.get("asset") or signal_data.get("asset"),
        "price": price,
        "strike": strike,
        "confidence": confidence,
        "probability_roxy": probability_roxy,
        "edge": edge,
        "risk_reward": risk_reward,
        "risk": signal_data.get("risk"),
        "decision_state": signal_data.get("decision_state"),
        "market_regime": market_regime,
        "data_quality": data_quality,
        "entry_window": entry_window,
        "checklist": checklist,
        "score_breakdown": dict(score_breakdown),
        "recommended_entry": (best_contract or {}).get("recommended_entry") if best_contract else signal_data.get("recommended_entry"),
        "max_recommended_amount": signal_data.get("max_recommended_amount"),
        "reason": comparison_data.get("reason") or "; ".join(str(reason) for reason in reasons[:2]),
        "reasons": reasons,
        "warning_flags": warnings,
        "deriv_plan": deriv_plan,
        "history": history_summary,
        "win_rate": history_summary.get("win_rate"),
        "best_timeframe": history_summary.get("best_timeframe"),
        "best_condition": best_condition,
        "historical_best_condition": history_summary.get("best_condition"),
        "best_signal": history_summary.get("best_signal"),
        "expectancy": history_summary.get("expectancy"),
        "average_edge": history_summary.get("average_edge"),
        "average_confidence": history_summary.get("average_confidence"),
        "history_fit": history_fit,
        "recent_performance": {
            "signals": recent_samples,
            "win_rate": round(recent_win_rate, 4) if recent_win_rate is not None else None,
            "expectancy": round(recent_expectancy, 4) if recent_expectancy is not None else None,
            "verdict": recent_verdict,
        },
        "ranked_contracts": ranked[:8],
    }


def build_strike_learning_report(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize Roxy's strike journal into operational learning instructions."""
    history_rows = list(rows or [])
    summary = summarize_strike_signal_history(history_rows)
    closed = int(_safe_float(summary.get("closed"), 0.0) or 0)
    no_trade = int(_safe_float(summary.get("no_trade"), 0.0) or 0)
    signals = int(_safe_float(summary.get("signals"), 0.0) or 0)
    win_rate = _safe_float(summary.get("win_rate"))
    expectancy = _safe_float(summary.get("expectancy"))
    recent = summary.get("recent_20") if isinstance(summary.get("recent_20"), Mapping) else {}
    recent_win_rate = _safe_float(recent.get("win_rate"))
    recent_expectancy = _safe_float(recent.get("expectancy"))

    def ranked_bucket(bucket: Mapping[str, Any], *, reverse: bool = True) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for key, value in bucket.items():
            if not isinstance(value, Mapping):
                continue
            bucket_signals = int(_safe_float(value.get("signals"), 0.0) or 0)
            items.append(
                {
                    "key": key,
                    "signals": bucket_signals,
                    "win_rate": value.get("win_rate"),
                    "expectancy": value.get("expectancy"),
                    "profit_loss": value.get("profit_loss"),
                }
            )
        items.sort(
            key=lambda item: (
                _safe_float(item.get("expectancy"), -999.0) or -999.0,
                _safe_float(item.get("win_rate"), -1.0) or -1.0,
                item.get("signals") or 0,
            ),
            reverse=reverse,
        )
        return items

    by_condition = summary.get("by_condition") if isinstance(summary.get("by_condition"), Mapping) else {}
    by_expiration = summary.get("by_expiration") if isinstance(summary.get("by_expiration"), Mapping) else {}
    by_signal = summary.get("by_signal") if isinstance(summary.get("by_signal"), Mapping) else {}
    strongest_conditions = ranked_bucket(by_condition, reverse=True)[:5]
    weakest_conditions = ranked_bucket(by_condition, reverse=False)[:5]
    best_timeframes = ranked_bucket(by_expiration, reverse=True)[:5]
    signal_edges = ranked_bucket(by_signal, reverse=True)

    recommendations: list[str] = []
    if closed < 20:
        recommendations.append("Seguir en paper/backtesting: la muestra cerrada aun es pequena para subir riesgo.")
    if win_rate is not None and win_rate < 0.52:
        recommendations.append("Bajar agresividad: win rate global por debajo de 52%.")
    if expectancy is not None and expectancy < 0:
        recommendations.append("Bloquear entradas con expectancy negativo hasta revisar condiciones.")
    if recent_win_rate is not None and recent_win_rate < 0.45:
        recommendations.append("Pausar senales verdes: la memoria reciente esta debil.")
    if recent_expectancy is not None and recent_expectancy < 0:
        recommendations.append("Reducir monto recomendado: el EV reciente esta negativo.")
    if no_trade > signals and signals:
        recommendations.append("Hay muchas oportunidades bloqueadas; revisar si los strikes estan demasiado cerca o faltan costos reales.")
    if strongest_conditions:
        best = strongest_conditions[0]
        recommendations.append(
            f"Priorizar condicion {best['key']} cuando tenga al menos {best['signals']} muestras y expectancy positivo."
        )
    if not recommendations:
        recommendations.append("Mantener reglas actuales y seguir registrando resultados antes de aumentar riesgo.")

    return {
        "summary": summary,
        "closed_signals": closed,
        "pending_or_no_trade": no_trade,
        "strongest_conditions": strongest_conditions,
        "weakest_conditions": weakest_conditions,
        "best_timeframes": best_timeframes,
        "signal_edges": signal_edges,
        "recommendations": recommendations,
        "operational_policy": {
            "allow_green_signals": bool(
                closed >= 20
                and (win_rate is None or win_rate >= 0.52)
                and (expectancy is None or expectancy >= 0)
                and (recent_win_rate is None or recent_win_rate >= 0.45)
            ),
            "minimum_samples_before_scaling": 50,
            "risk_mode": "paper" if closed < 20 else "reduced" if expectancy is not None and expectancy < 0.05 else "normal",
        },
    }


def log_strike_signal(signal: StrikeOptionSignal, path: str | Path | None = None) -> Path:
    log_path = Path(path or "logs/strike_options_signals.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = signal.to_dict()
    payload.setdefault("result", None)
    payload.setdefault("profit_loss", None)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n")
    return log_path


def load_strike_signal_history(path: str | Path | None = None, *, limit: int = 250) -> list[dict[str, Any]]:
    log_path = Path(path or "logs/strike_options_signals.jsonl")
    if not log_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows[-limit:] if limit > 0 else rows


def _parse_signal_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def strike_signal_expiration_time(row: Mapping[str, Any]) -> datetime | None:
    timestamp = _parse_signal_datetime(row.get("timestamp"))
    if timestamp is None:
        return None
    seconds = _safe_float(row.get("time_remaining_seconds"))
    if seconds is None:
        return None
    return timestamp + timedelta(seconds=max(0, int(seconds)))


def is_strike_signal_expired(
    row: Mapping[str, Any],
    *,
    now: datetime | str | None = None,
    grace_seconds: int = 0,
) -> bool:
    expires_at = strike_signal_expiration_time(row)
    if expires_at is None:
        return False
    if isinstance(now, str):
        now_dt = _parse_signal_datetime(now)
    elif isinstance(now, datetime):
        now_dt = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    else:
        now_dt = datetime.now(timezone.utc)
    if now_dt is None:
        return False
    return now_dt >= expires_at + timedelta(seconds=max(0, grace_seconds))


def summarize_strike_signal_history(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    actionable = [dict(row) for row in rows if row.get("signal") in {SIGNAL_YES, SIGNAL_NO}]
    closed = [row for row in actionable if row.get("result") in CLOSED_RESULTS]
    closed_recent = sorted(
        closed,
        key=lambda row: _parse_signal_datetime(row.get("settled_at") or row.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    wins = sum(1 for row in closed if row.get("result") == "WIN")
    losses = sum(1 for row in closed if row.get("result") == "LOSS")
    win_rate = wins / len(closed) if closed else None
    profit_loss = sum(_safe_float(row.get("profit_loss"), 0.0) or 0.0 for row in closed)
    recent_20 = closed_recent[:20]
    recent_20_profit_loss = sum(_safe_float(row.get("profit_loss"), 0.0) or 0.0 for row in recent_20)
    recent_20_wins = sum(1 for row in recent_20 if row.get("result") == "WIN")
    recent_20_losses = sum(1 for row in recent_20 if row.get("result") == "LOSS")
    by_expiration: dict[str, dict[str, Any]] = {}
    by_signal: dict[str, dict[str, Any]] = {}
    by_condition: dict[str, dict[str, Any]] = {}
    no_trade_count = sum(1 for row in rows if row.get("signal") == SIGNAL_NO_TRADE)
    total_confidence = 0.0
    confidence_count = 0
    total_edge = 0.0
    edge_count = 0
    for row in closed:
        confidence = _safe_float(row.get("confidence"))
        edge = _safe_float(row.get("edge"))
        if confidence is not None:
            total_confidence += confidence
            confidence_count += 1
        if edge is not None:
            total_edge += edge
            edge_count += 1
        for bucket_map, key in (
            (by_expiration, str(row.get("expiration") or "sin_expiracion")),
            (by_signal, str(row.get("signal") or "sin_senal")),
            (by_condition, _condition_key_from_signal(row)),
        ):
            bucket = bucket_map.setdefault(key, {"signals": 0, "wins": 0, "losses": 0, "profit_loss": 0.0})
            bucket["signals"] += 1
            bucket["wins"] += 1 if row.get("result") == "WIN" else 0
            bucket["losses"] += 1 if row.get("result") == "LOSS" else 0
            bucket["profit_loss"] = round(bucket["profit_loss"] + (_safe_float(row.get("profit_loss"), 0.0) or 0.0), 4)
    for bucket_map in (by_expiration, by_signal, by_condition):
        for bucket in bucket_map.values():
            bucket["win_rate"] = round(bucket["wins"] / bucket["signals"], 4) if bucket["signals"] else None
            bucket["expectancy"] = round(bucket["profit_loss"] / bucket["signals"], 4) if bucket["signals"] else None
    best_timeframe = None
    if by_expiration:
        best_timeframe = max(
            by_expiration.items(),
            key=lambda item: (
                item[1].get("expectancy") or 0.0,
                item[1].get("win_rate") or 0.0,
                item[1].get("signals") or 0,
            ),
        )[0]
    best_signal = None
    if by_signal:
        best_signal = max(
            by_signal.items(),
            key=lambda item: (
                item[1].get("expectancy") or 0.0,
                item[1].get("win_rate") or 0.0,
                item[1].get("signals") or 0,
            ),
        )[0]
    best_condition = None
    if by_condition:
        best_condition = max(
            by_condition.items(),
            key=lambda item: (
                item[1].get("expectancy") or 0.0,
                item[1].get("win_rate") or 0.0,
                item[1].get("signals") or 0,
            ),
        )[0]
    return {
        "signals": len(actionable),
        "closed": len(closed),
        "no_trade": no_trade_count,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "profit_loss": round(profit_loss, 4),
        "expectancy": round(profit_loss / len(closed), 4) if closed else None,
        "average_confidence": round(total_confidence / confidence_count, 2) if confidence_count else None,
        "average_edge": round(total_edge / edge_count, 4) if edge_count else None,
        "recent_20": {
            "signals": len(recent_20),
            "wins": recent_20_wins,
            "losses": recent_20_losses,
            "win_rate": round(recent_20_wins / len(recent_20), 4) if recent_20 else None,
            "profit_loss": round(recent_20_profit_loss, 4),
            "expectancy": round(recent_20_profit_loss / len(recent_20), 4) if recent_20 else None,
        },
        "best_timeframe": best_timeframe,
        "best_signal": best_signal,
        "best_condition": best_condition,
        "by_expiration": by_expiration,
        "by_signal": by_signal,
        "by_condition": by_condition,
    }


def score_signal_result(
    signal: StrikeOptionSignal | Mapping[str, Any],
    *,
    final_price: float,
    payout: float | None = None,
    settled_at: str | None = None,
) -> dict[str, Any]:
    data = signal.to_dict() if isinstance(signal, StrikeOptionSignal) else dict(signal)
    side = data.get("signal")
    strike = float(data.get("strike") or 0.0)
    max_loss = _safe_float(data.get("max_loss"), 1.0) or 1.0
    reward = max_loss
    if payout is not None:
        reward = payout - max_loss if payout > max_loss else payout
    if side == SIGNAL_YES:
        won = final_price > strike
    elif side == SIGNAL_NO:
        won = final_price < strike
    else:
        won = False
    data["result"] = "WIN" if won else "LOSS" if side in {SIGNAL_YES, SIGNAL_NO} else "NO_TRADE"
    data["was_correct"] = bool(won) if side in {SIGNAL_YES, SIGNAL_NO} else None
    data["profit_loss"] = round(float(reward if won else -max_loss), 4) if side in {SIGNAL_YES, SIGNAL_NO} else 0.0
    data["final_price"] = final_price
    data["final_distance_pct"] = round(((final_price - strike) / final_price), 6) if final_price else None
    data["settled_at"] = settled_at or datetime.now(timezone.utc).isoformat()
    return data


def settle_strike_signal_rows(
    rows: Sequence[Mapping[str, Any]],
    final_prices_by_asset: Mapping[str, float],
    *,
    payout_by_asset: Mapping[str, float] | None = None,
    settled_at: str | None = None,
) -> dict[str, Any]:
    """Close pending YES/NO rows when a final settlement price is available.

    This is intentionally data-only: it never places trades. It turns pending
    recommendations into auditable outcomes so Roxy can learn which setups are
    actually working.
    """
    prices = {str(key).upper(): _safe_float(value) for key, value in final_prices_by_asset.items()}
    payouts = {str(key).upper(): _safe_float(value) for key, value in (payout_by_asset or {}).items()}
    updated: list[dict[str, Any]] = []
    settled = 0
    skipped = 0
    for row in rows:
        data = dict(row)
        side = data.get("signal")
        result = data.get("result")
        asset = str(data.get("asset") or data.get("symbol") or "").upper()
        final_price = prices.get(asset)
        if side in {SIGNAL_YES, SIGNAL_NO} and result not in CLOSED_RESULTS and final_price is not None:
            data = score_signal_result(
                data,
                final_price=final_price,
                payout=payouts.get(asset) or _safe_float(data.get("payout")),
                settled_at=settled_at,
            )
            settled += 1
        elif side == SIGNAL_NO_TRADE and result is None:
            data["result"] = "NO_TRADE"
            data["profit_loss"] = 0.0
        else:
            skipped += 1
        updated.append(data)
    return {
        "rows": updated,
        "settled": settled,
        "skipped": skipped,
        "summary": summarize_strike_signal_history(updated),
    }


def settle_expired_strike_signal_rows(
    rows: Sequence[Mapping[str, Any]],
    final_prices_by_asset: Mapping[str, float],
    *,
    payout_by_asset: Mapping[str, float] | None = None,
    now: datetime | str | None = None,
    grace_seconds: int = 0,
    settled_at: str | None = None,
) -> dict[str, Any]:
    """Close only expired YES/NO rows and keep active recommendations pending."""
    prices = {str(key).upper(): _safe_float(value) for key, value in final_prices_by_asset.items()}
    payouts = {str(key).upper(): _safe_float(value) for key, value in (payout_by_asset or {}).items()}
    updated: list[dict[str, Any]] = []
    settled = 0
    pending = 0
    skipped = 0
    no_trade_marked = 0
    for row in rows:
        data = dict(row)
        side = data.get("signal")
        result = data.get("result")
        asset = str(data.get("asset") or data.get("symbol") or "").upper()
        if side == SIGNAL_NO_TRADE and result is None:
            data["result"] = "NO_TRADE"
            data["profit_loss"] = 0.0
            no_trade_marked += 1
        elif side in {SIGNAL_YES, SIGNAL_NO} and result not in CLOSED_RESULTS:
            if not is_strike_signal_expired(data, now=now, grace_seconds=grace_seconds):
                pending += 1
            elif prices.get(asset) is None:
                skipped += 1
            else:
                data = score_signal_result(
                    data,
                    final_price=prices[asset] or 0.0,
                    payout=payouts.get(asset) or _safe_float(data.get("payout")),
                    settled_at=settled_at,
                )
                settled += 1
        else:
            skipped += 1
        updated.append(data)
    return {
        "rows": updated,
        "settled": settled,
        "pending": pending,
        "skipped": skipped,
        "no_trade_marked": no_trade_marked,
        "summary": summarize_strike_signal_history(updated),
    }


def settle_strike_signal_history(
    path: str | Path,
    final_prices_by_asset: Mapping[str, float],
    *,
    output_path: str | Path | None = None,
    payout_by_asset: Mapping[str, float] | None = None,
    settled_at: str | None = None,
) -> dict[str, Any]:
    """Load a JSONL strike journal, settle pending rows, and write a JSONL copy."""
    source_path = Path(path)
    rows = load_strike_signal_history(source_path, limit=0)
    result = settle_strike_signal_rows(
        rows,
        final_prices_by_asset,
        payout_by_asset=payout_by_asset,
        settled_at=settled_at,
    )
    target_path = Path(output_path) if output_path is not None else source_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path == source_path and source_path.exists():
        backup_path = source_path.with_suffix(source_path.suffix + ".bak")
        backup_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        result["backup_path"] = str(backup_path)
    with target_path.open("w", encoding="utf-8") as handle:
        for row in result["rows"]:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    result["path"] = str(target_path)
    return result


def settle_expired_strike_signal_history(
    path: str | Path,
    final_prices_by_asset: Mapping[str, float],
    *,
    output_path: str | Path | None = None,
    payout_by_asset: Mapping[str, float] | None = None,
    now: datetime | str | None = None,
    grace_seconds: int = 0,
    settled_at: str | None = None,
) -> dict[str, Any]:
    """Load a strike journal, close expired rows only, and write a JSONL copy."""
    source_path = Path(path)
    rows = load_strike_signal_history(source_path, limit=0)
    result = settle_expired_strike_signal_rows(
        rows,
        final_prices_by_asset,
        payout_by_asset=payout_by_asset,
        now=now,
        grace_seconds=grace_seconds,
        settled_at=settled_at,
    )
    target_path = Path(output_path) if output_path is not None else source_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path == source_path and source_path.exists():
        backup_path = source_path.with_suffix(source_path.suffix + ".bak")
        backup_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        result["backup_path"] = str(backup_path)
    with target_path.open("w", encoding="utf-8") as handle:
        for row in result["rows"]:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    result["path"] = str(target_path)
    return result


def _condition_key_from_signal(row: Mapping[str, Any]) -> str:
    explicit = row.get("condition_key")
    if explicit:
        return str(explicit)
    indicators = row.get("indicators") if isinstance(row.get("indicators"), Mapping) else {}
    signal = str(row.get("signal") or "WAIT")
    parts = [signal]
    ema9 = _safe_float(indicators.get("ema9"))
    ema21 = _safe_float(indicators.get("ema21"))
    if ema9 is not None and ema21 is not None:
        parts.append("ema_bull" if ema9 > ema21 else "ema_bear" if ema9 < ema21 else "ema_flat")
    rsi = _safe_float(indicators.get("rsi"))
    if rsi is not None:
        if rsi >= 70:
            parts.append("rsi_hot")
        elif rsi >= 50:
            parts.append("rsi_bull")
        elif rsi <= 30:
            parts.append("rsi_cold")
        else:
            parts.append("rsi_bear")
    volume_bias = indicators.get("volume_bias")
    if volume_bias:
        parts.append(f"vol_{volume_bias}")
    candle_bias = indicators.get("candle_bias")
    if candle_bias:
        parts.append(f"candle_{candle_bias}")
    return "|".join(parts[:5]) if parts else "sin_condicion"
