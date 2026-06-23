from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd

import living_market


def test_tradingview_chart_url_normalizes_stocks_and_crypto():
    assert living_market.tradingview_chart_url("AAPL", "stock") == "https://www.tradingview.com/chart/?symbol=AAPL"
    assert living_market.tradingview_chart_url("BTC/USD", "crypto") == "https://www.tradingview.com/chart/?symbol=BTCUSD"
    assert living_market.tradingview_chart_url("WMT<script>", "stock") == "https://www.tradingview.com/chart/?symbol=WMTSCRIPT"


def _price_frame(rows: int = 80, *, start: float = 100.0, breakout: bool = True) -> pd.DataFrame:
    ts = pd.date_range("2026-06-01", periods=rows, freq="h", tz="UTC")
    closes = [start + idx * 0.35 for idx in range(rows)]
    if breakout:
        closes[-1] = max(closes[:-1]) + 5.0
    volumes = [100_000 + idx * 300 for idx in range(rows)]
    volumes[-1] = 320_000
    return pd.DataFrame(
        {
            "ts": ts,
            "open": [value - 0.2 for value in closes],
            "high": [value + 0.8 for value in closes],
            "low": [value - 0.8 for value in closes],
            "close": closes,
            "volume": volumes,
        }
    )


def test_build_market_opportunity_explains_signal_with_real_indicators():
    news = {"title": "SpaceX SPCX expands after IPO debut", "source": "rss"}
    opportunity = living_market.build_market_opportunity(
        "SPCX",
        "stock",
        _price_frame(),
        {"label": "yfinance fallback", "mode": "FALLBACK", "detail": "Velas reales"},
        related_news=news,
        now=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )

    assert opportunity is not None
    assert opportunity["symbol"] == "SPCX"
    assert opportunity["paper_only"] is True
    assert opportunity["price"] > 0
    assert opportunity["entry"] == opportunity["price"]
    assert opportunity["stop_loss"] < opportunity["entry"] < opportunity["take_profit"]
    assert opportunity["confidence"] >= 40
    assert "Breakout" in opportunity["reason"]
    assert opportunity["indicators"]["rsi14"] is not None
    assert opportunity["related_news"]["title"].startswith("SpaceX")
    assert opportunity["tradingview_url"] == "https://www.tradingview.com/chart/?symbol=SPCX"


def test_living_market_snapshot_uses_real_rows_and_surfaces_failures(monkeypatch):
    frame = _price_frame()

    def fake_news(limit=12):
        return (
            [
                {
                    "title": "SpaceX SPCX begins trading after IPO",
                    "summary": "",
                    "source": "rss",
                    "tickers": ["SPCX"],
                    "impact": "alto",
                    "new_ticker_signal": True,
                }
            ],
            [living_market.source_row("news:rss", "OK", "1 noticia")],
        )

    def fake_ipo(now=None):
        return [], living_market.source_row("nasdaq_ipo_calendar", "WARN", "0 filas IPO")

    def fake_history(symbol, market):
        if symbol == "BTC/USD":
            raise RuntimeError("exchange timeout")
        return frame, {"label": "yfinance fallback", "mode": "FALLBACK", "detail": "Velas reales"}

    monkeypatch.setattr(living_market, "fetch_market_news", fake_news)
    monkeypatch.setattr(living_market, "fetch_nasdaq_ipo_calendar", fake_ipo)
    monkeypatch.setattr(living_market, "fetch_asset_history", fake_history)

    snapshot = living_market.build_living_market_snapshot(
        stock_symbols=("SPCX",),
        crypto_symbols=("BTC/USD",),
        now=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )

    assert snapshot["data_mode"] == "REAL"
    assert snapshot["diagnostics"]["using_demo_data"] is False
    assert snapshot["opportunities"][0]["symbol"] == "SPCX"
    assert snapshot["opportunities"][0]["tradingview_url"].endswith("symbol=SPCX")
    assert snapshot["opportunities"][0]["related_news"]["title"].startswith("SpaceX")
    assert any(item["status"] == "FAIL" and "BTC/USD" in item["name"] for item in snapshot["sources"])
    assert any(item["symbol"] == "SPCX" and item["tradingview_url"].endswith("symbol=SPCX") for item in snapshot["new_tickers"])
    assert "exchange timeout" in " ".join(snapshot["diagnostics"]["data_errors"])


