import json

from roxy_trader.api_budget import ApiUsageLedger

from tools.external_market_sources import (
    CryptoComClient,
    ExternalMarketAggregator,
    FinvizEliteClient,
    NormalizedMarketRow,
    TradingViewIntegration,
    apply_external_market_context,
    build_external_confirmation,
    build_finviz_market_pulse,
    build_finviz_news_feed,
    build_finviz_pattern_strategies,
    mask_secret,
    normalize_symbol_for_match,
    redact_url,
)


def test_mask_secret_keeps_only_edges():
    assert mask_secret("abcdef1234567890") == "abcd...7890"
    assert mask_secret("short") == "*****"


def test_redact_url_hides_finviz_auth_token():
    url = "https://elite.finviz.com/export/screener?ft=111&auth=super-secret-token&v=111"
    redacted = redact_url(url)

    assert "super-secret-token" not in redacted
    assert "auth=supe...oken" in redacted
    assert "ft=111" in redacted


def test_finviz_client_parses_export_csv_without_exposing_url_secret():
    def fake_transport(url, body, headers):
        assert body is None
        assert headers["User-Agent"].startswith("RoxyTrading")
        return "Ticker,Company,Sector,Industry,Price,Change,Volume\nAAPL,Apple Inc.,Technology,Consumer Electronics,195.25,+1.23%,1234567\n"

    client = FinvizEliteClient(
        "https://elite.finviz.com/export/screener?auth=secret-token-value",
        transport=fake_transport,
    )
    rows = client.fetch_screener()
    status = client.status().to_dict()

    assert rows[0].symbol == "AAPL"
    assert rows[0].market == "stock"
    assert rows[0].price == 195.25
    assert rows[0].change_pct == 1.23
    assert rows[0].volume == 1234567
    assert rows[0].raw["sector"] == "Technology"
    assert "secret-token-value" not in str(status)


def test_finviz_client_emits_real_usage_telemetry(tmp_path, monkeypatch):
    usage_path = tmp_path / "usage.sqlite"
    monkeypatch.setenv("ROXY_API_TELEMETRY_ENABLED", "1")
    monkeypatch.setenv("ROXY_API_USAGE_DB", str(usage_path))
    client = FinvizEliteClient(
        "https://elite.finviz.com/export/screener?auth=secret-token-value",
        transport=lambda *_args: "Ticker,Price\nAAPL,195.25\n",
    )

    assert client.fetch_screener()[0].symbol == "AAPL"
    summary = ApiUsageLedger(usage_path).provider_summary("finviz")

    assert summary["requests"] == 1
    assert summary["errors"] == 0


def test_finviz_client_accepts_auth_token_env_without_exposing_secret():
    captured = {}

    def fake_transport(url, body, headers):
        captured["url"] = url
        return "Ticker,Company,Sector,Industry,Price,Change,Volume,Signal\nAAPL,Apple Inc.,Technology,Consumer Electronics,195.25,+1.23%,1234567,Channel Up\n"

    client = FinvizEliteClient.from_env({"ROXY_FINVIZ_AUTH_TOKEN": "token-value-123456"}, transport=fake_transport)
    rows = client.fetch_screener()
    status = client.status().to_dict()

    assert rows[0].symbol == "AAPL"
    assert "elite.finviz.com/export/screener" in captured["url"]
    assert "auth=token-value-123456" in captured["url"]
    assert "token-value-123456" not in str(status)
    assert "ROXY_FINVIZ_AUTH_TOKEN" in status["present_keys"]


