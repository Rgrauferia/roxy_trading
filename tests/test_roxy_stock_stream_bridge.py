import json

import pytest

from tools.roxy_stock_stream_bridge import app, normalize_stock_symbols, sse_event


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