def test_signal_state_blocks_public_stock_fallback_from_active_alerts(monkeypatch):
    frame = _price_frame()
    monkeypatch.setattr(living_market, "fetch_market_news", lambda limit=12: ([], []))
    monkeypatch.setattr(
        living_market,
        "fetch_nasdaq_ipo_calendar",
        lambda now=None: ([], living_market.source_row("nasdaq_ipo_calendar", "WARN", "0 filas IPO")),
    )
    monkeypatch.setattr(
        living_market,
        "fetch_asset_history",
        lambda symbol, market: (
            frame,
            {
                "label": "yfinance",
                "mode": "PUBLIC_MARKET_DATA",
                "detail": "Velas publicas.",
            },
        ),
    )

    snapshot = living_market.build_living_market_snapshot(
        stock_symbols=("AAPL",),
        crypto_symbols=(),
        now=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )

    assert snapshot["opportunities"]
    assert snapshot["opportunities"][0]["signal_state"] == "STALE_BLOCKED"
    assert snapshot["opportunities"][0]["alert_ready"] is False
    assert snapshot["active_alerts"] == 0


def test_signal_state_allows_confirmed_exchange_opportunity():
    opportunity = living_market.build_market_opportunity(
        "BTC/USD",
        "crypto",
        _price_frame(),
        {"label": "BinanceUS API", "mode": "EXCHANGE_API", "detail": "exchange"},
        now=datetime(2026, 6, 4, 7, 0, 0, tzinfo=timezone.utc),
    )
    opportunity["confidence"] = 75
    opportunity["data_age_seconds"] = 30

    state = living_market.classify_signal_state(opportunity)

    assert state["signal_state"] == "LIVE_READY"
    assert state["alert_ready"] is True


def test_living_market_snapshot_never_masks_total_data_failure_as_demo(monkeypatch):
    monkeypatch.setattr(living_market, "fetch_market_news", lambda limit=12: ([], []))
    monkeypatch.setattr(
        living_market,
        "fetch_nasdaq_ipo_calendar",
        lambda now=None: ([], living_market.source_row("nasdaq_ipo_calendar", "FAIL", "blocked")),
    )
    monkeypatch.setattr(
        living_market,
        "fetch_asset_history",
        lambda symbol, market: (_ for _ in ()).throw(RuntimeError("provider offline")),
    )

    snapshot = living_market.build_living_market_snapshot(
        stock_symbols=("AAPL",),
        crypto_symbols=(),
        now=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )

    assert snapshot["data_mode"] == "NO_DATA"
    assert snapshot["opportunities"] == []
    assert snapshot["diagnostics"]["using_demo_data"] is False
    assert snapshot["diagnostics"]["failing_source_count"] >= 1
    assert "provider offline" in " ".join(snapshot["diagnostics"]["data_errors"])


