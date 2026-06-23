import json

from tools import voice_assistant


def test_voice_assistant_summarizes_latest_opportunity(tmp_path, monkeypatch):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "opportunities": [
                    {
                        "symbol": "AAPL",
                        "ai_action": "WATCH",
                        "strategy_family": "Canal alcista",
                        "trade_decision": "TRADE_FOR_2PCT",
                        "entry": 203.4,
                        "stop": 199.8,
                        "risk_pct": 0.0177,
                        "recommended_target_pct": 0.02,
                        "explanation": "SMA20 esta sobre SMA100.",
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(voice_assistant, "BRIEF_PATH", brief_path)

    reply = voice_assistant.generate_reply("explicame apple")

    assert "AAPL" in reply
    assert "Canal alcista" in reply
    assert "SMA20" in reply


def test_voice_assistant_summarizes_learning(tmp_path, monkeypatch):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "learning_profiles": [
                    {
                        "strategy_family": "Pullback",
                        "bias": "positive",
                        "alerts": 5,
                        "lesson": "Pullback esta funcionando mejor.",
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(voice_assistant, "BRIEF_PATH", brief_path)

    reply = voice_assistant.generate_reply("que estas aprendiendo")

    assert "Pullback" in reply
    assert "positive" in reply


def test_voice_assistant_summarizes_lab_queue(tmp_path, monkeypatch):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "strategy_lab": [
                    {
                        "strategy_family": "Canal lateral",
                        "lab_state": "Tighten filter",
                        "lab_decision": "Reducir alertas hasta mejorar volumen.",
                        "rule": "Volumen relativo >= 1.1.",
                        "experiment_rule": "Volumen relativo >= 1.1.",
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(voice_assistant, "BRIEF_PATH", brief_path)

    reply = voice_assistant.generate_reply("laboratorio")

    assert "Canal lateral" in reply
    assert "Volumen relativo" in reply


def test_voice_assistant_routes_position_sizing_to_roxy_brain(tmp_path, monkeypatch):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "opportunities": [
                    {
                        "symbol": "AAPL",
                        "signal": "WATCH",
                        "entry": 203.4,
                        "stop": 199.8,
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(voice_assistant, "BRIEF_PATH", brief_path)

    state = voice_assistant.generate_reply_state("tamaño de posicion AAPL con capital 10000 riesgo 0.5%", user="local")

    assert state["intent"] == "position_size"
    assert "AAPL tamaño de posicion" in state["reply"]
    assert "Cantidad 13" in state["reply"]


def test_voice_assistant_routes_account_status_to_roxy_brain(tmp_path, monkeypatch):
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(
        json.dumps(
            {
                "account_summary": {
                    "equity": 10000.0,
                    "buying_power": 5000.0,
                    "exposure": 7200.0,
                    "open_positions": 4,
                }
            }
        )
    )
    monkeypatch.setattr(voice_assistant, "BRIEF_PATH", brief_path)

    state = voice_assistant.generate_reply_state("estado de cuenta", user="local")

    assert state["intent"] == "account_status"
    assert "riesgo de exposicion agresivo" in state["reply"]
    assert "risk_review" in state["suggested_actions"]


def test_voice_assistant_spanish_session_brief_mentions_trading_handoff():
    payload = voice_assistant.session_brief_from_state(
        {
            "session_id": "trade-demo",
            "turn_count": 2,
            "last_intent": "trading_dashboard_handoff",
            "last_safety_level": "guarded",
            "active_context": {
                "active_intent": "trading_dashboard_handoff",
                "active_symbol": "NVDA",
                "active_market": "stock",
                "active_timeframe": "15m",
                "last_safety_level": "guarded",
                "needs_confirmation": False,
                "next_best_actions": ["trade_readiness", "monitoring_plan"],
                "action_url": "http://127.0.0.1:3000/?view=Activo&symbol=NVDA&market=stock&tf=15m",
                "action_label": "Abrir Roxy Trade",
                "action_kind": "local_trading_dashboard",
            },
        },
        language="es",
    )

    assert payload["language"] == "es"
    assert payload["action_url"].endswith("symbol=NVDA&market=stock&tf=15m")
    assert "Simbolo activo: NVDA" in payload["speakable_summary"]
    assert "Mercado: stock, marco: 15 minutos" in payload["speakable_summary"]
    assert "Handoff operativo listo: Abrir Roxy Trade" in payload["speakable_summary"]


def test_voice_assistant_session_overview_is_speakable():
    payload = voice_assistant.session_overview_from_memory(
        {
            "session_count": 2,
            "total_turns": 5,
            "recent_sessions": [
                {
                    "session_id": "scalping",
                    "turn_count": 3,
                    "last_intent": "trade_readiness",
                    "active_symbol": "NVDA",
                    "active_market": "stock",
                    "active_timeframe": "15m",
                    "action_url": "http://127.0.0.1:3000/?view=Activo&symbol=NVDA&market=stock&tf=15m",
                },
                {"session_id": "earnings", "turn_count": 2, "last_intent": "market_summary"},
            ],
        },
        language="en",
    )

    assert payload["language"] == "en"
    assert payload["session_count"] == 2
    assert payload["recent_sessions"][0]["session_id"] == "scalping"
    assert "Recent sessions: scalping: 3 turn(s), NVDA stock 15 minutes, last topic trade_readiness" in payload[
        "speakable_summary"
    ]
    assert "trade handoff ready" in payload["speakable_summary"]
    assert "Roxy, switch session to scalping" in payload["speakable_summary"]
    assert payload["suggested_actions"] == ["switch_session", "session_brief"]


def test_voice_assistant_speakable_timeframe_expands_trading_shorthand():
    assert voice_assistant.speakable_timeframe("15m", "es") == "15 minutos"
    assert voice_assistant.speakable_timeframe("1m", "es") == "1 minuto"
    assert voice_assistant.speakable_timeframe("2h", "es") == "2 horas"
    assert voice_assistant.speakable_timeframe("15m", "en") == "15 minutes"
    assert voice_assistant.speakable_timeframe("1h", "en") == "1 hour"


def test_voice_assistant_speakable_trading_text_expands_compact_timeframes():
    text = "Falta 15m a la entrada, wait 2H4h valida, datos 30min."

    spoken = voice_assistant.speakable_trading_text(text, "es")

    assert "15 minutos a la entrada" in spoken
    assert "2 horas / 4 horas valida" in spoken
    assert "30 minutos" in spoken
    assert "15m" not in spoken
    assert "2H4h" not in spoken
