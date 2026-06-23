import os
import pytest

flask = pytest.importorskip("flask")

from tools import admin_api


def test_admin_api_audit_csv_and_log(tmp_path, monkeypatch):
    # Provide ADMIN_TOKEN via env and config fallback
    token = "testtoken123"
    monkeypatch.setenv("ADMIN_TOKEN", token)

    # ensure storage has at least one role audit entry
    import storage
    db = tmp_path / "roxy.db"
    storage.DB_PATH = str(db)
    storage.init_db(storage.DB_PATH)
    storage.set_user_role("alice", "admin", actor="system")

    client = admin_api.app.test_client()

    # CSV endpoint
    resp = client.get("/audit.csv", headers={"X-Admin-Token": token})
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "target_user" in text or "alice" in text

    # Log endpoint (may be empty at first)
    resp2 = client.get("/audit/log", headers={"X-Admin-Token": token})
    assert resp2.status_code == 200


def test_admin_api_health_and_tradingview_status(monkeypatch):
    monkeypatch.delenv("TRADINGVIEW_WEBHOOK_SECRET", raising=False)
    client = admin_api.app.test_client()

    health = client.get("/health")
    missing = client.get("/tradingview/status")
    monkeypatch.setenv("TRADINGVIEW_WEBHOOK_SECRET", "tv-secret")
    configured = client.get("/tradingview/status")

    assert health.status_code == 200
    assert health.get_json()["ok"] is True
    assert missing.get_json()["auth"] == "missing"
    assert configured.get_json()["auth"] == "configured"
    assert configured.get_json()["real_orders_enabled"] is False


def test_admin_api_tradingview_webhook_requires_secret(tmp_path, monkeypatch):
    monkeypatch.delenv("TRADINGVIEW_WEBHOOK_SECRET", raising=False)
    monkeypatch.chdir(tmp_path)
    client = admin_api.app.test_client()

    resp = client.post(
        "/tradingview/webhook",
        json={"symbol": "NASDAQ:AAPL", "timeframe": "15", "signal": "BUY", "price": 185},
    )

    assert resp.status_code == 503
    assert resp.get_json()["status"] == "MISSING_SECRET_CONFIG"


def test_admin_api_tradingview_webhook_records_authenticated_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADINGVIEW_WEBHOOK_SECRET", "tv-secret")
    monkeypatch.chdir(tmp_path)
    client = admin_api.app.test_client()

    resp = client.post(
        "/tradingview/webhook",
        headers={"X-TradingView-Secret": "tv-secret"},
        json={"symbol": "NASDAQ:AAPL", "timeframe": "15", "signal": "BUY", "price": 185},
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["symbol"] == "AAPL"
    assert body["signal"] == "BUY"
    assert (tmp_path / "alerts" / "tradingview_webhooks.jsonl").exists()


def test_admin_api_tradingview_webhook_rejects_invalid_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADINGVIEW_WEBHOOK_SECRET", "tv-secret")
    monkeypatch.chdir(tmp_path)
    client = admin_api.app.test_client()

    resp = client.post(
        "/tradingview/webhook",
        headers={"X-TradingView-Secret": "wrong"},
        json={"symbol": "NASDAQ:AAPL", "timeframe": "15", "signal": "BUY", "price": 185},
    )

    assert resp.status_code == 403
    assert resp.get_json()["status"] == "INVALID_SECRET"
