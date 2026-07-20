from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import math
from typing import Any, Mapping, Sequence

import pandas as pd

from roxy_trader.indicators import IndicatorConfig, add_indicators as add_central_indicators


VISUAL_STRATEGY_ENGINE_VERSION = "roxy-visual-strategies/1.1.0"


COMMON_STATUSES = {
    "SCANNING",
    "CANDIDATE",
    "WATCHING",
    "NEAR_ENTRY",
    "WAITING_CONFIRMATION",
    "READY",
    "ACTIVE",
    "LATE_ENTRY",
    "PARTIAL_TARGET",
    "PRIMARY_TARGET",
    "PROTECT_PROFIT",
    "EXIT",
    "STOPPED",
    "INVALIDATED",
    "EXPIRED",
    "AWAITING_BREAKOUT",
    "DATA_INSUFFICIENT",
}


@dataclass(frozen=True)
class OperationalStrategySignal:
    symbol: str
    strategy: str
    setupType: str
    direction: str
    status: str
    currentPrice: float | None
    entryZoneLow: float | None
    entryZoneHigh: float | None
    confirmationPrice: float | None
    stopPrice: float | None
    partialTarget: float | None
    primaryTarget: float | None
    secondaryTarget: float | None
    invalidationPrice: float | None
    riskPerShare: float | None
    potentialReward: float | None
    riskReward: float | None
    confidence: int
    timeframeEntry: str
    timeframeConfirmation: str
    detectedAt: str
    expiresAt: str
    provider: str
    providerTimestamp: str | None
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    chartAnnotations: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    voiceExplanation: str = ""
    monitoring: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def _round_price(value: float | None) -> float | None:
    if value is None:
        return None
    if abs(value) >= 100:
        return round(value, 2)
    if abs(value) >= 10:
        return round(value, 3)
    return round(value, 4)


def _empty_signal(
    *,
    symbol: str,
    status: str,
    provider: str,
    provider_timestamp: str | None,
    warnings: list[str],
    now: datetime,
) -> OperationalStrategySignal:
    return OperationalStrategySignal(
        symbol=symbol.upper(),
        strategy="Uptrend Pullback to EMA21",
        setupType="UPTREND_PULLBACK_EMA21",
        direction="LONG",
        status=status,
        currentPrice=None,
        entryZoneLow=None,
        entryZoneHigh=None,
        confirmationPrice=None,
        stopPrice=None,
        partialTarget=None,
        primaryTarget=None,
        secondaryTarget=None,
        invalidationPrice=None,
        riskPerShare=None,
        potentialReward=None,
        riskReward=None,
        confidence=0,
        timeframeEntry="15m",
        timeframeConfirmation="1h",
        detectedAt=now.isoformat(),
        expiresAt=(now + timedelta(minutes=45)).isoformat(),
        provider=provider,
        providerTimestamp=provider_timestamp,
        reasons=[],
        warnings=warnings,
        chartAnnotations=[],
        metrics={},
        voiceExplanation="No tengo suficientes datos confiables para recomendar una entrada.",
        monitoring={"refreshSeconds": 15, "nextAction": "Esperar datos completos."},
    )


def _normalize_ohlcv(candles: Any) -> pd.DataFrame:
    if candles is None:
        return pd.DataFrame()
    if isinstance(candles, pd.DataFrame):
        df = candles.copy()
    else:
        rows: list[Mapping[str, Any]] = []
        if isinstance(candles, Sequence) and not isinstance(candles, (str, bytes)):
            rows = [row for row in candles if isinstance(row, Mapping)]
        df = pd.DataFrame(rows)
    if df.empty:
        return df

    lower_map = {str(col).lower(): col for col in df.columns}
    renamed: dict[Any, str] = {}
    aliases = {
        "open": ("open", "o"),
        "high": ("high", "h"),
        "low": ("low", "l"),
        "close": ("close", "c", "price", "last"),
        "volume": ("volume", "v"),
        "time": ("time", "timestamp", "ts", "t", "datetime", "date"),
    }
    for target, names in aliases.items():
        for name in names:
            if name in lower_map:
                renamed[lower_map[name]] = target
                break
    df = df.rename(columns=renamed)
    for column in ("open", "high", "low", "close", "volume"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    if "time" not in df.columns:
        df["time"] = range(len(df))
    else:
        parsed_time = pd.to_datetime(df["time"], utc=True, errors="coerce")
        if parsed_time.notna().any():
            df["time"] = parsed_time
    required = {"open", "high", "low", "close"}
    if not required.issubset(set(df.columns)):
        return pd.DataFrame()
    return df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "close" not in df.columns:
        return df.copy()
    return add_central_indicators(
        df,
        config=IndicatorConfig(sma_windows=(50, 200), ema_windows=(9, 21)),
    )


def _slope_pct(series: pd.Series, periods: int = 8) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) <= periods:
        return None
    old = _safe_float(clean.iloc[-(periods + 1)])
    new = _safe_float(clean.iloc[-1])
    if old is None or new is None or old == 0:
        return None
    return ((new / old) - 1.0) * 100.0


