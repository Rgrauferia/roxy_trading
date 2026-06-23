import pandas as pd

from streamlit_app import focused_opportunity_table, ticker_intel_snapshot


def test_ticker_intel_snapshot_uses_selected_symbol_and_explains_blockers():
    table = focused_opportunity_table(
        {
            "opportunities": [
                {
                    "ai_action": "WATCH",
                    "symbol": "WMT",
                    "market": "stock",
                    "ai_score": 88,
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "strategy_family": "Canal alcista",
                    "risk_pct": 0.023,
                    "entry": 120.49,
                    "stop": 117.69,
                    "recommended_target_pct": 0.05,
                    "relative_volume_15m": 0.4,
                    "alert_readiness_score": 70,
                    "trigger_setup": "Esperar entrada 15m",
                    "reason": "Esperar continuacion alcista.",
                },
                {
                    "ai_action": "ALERT",
                    "symbol": "AAPL",
                    "market": "stock",
                    "ai_score": 96,
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "strategy_family": "Pullback",
                    "risk_pct": 0.015,
                    "recommended_target_pct": 0.04,
                    "relative_volume_15m": 1.8,
                    "alert_readiness_score": 94,
                },
            ]
        }
    )

    intel = ticker_intel_snapshot(table, pd.DataFrame(), "WMT")

    assert intel["symbol"] == "WMT"
    assert intel["status"] == "Vigilar"
    assert intel["entry"] == 120.49
    assert intel["stop"] == 117.69
    assert "Volumen relativo" in intel["blockers"][0]
    assert intel["why"] == "Esperar continuacion alcista."


def test_ticker_intel_snapshot_falls_back_to_best_ranked_symbol():
    table = focused_opportunity_table(
        {
            "opportunities": [
                {
                    "ai_action": "ALERT",
                    "symbol": "NVDA",
                    "market": "stock",
                    "ai_score": 91,
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "strategy_family": "Breakout",
                    "risk_pct": 0.018,
                    "recommended_target_pct": 0.05,
                    "relative_volume_15m": 1.5,
                    "alert_readiness_score": 90,
                }
            ]
        }
    )

    intel = ticker_intel_snapshot(table, pd.DataFrame(), "UNKNOWN")

    assert intel["symbol"] == "NVDA"
    assert intel["status"] == "Operar"
    assert intel["blockers"] == ["Listo para validacion manual final"]
