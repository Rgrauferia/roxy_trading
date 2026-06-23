import pandas as pd

from ma_reporting import build_scan_summary, render_scan_report


def test_build_scan_summary_splits_buy_and_filtered_buy():
    df = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "INTC",
                "signal": "BUY",
                "raw_signal": "BUY",
                "backtest_eligible": True,
                "setup": "PULLBACK",
                "score": 100,
                "backtest_total_return_pct": 0.34,
                "backtest_buy_hold_edge_pct": 0.04,
                "backtest_profit_factor": 5.6,
                "backtest_trades": 16,
            },
            {
                "market": "stock",
                "symbol": "AAPL",
                "signal": "WATCH",
                "raw_signal": "BUY",
                "backtest_eligible": False,
                "setup": "TREND_CONTINUATION",
                "score": 100,
                "backtest_total_return_pct": -0.01,
                "backtest_buy_hold_edge_pct": -0.22,
                "backtest_profit_factor": 0.8,
                "backtest_trades": 19,
            },
        ]
    )

    summary = build_scan_summary(df)

    assert summary["rows"] == 2
    assert summary["signal_counts"] == {"BUY": 1, "WATCH": 1}
    assert summary["raw_signal_counts"] == {"BUY": 2}
    assert summary["buy_count"] == 1
    assert summary["filtered_buy_count"] == 1
    assert summary["buy"][0]["symbol"] == "INTC"
    assert summary["filtered_buy"][0]["symbol"] == "AAPL"


def test_render_scan_report_contains_key_sections():
    summary = {
        "generated_at": "2026-01-01T00:00:00",
        "rows": 1,
        "signal_counts": {"BUY": 1},
        "raw_signal_counts": {"BUY": 1},
        "buy_count": 1,
        "filtered_buy_count": 0,
        "eligible_watch_count": 0,
        "buy": [{"market": "stock", "symbol": "INTC", "tf": "15m", "signal": "BUY", "raw_signal": "BUY"}],
        "filtered_buy": [],
        "eligible_watch": [],
    }

    report = render_scan_report(summary, scan_path="output/example.csv")

    assert "BUY after backtest filter" in report
    assert "Raw BUY downgraded by backtest filter" in report
    assert "stock INTC 15m" in report
