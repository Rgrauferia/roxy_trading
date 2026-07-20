import pandas as pd

from roxy_trader.operations import build_paper_operations_snapshot


def test_operations_snapshot_excludes_blocked_and_collapses_repeated_scans():
    crypto = pd.DataFrame(
        [
            {
                "ts": f"2026-06-22T12:{minute:02d}:00+00:00",
                "symbol": "ETH/USD",
                "market": "crypto",
                "strategy_family": "Pullback",
                "timeframe": "15m",
                "status": "CLOSED_HIT_5",
                "closed_outcome": "HIT_5",
                "closed_at": "2026-06-23T10:00:00+00:00",
                "entry": 100,
                "stop": 95,
                "take_profit": 105,
                "qty": 2,
                "notional": 200,
                "closed_move_pct": 0.05,
            }
            for minute in (0, 5, 10)
        ]
    )
    stocks = pd.DataFrame([{"status": "BLOCKED", "symbol": "AAPL", "ts": "2026-06-22T12:00:00Z"}])

    snapshot = build_paper_operations_snapshot(stocks, crypto)

    assert snapshot["mode"] == "PAPER_ONLY"
    assert snapshot["live_orders_enabled"] is False
    assert snapshot["summary"]["candidates"] == 4
    assert snapshot["summary"]["tracked"] == 1
    assert snapshot["summary"]["duplicates_collapsed"] == 2
    assert snapshot["summary"]["blocked"] == 1
    assert snapshot["summary"]["realized_pnl"] == 10.0
    assert snapshot["valuation"]["state"] == "REALIZED_PAPER_ONLY"
    assert snapshot["valuation"]["unrealized_pnl_available"] is False
    assert snapshot["valuation"]["broker_equity_included"] is False
    assert snapshot["operations"][0]["price_basis"] == "CLOSED_PAPER_RESULT"
    assert len(snapshot["operations"]) == 1


def test_operations_snapshot_applies_short_direction_to_closed_move():
    short = pd.DataFrame(
        [
            {
                "ts": "2026-07-19T12:00:00Z",
                "symbol": "TEST",
                "market": "stock",
                "strategy_family": "Breakdown",
                "timeframe": "15m",
                "status": "CLOSED_HIT_2",
                "closed_outcome": "HIT_2",
                "closed_move_pct": -0.02,
                "entry": 100,
                "qty": 3,
                "notional": 300,
                "side": "short",
            }
        ]
    )

    snapshot = build_paper_operations_snapshot(short, None)

    assert snapshot["summary"]["realized_pnl"] == 6.0
