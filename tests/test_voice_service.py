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
    assert "/v1/assist/stream" in r.text
    assert "loadMemory" in r.text
    assert "nextActions" in r.text
    assert "activeContext" in r.text
    assert "latency" in r.text
    assert "server_latency_ms" in r.text
    assert "assistStreamEndpoint" in r.text
    assert "readAssistStream" in r.text
    assert "sendViaStream" in r.text
    assert "sendViaState" in r.text
    assert "parseSseBlock" in r.text
    assert "Streaming no disponible" in r.text
    assert "settleAfterTurn" in r.text
    assert "if (!started) settleAfterTurn" in r.text
    assert "activeAssistController" in r.text
    assert "cancelActiveAssist" in r.text
    assert "AbortController" in r.text
    assert "isAbortError" in r.text
    assert "prepareListeningTurn" in r.text
    assert "isDuplicateFinalTranscript" in r.text
    assert "voice: duplicate ignored" in r.text
    assert "isRecoverableMicError" in r.text
    assert "recoverFromMicError" in r.text
    assert "voice: retry after " in r.text
    assert "mic waiting · " in r.text
    assert "assistTimeoutMs" in r.text
    assert "showAssistTimeout" in r.text
    assert "events: timeout" in r.text
    assert "controller.signal" in r.text
    assert "suggestedActionPrompts" in r.text
    assert "renderSuggestedActions" in r.text
    assert "renderActiveContext" in r.text
    assert "extractContextSymbol" in r.text
    assert "currentTurnContext" in r.text
    assert "renderActiveContext(currentTurnContext(state, text))" in r.text
    assert "state.suggested_actions" in r.text
    assert "confirm_before_execution" in r.text
    assert "alert_draft" in r.text
    assert "show_trade_ticket" in r.text
    assert "ask_capabilities" in r.text
    assert "connect_realtime_voice" in r.text
    assert "data-prompt" in r.text
    assert 'data-prompt="estado de roxy"' in r.text
    assert 'data-prompt="resumen de sesion"' in r.text
    assert 'data-prompt="briefing diario"' in r.text
    assert 'data-prompt="resumen del mercado"' in r.text
    assert 'data-prompt="frescura de datos"' in r.text
    assert 'data-prompt="vigila mi watchlist"' in r.text
    assert 'data-prompt="analiza impacto de noticia: pega aqui el titular"' in r.text
    assert 'data-prompt="puedo operar ahora"' in r.text
    assert 'data-prompt="explica riesgo entrada stop target"' in r.text
    assert 'data-prompt="top oportunidades"' in r.text
    assert 'data-prompt="plan de monitoreo"' in r.text
    assert 'data-prompt="prepara alerta"' in r.text
    assert 'data-prompt="checklist de entrada"' in r.text
    assert 'data-prompt="tamaño de posicion con capital 10000 riesgo 0.5%"' in r.text
    assert "chat" in r.text
    assert "conversationMode" in r.text
    assert "Modo conversacion" in r.text
    assert "scheduleListen" in r.text
    assert "wakeMode" in r.text
    assert "wakeWord" in r.text
    assert "extractWakeCommand" in r.text
    assert "languageCommandTarget" in r.text
    assert "commandMatches" in r.text
    assert "localizedText" in r.text
    assert "speakLocalControlMessage" in r.text
    assert "applyVoiceLanguageCommand" in r.text
    assert "setVoiceModeState" in r.text
    assert "applyVoiceListeningModeCommand" in r.text
    assert "repeatLastReplyByVoice" in r.text
    assert "explainVoiceCommands" in r.text
    assert "voiceNewsHeadline" in r.text
    assert "newsVoicePrompt" in r.text
    assert "sendVoiceNewsPrompt" in r.text
    assert "voiceCommandSymbol" in r.text
    assert "voiceCommandSymbols" in r.text
    assert "normalizeVoiceSymbol" in r.text
    assert "withVoiceSymbol" in r.text
    assert "commandRemainder" in r.text
    assert "applyVoiceDefaultSymbol" in r.text
    assert "applyVoiceWatchlist" in r.text
    assert "handleVoiceProfileCommand" in r.text
    assert "marketVoicePrompt" in r.text
    assert "sendVoiceMarketPrompt" in r.text
    assert "handleVoiceControlCommand" in r.text
    assert "manualWakeCommand" in r.text
    assert "if (handleVoiceControlCommand(manualWakeCommand)) return;" in r.text
    assert r.text.index("const manualWakeCommand = extractWakeCommand(finalText);") < r.text.index(
        "if (handleVoiceControlCommand(finalText)) return;"
    )
    assert "voice: language " in r.text
    assert "voice: wake on" in r.text
    assert "voice: wake off" in r.text
    assert "voice: conversation on" in r.text
    assert "voice: conversation off" in r.text
    assert "voice: manual mode" in r.text
    assert "voice: repeat" in r.text
    assert "voice: help" in r.text
    assert "voice: news shortcut" in r.text
    assert "voice: market shortcut" in r.text
    assert "voice: profile symbol" in r.text
    assert "voice: profile watchlist" in r.text
    assert "English mode." in r.text
    assert "Modo español." in r.text
    assert "Roxy, modo Siri" in r.text
    assert "Roxy, Siri mode" in r.text
    assert "Roxy, modo conversación" in r.text
    assert "Roxy, conversation mode" in r.text
    assert "Modo Siri activo" in r.text
    assert "Conversation mode active" in r.text
    assert "Roxy, símbolo NVDA" in r.text
    assert "Roxy, symbol NVDA" in r.text
    assert "Roxy, watchlist SPY QQQ NVDA" in r.text
    assert "Default symbol updated to " in r.text
    assert "Watchlist updated: " in r.text
    assert "Roxy, noticia Tesla sube" in r.text
    assert "news impact Nvidia reports revenue" in r.text
    assert "analiza impacto de noticia: " in r.text
    assert "news impact: " in r.text
    assert "Roxy, mercado" in r.text
    assert "Roxy, market" in r.text
    assert "Roxy, riesgo de SPY" in r.text
    assert "Roxy, risk SPY" in r.text
    assert "BTC/USD" in r.text
    assert "top opportunities" in r.text
    assert "can I trade now" in r.text
    assert "Roxy, repite" in r.text
    assert "Roxy, repeat" in r.text
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
    assert "voiceStatus" in r.text
    assert "updateVoiceDiagnostics" in r.text
    assert "voiceMatchesLanguage" in r.text
    assert "alignVoiceSelection" in r.text
    assert "syncLanguageFromState" in r.text
    assert "const activeLanguage = syncLanguageFromState(state)" in r.text
    assert "function speechLang" in r.text
    assert "function chooseVoice(languageOverride)" in r.text
    assert 'speak(lastReply, state.language || $("language").value)' in r.text
    assert "preferredName" in r.text
    assert 'id="language"' in r.text
    assert "roxyLiveLanguage" in r.text
    assert '"user", "session", "apiKey", "language"' in r.text
    assert "parseWatchlist" in r.text
    assert "currentProfilePayload" in r.text
    assert "profile: currentProfilePayload()" in r.text
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
    assert payload["response_source"] == "local_brain"
    assert isinstance(payload["turn_id"], str)
    assert payload["server_latency_ms"] >= 0
    assert "reply" in payload


