import pandas as pd

from streamlit_app import build_mini_opportunity_chart, focused_opportunity_table, mini_opportunity_rows


def test_mini_opportunity_rows_prioritize_trade_ready_then_score():
    table = focused_opportunity_table(
        {
            "opportunities": [
                {
                    "ai_action": "WATCH",
                    "symbol": "MSFT",
                    "market": "stock",
                    "ai_score": 99,
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "strategy_family": "Canal alcista",
                    "risk_pct": 0.03,
                    "recommended_target_pct": 0.02,
                    "alert_readiness_score": 70,
                },
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
                    "alert_readiness_score": 92,
                },
            ]
        }
    )

    rows = mini_opportunity_rows(table, pd.DataFrame(), limit=2)

    assert rows.columns.tolist() == ["symbol", "status", "tone", "market", "score", "risk", "target", "strategy", "next"]
    assert rows.loc[0, "symbol"] == "AAPL"
    assert rows.loc[0, "status"] == "Operar"
    assert rows.loc[1, "symbol"] == "MSFT"


def test_build_mini_opportunity_chart_is_interactive_with_price_tooltips():
    chart_df = pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=20, freq="15min"),
            "open": [100 + idx * 0.1 for idx in range(20)],
            "high": [101 + idx * 0.1 for idx in range(20)],
            "low": [99 + idx * 0.1 for idx in range(20)],
            "close": [100.4 + idx * 0.1 for idx in range(20)],
            "volume": [1000 + idx for idx in range(20)],
        }
    )

    spec = build_mini_opportunity_chart(chart_df, tone="buy").to_dict()

    assert spec["params"][0]["bind"] == "scales"
    assert any("tooltip" in layer.get("encoding", {}) for layer in spec["layer"])