def test_finviz_market_pulse_extracts_movers_patterns_and_sector_pressure():
    csv_text = "\n".join(
        [
            "Ticker,Company,Sector,Industry,Price,Change,Volume,Signal,Rel Volume,Perf Week",
            "NVDA,NVIDIA Corp.,Technology,Semiconductors,199.41,+4.21%,34100000,Unusual Volume,2.5,+8.1%",
            "RIVN,Rivian Automotive,Consumer Cyclical,Auto Manufacturers,13.20,-18.12%,441000000,Downgrades,4.4,-22.0%",
            "AAPL,Apple Inc.,Technology,Consumer Electronics,194.87,-0.64%,60200000,Wedge Up,1.1,+1.0%",
            "META,Meta Platforms,Communication Services,Internet Content,715.40,+2.55%,18000000,Channel Up,1.8,+3.2%",
        ]
    )

    def fake_transport(url, body, headers):
        return csv_text

    client = FinvizEliteClient(
        "https://elite.finviz.com/export/screener?auth=secret-token-value",
        transport=fake_transport,
    )
    rows = client.fetch_screener()
    pulse = build_finviz_market_pulse(rows)

    assert pulse["row_count"] == 4
    assert pulse["major_movers"][0]["symbol"] == "RIVN"
    assert any(item["symbol"] == "AAPL" and item["signal"] == "Wedge Up" for item in pulse["pattern_signals"])
    assert pulse["sector_counts"]["Technology"] == 2
    assert pulse["summary"]["bullish_count"] == 2
    assert pulse["summary"]["bearish_count"] == 2
    assert any(item["strategy_family"] == "Ascending Channel" for item in pulse["pattern_strategies"])
    assert any(item["category"] == "Unusual Volume" for item in pulse["news_feed"])
    assert any(item["category"] == "Downgrades" for item in pulse["news_feed"])
    assert pulse["summary"]["news_count"] >= 2


def test_finviz_news_feed_extracts_major_news_and_analyst_events():
    rows = [
        {
            "source": "Finviz Elite",
            "symbol": "NVDA",
            "market": "stock",
            "price": 199.41,
            "change_pct": 0.71,
            "volume": 34100000,
            "signal": "Major News",
            "raw": {"Company": "NVIDIA Corp.", "Rel Volume": "1.8"},
        },
        {
            "source": "Finviz Elite",
            "symbol": "AMD",
            "market": "stock",
            "price": 141.22,
            "change_pct": -6.51,
            "volume": 28000000,
            "signal": "Downgrades",
            "raw": {"Company": "AMD Inc.", "Rel Volume": "2.2"},
        },
        {
            "source": "Finviz Elite",
            "symbol": "AAPL",
            "market": "stock",
            "price": 194.87,
            "change_pct": 1.28,
            "volume": 60200000,
            "signal": "Insider Buying",
            "raw": {"Company": "Apple Inc.", "Rel Volume": "1.1"},
        },
    ]

    feed = build_finviz_news_feed(rows)
    by_symbol = {item["symbol"]: item for item in feed}

    assert by_symbol["NVDA"]["category"] == "Major News"
    assert by_symbol["AMD"]["category"] == "Downgrades"
    assert by_symbol["AMD"]["impact"] == "alto"
    assert by_symbol["AMD"]["tone"] == "negative"
    assert by_symbol["AAPL"]["category"] == "Insider Buying"
    assert all(item["source"] == "Finviz Elite" for item in feed)


def test_finviz_pattern_strategies_convert_chart_labels_to_operating_plan():
    rows = [
        {
            "source": "Finviz Elite",
            "symbol": "AAPL",
            "market": "stock",
            "price": 194.87,
            "change_pct": 1.28,
            "volume": 60200000,
            "signal": "Triangle Asc.",
            "raw": {"Company": "Apple Inc.", "Sector": "Technology", "Rel Volume": "1.7"},
        },
        {
            "source": "Finviz Elite",
            "symbol": "MSFT",
            "market": "stock",
            "price": 505.12,
            "change_pct": 0.54,
            "volume": 32100000,
            "signal": "Channel Up",
            "raw": {"Company": "Microsoft Corp.", "Sector": "Technology", "Rel Volume": "1.2"},
        },
    ]

    strategies = build_finviz_pattern_strategies(rows)
    by_symbol = {item["symbol"]: item for item in strategies}

    assert by_symbol["AAPL"]["strategy_family"] == "Ascending Triangle"
    assert by_symbol["AAPL"]["action"] == "COMPRAR"
    assert "Soporte ascendente" in by_symbol["AAPL"]["entry_zone"]
    assert by_symbol["MSFT"]["strategy_family"] == "Ascending Channel"
    assert "Linea inferior" in by_symbol["MSFT"]["entry_zone"]
    assert by_symbol["MSFT"]["status"] == "WAIT_LIVE_CHART_CONFIRMATION"


