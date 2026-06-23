import pandas as pd

from streamlit_app import focused_opportunity_table, radar_plan_label, scanner_blotter_rows


def test_scanner_blotter_rows_formats_dense_screener_columns():
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
                }
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
                "confluence_score": 84,
                "trigger_setup": "TREND_CONTINUATION",
                "risk_pct": 0.027,
                "recommended_target_pct": 0.05,
                "relative_volume_15m": 1.6,
                "entry_tf": "15m",
            }
        ]
    )

    rows = scanner_blotter_rows(table, confluence, limit=10)

    assert rows.columns.tolist() == ["#", "Prioridad", "Ticker", "Estado", "Edge", "Score", "Setup", "Riesgo", "Target", "RVol", "TF", "Siguiente"]
    assert rows["Ticker"].tolist() == ["AAPL", "NVDA"]
    assert rows.loc[0, "Prioridad"] == "🔥 Operar"
    assert rows.loc[0, "Estado"] == "Operar"
    assert rows.loc[0, "Edge"] > rows.loc[1, "Edge"]
    assert rows.loc[0, "Score"] == 91
    assert rows.loc[0, "Riesgo"] == "1.80%"
    assert rows.loc[1, "RVol"] == "1.6x"


def test_radar_plan_label_prioritizes_next_action():
    assert radar_plan_label("Operar", "🔥 OPERAR", "1.80%", "4.00%", "1.6x", "OK") == "Validar ticket"
    assert radar_plan_label("Vigilar", "👀 ESPERAR", "2.70%", "5.00%", "0.6x", "volumen") == "Esperar volumen"
    assert radar_plan_label("Evitar", "⛔ NO TOCAR", "2.00%", "4.00%", "1.4x", "bloqueado") == "No tocar"
