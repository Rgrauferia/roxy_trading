from __future__ import annotations

from datetime import datetime, timezone
import math

import pandas as pd

from roxy_trader.operational_strategies import detect_visual_price_structures, evaluate_uptrend_pullback_to_ema21
from salto_strategies import strategy_family_for_opportunity


def _trend_candles(count: int, *, start: float = 100.0, step: float = 0.34) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    price = start
    for index in range(count):
        price += step
        if index % 12 == 0:
            price -= step * 3.0
        open_price = price - 0.16
        close = price + 0.08
        rows.append(
            {
                "open": open_price,
                "high": close + 0.34,
                "low": open_price - 0.28,
                "close": close,
                "volume": 100_000 + (index * 700),
            }
        )
    return rows


def _pullback_15m_ready(count: int = 70) -> list[dict[str, float]]:
    df = pd.DataFrame(_trend_candles(count, start=101.0, step=0.12))
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
    ema21 = float(df["ema21"].iloc[-1])
    prior_high = ema21 + 0.55
    df.loc[df.index[-2], ["open", "high", "low", "close", "volume"]] = [
        ema21 + 0.35,
        prior_high,
        ema21 - 0.08,
        ema21 + 0.18,
        180_000,
    ]
    df.loc[df.index[-1], ["open", "high", "low", "close", "volume"]] = [
        ema21 + 0.05,
        prior_high + 0.18,
        ema21 - 0.12,
        prior_high + 0.11,
        260_000,
    ]
    return df[["open", "high", "low", "close", "volume"]].to_dict("records")


def _symmetric_triangle_candles(count: int = 66) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    timestamps = pd.date_range("2026-06-01", periods=count, freq="15min", tz="UTC")
    for index, timestamp in enumerate(timestamps):
        upper = 110.0 - index * 0.075
        lower = 100.0 + index * 0.055
        midpoint = (upper + lower) / 2
        phase = index % 6
        if phase == 1:
            close, high, low = upper - 0.08, upper, upper - 0.32
        elif phase == 4:
            close, high, low = lower + 0.08, lower + 0.32, lower
        else:
            close, high, low = midpoint, midpoint + 0.18, midpoint - 0.18
        rows.append(
            {
                "ts": timestamp,
                "open": close - 0.04,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000 + index * 3,
            }
        )
    return rows


def _priced_candles(closes: list[float], volumes: list[float] | None = None) -> list[dict[str, object]]:
    timestamps = pd.date_range("2026-06-01", periods=len(closes), freq="15min", tz="UTC")
    volume_values = volumes or [1000.0] * len(closes)
    return [
        {
            "ts": timestamp,
            "open": close - 0.1,
            "high": close + 0.25,
            "low": close - 0.25,
            "close": close,
            "volume": volume,
        }
        for timestamp, close, volume in zip(timestamps, closes, volume_values)
    ]


def _bullish_divergence_candles() -> list[dict[str, object]]:
    closes = [100 + index * 0.03 for index in range(45)]
    closes += [101, 99, 96, 92, 88, 91, 95, 98, 100]
    closes += [100 - (12.6 * index / 11) for index in range(12)]
    closes += [88, 90, 92]
    return _priced_candles(closes)


def test_uptrend_pullback_ema21_returns_ready_plan_with_annotations():
    signal = evaluate_uptrend_pullback_to_ema21(
        symbol="AAPL",
        candles_1h=_trend_candles(90, start=95.0, step=0.42),
        candles_15m=_pullback_15m_ready(),
        provider="test-feed",
        provider_timestamp="2026-07-14T20:00:00Z",
        screener_reason="Finviz + Roxy uptrend candidate",
        relative_strength=1.2,
        now=datetime(2026, 7, 14, 20, 0, tzinfo=timezone.utc),
    )

    assert signal["symbol"] == "AAPL"
    assert signal["setupType"] == "UPTREND_PULLBACK_EMA21"
    assert signal["status"] in {"READY", "NEAR_ENTRY", "WAITING_CONFIRMATION"}
    assert signal["entryZoneLow"] < signal["entryZoneHigh"]
    assert signal["confirmationPrice"] > signal["entryZoneLow"]
    assert signal["stopPrice"] < signal["entryZoneLow"]
    assert signal["primaryTarget"] > signal["confirmationPrice"]
    assert signal["riskReward"] >= 1.0
    assert signal["confidence"] >= 60
    assert any(item["type"] == "ENTRY_ZONE" for item in signal["chartAnnotations"])
    assert any(item["type"] == "TREND_HEALTH" for item in signal["chartAnnotations"])
    assert "EMA21" in signal["voiceExplanation"]


