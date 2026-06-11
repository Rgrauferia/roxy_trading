import pandas as pd

from streamlit_app import buy_readiness_gap_rows


def test_buy_readiness_gap_rows_lists_missing_buy_requirements():
    confluence = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "confluence_score": 95,
                "trigger_raw_signal": "BUY",
                "trend_signal": "WATCH",
                "trend_setup": "TREND_CONTINUATION",
                "higher_tf_confirmations": 2,
                "higher_tf_blocks": 0,
                "risk_pct": 0.018,
                "relative_volume_15m": 1.2,
                "target_2pct_ok": True,
                "backtest_eligible": True,
            },
            {
                "symbol": "MSFT",
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "confluence_score": 82,
                "trigger_raw_signal": "BUY",
                "trend_signal": "WATCH",
                "trend_setup": "EARLY_UPTREND",
                "higher_tf_confirmations": 1,
                "higher_tf_blocks": 1,
                "risk_pct": 0.05,
                "relative_volume_15m": 0.4,
                "target_2pct_ok": False,
                "backtest_eligible": False,
            },
        ]
    )

    rows = buy_readiness_gap_rows(confluence, limit=5)
    by_symbol = {row["symbol"]: row for row in rows.to_dict("records")}

    assert rows.columns.tolist() == ["symbol", "tone", "ready", "missing_count", "passed_count", "missing", "passed", "risk", "score", "decision"]
    assert by_symbol["AAPL"]["tone"] == "buy"
    assert by_symbol["AAPL"]["ready"] is True
    assert by_symbol["AAPL"]["missing"] == "Listo para operar"
    assert by_symbol["MSFT"]["tone"] == "watch"
    assert by_symbol["MSFT"]["missing_count"] == 5
    assert "2h/4h no bloquean" in by_symbol["MSFT"]["missing"]
    assert "riesgo <=3.5%" in by_symbol["MSFT"]["missing"]
    assert "volumen acompaña" in by_symbol["MSFT"]["missing"]
    assert "15m gatillo BUY" in by_symbol["MSFT"]["passed"]


def test_buy_readiness_gap_rows_handles_empty_input():
    rows = buy_readiness_gap_rows(pd.DataFrame())

    assert rows.columns.tolist() == ["symbol", "tone", "ready", "missing_count", "passed_count", "missing", "passed", "risk", "score", "decision"]
    assert rows.empty