def _pivot_values(df: pd.DataFrame, column: str, *, mode: str) -> list[float]:
    values: list[float] = []
    if len(df) < 5:
        return values
    for index in range(2, len(df) - 2):
        current = float(df[column].iloc[index])
        window = df[column].iloc[index - 2 : index + 3]
        if mode == "high" and current == float(window.max()):
            values.append(current)
        if mode == "low" and current == float(window.min()):
            values.append(current)
    return values[-6:]


def _higher_sequence_count(values: list[float]) -> int:
    if len(values) < 2:
        return 0
    count = 0
    for prev, current in zip(values, values[1:]):
        if current > prev:
            count += 1
    return count


def _nearest_resistance(df: pd.DataFrame, price: float) -> float | None:
    pivot_highs = _pivot_values(df.tail(100), "high", mode="high")
    structural_above = [float(value) for value in pivot_highs if float(value) > price]
    if structural_above:
        return min(structural_above)
    highs = pd.to_numeric(df["high"], errors="coerce").dropna()
    if highs.empty:
        return None
    recent_max = float(highs.tail(80).max())
    if recent_max > price * 1.003:
        return recent_max
    return None


def _pivot_points(df: pd.DataFrame, column: str, *, mode: str) -> list[tuple[int, float]]:
    points: list[tuple[int, float]] = []
    if len(df) < 7 or column not in df.columns:
        return points
    values = pd.to_numeric(df[column], errors="coerce")
    for index in range(2, len(df) - 2):
        current = _safe_float(values.iloc[index])
        if current is None:
            continue
        window = values.iloc[index - 2 : index + 3].dropna()
        if len(window) < 5:
            continue
        if mode == "high" and current >= float(window.max()):
            points.append((index, current))
        elif mode == "low" and current <= float(window.min()):
            points.append((index, current))
    return points


def _linear_fit(points: list[tuple[int, float]]) -> tuple[float, float] | None:
    if len(points) < 2:
        return None
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator <= 0:
        return None
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator
    return slope, y_mean - slope * x_mean


def _epoch_seconds(value: Any, fallback: int) -> int:
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.notna(parsed):
        return int(parsed.timestamp())
    return int(fallback)


