import pandas as pd

from streamlit_app import scanner_breadth_summary


def test_scanner_breadth_summary_measures_scan_and_confluence_strength():
    scan = pd.DataFrame(
        [
            {"symbol": "AAPL", "signal": "WATCH", "raw_signal": "BUY", "score": 92, "dist_sma200_pct": 4.2, "relative_volume": 1.5, "tf": "15m"},
            {"symbol": "NVDA", "signal": "WATCH", "raw_signal": "WATCH", "score": 74, "dist_sma200_pct": -1.0, "relative_volume": 0.8, "tf": "1h"},
            {"symbol": "MSFT", "signal": "WATCH", "raw_signal": "BUY", "score": 81, "dist_sma200_pct": 2.1, "relative_volume": 1.3, "tf": "15m"},
        ]
    )
    confluence = pd.DataFrame(
        [
            {"symbol": "AAPL", "signal": "BUY", "confluence_score": 82, "risk_pct": 0.02},
            {"symbol": "NVDA", "signal": "WATCH", "confluence_score": 71, "risk_pct": 0.04},
        ]
    )

    rows = {row["label"]: row for row in scanner_breadth_summary(scan, confluence)}

    assert rows["BUY crudo"]["positive"] == 2
    assert rows["Sobre SMA200"]["pct"] == 2 / 3 * 100
    assert rows["Score >=80"]["positive"] == 2
    assert rows["Volumen >1.2x"]["positive"] == 2
    assert rows["Marco dominante"]["detail"] == "15m"
    assert rows["Confluencia BUY"]["positive"] == 1
    assert rows["Riesgo <=3.5%"]["positive"] == 1
