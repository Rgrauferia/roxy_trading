import pandas as pd

from streamlit_app import executive_cockpit_summary, focused_opportunity_table


def test_executive_cockpit_summary_surfaces_top_decision_and_counts():
    table = focused_opportunity_table(
        {
            "source_freshness": {"label": "Frescos"},
            "market_session": {"stock_session": "After-hours"},
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
                    "alert_readiness_score": 94,
                },
                {
                    "ai_action": "WATCH",
                    "symbol": "MSFT",
                    "market": "stock",
                    "ai_score": 81,
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "strategy_family": "Canal alcista",
                    "risk_pct": 0.03,
                    "recommended_target_pct": 0.02,
                    "relative_volume_15m": 0.9,
                    "alert_readiness_score": 70,
                },
            ],
        }
    )
    confluence = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "confluence_score": 94,
                "trigger_setup": "PULLBACK",
                "trend_setup": "TREND_CONTINUATION",
                "higher_tf_confirmations": 2,
                "higher_tf_blocks": 0,
                "risk_pct": 0.018,
                "relative_volume_15m": 1.8,
                "recommended_target_pct": 0.05,
                "target_2pct_ok": True,
            },
            {
                "symbol": "TSLA",
                "signal": "AVOID",
                "trade_decision": "NO_TRADE_DOWNTREND",
                "confluence_score": 25,
                "higher_tf_confirmations": 0,
                "higher_tf_blocks": 2,
                "risk_pct": 0.08,
            },
        ]
    )
    scan = pd.DataFrame(
        [
            {"symbol": "SPY", "signal": "BUY", "trade_decision": "TRADE_FOR_2PCT", "score": 88, "risk_pct": 0.02},
            {"symbol": "QQQ", "signal": "BUY", "trade_decision": "TRADE_FOR_2PCT", "score": 86, "risk_pct": 0.02},
        ]
    )
    brief = {"source_freshness": {"label": "Frescos"}, "market_session": {"stock_session": "After-hours"}}

    summary = executive_cockpit_summary(table, confluence, scan, brief)

    assert summary["top_symbol"] == "AAPL"
    assert summary["headline"] == "AAPL · Operar"
    assert summary["ready"] == 1
    assert summary["watch"] == 1
    assert summary["validated"] == 1
    assert summary["blocked"] == 1
    assert summary["session"] == "After-hours"
    assert summary["freshness"] == "Frescos"
    assert len(summary["tape"]) >= 2


def test_executive_cockpit_summary_handles_empty_inputs():
    summary = executive_cockpit_summary(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {})

    assert summary["headline"] == "Sin oportunidad priorizada"
    assert summary["total"] == 0
    assert summary["ready"] == 0
    assert summary["tape"] == []
