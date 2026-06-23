import pandas as pd

from streamlit_app import focused_opportunity_table, opportunity_compare_rows


def test_opportunity_compare_rows_prioritizes_and_explains_candidates():
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
                    "relative_volume_15m": 1.7,
                    "alert_readiness_score": 91,
                },
                {
                    "ai_action": "WATCH",
                    "symbol": "MSFT",
                    "market": "stock",
                    "ai_score": 86,
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "strategy_family": "Canal",
                    "risk_pct": 0.052,
                    "recommended_target_pct": 0.03,
                    "relative_volume_15m": 1.1,
                    "alert_readiness_score": 72,
                },
            ]
        }
    )
    confluence = pd.DataFrame(
        [
            {
                "symbol": "NVDA",
                "market": "stock",
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "confluence_score": 82,
                "trigger_setup": "TREND_CONTINUATION",
                "risk_pct": 0.024,
                "recommended_target_pct": 0.04,
                "relative_volume_15m": 0.6,
            }
        ]
    )

    rows = opportunity_compare_rows(table, confluence, limit=3)
    by_symbol = {row["symbol"]: row for row in rows.to_dict("records")}

    assert rows.columns.tolist() == ["rank", "symbol", "status", "tone", "edge", "score", "risk", "target", "rel_volume", "strategy", "next", "verdict"]
    assert rows.loc[0, "symbol"] == "AAPL"
    assert by_symbol["AAPL"]["verdict"].startswith("Mejor candidata")
    assert by_symbol["MSFT"]["verdict"] == "Riesgo alto: esperar mejor entrada."
    assert by_symbol["NVDA"]["verdict"] == "Falta volumen real para confiar."
