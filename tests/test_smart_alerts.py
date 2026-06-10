from smart_alerts import evaluate_smart_alert


def test_smart_alert_ready_requires_full_checklist():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 82,
        "trend_score": 78,
        "trigger_score": 72,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.2,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is True
    assert gate["gate"] == "ALERT_READY"
    assert gate["quality"] == "A+"
    assert gate["primary_blocker"] == "Listo para preview manual"
    assert gate["next_action"].startswith("Preparar plan manual")
    assert gate["passed_count"] == gate["total_checks"]
    assert gate["blockers"] == []


def test_smart_alert_blocks_missing_volume():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 82,
        "trend_score": 78,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "WAIT_VOLUME"
    assert gate["quality"] == "B"
    assert gate["primary_blocker"].startswith("Volumen acompana")
    assert gate["movement"].startswith("Esperar volumen")
    assert any("Volumen acompana" in item for item in gate["blockers"])


def test_smart_alert_blocks_bad_memory():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 82,
        "trend_score": 78,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.2,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
    }
    memory = {"strategy_stats": {"Pullback": {"alerts": 4, "hit_2pct": 0, "stops": 3}}}

    gate = evaluate_smart_alert(row, memory)

    assert gate["notification_ok"] is False
    assert gate["quality"] == "C"
    assert any("Filtro memoria" in item for item in gate["blockers"])


def test_smart_alert_blocks_higher_timeframe_contradiction():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 82,
        "trend_score": 78,
        "trigger_score": 72,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.2,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
        "higher_tf_bias": "BLOCKED",
        "higher_tf_confirmations": 1,
        "higher_tf_blocks": 1,
        "htf_2h_signal": "BUY",
        "htf_4h_signal": "AVOID",
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "WAIT_HTF_CONFIRM"
    assert gate["quality"] == "B"
    assert any("2h/4h validan" in item for item in gate["blockers"])
    assert "2h/4h" in gate["movement"]


def test_smart_alert_blocks_explicit_missing_higher_timeframe_context():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 82,
        "trend_score": 78,
        "trigger_score": 72,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.2,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
        "higher_tf_bias": "NO_DATA",
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "WAIT_HTF_CONFIRM"
    assert gate["primary_blocker"].startswith("2h/4h validan")


def test_smart_alert_blocks_when_source_freshness_disallows_alerts():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 82,
        "trend_score": 78,
        "trigger_score": 72,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.2,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
        "source_freshness": {
            "status": "STALE",
            "label": "Estancados",
            "detail": "live/confluencia llevan 45 min sin refrescar.",
            "alerts_allowed": False,
        },
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "BLOCKED_REALTIME_DATA"
    assert gate["primary_blocker"].startswith("Datos realtime")
    assert gate["quality"] == "C"


def test_smart_alert_blocks_when_realtime_health_disallows_alerts():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 82,
        "trend_score": 78,
        "trigger_score": 72,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.2,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
        "realtime_health": {
            "status": "FAIL",
            "label": "Health fallo",
            "detail": "heartbeat failed",
            "alerts_allowed": False,
        },
    }

    gate = evaluate_smart_alert(row)

    assert gate["notification_ok"] is False
    assert gate["gate"] == "BLOCKED_REALTIME_DATA"
    assert "heartbeat failed" in gate["primary_blocker"]


def test_smart_alert_uses_shadow_memory_before_real_alert_sample():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 82,
        "trend_score": 78,
        "trigger_score": 72,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.2,
        "backtest_eligible": True,
        "trigger_setup": "PULLBACK",
        "trend_setup": "TREND_CONTINUATION",
    }
    memory = {
        "strategy_stats": {
            "Pullback": {
                "alerts": 0,
                "shadow_observed": 4,
                "shadow_near_2pct": 1,
                "shadow_hit_2pct": 0,
                "shadow_near_stop": 3,
            }
        }
    }

    gate = evaluate_smart_alert(row, memory)

    assert gate["notification_ok"] is False
    assert gate["quality"] == "C"
    assert gate["gate"] == "WAIT_FULL_CHECKLIST"
    assert any("shadow stop" in item for item in gate["blockers"])
