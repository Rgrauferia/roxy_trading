import pandas as pd

from dashboard_metrics import (
    best_confluence_candidate,
    option_expiry_counts,
    option_quality_points,
    risk_score_points,
    score_distribution,
    setup_counts_by_timeframe,
    signal_counts_by_timeframe,
    target_ladder_counts,
    trade_decision_counts,
)


def test_signal_and_setup_counts_are_split_by_timeframe():
    scan = pd.DataFrame(
        [
            {"tf": "1h", "signal": "WATCH", "setup": "NEUTRAL", "score": 50, "symbol": "AAPL"},
            {"tf": "15m", "signal": "BUY", "setup": "PULLBACK", "score": 92, "symbol": "AAPL"},
            {"tf": "15m", "signal": "BUY", "setup": "PULLBACK", "score": 88, "symbol": "MSFT"},
            {"tf": "1h", "signal": "AVOID", "setup": "DOWNTREND", "score": 12, "symbol": "MSFT"},
        ]
    )

    signal_counts = signal_counts_by_timeframe(scan)
    setup_counts = setup_counts_by_timeframe(scan)
    scores = score_distribution(scan)

    assert signal_counts.to_dict("records")[0] == {"tf": "15m", "signal": "BUY", "count": 2}
    assert {"tf": "1h", "setup": "DOWNTREND", "count": 1} in setup_counts.to_dict("records")
    assert sorted(scores["score"].tolist()) == [12, 50, 88, 92]


def test_target_ladder_and_decision_counts_handle_csv_bool_strings():
    confluence = pd.DataFrame(
        [
            {
                "target_2pct_ok": "True",
                "target_5pct_ok": "true",
                "target_10pct_ok": "False",
                "trade_decision": "TRADE_FOR_5PCT",
            },
            {
                "target_2pct_ok": True,
                "target_5pct_ok": False,
                "target_10pct_ok": False,
                "trade_decision": "WAIT",
            },
        ]
    )

    ladder = target_ladder_counts(confluence)
    decisions = trade_decision_counts(confluence)

    assert ladder.to_dict("records") == [
        {"target": "2%", "count": 2},
        {"target": "5%", "count": 1},
        {"target": "10%", "count": 0},
    ]
    assert set(decisions["trade_decision"]) == {"TRADE_FOR_5PCT", "WAIT"}


def test_risk_score_points_prepare_percent_for_chart():
    confluence = pd.DataFrame(
        [
            {
                "market": "stock",
                "symbol": "NVDA",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_10PCT",
                "risk_pct": "0.025",
                "confluence_score": "94",
            }
        ]
    )

    points = risk_score_points(confluence)

    assert points.loc[0, "risk_pct"] == 0.025
    assert points.loc[0, "risk_display_pct"] == 2.5
    assert points.loc[0, "confluence_score"] == 94


def test_option_helpers_prepare_quality_and_expiry_views():
    options = pd.DataFrame(
        [
            {
                "symbol": "NVDA",
                "contractSymbol": "NVDA260619C00150000",
                "option_decision": "BUY_CALL",
                "option_score": "82",
                "spread_pct": "0.12",
                "breakeven_pct": "0.034",
                "dte": "13",
                "expiry": "2026-06-19",
            },
            {
                "symbol": "AMD",
                "contractSymbol": "AMD260619C00200000",
                "option_decision": "WATCH",
                "option_score": "65",
                "spread_pct": "0.18",
                "breakeven_pct": "0.05",
                "dte": "13",
                "expiry": "2026-06-19",
            },
        ]
    )

    quality = option_quality_points(options)
    expiries = option_expiry_counts(options)

    assert quality.loc[0, "spread_display_pct"] == 12.0
    assert quality.loc[0, "breakeven_display_pct"] == 3.4000000000000004
    assert expiries.to_dict("records") == [{"expiry": "2026-06-19", "count": 2}]


def test_best_confluence_candidate_prioritizes_actionable_trade():
    confluence = pd.DataFrame(
        [
            {
                "symbol": "SLOW",
                "signal": "WATCH",
                "trade_decision": "WAIT",
                "confluence_score": 99,
                "recommended_target_pct": None,
            },
            {
                "symbol": "FAST",
                "signal": "BUY",
                "trade_decision": "TRADE_FOR_5PCT",
                "confluence_score": 80,
                "recommended_target_pct": 0.05,
            },
        ]
    )

    best = best_confluence_candidate(confluence)

    assert best["symbol"] == "FAST"
    assert best["trade_decision"] == "TRADE_FOR_5PCT"
