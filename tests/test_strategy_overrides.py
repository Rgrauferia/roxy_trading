from __future__ import annotations

import json

from strategy_overrides import apply_strategy_override_to_row, load_strategy_overrides


def test_load_strategy_overrides_returns_empty_when_missing(tmp_path):
    payload = load_strategy_overrides(tmp_path / "missing.json")

    assert payload["strategy_overrides"] == {}


def test_shadow_override_demotes_alert_to_watch():
    row = {
        "symbol": "AAPL",
        "strategy_family": "Pullback",
        "ai_action": "ALERT",
        "ai_score": 82,
        "alert_readiness_score": 78,
        "alert_blockers": [],
    }
    overrides = {
        "strategy_overrides": {
            "Pullback": {
                "action": "SHADOW_TEST",
                "mode": "PAPER_ONLY",
                "reason": "Autopilot necesita mas evidencia.",
                "max_position_scale": 0.0,
            }
        }
    }

    adjusted = apply_strategy_override_to_row(row, overrides)

    assert adjusted["ai_action"] == "WATCH"
    assert adjusted["alert_gate"] == "BLOCKED_BY_AUTOPILOT_SHADOW"
    assert adjusted["autopilot_override_action"] == "SHADOW_TEST"
    assert "mas evidencia" in adjusted["alert_blockers"][-1]


def test_tighten_filter_reduces_readiness():
    row = {
        "symbol": "AAPL",
        "strategy_family": "Canal lateral",
        "ai_action": "WATCH",
        "ai_score": 70,
        "alert_readiness_score": 75,
    }
    overrides = {
        "strategy_overrides": {
            "Canal lateral": {
                "action": "TIGHTEN_FILTER",
                "mode": "PAPER_ONLY",
                "min_readiness_delta": 10,
                "reason": "Stops altos.",
            }
        }
    }

    adjusted = apply_strategy_override_to_row(row, overrides)

    assert adjusted["alert_readiness_score"] == 65
    assert adjusted["alert_gate"] == "BLOCKED_BY_AUTOPILOT_FILTER"


def test_rolled_back_override_is_ignored():
    row = {
        "symbol": "AAPL",
        "strategy_family": "Pullback",
        "ai_action": "ALERT",
        "alert_readiness_score": 78,
    }
    overrides = {
        "strategy_overrides": {
            "Pullback": {
                "action": "SHADOW_TEST",
                "status": "ROLLED_BACK",
                "active": False,
                "reason": "Recovered.",
            }
        }
    }

    adjusted = apply_strategy_override_to_row(row, overrides)

    assert adjusted["ai_action"] == "ALERT"
    assert "autopilot_override_action" not in adjusted


def test_load_strategy_overrides_reads_json(tmp_path):
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps({"version": 1, "strategy_overrides": {"Pullback": {"action": "SHADOW_TEST"}}}))

    payload = load_strategy_overrides(path)

    assert payload["strategy_overrides"]["Pullback"]["action"] == "SHADOW_TEST"
