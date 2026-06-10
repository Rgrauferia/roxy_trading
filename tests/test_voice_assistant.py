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
