import pandas as pd

from streamlit_app import focused_opportunity_table, scanner_matrix_summary, scanner_opportunity_matrix_rows


def test_opportunity_matrix_prioritizes_actionable_low_risk_setups():
    table = focused_opportunity_table(
        {
            "opportunities": [
                {
                    "ai_action": "ALERT",
                    "symbol": "AAPL",
                    "market": "stock",
                    "ai_score": 88,
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "strategy_family": "Pullback",
                    "risk_pct": 0.018,
                    "recommended_target_pct": 0.05,
                    "relative_volume_15m": 1.5,
                    "alert_readiness_score": 92,
                },
                {
                    "ai_action": "WATCH",
                    "symbol": "MSFT",
                    "market": "stock",
                    "ai_score": 92,
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "strategy_family": "Canal alcista",
                    "risk_pct": 0.072,
                    "recommended_target_pct": 0.02,
                    "relative_volume_15m": 0.7,
                    "alert_readiness_score": 65,
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
                "relative_volume_15m": 2.1,
                "entry_tf": "15m",
            }
        ]
    )

    rows = scanner_opportunity_matrix_rows(table, confluence, limit=3)

    assert rows.columns.tolist() == ["rank", "symbol", "status", "tone", "edge", "score", "risk", "rel_volume", "strategy", "next"]
    assert rows.loc[0, "symbol"] == "AAPL"
    assert rows.loc[0, "status"] == "Operar"
    assert rows.loc[0, "edge"] > rows.loc[1, "edge"]
    assert "MSFT" in rows["symbol"].tolist()


def test_scanner_matrix_summary_counts_watch_low_risk_and_volume():
    rows = pd.DataFrame(
        [
            {"symbol": "AAPL", "status": "Operar", "risk": 0.02, "rel_volume": 1.4, "edge": 100},
            {"symbol": "NVDA", "status": "Vigilar", "risk": 0.03, "rel_volume": 2.2, "edge": 91},
            {"symbol": "MSFT", "status": "Vigilar", "risk": 0.05, "rel_volume": 0.8, "edge": 80},
        ]
    )

    summary = scanner_matrix_summary(rows)

    assert summary["top_symbol"] == "AAPL"
    assert summary["top_status"] == "Operar"
    assert summary["watch_count"] == 2
    assert summary["low_risk"] == 2
    assert summary["volume_count"] == 2