def test_live_price_snapshot_reads_crypto_ticker_with_age(monkeypatch):
    class FakeExchange:
        def fetch_ticker(self, symbol):
            return {"last": 125.5, "timestamp": int(datetime(2026, 6, 15, 11, 59, 58, tzinfo=timezone.utc).timestamp() * 1000)}

    fake_ccxt = SimpleNamespace(binanceus=lambda config: FakeExchange())
    monkeypatch.setitem(__import__("sys").modules, "ccxt", fake_ccxt)

    snapshot = living_market.build_live_price_snapshot(
        "SOL/USD",
        "crypto",
        now=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert snapshot["price"] == 125.5
    assert snapshot["freshness"] == "LIVE"
    assert snapshot["age_seconds"] == 2
    assert snapshot["source"] == "BinanceUS ticker"
    assert snapshot["provider"] == "BinanceUS"
    assert snapshot["market_open"] is True


def test_live_price_snapshot_reports_fail_without_fake_price(monkeypatch):
    class FailingExchange:
        def fetch_ticker(self, symbol):
            raise RuntimeError("ticker offline")

    fake_ccxt = SimpleNamespace(binanceus=lambda config: FailingExchange())
    monkeypatch.setitem(__import__("sys").modules, "ccxt", fake_ccxt)

    snapshot = living_market.build_live_price_snapshot(
        "BTC/USD",
        "crypto",
        now=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert snapshot["price"] is None
    assert snapshot["freshness"] == "FAIL"
    assert "ticker offline" in snapshot["error"]
    assert "No usar para trading" in snapshot["latency_note"]


def test_live_price_snapshot_prefers_alpaca_for_stocks(monkeypatch):
    monkeypatch.setattr(
        living_market,
        "fetch_alpaca_latest_trade",
        lambda symbol: {
            "ok": True,
            "price": 214.25,
            "price_time": datetime(2026, 6, 15, 11, 59, 55, tzinfo=timezone.utc),
            "source": "Alpaca IEX",
            "source_mode": "BROKER_DATA",
            "detail": "Latest trade de Alpaca.",
        },
    )
    monkeypatch.setattr(
        living_market,
        "fetch_yfinance_live_price",
        lambda symbol: (_ for _ in ()).throw(AssertionError("yfinance should not be called")),
    )

    snapshot = living_market.build_live_price_snapshot(
        "AAPL",
        "stock",
        now=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert snapshot["price"] == 214.25
    assert snapshot["source"] == "Alpaca IEX"
    assert snapshot["source_mode"] == "BROKER_DATA"
    assert snapshot["freshness"] == "LIVE"
    assert snapshot["provider"] == "Alpaca"
    assert snapshot["market_open"] is True
    assert snapshot["provider_issue"] == ""


def test_live_price_snapshot_keeps_alpaca_issue_when_falling_back_to_yfinance(monkeypatch):
    monkeypatch.setattr(
        living_market,
        "fetch_alpaca_latest_trade",
        lambda symbol: {
            "ok": False,
            "configured": True,
            "reason": "alpaca_auth",
            "detail": "Alpaca rechazo credenciales.",
            "action": "Rotar credenciales.",
        },
    )
    monkeypatch.setattr(
        living_market,
        "fetch_yfinance_live_price",
        lambda symbol: {
            "price": 214.25,
            "price_time": datetime(2026, 6, 15, 11, 59, 0, tzinfo=timezone.utc),
        },
    )

    snapshot = living_market.build_live_price_snapshot(
        "AAPL",
        "stock",
        now=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert snapshot["price"] == 214.25
    assert snapshot["source"] == "yfinance public"
    assert snapshot["source_mode"] == "PUBLIC_MARKET_DATA"
    assert snapshot["provider"] == "yfinance"
    assert snapshot["market_open"] is True
    assert snapshot["provider_issue"] == "alpaca_auth"
    assert "Alpaca no confirmado" in snapshot["latency_note"]


def test_yfinance_live_price_prefers_quote_current_price_before_extended_candle(monkeypatch):
    class FakeTicker:
        info = {
            "currentPrice": 169.62,
            "regularMarketPrice": 169.62,
            "postMarketPrice": 169.45,
            "regularMarketTime": 1781553601,
            "postMarketTime": 1781567991,
        }
        fast_info = {"lastPrice": 169.62}

    def fake_download(*args, **kwargs):
        raise AssertionError("history candle should not be used when quote price is available")

    fake_yf = SimpleNamespace(Ticker=lambda symbol: FakeTicker(), download=fake_download)
    monkeypatch.setitem(__import__("sys").modules, "yfinance", fake_yf)

    price = living_market.fetch_yfinance_live_price("COIN")

    assert price["price"] == 169.62
    assert price["field"] == "currentPrice"
    assert price["regular_market_price"] == 169.62
    assert price["post_market_price"] == 169.45


def test_live_price_snapshot_uses_public_quote_for_stock_comparison_price(monkeypatch):
    monkeypatch.setattr(
        living_market,
        "fetch_alpaca_latest_trade",
        lambda symbol: {
            "ok": False,
            "configured": True,
            "reason": "alpaca_auth",
            "detail": "Alpaca rechazo credenciales.",
            "action": "Rotar credenciales.",
        },
    )
    monkeypatch.setattr(
        living_market,
        "fetch_yfinance_live_price",
        lambda symbol: {
            "price": 169.62,
            "price_time": datetime(2026, 6, 15, 20, 0, 1, tzinfo=timezone.utc),
            "field": "currentPrice",
            "label": "currentPrice",
            "regular_market_price": 169.62,
            "post_market_price": 169.45,
        },
    )

    snapshot = living_market.build_live_price_snapshot(
        "COIN",
        "stock",
        now=datetime(2026, 6, 16, 5, 59, 48, tzinfo=timezone.utc),
    )

    assert snapshot["price"] == 169.62
    assert snapshot["source"] == "yfinance currentPrice"
    assert snapshot["source_mode"] == "PUBLIC_MARKET_DATA"
    assert snapshot["regular_market_price"] == 169.62
    assert snapshot["post_market_price"] == 169.45
    assert "Comparacion sesiones" in snapshot["latency_note"]


def test_live_price_snapshot_preserves_alpaca_issue_when_public_fallback_fails(monkeypatch):
    monkeypatch.setattr(
        living_market,
        "fetch_alpaca_latest_trade",
        lambda symbol: {
            "ok": False,
            "configured": True,
            "reason": "alpaca_auth",
            "detail": "Alpaca rechazo credenciales.",
            "action": "Rotar credenciales.",
        },
    )
    monkeypatch.setattr(
        living_market,
        "fetch_yfinance_live_price",
        lambda symbol: (_ for _ in ()).throw(RuntimeError("sin velas publicas")),
    )

    snapshot = living_market.build_live_price_snapshot(
        "AAPL",
        "stock",
        now=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert snapshot["price"] is None
    assert snapshot["freshness"] == "FAIL"
    assert snapshot["provider_issue"] == "alpaca_auth"
    assert "sin velas publicas" in snapshot["error"]


def test_live_price_snapshot_names_closed_stock_session_when_no_tick(monkeypatch):
    monkeypatch.setattr(
        living_market,
        "fetch_alpaca_latest_trade",
        lambda symbol: {
            "ok": False,
            "configured": True,
            "reason": "alpaca_no_trade",
            "detail": "Sin trade.",
            "action": "Esperar mercado.",
        },
    )
    monkeypatch.setattr(
        living_market,
        "fetch_yfinance_live_price",
        lambda symbol: (_ for _ in ()).throw(RuntimeError("sin velas publicas")),
    )

    snapshot = living_market.build_live_price_snapshot(
        "AAPL",
        "stock",
        now=datetime(2026, 6, 15, 4, 30, 0, tzinfo=timezone.utc),
    )

    assert snapshot["price"] is None
    assert snapshot["freshness"] == "FAIL"
    assert snapshot["source"] == "mercado cerrado"
    assert snapshot["market_open"] is False
    assert "sin tick live de acciones" in snapshot["latency_note"]


def test_alpaca_market_data_diagnostic_reports_missing_credentials():
    diagnostic = living_market.build_alpaca_market_data_diagnostic(
        "AAPL",
        env={},
        now=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert diagnostic["status"] == "FAIL"
    assert diagnostic["error_category"] == "NOT_CONFIGURED"
    assert diagnostic["safe_for_signals"] is False
    assert "ALPACA_API_KEY" in diagnostic["missing_keys"]
    assert diagnostic["live_orders_allowed"] is False


def test_alpaca_market_data_diagnostic_reports_placeholder_credentials(monkeypatch):
    monkeypatch.setattr(
        living_market,
        "fetch_alpaca_latest_trade",
        lambda symbol, env=None: (_ for _ in ()).throw(AssertionError("placeholder keys should not probe Alpaca")),
    )

    diagnostic = living_market.build_alpaca_market_data_diagnostic(
        "AAPL",
        env={
            "ALPACA_API_KEY": "TU_KEY_PAPER",
            "ALPACA_API_SECRET": "TU_SECRET_PAPER",
            "ALPACA_PAPER": "true",
            "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
        },
        now=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert diagnostic["status"] == "FAIL"
    assert diagnostic["error_category"] == "PLACEHOLDER_KEYS"
    assert diagnostic["configured"] is False
    assert diagnostic["placeholder_keys"] == ["ALPACA_API_KEY", "ALPACA_API_SECRET"]
    assert diagnostic["probes"] == []
    assert diagnostic["safe_for_signals"] is False
    assert "credenciales paper reales" in diagnostic["next_action"]
    assert diagnostic["live_orders_allowed"] is False


def test_alpaca_market_data_diagnostic_confirms_readonly_feed(monkeypatch):
    probe_time = datetime(2026, 6, 15, 11, 59, 55, tzinfo=timezone.utc)
    ok_result = {
        "ok": True,
        "configured": True,
        "price": 214.25,
        "price_time": probe_time,
        "source": "Alpaca IEX",
        "source_mode": "BROKER_DATA",
        "detail": "ok",
    }
    monkeypatch.setattr(living_market, "fetch_alpaca_latest_trade", lambda symbol, env=None: ok_result)
    monkeypatch.setattr(living_market, "fetch_alpaca_latest_quote", lambda symbol, env=None: ok_result)
    monkeypatch.setattr(living_market, "fetch_alpaca_latest_bar", lambda symbol, env=None: ok_result)

    diagnostic = living_market.build_alpaca_market_data_diagnostic(
        "AAPL",
        env={
            "ALPACA_API_KEY": "key",
            "ALPACA_API_SECRET": "secret",
            "ALPACA_PAPER": "true",
            "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
            "ALPACA_DATA_FEED": "iex",
        },
        now=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert diagnostic["status"] == "OK"
    assert diagnostic["safe_for_signals"] is True
    assert diagnostic["feed"] == "IEX"
    assert diagnostic["mode"] == "paper"
    assert diagnostic["live_orders_allowed"] is False
    assert all(item["status"] == "OK" for item in diagnostic["probes"])


def test_alpaca_market_data_diagnostic_surfaces_auth_invalid(monkeypatch):
    auth_fail = {
        "ok": False,
        "configured": True,
        "reason": "alpaca_auth",
        "detail": "Alpaca rechazo credenciales.",
        "action": "Rotar credenciales.",
        "error": "401 unauthorized",
    }
    monkeypatch.setattr(living_market, "fetch_alpaca_latest_trade", lambda symbol, env=None: auth_fail)
    monkeypatch.setattr(
        living_market,
        "fetch_alpaca_latest_quote",
        lambda symbol, env=None: (_ for _ in ()).throw(AssertionError("quote should be skipped after auth fail")),
    )
    monkeypatch.setattr(
        living_market,
        "fetch_alpaca_latest_bar",
        lambda symbol, env=None: (_ for _ in ()).throw(AssertionError("bar should be skipped after auth fail")),
    )

    diagnostic = living_market.build_alpaca_market_data_diagnostic(
        "AAPL",
        env={
            "ALPACA_API_KEY": "bad",
            "ALPACA_SECRET_KEY": "bad-secret",
            "ALPACA_PAPER": "true",
            "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
        },
        now=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert diagnostic["status"] == "FAIL"
    assert diagnostic["error_category"] == "AUTH_INVALID"
    assert diagnostic["safe_for_signals"] is False
    assert diagnostic["probes"][0]["error_category"] == "AUTH_INVALID"
    assert diagnostic["probes"][1]["status"] == "SKIPPED"
    assert "Rotar credenciales" in diagnostic["next_action"]
