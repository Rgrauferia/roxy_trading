from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from monetization_readiness import (
    PROFITABILITY_MIN_CLOSED,
    SIGNAL_VALIDATION_MIN_CLOSED,
    backtest_profitability_summary,
    build_monetization_readiness_report,
    combined_paper_monetization_summary,
    paper_weekly_consistency_summary,
    subscription_scenarios,
)


def _closed_rows_by_week(*, weeks: int, hits_per_week: int, stops_per_week: int = 0) -> list[dict]:
    rows: list[dict] = []
    start = datetime(2026, 1, 1, 14, 30, tzinfo=timezone.utc)
    for week in range(weeks):
        ts = (start + timedelta(days=week * 7)).isoformat()
        rows.extend(
            {
                "ts": ts,
                "status": "CLOSED_HIT_2",
                "closed_outcome": "HIT_2",
                "closed_move_pct": 0.02,
            }
            for _ in range(hits_per_week)
        )
        rows.extend(
            {
                "ts": ts,
                "status": "CLOSED_STOP",
                "closed_outcome": "STOP",
                "closed_move_pct": -0.01,
            }
            for _ in range(stops_per_week)
        )
    return rows


def test_monetization_report_does_not_treat_blocked_candidates_as_tracked_evidence():
    journal = pd.DataFrame(
        [
            {"status": "BLOCKED", "closed_outcome": "", "closed_move_pct": ""}
            for _ in range(25)
        ]
    )

    report = build_monetization_readiness_report(
        accuracy_report={"headline": {"measured": 0}},
        alpaca_journal=journal,
        live_status={"source_freshness": {"status": "FRESH", "alerts_allowed": True}},
        live_orders_enabled=False,
    )

    assert report["stage"] == "PRIVATE_ALPHA"
    assert report["beta_ready"] is False
    assert report["signal_validated"] is False
    assert "alpha privada" in report["can_sell_as"]
    assert "garantia" in report["cannot_sell_as"]
    assert report["paper_summary"]["candidates"] == 25
    assert report["paper_summary"]["tracked"] == 0
    assert report["paper_summary"]["blocked"] == 25
    assert report["paper_summary"]["closed"] == 0
    assert report["warnings"]


def test_monetization_report_requires_live_freshness_and_live_orders_off():
    journal = pd.DataFrame([{"status": "READY_FOR_PAPER"} for _ in range(40)])

    report = build_monetization_readiness_report(
        accuracy_report={"headline": {"measured": 0}},
        alpaca_journal=journal,
        live_status={"source_freshness": {"status": "STALE", "alerts_allowed": False}},
        live_orders_enabled=True,
    )

    assert report["stage"] == "FOUNDATION_BLOCKED"
    assert report["beta_ready"] is False
    assert len(report["blockers"]) == 2


def test_monetization_report_marks_signal_validation_after_enough_closed_results():
    journal = pd.DataFrame(_closed_rows_by_week(weeks=4, hits_per_week=25))

    report = build_monetization_readiness_report(
        accuracy_report={"headline": {"measured": SIGNAL_VALIDATION_MIN_CLOSED}},
        alpaca_journal=journal,
        live_status={"source_freshness": {"status": "FRESH", "alerts_allowed": True}},
        live_orders_enabled=False,
    )

    assert report["stage"] == "SIGNAL_VALIDATION_READY"
    assert report["signal_validated"] is True
    assert report["paper_summary"]["hit_2_rate"] == 1.0
    assert report["profitability_validation"]["stage"] == "PAPER_VALIDATED"
    assert report["profitability_validation"]["can_claim_profitability"] is True


def test_profitability_validation_marks_backtest_promising_but_not_proven():
    journal = pd.DataFrame([{"status": "BLOCKED"} for _ in range(25)])
    backtests = pd.DataFrame(
        [
            {
                "symbol": f"SYM{index}",
                "eligible": True,
                "total_return_pct": 0.08 + (index * 0.001),
                "win_rate": 0.43,
                "profit_factor": 2.1,
                "max_drawdown_pct": 0.06,
            }
            for index in range(12)
        ]
    )

    report = build_monetization_readiness_report(
        accuracy_report={"headline": {"measured": 0}},
        alpaca_journal=journal,
        backtest_rows=backtests,
        live_status={"source_freshness": {"status": "FRESH", "alerts_allowed": True}},
        live_orders_enabled=False,
    )

    profitability = report["profitability_validation"]
    assert profitability["stage"] == "BACKTEST_PROMISING"
    assert profitability["can_claim_profitability"] is False
    assert profitability["backtest"]["avg_profit_factor"] == pytest.approx(2.1)
    assert profitability["backtest"]["promising"] is True


