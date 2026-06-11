import pandas as pd

from streamlit_app import buy_gap_next_step, buy_readiness_blocker_summary, buy_readiness_gap_rows


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

    assert rows.columns.tolist() == ["symbol", "tone", "ready", "readiness_pct", "missing_count", "passed_count", "next_step", "missing", "passed", "risk", "score", "decision"]
    assert by_symbol["AAPL"]["tone"] == "buy"
    assert by_symbol["AAPL"]["ready"] is True
    assert by_symbol["AAPL"]["readiness_pct"] == 100
    assert by_symbol["AAPL"]["next_step"].startswith("Listo")
    assert by_symbol["AAPL"]["missing"] == "Listo para operar"
    assert by_symbol["MSFT"]["tone"] == "watch"
    assert by_symbol["MSFT"]["missing_count"] == 5
    assert by_symbol["MSFT"]["readiness_pct"] == 29
    assert "desbloqueo multi-timeframe" in by_symbol["MSFT"]["next_step"]
    assert "2h/4h no bloquean" in by_symbol["MSFT"]["missing"]
    assert "riesgo <=3.5%" in by_symbol["MSFT"]["missing"]
    assert "volumen acompaña" in by_symbol["MSFT"]["missing"]
    assert "15m gatillo BUY" in by_symbol["MSFT"]["passed"]


def test_buy_readiness_gap_rows_handles_empty_input():
    rows = buy_readiness_gap_rows(pd.DataFrame())

    assert rows.columns.tolist() == ["symbol", "tone", "ready", "readiness_pct", "missing_count", "passed_count", "next_step", "missing", "passed", "risk", "score", "decision"]
    assert rows.empty


def test_buy_gap_next_step_uses_first_blocker_as_action():
    assert buy_gap_next_step(["riesgo <=3.5%", "volumen acompaña"], False) == "Mejorar entrada/stop o descartar si el riesgo sigue alto."


def test_buy_readiness_blocker_summary_prioritizes_repeated_gap():
    confluence = pd.DataFrame(
        [
            {
                "symbol": "WMT",
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "confluence_score": 88,
                "trigger_raw_signal": "BUY",
                "trend_signal": "WATCH",
                "trend_setup": "CHANNEL_BREAK",
                "higher_tf_confirmations": 2,
                "higher_tf_blocks": 0,
                "risk_pct": 0.022,
                "relative_volume_15m": 1.1,
                "target_2pct_ok": False,
                "backtest_eligible": True,
            },
            {
                "symbol": "SCHW",
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "confluence_score": 84,
                "trigger_raw_signal": "BUY",
                "trend_signal": "WATCH",
                "trend_setup": "PULLBACK",
                "higher_tf_confirmations": 1,
                "higher_tf_blocks": 0,
                "risk_pct": 0.026,
                "relative_volume_15m": 0.9,
                "target_2pct_ok": False,
                "backtest_eligible": True,
            },
            {
                "symbol": "COST",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "confluence_score": 90,
                "trigger_raw_signal": "BUY",
                "trend_signal": "BUY",
                "trend_setup": "TREND_CONTINUATION",
                "higher_tf_confirmations": 2,
                "higher_tf_blocks": 0,
                "risk_pct": 0.017,
                "relative_volume_15m": 1.3,
                "target_2pct_ok": True,
                "backtest_eligible": True,
            },
        ]
    )

    summary = buy_readiness_blocker_summary(confluence)

    assert summary["dominant"] == "target 2% viable"
    assert summary["count"] == 2
    assert summary["ready"] == 1
    assert summary["watch"] == 2
    assert summary["avoid"] == 0
    assert summary["avg_readiness"] is not None
    assert "target mínimo 2%" in summary["next_step"]
    assert summary["symbols"] == "WMT · SCHW"
