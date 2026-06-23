from __future__ import annotations

import json

import roxy_autopilot


def test_autopilot_builds_paper_only_strategy_proposal():
    memory = {
        "strategy_stats": {
            "Canal lateral": {
                "seen": 12,
                "alerts": 5,
                "hit_2pct": 0,
                "hit_5pct": 0,
                "hit_10pct": 0,
                "stops": 4,
            }
        },
        "signal_journal": [],
    }

    proposals = roxy_autopilot.build_improvement_proposals(memory)

    assert proposals
    first = proposals[0]
    assert first["type"] == "strategy_override"
    assert first["safety_mode"] == "PAPER_ONLY"
    assert first["override"]["action"] == "TIGHTEN_FILTER"
    assert first["override"]["max_position_scale"] == 0.0


def test_autopilot_deduplicates_strategy_proposals(monkeypatch):
    monkeypatch.setattr(
        roxy_autopilot,
        "autonomous_learning_plan",
        lambda memory: [
            {
                "strategy_family": "Pullback",
                "action": "SHADOW_TEST_WAIT_VOLUME",
                "why": "volume",
                "evidence_score": 0,
            },
            {
                "strategy_family": "Pullback",
                "action": "SHADOW_TEST_WAIT_CONFIRMATION",
                "why": "confirmation",
                "evidence_score": 0,
            },
        ],
    )

    proposals = roxy_autopilot.build_improvement_proposals({"strategy_stats": {}, "signal_journal": []})

    assert len(proposals) == 1
    assert proposals[0]["id"] == "shadow_test_pullback"


def test_autopilot_does_not_apply_without_code_write_flag():
    proposals = [
        {
            "id": "tighten_filter_pullback",
            "type": "strategy_override",
            "override": {"strategy_family": "Pullback", "action": "TIGHTEN_FILTER"},
        }
    ]

    applied = roxy_autopilot.apply_proposals(proposals, env={})

    assert applied[0]["applied"] is False
    assert roxy_autopilot.CODE_WRITE_ENV in applied[0]["reason"]


def test_autopilot_applies_only_strategy_override_when_enabled(tmp_path, monkeypatch):
    target = tmp_path / "roxy_strategy_overrides.json"
    monkeypatch.setattr(roxy_autopilot, "STRATEGY_OVERRIDES_PATH", target)
    proposal = {
        "id": "tighten_filter_pullback",
        "type": "strategy_override",
        "override": {
            "strategy_family": "Pullback",
            "action": "TIGHTEN_FILTER",
            "mode": "PAPER_ONLY",
            "max_position_scale": 0.0,
        },
    }

    applied = roxy_autopilot.apply_proposals([proposal], env={roxy_autopilot.CODE_WRITE_ENV: "1"})

    assert applied[0]["applied"] is True
    payload = json.loads(target.read_text())
    override = payload["strategy_overrides"]["Pullback"]
    assert override["action"] == "TIGHTEN_FILTER"
    assert override["mode"] == "PAPER_ONLY"
    assert override["max_position_scale"] == 0.0
    assert override["proposal_id"] == "tighten_filter_pullback"


def test_autopilot_skips_already_active_override(tmp_path, monkeypatch):
    target = tmp_path / "roxy_strategy_overrides.json"
    target.write_text(
        json.dumps(
            {
                "version": 1,
                "strategy_overrides": {
                    "Pullback": {
                        "strategy_family": "Pullback",
                        "action": "SHADOW_TEST",
                        "status": "ACTIVE",
                        "active": True,
                        "proposal_id": "shadow_test_pullback",
                    }
                },
            }
        )
    )
    monkeypatch.setattr(roxy_autopilot, "STRATEGY_OVERRIDES_PATH", target)
    proposal = {
        "id": "shadow_test_pullback",
        "type": "strategy_override",
        "override": {
            "strategy_family": "Pullback",
            "action": "SHADOW_TEST",
            "status": "ACTIVE",
            "active": True,
        },
    }

    applied = roxy_autopilot.apply_proposals([proposal], env={roxy_autopilot.CODE_WRITE_ENV: "1"})

    assert applied[0]["applied"] is False
    assert applied[0]["reason"] == "override already active"
    assert not list(tmp_path.glob("*.bak.*"))


def test_autopilot_report_keeps_real_money_disabled(monkeypatch):
    monkeypatch.setattr(roxy_autopilot, "build_health_snapshot", lambda: {"status": "OK", "issues": []})
    monkeypatch.setattr(roxy_autopilot, "write_proposal_files", lambda proposals: [])
    monkeypatch.setattr(
        roxy_autopilot,
        "build_improvement_proposals",
        lambda memory, **kwargs: [
            {
                "id": "collect_more_signal_data",
                "type": "learning_task",
                "status": "WAITING_FOR_DATA",
                "safety_mode": "PAPER_ONLY",
            }
        ],
    )

    report = roxy_autopilot.build_autopilot_report(memory={}, apply=False, env={roxy_autopilot.CODE_WRITE_ENV: "1"})

    assert report["paper_only"] is True
    assert report["live_orders_allowed"] is False
    assert report["guardrails"]["real_money_trading"] == "DISABLED"
    assert report["code_write_enabled"] is True


