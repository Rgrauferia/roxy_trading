import pandas as pd

from symbol_detail import (
    alpaca_credentials_available,
    alpaca_env_credentials,
    alpaca_fallback_info,
    alpaca_placeholder_credential_keys,
    fetch_symbol_history_with_source,
    classify_strategy_playbook,
    detect_reference_strategies,
    latest_chart_strategy_events,
    latest_confluence_row,
    latest_symbol_rows,
    normalize_polygon_aggs_payload,
    polygon_credentials_available,
    polygon_api_key,
    prepare_symbol_chart_data,
    resample_ohlcv,
    resolve_symbol_query,
)


def _contract_frame(frame: pd.DataFrame) -> pd.DataFrame:
    expected = frame.copy()
    expected["ts"] = pd.to_datetime(expected["ts"], utc=True)
    return expected


def test_resolve_symbol_query_accepts_company_names_and_crypto_aliases():
    assert resolve_symbol_query("Apple") == "AAPL"
    assert resolve_symbol_query("aapl") == "AAPL"
    assert resolve_symbol_query("Bitcoin", market="crypto") == "BTC/USD"
    assert resolve_symbol_query("sol", market="crypto") == "SOL/USD"
    assert resolve_symbol_query("link", market="crypto") == "LINK/USD"


def test_prepare_symbol_chart_data_adds_sma_lines():
    df = pd.DataFrame(
        {
            "ts": pd.date_range("2024-01-01", periods=220, freq="D"),
            "open": range(220),
            "high": [value + 1 for value in range(220)],
            "low": [value - 1 for value in range(220)],
            "close": range(220),
            "volume": [1000] * 220,
        }
    )

    out = prepare_symbol_chart_data(df)

    assert {"close", "sma20", "sma40", "sma100", "sma200"}.issubset(out.columns)
    assert {"ema9", "bb_upper", "bb_lower", "range_high_60", "range_low_60"}.issubset(out.columns)
    assert {"rsi14", "macd", "macd_signal", "macd_hist"}.issubset(out.columns)
    assert pd.notna(out["sma200"].iloc[-1])
    assert pd.notna(out["ema9"].iloc[-1])
    assert pd.notna(out["rsi14"].iloc[-1])


def test_resample_ohlcv_builds_two_hour_candles():
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

    assert list(out.columns) == ["ts", "open", "high", "low", "close", "volume"]
    assert len(out) >= 2
    last = out.iloc[-1]
    assert last["open"] == 12
    assert last["high"] == 15
    assert last["low"] == 11
    assert last["close"] == 14.5
    assert last["volume"] == 700


def test_fetch_symbol_history_with_source_prefers_alpaca_when_available(monkeypatch):
    alpaca_df = pd.DataFrame(
        {
            "ts": pd.date_range("2026-06-01 09:30", periods=3, freq="15min"),
            "open": [10, 11, 12],
            "high": [11, 12, 13],
            "low": [9, 10, 11],
            "close": [10.5, 11.5, 12.5],
            "volume": [100, 120, 140],
        }
    )

    monkeypatch.setattr("symbol_detail.fetch_alpaca_stock_ohlcv", lambda *args, **kwargs: alpaca_df)

    out, source = fetch_symbol_history_with_source(
        "AAPL",
        market="stock",
        timeframe="15m",
        env={"ALPACA_API_KEY": "key", "ALPACA_API_SECRET": "secret"},
    )

    assert out.equals(_contract_frame(alpaca_df))
    assert source["provider"] == "Alpaca"
    assert source["source"] == "alpaca_iex"
    assert source["mode"] == "BROKER_DATA"
    assert source["fallback"] is False
    assert source["contract_version"] == "roxy-market-data/1.0.0"
    assert source["status"] == "OK"
    assert source["row_count"] == 3
    assert source["timeframe"] == "15m"
    assert source["latency_class"] == "provider_native"


def test_alpaca_env_credentials_accepts_secret_key_alias():
    env = {"ALPACA_API_KEY": "key", "ALPACA_SECRET_KEY": "secret"}

    credentials = alpaca_env_credentials(env)

    assert credentials["key_name"] == "ALPACA_API_KEY"
    assert credentials["secret_name"] == "ALPACA_SECRET_KEY"
    assert credentials["key"] == "key"
    assert credentials["secret"] == "secret"
    assert alpaca_credentials_available(env) is True


