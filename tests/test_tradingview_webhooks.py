from datetime import datetime, timedelta, timezone

from tradingview_webhooks import (
    append_tradingview_webhook,
    append_authenticated_tradingview_webhook,
    latest_tradingview_confirmation,
    load_tradingview_webhooks,
    normalize_tradingview_payload,
    tradingview_confirmation_bias_for_opportunity,
    validate_tradingview_webhook_secret,
)


def test_normalize_tradingview_payload_sanitizes_secret_and_symbol():
    row = normalize_tradingview_payload(
        {
            "ticker": "NASDAQ:AAPL",
            "interval": "15",
            "action": "buy",
            "close": "185.25",
            "strategy": {"name": "ignored", "order": {"action": "buy"}},
            "message": "Pullback 20/40",
            "passphrase": "do-not-store",
        },
        now=datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc),
    )

    assert row["symbol"] == "AAPL"
    assert row["exchange"] == "NASDAQ"
    assert row["timeframe"] == "15m"
    assert row["signal"] == "BUY"
    assert row["price"] == 185.25
    assert row["market"] == "stock"
    assert row["raw_payload"]["passphrase"] == "[redacted]"


def test_append_load_and_dedupe_tradingview_webhooks(tmp_path):
    path = tmp_path / "tv.jsonl"
    payload = {
        "symbol": "BINANCE:BTCUSDT",
        "timeframe": "60",
        "signal": "LONG",
        "price": 65000,
        "message": "Breakout",
    }

    first = append_tradingview_webhook(payload, path, now=datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc))
    second = append_tradingview_webhook(payload, path, now=datetime(2026, 6, 15, 15, 1, tzinfo=timezone.utc))
    rows = load_tradingview_webhooks(path)

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert len(rows) == 1
    assert rows.iloc[0]["symbol"] == "BTC/USDT"
    assert rows.iloc[0]["timeframe"] == "1h"
    assert rows.iloc[0]["market"] == "crypto"


def test_latest_confirmation_matches_symbol_alias_and_freshness(tmp_path):
    path = tmp_path / "tv.jsonl"
    now = datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc)
    append_tradingview_webhook(
        {"symbol": "NASDAQ:AAPL", "timeframe": "15", "signal": "BUY", "price": 100},
        path,
        now=now - timedelta(minutes=10),
    )
    rows = load_tradingview_webhooks(path)

    latest = latest_tradingview_confirmation("AAPL", "15m", rows=rows, now=now, max_age_minutes=30)

    assert latest["fresh"] is True
    assert latest["signal"] == "BUY"
    assert latest["age_minutes"] == 10


def test_latest_confirmation_matches_crypto_usdt_to_usd_alias(tmp_path):
    path = tmp_path / "tv.jsonl"
    now = datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc)
    append_tradingview_webhook(
        {"symbol": "BINANCE:BTCUSDT", "timeframe": "60", "signal": "BUY", "price": 65000},
        path,
        now=now,
    )
    rows = load_tradingview_webhooks(path)

    latest = latest_tradingview_confirmation("BTC/USD", "1h", rows=rows, now=now, max_age_minutes=30)

    assert latest["fresh"] is True
    assert latest["symbol"] == "BTC/USDT"


def test_confirmation_bias_rewards_buy_and_penalizes_sell(tmp_path):
    now = datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc)
    path = tmp_path / "tv.jsonl"
    append_tradingview_webhook(
        {"symbol": "AAPL", "timeframe": "15m", "signal": "BUY", "price": 100},
        path,
        now=now,
    )
    append_tradingview_webhook(
        {"symbol": "MSFT", "timeframe": "15m", "signal": "SELL", "price": 200},
        path,
        now=now,
    )
    rows = load_tradingview_webhooks(path)

    buy = tradingview_confirmation_bias_for_opportunity(
        {"symbol": "AAPL", "timeframe": "15m"}, rows=rows, now=now
    )
    sell = tradingview_confirmation_bias_for_opportunity(
        {"symbol": "MSFT", "timeframe": "15m"}, rows=rows, now=now
    )

    assert buy["label"] == "TradingView confirma"
    assert buy["priority_delta"] == 1
    assert sell["label"] == "TradingView contradice"
    assert sell["priority_delta"] == -1


def test_validate_tradingview_webhook_secret_accepts_header_and_payload():
    env = {"TRADINGVIEW_WEBHOOK_SECRET": "tv-secret"}

    header_result = validate_tradingview_webhook_secret(
        {"symbol": "AAPL"},
        headers={"X-TradingView-Secret": "tv-secret"},
        env=env,
    )
    payload_result = validate_tradingview_webhook_secret(
        {"symbol": "AAPL", "passphrase": "tv-secret"},
        headers={},
        env=env,
    )
    roxy_header_result = validate_tradingview_webhook_secret(
        {"symbol": "AAPL"},
        headers={"X-Roxy-TradingView-Secret": "tv-secret"},
        env=env,
    )
    bad_result = validate_tradingview_webhook_secret(
        {"symbol": "AAPL", "passphrase": "wrong"},
        headers={},
        env=env,
    )

    assert header_result["ok"] is True
    assert payload_result["ok"] is True
    assert roxy_header_result["ok"] is True
    assert bad_result["ok"] is False
    assert bad_result["status"] == "INVALID_SECRET"


def test_append_authenticated_tradingview_webhook_records_without_storing_secret(tmp_path):
    path = tmp_path / "tv.jsonl"
    result = append_authenticated_tradingview_webhook(
        {
            "symbol": "NASDAQ:AAPL",
            "timeframe": "15",
            "signal": "BUY",
            "price": 185,
            "passphrase": "tv-secret",
        },
        env={"TRADINGVIEW_WEBHOOK_SECRET": "tv-secret"},
        path=path,
        now=datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc),
    )
    rows = load_tradingview_webhooks(path)

    assert result["ok"] is True
    assert result["status"] == "RECORDED"
    assert rows.iloc[0]["symbol"] == "AAPL"
    assert rows.iloc[0]["raw_payload"]["passphrase"] == "[redacted]"
