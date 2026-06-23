from trade_plan import build_trade_plan


def test_trade_plan_recommends_highest_feasible_target():
    plan = build_trade_plan(
        signal="BUY",
        entry=100,
        stop=99,
        confluence_score=90,
        trend_score=82,
        atr_pct=0.01,
        relative_volume=1.6,
    )

    assert plan["trade_decision"] == "TRADE_FOR_10PCT"
    assert plan["recommended_target_pct"] == 0.10
    assert round(plan["recommended_target_price"], 2) == 110
    assert plan["target_2pct_ok"] is True
    assert plan["target_5pct_ok"] is True
    assert plan["target_10pct_ok"] is True
    assert plan["risk_level"] == "LOW"


def test_trade_plan_blocks_buy_when_no_target_pays_enough_reward():
    plan = build_trade_plan(
        signal="BUY",
        entry=100,
        stop=94,
        confluence_score=90,
        trend_score=82,
        atr_pct=0.01,
        relative_volume=1.6,
    )

    assert plan["trade_decision"] == "NO_TRADE_RISK_REWARD"
    assert plan["recommended_target_pct"] is None
    assert plan["target_2pct_ok"] is False
    assert plan["risk_level"] == "HIGH"


def test_trade_plan_waits_when_signal_is_watch():
    plan = build_trade_plan(
        signal="WATCH",
        entry=100,
        stop=99,
        confluence_score=80,
        trend_score=70,
        atr_pct=0.01,
        relative_volume=1.2,
    )

    assert plan["trade_decision"] == "WAIT"
    assert plan["recommended_target_pct"] is None
