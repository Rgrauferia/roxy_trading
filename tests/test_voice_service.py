import os
import logging
from fastapi.testclient import TestClient


def test_health():
    from tools import voice_service

    client = TestClient(voice_service.app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_assist_stub(monkeypatch):
    # ensure API key mode is bypassed by setting VOICE_API_KEY to a known value
    os.environ["VOICE_API_KEY"] = "testkey"
    from tools import voice_service

    # monkeypatch the rule-based backend
    try:
        from tools import voice_assistant

        monkeypatch.setattr(voice_assistant, "generate_reply", lambda q, user=None: "stub-reply")
    except Exception:
        pass

    client = TestClient(voice_service.app)
    headers = {"Authorization": "Bearer testkey", "Content-Type": "application/json"}
    r = client.post("/v1/assist", json={"query": "hello", "user": "alice"}, headers=headers)
    assert r.status_code == 200
    assert "reply" in r.json()


def test_dev_auth_warning_logs_once(monkeypatch, caplog):
    from tools import voice_service

    monkeypatch.setattr(voice_service, "VOICE_API_KEY", None)
    monkeypatch.setattr(voice_service, "_DEV_AUTH_WARNING_LOGGED", False)
    monkeypatch.setattr(voice_service, "llm", None)
    if voice_service.va_backend is not None:
        monkeypatch.setattr(voice_service.va_backend, "generate_reply", lambda q, user=None: "stub-reply")
    voice_service._RATE_STATE.clear()

    client = TestClient(voice_service.app)
    with caplog.at_level(logging.WARNING, logger="voice_service"):
        for _ in range(2):
            r = client.post("/v1/assist", json={"query": "hello"})
            assert r.status_code == 200

    messages = [record.message for record in caplog.records if "VOICE_API_KEY not set" in record.message]
    assert messages == ["VOICE_API_KEY not set — running in permissive dev mode"]