def test_uptrend_pullback_ema21_refuses_insufficient_data():
    signal = evaluate_uptrend_pullback_to_ema21(
        symbol="MSFT",
        candles_1h=_trend_candles(10),
        candles_15m=_trend_candles(10),
    )

    assert signal["status"] == "DATA_INSUFFICIENT"
    assert signal["confidence"] == 0
    assert signal["entryZoneLow"] is None
    assert signal["warnings"]


def test_uptrend_pullback_strategy_family_is_separate():
    assert (
        strategy_family_for_opportunity({"symbol": "NVDA", "setup": "UPTREND_PULLBACK_EMA21"})
        == "Roxy: Uptrend Pullback EMA21"
    )
    assert (
        strategy_family_for_opportunity({"symbol": "AMD", "strategy": "Pullback EMA21"})
        == "Roxy: Uptrend Pullback EMA21"
    )


def test_visual_structure_detector_returns_triangle_geometry_from_pivots():
    signals = detect_visual_price_structures(
        symbol="TEST",
        candles=_symmetric_triangle_candles(),
        timeframe="15m",
        provider="fixture-provider",
    )
    triangle = next(item for item in signals if item["setupType"] == "SYMMETRIC_TRIANGLE")

    assert triangle["status"] == "AWAITING_BREAKOUT"
    assert triangle["provider"] == "fixture-provider"
    assert triangle["confidence"] >= 58
    lines = [item for item in triangle["chartAnnotations"] if item["type"] == "TREND_LINE"]
    assert {line["role"] for line in lines} == {"support", "resistance"}
    assert all(line["startTime"] < line["endTime"] for line in lines)
    assert lines[0]["startValue"] != lines[0]["endValue"]


def test_visual_structure_detector_requires_real_sample_and_never_fills_missing_data():
    assert detect_visual_price_structures(
        symbol="EMPTY",
        candles=_symmetric_triangle_candles(12),
        timeframe="15m",
    ) == []


def test_visual_detector_marks_volume_surge_and_overbought_without_calling_it_an_entry():
    closes = [100 + index * 0.5 for index in range(80)]
    volumes = [1000.0] * 79 + [3000.0]

    signals = detect_visual_price_structures(
        symbol="MOMO",
        candles=_priced_candles(closes, volumes),
        timeframe="15m",
        provider="fixture-provider",
    )
    by_type = {item["setupType"]: item for item in signals}

    assert by_type["VOLUME_SURGE"]["status"] == "DETECTED"
    assert "3.00x" in by_type["VOLUME_SURGE"]["reasons"][0]
    assert by_type["RSI_OVERBOUGHT"]["direction"] == "WAIT"
    assert by_type["RSI_OVERBOUGHT"]["status"] == "WATCHING"
    assert "no es una señal automática de venta" in by_type["RSI_OVERBOUGHT"]["warnings"][0]


def test_visual_detector_finds_latest_ema_cross_from_central_indicators():
    closes = [100 - index * 0.08 for index in range(71)] + [99.4]

    signals = detect_visual_price_structures(
        symbol="CROSS",
        candles=_priced_candles(closes),
        timeframe="1h",
    )
    cross = next(item for item in signals if item["setupType"] == "EMA_BULLISH_CROSS")

    assert cross["status"] == "WAITING_CONFIRMATION"
    assert cross["direction"] == "LONG"
    assert cross["chartAnnotations"][0]["type"] == "PRICE_MARKER"


def test_visual_detector_draws_confirmed_bullish_retest_level():
    closes = [100 + math.sin(index) * 0.2 for index in range(65)]
    closes += [102.0, 103.0, 102.0, 101.0, 100.45, 100.55]
    volumes = [1000.0] * len(closes)
    volumes[-1] = 1200.0

    signals = detect_visual_price_structures(
        symbol="RETEST",
        candles=_priced_candles(closes, volumes),
        timeframe="15m",
    )
    retest = next(item for item in signals if item["setupType"] == "BULLISH_RETEST")

    assert retest["status"] == "READY"
    assert retest["chartAnnotations"][0]["type"] == "RETEST_LEVEL"
    assert "conserva como soporte" in retest["reasons"][1]


def test_visual_detector_draws_price_leg_for_bullish_rsi_divergence():
    signals = detect_visual_price_structures(
        symbol="DIVERGE",
        candles=_bullish_divergence_candles(),
        timeframe="15m",
        provider="fixture-provider",
    )
    divergence = next(item for item in signals if item["setupType"] == "BULLISH_RSI_DIVERGENCE")

    assert divergence["status"] == "WAITING_CONFIRMATION"
    assert divergence["direction"] == "LONG"
    assert "RSI entre pivotes" in divergence["reasons"][1]
    annotation = divergence["chartAnnotations"][0]
    assert annotation["type"] == "TREND_LINE"
    assert annotation["role"] == "bullish_divergence"
    assert annotation["startTime"] < annotation["endTime"]
    assert annotation["startValue"] > annotation["endValue"]
