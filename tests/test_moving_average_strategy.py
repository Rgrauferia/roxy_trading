import pandas as pd

from moving_average_strategy import add_moving_averages, analyze_moving_average_setup, scan_moving_average_strategy


def ohlcv_from_closes(closes):
    return pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=len(closes), freq="D"),
            "open": closes,
            "high": [value * 1.01 for value in closes],
            "low": [value * 0.99 for value in closes],
            "close": closes,
            "volume": [1000] * len(closes),
        }
    )


def test_add_moving_averages_creates_expected_columns():
    df = ohlcv_from_closes(range(1, 221))
    out = add_moving_averages(df)

    assert {"sma20", "sma40", "sma100", "sma200"}.issubset(out.columns)
    assert out["sma200"].iloc[-1] == sum(range(21, 221)) / 200


def test_analyze_moving_average_setup_buy_for_clean_uptrend():
    df = ohlcv_from_closes([100 + idx * 0.5 for idx in range(260)])
    result = analyze_moving_average_setup(df)

    assert result["signal"] == "BUY"
    assert result["setup"] == "TREND_CONTINUATION"
    assert result["score"] >= 70
    assert result["sma20"] > result["sma40"] > result["sma100"] > result["sma200"]
    assert result["stop"] < result["entry"]
    assert result["relative_volume"] == 1.0
    assert result["atr14"] > 0
    assert result["atr_pct"] > 0


def test_analyze_moving_average_setup_avoids_downtrend():
    df = ohlcv_from_closes([260 - idx * 0.5 for idx in range(260)])
    result = analyze_moving_average_setup(df)

    assert result["signal"] == "AVOID"
    assert result["setup"] == "DOWNTREND"
    assert result["score"] < 45


def test_analyze_moving_average_setup_requires_two_hundred_bars():
    df = ohlcv_from_closes(range(1, 120))
    result = analyze_moving_average_setup(df)

    assert result["signal"] == "INSUFFICIENT_DATA"
    assert result["setup"] == "INSUFFICIENT_DATA"


def test_scan_moving_average_strategy_sorts_results():
    uptrend = ohlcv_from_closes([100 + idx * 0.5 for idx in range(260)])
    downtrend = ohlcv_from_closes([260 - idx * 0.5 for idx in range(260)])

    def fetcher(symbol):
        return uptrend if symbol == "UP" else downtrend

    out = scan_moving_average_strategy(["DOWN", "UP"], fetcher, market="stock", timeframe="1d")

    assert list(out["symbol"]) == ["UP", "DOWN"]
    assert out.loc[0, "signal"] == "BUY"
    assert out.loc[1, "signal"] == "AVOID"
