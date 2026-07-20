from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from roxy_trader.indicators import IndicatorConfig, add_indicators as add_central_indicators


MA_WINDOWS = (20, 40, 100, 200)


@dataclass(frozen=True)
class MovingAverageConfig:
    buy_score: int = 70
    watch_score: int = 45
    max_extension_pct: float = 12.0
    pullback_band_pct: float = 3.0
    stop_buffer_pct: float = 1.5


def add_moving_averages(df: pd.DataFrame, windows: Iterable[int] = MA_WINDOWS) -> pd.DataFrame:
    if "close" not in df.columns:
        raise ValueError("DataFrame must include a close column")

    requested_windows = tuple(dict.fromkeys(int(window) for window in windows))
    enriched = add_central_indicators(
        df,
        config=IndicatorConfig(sma_windows=requested_windows, ema_windows=()),
    )
    derived = [f"sma{window}" for window in requested_windows]
    if "volume" in df.columns:
        derived += ["volume_sma20", "relative_volume"]
    if {"high", "low", "close"}.issubset(df.columns):
        derived += ["atr14", "atr_pct"]
    out = enriched[[*df.columns, *[column for column in derived if column in enriched.columns and column not in df.columns]]]
    out.attrs.update(enriched.attrs)
    return out


def _pct_distance(value: float, reference: float) -> float | None:
    if reference == 0 or pd.isna(value) or pd.isna(reference):
        return None
    return float(((value / reference) - 1.0) * 100.0)


def _slope_pct(series: pd.Series, periods: int = 10) -> float | None:
    clean = series.dropna()
    if len(clean) <= periods:
        return None
    old = float(clean.iloc[-(periods + 1)])
    new = float(clean.iloc[-1])
    return _pct_distance(new, old)


def _crossed_above(fast: pd.Series, slow: pd.Series) -> bool:
    if len(fast) < 2 or len(slow) < 2:
        return False
    prev_fast, last_fast = fast.iloc[-2], fast.iloc[-1]
    prev_slow, last_slow = slow.iloc[-2], slow.iloc[-1]
    return bool(pd.notna(prev_fast) and pd.notna(prev_slow) and prev_fast <= prev_slow and last_fast > last_slow)


def _crossed_below(fast: pd.Series, slow: pd.Series) -> bool:
    if len(fast) < 2 or len(slow) < 2:
        return False
    prev_fast, last_fast = fast.iloc[-2], fast.iloc[-1]
    prev_slow, last_slow = slow.iloc[-2], slow.iloc[-1]
    return bool(pd.notna(prev_fast) and pd.notna(prev_slow) and prev_fast >= prev_slow and last_fast < last_slow)


