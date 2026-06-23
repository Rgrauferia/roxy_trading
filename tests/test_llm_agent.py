import json
from fastapi.testclient import TestClient

from tools import voice_service

client = TestClient(voice_service.app)


def test_ai_signal_endpoint_returns_list():
    resp = client.post("/api/ai/signal", json={"symbols": ["AAPL", "MSFT"], "horizon": "1d"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # each item should have symbol and action
    for item in data:
        assert 'symbol' in item
        assert 'action' in item
