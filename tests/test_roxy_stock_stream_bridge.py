import json
from pathlib import Path

import pytest

from tools import roxy_stock_stream_bridge
from tools.roxy_stock_stream_bridge import app, normalize_stock_symbols, sse_event, stock_snapshot_payload


def test_normalize_stock_symbols_limits_and_sanitizes_input():
    symbols = normalize_stock_symbols(" aapl, MSFT; nvda!, TSLA, AAPL ")

    assert symbols == ["AAPL", "MSFT", "NVDA", "TSLA"]
    assert len(normalize_stock_symbols(",".join(f"SYM{i}" for i in range(40)))) == 24


def test_sse_event_contains_named_event_and_json_payload():
    packed = sse_event("quote", {"symbol": "AAPL", "price": 100.25})

    assert packed.startswith("event: quote\n")
    data_line = [line for line in packed.splitlines() if line.startswith("data: ")][0]
    assert json.loads(data_line.replace("data: ", "")) == {"symbol": "AAPL", "price": 100.25}


def test_stock_bridge_root_and_health_endpoints_are_render_friendly():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(app)

    root = client.get("/")
    health = client.get("/health")

    assert root.status_code == 200
    assert root.json()["service"] == "roxy-stock-stream-bridge"
    assert health.status_code == 200
    assert health.json()["ok"] is True


def test_stock_bridge_snapshot_endpoint_returns_sanitized_quotes(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    def fake_quote(symbol):
        return {
            "symbol": symbol,
            "price": 123.45,
            "changePct": 0.12,
            "source": "test provider",
            "marketOpen": True,
            "updatedAt": "10:30:00 AM",
        }

    monkeypatch.setattr(roxy_stock_stream_bridge, "_quote_from_snapshot", fake_quote)
    client = TestClient(app)

    response = client.get("/v1/market/stock-snapshot?symbols=aapl,msft")
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert set(payload["symbols"]) == {"AAPL", "MSFT"}
    assert payload["quotes"]["AAPL"]["mode"] == "snapshot"
    assert payload["quotes"]["AAPL"]["price"] == 123.45


def test_stock_snapshot_payload_omits_unavailable_symbols(monkeypatch):
    def fake_quote(symbol):
        if symbol == "AAPL":
            return {"symbol": symbol, "price": 200, "source": "test"}
        return None

    monkeypatch.setattr(roxy_stock_stream_bridge, "_quote_from_snapshot", fake_quote)

    payload = stock_snapshot_payload(["AAPL", "MSFT"])

    assert payload["symbols"] == ["AAPL"]
    assert "MSFT" not in payload["quotes"]


def test_stock_bridge_yahoo_fallback_parses_chart_quote(monkeypatch):
    sample = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": 210.25,
                        "previousClose": 200.0,
                        "marketState": "REGULAR",
                        "regularMarketTime": 1783320000,
                    },
                    "indicators": {"quote": [{"close": [208.1, 210.25]}]},
                }
            ]
        }
    }

    monkeypatch.setattr(roxy_stock_stream_bridge, "_http_json", lambda *args, **kwargs: sample)

    quote = roxy_stock_stream_bridge._yahoo_quote("AAPL")

    assert quote["symbol"] == "AAPL"
    assert quote["price"] == 210.25
    assert quote["changePct"] == 5.125
    assert quote["marketOpen"] is True
    assert quote["source"] == "Yahoo chart fallback"


def test_stock_bridge_dockerfile_uses_render_safe_entrypoint_and_port():
    dockerfile = Path("Dockerfile.stock-bridge").read_text(encoding="utf-8")
    render_config = Path("render.yaml").read_text(encoding="utf-8")

    assert 'ENTRYPOINT ["./scripts/stock_bridge_entrypoint.sh"]' in dockerfile
    assert "EXPOSE 10000" in dockerfile
    assert "port ${PORT:-10000}" in Path("scripts/stock_bridge_entrypoint.sh").read_text(encoding="utf-8")
    assert "name: roxy-stock-stream" in render_config
    assert "value: 10000" in render_config