def test_autoheal_needed_targets_detects_stale_and_missing_files():
    health = {
        "files": [
            {"name": "roxy_ai_brief", "status": "STALE", "age_seconds": 700, "max_age_seconds": 300},
            {"name": "alert_quality", "status": "WARN", "age_seconds": 200, "max_age_seconds": 300},
            {"name": "chart_realtime_health", "status": "FAIL", "age_seconds": None, "max_age_seconds": 300},
        ]
    }

    targets = roxy_autopilot.autoheal_needed_targets(health)

    assert targets == ["roxy_ai_brief", "chart_realtime_health"]


def test_autoheal_stale_reports_can_skip_when_disabled():
    health = {
        "files": [
            {"name": "roxy_ai_brief", "status": "STALE", "age_seconds": 700, "max_age_seconds": 300},
        ]
    }

    actions = roxy_autopilot.autoheal_stale_reports(health, enabled=False)

    assert actions[0]["status"] == "SKIPPED"
    assert "roxy_ai_watch.py" in " ".join(actions[0]["command"])


def test_run_autoheal_command_uses_allowlisted_command(monkeypatch):
    calls = []

    class Result:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(command, cwd, text, capture_output, timeout):
        calls.append(
            {
                "command": command,
                "cwd": cwd,
                "text": text,
                "capture_output": capture_output,
                "timeout": timeout,
            }
        )
        return Result()

    monkeypatch.setattr(roxy_autopilot.subprocess, "run", fake_run)
    monkeypatch.setattr(roxy_autopilot, "autopilot_python_path", lambda: "/tmp/python")

    action = roxy_autopilot.run_autoheal_command("alert_quality", timeout_seconds=12)

    assert action["ok"] is True
    assert action["status"] == "OK"
    assert calls[0]["command"] == ["/tmp/python", str(roxy_autopilot.project_path("alert_quality.py"))]
    assert calls[0]["timeout"] == 12


def test_override_review_recommends_rollback_for_good_shadow_signals():
    memory = {
        "signal_journal": [
            {"strategy_family": "Pullback", "status": "HIT_2PCT", "milestones": ["2%"]},
            {"strategy_family": "Pullback", "status": "HIT_5PCT", "milestones": ["2%", "5%"]},
            {"strategy_family": "Pullback", "status": "OPEN", "milestones": ["2%"]},
        ]
    }
    override = {"action": "SHADOW_TEST", "status": "ACTIVE", "active": True}

    review = roxy_autopilot.review_override_row("Pullback", override, memory)

    assert review["recommendation"] == "ROLLBACK"
    assert review["next_status"] == "ROLLBACK_READY"
    assert review["metrics"]["hit_2_rate"] == 1.0


def test_override_review_confirms_filter_for_bad_shadow_signals():
    memory = {
        "signal_journal": [
            {"strategy_family": "Canal lateral", "status": "STOP"},
            {"strategy_family": "Canal lateral", "status": "STOP"},
            {"strategy_family": "Canal lateral", "status": "STOP"},
        ]
    }
    override = {"action": "TIGHTEN_FILTER", "status": "ACTIVE", "active": True}

    review = roxy_autopilot.review_override_row("Canal lateral", override, memory)

    assert review["recommendation"] == "KEEP_FILTER"
    assert review["next_status"] == "CONFIRMED_FILTER"


def test_apply_override_rollbacks_requires_code_write_flag(tmp_path, monkeypatch):
    target = tmp_path / "roxy_strategy_overrides.json"
    target.write_text(
        json.dumps(
            {
                "version": 1,
                "strategy_overrides": {
                    "Pullback": {"action": "SHADOW_TEST", "status": "ACTIVE", "active": True}
                },
            }
        )
    )
    memory = {
        "signal_journal": [
            {"strategy_family": "Pullback", "status": "HIT_2PCT", "milestones": ["2%"]},
            {"strategy_family": "Pullback", "status": "HIT_2PCT", "milestones": ["2%"]},
            {"strategy_family": "Pullback", "status": "HIT_2PCT", "milestones": ["2%"]},
        ]
    }

    applied = roxy_autopilot.apply_override_rollbacks(memory, env={}, path=target)

    assert applied[0]["applied"] is False
    assert json.loads(target.read_text())["strategy_overrides"]["Pullback"]["active"] is True


def test_apply_override_rollbacks_disables_override_when_enabled(tmp_path):
    target = tmp_path / "roxy_strategy_overrides.json"
    target.write_text(
        json.dumps(
            {
                "version": 1,
                "strategy_overrides": {
                    "Pullback": {"action": "SHADOW_TEST", "status": "ACTIVE", "active": True}
                },
            }
        )
    )
    memory = {
        "signal_journal": [
            {"strategy_family": "Pullback", "status": "HIT_2PCT", "milestones": ["2%"]},
            {"strategy_family": "Pullback", "status": "HIT_5PCT", "milestones": ["2%", "5%"]},
            {"strategy_family": "Pullback", "status": "HIT_2PCT", "milestones": ["2%"]},
        ]
    }

    applied = roxy_autopilot.apply_override_rollbacks(
        memory,
        env={roxy_autopilot.CODE_WRITE_ENV: "1"},
        path=target,
    )

    payload = json.loads(target.read_text())
    assert applied[0]["applied"] is True
    assert payload["strategy_overrides"]["Pullback"]["active"] is False
    assert payload["strategy_overrides"]["Pullback"]["status"] == "ROLLED_BACK"