def test_profitability_validation_requires_closed_paper_before_claims():
    journal = pd.DataFrame(_closed_rows_by_week(weeks=10, hits_per_week=7, stops_per_week=3))

    report = build_monetization_readiness_report(
        accuracy_report={"headline": {"measured": PROFITABILITY_MIN_CLOSED}},
        alpaca_journal=journal,
        live_status={"source_freshness": {"status": "FRESH", "alerts_allowed": True}},
        live_orders_enabled=False,
    )

    profitability = report["profitability_validation"]
    assert profitability["stage"] == "PAPER_VALIDATED"
    assert profitability["can_claim_profitability"] is True
    assert profitability["paper_hit_2_rate"] == 0.7
    assert profitability["paper_stop_rate"] == 0.3
    assert profitability["weekly"]["consistent"] is True


def test_weekly_consistency_requires_results_across_multiple_weeks():
    one_week_journal = pd.DataFrame(_closed_rows_by_week(weeks=1, hits_per_week=100))
    multi_week_journal = pd.DataFrame(_closed_rows_by_week(weeks=4, hits_per_week=25))

    one_week = paper_weekly_consistency_summary(one_week_journal)
    multi_week = paper_weekly_consistency_summary(multi_week_journal)

    assert one_week["consistent"] is False
    assert one_week["consistent_weeks"] == 1
    assert multi_week["consistent"] is True
    assert multi_week["weeks_observed"] == 4


def test_backtest_profitability_summary_uses_eligible_rows():
    rows = pd.DataFrame(
        [
            {"symbol": "A", "eligible": True, "total_return_pct": 0.20, "profit_factor": 2.0, "max_drawdown_pct": 0.05},
            {"symbol": "B", "eligible": False, "total_return_pct": -0.50, "profit_factor": 0.2, "max_drawdown_pct": 0.30},
        ]
        + [
            {
                "symbol": f"E{index}",
                "eligible": True,
                "total_return_pct": 0.03,
                "profit_factor": 1.8,
                "max_drawdown_pct": 0.04,
            }
            for index in range(10)
        ]
    )

    summary = backtest_profitability_summary(rows)

    assert summary["rows"] == 12
    assert summary["eligible_rows"] == 11
    assert summary["promising"] is True
    assert "A" in summary["top_symbols"]


def test_combined_paper_summary_counts_crypto_and_alpaca_results():
    alpaca = pd.DataFrame(
        [
            {"status": "CLOSED_STOP", "closed_outcome": "STOP", "closed_move_pct": -0.01},
            {"status": "READY_FOR_PAPER", "closed_outcome": ""},
        ]
    )
    crypto = pd.DataFrame(
        [{"status": "CLOSED_HIT_5", "closed_outcome": "HIT_5", "closed_move_pct": 0.052}]
    )

    summary = combined_paper_monetization_summary(alpaca, crypto)

    assert summary["tracked"] == 3
    assert summary["candidates"] == 3
    assert summary["closed"] == 2
    assert summary["hit_2"] == 1
    assert summary["hit_5"] == 1
    assert summary["stops"] == 1
    assert summary["hit_2_rate"] == 0.5
    assert summary["stop_rate"] == 0.5


def test_paper_summary_collapses_correlated_scanner_snapshots_into_one_episode():
    rows = pd.DataFrame(
        [
            {
                "ts": f"2026-06-22T12:{minute:02d}:00+00:00",
                "market": "crypto",
                "symbol": "ETH/USD",
                "strategy_family": "Pullback",
                "timeframe": "15m",
                "status": "CLOSED_HIT_5",
                "closed_outcome": "HIT_5",
                "closed_at": "2026-06-23T10:00:00+00:00",
            }
            for minute in (0, 5, 10, 15)
        ]
    )

    summary = combined_paper_monetization_summary(crypto_journal=rows)

    assert summary["candidates"] == 4
    assert summary["tracked"] == 1
    assert summary["closed"] == 1
    assert summary["hit_5"] == 1
    assert summary["duplicates_collapsed"] == 3


def test_subscription_scenarios_apply_store_commission():
    rows = subscription_scenarios(commission_rate=0.15)

    assert rows[0]["gross_monthly"] == 1900.0
    assert rows[0]["net_monthly_after_store"] == 1615.0
    assert rows[1]["tier"] == "Pro Trader"
