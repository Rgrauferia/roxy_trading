import os
import logging
from fastapi.testclient import TestClient


def test_health():
    from tools import voice_service

    client = TestClient(voice_service.app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_roxy_live_page():
    from tools import voice_service

    client = TestClient(voice_service.app)
    r = client.get("/roxy-live")
    assert r.status_code == 200
    assert "Roxy Live" in r.text
    assert "/v1/assist/state" in r.text
    assert "loadMemory" in r.text
    assert "data-prompt" in r.text
    assert 'data-prompt="estado de roxy"' in r.text
    assert "chat" in r.text
    assert "conversationMode" in r.text
    assert "Modo conversacion" in r.text
    assert "scheduleListen" in r.text
    assert "wakeMode" in r.text
    assert "wakeWord" in r.text
    assert "extractWakeCommand" in r.text
    assert "Wake Roxy activo" in r.text
    assert "feedbackUp" in r.text
    assert "/v1/feedback" in r.text
    assert "feedbackNote" in r.text
    assert "note: $(\"feedbackNote\").value" in r.text
    assert "loadLearning" in r.text
    assert "/v1/learning/status" in r.text
    assert "/assets/roxy_avatar.jpg" in r.text
    assert "/assets/roxy_avatar_icon.jpg" in r.text
    assert "/assets/roxy_avatar_card.jpg" in r.text
    assert "Roxy IA activa" in r.text
    assert "voiceSelect" in r.text
    assert "voiceRate" in r.text
    assert "voicePitch" in r.text
    assert "preferredName" in r.text
    assert 'id="language"' in r.text
    assert "roxyLiveLanguage" in r.text
    assert "language: $(\"language\").value" in r.text
    assert "/v1/profile" in r.text
    assert "loadSources" in r.text
    assert "/v1/knowledge/sources" in r.text
    assert "roxyLiveApiKey" not in r.text


def test_roxy_avatar_asset_served():
    from tools import voice_service

    client = TestClient(voice_service.app)
    r = client.get("/assets/roxy_avatar.jpg")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/")


def test_roxy_avatar_variants_served():
    from tools import voice_service

    client = TestClient(voice_service.app)
    for name in ("roxy_avatar_mini.jpg", "roxy_avatar_icon.jpg", "roxy_avatar_splash.jpg", "roxy_avatar_card.jpg"):
        r = client.get(f"/assets/{name}")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/")


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


def test_assist_state_returns_structured_roxy_state(monkeypatch):
    os.environ["VOICE_API_KEY"] = "testkey"
    from tools import voice_service

    monkeypatch.setattr(voice_service, "VOICE_API_KEY", "testkey")
    monkeypatch.setattr(voice_service, "llm", None)
    monkeypatch.setattr(
        voice_service.va_backend,
        "generate_reply_state",
        lambda q, user=None, session_id=None: {
            "reply": "Puedo conversar y explicar senales.",
            "intent": "capabilities",
            "voice_style": "female_es_latam",
            "should_speak": True,
            "needs_live_source": False,
            "safety_level": "guarded",
            "suggested_actions": ["connect_realtime_voice"],
        },
    )
    voice_service._RATE_STATE.clear()

    client = TestClient(voice_service.app)
    headers = {"Authorization": "Bearer testkey", "Content-Type": "application/json"}
    r = client.post(
        "/v1/assist/state",
        json={"query": "que puedes hacer", "user": "alice", "session_id": "test-session"},
        headers=headers,
    )

    assert r.status_code == 200
    payload = r.json()
    assert payload["intent"] == "capabilities"
    assert payload["voice_style"] == "female_es_latam"
    assert "reply" in payload


def test_assist_session_returns_memory_state(monkeypatch):
    os.environ["VOICE_API_KEY"] = "testkey"
    from tools import voice_service

    monkeypatch.setattr(voice_service, "VOICE_API_KEY", "testkey")
    monkeypatch.setattr(
        voice_service.va_backend,
        "get_session_state",
        lambda session_id, limit=8: {
            "session_id": session_id,
            "turn_count": 1,
            "last_intent": "opportunity",
            "last_safety_level": "guarded",
            "recent_turns": [{"intent": "opportunity"}],
        },
    )
    voice_service._RATE_STATE.clear()

    client = TestClient(voice_service.app)
    headers = {"Authorization": "Bearer testkey"}
    r = client.get("/v1/assist/session/demo-session", headers=headers)

    assert r.status_code == 200
    payload = r.json()
    assert payload["session_id"] == "demo-session"
    assert payload["last_intent"] == "opportunity"


def test_assist_events_returns_ordered_events(monkeypatch):
    os.environ["VOICE_API_KEY"] = "testkey"
    from tools import voice_service

    monkeypatch.setattr(voice_service, "VOICE_API_KEY", "testkey")
    monkeypatch.setattr(voice_service, "llm", None)
    monkeypatch.setattr(
        voice_service.va_backend,
        "generate_reply_state",
        lambda q, user=None, session_id=None: {
            "reply": "Hola.",
            "intent": "greeting",
            "voice_style": "female_es_latam",
            "avatar_state": "speaking",
            "emotion": "warm",
            "should_speak": True,
            "needs_live_source": False,
            "safety_level": "normal",
            "priority": "normal",
            "suggested_actions": [],
            "events": [{"type": "transcript_received"}, {"type": "speak"}],
        },
    )
    voice_service._RATE_STATE.clear()

    client = TestClient(voice_service.app)
    headers = {"Authorization": "Bearer testkey", "Content-Type": "application/json"}
    r = client.post("/v1/assist/events", json={"query": "hola", "session_id": "demo"}, headers=headers)

    assert r.status_code == 200
    payload = r.json()
    assert [event["type"] for event in payload["events"]] == ["transcript_received", "speak"]


def test_profile_endpoints(monkeypatch):
    os.environ["VOICE_API_KEY"] = "testkey"
    from tools import voice_service

    store = {}
    monkeypatch.setattr(voice_service, "VOICE_API_KEY", "testkey")
    monkeypatch.setattr(
        voice_service.va_backend, "update_user_profile", lambda user, profile: store.setdefault(user, profile)
    )
    monkeypatch.setattr(voice_service.va_backend, "get_user_profile", lambda user: store.get(user, {}))

    client = TestClient(voice_service.app)
    headers = {"Authorization": "Bearer testkey", "Content-Type": "application/json"}
    saved = client.post(
        "/v1/profile",
        json={"user": "local", "profile": {"preferred_name": "Roberto", "trading_mode": "paper"}},
        headers=headers,
    )
    loaded = client.get("/v1/profile/local", headers={"Authorization": "Bearer testkey"})

    assert saved.status_code == 200
    assert loaded.status_code == 200
    assert loaded.json()["preferred_name"] == "Roberto"


def test_knowledge_sources_endpoint(monkeypatch):
    os.environ["VOICE_API_KEY"] = "testkey"
    from tools import voice_service

    monkeypatch.setattr(voice_service, "VOICE_API_KEY", "testkey")
    monkeypatch.setattr(
        voice_service.va_backend,
        "get_knowledge_sources",
        lambda: [{"path": "README.md", "exists": True, "size_bytes": 100, "modified_at": "now"}],
    )

    client = TestClient(voice_service.app)
    r = client.get("/v1/knowledge/sources", headers={"Authorization": "Bearer testkey"})

    assert r.status_code == 200
    assert r.json()["sources"][0]["path"] == "README.md"


def test_feedback_endpoints(monkeypatch):
    os.environ["VOICE_API_KEY"] = "testkey"
    from tools import voice_service

    saved = []
    monkeypatch.setattr(voice_service, "VOICE_API_KEY", "testkey")
    monkeypatch.setattr(voice_service.va_backend, "record_feedback", lambda payload: saved.append(payload) or payload)
    monkeypatch.setattr(
        voice_service.va_backend,
        "get_feedback_summary",
        lambda user=None: {"total": len(saved), "up": 1, "down": 0, "top_intents": [], "recent": saved},
    )

    client = TestClient(voice_service.app)
    headers = {"Authorization": "Bearer testkey", "Content-Type": "application/json"}
    posted = client.post(
        "/v1/feedback",
        json={"rating": "up", "user": "local", "intent": "greeting", "query": "hola", "reply": "hola"},
        headers=headers,
    )
    summary = client.get("/v1/feedback/summary?user=local", headers={"Authorization": "Bearer testkey"})

    assert posted.status_code == 200
    assert summary.status_code == 200
    assert summary.json()["total"] == 1


def test_learning_status_endpoint(monkeypatch):
    os.environ["VOICE_API_KEY"] = "testkey"
    from tools import voice_service

    monkeypatch.setattr(voice_service, "VOICE_API_KEY", "testkey")
    monkeypatch.setattr(
        voice_service.va_backend,
        "get_learning_snapshot",
        lambda user=None, session_id=None: {
            "status": "learning",
            "mode": "local_feedback_profile_memory",
            "user": user,
            "session_id": session_id,
            "feedback": {"total": 2, "up": 1, "down": 1, "top_intents": [], "recent": []},
            "memory": {"turn_count": 3, "recent_turns": []},
            "knowledge_sources": [],
            "recommendations": ["Revisar oportunidad."],
        },
    )

    client = TestClient(voice_service.app)
    r = client.get(
        "/v1/learning/status?user=local&session_id=demo",
        headers={"Authorization": "Bearer testkey"},
    )

    assert r.status_code == 200
    payload = r.json()
    assert payload["status"] == "learning"
    assert payload["feedback"]["down"] == 1
    assert payload["memory"]["turn_count"] == 3


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