def test_crypto_com_client_parses_public_ticker_response():
    payload = {
        "id": 1,
        "method": "public/get-tickers",
        "result": {
            "data": [
                {
                    "i": "BTC_USDT",
                    "b": "60070.25",
                    "a": "60074.29",
                    "k": "60072.10",
                    "v": "114.2",
                    "h": "0.31",
                    "t": 1783290600000,
                }
            ]
        },
    }

    def fake_transport(url, body, headers):
        assert url == "https://api.crypto.com/exchange/v1/public/get-tickers?instrument_name=BTC_USDT"
        assert body is None
        return json.dumps(payload)

    client = CryptoComClient(transport=fake_transport)
    row = client.get_ticker("BTC_USDT")

    assert row.symbol == "BTC/USDT"
    assert row.market == "crypto"
    assert row.price == 60074.29
    assert row.change_pct == 0.31
    assert row.volume == 114.2


def test_crypto_com_status_does_not_print_secret_values():
    client = CryptoComClient(api_key="visible-key-value", api_secret="secret-value")
    status = client.status().to_dict()

    assert status["configured"] is True
    assert "visible-key-value" not in str(status)
    assert "secret-value" not in str(status)


def test_tradingview_status_tracks_webhook_configuration_without_secret_value():
    status = TradingViewIntegration(
        {
            "TRADINGVIEW_WEBHOOK_SECRET": "my-secret",
            "TRADINGVIEW_PUBLIC_WEBHOOK_URL": "https://example.com/tradingview/webhook",
        }
    ).status().to_dict()

    assert status["configured"] is True
    assert status["mode"] == "CHARTS_AND_WEBHOOK_CONFIRMATION"
    assert "my-secret" not in str(status)


def test_aggregator_status_without_env_is_safe_and_non_remote():
    snapshot = ExternalMarketAggregator.from_env({}).fetch_snapshot(include_remote=False)

    assert snapshot["rows"] == []
    assert snapshot["market_pulse"]["finviz"]["row_count"] == 0
    assert {row["provider"] for row in snapshot["statuses"]} == {
        "Finviz Elite",
        "Crypto.com Exchange",
        "TradingView",
    }


def test_symbol_normalization_matches_crypto_variants():
    assert normalize_symbol_for_match("BTC/USD", "crypto") == "BTCUSDT"
    assert normalize_symbol_for_match("BTC_USDT", "crypto") == "BTCUSDT"
    assert normalize_symbol_for_match("AAPL", "stock") == "AAPL"


def test_external_confirmation_uses_crypto_com_row_for_btc_direction():
    opportunity = {"symbol": "BTC/USD", "market": "crypto", "signal": "BUY"}
    rows = [
        NormalizedMarketRow(
            source="Crypto.com Exchange",
            symbol="BTC/USDT",
            market="crypto",
            price=60074.29,
            change_pct=0.31,
            volume=114.2,
            signal="public/get-ticker",
        )
    ]

    confirmation = build_external_confirmation(opportunity, rows)

    assert confirmation["confirmed"] is True
    assert confirmation["price"] == 60074.29
    assert confirmation["score_adjustment"] > 0
    assert confirmation["color"] == "green"


def test_external_confirmation_uses_finviz_screener_for_stock_row():
    opportunity = {"symbol": "AAPL", "market": "stock", "signal": "BUY"}
    rows = [
        {
            "source": "Finviz Elite",
            "symbol": "AAPL",
            "market": "stock",
            "price": 195.25,
            "change_pct": 1.23,
            "volume": 1234567,
            "signal": "Breakout",
        }
    ]

    enriched = apply_external_market_context(opportunity, rows)

    assert enriched["external_confirmation"]["confirmed"] is True
    assert enriched["external_confirmation"]["bias"] == "ARRIBA"
    assert enriched["external_price"] == 195.25


def test_external_confirmation_includes_finviz_pattern_strategy():
    opportunity = {"symbol": "AAPL", "market": "stock", "signal": "BUY"}
    rows = [
        {
            "source": "Finviz Elite",
            "symbol": "AAPL",
            "market": "stock",
            "price": 195.25,
            "change_pct": 1.23,
            "volume": 1234567,
            "signal": "Channel Up",
            "raw": {"Rel Volume": "1.5"},
        }
    ]

    confirmation = build_external_confirmation(opportunity, rows)

    assert confirmation["pattern_strategy"]["strategy_family"] == "Ascending Channel"
    assert confirmation["pattern_strategy"]["action"] == "COMPRAR"
    assert any("Ascending Channel" in reason for reason in confirmation["reasons"])
