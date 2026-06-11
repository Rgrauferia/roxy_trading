import json

from tools.roxy_interactive_brain import (
    RoxyConversationMemory,
    RoxyFeedbackMemory,
    RoxyInteractiveBrain,
    RoxyUserProfile,
    build_voice_events,
    list_knowledge_sources,
)


def test_roxy_brain_identity_defines_female_voice_and_guardrails(tmp_path):
    brain = RoxyInteractiveBrain(brief_path=tmp_path / "brief.json", memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("como debe ser tu rostro y voz")

    assert response.intent == "identity"
    assert response.voice_style == "female_es_latam"
    assert response.avatar_state == "speaking"
    assert response.emotion == "professional"
    assert response.safety_level == "guarded"
    assert "voz femenina" in response.reply
    assert "confirmacion" in response.reply


def test_roxy_brain_does_not_invent_news_without_source(tmp_path):
    brain = RoxyInteractiveBrain(brief_path=tmp_path / "brief.json", memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("dime las noticias del mercado hoy")

    assert response.intent == "news_unavailable"
    assert response.needs_live_source is True
    assert "no voy a inventarlos" in response.reply


def test_roxy_brain_reads_latest_opportunity_from_brief(tmp_path):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "opportunities": [
                    {
                        "symbol": "NVDA",
                        "ai_action": "WATCH",
                        "strategy_family": "Pullback",
                        "trade_decision": "WAIT_15M_ENTRY",
                        "entry": 142.25,
                        "stop": 139.5,
                        "risk_pct": 0.0193,
                        "recommended_target_pct": 0.02,
                        "explanation": "Falta confirmacion de volumen.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    brain = RoxyInteractiveBrain(brief_path=brief_path, memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("recomienda nvda")

    assert response.intent == "opportunity"
    assert response.safety_level == "guarded"
    assert "NVDA" in response.reply
    assert "Pullback" in response.reply
    assert "Falta confirmacion" in response.reply


def test_roxy_brain_remembers_session_context(tmp_path):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "opportunities": [
                    {
                        "symbol": "SPY",
                        "ai_action": "WATCH",
                        "strategy_family": "Trend",
                        "trade_decision": "WAIT",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    memory = RoxyConversationMemory(path=tmp_path / "conversation.json")
    brain = RoxyInteractiveBrain(
        brief_path=brief_path,
        memory_path=tmp_path / "memory.json",
        conversation_memory=memory,
    )

    first = brain.generate_reply("resumen de oportunidad", session_id="demo")
    second = brain.generate_reply("y el riesgo?", session_id="demo")

    assert first.intent == "opportunity"
    assert second.intent == "followup"
    assert "oportunidad anterior" in second.reply


def test_roxy_brain_redacts_secrets_in_memory(tmp_path):
    memory_path = tmp_path / "conversation.json"
    memory = RoxyConversationMemory(path=memory_path)
    brain = RoxyInteractiveBrain(
        brief_path=tmp_path / "brief.json",
        memory_path=tmp_path / "memory.json",
        conversation_memory=memory,
    )

    brain.generate_reply("mi secret=abcdefghijklmnopqrstuvwxyz1234567890", session_id="demo")

    saved = memory_path.read_text(encoding="utf-8")
    assert "abcdefghijklmnopqrstuvwxyz1234567890" not in saved
    assert "[redacted]" in saved


def test_roxy_brain_requires_confirmation_for_sensitive_actions(tmp_path):
    brain = RoxyInteractiveBrain(brief_path=tmp_path / "brief.json", memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("compra ahora NVDA en real")

    assert response.intent == "action_confirmation_required"
    assert response.avatar_state == "blocked"
    assert response.emotion == "serious"
    assert response.safety_level == "critical"
    assert response.priority == "high"
    assert "confirmacion explicita" in response.reply
    assert "require_explicit_confirmation" in response.suggested_actions
    events = build_voice_events("compra ahora NVDA en real", response)
    assert events[-1]["type"] == "action_confirmation_required"


def test_roxy_reply_state_includes_visual_contract(tmp_path):
    brain = RoxyInteractiveBrain(brief_path=tmp_path / "brief.json", memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("hola")
    payload = response.as_dict()

    assert payload["voice_style"] == "female_es_latam"
    assert payload["avatar_state"] == "speaking"
    assert payload["emotion"] == "warm"
    assert payload["priority"] == "normal"


def test_roxy_voice_events_include_speak_event(tmp_path):
    brain = RoxyInteractiveBrain(brief_path=tmp_path / "brief.json", memory_path=tmp_path / "memory.json")
    response = brain.generate_reply("hola")

    events = build_voice_events("hola", response)

    assert [event["type"] for event in events[:4]] == [
        "transcript_received",
        "thinking",
        "reply_ready",
        "speak",
    ]
    assert events[-1]["voice_style"] == "female_es_latam"


def test_roxy_brain_reads_local_knowledge_source(tmp_path):
    knowledge_path = tmp_path / "manual.md"
    knowledge_path.write_text(
        "# Manual Roxy\n\nRoxy Trading usa memoria, brief local y reglas de seguridad para explicar senales.",
        encoding="utf-8",
    )
    brain = RoxyInteractiveBrain(
        brief_path=tmp_path / "brief.json",
        memory_path=tmp_path / "memory.json",
        knowledge_paths=(knowledge_path,),
    )

    response = brain.generate_reply("lee el manual de memoria y seguridad")

    assert response.intent == "knowledge"
    assert response.emotion == "informative"
    assert "manual.md" in response.reply
    assert "memoria" in response.reply


def test_list_knowledge_sources_reports_existing_files(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("Roxy source", encoding="utf-8")

    sources = list_knowledge_sources((source, tmp_path / "missing.md"))

    assert sources[0]["exists"] is True
    assert sources[0]["size_bytes"] > 0
    assert sources[1]["exists"] is False


def test_roxy_user_profile_updates_are_sanitized(tmp_path):
    profile = RoxyUserProfile(path=tmp_path / "profile.json")

    saved = profile.update(
        "local",
        {
            "preferred_name": "Roberto",
            "watchlist": "spy, qqq, nvda, tokensecretabcdefghijklmnopqrstuvwxyz123",
            "api_key": "should-not-save",
            "voice_rate": 9,
        },
    )

    assert saved["preferred_name"] == "Roberto"
    assert "api_key" not in saved
    assert saved["voice_rate"] == 1.5
    assert saved["watchlist"] == ["SPY", "QQQ", "NVDA"]


def test_roxy_brain_uses_preferred_name_and_watchlist(tmp_path):
    profile = RoxyUserProfile(path=tmp_path / "profile.json")
    profile.update("local", {"preferred_name": "Roberto", "watchlist": ["SPY", "QQQ"]})
    brain = RoxyInteractiveBrain(
        brief_path=tmp_path / "brief.json",
        memory_path=tmp_path / "memory.json",
        user_profile=profile,
    )

    greeting = brain.generate_reply("hola", user="local")
    capabilities = brain.generate_reply("que puedes hacer", user="local")

    assert "Hola Roberto" in greeting.reply
    assert "SPY, QQQ" in capabilities.reply


def test_roxy_feedback_memory_records_and_summarizes(tmp_path):
    feedback = RoxyFeedbackMemory(path=tmp_path / "feedback.json")

    feedback.record({"rating": "up", "user": "local", "intent": "greeting", "query": "hola", "reply": "Hola"})
    feedback.record(
        {"rating": "down", "user": "local", "intent": "opportunity", "query": "api_key=secret123", "reply": "x"}
    )

    summary = feedback.summary(user="local")

    assert summary["total"] == 2
    assert summary["up"] == 1
    assert summary["down"] == 1
    assert summary["top_intents"][0]["intent"] == "opportunity"
    assert "secret123" not in json.dumps(summary)


def test_roxy_brain_reports_feedback_learning(tmp_path):
    feedback = RoxyFeedbackMemory(path=tmp_path / "feedback.json")
    feedback.record({"rating": "up", "user": "local", "intent": "capabilities", "query": "q", "reply": "r"})
    brain = RoxyInteractiveBrain(
        brief_path=tmp_path / "brief.json",
        memory_path=tmp_path / "memory.json",
        feedback_memory=feedback,
    )

    response = brain.generate_reply("que aprendiste del feedback", user="local")

    assert response.intent == "feedback_learning"
    assert "1 feedback" in response.reply
    assert "capabilities" in response.reply
