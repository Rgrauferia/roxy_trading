import pandas as pd

import symbol_detail


def _five_minute_candles(rows: int = 24) -> pd.DataFrame:
    timestamps = pd.date_range("2026-07-17 13:30:00+00:00", periods=rows, freq="5min")
    return pd.DataFrame(
        {
            "ts": timestamps,
            "open": [100.0 + index for index in range(rows)],
            "high": [101.0 + index for index in range(rows)],
            "low": [99.0 + index for index in range(rows)],
            "close": [100.5 + index for index in range(rows)],
            "volume": [1000.0] * rows,
        }
    )


def test_twenty_minute_crypto_candles_are_derived_from_real_five_minute_rows(monkeypatch):
    source = _five_minute_candles()
    calls = []

    def fake_fetch(symbol, timeframe, limit):
        calls.append((symbol, timeframe, limit))
        return source

    import roxy_scanner

    monkeypatch.setattr(roxy_scanner, "fetch_crypto_ohlcv", fake_fetch)
    result, metadata = symbol_detail.fetch_symbol_history_with_source(
        "BTC/USD", market="crypto", timeframe="20m"
    )

    assert calls == [("BTC/USD", "5m", 1000)]
    assert metadata["derived_from"] == "5m"
    assert metadata["timeframe"] == "20m"
    assert not result.empty
    assert float(result["volume"].iloc[-1]) <= 4000.0


def test_thirty_minute_stock_candles_use_fifteen_minute_provider_rows(monkeypatch):
    source = _five_minute_candles(12)
    calls = []

    def fake_fetch(symbol, *, timeframe, include_extended_hours, env):
        calls.append((symbol, timeframe, include_extended_hours, env))
        return source, {"provider": "Alpaca", "fallback": False}

    monkeypatch.setattr(symbol_detail, "_fetch_stock_history_with_source", fake_fetch)
    result, metadata = symbol_detail.fetch_symbol_history_with_source(
        "AAPL", market="stock", timeframe="30m", env={"test": "1"}
    )

    assert calls == [("AAPL", "15m", True, {"test": "1"})]
    assert metadata["derived_from"] == "15m"
    assert metadata["timeframe"] == "30m"
    assert not result.empty
