import json
import sys

import pandas as pd

from tools import ma_scan
from tools.ma_scan import (
    apply_backtest_filter,
    build_crypto_history_cache,
    parse_csv_list,
    resample_ohlcv,
    sort_scan_results,
    stock_fetch_interval,
    stock_period_for_interval,
)


def test_apply_backtest_filter_degrades_noneligible_buy_to_watch():
    scan = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "AAPL",
                "signal": "BUY",
                "setup": "TREND_CONTINUATION",
                "score": 90,
                "reasons": ["Alineacion alcista"],
            }
        ]
    )
    eligibility = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "AAPL",
                "eligible": False,
                "profit_factor": 0.8,
                "eligibility_reasons": "profit_factor<1.2",
            }
        ]
    )

    out = apply_backtest_filter(scan, eligibility, require_eligible=True)

    assert out.loc[0, "raw_signal"] == "BUY"
    assert out.loc[0, "signal"] == "WATCH"
    assert bool(out.loc[0, "backtest_eligible"]) is False
    assert "Backtest filter: profit_factor<1.2" in out.loc[0, "reasons"]


def test_apply_backtest_filter_keeps_eligible_buy():
    scan = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "MSFT",
                "signal": "BUY",
                "setup": "TREND_CONTINUATION",
                "score": 88,
                "reasons": [],
            }
        ]
    )
    eligibility = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "MSFT",
                "eligible": True,
                "profit_factor": 2.0,
                "eligibility_reasons": "",
            }
        ]
    )

    out = apply_backtest_filter(scan, eligibility, require_eligible=True)

    assert out.loc[0, "raw_signal"] == "BUY"
    assert out.loc[0, "signal"] == "BUY"
    assert bool(out.loc[0, "backtest_eligible"]) is True


def test_sort_scan_results_prioritizes_eligible_buys():
    df = pd.DataFrame(
        [
            {"symbol": "WATCH_HIGH", "signal": "WATCH", "score": 100, "backtest_eligible": False},
            {"symbol": "BUY_LOW", "signal": "BUY", "score": 75, "backtest_eligible": True},
            {"symbol": "BUY_HIGH_FILTERED", "signal": "WATCH", "score": 95, "backtest_eligible": False},
        ]
    )

    out = sort_scan_results(df)

    assert list(out["symbol"]) == ["BUY_LOW", "WATCH_HIGH", "BUY_HIGH_FILTERED"]


def test_parse_csv_list_strips_empty_values():
    assert parse_csv_list("15m, 1h,,") == ["15m", "1h"]


def test_stock_period_for_interval_uses_intraday_default():
    assert stock_period_for_interval("15m", None, "60d") == "60d"
    assert stock_period_for_interval("1h", None, "60d") == "60d"
    assert stock_period_for_interval("2h", None, "60d") == "730d"
    assert stock_period_for_interval("4h", None, "60d") == "730d"
    assert stock_period_for_interval("1d", None, "60d") == "2y"
    assert stock_period_for_interval("15m", "30d", "60d") == "30d"


def test_stock_fetch_interval_maps_one_hour_for_yahoo():
    assert stock_fetch_interval("1h") == "60m"
    assert stock_fetch_interval("15m") == "15m"


def test_resample_ohlcv_for_derived_stock_interval():
    df = pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01 09:00", periods=4, freq="h"),
            "open": [10, 11, 12, 13],
            "high": [11, 12, 14, 15],
            "low": [9, 10, 11, 12],
            "close": [10.5, 11.5, 13.5, 14.5],
            "volume": [100, 200, 300, 400],
        }
    )

    out = resample_ohlcv(df, "2h")

    assert out.iloc[-1]["open"] == 12
    assert out.iloc[-1]["high"] == 15
    assert out.iloc[-1]["low"] == 11
    assert out.iloc[-1]["close"] == 14.5
    assert out.iloc[-1]["volume"] == 700


