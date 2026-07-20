from __future__ import annotations

import pandas as pd
import pytest

import roxy_scanner
from roxy_scanner import binanceus_symbol_coverage, fetch_crypto_ohlcv, risk_reward


def test_risk_reward_normal():
    # entry=10, stop=8, tp1=12 -> risk=2 reward=2 -> rr=1.0
    assert risk_reward(10, 8, 12) == pytest.approx(1.0)


def test_risk_reward_none_inputs():
    assert risk_reward(None, 8, 12) is None
    assert risk_reward(10, None, 12) is None
    assert risk_reward(10, 8, None) is None


def test_risk_reward_nonpositive_risk():
    # stop above entry -> invalid risk
    assert risk_reward(10, 12, 12) is None


class FakeBinanceUS:
    def __init__(self, markets=None, error: Exception | None = None):
        self.markets = markets or {}
        self.error = error
        self.fetch_calls = []

    def load_markets(self):
        if self.error:
            raise self.error
        return self.markets

    def fetch_ohlcv(self, symbol, *, timeframe, limit):
        self.fetch_calls.append((symbol, timeframe, limit))
        return [[1_700_000_000_000, 1, 2, 0.5, 1.5, 100]]


def test_binanceus_symbol_coverage_resolves_exact_fallback_and_unsupported():
    exchange = FakeBinanceUS({"BTC/USD": {}, "WIF/USDT": {}})

    coverage = binanceus_symbol_coverage(
        ["btc/usd", "WIF/USD", "MISSING/USD", "BTC/USD"],
        exchange=exchange,
    )

    assert coverage["status"] == "CONNECTED"
    assert coverage["requested_count"] == 3
    assert coverage["supported_count"] == 2
    assert coverage["unsupported_count"] == 1
    assert coverage["exact_count"] == 1
    assert coverage["quote_fallback_count"] == 1
    assert coverage["symbol_map"] == {"BTC/USD": "BTC/USD", "WIF/USD": "WIF/USDT"}
    assert coverage["unsupported_symbols"] == ["MISSING/USD"]


def test_binanceus_symbol_coverage_fails_open_when_catalog_is_unavailable():
    coverage = binanceus_symbol_coverage(["BTC/USD"], exchange=FakeBinanceUS(error=TimeoutError()))

    assert coverage["status"] == "PROVIDER_UNAVAILABLE"
    assert coverage["supported_symbols"] == ["BTC/USD"]
    assert coverage["symbol_map"] == {"BTC/USD": "BTC/USD"}
    assert coverage["error"] == "TimeoutError"


def test_fetch_crypto_ohlcv_reuses_exchange_and_provider_symbol(monkeypatch):
    exchange = FakeBinanceUS()
    monkeypatch.setattr(
        roxy_scanner,
        "create_binanceus_exchange",
        lambda: pytest.fail("No debe crear otro exchange cuando recibe uno"),
    )

    out = fetch_crypto_ohlcv(
        "WIF/USD",
        "15m",
        limit=200,
        exchange=exchange,
        provider_symbol="WIF/USDT",
    )

    assert exchange.fetch_calls == [("WIF/USDT", "15m", 200)]
    assert list(out.columns) == ["ts", "open", "high", "low", "close", "volume"]
    assert pd.api.types.is_datetime64_any_dtype(out["ts"])
