import pandas as pd

from streamlit_app import (
    filter_trading_desk_display,
    focused_opportunity_table,
    trading_desk_action_queue,
    trading_desk_blocker_counts,
    trading_desk_blocker_summary,
    trading_desk_next_step_summary,
    trading_desk_paper_state,
    trading_desk_preset_counts,
    trading_desk_priority_label,
    trading_desk_rows,
    trading_desk_summary,
    trading_desk_urgency_label,
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

    assert rows.columns.tolist() == ["#", "Prioridad", "Ticker", "Estado", "Paper", "Falta", "Edge", "Score", "Riesgo", "Target", "RVol", "HTF", "Mover", "Setup", "Siguiente", "Razón"]
    assert rows.loc[0, "Ticker"] == "AAPL"
    assert by_symbol["AAPL"]["Estado"] == "Operar"
    assert by_symbol["AAPL"]["Prioridad"] == "🔥 Paper listo"
    assert by_symbol["AAPL"]["Paper"] == "Paper listo"
    assert by_symbol["AAPL"]["Falta"] == "Completo"
    assert by_symbol["AAPL"]["Riesgo"] == "1.80%"
    assert by_symbol["AAPL"]["Target"] == "5.00%"
    assert by_symbol["AAPL"]["RVol"] == "1.7x"
    assert by_symbol["AAPL"]["HTF"] == "2/2"
    assert by_symbol["AAPL"]["Mover"] == "Ruptura"
    assert "confirman" in by_symbol["AAPL"]["Razón"]
    assert by_symbol["MSFT"]["Mover"] == "Pullback"
    assert by_symbol["MSFT"]["Prioridad"] == "👀 Vigilar"
    assert by_symbol["MSFT"]["Paper"] == "Setup"
    assert by_symbol["MSFT"]["Falta"] == "Falta 15m"
    assert by_symbol["MSFT"]["Siguiente"] == "Esperar gatillo 15m"


def test_trading_desk_rows_returns_expected_columns_when_empty():
    rows = trading_desk_rows(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    assert rows.columns.tolist() == ["#", "Prioridad", "Ticker", "Estado", "Paper", "Falta", "Edge", "Score", "Riesgo", "Target", "RVol", "HTF", "Mover", "Setup", "Siguiente", "Razón"]
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



def test_filter_trading_desk_display_searches_priority_label():
    rows = pd.DataFrame(
        [
            {"#": 1, "Prioridad": "🔥 Paper listo", "Ticker": "AAPL", "Estado": "Operar", "Paper": "Paper listo", "Score": "92", "Riesgo": "1.80%", "RVol": "1.4x", "Setup": "Pullback", "Siguiente": "Confirmar", "Razón": "1h confirma", "Mover": "Ruptura"},
            {"#": 2, "Prioridad": "👀 Vigilar", "Ticker": "MSFT", "Estado": "Vigilar", "Paper": "Setup", "Score": "74", "Riesgo": "3.20%", "RVol": "0.8x", "Setup": "Canal", "Siguiente": "Esperar", "Razón": "Falta 15m", "Mover": "Pullback"},
        ]
    )

    filtered = filter_trading_desk_display(rows, query="paper listo")

    assert filtered["Ticker"].tolist() == ["AAPL"]


def test_filter_trading_desk_display_searches_blocker_summary():
    rows = pd.DataFrame(
        [
            {"#": 1, "Prioridad": "🔥 Paper listo", "Ticker": "AAPL", "Estado": "Operar", "Paper": "Paper listo", "Falta": "Completo", "Score": "92", "Riesgo": "1.80%", "RVol": "1.4x", "Setup": "Pullback", "Siguiente": "Confirmar", "Razón": "1h confirma", "Mover": "Ruptura"},
            {"#": 2, "Prioridad": "👀 Vigilar", "Ticker": "MSFT", "Estado": "Vigilar", "Paper": "Setup", "Falta": "Falta 15m", "Score": "74", "Riesgo": "3.20%", "RVol": "0.8x", "Setup": "Canal", "Siguiente": "Esperar", "Razón": "Falta 15m", "Mover": "Pullback"},
        ]
    )

    filtered = filter_trading_desk_display(rows, query="falta 15m")

    assert filtered["Ticker"].tolist() == ["MSFT"]


def test_filter_trading_desk_display_filters_blocker_summary():
    rows = pd.DataFrame(
        [
            {"#": 1, "Ticker": "AAPL", "Estado": "Operar", "Paper": "Paper listo", "Falta": "Completo", "Score": "92", "Riesgo": "1.80%", "RVol": "1.4x", "Setup": "Pullback", "Siguiente": "Confirmar", "Razón": "1h confirma", "Mover": "Ruptura"},
            {"#": 2, "Ticker": "MSFT", "Estado": "Vigilar", "Paper": "Setup", "Falta": "Falta 15m", "Score": "74", "Riesgo": "3.20%", "RVol": "0.8x", "Setup": "Canal", "Siguiente": "Esperar", "Razón": "Falta 15m", "Mover": "Pullback"},
            {"#": 3, "Ticker": "TSLA", "Estado": "Evitar", "Paper": "No tocar", "Falta": "No tocar", "Score": "65", "Riesgo": "7.00%", "RVol": "0.7x", "Setup": "Debilidad", "Siguiente": "No tocar", "Razón": "Riesgo alto", "Mover": "Debilidad"},
        ]
    )

    filtered = filter_trading_desk_display(rows, blocker="Falta 15m")

    assert filtered["Ticker"].tolist() == ["MSFT"]
    assert filtered["#"].tolist() == [1]

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


def test_trading_desk_preset_counts_match_fast_presets():
    rows = pd.DataFrame(
        [
            {"#": 1, "Ticker": "AAPL", "Estado": "Operar", "Paper": "Paper listo", "Score": "92", "Riesgo": "1.80%", "RVol": "1.4x", "Setup": "Pullback", "Siguiente": "Confirmar", "Razón": "1h confirma", "Mover": "Ruptura"},
            {"#": 2, "Ticker": "NVDA", "Estado": "Vigilar", "Paper": "Setup", "Score": "88", "Riesgo": "2.20%", "RVol": "1.8x", "Setup": "Canal", "Siguiente": "Esperar", "Razón": "Volumen vivo", "Mover": "Ruptura"},
            {"#": 3, "Ticker": "TSLA", "Estado": "Evitar", "Paper": "No tocar", "Score": "65", "Riesgo": "7.00%", "RVol": "0.7x", "Setup": "Debilidad", "Siguiente": "No tocar", "Razón": "Riesgo alto", "Mover": "Debilidad"},
        ]
    )

    counts = trading_desk_preset_counts(rows)

    assert counts == {
        "Todos": 3,
        "Operar ahora": 1,
        "Paper listo": 1,
        "Alto score": 2,
        "Bajo riesgo": 2,
        "Volumen vivo": 2,
        "No tocar": 1,
    }




def test_trading_desk_blocker_summary_explains_missing_requirement():
    assert trading_desk_blocker_summary("Operar", "Paper listo", "Confirmar", "1h confirma") == "Completo"
    assert trading_desk_blocker_summary("Operar", "Bloq riesgo/target", "Esperar", "Riesgo alto") == "Falta Riesgo + Target 2%"
    assert trading_desk_blocker_summary("Vigilar", "Setup", "Esperar", "Falta 15m") == "Falta 15m"
    assert trading_desk_blocker_summary("Evitar", "No tocar", "No tocar", "Riesgo alto") == "No tocar"


def test_trading_desk_next_step_summary_turns_blockers_into_actions():
    assert trading_desk_next_step_summary("Vigilar", "Setup", "Falta 15m", "Esperar", "Falta 15m") == "Esperar gatillo 15m"
    assert (
        trading_desk_next_step_summary(
            "Operar", "Bloq riesgo/target", "Falta Riesgo + Target 2%", "Esperar", "Riesgo alto"
        )
        == "Ajustar riesgo/target"
    )
    assert trading_desk_next_step_summary("Operar", "Bloq volumen", "Falta Volumen", "-", "RVol bajo") == "Esperar volumen"
    assert trading_desk_next_step_summary("Evitar", "No tocar", "No tocar", "No tocar", "Riesgo alto") == "No tocar"


def test_trading_desk_priority_label_marks_operational_state():
    assert trading_desk_priority_label("Operar", "Paper listo", 90, 0.018, 1.4) == "🔥 Paper listo"
    assert trading_desk_priority_label("Operar", "Bloq riesgo/target", 90, 0.06, 1.4) == "⚠ Bloqueada"
    assert trading_desk_priority_label("Vigilar", "Setup", 88, 0.022, 0.9) == "👀 Alta vigilancia"
    assert trading_desk_priority_label("Vigilar", "Setup", 70, 0.022, 0.9) == "👀 Vigilar"
    assert trading_desk_priority_label("Evitar", "No tocar", 99, 0.07, 2.0) == "⛔ No tocar"


def test_trading_desk_blocker_counts_groups_visible_requirements():
    rows = pd.DataFrame(
        [
            {"Ticker": "AAPL", "Falta": "Completo"},
            {"Ticker": "NVDA", "Falta": "Falta 15m"},
            {"Ticker": "MSFT", "Falta": "Falta 15m"},
            {"Ticker": "TSLA", "Falta": "No tocar"},
        ]
    )

    counts = trading_desk_blocker_counts(rows)

    assert counts[["blocker", "count", "tone"]].to_dict("records") == [
        {"blocker": "Falta 15m", "count": 2, "tone": "watch"},
        {"blocker": "Completo", "count": 1, "tone": "buy"},
        {"blocker": "No tocar", "count": 1, "tone": "avoid"},
    ]

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


def test_trading_desk_action_queue_prioritizes_paper_ready_then_watch():
    rows = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Estado": "Vigilar",
                "Paper": "Setup",
                "Score": "94",
                "Riesgo": "2.20%",
                "RVol": "1.8x",
                "Setup": "Canal",
                "Siguiente": "Esperar gatillo",
                "Razón": "Falta 15m",
            },
            {
                "Ticker": "AAPL",
                "Estado": "Operar",
                "Paper": "Paper listo",
                "Score": "90",
                "Riesgo": "1.80%",
                "RVol": "1.4x",
                "Setup": "Pullback",
                "Siguiente": "Confirmar ticket",
                "Razón": "1h confirma",
            },
            {
                "Ticker": "TSLA",
                "Estado": "Evitar",
                "Paper": "No tocar",
                "Score": "99",
                "Riesgo": "7.00%",
                "RVol": "2.0x",
                "Setup": "Debilidad",
                "Siguiente": "No tocar",
                "Razón": "Riesgo alto",
            },
        ]
    )

    queue = trading_desk_action_queue(rows, limit=3)

    assert queue["ticker"].tolist() == ["AAPL", "NVDA", "TSLA"]
    assert queue.loc[0, "tone"] == "buy"
    assert queue.loc[0, "urgency"] == "Ahora"
    assert queue.loc[0, "blocker"] == "Completo"
    assert queue.loc[0, "next_step"] == "Confirmar ticket"
    assert queue.loc[0, "action"] == "Preparar paper: confirmar stop, target y tamaño."
    assert queue.loc[1, "tone"] == "watch"
    assert queue.loc[1, "urgency"] == "Vigilar cerca"
    assert queue.loc[1, "blocker"] == "Falta 15m"
    assert queue.loc[1, "next_step"] == "Esperar gatillo 15m"
    assert queue.loc[1, "action"] == "Esperar gatillo"
    assert queue.loc[2, "tone"] == "avoid"
    assert queue.loc[2, "urgency"] == "No tocar"
    assert queue.loc[2, "blocker"] == "No tocar"
    assert queue.loc[2, "next_step"] == "No tocar"