def test_assist_state_syncs_inline_profile_before_reply(monkeypatch):
    os.environ["VOICE_API_KEY"] = "testkey"
    from tools import voice_service

    calls = []
    monkeypatch.setattr(voice_service, "VOICE_API_KEY", "testkey")
    monkeypatch.setattr(voice_service, "llm", None)
    monkeypatch.setattr(
        voice_service.va_backend,
        "update_user_profile",
        lambda user, profile: calls.append(("profile", user, profile)) or profile,
    )
    monkeypatch.setattr(
        voice_service.va_backend,
        "generate_reply_state",
        lambda q, user=None, session_id=None: calls.append(("reply", user, session_id))
        or {
            "reply": "Perfil aplicado.",
            "intent": "profile_context",
            "voice_style": "female_es_latam",
            "should_speak": True,
            "needs_live_source": False,
            "safety_level": "normal",
            "suggested_actions": [],
        },
    )
    voice_service._RATE_STATE.clear()

    client = TestClient(voice_service.app)
    headers = {"Authorization": "Bearer testkey", "Content-Type": "application/json"}
    r = client.post(
        "/v1/assist/state",
        json={
            "query": "vigila mi watchlist",
            "user": "alice",
            "session_id": "profile-session",
            "profile": {"language": "en", "default_symbol": "SPY", "watchlist": ["SPY", "QQQ"]},
        },
        headers=headers,
    )

    assert r.status_code == 200
    assert r.json()["intent"] == "profile_context"
    assert calls[0] == ("profile", "alice", {"language": "en", "default_symbol": "SPY", "watchlist": ["SPY", "QQQ"]})
    assert calls[1] == ("reply", "alice", "profile-session")


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
            "active_context": {
                "active_intent": "opportunity",
                "active_symbol": "SPY",
                "active_topic": "resumen de oportunidad",
                "last_safety_level": "guarded",
                "needs_confirmation": False,
                "next_best_actions": ["trade_readiness", "monitoring_plan"],
            },
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
    assert payload["active_context"]["active_symbol"] == "SPY"


