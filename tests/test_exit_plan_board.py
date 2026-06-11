import pandas as pd

from streamlit_app import exit_plan_rows, focused_opportunity_table


def test_exit_plan_rows_builds_protection_rules_for_ready_trade():
    table = focused_opportunity_table(
        {
            "opportunities": [
                {
                    "ai_action": "ALERT",
                    "symbol": "NVDA",
                    "market": "stock",
                    "ai_score": 94,
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "entry": 120.0,
                    "stop": 116.4,
                    "recommended_target_pct": 0.04,
                    "relative_volume_15m": 1.4,
                    "alert_readiness_score": 91,
                }
            ]
        }
    )

    rows = exit_plan_rows(table, pd.DataFrame())
    row = rows.iloc[0].to_dict()

    assert row["symbol"] == "NVDA"
    assert row["tone"] == "buy"
    assert row["target_1"] == 124.8
    assert row["target_2"] == 126.0
    assert "mover stop" in row["protect"]
    assert "Salir si pierde" in row["exit_rule"]


def test_exit_plan_rows_blocks_missing_stop_before_execution():
    table = focused_opportunity_table(
        {
            "opportunities": [
                {
                    "ai_action": "WATCH",
                    "symbol": "AAPL",
                    "market": "stock",
                    "ai_score": 80,
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "entry": 190.0,
                    "recommended_target_pct": 0.03,
                    "alert_readiness_score": 60,
                }
            ]
        }
    )

    rows = exit_plan_rows(table, pd.DataFrame())
    row = rows.iloc[0].to_dict()

    assert row["tone"] == "avoid"
    assert row["protect"] == "No operar sin entrada/stop"
    assert row["exit_rule"] == "Esperar plan completo antes de enviar ticket."
