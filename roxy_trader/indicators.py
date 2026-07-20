from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import pandas as pd


INDICATOR_ENGINE_VERSION = "roxy-indicators/1.1.0"


@dataclass(frozen=True)
class IndicatorConfig:
    sma_windows: tuple[int, ...] = (20, 40, 50, 100, 200)
    ema_windows: tuple[int, ...] = (9, 21, 50, 200)
    rsi_period: int = 14
    atr_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bollinger_period: int = 20
    bollinger_stddev: float = 2.0
    volume_period: int = 20


def indicator_contract(config: IndicatorConfig | None = None) -> dict[str, object]:
    cfg = config or IndicatorConfig()
    return {
        "engine": INDICATOR_ENGINE_VERSION,
        "config": asdict(cfg),
        "formulas": {
            "sma": "arithmetic rolling mean; full window required",
            "ema": "exponential mean; adjust=False",
            "rsi": "Wilder smoothing (alpha=1/period); full warmup required",
            "atr": "Wilder smoothing of true range (alpha=1/period); full warmup required",
            "macd": "EMA(fast)-EMA(slow), signal EMA; adjust=False",
            "bollinger": "SMA +/- multiplier * population standard deviation (ddof=0)",
            "vwap": "cumulative typical-price volume weighted by explicit session or UTC date",
            "relative_volume": "volume / arithmetic volume SMA",
        },
    }


def _positive_windows(values: Iterable[int]) -> tuple[int, ...]:
    return tuple(dict.fromkeys(int(value) for value in values if int(value) > 0))


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)


def simple_moving_average(
    close: pd.Series,
    window: int,
    *,
    min_periods: int | None = None,
) -> pd.Series:
    """Return the canonical arithmetic moving average."""
    window = max(1, int(window))
    warmup = window if min_periods is None else max(1, min(window, int(min_periods)))
    result = _numeric(close).rolling(window, min_periods=warmup).mean()
    result.name = f"sma{window}"
    return result


def exponential_moving_average(close: pd.Series, window: int) -> pd.Series:
    """Return the canonical adjust=False exponential moving average."""
    window = max(1, int(window))
    result = _numeric(close).ewm(span=window, adjust=False).mean()
    result.name = f"ema{window}"
    return result


def bollinger_bands(
    close: pd.Series,
    period: int = 20,
    standard_deviations: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return canonical middle, upper and lower Bollinger bands (population stddev)."""
    period = max(1, int(period))
    values = _numeric(close)
    middle = simple_moving_average(values, period)
    deviation = values.rolling(period, min_periods=period).std(ddof=0)
    upper = middle + float(standard_deviations) * deviation
    lower = middle - float(standard_deviations) * deviation
    middle.name, upper.name, lower.name = "bb_mid", "bb_upper", "bb_lower"
    return middle, upper, lower


def true_range(df: pd.DataFrame) -> pd.Series:
    required = {"high", "low", "close"}
    if not required.issubset(df.columns):
        return pd.Series(index=df.index, dtype=float, name="true_range")
    high = _numeric(df["high"])
    low = _numeric(df["low"])
    close = _numeric(df["close"])
    previous_close = close.shift(1)
    result = pd.concat(
        [(high - low).abs(), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    result.name = "true_range"
    return result


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    period = max(1, int(period))
    values = _numeric(close)
    delta = values.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    average_gain = gains.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    average_loss = losses.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    relative_strength = average_gain / average_loss.mask(average_loss == 0)
    result = 100.0 - (100.0 / (1.0 + relative_strength))
    result = result.mask((average_loss == 0) & (average_gain > 0), 100.0)
    result = result.mask((average_loss == 0) & (average_gain == 0), 50.0)
    result.name = f"rsi{period}"
    return result


def wilder_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    period = max(1, int(period))
    result = true_range(df).ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    result.name = f"atr{period}"
    return result


def _session_groups(df: pd.DataFrame) -> pd.Series:
    if "session" in df.columns:
        return df["session"].astype(str)
    if "ts" in df.columns:
        timestamps = pd.to_datetime(df["ts"], errors="coerce", utc=True)
        return timestamps.dt.strftime("%Y-%m-%d").fillna("unknown")
    return pd.Series("all", index=df.index)


def session_vwap(df: pd.DataFrame) -> pd.Series:
    required = {"high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        return pd.Series(index=df.index, dtype=float, name="vwap")
    typical_price = (_numeric(df["high"]) + _numeric(df["low"]) + _numeric(df["close"])) / 3.0
    volume = _numeric(df["volume"]).fillna(0.0)
    groups = _session_groups(df)
    cumulative_value = (typical_price * volume).groupby(groups, sort=False).cumsum()
    cumulative_volume = volume.groupby(groups, sort=False).cumsum().replace(0, pd.NA)
    result = cumulative_value / cumulative_volume
    result.name = "vwap"
    return result


def add_indicators(df: pd.DataFrame, *, config: IndicatorConfig | None = None) -> pd.DataFrame:
    if "close" not in df.columns:
        raise ValueError("DataFrame must include a close column")
    cfg = config or IndicatorConfig()
    out = df.copy()
    close = _numeric(out["close"])
    out["close"] = close

    for window in _positive_windows(cfg.sma_windows):
        out[f"sma{window}"] = simple_moving_average(close, window)
    for window in _positive_windows(cfg.ema_windows):
        out[f"ema{window}"] = exponential_moving_average(close, window)

    out[f"rsi{cfg.rsi_period}"] = wilder_rsi(close, cfg.rsi_period)
    fast = exponential_moving_average(close, cfg.macd_fast)
    slow = exponential_moving_average(close, cfg.macd_slow)
    out["macd"] = fast - slow
    out["macd_signal"] = exponential_moving_average(out["macd"], cfg.macd_signal)
    out["macd_hist"] = out["macd"] - out["macd_signal"]

    out["bb_mid"], out["bb_upper"], out["bb_lower"] = bollinger_bands(
        close,
        cfg.bollinger_period,
        cfg.bollinger_stddev,
    )

    if {"high", "low", "close"}.issubset(out.columns):
        out[f"atr{cfg.atr_period}"] = wilder_atr(out, cfg.atr_period)
        out["atr_pct"] = out[f"atr{cfg.atr_period}"] / close.replace(0, pd.NA)
    if "volume" in out.columns:
        out["volume"] = _numeric(out["volume"])
        volume_period = max(1, int(cfg.volume_period))
        out[f"volume_sma{volume_period}"] = out["volume"].rolling(
            volume_period, min_periods=volume_period
        ).mean()
        out["relative_volume"] = out["volume"] / out[f"volume_sma{volume_period}"].replace(0, pd.NA)
        if {"high", "low"}.issubset(out.columns):
            out["vwap"] = session_vwap(out)

    out.attrs["indicator_engine"] = indicator_contract(cfg)
    return out
