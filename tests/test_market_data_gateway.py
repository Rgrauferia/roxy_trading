import pandas as pd

from roxy_trader.market_data import (
    MARKET_DATA_CONTRACT_VERSION,
    MarketDataGateway,
    normalize_candle_batch,
)


def candle_frame(price: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.date_range("2026-07-01", periods=3, freq="h", tz="UTC"),
            "open": [price, price + 1, price + 2],
            "high": [price + 2, price + 3, price + 4],
            "low": [price - 1, price, price + 1],
            "close": [price + 1, price + 2, price + 3],
            "volume": [1000, 1100, 1200],
        }
    )


def test_normalized_candle_contract_exposes_provenance_and_freshness_fields():
    batch = normalize_candle_batch(
        candle_frame(),
        symbol="aapl",
        market="stock",
        timeframe="1h",
        metadata={
            "provider": "Alpaca",
            "source": "alpaca_iex",
            "mode": "BROKER_DATA",
            "fallback": False,
        },
    )

    assert batch.available
    assert batch.metadata["contract_version"] == MARKET_DATA_CONTRACT_VERSION
    assert batch.metadata["symbol"] == "AAPL"
    assert batch.metadata["status"] == "OK"
    assert batch.metadata["row_count"] == 3
    assert batch.metadata["last_timestamp"]
    assert batch.metadata["latency_class"] == "provider_native"
    assert batch.metadata["is_delayed"] is False


def test_normalized_candle_contract_rejects_impossible_or_nonpositive_candles():
    frame = candle_frame()
    frame.loc[0, "high"] = frame.loc[0, "open"] - 1
    frame.loc[1, "close"] = 0

    batch = normalize_candle_batch(
        frame,
        symbol="BTC/USD",
        market="crypto",
        timeframe="1h",
        metadata={"provider": "BinanceUS", "source": "ccxt:binanceus", "mode": "EXCHANGE_API"},
    )

    assert batch.available
    assert len(batch.frame) == 1
    assert (batch.frame[["open", "high", "low", "close"]] > 0).all().all()


def test_gateway_falls_through_empty_provider_and_preserves_attempts():
    gateway = MarketDataGateway()
    gateway.register_history_provider(
        market="stock",
        provider_id="Alpaca",
        priority=10,
        fetcher=lambda _symbol, _timeframe, _limit: pd.DataFrame(),
        metadata={"mode": "BROKER_DATA"},
    )
    gateway.register_history_provider(
        market="stock",
        provider_id="Polygon",
        priority=20,
        fetcher=lambda _symbol, _timeframe, _limit: (
            candle_frame(200),
            {"source": "polygon_aggs", "mode": "PREMIUM_DATA"},
        ),
    )

    batch = gateway.fetch_history(symbol="MSFT", market="stock", timeframe="15m")

    assert batch.available
    assert batch.metadata["provider"] == "Polygon"
    assert [attempt["status"] for attempt in batch.metadata["attempts"]] == ["NO_DATA", "OK"]


def test_gateway_reports_explicit_no_data_after_provider_error():
    gateway = MarketDataGateway()

    def broken(_symbol, _timeframe, _limit):
        raise RuntimeError("provider down")

    gateway.register_history_provider(market="crypto", provider_id="BinanceUS", fetcher=broken)
    batch = gateway.fetch_history(symbol="BTC/USD", market="crypto", timeframe="1m")

    assert not batch.available
    assert batch.metadata["status"] == "NO_DATA"
    assert batch.metadata["provider"] == "unavailable"
    assert batch.metadata["attempts"][0]["status"] == "ERROR"
    assert "provider down" in batch.metadata["attempts"][0]["detail"]
