from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
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
    result: str | None = None
    profit_loss: float | None = None

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

    momentum_values = [value for value in (momentum_1, momentum_3, momentum_5) if value is not None]
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

    close_strike_threshold = 0.00035
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

    if request.time_remaining_seconds < 60:
        warning_flags.append("Queda menos de 1 minuto.")
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
    bad_edge = edge is not None and edge < 0.03
    bad_rr = risk_reward is not None and risk_reward < 0.55
    too_short = request.time_remaining_seconds < 60 and selected_probability < 88
    too_close = abs_distance_pct <= close_strike_threshold and selected_probability < 78

    blockers = []
    if mixed_signals:
        blockers.append("senales mezcladas")
    if weak_confidence:
        blockers.append("confianza insuficiente")
    if bad_edge:
        blockers.append("edge insuficiente contra el costo del contrato")
    if bad_rr:
        blockers.append("payout no compensa el riesgo")
    if too_short:
        blockers.append("tiempo restante demasiado corto")
    if too_close:
        blockers.append("strike demasiado cerca sin ventaja clara")

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
        max_recommended_amount = round((max_loss or request.stake) * (0.5 if risk == "Medio" else 1.0), 2)

    if not reasons:
        reasons.append("No hay suficientes datos de velas para confirmar una ventaja.")

    deriv_contract = {
        "asset": request.asset,
        "contract": f"{request.asset} will be above ${strike:,.2f}",
        "direction": signal if signal in {SIGNAL_YES, SIGNAL_NO} else "WAIT",
        "strike": strike,
        "expiration": request.expiration_label or f"{request.time_remaining_seconds}s",
        "status": "READY" if signal in {SIGNAL_YES, SIGNAL_NO} and color == COLOR_GREEN else "WAIT",
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
    )


def format_roxy_strike_response(signal: StrikeOptionSignal) -> str:
    reason_text = "\n".join(f"- {reason}" for reason in signal.reasons)
    warning_text = "\n".join(f"- {warning}" for warning in signal.warning_flags) or "- Sin bloqueos criticos."
    return (
        f"Activo: {signal.asset}\n"
        f"Precio actual: {signal.price:,.2f}\n"
        f"Strike: {signal.strike:,.2f}\n"
        f"Tiempo restante: {signal.time_remaining_seconds}s\n"
        f"Senal: {signal.signal}\n"
        f"Confianza: {signal.confidence}%\n"
        f"Razon:\n{reason_text}\n"
        f"Riesgo: {signal.risk}\n"
        f"Entrada recomendada: {signal.recommended_entry}\n"
        f"Monto maximo recomendado: {signal.max_recommended_amount}\n"
        f"Alertas:\n{warning_text}\n"
        f"Comentario de Roxy: {'Operar solo en paper o con riesgo controlado; no hay garantias.' if signal.signal != SIGNAL_NO_TRADE else 'No fuerces la entrada. Espero una ventaja mas clara.'}"
    )


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


def summarize_strike_signal_history(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    actionable = [dict(row) for row in rows if row.get("signal") in {SIGNAL_YES, SIGNAL_NO}]
    closed = [row for row in actionable if row.get("result") in {"WIN", "LOSS"}]
    wins = sum(1 for row in closed if row.get("result") == "WIN")
    losses = sum(1 for row in closed if row.get("result") == "LOSS")
    win_rate = wins / len(closed) if closed else None
    profit_loss = sum(_safe_float(row.get("profit_loss"), 0.0) or 0.0 for row in closed)
    by_expiration: dict[str, dict[str, Any]] = {}
    for row in closed:
        key = str(row.get("expiration") or "sin_expiracion")
        bucket = by_expiration.setdefault(key, {"signals": 0, "wins": 0, "losses": 0, "profit_loss": 0.0})
        bucket["signals"] += 1
        bucket["wins"] += 1 if row.get("result") == "WIN" else 0
        bucket["losses"] += 1 if row.get("result") == "LOSS" else 0
        bucket["profit_loss"] = round(bucket["profit_loss"] + (_safe_float(row.get("profit_loss"), 0.0) or 0.0), 4)
    for bucket in by_expiration.values():
        bucket["win_rate"] = round(bucket["wins"] / bucket["signals"], 4) if bucket["signals"] else None
    best_timeframe = None
    if by_expiration:
        best_timeframe = max(
            by_expiration.items(),
            key=lambda item: ((item[1].get("win_rate") or 0.0), item[1].get("signals") or 0),
        )[0]
    return {
        "signals": len(actionable),
        "closed": len(closed),
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "profit_loss": round(profit_loss, 4),
        "best_timeframe": best_timeframe,
        "by_expiration": by_expiration,
    }


def score_signal_result(
    signal: StrikeOptionSignal | Mapping[str, Any],
    *,
    final_price: float,
    payout: float | None = None,
) -> dict[str, Any]:
    data = signal.to_dict() if isinstance(signal, StrikeOptionSignal) else dict(signal)
    side = data.get("signal")
    strike = float(data.get("strike") or 0.0)
    max_loss = _safe_float(data.get("max_loss"), 1.0) or 1.0
    reward = payout if payout is not None else max_loss
    if side == SIGNAL_YES:
        won = final_price > strike
    elif side == SIGNAL_NO:
        won = final_price < strike
    else:
        won = False
    data["result"] = "WIN" if won else "LOSS" if side in {SIGNAL_YES, SIGNAL_NO} else "NO_TRADE"
    data["profit_loss"] = round(float(reward if won else -max_loss), 4) if side in {SIGNAL_YES, SIGNAL_NO} else 0.0
    data["final_price"] = final_price
    return data
