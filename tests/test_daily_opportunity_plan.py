from daily_opportunity_plan import build_daily_opportunity_plan, build_daily_plan_row, expectancy_r, reward_risk_ratio


def test_daily_plan_marks_clean_alert_as_operar_ahora():
    row = {
        "symbol": "AAPL",
        "market": "stock",
        "ai_action": "ALERT",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_2PCT",
        "alert_gate": "ALERT_READY",
        "alert_readiness_score": 100,
        "ai_score": 91,
        "trend_score": 82,
        "trigger_score": 76,
        "risk_pct": 0.018,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.2,
        "backtest_eligible": True,
        "entry": 200,
        "stop": 196,
        "strategy_family": "Canal alcista",
        "learning_bias": "positive",
    }

    plan_row = build_daily_plan_row(row)

    assert plan_row["stage"] == "OPERAR_AHORA"
    assert plan_row["decision"] in {"Operar", "Mirar call"}
    assert plan_row["probability"] >= 85
    assert plan_row["reward_risk"] > 2
    assert plan_row["expectancy_r"] > 1
    assert plan_row["edge_label"] == "Entrar si confirma precio"
    assert "10 trades" in plan_row["portfolio_math"]
    assert plan_row["target_2"] == 204


def test_daily_plan_marks_near_setup_as_proxima_entrada():
    row = {
        "symbol": "NVDA",
        "market": "stock",
        "ai_action": "WATCH",
        "signal": "WATCH",
        "trade_decision": "WAIT",
        "alert_gate": "WAIT_15M_ENTRY",
        "alert_readiness_score": 82,
        "ai_score": 78,
        "trend_score": 76,
        "risk_pct": 0.024,
        "recommended_target_pct": 0.02,
        "relative_volume_15m": 0.95,
        "entry": 150,
        "stop": 146,
        "strategy_family": "Pullback",
    }

    plan = build_daily_opportunity_plan([row])

    assert plan["status"] == "OK"
    assert plan["summary"]["status"] == "OK"
    assert plan["proxima_entrada"] == 1
    assert plan["summary"]["total"] == 1
    assert plan["summary"]["stage_counts"]["PROXIMA_ENTRADA"] == 1
    assert plan["summary"]["market_counts"]["stock"] == 1
    assert plan["summary"]["top"]["symbol"] == "NVDA"
    assert "edge_label" in plan["summary"]["top"]
    assert "timing_verdict" in plan["summary"]["top"]
    assert plan["summary"]["next_action"] == "Vigilar gatillos 15m de proximas entradas"
    assert plan["opportunities"] == plan["rows"]
    assert plan["rows"][0]["stage"] == "PROXIMA_ENTRADA"
    assert plan["rows"][0]["decision"] == "Esperar"
    assert "15m" in plan["rows"][0]["entry_trigger"]
    assert plan["rows"][0]["mtf_alignment"] in {"UNKNOWN", "PARTIAL", "CONFIRMED", "BLOCKED"}


def test_daily_plan_blocks_bad_structure():
    row = {
        "symbol": "TSLA",
        "market": "stock",
        "ai_action": "WATCH",
        "signal": "AVOID",
        "trade_decision": "NO_TRADE",
        "alert_gate": "NO_TRADE_STRUCTURE",
        "alert_readiness_score": 45,
        "ai_score": 66,
        "risk_pct": 0.012,
        "recommended_target_pct": 0.05,
        "entry": 300,
        "stop": 296,
        "strategy_family": "Tendencia bajista",
    }

    plan = build_daily_opportunity_plan([row])

    assert plan["no_operar"] == 1
    assert plan["rows"][0]["stage"] == "NO_OPERAR"
    assert plan["rows"][0]["probability"] <= 35


def test_daily_plan_penalizes_blocked_multitimeframe_context():
    base = {
        "symbol": "AMD",
        "market": "stock",
        "ai_action": "WATCH",
        "signal": "WATCH",
        "trade_decision": "WAIT",
        "alert_gate": "WAIT_15M_ENTRY",
        "alert_readiness_score": 82,
        "ai_score": 80,
        "trend_score": 75,
        "risk_pct": 0.02,
        "recommended_target_pct": 0.05,
        "relative_volume_15m": 1.0,
        "entry": 100,
        "stop": 98,
        "strategy_family": "Pullback",
    }

    confirmed = build_daily_plan_row({**base, "higher_tf_bias": "CONFIRMED"})
    blocked = build_daily_plan_row({**base, "higher_tf_bias": "BLOCKED", "higher_tf_blocks": 2})

    assert blocked["mtf_alignment"] == "BLOCKED"
    assert blocked["probability"] < confirmed["probability"]


def test_daily_plan_measures_portfolio_expectancy_not_zero_risk():
    reward_r = reward_risk_ratio(0.02, 0.05)

    assert round(reward_r, 2) == 2.50
    assert expectancy_r(70, reward_r) > 1.0

    row = build_daily_plan_row(
        {
            "symbol": "COIN",
            "market": "stock",
            "ai_action": "WATCH",
            "signal": "BUY",
            "trade_decision": "TRADE_FOR_5PCT",
            "alert_gate": "WAIT_15M_ENTRY",
            "alert_readiness_score": 88,
            "ai_score": 90,
            "trend_score": 84,
            "trigger_score": 78,
            "risk_pct": 0.02,
            "recommended_target_pct": 0.05,
            "relative_volume_15m": 1.4,
            "entry": 170,
            "stop": 166.6,
            "strategy_family": "Canal alcista",
        }
    )

    assert row["stage"] == "PROXIMA_ENTRADA"
    assert row["edge_label"] in {"Ventaja 70/30", "Edge positivo"}
    assert row["expectancy_r"] > 0
    assert "ganan" in row["portfolio_math"]


def test_daily_plan_does_not_promote_negative_expectancy():
    row = build_daily_plan_row(
        {
            "symbol": "WEAK",
            "market": "stock",
            "ai_action": "WATCH",
            "signal": "WATCH",
            "trade_decision": "WAIT",
            "alert_gate": "WAIT_15M_ENTRY",
            "alert_readiness_score": 58,
            "ai_score": 60,
            "trend_score": 55,
            "trigger_score": 50,
            "risk_pct": 0.05,
            "recommended_target_pct": 0.02,
            "relative_volume_15m": 0.5,
            "entry": 20,
            "stop": 19,
            "strategy_family": "Pullback debil",
        }
    )

    assert row["expectancy_r"] is not None
    assert row["expectancy_r"] < 0
    assert row["edge_label"] == "Sin edge suficiente"
    assert "no compensa" in row["timing_verdict"]