def test_assist_context_returns_compact_session_context(monkeypatch):
    os.environ["VOICE_API_KEY"] = "testkey"
    from tools import voice_service

    monkeypatch.setattr(voice_service, "VOICE_API_KEY", "testkey")
    monkeypatch.setattr(
        voice_service.va_backend,
        "get_session_state",
        lambda session_id, limit=8: {
            "session_id": session_id,
            "turn_count": 2,
            "last_intent": "trade_readiness",
            "last_safety_level": "critical",
            "active_context": {
                "active_intent": "trade_readiness",
                "active_symbol": "SPY",
                "active_topic": "puedo operar ahora",
                "last_safety_level": "critical",
                "needs_confirmation": True,
                "next_best_actions": ["show_risk_check", "show_trade_ticket"],
            },
            "recent_turns": [{"intent": "opportunity"}, {"intent": "trade_readiness"}],
        },
    )
    voice_service._RATE_STATE.clear()

    client = TestClient(voice_service.app)
    r = client.get("/v1/assist/context/demo-session", headers={"Authorization": "Bearer testkey"})

    assert r.status_code == 200
    payload = r.json()
    assert payload["session_id"] == "demo-session"
    assert payload["turn_count"] == 2
    assert "recent_turns" not in payload
    assert payload["active_context"]["active_symbol"] == "SPY"
    assert payload["active_context"]["needs_confirmation"] is True


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


def test_assist_stream_returns_sse_turn_events(monkeypatch):
    os.environ["VOICE_API_KEY"] = "testkey"
    from tools import voice_service

    monkeypatch.setattr(voice_service, "VOICE_API_KEY", "testkey")
    monkeypatch.setattr(voice_service, "llm", None)
    monkeypatch.setattr(
        voice_service.va_backend,
        "generate_reply_state",
        lambda q, user=None, session_id=None: {
            "reply": "Hola. Estoy escuchando.",
            "intent": "greeting",
            "language": "es",
            "voice_style": "female_es_latam",
            "avatar_state": "speaking",
            "emotion": "warm",
            "should_speak": True,
            "needs_live_source": False,
            "safety_level": "normal",
            "priority": "normal",
            "suggested_actions": ["ask_capabilities"],
        },
    )
    voice_service._RATE_STATE.clear()

    client = TestClient(voice_service.app)
    headers = {"Authorization": "Bearer testkey", "Content-Type": "application/json"}
    r = client.post("/v1/assist/stream", json={"query": "hola", "session_id": "demo"}, headers=headers)

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "event: transcript_received" in r.text
    assert "event: thinking" in r.text
    assert "event: reply_ready" in r.text
    assert "event: speak" in r.text
    assert "event: done" in r.text
    assert '"server_latency_ms"' in r.text
    assert '"response_source": "local_brain"' in r.text


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
            "memory": {
                "turn_count": 3,
                "active_context": {
                    "active_intent": "opportunity",
                    "active_symbol": "SPY",
                    "active_topic": "resumen de oportunidad",
                    "last_safety_level": "guarded",
                    "needs_confirmation": False,
                    "next_best_actions": ["trade_readiness", "monitoring_plan"],
                },
                "recent_turns": [],
            },
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
    assert payload["memory"]["active_context"]["active_symbol"] == "SPY"


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