def test_main_writes_timing_json(tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "watchlist_stocks.txt").write_text("AAPL\n")
    (data_dir / "watchlist_crypto.txt").write_text("BTC/USD\n")
    timing_path = tmp_path / "alerts" / "timing.json"
    coverage_path = tmp_path / "alerts" / "coverage.json"

    def frame(market: str, symbol: str, tf: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "market": market,
                    "symbol": symbol,
                    "tf": tf,
                    "signal": "WATCH",
                    "score": 55,
                    "reasons": ["test"],
                }
            ]
        )

    monkeypatch.setattr(ma_scan, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(ma_scan, "DATA_DIR", data_dir)
    monkeypatch.setattr(ma_scan, "run_stock_scan", lambda symbols, interval, period, config, include_extended_hours=False: frame("stock", symbols[0], interval))
    exchange = object()
    monkeypatch.setattr("roxy_scanner.create_binanceus_exchange", lambda: exchange)
    monkeypatch.setattr(
        "roxy_scanner.binanceus_symbol_coverage",
        lambda symbols, exchange=None: {
            "contract_version": "roxy-binanceus-symbol-coverage/1.0.0",
            "status": "CONNECTED",
            "requested_count": len(symbols),
            "supported_count": len(symbols),
            "unsupported_count": 0,
            "exact_count": len(symbols),
            "quote_fallback_count": 0,
            "supported_symbols": symbols,
            "unsupported_symbols": [],
            "symbol_map": {symbol: symbol for symbol in symbols},
        },
    )
    monkeypatch.setattr(
        ma_scan,
        "run_crypto_scan",
        lambda symbols, timeframe, limit, config, **kwargs: frame("crypto", symbols[0], timeframe),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ma_scan.py",
            "--market",
            "both",
            "--stock-intervals",
            "15m",
            "--crypto-timeframes",
            "1h",
            "--timing-json",
            str(timing_path),
            "--crypto-coverage-json",
            str(coverage_path),
            "--save",
        ],
    )

    ma_scan.main()

    payload = json.loads(timing_path.read_text())
    assert payload["status"] == "SUCCESS"
    assert payload["market"] == "both"
    assert payload["total_rows"] == 2
    assert payload["saved_path"]
    assert [step["market"] for step in payload["steps"]] == ["stock", "crypto"]
    assert [step["timeframe"] for step in payload["steps"]] == ["15m", "1h"]
    assert all(step["duration_seconds"] >= 0 for step in payload["steps"])
    assert payload["crypto_symbol_coverage"]["supported_count"] == 1
    assert json.loads(coverage_path.read_text())["unsupported_count"] == 0


def test_run_crypto_scan_uses_provider_mapping_and_shared_exchange(monkeypatch):
    calls = []
    exchange = object()

    def fake_fetch(symbol, *, timeframe, limit, exchange=None, provider_symbol=None):
        calls.append((symbol, provider_symbol, timeframe, limit, exchange))
        return pd.DataFrame(
            {
                "ts": pd.date_range("2026-01-01", periods=220, freq="15min"),
                "open": range(220),
                "high": [value + 2 for value in range(220)],
                "low": [value - 1 for value in range(220)],
                "close": [value + 1 for value in range(220)],
                "volume": [1000] * 220,
            }
        )

    monkeypatch.setattr("roxy_scanner.fetch_crypto_ohlcv", fake_fetch)

    out = ma_scan.run_crypto_scan(
        ["WIF/USD"],
        "15m",
        200,
        ma_scan.MovingAverageConfig(),
        exchange=exchange,
        symbol_map={"WIF/USD": "WIF/USDT"},
    )

    assert calls == [("WIF/USD", "WIF/USDT", "15m", 200, exchange)]
    assert out.loc[0, "symbol"] == "WIF/USD"
    assert out.loc[0, "provider_symbol"] == "WIF/USDT"
    assert out.loc[0, "symbol_resolution"] == "QUOTE_FALLBACK"
    assert out.loc[0, "data_source"] == "ccxt:binanceus"


def test_crypto_history_cache_fetches_one_expanded_hourly_series_for_two_and_four_hours():
    calls = []
    exchange = object()

    def fake_fetch(symbol, *, timeframe, limit, exchange=None, provider_symbol=None):
        calls.append((symbol, provider_symbol, timeframe, limit, exchange))
        return pd.DataFrame(
            {
                "ts": pd.date_range("2026-01-01", periods=1000, freq="h"),
                "open": [100.0] * 1000,
                "high": [102.0] * 1000,
                "low": [99.0] * 1000,
                "close": [101.0] * 1000,
                "volume": [1000.0] * 1000,
            }
        )

    cache, meta = build_crypto_history_cache(
        ["BTC/USD", "WIF/USD"],
        ["15m", "1h", "2h", "4h"],
        500,
        exchange=exchange,
        symbol_map={"WIF/USD": "WIF/USDT"},
        fetcher=fake_fetch,
    )

    assert calls == [
        ("BTC/USD", "BTC/USD", "1h", 1000, exchange),
        ("WIF/USD", "WIF/USDT", "1h", 1000, exchange),
    ]
    assert len(cache[("BTC/USD", "2h")]) >= 500
    assert len(cache[("BTC/USD", "4h")]) >= 250
    assert meta["saved_request_count"] == 4
    assert meta["derived_timeframes"] == ["2h", "4h"]


def test_run_crypto_scan_uses_prefetched_history_without_provider_request(monkeypatch):
    monkeypatch.setattr(
        "roxy_scanner.fetch_crypto_ohlcv",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("provider should not be called")),
    )
    history = pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=240, freq="4h"),
            "open": [100.0 + value * 0.1 for value in range(240)],
            "high": [101.0 + value * 0.1 for value in range(240)],
            "low": [99.0 + value * 0.1 for value in range(240)],
            "close": [100.5 + value * 0.1 for value in range(240)],
            "volume": [1000.0] * 240,
        }
    )

    out = ma_scan.run_crypto_scan(
        ["BTC/USD"],
        "4h",
        500,
        ma_scan.MovingAverageConfig(),
        exchange=object(),
        history_by_symbol={"BTC/USD": history},
    )

    assert out.loc[0, "symbol"] == "BTC/USD"
    assert out.loc[0, "tf"] == "4h"
    assert out.loc[0, "signal"] != "ERROR"
