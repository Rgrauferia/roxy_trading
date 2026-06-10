import pandas as pd

from streamlit_app import market_index_strip_rows


def test_market_index_strip_rows_reads_major_etfs_and_crypto_context():
    scan = pd.DataFrame(
        [
            {"symbol": "SPY", "signal": "WATCH", "score": 70, "setup": "NEUTRAL", "relative_volume": 1.2, "tf": "1h"},
            {"symbol": "QQQ", "signal": "WATCH", "score": 80, "setup": "TREND_CONTINUATION", "relative_volume": 1.4, "tf": "1h"},
        ]
    )
    confluence = pd.DataFrame(
        [
            {
                "symbol": "SPY",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_2PCT",
                "confluence_score": 88,
                "trigger_setup": "PULLBACK",
                "risk_pct": 0.02,
                "relative_volume_15m": 1.5,
                "entry_tf": "15m",
            },
            {
                "symbol": "BTC/USD",
                "signal": "AVOID",
                "trade_decision": "NO_TRADE_DOWNTREND",
                "confluence_score": 20,
                "trigger_setup": "DOWNTREND",
                "risk_pct": 0.05,
            },
        ]
    )

    rows = market_index_strip_rows(scan, confluence)
    by_symbol = {row["symbol"]: row for row in rows}

    assert by_symbol["SPY"]["status"] == "Operar"
    assert by_symbol["SPY"]["tone"] == "buy"
    assert by_symbol["SPY"]["score"] == 88
    assert by_symbol["SPY"]["relative_volume"] == 1.5
    assert by_symbol["QQQ"]["status"] == "Vigilar"
    assert by_symbol["BTC/USD"]["status"] == "Evitar"
    assert by_symbol["BTC/USD"]["tone"] == "avoid"
