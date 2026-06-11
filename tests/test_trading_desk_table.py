import pandas as pd

from streamlit_app import (
    filter_trading_desk_display,
    focused_opportunity_table,
    trading_desk_paper_state,
    trading_desk_rows,
    trading_desk_summary,
)


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

    assert rows.columns.tolist() == ["#", "Ticker", "Estado", "Paper", "Edge", "Score", "Riesgo", "Target", "RVol", "HTF", "Mover", "Setup", "Siguiente", "Razón"]
    assert rows.loc[0, "Ticker"] == "AAPL"
    assert by_symbol["AAPL"]["Estado"] == "Operar"
    assert by_symbol["AAPL"]["Paper"] == "Paper listo"
    assert by_symbol["AAPL"]["Riesgo"] == "1.80%"
    assert by_symbol["AAPL"]["Target"] == "5.00%"
    assert by_symbol["AAPL"]["RVol"] == "1.7x"
    assert by_symbol["AAPL"]["HTF"] == "2/2"
    assert by_symbol["AAPL"]["Mover"] == "Ruptura"
    assert "confirman" in by_symbol["AAPL"]["Razón"]
    assert by_symbol["MSFT"]["Mover"] == "Pullback"
    assert by_symbol["MSFT"]["Paper"] == "Setup"


def test_trading_desk_rows_returns_expected_columns_when_empty():
    rows = trading_desk_rows(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    assert rows.columns.tolist() == ["#", "Ticker", "Estado", "Paper", "Edge", "Score", "Riesgo", "Target", "RVol", "HTF", "Mover", "Setup", "Siguiente", "Razón"]
    assert rows.empty

def test_filter_trading_desk_display_filters_status_score_and_query():
    rows = pd.DataFrame(
        [
            {"#": 1, "Ticker": "AAPL", "Estado": "Operar", "Score": "92", "Riesgo": "1.80%", "RVol": "1.4x", "Setup": "Pullback", "Siguiente": "Confirmar", "Razón": "1h confirma", "Mover": "Ruptura"},
            {"#": 2, "Ticker": "MSFT", "Estado": "Vigilar", "Score": "74", "Riesgo": "3.20%", "RVol": "0.8x", "Setup": "Canal", "Siguiente": "Esperar", "Razón": "Falta 15m", "Mover": "Pullback"},
            {"#": 3, "Ticker": "TSLA", "Estado": "Evitar", "Score": "65", "Riesgo": "7.00%", "RVol": "1.1x", "Setup": "Debilidad", "Siguiente": "No tocar", "Razón": "Riesgo alto", "Mover": "Debilidad"},
        ]
    )

    filtered = filter_trading_desk_display(rows, status="Vigilar", min_score=70, query="canal")

    assert filtered["Ticker"].tolist() == ["MSFT"]
    assert filtered["#"].tolist() == [1]


def test_filter_trading_desk_display_searches_paper_state():
    rows = pd.DataFrame(
        [
            {"#": 1, "Ticker": "AAPL", "Estado": "Operar", "Paper": "Paper listo", "Score": "92", "Riesgo": "1.80%", "RVol": "1.4x", "Setup": "Pullback", "Siguiente": "Confirmar", "Razón": "1h confirma", "Mover": "Ruptura"},
            {"#": 2, "Ticker": "MSFT", "Estado": "Vigilar", "Paper": "Setup", "Score": "74", "Riesgo": "3.20%", "RVol": "0.8x", "Setup": "Canal", "Siguiente": "Esperar", "Razón": "Falta 15m", "Mover": "Pullback"},
        ]
    )

    filtered = filter_trading_desk_display(rows, query="paper listo")

    assert filtered["Ticker"].tolist() == ["AAPL"]


def test_filter_trading_desk_display_applies_fast_presets():
    rows = pd.DataFrame(
        [
            {"#": 1, "Ticker": "AAPL", "Estado": "Operar", "Paper": "Paper listo", "Score": "92", "Riesgo": "1.80%", "RVol": "1.4x", "Setup": "Pullback", "Siguiente": "Confirmar", "Razón": "1h confirma", "Mover": "Ruptura"},
            {"#": 2, "Ticker": "NVDA", "Estado": "Vigilar", "Paper": "Setup", "Score": "88", "Riesgo": "2.20%", "RVol": "1.8x", "Setup": "Canal", "Siguiente": "Esperar", "Razón": "Volumen vivo", "Mover": "Ruptura"},
            {"#": 3, "Ticker": "TSLA", "Estado": "Evitar", "Paper": "No tocar", "Score": "65", "Riesgo": "7.00%", "RVol": "0.7x", "Setup": "Debilidad", "Siguiente": "No tocar", "Razón": "Riesgo alto", "Mover": "Debilidad"},
        ]
    )

    assert filter_trading_desk_display(rows, preset="Operar ahora")["Ticker"].tolist() == ["AAPL"]
    assert filter_trading_desk_display(rows, preset="Paper listo")["Ticker"].tolist() == ["AAPL"]
    assert filter_trading_desk_display(rows, preset="Alto score")["Ticker"].tolist() == ["AAPL", "NVDA"]
    assert filter_trading_desk_display(rows, preset="Bajo riesgo")["Ticker"].tolist() == ["AAPL", "NVDA"]
    assert filter_trading_desk_display(rows, preset="Volumen vivo")["Ticker"].tolist() == ["AAPL", "NVDA"]
    assert filter_trading_desk_display(rows, preset="No tocar")["Ticker"].tolist() == ["TSLA"]


def test_trading_desk_summary_counts_visible_operational_state():
    rows = pd.DataFrame(
        [
            {"Ticker": "AAPL", "Estado": "Operar", "Score": "92", "Riesgo": "1.80%", "RVol": "1.4x"},
            {"Ticker": "NVDA", "Estado": "Vigilar", "Score": "88", "Riesgo": "2.20%", "RVol": "1.8x"},
            {"Ticker": "TSLA", "Estado": "Evitar", "Score": "65", "Riesgo": "7.00%", "RVol": "0.7x"},
        ]
    )

    summary = trading_desk_summary(rows)

    assert summary["visible"] == 3
    assert summary["operar"] == 1
    assert summary["vigilar"] == 1
    assert summary["evitar"] == 1
    assert summary["best_symbol"] == "AAPL"
    assert summary["best_score"] == 92
    assert summary["avg_risk"] == 3.67
    assert summary["volume_live"] == 2


def test_trading_desk_paper_state_flags_blockers():
    assert trading_desk_paper_state(status="Operar", risk=0.018, target=0.03, rel_volume=1.2, htf="2/2") == "Paper listo"
    assert trading_desk_paper_state(status="Vigilar", risk=0.018, target=0.03, rel_volume=1.2, htf="2/2") == "Setup"
    assert trading_desk_paper_state(status="Evitar", risk=0.018, target=0.03, rel_volume=1.2, htf="2/2") == "No tocar"
    assert trading_desk_paper_state(status="Operar", risk=0.06, target=0.01, rel_volume=0.4, htf="0/2") == "Bloq riesgo/target"
