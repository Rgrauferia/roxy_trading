import pandas as pd

from streamlit_app import (
    build_mini_opportunity_chart,
    focused_opportunity_table,
    mini_opportunity_rows,
    top_opportunity_card_details,
)


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

    assert any(param.get("bind") == "scales" for param in spec["params"])
    assert any(param.get("name") == "mini_hover" for param in spec["params"])
    assert any(layer.get("mark", {}).get("type") == "rule" for layer in spec["layer"])
    assert any("tooltip" in layer.get("encoding", {}) for layer in spec["layer"])


def test_build_mini_opportunity_chart_fallback_explains_data_gap():
    spec = build_mini_opportunity_chart(pd.DataFrame(), tone="watch").to_dict()
    datasets = " ".join(str(value) for value in spec.get("datasets", {}).values())

    assert "Sin historial local" in datasets
    assert "Validar proveedor / recargar scanner" in datasets
    assert len(spec["layer"]) == 3


def test_top_opportunity_card_details_surface_next_action():
    details = top_opportunity_card_details(
        {
            "status": "Vigilar",
            "score": 88,
            "risk": 0.022,
            "target": 0.05,
            "next": "Esperar cierre 15m sobre SMA20.",
        }
    )

    assert details["metrics"] == "Score 88 · Riesgo 2.20% · Target 5.00%"
    assert details["next"] == "Esperar cierre 15m sobre SMA20."


def test_top_opportunity_card_details_fallback_depends_on_status():
    operar = top_opportunity_card_details({"status": "Operar", "next": "-"})
    evitar = top_opportunity_card_details({"status": "Evitar", "next": "-"})

    assert "Confirmar ticket manual" in operar["next"]
    assert "No tocar" in evitar["next"]