def detect_visual_price_structures(
    *,
    symbol: str,
    candles: Any,
    timeframe: str,
    provider: str = "unknown",
) -> list[dict[str, Any]]:
    """Detect a small, auditable set of structures and return chart geometry."""
    df = _add_indicators(_normalize_ohlcv(candles))
    if len(df) < 40:
        return []
    window = df.tail(72).reset_index(drop=True)
    last = window.iloc[-1]
    current = _safe_float(last.get("close"))
    if current is None or current <= 0:
        return []
    results: list[dict[str, Any]] = []

    def add_signal(
        setup_type: str,
        strategy: str,
        direction: str,
        status: str,
        confidence: int,
        reasons: list[str],
        annotations: list[dict[str, Any]],
        warnings: list[str] | None = None,
    ) -> None:
        results.append(
            {
                "symbol": str(symbol or "").upper(),
                "setupType": setup_type,
                "strategy": strategy,
                "direction": direction,
                "status": status,
                "confidence": int(max(0, min(100, confidence))),
                "timeframe": timeframe,
                "provider": provider,
                "providerTimestamp": (
                    pd.to_datetime(last.get("time"), utc=True, errors="coerce").isoformat()
                    if pd.notna(pd.to_datetime(last.get("time"), utc=True, errors="coerce"))
                    else None
                ),
                "reasons": reasons,
                "warnings": list(warnings or []),
                "chartAnnotations": annotations,
            }
        )

    ema9 = _safe_float(last.get("ema9"))
    ema21 = _safe_float(last.get("ema21"))
    ema50 = _safe_float(last.get("ema50"))
    ema21_slope = _slope_pct(window["ema21"], 8) or 0.0
    if all(value is not None for value in (ema9, ema21, ema50)):
        if current > ema9 > ema21 > ema50 and ema21_slope > 0:
            add_signal(
                "UPTREND",
                "Tendencia alcista",
                "LONG",
                "DETECTED",
                72,
                ["Precio y EMA9 están sobre EMA21/EMA50.", "La pendiente EMA21 es positiva."],
                [],
            )
        elif current < ema9 < ema21 < ema50 and ema21_slope < 0:
            add_signal(
                "DOWNTREND",
                "Tendencia bajista",
                "SHORT",
                "DETECTED",
                72,
                ["Precio y EMA9 están debajo de EMA21/EMA50.", "La pendiente EMA21 es negativa."],
                [],
            )

    previous = window.iloc[-2]
    previous_ema9 = _safe_float(previous.get("ema9"))
    previous_ema21 = _safe_float(previous.get("ema21"))
    if all(value is not None for value in (ema9, ema21, previous_ema9, previous_ema21)):
        if previous_ema9 <= previous_ema21 and ema9 > ema21:
            add_signal(
                "EMA_BULLISH_CROSS",
                "Cruce alcista EMA9/EMA21",
                "LONG",
                "WAITING_CONFIRMATION",
                68,
                ["EMA9 cruzó sobre EMA21 en la última vela.", "Roxy espera confirmación de precio y volumen."],
                [{"type": "PRICE_MARKER", "label": "Cruce EMA9/21 alcista", "timeframe": timeframe, "value": _round_price(current)}],
            )
        elif previous_ema9 >= previous_ema21 and ema9 < ema21:
            add_signal(
                "EMA_BEARISH_CROSS",
                "Cruce bajista EMA9/EMA21",
                "SHORT",
                "WAITING_CONFIRMATION",
                68,
                ["EMA9 cruzó debajo de EMA21 en la última vela.", "Roxy espera confirmación de precio y volumen."],
                [{"type": "PRICE_MARKER", "label": "Cruce EMA9/21 bajista", "timeframe": timeframe, "value": _round_price(current)}],
            )

    rsi = _safe_float(last.get("rsi14"))
    if rsi is not None and rsi >= 70:
        add_signal(
            "RSI_OVERBOUGHT",
            "Sobrecompra RSI",
            "WAIT",
            "WATCHING",
            min(88, int(55 + (rsi - 70) * 2)),
            [f"RSI14 en {rsi:.1f}, por encima de 70."],
            [{"type": "PRICE_MARKER", "label": f"RSI {rsi:.1f} sobrecompra", "timeframe": timeframe, "value": _round_price(current)}],
            ["Sobrecompra no es una señal automática de venta; exige pérdida de estructura."],
        )
    elif rsi is not None and rsi <= 30:
        add_signal(
            "RSI_OVERSOLD",
            "Sobreventa RSI",
            "WAIT",
            "WATCHING",
            min(88, int(55 + (30 - rsi) * 2)),
            [f"RSI14 en {rsi:.1f}, por debajo de 30."],
            [{"type": "PRICE_MARKER", "label": f"RSI {rsi:.1f} sobreventa", "timeframe": timeframe, "value": _round_price(current)}],
            ["Sobreventa no es una señal automática de compra; exige recuperación de estructura."],
        )

    for mode, setup_type, strategy, direction in (
        ("low", "BULLISH_RSI_DIVERGENCE", "Divergencia alcista RSI", "LONG"),
        ("high", "BEARISH_RSI_DIVERGENCE", "Divergencia bajista RSI", "SHORT"),
    ):
        price_column = "low" if mode == "low" else "high"
        pivots = _pivot_points(window, price_column, mode=mode)[-4:]
        if len(pivots) < 2:
            continue
        first_pivot, second_pivot = pivots[-2], pivots[-1]
        if second_pivot[0] - first_pivot[0] < 4:
            continue
        first_rsi = _safe_float(window.iloc[first_pivot[0]].get("rsi14"))
        second_rsi = _safe_float(window.iloc[second_pivot[0]].get("rsi14"))
        if first_rsi is None or second_rsi is None or first_pivot[1] <= 0:
            continue
        price_change_pct = ((second_pivot[1] / first_pivot[1]) - 1.0) * 100.0
        rsi_change = second_rsi - first_rsi
        divergent = (
            mode == "low" and price_change_pct <= -0.25 and rsi_change >= 3.0
        ) or (
            mode == "high" and price_change_pct >= 0.25 and rsi_change <= -3.0
        )
        if not divergent:
            continue
        start_time = _epoch_seconds(window.iloc[first_pivot[0]].get("time"), first_pivot[0])
        end_time = _epoch_seconds(window.iloc[second_pivot[0]].get("time"), second_pivot[0])
        add_signal(
            setup_type,
            strategy,
            direction,
            "WAITING_CONFIRMATION",
            min(86, int(64 + abs(rsi_change))),
            [
                f"Precio entre pivotes {price_change_pct:+.2f}%.",
                f"RSI entre pivotes {rsi_change:+.1f} puntos.",
                "La divergencia requiere confirmación de ruptura de estructura.",
            ],
            [
                {
                    "type": "TREND_LINE",
                    "role": "bullish_divergence" if mode == "low" else "bearish_divergence",
                    "label": strategy,
                    "timeframe": timeframe,
                    "startTime": start_time,
                    "endTime": end_time,
                    "startValue": _round_price(first_pivot[1]),
                    "endValue": _round_price(second_pivot[1]),
                }
            ],
        )

    highs = _pivot_points(window, "high", mode="high")[-5:]
    lows = _pivot_points(window, "low", mode="low")[-5:]
    high_fit = _linear_fit(highs)
    low_fit = _linear_fit(lows)
    if high_fit and low_fit and len(highs) >= 2 and len(lows) >= 2:
        upper_slope, upper_intercept = high_fit
        lower_slope, lower_intercept = low_fit
        start_index = max(0, min(highs[0][0], lows[0][0]))
        end_index = len(window) - 1
        upper_start = upper_slope * start_index + upper_intercept
        upper_end = upper_slope * end_index + upper_intercept
        lower_start = lower_slope * start_index + lower_intercept
        lower_end = lower_slope * end_index + lower_intercept
        gap_start = upper_start - lower_start
        gap_end = upper_end - lower_end
        convergence = gap_start > 0 and gap_end > 0 and gap_end < gap_start * 0.86
        upper_pct = (upper_slope / current) * 100.0
        lower_pct = (lower_slope / current) * 100.0
        setup_type = ""
        strategy = ""
        direction = "WAIT"
        if convergence and upper_pct < -0.015 and lower_pct > 0.015:
            setup_type, strategy = "SYMMETRIC_TRIANGLE", "Triangulo simetrico"
        elif convergence and abs(upper_pct) <= 0.025 and lower_pct > 0.015:
            setup_type, strategy, direction = "ASCENDING_TRIANGLE", "Triangulo ascendente", "LONG"
        elif convergence and upper_pct < -0.015 and abs(lower_pct) <= 0.025:
            setup_type, strategy, direction = "DESCENDING_TRIANGLE", "Triangulo descendente", "SHORT"
        elif convergence and upper_pct > 0 and lower_pct > upper_pct + 0.01:
            setup_type, strategy, direction = "RISING_WEDGE", "Wedge ascendente", "SHORT"
        elif convergence and lower_pct < 0 and upper_pct < lower_pct - 0.01:
            setup_type, strategy, direction = "FALLING_WEDGE", "Wedge descendente", "LONG"
        if setup_type:
            start_time = _epoch_seconds(window.iloc[start_index].get("time"), start_index)
            end_time = _epoch_seconds(window.iloc[end_index].get("time"), end_index)
            progress = max(0, min(100, int(round((1.0 - gap_end / gap_start) * 100))))
            annotations = [
                {
                    "type": "TREND_LINE",
                    "role": "resistance",
                    "label": "Resistencia estructura",
                    "timeframe": timeframe,
                    "startTime": start_time,
                    "endTime": end_time,
                    "startValue": _round_price(upper_start),
                    "endValue": _round_price(upper_end),
                },
                {
                    "type": "TREND_LINE",
                    "role": "support",
                    "label": "Soporte estructura",
                    "timeframe": timeframe,
                    "startTime": start_time,
                    "endTime": end_time,
                    "startValue": _round_price(lower_start),
                    "endValue": _round_price(lower_end),
                },
            ]
            distance_to_resistance = abs(upper_end - current) / current
            distance_to_support = abs(current - lower_end) / current
            near_label = (
                "Precio cerca de resistencia."
                if distance_to_resistance <= 0.008
                else "Precio cerca de soporte."
                if distance_to_support <= 0.008
                else "Precio dentro de la estructura."
            )
            add_signal(
                setup_type,
                strategy,
                direction,
                "AWAITING_BREAKOUT",
                58 + min(24, progress // 3),
                [f"Convergencia geométrica {progress}%.", near_label, f"{len(highs)} pivotes altos y {len(lows)} pivotes bajos."],
                annotations,
                ["La estructura se invalida si el precio deja de respetar una de las dos líneas."],
            )

    recent = window.tail(21)
    prior = recent.iloc[:-1]
    prior_high = _safe_float(prior["high"].max())
    prior_low = _safe_float(prior["low"].min())
    average_volume = _safe_float(pd.to_numeric(prior["volume"], errors="coerce").mean()) or 0.0
    current_volume = _safe_float(last.get("volume")) or 0.0
    relative_volume = current_volume / average_volume if average_volume > 0 else 0.0
    if relative_volume >= 1.5:
        candle_direction = "LONG" if current >= (_safe_float(last.get("open")) or current) else "SHORT"
        add_signal(
            "VOLUME_SURGE",
            "Incremento de volumen",
            candle_direction,
            "DETECTED",
            min(92, int(62 + (relative_volume - 1.5) * 12)),
            [f"Volumen de la vela actual {relative_volume:.2f}x sobre el promedio de 20 velas."],
            [{"type": "PRICE_MARKER", "label": f"Volumen {relative_volume:.2f}x", "timeframe": timeframe, "value": _round_price(current)}],
        )
    if prior_high and current > prior_high * 1.001:
        confirmed = relative_volume >= 1.2
        add_signal(
            "BREAKOUT",
            "Ruptura alcista",
            "LONG",
            "READY" if confirmed else "WAITING_CONFIRMATION",
            82 if confirmed else 64,
            ["Cierre sobre el máximo de las 20 velas previas.", f"Volumen relativo {relative_volume:.2f}x."],
            [{"type": "BREAKOUT_LEVEL", "label": "Nivel de ruptura", "timeframe": timeframe, "value": _round_price(prior_high)}],
            [] if confirmed else ["Falta volumen de confirmación >= 1.2x."],
        )
    elif prior_low and current < prior_low * 0.999:
        confirmed = relative_volume >= 1.2
        add_signal(
            "BREAKDOWN",
            "Ruptura bajista",
            "SHORT",
            "READY" if confirmed else "WAITING_CONFIRMATION",
            82 if confirmed else 64,
            ["Cierre debajo del mínimo de las 20 velas previas.", f"Volumen relativo {relative_volume:.2f}x."],
            [{"type": "BREAKOUT_LEVEL", "label": "Nivel de ruptura", "timeframe": timeframe, "value": _round_price(prior_low)}],
            [] if confirmed else ["Falta volumen de confirmación >= 1.2x."],
        )

    if not any(item["setupType"] in {"BREAKOUT", "BREAKDOWN"} for item in results):
        for offset in range(2, min(11, len(window) - 21)):
            breakout_index = len(window) - 1 - offset
            history = window.iloc[max(0, breakout_index - 20) : breakout_index]
            breakout_row = window.iloc[breakout_index]
            if history.empty:
                continue
            level_high = _safe_float(history["high"].max())
            level_low = _safe_float(history["low"].min())
            breakout_close = _safe_float(breakout_row.get("close"))
            if breakout_close is None:
                continue
            if level_high and breakout_close > level_high * 1.001 and current >= level_high and (_safe_float(last.get("low")) or current) <= level_high * 1.006:
                confirmed = current > (_safe_float(last.get("open")) or current) and relative_volume >= 0.8
                add_signal(
                    "BULLISH_RETEST",
                    "Retesteo alcista",
                    "LONG",
                    "READY" if confirmed else "WAITING_CONFIRMATION",
                    78 if confirmed else 65,
                    [f"Ruptura ocurrió hace {offset} velas.", "El precio volvió al nivel roto y lo conserva como soporte."],
                    [{"type": "RETEST_LEVEL", "label": "Nivel de retesteo alcista", "timeframe": timeframe, "value": _round_price(level_high)}],
                    [] if confirmed else ["Falta vela alcista con volumen relativo >= 0.8x."],
                )
                break
            if level_low and breakout_close < level_low * 0.999 and current <= level_low and (_safe_float(last.get("high")) or current) >= level_low * 0.994:
                confirmed = current < (_safe_float(last.get("open")) or current) and relative_volume >= 0.8
                add_signal(
                    "BEARISH_RETEST",
                    "Retesteo bajista",
                    "SHORT",
                    "READY" if confirmed else "WAITING_CONFIRMATION",
                    78 if confirmed else 65,
                    [f"Ruptura bajista ocurrió hace {offset} velas.", "El precio volvió al nivel roto y lo respeta como resistencia."],
                    [{"type": "RETEST_LEVEL", "label": "Nivel de retesteo bajista", "timeframe": timeframe, "value": _round_price(level_low)}],
                    [] if confirmed else ["Falta vela bajista con volumen relativo >= 0.8x."],
                )
                break

    if not any(item["setupType"] in {"BREAKOUT", "BREAKDOWN"} for item in results):
        range_high = _safe_float(recent["high"].max())
        range_low = _safe_float(recent["low"].min())
        range_pct = ((range_high - range_low) / current) * 100 if range_high and range_low else 100.0
        if range_high and range_low and range_pct <= 3.5:
            add_signal(
                "CONSOLIDATION",
                "Consolidacion",
                "WAIT",
                "AWAITING_BREAKOUT",
                max(45, min(72, int(78 - range_pct * 8))),
                [f"Rango de 20 velas limitado a {range_pct:.2f}%."],
                [
                    {"type": "RESISTANCE", "label": "Resistencia rango", "timeframe": timeframe, "value": _round_price(range_high)},
                    {"type": "SUPPORT", "label": "Soporte rango", "timeframe": timeframe, "value": _round_price(range_low)},
                ],
            )

    support_candidates = [value for _index, value in _pivot_points(window, "low", mode="low") if value < current]
    resistance_candidates = [value for _index, value in _pivot_points(window, "high", mode="high") if value > current]
    if support_candidates and resistance_candidates:
        support = max(support_candidates)
        resistance = min(resistance_candidates)
        if support < current < resistance:
            add_signal(
                "SUPPORT_RESISTANCE",
                "Soporte y resistencia",
                "WAIT",
                "WATCHING",
                56,
                ["Niveles derivados de pivotes confirmados, no de valores manuales."],
                [
                    {"type": "SUPPORT", "label": "Soporte por pivotes", "timeframe": timeframe, "value": _round_price(support)},
                    {"type": "RESISTANCE", "label": "Resistencia por pivotes", "timeframe": timeframe, "value": _round_price(resistance)},
                ],
            )

    priority = {
        "BREAKOUT": 0,
        "BREAKDOWN": 0,
        "BULLISH_RETEST": 1,
        "BEARISH_RETEST": 1,
        "BULLISH_RSI_DIVERGENCE": 1,
        "BEARISH_RSI_DIVERGENCE": 1,
        "ASCENDING_TRIANGLE": 1,
        "DESCENDING_TRIANGLE": 1,
        "SYMMETRIC_TRIANGLE": 1,
        "RISING_WEDGE": 1,
        "FALLING_WEDGE": 1,
        "CONSOLIDATION": 2,
        "EMA_BULLISH_CROSS": 2,
        "EMA_BEARISH_CROSS": 2,
        "VOLUME_SURGE": 3,
        "RSI_OVERBOUGHT": 4,
        "RSI_OVERSOLD": 4,
        "SUPPORT_RESISTANCE": 5,
        "UPTREND": 3,
        "DOWNTREND": 3,
    }
    return sorted(results, key=lambda item: (priority.get(item["setupType"], 9), -int(item["confidence"])))


def evaluate_uptrend_pullback_to_ema21(
    *,
    symbol: str,
    candles_1h: Any,
    candles_15m: Any,
    provider: str = "unknown",
    provider_timestamp: str | None = None,
    screener_reason: str | None = None,
    relative_strength: float | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate a provider-backed 1h uptrend + 15m EMA21 pullback for stocks or crypto."""
    now = now or datetime.now(timezone.utc)
    symbol = (symbol or "").upper().strip() or "UNKNOWN"
    h1 = _add_indicators(_normalize_ohlcv(candles_1h))
    m15 = _add_indicators(_normalize_ohlcv(candles_15m))
    if len(h1) < 55 or len(m15) < 35:
        return _empty_signal(
            symbol=symbol,
            status="DATA_INSUFFICIENT",
            provider=provider,
            provider_timestamp=provider_timestamp,
            warnings=[
                "Se requieren al menos 55 velas de 1h y 35 velas de 15m para validar estructura.",
                "Roxy no genera entrada cuando la muestra no es confiable.",
            ],
            now=now,
        ).to_dict()

    last_1h = h1.iloc[-1]
    last_15m = m15.iloc[-1]
    prev_15m = m15.iloc[-2]
    current_price = float(last_15m["close"])
    atr = float(last_15m["atr14"] or max(0.01, current_price * 0.005))
    ema9_1h = float(last_1h["ema9"])
    ema21_1h = float(last_1h["ema21"])
    ema21_15m = float(last_15m["ema21"])
    ema9_15m = float(last_15m["ema9"])
    rsi = float(last_15m["rsi14"])
    relative_volume = float(last_15m["relative_volume"])
    highs = _pivot_values(h1, "high", mode="high")
    lows = _pivot_values(h1, "low", mode="low")
    higher_high_count = _higher_sequence_count(highs)
    higher_low_count = _higher_sequence_count(lows)
    ema21_slope_1h = _slope_pct(h1["ema21"], 8) or 0.0
    ema9_slope_15m = _slope_pct(m15["ema9"], 5) or 0.0
    resistance = _nearest_resistance(h1, current_price)
    distance_to_ema9 = ((current_price / ema9_15m) - 1.0) * 100.0 if ema9_15m else 0.0
    distance_to_ema21 = ((current_price / ema21_15m) - 1.0) * 100.0 if ema21_15m else 0.0
    distance_to_resistance = ((resistance / current_price) - 1.0) * 100.0 if resistance else None
    extension_from_ema = abs(distance_to_ema21)
    trend_strength = 0
    reasons: list[str] = []
    warnings: list[str] = []

    if current_price > ema21_1h:
        trend_strength += 18
        reasons.append("Precio sobre EMA21 en 1h.")
    else:
        warnings.append("Precio debajo de EMA21 en 1h; tendencia no confirmada.")
    if ema9_1h > ema21_1h:
        trend_strength += 16
        reasons.append("EMA9 sobre EMA21 en 1h.")
    else:
        warnings.append("EMA9 no domina EMA21 en 1h.")
    if ema21_slope_1h > 0:
        trend_strength += 14
        reasons.append("Pendiente de EMA21 1h positiva.")
    else:
        warnings.append("Pendiente de EMA21 1h plana o bajista.")
    if higher_high_count >= 2:
        trend_strength += 12
        reasons.append(f"Estructura con {higher_high_count} máximos crecientes recientes.")
    if higher_low_count >= 2:
        trend_strength += 12
        reasons.append(f"Estructura con {higher_low_count} mínimos crecientes recientes.")
    if relative_strength is not None and relative_strength > 0:
        trend_strength += 8
        reasons.append("Fuerza relativa positiva contra el mercado.")
    if relative_volume >= 1.1:
        trend_strength += 8
        reasons.append("Volumen relativo confirma participación.")
    if distance_to_resistance is None or distance_to_resistance >= 1.2:
        trend_strength += 12
        reasons.append("Hay espacio razonable hasta resistencia.")
    else:
        warnings.append("Resistencia cercana reduce margen de ganancia.")

    near_ema21 = abs(current_price - ema21_15m) <= max(atr * 0.85, current_price * 0.008)
    rejection_candle = (
        float(last_15m["close"]) > float(last_15m["open"])
        and float(last_15m["low"]) <= ema21_15m + atr * 0.45
        and float(last_15m["close"]) >= float(prev_15m["high"]) - atr * 0.15
    )
    if near_ema21:
        reasons.append("Precio cerca de la EMA21 en 15m; zona de pullback activa.")
    else:
        warnings.append("Precio no está en zona óptima de EMA21 15m.")
    if rejection_candle:
        reasons.append("Vela 15m muestra rechazo alcista y recuperación.")
    else:
        warnings.append("Todavía falta vela de confirmación alcista.")

    entry_low = ema21_15m - atr * 0.35
    entry_high = ema21_15m + atr * 0.45
    confirmation = max(float(last_15m["high"]), float(prev_15m["high"]))
    swing_lows = _pivot_values(m15.tail(60), "low", mode="low")
    recent_higher_low = swing_lows[-1] if swing_lows else float(m15["low"].tail(12).min())
    stop = min(recent_higher_low, entry_low) - atr * 0.25
    entry_reference = max(current_price, confirmation)
    risk = max(0.01, entry_reference - stop)
    partial = entry_reference + risk
    primary = entry_reference + risk * 2.0
    secondary = entry_reference + risk * 3.0
    if resistance and resistance > entry_reference:
        primary = min(primary, resistance)
    reward = primary - entry_reference
    risk_reward = reward / risk if risk > 0 else None

    status = "WATCHING"
    if current_price <= stop:
        status = "INVALIDATED"
        warnings.append("Precio tocó o perdió el nivel de invalidación.")
    elif trend_strength < 54:
        status = "WATCHING"
    elif extension_from_ema > 3.0:
        status = "LATE_ENTRY"
        warnings.append("Entrada tardía: precio extendido de EMA21.")
    elif near_ema21 and not rejection_candle:
        status = "WAITING_CONFIRMATION"
    elif near_ema21 and rejection_candle and (risk_reward or 0) >= 1.6:
        status = "READY"
    elif near_ema21:
        status = "NEAR_ENTRY"
    if risk_reward is not None and risk_reward < 1.4:
        status = "WAITING_CONFIRMATION" if status == "READY" else status
        warnings.append("Riesgo/beneficio todavía no es suficiente.")

    confidence = int(max(0, min(100, trend_strength + (10 if near_ema21 else 0) + (12 if rejection_candle else 0))))
    metrics = {
        "trendStrength": trend_strength,
        "higherHighCount": higher_high_count,
        "higherLowCount": higher_low_count,
        "trendlineSlope": round(ema21_slope_1h, 3),
        "distanceToTrendline": None,
        "distanceToEMA9": round(distance_to_ema9, 3),
        "distanceToEMA21": round(distance_to_ema21, 3),
        "distanceToResistance": round(distance_to_resistance, 3) if distance_to_resistance is not None else None,
        "extensionFromEMA": round(extension_from_ema, 3),
        "relativeStrength": relative_strength,
        "volumeConfirmation": round(relative_volume, 2),
        "ema9_1h": _round_price(ema9_1h),
        "ema21_1h": _round_price(ema21_1h),
        "ema9_15m": _round_price(ema9_15m),
        "ema21_15m": _round_price(ema21_15m),
        "rsi14": round(rsi, 2),
    }
    chart_annotations = [
        {"type": "EMA", "label": "EMA9 15m", "timeframe": "15m", "value": _round_price(ema9_15m)},
        {"type": "EMA", "label": "EMA21 15m", "timeframe": "15m", "value": _round_price(ema21_15m)},
        {
            "type": "ENTRY_ZONE",
            "label": "Pullback EMA21",
            "timeframe": "15m",
            "low": _round_price(entry_low),
            "high": _round_price(entry_high),
        },
        {"type": "CONFIRMATION", "label": "Cierre sobre activación", "timeframe": "15m", "value": _round_price(confirmation)},
        {"type": "STOP_LINE", "label": "Stop bajo último HL", "timeframe": "15m", "value": _round_price(stop)},
        {"type": "TARGET", "label": "Parcial 1R", "timeframe": "15m", "value": _round_price(partial)},
        {"type": "TARGET", "label": "Objetivo principal", "timeframe": "1h", "value": _round_price(primary)},
        {"type": "TARGET", "label": "Objetivo extendido", "timeframe": "1h", "value": _round_price(secondary)},
        {"type": "INVALIDATION", "label": "Invalidación", "timeframe": "15m", "value": _round_price(stop)},
        {
            "type": "TREND_HEALTH",
            "label": "Trend Health",
            "timeframe": "1h",
            "value": confidence,
            "status": status,
        },
        {
            "type": "STRUCTURE",
            "label": "HH/HL",
            "timeframe": "1h",
            "higherHighCount": higher_high_count,
            "higherLowCount": higher_low_count,
        },
    ]
    if screener_reason:
        reasons.insert(0, f"Candidato de screener: {screener_reason}.")

    if status == "READY":
        voice = (
            f"{symbol} mantiene estructura alcista en una hora. En quince minutos rechazo la EMA21. "
            f"La entrada se activa sobre {_round_price(confirmation)}, stop {_round_price(stop)} "
            f"y objetivo principal {_round_price(primary)}. Riesgo beneficio {round(risk_reward or 0, 2)}."
        )
    elif status == "WAITING_CONFIRMATION":
        voice = (
            f"{symbol} tiene tendencia alcista, pero todavia no hay entrada confirmada. "
            f"Estoy esperando rechazo alcista y cierre sobre {_round_price(confirmation)}."
        )
    elif status == "LATE_ENTRY":
        voice = f"{symbol} esta alcista, pero el precio esta extendido de la EMA21. No persigo la entrada."
    elif status == "INVALIDATED":
        voice = f"{symbol} perdio la zona de invalidacion. Roxy no opera este setup."
    else:
        voice = f"{symbol} esta en observacion. La estructura aun no cumple todas las condiciones del pullback a EMA21."

    signal = OperationalStrategySignal(
        symbol=symbol,
        strategy="Uptrend Pullback to EMA21",
        setupType="UPTREND_PULLBACK_EMA21",
        direction="LONG",
        status=status,
        currentPrice=_round_price(current_price),
        entryZoneLow=_round_price(entry_low),
        entryZoneHigh=_round_price(entry_high),
        confirmationPrice=_round_price(confirmation),
        stopPrice=_round_price(stop),
        partialTarget=_round_price(partial),
        primaryTarget=_round_price(primary),
        secondaryTarget=_round_price(secondary),
        invalidationPrice=_round_price(stop),
        riskPerShare=_round_price(risk),
        potentialReward=_round_price(reward),
        riskReward=round(risk_reward, 2) if risk_reward is not None else None,
        confidence=confidence,
        timeframeEntry="15m",
        timeframeConfirmation="1h",
        detectedAt=now.isoformat(),
        expiresAt=(now + timedelta(minutes=45)).isoformat(),
        provider=provider,
        providerTimestamp=provider_timestamp,
        reasons=reasons,
        warnings=warnings,
        chartAnnotations=chart_annotations,
        metrics=metrics,
        voiceExplanation=voice,
        monitoring={
            "refreshSeconds": 15,
            "watch": [
                "15m close above confirmationPrice",
                "price remains above stopPrice",
                "1h EMA9 remains above EMA21",
                "relative volume stays healthy",
            ],
            "nextAction": "Operar solo si status es READY; si no, esperar confirmacion.",
        },
    )
    return signal.to_dict()
