import pandas as pd

from streamlit_app import focused_opportunity_table, screener_preset_rows


def test_screener_preset_rows_groups_core_finviz_views():
    table = focused_opportunity_table(
        {
            "opportunities": [
                {
                    "ai_action": "ALERT",
                    "symbol": "NVDA",
                    "market": "stock",
                    "ai_score": 95,
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "strategy_family": "Breakout",
                    "risk_pct": 0.018,
                    "recommended_target_pct": 0.05,
                    "relative_volume_15m": 1.6,
                    "alert_readiness_score": 92,
                },
                {
                    "ai_action": "WATCH",
                    "symbol": "AAPL",
                    "market": "stock",
                    "ai_score": 86,
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "strategy_family": "Pullback",
                    "risk_pct": 0.024,
                    "recommended_target_pct": 0.04,
                    "relative_volume_15m": 0.9,
                    "alert_readiness_score": 73,
                },
                {
                    "ai_action": "WATCH",
                    "symbol": "TSLA",
                    "market": "stock",
                    "ai_score": 70,
                    "signal": "AVOID",
                    "trade_decision": "NO_TRADE_RISK",
                    "strategy_family": "Breakout",
                    "risk_pct": 0.061,
                    "recommended_target_pct": 0.01,
                    "relative_volume_15m": 2.1,
                    "alert_readiness_score": 35,
                },
            ]
        }
    )

    rows = screener_preset_rows(table, pd.DataFrame())
    by_preset = {row["preset"]: row for row in rows.to_dict("records")}

    assert rows.columns.tolist() == ["preset", "tone", "count", "avg_edge", "top_symbols", "rule"]
    assert by_preset["Breakouts"]["count"] == 2
    assert by_preset["Pullbacks"]["top_symbols"] == "AAPL"
    assert by_preset["Bajo riesgo"]["count"] == 2
    assert by_preset["Volumen"]["count"] == 2
    assert by_preset["Evitar"]["top_symbols"] == "TSLA"
