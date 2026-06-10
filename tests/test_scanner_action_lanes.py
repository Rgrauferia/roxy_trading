from streamlit_app import (
    filter_scanner_explorer_rows,
    focused_opportunity_table,
    scanner_action_lane_rows,
    scanner_strategy_options,
)


def test_scanner_action_lane_rows_groups_ready_watch_and_avoid_setups():
    table = focused_opportunity_table(
        {
            "opportunities": [
                {
                    "ai_action": "ALERT",
                    "symbol": "AAPL",
                    "market": "stock",
                    "ai_score": 91,
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "strategy_family": "Pullback",
                    "risk_pct": 0.018,
                    "recommended_target_pct": 0.04,
                    "alert_readiness_score": 86,
                },
                {
                    "ai_action": "WATCH",
                    "symbol": "NVDA",
                    "market": "stock",
                    "ai_score": 77,
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "strategy_family": "Canal alcista",
                    "risk_pct": 0.042,
                    "recommended_target_pct": 0.03,
                    "alert_readiness_score": 64,
                },
                {
                    "ai_action": "AVOID",
                    "symbol": "TSLA",
                    "market": "stock",
                    "ai_score": 62,
                    "signal": "AVOID",
                    "trade_decision": "NO_TRADE_DOWNTREND",
                    "strategy_family": "Tendencia bajista",
                    "risk_pct": 0.052,
                    "recommended_target_pct": 0.02,
                    "alert_readiness_score": 31,
                },
            ]
        }
    )

    lanes = scanner_action_lane_rows(table)

    assert lanes["lane"].tolist() == ["Ahora", "Esperar gatillo", "No tocar"]
    assert lanes["tone"].tolist() == ["buy", "watch", "avoid"]
    assert lanes["symbol"].tolist() == ["AAPL", "NVDA", "TSLA"]
    assert lanes.loc[0, "strategy"] == "Pullback"
    assert lanes.loc[1, "trigger"].startswith("Esperar")


def test_filter_scanner_explorer_rows_combines_status_market_strategy_and_readiness():
    table = focused_opportunity_table(
        {
            "opportunities": [
                {
                    "ai_action": "ALERT",
                    "symbol": "AAPL",
                    "market": "stock",
                    "ai_score": 91,
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "strategy_family": "Pullback",
                    "alert_readiness_score": 86,
                },
                {
                    "ai_action": "WATCH",
                    "symbol": "NVDA",
                    "market": "stock",
                    "ai_score": 77,
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "strategy_family": "Canal alcista",
                    "alert_readiness_score": 64,
                },
                {
                    "ai_action": "WATCH",
                    "symbol": "BTC/USD",
                    "market": "crypto",
                    "ai_score": 74,
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "strategy_family": "Pullback",
                    "alert_readiness_score": 70,
                },
            ]
        }
    )

    filtered = filter_scanner_explorer_rows(
        table,
        bucket="Vigilar",
        market="crypto",
        strategy="Pullback",
        min_readiness=65,
    )

    assert scanner_strategy_options(table) == ["Todos", "Canal alcista", "Pullback"]
    assert filtered["symbol"].tolist() == ["BTC/USD"]
    assert filter_scanner_explorer_rows(table, strategy="Canal alcista", min_readiness=80).empty
