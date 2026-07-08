import pandas as pd

from roxy_ai import extract_opportunities
from roxy_decision_engine import process_opportunity_with_decision, process_opportunities_with_decisions


def ready_row(**overrides):
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "signal": "BUY",
        "trade_decision": "TRADE_FOR_5PCT",
        "confluence_score": 90,
        "ai_score": 90,
        "trend_score": 86,
        "trigger_score": 80,
        "risk_pct": 0.015,
        "recommended_target_pct": 0.05,
        "entry": 100.0,
        "stop": 98.5,
        "recommended_target_price": 105.0,
        "relative_volume_15m": 1.35,
        "backtest_eligible": True,
        "trigger_setup": "EMA 9/21 Pullback",
        "trend_setup": "TREND_CONTINUATION",
        "chart_data_contract": {"gate": "LIVE_DATA_OK", "operable": True, "source": "test"},
        "source_freshness": {"alerts_allowed": True, "label": "Frescos", "detail": "test"},
    }
    row.update(overrides)
    return row


def test_decision_engine_marks_complete_setup_operate_now():
    row = process_opportunity_with_decision(ready_row(), enrich_knowledge=False)

    decision = row["roxy_decision"]
    assert decision["status"] == "OPERATE_NOW"
    assert decision["direction"] == "ARRIBA"
    assert decision["entry"] == 100.0
    assert decision["stop"] == 98.5
    assert decision["target"] == 105.0
    assert decision["reward_r"] >= 1.0
    assert not decision["missing_fields"]
    assert "orden limite" in " ".join(decision["execution_rules"]).lower()


def test_decision_engine_waits_when_operational_fields_are_missing():
    row = ready_row(entry=None, stop=None, recommended_target_price=None, risk_pct=None)
    row.pop("entry", None)
    row.pop("stop", None)
    row.pop("recommended_target_price", None)
    row.pop("risk_pct", None)

    decided = process_opportunity_with_decision(row, enrich_knowledge=False)

    decision = decided["roxy_decision"]
    assert decision["status"] == "WAIT_CONFIRMATION"
    assert {"entrada", "stop", "target", "riesgo"} <= set(decision["missing_fields"])
    assert decided["roxy_priority_score"] < 80


def test_decision_engine_blocks_stale_realtime_context():
    row = ready_row(
        source_freshness={"alerts_allowed": False, "label": "Estancados", "detail": "live viejo"},
    )

    decided = process_opportunity_with_decision(row, enrich_knowledge=False)

    assert decided["roxy_decision"]["status"] == "NO_TRADE"
    assert decided["roxy_decision"]["live_ok"] is False
    assert "live viejo" in decided["roxy_decision"]["live_detail"]


def test_decision_engine_includes_external_confirmation_context():
    row = ready_row(
        _external_market_rows=[
            {
                "source": "Finviz Elite",
                "symbol": "AAPL",
                "market": "stock",
                "price": 101.25,
                "change_pct": 1.2,
                "volume": 1_500_000,
                "signal": "Breakout",
            }
        ]
    )

    decided = process_opportunity_with_decision(row, enrich_knowledge=False)

    external = decided["roxy_decision"]["external_confirmation"]
    assert external["confirmed"] is True
    assert external["price"] == 101.25
    assert external["score_adjustment"] > 0
    assert "Confirmacion externa" in " ".join(decided["roxy_decision"]["reasons"])


def test_process_opportunities_sorts_operable_first():
    rows = [
        ready_row(symbol="MSFT", signal="WATCH", trade_decision="WAIT", confluence_score=72, ai_score=72),
        ready_row(symbol="AAPL"),
    ]

    decided = process_opportunities_with_decisions(rows, enrich_knowledge=False)

    assert decided[0]["symbol"] == "AAPL"
    assert decided[0]["roxy_decision_status"] == "OPERATE_NOW"


def test_extract_opportunities_adds_roxy_decision_profile():
    frame = pd.DataFrame([ready_row()])

    rows = extract_opportunities(frame, limit=1)

    assert len(rows) == 1
    assert rows[0]["symbol"] == "AAPL"
    assert rows[0]["roxy_decision"]["status"] in {"OPERATE_NOW", "WAIT_CONFIRMATION"}
    assert rows[0]["roxy_decision"]["next_action"]
