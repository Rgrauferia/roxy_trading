import pandas as pd

from streamlit_app import focused_opportunity_table, market_movers_tape_rows


def test_market_movers_tape_rows_builds_finviz_style_groups():
    table = focused_opportunity_table(
        {
            "opportunities": [
                {
                    "ai_action": "ALERT",
                    "symbol": "AAPL",
                    "market": "stock",
                    "ai_score": 94,
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "strategy_family": "Pullback",
                    "risk_pct": 0.018,
                    "recommended_target_pct": 0.04,
                    "relative_volume_15m": 1.6,
                    "alert_readiness_score": 90,
                },
                {
                    "ai_action": "WATCH",
                    "symbol": "MSFT",
                    "market": "stock",
                    "ai_score": 88,
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "strategy_family": "Canal",
                    "risk_pct": 0.031,
                    "recommended_target_pct": 0.03,
                    "relative_volume_15m": 0.9,
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
                "confluence_score": 86,
                "trigger_setup": "TREND_CONTINUATION",
                "risk_pct": 0.022,
                "recommended_target_pct": 0.05,
                "relative_volume_15m": 2.4,
            },
            {
                "symbol": "TSLA",
                "market": "stock",
                "signal": "AVOID",
                "trade_decision": "NO_TRADE_DOWNTREND",
                "confluence_score": 45,
                "trigger_setup": "DOWNTREND",
                "risk_pct": 0.08,
                "recommended_target_pct": 0.01,
                "relative_volume_15m": 1.2,
            },
        ]
    )

    rows = market_movers_tape_rows(table, confluence, limit_per_group=2)
    grouped = rows.groupby("group")["symbol"].apply(list).to_dict()

    assert rows.columns.tolist() == ["group", "tone", "symbol", "status", "score", "risk", "rel_volume", "strategy", "next"]
    assert grouped["Top Score"][0] == "AAPL"
    assert grouped["Volumen"][0] == "NVDA"
    assert grouped["Riesgo Bajo"][0] == "AAPL"
    assert "MSFT" in grouped["Gatillo Cerca"]
    assert grouped["No Tocar"] == ["TSLA"]