def test_trading_desk_urgency_label_marks_operational_timing():
    assert trading_desk_urgency_label("Operar", "Paper listo", 90, 1.8, 1.4) == "Ahora"
    assert trading_desk_urgency_label("Operar", "Paper listo", 76, 3.0, 0.9) == "Lista"
    assert trading_desk_urgency_label("Operar", "Bloq riesgo", 88, 4.0, 1.6) == "Bloqueada"
    assert trading_desk_urgency_label("Vigilar", "Setup", 88, 2.2, 0.9) == "Vigilar cerca"
    assert trading_desk_urgency_label("Vigilar", "Setup", 70, 2.2, 0.9) == "Esperar"
    assert trading_desk_urgency_label("Evitar", "No tocar", 99, 7.0, 2.0) == "No tocar"


def test_trading_desk_paper_state_flags_blockers():
    assert trading_desk_paper_state(status="Operar", risk=0.018, target=0.03, rel_volume=1.2, htf="2/2") == "Paper listo"
    assert trading_desk_paper_state(status="Vigilar", risk=0.018, target=0.03, rel_volume=1.2, htf="2/2") == "Setup"
    assert trading_desk_paper_state(status="Evitar", risk=0.018, target=0.03, rel_volume=1.2, htf="2/2") == "No tocar"
    assert trading_desk_paper_state(status="Operar", risk=0.06, target=0.01, rel_volume=0.4, htf="0/2") == "Bloq riesgo/target"
