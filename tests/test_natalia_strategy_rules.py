from natalia_strategy_rules import evaluate_natalia_strategy_rules
from smart_alerts import evaluate_smart_alert
from trade_brief import build_symbol_trade_brief


def test_natalia_rules_block_buy_below_sma200():
    result = evaluate_natalia_strategy_rules(
        {
            "signal": "BUY",
            "setup": "PULLBACK",
            "close": 90,
            "sma20": 95,
            "sma40": 96,
            "sma100": 98,
            "sma200": 100,
            "relative_volume": 1.2,
        },
        {
            "signal": "BUY",
            "trade_decision": "TRADE_FOR_5PCT",
            "entry": 90,
            "risk_pct": 0.02,
            "recommended_target_pct": 0.05,
            "relative_volume_15m": 1.2,
        },
    )

    assert result["decision_gate"] == "BLOCK_BUY"
    assert result["hard_block"] is True
    assert any("SMA200" in reason for reason in result["reasons"])


def test_natalia_rules_allow_clean_aligned_setup():
    result = evaluate_natalia_strategy_rules(
        {
            "signal": "BUY",
            "setup": "TREND_CONTINUATION",
            "close": 110,
            "sma20": 108,
            "sma40": 103,
            "sma100": 96,
            "sma200": 88,
            "relative_volume": 1.3,
        },
        {
            "signal": "BUY",
            "trade_decision": "TRADE_FOR_5PCT",
            "risk_pct": 0.02,
            "recommended_target_pct": 0.05,
            "relative_volume_15m": 1.3,
        },
    )

    assert result["decision_gate"] == "ALLOW"
    assert result["alert_ok"] is True


def test_trade_brief_uses_natalia_rules_to_block_below_sma200():
    brief = build_symbol_trade_brief(
        symbol="AAPL",
        market="stock",
        timeframe="15m",
        setup={
            "signal": "BUY",
            "setup": "PULLBACK",
            "score": 90,
            "entry": 90,
            "close": 90,
            "stop": 88,
            "sma20": 95,
            "sma40": 96,
            "sma100": 98,
            "sma200": 100,
            "relative_volume": 1.2,
            "backtest_eligible": True,
        },
        confluence={
            "signal": "BUY",
            "trade_decision": "TRADE_FOR_5PCT",
            "confluence_score": 90,
            "entry": 90,
            "stop": 88,
            "risk_pct": 0.02,
            "relative_volume_15m": 1.2,
            "recommended_target_pct": 0.05,
            "backtest_eligible": True,
            "trend_setup": "TREND_CONTINUATION",
            "trigger_setup": "PULLBACK",
        },
    )

    assert brief["decision"] == "No operar"
    assert brief["natalia_rules"]["decision_gate"] == "BLOCK_BUY"
    assert any(item["label"] == "Reglas Natalia" and not item["passed"] for item in brief["condition_checks"])


def test_smart_alert_uses_natalia_rules_to_block_below_sma200():
    gate = evaluate_smart_alert(
        {
            "market": "stock",
            "symbol": "AAPL",
            "signal": "BUY",
            "trade_decision": "TRADE_FOR_5PCT",
            "confluence_score": 88,
            "trend_score": 80,
            "trigger_score": 74,
            "risk_pct": 0.02,
            "recommended_target_pct": 0.05,
            "relative_volume_15m": 1.2,
            "backtest_eligible": True,
            "trigger_setup": "PULLBACK",
            "trend_setup": "TREND_CONTINUATION",
            "close": 90,
            "entry": 90,
            "sma20": 95,
            "sma40": 96,
            "sma100": 98,
            "sma200": 100,
        }
    )

    assert gate["notification_ok"] is False
    assert gate["gate"] == "NO_TRADE_NATALIA_RULES"
    assert any(item["rule"] == "Reglas Natalia" and not item["passed"] for item in gate["checks"])