def analyze_moving_average_setup(
    df: pd.DataFrame,
    *,
    config: MovingAverageConfig | None = None,
    precomputed_indicators: bool = False,
) -> dict:
    cfg = config or MovingAverageConfig()
    if precomputed_indicators:
        required = {"close", *(f"sma{window}" for window in MA_WINDOWS)}
        missing = required.difference(df.columns)
        if missing:
            raise ValueError(f"Missing precomputed columns: {', '.join(sorted(missing))}")
        data = df
    else:
        data = add_moving_averages(df)
    complete = data.dropna(subset=[f"sma{window}" for window in MA_WINDOWS])
    if complete.empty:
        return {
            "score": 0,
            "signal": "INSUFFICIENT_DATA",
            "setup": "INSUFFICIENT_DATA",
            "reasons": ["Se necesitan al menos 200 velas para SMA200"],
            "entry": None,
            "stop": None,
            "risk_anchor": None,
        }

    last = complete.iloc[-1]
    close = float(last["close"])
    sma20 = float(last["sma20"])
    sma40 = float(last["sma40"])
    sma100 = float(last["sma100"])
    sma200 = float(last["sma200"])

    score = 0
    reasons: list[str] = []

    bullish_stack = sma20 > sma40 > sma100 > sma200
    bearish_stack = sma20 < sma40 < sma100 < sma200
    close_above_all = close > max(sma20, sma40, sma100, sma200)
    close_below_200 = close < sma200

    if close > sma200:
        score += 15
        reasons.append("Precio por encima de SMA200")
    else:
        score -= 15
        reasons.append("Precio por debajo de SMA200")

    if sma100 > sma200:
        score += 15
        reasons.append("SMA100 por encima de SMA200")

    if sma40 > sma100:
        score += 10
        reasons.append("SMA40 por encima de SMA100")

    if sma20 > sma40:
        score += 10
        reasons.append("SMA20 por encima de SMA40")

    if bullish_stack:
        score += 25
        reasons.append("Alineacion alcista 20 > 40 > 100 > 200")
    elif bearish_stack:
        score -= 25
        reasons.append("Alineacion bajista 20 < 40 < 100 < 200")

    if close_above_all:
        score += 10
        reasons.append("Precio por encima de todas las medias")

    slope20 = _slope_pct(complete["sma20"], periods=10)
    slope40 = _slope_pct(complete["sma40"], periods=10)
    slope100 = _slope_pct(complete["sma100"], periods=10)
    relative_volume = float(last["relative_volume"]) if "relative_volume" in last.index and pd.notna(last["relative_volume"]) else None
    atr14 = float(last["atr14"]) if "atr14" in last.index and pd.notna(last["atr14"]) else None
    atr_pct = float(last["atr_pct"]) if "atr_pct" in last.index and pd.notna(last["atr_pct"]) else None

    if slope20 is not None and slope20 > 0:
        score += 5
        reasons.append("SMA20 subiendo")
    if slope40 is not None and slope40 > 0:
        score += 5
        reasons.append("SMA40 subiendo")
    if slope100 is not None and slope100 > 0:
        score += 5
        reasons.append("SMA100 subiendo")

    if _crossed_above(complete["sma20"], complete["sma40"]):
        score += 12
        reasons.append("Cruce alcista SMA20 sobre SMA40")
    if _crossed_above(complete["sma40"], complete["sma100"]):
        score += 12
        reasons.append("Cruce alcista SMA40 sobre SMA100")
    if _crossed_below(complete["sma20"], complete["sma40"]):
        score -= 12
        reasons.append("Cruce bajista SMA20 bajo SMA40")

    dist20 = _pct_distance(close, sma20)
    dist40 = _pct_distance(close, sma40)
    dist200 = _pct_distance(close, sma200)
    extension = _pct_distance(close, sma20)

    near_20_or_40 = any(dist is not None and abs(dist) <= cfg.pullback_band_pct for dist in (dist20, dist40))
    if bullish_stack and close > sma100 and near_20_or_40:
        score += 12
        reasons.append("Pullback cerca de SMA20/SMA40 en tendencia alcista")

    if extension is not None and extension > cfg.max_extension_pct:
        score -= 15
        reasons.append("Precio extendido sobre SMA20")

    if relative_volume is not None:
        if relative_volume >= 1.5:
            score += 8
            reasons.append("Volumen fuerte vs promedio 20")
        elif relative_volume >= 1.1:
            score += 4
            reasons.append("Volumen arriba del promedio")
        elif relative_volume < 0.7:
            score -= 5
            reasons.append("Volumen debil")

    score = int(max(0, min(100, score)))

    if close_below_200 or bearish_stack:
        setup = "DOWNTREND"
    elif bullish_stack and close_above_all:
        setup = "TREND_CONTINUATION"
    elif bullish_stack and near_20_or_40:
        setup = "PULLBACK"
    elif sma20 > sma40 and sma40 > sma100 and close > sma200:
        setup = "EARLY_UPTREND"
    else:
        setup = "NEUTRAL"

    if setup in {"TREND_CONTINUATION", "PULLBACK", "EARLY_UPTREND"} and score >= cfg.buy_score:
        signal = "BUY"
    elif score >= cfg.watch_score and not close_below_200:
        signal = "WATCH"
    else:
        signal = "AVOID"

    risk_anchor = min(sma40, sma100) if bullish_stack else sma200
    stop = risk_anchor * (1.0 - cfg.stop_buffer_pct / 100.0) if risk_anchor > 0 else None

    return {
        "score": score,
        "signal": signal,
        "setup": setup,
        "reasons": reasons,
        "entry": close,
        "stop": float(stop) if stop is not None else None,
        "risk_anchor": float(risk_anchor) if risk_anchor else None,
        "close": close,
        "sma20": sma20,
        "sma40": sma40,
        "sma100": sma100,
        "sma200": sma200,
        "dist_sma20_pct": dist20,
        "dist_sma40_pct": dist40,
        "dist_sma200_pct": dist200,
        "slope_sma20_pct": slope20,
        "slope_sma40_pct": slope40,
        "slope_sma100_pct": slope100,
        "volume": float(last["volume"]) if "volume" in last.index and pd.notna(last["volume"]) else None,
        "volume_sma20": float(last["volume_sma20"]) if "volume_sma20" in last.index and pd.notna(last["volume_sma20"]) else None,
        "relative_volume": relative_volume,
        "atr14": atr14,
        "atr_pct": atr_pct,
    }


def scan_moving_average_strategy(
    symbols: Iterable[str],
    fetcher,
    *,
    market: str,
    timeframe: str,
    config: MovingAverageConfig | None = None,
) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        try:
            df = fetcher(symbol)
            if df is None or df.empty:
                rows.append(
                    {
                        "market": market,
                        "symbol": symbol,
                        "tf": timeframe,
                        "score": 0,
                        "signal": "NO_DATA",
                        "setup": "NO_DATA",
                        "reasons": ["No se pudo obtener data"],
                    }
                )
                continue
            result = analyze_moving_average_setup(df, config=config)
            rows.append({"market": market, "symbol": symbol, "tf": timeframe, **result})
        except Exception as exc:
            rows.append(
                {
                    "market": market,
                    "symbol": symbol,
                    "tf": timeframe,
                    "score": 0,
                    "signal": "ERROR",
                    "setup": "ERROR",
                    "reasons": [str(exc)],
                }
            )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["score", "symbol"], ascending=[False, True]).reset_index(drop=True)
