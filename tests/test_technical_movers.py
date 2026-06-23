import pandas as pd

from streamlit_app import technical_mover_rows


def test_technical_mover_rows_groups_breakouts_pullbacks_and_weakness():
    scan = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "score": 95,
                "setup": "TREND_CONTINUATION",
                "raw_signal": "BUY",
                "dist_sma20_pct": 1.8,
                "dist_sma200_pct": 12.0,
                "relative_volume": 1.4,
            },
            {
                "symbol": "MSFT",
                "score": 89,
                "setup": "PULLBACK",
                "raw_signal": "WATCH",
                "dist_sma20_pct": -1.2,
                "dist_sma200_pct": 8.0,
                "relative_volume": 0.9,
            },
            {
                "symbol": "TSLA",
                "score": 40,
                "setup": "DOWNTREND",
                "raw_signal": "AVOID",
                "dist_sma20_pct": -4.0,
                "dist_sma200_pct": -9.0,
                "relative_volume": 1.8,
            },
        ]
    )

    rows = technical_mover_rows(scan, limit_per_lane=2)
    by_symbol = {row["symbol"]: row for row in rows.to_dict("records")}

    assert rows.columns.tolist() == ["lane", "tone", "symbol", "score", "setup", "move", "sma200", "rel_volume"]
    assert by_symbol["AAPL"]["lane"] == "Ruptura"
    assert by_symbol["AAPL"]["tone"] == "buy"
    assert by_symbol["MSFT"]["lane"] == "Pullback"
    assert by_symbol["MSFT"]["tone"] == "watch"
    assert by_symbol["TSLA"]["lane"] == "Debilidad"
    assert by_symbol["TSLA"]["tone"] == "avoid"


def test_technical_mover_rows_limits_each_lane_independently():
    scan = pd.DataFrame(
        [
            {"symbol": "A", "score": 90, "setup": "TREND_CONTINUATION", "raw_signal": "BUY", "dist_sma20_pct": 1.0, "dist_sma200_pct": 5.0, "relative_volume": 1.0},
            {"symbol": "B", "score": 80, "setup": "TREND_CONTINUATION", "raw_signal": "BUY", "dist_sma20_pct": 0.5, "dist_sma200_pct": 4.0, "relative_volume": 1.2},
            {"symbol": "C", "score": 70, "setup": "PULLBACK", "raw_signal": "WATCH", "dist_sma20_pct": -0.7, "dist_sma200_pct": 6.0, "relative_volume": 0.8},
            {"symbol": "D", "score": 60, "setup": "DOWNTREND", "raw_signal": "AVOID", "dist_sma20_pct": -1.5, "dist_sma200_pct": -2.0, "relative_volume": 1.1},
        ]
    )

    rows = technical_mover_rows(scan, limit_per_lane=1)

    assert rows["lane"].value_counts().to_dict() == {"Ruptura": 1, "Pullback": 1, "Debilidad": 1}
    assert rows[rows["lane"].eq("Ruptura")]["symbol"].tolist() == ["A"]
