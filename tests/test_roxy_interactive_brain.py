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


def test_roxy_brain_summarizes_market_regime_in_spanish(tmp_path):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "alert_gate_summary": {
                    "total_opportunities": 2,
                    "watch_count": 2,
                    "ready_ratio": 0.0,
                    "top_gate_label": "Esperar entrada 15m",
                    "top_readiness": 73.7,
                },
                "daily_opportunity_plan": {
                    "market_counts": {"crypto": 2},
                    "market_session": {"stock_session": "After-hours", "crypto_session": "24h"},
                    "opportunities": [
                        {
                            "symbol": "BTC/USD",
                            "signal": "WATCH",
                            "mtf_explanation": "Lectura actual ALCISTA/canal alcista corto plazo",
                            "readiness": 73.7,
                        },
                        {
                            "symbol": "ETH/USD",
                            "signal": "WATCH",
                            "trend_setup": "PULLBACK",
                            "readiness": 68.0,
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    brain = RoxyInteractiveBrain(brief_path=brief_path, memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("resumen del mercado")

    assert response.intent == "market_summary"
    assert response.language == "es"
    assert response.safety_level == "guarded"
    assert "Regimen local del mercado: alcista" in response.reply
    assert "Nota de riesgo" in response.reply


def test_roxy_brain_summarizes_market_regime_in_english(tmp_path):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "alert_gate_summary": {
                    "total_opportunities": 1,
                    "watch_count": 1,
                    "ready_ratio": 0.25,
                    "top_gate_label": "Esperar entrada 15m",
                    "top_readiness": 80,
                },
                "daily_opportunity_plan": {
                    "market_counts": {"stock": 1},
                    "market_session": {"stock_session": "Regular", "crypto_session": "24h"},
                    "opportunities": [
                        {"symbol": "SPY", "signal": "WATCH", "trend_setup": "TREND_CONTINUATION", "trend_score": 82}
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    brain = RoxyInteractiveBrain(brief_path=brief_path, memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("market trend")

    assert response.intent == "market_summary"
    assert response.language == "en"
    assert response.voice_style == "female_en_us"
    assert "Local market regime: bullish" in response.reply
    assert "top gate Wait for 15m entry" in response.reply
    assert "Risk note" in response.reply


def test_roxy_brain_generates_daily_briefing_in_spanish(tmp_path):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "alert_gate_summary": {
                    "alert_count": 0,
                    "total_opportunities": 1,
                    "watch_count": 1,
                    "ready_ratio": 0.0,
                    "top_gate_label": "Esperar entrada 15m",
                    "top_readiness": 70,
                },
                "daily_opportunity_plan": {
                    "generated_at": "2026-06-12T20:40:00+00:00",
                    "alert_policy": "Solo alertar con checklist completo.",
                    "market_counts": {"crypto": 1},
                    "market_session": {"local_time": "2026-06-12 16:40", "stock_session": "After-hours", "crypto_session": "24h"},
                    "opportunities": [
                        {
                            "symbol": "BTC/USD",
                            "signal": "WATCH",
                            "decision": "Esperar",
                            "entry": 63510.94,
                            "stop": 62564.50,
                            "risk_pct": 0.0149,
                            "readiness": 70,
                            "what_is_missing": "15m da entrada: WAIT",
                            "mtf_explanation": "Lectura actual ALCISTA",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    brain = RoxyInteractiveBrain(brief_path=brief_path, memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("briefing diario")

    assert response.intent == "daily_briefing"
    assert response.language == "es"
    assert "Briefing diario" in response.reply
    assert "Regimen local del mercado" in response.reply
    assert "Top watch: BTC/USD" in response.reply
    assert "riesgo 1.49%" in response.reply
    assert "no ejecutar sin confirmacion explicita" in response.reply


def test_roxy_brain_generates_daily_briefing_in_english(tmp_path):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "alert_gate_summary": {
                    "alert_count": 0,
                    "total_opportunities": 1,
                    "watch_count": 1,
                    "ready_ratio": 0.0,
                    "top_gate_label": "Esperar entrada 15m",
                    "top_readiness": 70,
                },
                "daily_opportunity_plan": {
                    "generated_at": "2026-06-12T20:40:00+00:00",
                    "alert_policy": "Solo alertar cuando 1h confirma, 15m da entrada, volumen acompana, riesgo es bajo y target 2% es viable.",
                    "market_counts": {"crypto": 1},
                    "market_session": {"local_time": "2026-06-12 16:40", "stock_session": "After-hours", "crypto_session": "24h"},
                    "opportunities": [
                        {
                            "symbol": "BTC/USD",
                            "signal": "WATCH",
                            "decision": "Esperar",
                            "entry": 63510.94,
                            "stop": 62564.50,
                            "risk_pct": 0.0149,
                            "readiness": 70,
                            "what_is_missing": "15m da entrada: WAIT",
                            "mtf_explanation": "Bullish watch",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    brain = RoxyInteractiveBrain(brief_path=brief_path, memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("daily briefing")

    assert response.intent == "daily_briefing"
    assert response.language == "en"
    assert response.voice_style == "female_en_us"
    assert "Daily briefing" in response.reply
    assert "Local market regime" in response.reply
    assert "Top watch: BTC/USD" in response.reply
    assert "risk 1.49%" in response.reply
    assert "Policy: Only alert when 1h confirms" in response.reply
    assert "Solo alertar" not in response.reply
    assert ".." not in response.reply
    assert "do not execute without explicit confirmation" in response.reply


def test_roxy_brain_explains_opportunity_risk_plan_in_spanish(tmp_path):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "daily_opportunity_plan": {
                    "opportunities": [
                        {
                            "symbol": "BTC/USD",
                            "signal": "WATCH",
                            "decision": "Esperar",
                            "entry": 63510.94,
                            "stop": 62564.50,
                            "risk_pct": 0.0149,
                            "target_2": 64781.15,
                            "target_5": 66686.48,
                            "target_10": 69862.03,
                            "entry_trigger": "Esperar gatillo BUY en 15m mientras 1h sigue valido.",
                            "invalidation": "Invalidar si pierde 62564.50.",
                            "what_is_missing": "15m da entrada: WAIT | Volumen acompana: falta volumen",
                            "why": "No operar todavia.",
                            "readiness": 68.4,
                            "probability": 69,
                            "quality": "C",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    brain = RoxyInteractiveBrain(brief_path=brief_path, memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("explica riesgo de BTC")

    assert response.intent == "opportunity_risk"
    assert response.language == "es"
    assert response.safety_level == "guarded"
    assert "BTC/USD plan de riesgo" in response.reply
    assert "entrada 63510.94" in response.reply
    assert "stop 62564.50" in response.reply
    assert "riesgo 1.49%" in response.reply
    assert "Falta: 15m da entrada: WAIT" in response.reply
    assert "requiere confirmacion" in response.reply


def test_roxy_brain_matches_crypto_base_symbol_for_risk_plan(tmp_path):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "daily_opportunity_plan": {
                    "opportunities": [
                        {"symbol": "SOL/USD", "signal": "WATCH", "entry": 66.67, "stop": 65.92},
                        {"symbol": "BTC/USD", "signal": "WATCH", "entry": 63510.94, "stop": 62564.50},
                        {"symbol": "ETH/USD", "signal": "WATCH", "entry": 1666.28, "stop": 1632.20},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    brain = RoxyInteractiveBrain(brief_path=brief_path, memory_path=tmp_path / "memory.json")

    btc = brain.generate_reply("explain risk BTC")
    eth = brain.generate_reply("explain risk ETH-USD")

    assert "BTC/USD risk plan" in btc.reply
    assert "entry 63510.94" in btc.reply
    assert "ETH/USD risk plan" in eth.reply
    assert "entry 1666.28" in eth.reply


def test_roxy_brain_explains_opportunity_risk_plan_in_english(tmp_path):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "daily_opportunity_plan": {
                    "opportunities": [
                        {
                            "symbol": "NVDA",
                            "signal": "WATCH",
                            "decision": "Esperar",
                            "entry": 142.25,
                            "stop": 139.5,
                            "risk_pct": 0.0193,
                            "target_2": 145.09,
                            "target_5": 149.36,
                            "target_10": 156.48,
                            "entry_trigger": "Esperar gatillo BUY en 15m mientras 1h sigue valido.",
                            "invalidation": "Invalidar si pierde 139.50.",
                            "what_is_missing": "15m da entrada: WAIT | Volumen acompana: falta volumen",
                            "why": "No operar todavia: faltan condiciones importantes del checklist.",
                            "readiness": 72,
                            "probability": 65,
                            "quality": "B",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    brain = RoxyInteractiveBrain(brief_path=brief_path, memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("explain risk entry stop target NVDA")

    assert response.intent == "opportunity_risk"
    assert response.language == "en"
    assert response.voice_style == "female_en_us"
    assert "NVDA risk plan" in response.reply
    assert "entry 142.25" in response.reply
    assert "risk 1.93%" in response.reply
    assert "decision Wait" in response.reply
    assert "Trigger: Wait for a 15m BUY trigger while 1h remains valid." in response.reply
    assert "Missing: 15m entry: WAIT | Volume confirms: missing volume" in response.reply
    assert ".." not in response.reply
    assert "not an execution order" in response.reply


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
    assert second.intent == "opportunity_risk"
    assert "SPY plan de riesgo" in second.reply


def test_roxy_conversation_memory_prunes_old_sessions(tmp_path):
    memory_path = tmp_path / "conversation.json"
    memory = RoxyConversationMemory(path=memory_path, max_turns=2, max_sessions=2)
    reply = RoxyInteractiveBrain(brief_path=tmp_path / "brief.json", memory_path=tmp_path / "memory.json").generate_reply(
        "hola"
    )

    memory.append("session-a", "hola", reply)
    memory.append("session-b", "hola", reply)
    memory.append("session-c", "hola", reply)

    saved = json.loads(memory_path.read_text(encoding="utf-8"))
    sessions = saved["sessions"]
    assert len(sessions) == 2
    assert "session-c" in sessions
    assert "session-b" in sessions
    assert "session-a" not in sessions


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

    assert payload["language"] == "es"
    assert payload["voice_style"] == "female_es_latam"
    assert payload["avatar_state"] == "speaking"
    assert payload["emotion"] == "warm"
    assert payload["priority"] == "normal"


def test_roxy_brain_answers_core_prompts_in_english(tmp_path):
    brain = RoxyInteractiveBrain(brief_path=tmp_path / "brief.json", memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("what can you do")

    assert response.intent == "capabilities"
    assert response.language == "en"
    assert response.voice_style == "female_en_us"
    assert "I can hold a natural conversation" in response.reply
    assert "Puedo" not in response.reply


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
            "language": "English",
            "voice_rate": 9,
        },
    )

    assert saved["preferred_name"] == "Roberto"
    assert "api_key" not in saved
    assert saved["language"] == "en"
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


def test_roxy_brain_uses_profile_language_preference(tmp_path):
    profile = RoxyUserProfile(path=tmp_path / "profile.json")
    profile.update("local", {"preferred_name": "Roberto", "language": "en"})
    brain = RoxyInteractiveBrain(
        brief_path=tmp_path / "brief.json",
        memory_path=tmp_path / "memory.json",
        user_profile=profile,
    )

    response = brain.generate_reply("hola", user="local")

    assert response.language == "en"
    assert response.voice_style == "female_en_us"
    assert response.reply.startswith("Hi Roberto")


def test_roxy_brain_reports_autonomy_status_without_symbol_confusion(tmp_path):
    profile = RoxyUserProfile(path=tmp_path / "profile.json")
    profile.update("local", {"preferred_name": "Roberto"})
    feedback = RoxyFeedbackMemory(path=tmp_path / "feedback.json")
    feedback.record({"rating": "down", "user": "local", "intent": "capabilities"})
    memory = RoxyConversationMemory(path=tmp_path / "conversation.json")
    brain = RoxyInteractiveBrain(
        brief_path=tmp_path / "brief.json",
        memory_path=tmp_path / "memory.json",
        conversation_memory=memory,
        user_profile=profile,
        feedback_memory=feedback,
    )
    brain.generate_reply("hola", user="local", session_id="demo")

    response = brain.generate_reply("estado", user="local", session_id="demo")

    assert response.intent == "autonomy_status"
    assert response.avatar_state == "ready"
    assert response.safety_level == "guarded"
    assert "Estoy activa Roberto" in response.reply
    assert "Feedback aprendido" in response.reply
    assert "enable_wake_roxy" in response.suggested_actions
    assert "ESTADO:" not in response.reply


def test_roxy_brain_reports_english_autonomy_status(tmp_path):
    brain = RoxyInteractiveBrain(brief_path=tmp_path / "brief.json", memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("status roxy", user="local", session_id="demo")

    assert response.intent == "autonomy_status"
    assert response.language == "en"
    assert "I'm active" in response.reply
    assert "guardrails are on" in response.reply


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


def test_roxy_feedback_memory_returns_intent_guidance(tmp_path):
    feedback = RoxyFeedbackMemory(path=tmp_path / "feedback.json")

    feedback.record({"rating": "down", "user": "local", "intent": "opportunity", "note": "mas corto"})
    feedback.record({"rating": "up", "user": "local", "intent": "capabilities"})

    guidance = feedback.guidance_for_intent("opportunity", user="local")

    assert guidance["total"] == 1
    assert guidance["down"] == 1
    assert guidance["needs_adjustment"] is True
    assert guidance["latest_note"] == "mas corto"


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


def test_roxy_brain_applies_negative_feedback_to_next_same_intent(tmp_path):
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
    feedback = RoxyFeedbackMemory(path=tmp_path / "feedback.json")
    feedback.record(
        {
            "rating": "down",
            "user": "local",
            "intent": "opportunity",
            "query": "resumen",
            "reply": "demasiado largo",
            "note": "mas directo",
        }
    )
    brain = RoxyInteractiveBrain(
        brief_path=brief_path,
        memory_path=tmp_path / "memory.json",
        feedback_memory=feedback,
    )

    response = brain.generate_reply("resumen de oportunidad", user="local")

    assert response.intent == "opportunity"
    assert response.reply.startswith("Ajuste por tu feedback")
    assert "mas directo" in response.reply
    assert "feedback_adjusted" in response.suggested_actions


def test_roxy_brain_reads_opportunity_in_english(tmp_path):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "opportunities": [
                    {
                        "symbol": "NVDA",
                        "ai_action": "WATCH",
                        "strategy_family": "Pullback",
                        "trade_decision": "WAIT",
                        "entry": 142.25,
                        "stop": 139.5,
                        "risk_pct": 0.0193,
                        "recommended_target_pct": 0.02,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    brain = RoxyInteractiveBrain(brief_path=brief_path, memory_path=tmp_path / "memory.json")

    response = brain.generate_reply("recommend NVDA")

    assert response.intent == "opportunity"
    assert response.language == "en"
    assert response.voice_style == "female_en_us"
    assert "Entry 142.25" in response.reply
    assert "risk 1.93%" in response.reply


def test_roxy_learning_snapshot_combines_profile_feedback_memory_and_sources(tmp_path):
    profile = RoxyUserProfile(path=tmp_path / "profile.json")
    profile.update("local", {"preferred_name": "Roberto", "watchlist": ["SPY"]})
    feedback = RoxyFeedbackMemory(path=tmp_path / "feedback.json")
    feedback.record({"rating": "down", "user": "local", "intent": "opportunity", "note": "mas claro"})
    memory = RoxyConversationMemory(path=tmp_path / "conversation.json")
    knowledge_path = tmp_path / "manual.md"
    knowledge_path.write_text("Manual Roxy", encoding="utf-8")
    brain = RoxyInteractiveBrain(
        brief_path=tmp_path / "brief.json",
        memory_path=tmp_path / "memory.json",
        conversation_memory=memory,
        user_profile=profile,
        feedback_memory=feedback,
        knowledge_paths=(knowledge_path,),
    )
    brain.generate_reply("hola", user="local", session_id="demo")

    snapshot = brain.learning_snapshot(user="local", session_id="demo")

    assert snapshot["status"] == "learning"
    assert snapshot["profile"]["preferred_name"] == "Roberto"
    assert snapshot["feedback"]["down"] == 1
    assert snapshot["memory"]["turn_count"] == 1
    assert snapshot["knowledge_sources"][0]["exists"] is True
    assert any("feedback negativo" in item for item in snapshot["recommendations"])
