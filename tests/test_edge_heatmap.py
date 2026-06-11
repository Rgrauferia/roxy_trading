import pandas as pd

from streamlit_app import focused_opportunity_table, opportunity_edge_heatmap_rows


def test_opportunity_edge_heatmap_rows_group_by_strategy_and_status():
    table = focused_opportunity_table(
        {
            "opportunities": [
                {
                    "ai_action": "ALERT",
                    "symbol": "AAPL",
                    "market": "stock",
                    "ai_score": 92,
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "strategy_family": "Pullback",
                    "risk_pct": 0.018,
                    "recommended_target_pct": 0.05,
                    "relative_volume_15m": 1.8,
                    "alert_readiness_score": 91,
                },
                {
                    "ai_action": "WATCH",
                    "symbol": "MSFT",
                    "market": "stock",
                    "ai_score": 84,
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "strategy_family": "Pullback",
                    "risk_pct": 0.03,
                    "recommended_target_pct": 0.03,
                    "relative_volume_15m": 0.9,
                    "alert_readiness_score": 71,
                },
            ]
        }
    )
    confluence = pd.DataFrame(
        [
            {
                "symbol": "TSLA",
                "market": "stock",
                "signal": "AVOID",
                "trade_decision": "NO_TRADE_DOWNTREND",
                "confluence_score": 40,
                "trigger_setup": "DOWNTREND",
                "risk_pct": 0.08,
                "recommended_target_pct": 0.01,
                "relative_volume_15m": 1.1,
            }
        ]
    )

    rows = opportunity_edge_heatmap_rows(table, confluence, limit=10)
    pullback_operar = rows[(rows["strategy"].eq("Pullback")) & (rows["status"].eq("Operar"))].iloc[0]

    assert rows.columns.tolist() == ["strategy", "status", "tone", "count", "avg_edge", "avg_score", "avg_risk", "avg_volume", "symbols"]
    assert pullback_operar["count"] == 1
    assert pullback_operar["symbols"] == "AAPL"
    assert pullback_operar["avg_edge"] > rows[rows["status"].eq("Evitar")].iloc[0]["avg_edge"]
