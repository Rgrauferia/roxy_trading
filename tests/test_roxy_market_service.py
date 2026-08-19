import importlib

from fastapi.testclient import TestClient

from roxy_trader.openai_brain import RoxyOpenAIConfig


def load_service(monkeypatch, product):
    monkeypatch.setenv("ROXY_MARKET_PRODUCT", product)
    monkeypatch.setenv(f"ROXY_{product.upper()}_ACCESS_KEY", f"{product}-access-key")
    monkeypatch.setenv(f"ROXY_{product.upper()}_OPENAI_ENABLED", "0")
    from tools import roxy_market_service

    return importlib.reload(roxy_market_service)


def verified_snapshot(symbol):
    return {
        "symbol": symbol,
        "price": 123.45,
        "previous_close": 120.0,
        "change_pct": 0.02875,
        "price_timestamp": "2026-08-19T14:31:00+00:00",
        "observed_at": "2026-08-19T14:31:01+00:00",
        "freshness": "LIVE",
        "source": "Proveedor verificado",
        "source_mode": "TEST_PROVIDER",
        "provider": "Proveedor",
        "market_open": True,
        "latency_note": "Dato verificado para prueba",
    }


def test_trading_surface_pairs_once_and_builds_server_side_context(monkeypatch):
    service = load_service(monkeypatch, "trading")
    monkeypatch.setattr(service, "_fetch_market_snapshot", verified_snapshot)
    service._CONTEXT_CACHE.clear()
    client = TestClient(service.app, base_url="https://stocks.test")

    page = client.get("/")
    denied = client.get("/v1/config")
    paired = client.post(
        "/v1/session", headers={"Authorization": "Bearer trading-access-key"}
    )
    config = client.get("/v1/config")
    context = client.get("/v1/market/AAPL")
    answer = client.post(
        "/v1/ai/explain",
        json={"question": "Explica el precio actual", "symbol": "AAPL", "depth": "routine"},
    )

    assert page.status_code == 200
    assert "ROXY_TRADING_OPENAI_API_KEY" not in page.text
    assert denied.status_code == 401
    assert paired.status_code == 200
    assert "HttpOnly" in paired.headers["set-cookie"]
    assert "Secure" in paired.headers["set-cookie"]
    assert "Max-Age=31536000" in paired.headers["set-cookie"]
    assert config.json()["product"] == "trading"
    assert context.json()["price"] == 123.45
    assert context.json()["sources"][0]["name"] == "Proveedor verificado"
    assert answer.json()["answer"]["blocked_reason"] == "not_configured"
    assert answer.json()["answer"]["execution_allowed"] is False


def test_crypto_surface_is_independent_and_normalizes_pairs(monkeypatch):
    service = load_service(monkeypatch, "crypto")
    monkeypatch.setattr(service, "_fetch_market_snapshot", verified_snapshot)
    service._CONTEXT_CACHE.clear()
    client = TestClient(service.app)
    headers = {"Authorization": "Bearer crypto-access-key"}

    config = client.get("/v1/config", headers=headers)
    context = client.get("/v1/market/BTC", headers=headers)

    assert config.json()["product"] == "crypto"
    assert config.json()["openai"]["product"] == "roxy_crypto"
    assert context.json()["symbol"] == "BTC/USD"
    assert context.json()["market"] == "crypto"


def test_openai_credentials_budgets_and_ledgers_are_product_scoped():
    env = {
        "ROXY_TRADING_OPENAI_API_KEY": "trading-secret",
        "ROXY_TRADING_OPENAI_ENABLED": "1",
        "ROXY_TRADING_OPENAI_MONTHLY_BUDGET_USD": "11",
        "ROXY_CRYPTO_OPENAI_API_KEY": "crypto-secret",
        "ROXY_CRYPTO_OPENAI_ENABLED": "1",
        "ROXY_CRYPTO_OPENAI_MONTHLY_BUDGET_USD": "7",
    }

    trading = RoxyOpenAIConfig.from_env(env, product="trading")
    crypto = RoxyOpenAIConfig.from_env(env, product="crypto")

    assert trading.api_key == "trading-secret"
    assert crypto.api_key == "crypto-secret"
    assert trading.product == "roxy_trading"
    assert crypto.product == "roxy_crypto"
    assert trading.monthly_budget_usd == 11
    assert crypto.monthly_budget_usd == 7
    assert trading.ledger_path != crypto.ledger_path
    assert "api_key" not in trading.public_status()
    assert "api_key" not in crypto.public_status()