def test_polygon_api_key_accepts_token_alias_without_values():
    env = {"POLYGON_API_TOKEN": "polygon-secret"}

    key, key_name = polygon_api_key(env)

    assert key == "polygon-secret"
    assert key_name == "POLYGON_API_TOKEN"
    assert polygon_credentials_available(env) is True


def test_fetch_symbol_history_with_source_prefers_alpaca_with_secret_key_alias(monkeypatch):
    alpaca_df = pd.DataFrame(
        {
            "ts": pd.date_range("2026-06-01 09:30", periods=3, freq="15min"),
            "open": [10, 11, 12],
            "high": [11, 12, 13],
            "low": [9, 10, 11],
            "close": [10.5, 11.5, 12.5],
            "volume": [100, 120, 140],
        }
    )

    monkeypatch.setattr("symbol_detail.fetch_alpaca_stock_ohlcv", lambda *args, **kwargs: alpaca_df)

    out, source = fetch_symbol_history_with_source(
        "AAPL",
        market="stock",
        timeframe="15m",
        env={"ALPACA_API_KEY": "key", "ALPACA_SECRET_KEY": "secret"},
    )

    assert out.equals(_contract_frame(alpaca_df))
    assert source["provider"] == "Alpaca"
    assert source["mode"] == "BROKER_DATA"


def test_normalize_polygon_aggs_payload_maps_ohlcv_columns():
    out = normalize_polygon_aggs_payload(
        {
            "results": [
                {"t": 1_780_000_000_000, "o": "10", "h": "11", "l": "9", "c": "10.5", "v": "1000"},
                {"t": 1_780_003_600_000, "o": "10.5", "h": "12", "l": "10", "c": "11.5", "v": "1200"},
            ]
        }
    )

    assert list(out.columns) == ["ts", "open", "high", "low", "close", "volume"]
    assert len(out) == 2
    assert out.loc[0, "open"] == 10.0
    assert out.loc[1, "close"] == 11.5


def test_fetch_symbol_history_with_source_uses_polygon_after_alpaca_auth_failure(monkeypatch):
    polygon_df = pd.DataFrame(
        {
            "ts": pd.date_range("2026-06-01 09:30", periods=3, freq="h"),
            "open": [30, 31, 32],
            "high": [31, 32, 33],
            "low": [29, 30, 31],
            "close": [30.5, 31.5, 32.5],
            "volume": [300, 320, 340],
        }
    )

    def raise_auth(*args, **kwargs):
        raise RuntimeError("401 unauthorized invalid API key")

    monkeypatch.setattr("symbol_detail.fetch_alpaca_stock_ohlcv", raise_auth)
    monkeypatch.setattr("symbol_detail.fetch_polygon_stock_ohlcv", lambda *args, **kwargs: polygon_df)

    out, source = fetch_symbol_history_with_source(
        "AAPL",
        market="stock",
        timeframe="1h",
        env={"ALPACA_API_KEY": "key", "ALPACA_API_SECRET": "secret", "POLYGON_API_KEY": "polygon-key-value"},
    )

    assert out.equals(_contract_frame(polygon_df))
    assert source["provider"] == "Polygon"
    assert source["source"] == "polygon_aggs"
    assert source["mode"] == "PREMIUM_DATA"
    assert source["fallback"] is False
    assert source["upstream_fallback_reason"] == "alpaca_auth"
    assert "polygon-key-value" not in str(source)


