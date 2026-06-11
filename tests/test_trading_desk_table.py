import pandas as pd

from streamlit_app import focused_opportunity_table, trading_desk_rows


def test_trading_desk_rows_merge_edge_validation_and_movers():
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
                    "alert_readiness_score": 90,
                },
                {
                    "ai_action": "WATCH",
                    "symbol": "MSFT",
                    "market": "stock",
                    "ai_score": 82,
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "strategy_family": "Canal alcista",
                    "risk_pct": 0.032,
                    "recommended_target_pct": 0.02,
                    "relative_volume_15m": 0.8,
                    "alert_readiness_score": 68,
                },
            ]
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
                "relative_volume_15m": 1.7,
                "recommended_target_pct": 0.05,
                "target_2pct_ok": True,
                "reasons": "1h y 2h confirman",
            },
            {
                "symbol": "MSFT",
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "confluence_score": 82,
                "trigger_setup": "TREND_CONTINUATION",
                "trend_setup": "EARLY_UPTREND",
                "higher_tf_confirmations": 1,
                "higher_tf_blocks": 1,
                "risk_pct": 0.032,
                "recommended_target_pct": 0.02,
                "target_2pct_ok": False,
                "reasons": "Falta 15m",
            },
        ]
    )
    scan = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "score": 91,
                "setup": "TREND_CONTINUATION",
                "raw_signal": "BUY",
                "dist_sma20_pct": 1.2,
                "dist_sma200_pct": 10.0,
                "relative_volume": 1.7,
            },
            {
                "symbol": "MSFT",
                "score": 82,
                "setup": "PULLBACK",
                "raw_signal": "WATCH",
                "dist_sma20_pct": -1.0,
                "dist_sma200_pct": 8.0,
                "relative_volume": 0.8,
            },
        ]
    )

    rows = trading_desk_rows(table, confluence, scan, limit=10)
    by_symbol = {row["Ticker"]: row for row in rows.to_dict("records")}

    assert rows.columns.tolist() == ["#", "Ticker", "Estado", "Edge", "Score", "Riesgo", "Target", "RVol", "HTF", "Mover", "Setup", "Siguiente", "Razón"]
    assert rows.loc[0, "Ticker"] == "AAPL"
    assert by_symbol["AAPL"]["Estado"] == "Operar"
    assert by_symbol["AAPL"]["Riesgo"] == "1.80%"
    assert by_symbol["AAPL"]["Target"] == "5.00%"
    assert by_symbol["AAPL"]["RVol"] == "1.7x"
    assert by_symbol["AAPL"]["HTF"] == "2/2"
    assert by_symbol["AAPL"]["Mover"] == "Ruptura"
    assert "confirman" in by_symbol["AAPL"]["Razón"]
    assert by_symbol["MSFT"]["Mover"] == "Pullback"


def test_trading_desk_rows_returns_expected_columns_when_empty():
    rows = trading_desk_rows(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    assert rows.columns.tolist() == ["#", "Ticker", "Estado", "Edge", "Score", "Riesgo", "Target", "RVol", "HTF", "Mover", "Setup", "Siguiente", "Razón"]
    assert rows.empty
