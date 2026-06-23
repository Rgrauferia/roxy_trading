import pandas as pd

from streamlit_app import confluence_validation_rows


def test_confluence_validation_rows_formats_multitimeframe_gates():
    confluence = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "confluence_score": 91,
                "trigger_setup": "PULLBACK",
                "trend_setup": "TREND_CONTINUATION",
                "higher_tf_confirmations": 2,
                "higher_tf_blocks": 0,
                "risk_pct": 0.018,
                "target_2pct_ok": True,
                "backtest_eligible": True,
                "backtest_profit_factor": 1.63,
                "reasons": "1h confirma; 2h confirma",
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
                "risk_pct": 0.031,
                "target_2pct_ok": False,
                "backtest_eligible": False,
                "backtest_profit_factor": 0.8,
                "reasons": "Falta cierre 15m",
            },
            {
                "symbol": "TSLA",
                "signal": "AVOID",
                "trade_decision": "NO_TRADE_DOWNTREND",
                "confluence_score": 20,
                "trigger_setup": "DOWNTREND",
                "trend_setup": "DOWNTREND",
                "higher_tf_confirmations": 0,
                "higher_tf_blocks": 2,
                "risk_pct": 0.08,
                "target_2pct_ok": False,
                "backtest_eligible": True,
                "backtest_profit_factor": 1.2,
                "reasons": "2h y 4h bloquean",
            },
        ]
    )

    rows = confluence_validation_rows(confluence, limit=3)
    by_symbol = {row["symbol"]: row for row in rows.to_dict("records")}

    assert rows.columns.tolist() == ["symbol", "tone", "decision", "trigger", "trend", "htf", "risk", "target_2pct", "backtest", "reason"]
    assert by_symbol["AAPL"]["tone"] == "buy"
    assert by_symbol["AAPL"]["decision"] == "Validado"
    assert by_symbol["AAPL"]["htf"] == "2/2"
    assert by_symbol["AAPL"]["target_2pct"] == "2% OK"
    assert by_symbol["AAPL"]["backtest"] == "PF 1.6"
    assert by_symbol["MSFT"]["tone"] == "watch"
    assert by_symbol["MSFT"]["target_2pct"] == "2% falta"
    assert by_symbol["MSFT"]["backtest"] == "No hist"
    assert by_symbol["TSLA"]["tone"] == "avoid"
    assert by_symbol["TSLA"]["decision"] == "Bloqueado"