def test_fetch_symbol_history_with_source_falls_back_to_yfinance_when_alpaca_empty(monkeypatch):
    fallback_df = pd.DataFrame(
        {
            "ts": pd.date_range("2026-06-01", periods=2, freq="h"),
            "open": [20, 21],
            "high": [21, 22],
            "low": [19, 20],
            "close": [20.5, 21.5],
            "volume": [200, 220],
        }
    )

    monkeypatch.setattr("symbol_detail.fetch_alpaca_stock_ohlcv", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr("roxy_scanner.fetch_stock_ohlcv", lambda *args, **kwargs: fallback_df)

    out, source = fetch_symbol_history_with_source(
        "AAPL",
        market="stock",
        timeframe="1h",
        env={"ALPACA_API_KEY": "key", "ALPACA_API_SECRET": "secret"},
    )

    assert out.equals(_contract_frame(fallback_df))
    assert source["provider"] == "yfinance"
    assert source["mode"] == "FALLBACK"
    assert source["fallback"] is True
    assert source["is_delayed"] is True
    assert source["latency_class"] == "public_fallback"
    assert source["fallback_reason"] == "alpaca_empty"
    assert "sin velas" in source["fallback_detail"]


def test_fetch_symbol_history_with_source_reports_alpaca_placeholder_credentials(monkeypatch):
    fallback_df = pd.DataFrame(
        {
            "ts": pd.date_range("2026-06-01", periods=2, freq="h"),
            "open": [20, 21],
            "high": [21, 22],
            "low": [19, 20],
            "close": [20.5, 21.5],
            "volume": [200, 220],
        }
    )

    monkeypatch.setattr(
        "symbol_detail.fetch_alpaca_stock_ohlcv",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("placeholder keys should not call Alpaca")),
    )
    monkeypatch.setattr("roxy_scanner.fetch_stock_ohlcv", lambda *args, **kwargs: fallback_df)

    env = {"ALPACA_API_KEY": "TU_KEY_PAPER", "ALPACA_API_SECRET": "TU_SECRET_PAPER"}
    out, source = fetch_symbol_history_with_source("AAPL", market="stock", timeframe="1h", env=env)

    assert out.equals(_contract_frame(fallback_df))
    assert alpaca_credentials_available(env) is False
    assert alpaca_placeholder_credential_keys(env) == ["ALPACA_API_KEY", "ALPACA_API_SECRET"]
    assert source["fallback_reason"] == "alpaca_placeholder_credentials"
    assert "placeholders" in source["fallback_detail"]
    assert "claves paper reales" in source["fallback_action"]


def test_fetch_symbol_history_with_source_classifies_alpaca_feed_permission(monkeypatch):
    fallback_df = pd.DataFrame(
        {
            "ts": pd.date_range("2026-06-01", periods=2, freq="h"),
            "open": [20, 21],
            "high": [21, 22],
            "low": [19, 20],
            "close": [20.5, 21.5],
            "volume": [200, 220],
        }
    )

    def raise_feed_error(*args, **kwargs):
        raise RuntimeError("403 subscription does not permit querying SIP feed")

    monkeypatch.setattr("symbol_detail.fetch_alpaca_stock_ohlcv", raise_feed_error)
    monkeypatch.setattr("roxy_scanner.fetch_stock_ohlcv", lambda *args, **kwargs: fallback_df)

    out, source = fetch_symbol_history_with_source(
        "AAPL",
        market="stock",
        timeframe="1h",
        env={"ALPACA_API_KEY": "key", "ALPACA_API_SECRET": "secret"},
    )

    assert out.equals(_contract_frame(fallback_df))
    assert source["fallback_reason"] == "alpaca_feed_permission"
    assert "feed/permisos" in source["fallback_detail"]
    assert "IEX/SIP" in source["fallback_action"]


def test_alpaca_fallback_info_classifies_auth_and_rate_limit():
    auth = alpaca_fallback_info("alpaca_error", exc=RuntimeError("401 unauthorized invalid API key"))
    rate = alpaca_fallback_info("alpaca_error", exc=RuntimeError("429 rate limit exceeded"))

    assert auth["fallback_reason"] == "alpaca_auth"
    assert "credenciales" in auth["fallback_action"]
    assert rate["fallback_reason"] == "alpaca_rate_limit"
    assert "reintentar" in rate["fallback_action"]


def test_latest_symbol_rows_and_confluence_are_case_insensitive():
    scan = pd.DataFrame(
        [
            {"symbol": "AAPL", "tf": "15m", "score": 90},
            {"symbol": "MSFT", "tf": "15m", "score": 80},
        ]
    )
    confluence = pd.DataFrame(
        [
            {"symbol": "aapl", "confluence_score": 70, "signal": "WATCH"},
            {"symbol": "AAPL", "confluence_score": 91, "signal": "BUY"},
        ]
    )

    assert len(latest_symbol_rows(scan, "aapl")) == 1
    assert latest_confluence_row(confluence, "AAPL")["signal"] == "BUY"


def test_classify_strategy_playbook_confirms_stock_options_only_with_confluence():
    setup = {
        "signal": "BUY",
        "setup": "PULLBACK",
        "score": 88,
        "entry": 101,
        "close": 101,
        "stop": 99,
        "sma20": 100,
        "sma40": 98,
        "sma100": 90,
        "sma200": 80,
        "dist_sma20_pct": 1.0,
        "dist_sma40_pct": 3.0,
    }
    confluence = {"signal": "BUY", "trade_decision": "TRADE_FOR_5PCT"}

    playbook = classify_strategy_playbook(setup, confluence=confluence, market="stock", timeframe="1h")

    assert playbook["regime"] == "Canal alcista"
    assert playbook["strategy"] == "Rebote en SMA20/SMA40"
    assert "Operable" in playbook["stock_plan"]
    assert "Opciones" in playbook["options_plan"]


