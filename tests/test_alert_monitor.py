from __future__ import annotations

from datetime import datetime, timezone

from roxy_trader.alert_monitor import (
    ALERT_MONITOR_CONTRACT_VERSION,
    alert_quote_gate,
    alert_technical_gate,
    monitor_price_alerts,
)
from roxy_trader.watchlists import WatchlistStore
from tools import price_alert_monitor


def crypto_quote(price: float, *, age: int = 2) -> dict:
    return {
        "price": price,
        "age_seconds": age,
        "freshness": "LIVE",
        "source_mode": "EXCHANGE_TICKER",
        "provider": "BinanceUS",
        "source": "BinanceUS ticker",
        "market_open": True,
    }


def test_alert_quote_gate_accepts_exchange_crypto_and_broker_stock_only():
    assert alert_quote_gate(crypto_quote(3500), market="crypto")["accepted"] is True
    assert alert_quote_gate(
        {
            "price": 200,
            "age_seconds": 3,
            "freshness": "FRESH",
            "source_mode": "BROKER_DATA",
            "provider": "Alpaca",
            "source": "Alpaca IEX",
            "market_open": True,
        },
        market="stock",
    )["accepted"] is True
    fallback = alert_quote_gate(
        {
            "price": 200,
            "age_seconds": 3,
            "freshness": "LIVE",
            "source_mode": "PUBLIC_MARKET_DATA",
            "provider": "yfinance",
            "source": "yfinance currentPrice",
            "market_open": True,
        },
        market="stock",
    )
    assert fallback["accepted"] is False
    assert fallback["status"] == "PROVEEDOR_PREMIUM_BLOQUEADO"


def test_alert_quote_gate_rejects_stale_or_missing_prices():
    assert alert_quote_gate(crypto_quote(100, age=121), market="crypto")["status"] == "DATO_RETRASADO"
    assert alert_quote_gate({"freshness": "FAIL"}, market="crypto")["status"] == "SIN_DATOS"


def technical_snapshot(**overrides):
    return {
        "previous_fast": 99,
        "previous_slow": 100,
        "current_fast": 101,
        "current_slow": 100,
        "relative_volume": 1.9,
        "indicator_engine": "roxy-indicators/1.1.0",
        "freshness": "FRESH",
        "age_seconds": 10,
        "source": "BinanceUS klines",
        "source_mode": "EXCHANGE_API",
        "provider": "BinanceUS",
        **overrides,
    }


def test_technical_gate_requires_central_engine_fresh_verified_candles():
    accepted = alert_technical_gate(
        technical_snapshot(), alert_type="ema_cross_above", market="crypto", timeframe="15m"
    )
    assert accepted["accepted"] is True
    assert accepted["current_fast"] == 101
    assert alert_technical_gate(
        technical_snapshot(indicator_engine="private-formula"),
        alert_type="ema_cross_above", market="crypto", timeframe="15m",
    )["status"] == "INDICATOR_ENGINE_INVALID"
    assert alert_technical_gate(
        technical_snapshot(source_mode="FALLBACK", provider="yfinance"),
        alert_type="relative_volume_above", market="stock", timeframe="15m",
    )["status"] == "VELAS_PREMIUM_BLOQUEADAS"


