from pathlib import Path

import pandas as pd
import pytest

from moving_average_strategy import add_moving_averages
from roxy_scanner import add_indicators as add_scanner_indicators
from roxy_trader.indicators import (
    INDICATOR_ENGINE_VERSION,
    IndicatorConfig,
    add_indicators,
    exponential_moving_average,
    indicator_contract,
    session_vwap,
    simple_moving_average,
    true_range,
    wilder_atr,
    wilder_rsi,
)
from symbol_detail import prepare_symbol_chart_data
from tools.features import compute_technical_indicators


def sample_ohlcv(count: int = 240) -> pd.DataFrame:
    close = pd.Series([100.0 + index for index in range(count)])
    return pd.DataFrame(
        {
            "ts": pd.date_range("2026-07-01", periods=count, freq="15min", tz="UTC"),
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": [1000.0 + index for index in range(count)],
        }
    )


def test_indicator_contract_is_versioned_and_documents_formulas():
    contract = indicator_contract()

    assert contract["engine"] == INDICATOR_ENGINE_VERSION
    assert "Wilder" in contract["formulas"]["rsi"]
    assert "ddof=0" in contract["formulas"]["bollinger"]
    assert contract["config"]["macd_fast"] == 12


def test_wilder_rsi_handles_rising_and_flat_series_after_warmup():
    rising = wilder_rsi(pd.Series(range(40), dtype=float), 14)
    flat = wilder_rsi(pd.Series([10.0] * 40), 14)

    assert rising.iloc[-1] == pytest.approx(100.0)
    assert flat.iloc[-1] == pytest.approx(50.0)
    assert rising.iloc[:14].isna().all()


def test_true_range_and_wilder_atr_include_previous_close_gap():
    frame = pd.DataFrame(
        {
            "high": [11.0, 16.0, 17.0, 18.0],
            "low": [9.0, 14.0, 15.0, 16.0],
            "close": [10.0, 15.0, 16.0, 17.0],
        }
    )

    ranges = true_range(frame)
    atr = wilder_atr(frame, 2)

    assert ranges.tolist() == pytest.approx([2.0, 6.0, 2.0, 2.0])
    assert atr.iloc[-1] == pytest.approx(2.5)


def test_bollinger_and_vwap_are_deterministic():
    frame = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2026-07-01T10:00:00Z", "2026-07-01T10:15:00Z"]),
            "high": [11.0, 13.0],
            "low": [9.0, 11.0],
            "close": [10.0, 12.0],
            "volume": [100.0, 300.0],
        }
    )
    vwap = session_vwap(frame)
    constant = add_indicators(
        pd.DataFrame({"close": [5.0] * 25}),
        config=IndicatorConfig(sma_windows=(20,), ema_windows=()),
    )

    assert vwap.iloc[0] == pytest.approx(10.0)
    assert vwap.iloc[1] == pytest.approx(11.5)
    assert constant["bb_mid"].iloc[-1] == pytest.approx(5.0)
    assert constant["bb_upper"].iloc[-1] == pytest.approx(5.0)
    assert constant["bb_lower"].iloc[-1] == pytest.approx(5.0)


def test_public_moving_average_helpers_are_the_canonical_series_api():
    close = pd.Series([1.0, 2.0, 3.0, 4.0])

    sma = simple_moving_average(close, 3)
    ema = exponential_moving_average(close, 3)

    assert sma.iloc[:2].isna().all()
    assert sma.iloc[-1] == pytest.approx(3.0)
    assert ema.tolist() == pytest.approx(close.ewm(span=3, adjust=False).mean().tolist())
    assert sma.name == "sma3"
    assert ema.name == "ema3"


def test_main_consumers_share_central_indicator_values_and_version():
    frame = sample_ohlcv()
    central = add_indicators(frame)
    moving = add_moving_averages(frame)
    chart = prepare_symbol_chart_data(frame)
    scanner = add_scanner_indicators(frame)

    assert moving.attrs["indicator_engine"]["engine"] == INDICATOR_ENGINE_VERSION
    assert chart["rsi14"].iloc[-1] == pytest.approx(central["rsi14"].iloc[-1])
    assert chart["atr14"].iloc[-1] == pytest.approx(central["atr14"].iloc[-1])
    assert scanner["rsi"].iloc[-1] == pytest.approx(central["rsi14"].iloc[-1])
    assert scanner["atr"].iloc[-1] == pytest.approx(central["atr14"].iloc[-1])
    assert moving["sma200"].iloc[-1] == pytest.approx(central["sma200"].iloc[-1])


def test_feature_store_aliases_match_central_wilder_and_average_values():
    frame = sample_ohlcv(100)
    features = compute_technical_indicators(frame)
    central = add_indicators(
        frame,
        config=IndicatorConfig(sma_windows=(3, 10, 30), ema_windows=(3, 10, 30)),
    )

    assert features.attrs["indicator_engine"]["engine"] == INDICATOR_ENGINE_VERSION
    assert features["sma_10"].iloc[-1] == pytest.approx(central["sma10"].iloc[-1])
    assert features["ema_10"].iloc[-1] == pytest.approx(central["ema10"].iloc[-1])
    assert features["rsi_14"].iloc[-1] == pytest.approx(central["rsi14"].iloc[-1])
    assert features["atr_14"].iloc[-1] == pytest.approx(central["atr14"].iloc[-1])


def test_operational_consumers_do_not_reintroduce_local_ema_rsi_atr_or_bollinger_formulas():
    root = Path(__file__).resolve().parents[1]
    sources = {
        name: (root / name).read_text(encoding="utf-8")
        for name in (
            "dashboard.py",
            "roxy_alpaca_bot.py",
            "tools/features.py",
            "tools/modeling.py",
            "streamlit_app.py",
        )
    }

    assert all(".ewm(" not in source for source in sources.values())
    forbidden_fragments = (
        "avg_gain = gain.rolling",
        "roll_up = up.rolling",
        "tr.rolling(period).mean",
        "close.rolling(20).mean",
        "closes.rolling(200",
    )
    assert all(fragment not in source for source in sources.values() for fragment in forbidden_fragments)
    assert "add_central_indicators" in sources["dashboard.py"]
    assert "session_vwap" in sources["roxy_alpaca_bot.py"]
    assert "add_central_indicators" in sources["streamlit_app.py"]


def test_chart_contract_now_exposes_required_professional_indicators():
    chart = prepare_symbol_chart_data(sample_ohlcv())

    assert {
        "ema9",
        "ema21",
        "ema50",
        "ema200",
        "sma20",
        "sma200",
        "vwap",
        "rsi14",
        "macd",
        "macd_signal",
        "macd_hist",
        "bb_upper",
        "bb_lower",
        "atr14",
        "relative_volume",
    }.issubset(chart.columns)