def test_classify_strategy_playbook_blocks_buy_when_intraday_confluence_is_not_ready():
    setup = {
        "signal": "BUY",
        "setup": "TREND_CONTINUATION",
        "score": 91,
        "entry": 120,
        "close": 120,
        "stop": 100,
        "sma20": 115,
        "sma40": 110,
        "sma100": 90,
        "sma200": 80,
        "dist_sma20_pct": 4.3,
        "dist_sma40_pct": 9.1,
    }
    confluence = {"signal": "AVOID", "trade_decision": "NO_TRADE"}

    playbook = classify_strategy_playbook(setup, confluence=confluence, market="stock", timeframe="1d")

    assert "Watchlist fuerte" in playbook["stock_plan"]
    assert "intradia" in playbook["stock_plan"]
    assert "esperar" in playbook["options_plan"].lower()


def test_classify_strategy_playbook_marks_downtend_as_no_trade():
    setup = {
        "signal": "AVOID",
        "setup": "DOWNTREND",
        "score": 20,
        "entry": 70,
        "close": 70,
        "stop": 76,
        "sma20": 72,
        "sma40": 75,
        "sma100": 78,
        "sma200": 80,
        "dist_sma20_pct": -2.8,
        "dist_sma40_pct": -6.7,
    }

    playbook = classify_strategy_playbook(setup, market="stock", timeframe="1d")

    assert playbook["regime"] == "Bajista / debajo de SMA200"
    assert "No operar" in playbook["stock_plan"]


def test_detect_reference_strategies_marks_bullish_channel_active():
    df = pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01", periods=240, freq="D"),
            "open": [100 + value * 0.5 for value in range(240)],
            "high": [101 + value * 0.5 for value in range(240)],
            "low": [99 + value * 0.5 for value in range(240)],
            "close": [100 + value * 0.5 for value in range(240)],
            "volume": [1000] * 240,
        }
    )
    chart_df = prepare_symbol_chart_data(df)
    setup = {
        "signal": "BUY",
        "setup": "TREND_CONTINUATION",
        "sma20": chart_df["sma20"].iloc[-1],
        "sma40": chart_df["sma40"].iloc[-1],
        "sma100": chart_df["sma100"].iloc[-1],
        "sma200": chart_df["sma200"].iloc[-1],
    }

    rows = detect_reference_strategies(chart_df, setup)
    by_family = {row["family"]: row for row in rows}

    assert by_family["Canal alcista con tendencia alcista"]["status"] == "ACTIVE"
    assert by_family["Tendencia alcista de largo plazo"]["status"] == "ACTIVE"


def test_detect_reference_strategies_marks_lateral_channel_active():
    closes = [100 + ((value % 20) - 10) * 0.35 for value in range(240)]
    df = pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01", periods=240, freq="D"),
            "open": closes,
            "high": [value + 1 for value in closes],
            "low": [value - 1 for value in closes],
            "close": closes,
            "volume": [1000] * 240,
        }
    )
    chart_df = prepare_symbol_chart_data(df)

    rows = detect_reference_strategies(chart_df, {"signal": "WATCH", "setup": "NEUTRAL"})
    by_family = {row["family"]: row for row in rows}

    assert by_family["Canal lateral"]["status"] == "ACTIVE"


def test_latest_chart_strategy_events_marks_bullish_stack_and_low_volume():
    df = pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01", periods=240, freq="D"),
            "open": [100 + value * 0.45 for value in range(240)],
            "high": [101 + value * 0.45 for value in range(240)],
            "low": [99 + value * 0.45 for value in range(240)],
            "close": [100 + value * 0.45 for value in range(240)],
            "volume": [1000] * 239 + [400],
        }
    )
    chart_df = prepare_symbol_chart_data(df)

    events = latest_chart_strategy_events(chart_df, {"setup": "TREND_CONTINUATION"})
    by_event = {row["event"]: row for row in events}

    assert by_event["MA_STACK_BULL"]["status"] == "ACTIVE"
    assert by_event["LOW_VOLUME"]["status"] == "BLOCKED"