def test_monitor_triggers_once_deduplicates_quotes_and_records_notification(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    for user in ("alice", "bob"):
        store.create_price_alert(
            user,
            symbol="ETH/USD",
            market="crypto",
            alert_type="price_above",
            threshold=3000,
        )
    fetches = []
    notifications = []

    def fetch(symbol, market):
        fetches.append((symbol, market))
        return crypto_quote(3100)

    report = monitor_price_alerts(
        store,
        fetch,
        notifier=lambda message: notifications.append(message) or {"sent": False, "reason": "recorded_local"},
        now=datetime(2026, 7, 19, tzinfo=timezone.utc),
    )

    assert report["contract_version"] == ALERT_MONITOR_CONTRACT_VERSION
    assert report["status"] == "OK"
    assert report["evaluated"] == 2
    assert report["triggered"] == 2
    assert report["notifications"] == 2
    assert fetches == [("ETH/USD", "crypto")]
    assert len(notifications) == 2
    assert all(store.alerts_snapshot(user)[0]["status"] == "Activada" for user in ("alice", "bob"))

    second = monitor_price_alerts(store, fetch)
    assert second["status"] == "NO_DATA"
    assert second["triggered"] == 0
    assert fetches == [("ETH/USD", "crypto")]


def test_failed_delivery_remains_durable_and_retries_without_refetching_price(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    store.create_price_alert(
        "user", symbol="ETH/USD", market="crypto", alert_type="price_above", threshold=3000
    )
    fetches = []

    first = monitor_price_alerts(
        store,
        lambda *_args: fetches.append(True) or crypto_quote(3100),
        notifier=lambda _message: {"sent": False, "reason": "channel_timeout", "channels": ["webhook"]},
    )

    assert first["status"] == "WARNING"
    assert first["triggered"] == 1
    assert first["notification_failures"] == 1
    assert first["notification_pending"] == 1
    alert = store.alerts_snapshot("user")[0]
    assert alert["status"] == "Activada"
    assert alert["notification_status"] == "RETRY_PENDING"
    assert alert["notification_attempts"] == 1

    second = monitor_price_alerts(
        store,
        lambda *_args: fetches.append(True) or crypto_quote(3100),
        notifier=lambda _message: {"sent": True, "reason": "delivered", "channels": ["webhook"]},
    )

    assert second["status"] == "OK"
    assert second["active_alerts"] == 0
    assert second["evaluated"] == 0
    assert second["notifications"] == 1
    assert second["notification_pending"] == 0
    assert fetches == [True]
    delivered = store.alerts_snapshot("user")[0]
    assert delivered["notification_status"] == "DELIVERED"
    assert delivered["notification_attempts"] == 2
    assert delivered["notified_at"]


def test_monitor_keeps_rule_active_and_persists_degraded_provider_state(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    store.create_price_alert(
        "user",
        symbol="AAPL",
        market="stock",
        alert_type="price_above",
        threshold=100,
    )

    report = monitor_price_alerts(
        store,
        lambda _symbol, _market: {
            "price": 200,
            "age_seconds": 1,
            "freshness": "LIVE",
            "source_mode": "PUBLIC_MARKET_DATA",
            "provider": "yfinance",
            "source": "yfinance currentPrice",
            "market_open": True,
        },
    )

    alert = store.alerts_snapshot("user")[0]
    assert report["status"] == "WARNING"
    assert report["evaluated"] == 0
    assert report["blocked"] == 1
    assert alert["status"] == "Activa"
    assert alert["monitor_status"] == "PROVEEDOR_PREMIUM_BLOQUEADO"
    assert "fallback" in alert["monitor_detail"]
    assert alert["last_source"] == "yfinance currentPrice"


def test_monitor_is_no_data_without_active_rules(tmp_path):
    report = monitor_price_alerts(WatchlistStore(tmp_path / "watchlists.json"), lambda *_args: crypto_quote(1))

    assert report["status"] == "NO_DATA"
    assert report["detail"] == "No hay alertas activas para monitorear."


def test_monitor_expires_due_rule_before_fetching_market_data(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    store.create_price_alert(
        "user", symbol="AAPL", market="stock", alert_type="price_above", threshold=100
    )
    payload = store._read_unlocked()
    payload["users"]["user"]["alerts"][0]["expires_at"] = "2026-07-18T00:00:00+00:00"
    store._write_unlocked(payload)
    calls = []

    report = monitor_price_alerts(
        store,
        lambda *_args: calls.append(True) or crypto_quote(200),
        now=datetime(2026, 7, 19, tzinfo=timezone.utc),
    )

    assert report["status"] == "NO_DATA"
    assert report["expired"] == 1
    assert calls == []
    assert store.alerts_snapshot("user")[0]["status"] == "Expirada"


def test_monitor_evaluates_ema_and_volume_rules_with_verified_technical_fetcher(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    store.create_technical_alert(
        "user", symbol="ETH/USD", market="crypto", alert_type="ema_cross_above", timeframe="15m"
    )
    store.create_technical_alert(
        "user", symbol="ETH/USD", market="crypto", alert_type="relative_volume_above",
        timeframe="15m", threshold=1.8,
    )
    calls = []
    notifications = []

    def technical_fetch(symbol, market, timeframe, fast, slow):
        calls.append((symbol, market, timeframe, fast, slow))
        return technical_snapshot()

    report = monitor_price_alerts(
        store,
        lambda *_args: crypto_quote(3500),
        technical_fetcher=technical_fetch,
        notifier=lambda message: notifications.append(message) or {"sent": True},
    )

    assert report["status"] == "OK"
    assert report["evaluated"] == 2
    assert report["triggered"] == 2
    assert report["notifications"] == 2
    assert len(calls) == 2
    assert any("EMA9 cruzó sobre EMA21" in message for message in notifications)
    assert any("volumen relativo alcanzó 1.9x" in message for message in notifications)
    assert all(row["status"] == "Activada" for row in store.alerts_snapshot("user"))


def test_monitor_blocks_technical_rule_when_fetcher_or_premium_history_is_unavailable(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.json")
    store.create_technical_alert(
        "user", symbol="AAPL", market="stock", alert_type="ema_cross_below", timeframe="15m"
    )
    stock_quote = {
        "price": 200, "age_seconds": 1, "freshness": "FRESH", "source_mode": "BROKER_DATA",
        "provider": "Alpaca", "source": "Alpaca IEX", "market_open": True,
    }
    missing = monitor_price_alerts(store, lambda *_args: stock_quote)
    assert missing["status"] == "WARNING"
    assert store.alerts_snapshot("user")[0]["monitor_status"] == "TECHNICAL_FETCHER_NOT_CONFIGURED"

    fallback = monitor_price_alerts(
        store,
        lambda *_args: stock_quote,
        technical_fetcher=lambda *_args: technical_snapshot(
            source_mode="FALLBACK", provider="yfinance", source="yfinance fallback"
        ),
    )
    assert fallback["status"] == "WARNING"
    alert = store.alerts_snapshot("user")[0]
    assert alert["status"] == "Activa"
    assert alert["monitor_status"] == "VELAS_PREMIUM_BLOQUEADAS"


def test_recurring_monitor_builds_technical_snapshot_with_central_engine(monkeypatch):
    import pandas as pd

    now = pd.Timestamp.now(tz="UTC").floor("min")
    frame = pd.DataFrame(
        {
            "ts": pd.date_range(end=now, periods=60, freq="15min"),
            "open": [100 + index * 0.1 for index in range(60)],
            "high": [101 + index * 0.1 for index in range(60)],
            "low": [99 + index * 0.1 for index in range(60)],
            "close": [100.5 + index * 0.1 for index in range(60)],
            "volume": [1000 + index * 10 for index in range(60)],
        }
    )
    monkeypatch.setattr(
        price_alert_monitor,
        "fetch_symbol_history_with_source",
        lambda *_args, **_kwargs: (
            frame,
            {"mode": "EXCHANGE_API", "provider": "BinanceUS", "label": "BinanceUS API"},
        ),
    )

    snapshot = price_alert_monitor.build_technical_alert_snapshot("BTC/USD", "crypto", "15m", 9, 21)

    assert snapshot["indicator_engine"] == "roxy-indicators/1.1.0"
    assert snapshot["source_mode"] == "EXCHANGE_API"
    assert snapshot["provider"] == "BinanceUS"
    assert snapshot["freshness"] == "FRESH"
    assert snapshot["age_seconds"] < 120
    assert snapshot["relative_volume"] > 0
