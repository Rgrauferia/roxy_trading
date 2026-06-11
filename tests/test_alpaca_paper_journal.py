from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from streamlit_app import (
    alpaca_paper_chart_markers,
    alpaca_paper_journal_snapshot,
    alpaca_paper_strategy_ranking,
    alpaca_time_ago,
)


def test_alpaca_time_ago_formats_recent_durations():
    now = datetime(2026, 6, 11, 12, 0, 0)

    assert alpaca_time_ago(datetime(2026, 6, 11, 11, 58, 0), now=now) == "2m"
    assert alpaca_time_ago(datetime(2026, 6, 11, 9, 0, 0), now=now) == "3h"
    assert alpaca_time_ago(datetime(2026, 6, 8, 12, 0, 0), now=now) == "3d"


def test_alpaca_paper_journal_snapshot_reads_positions_and_orders():
    calls = {}

    class FakeClient:
        def get_all_positions(self):
            return [
                SimpleNamespace(
                    symbol="AAPL",
                    qty="2",
                    avg_entry_price="100.00",
                    current_price="105.00",
                    market_value="210.00",
                    unrealized_pl="10.00",
                    unrealized_plpc="0.05",
                )
            ]

        def get_orders(self):
            return [
                SimpleNamespace(
                    symbol="AAPL",
                    side="buy",
                    status="filled",
                    qty="2",
                    filled_qty="2",
                    type="market",
                    order_class="bracket",
                    submitted_at=datetime(2026, 6, 11, 10, 0, 0),
                    filled_at=datetime(2026, 6, 11, 10, 5, 0),
                    limit_price=None,
                    stop_price=None,
                )
            ]

    def factory(api_key, secret_key):
        calls["api_key"] = api_key
        calls["secret_key"] = secret_key
        return FakeClient()

    snapshot = alpaca_paper_journal_snapshot(
        {"ALPACA_API_KEY": "paper-key-value", "ALPACA_API_SECRET": "paper-secret-value"},
        client_factory=factory,
        now=datetime(2026, 6, 11, 12, 5, 0),
    )

    assert snapshot["connected"] is True
    assert snapshot["status"] == "Paper journal conectado"
    assert snapshot["summary"]["open_positions"] == 1
    assert snapshot["summary"]["recent_orders"] == 1
    assert snapshot["summary"]["unrealized_pl"] == 10.0
    assert snapshot["summary"]["exposure"] == 210.0
    assert snapshot["positions"][0]["symbol"] == "AAPL"
    assert snapshot["positions"][0]["time_in_trade"] == "2h"
    assert snapshot["orders"][0]["status"] == "FILLED"
    assert calls == {"api_key": "paper-key-value", "secret_key": "paper-secret-value"}
    assert "paper-key-value" not in str(snapshot)
    assert "paper-secret-value" not in str(snapshot)


def test_alpaca_paper_journal_snapshot_blocks_live_before_client_call():
    called = False

    def factory(api_key, secret_key):
        nonlocal called
        called = True
        raise AssertionError("client should not be created for live endpoint")

    snapshot = alpaca_paper_journal_snapshot(
        {
            "ALPACA_API_KEY": "live-key-value",
            "ALPACA_API_SECRET": "live-secret-value",
            "ALPACA_PAPER": "false",
            "ALPACA_BASE_URL": "https://api.alpaca.markets",
        },
        client_factory=factory,
    )

    assert called is False
    assert snapshot["connected"] is False
    assert snapshot["status"] == "Paper journal pendiente"
    assert "live-key-value" not in str(snapshot)
    assert "live-secret-value" not in str(snapshot)


def test_alpaca_paper_strategy_ranking_groups_activity_by_setup():
    snapshot = {
        "positions": [
            {"symbol": "AAPL", "unrealized_pl": 12.0, "market_value": 220.0},
            {"symbol": "MSFT", "unrealized_pl": -5.0, "market_value": 300.0},
        ],
        "orders": [
            {"symbol": "AAPL", "status": "FILLED"},
            {"symbol": "MSFT", "status": "FILLED"},
            {"symbol": "TSLA", "status": "NEW"},
        ],
    }
    opportunities = pd.DataFrame(
        [
            {"symbol": "AAPL", "strategy_family": "Pullback"},
            {"symbol": "MSFT", "strategy_family": "Canal alcista"},
            {"symbol": "TSLA", "strategy_family": "Breakout"},
        ]
    )

    rows = alpaca_paper_strategy_ranking(snapshot, opportunities)

    assert list(rows.columns) == ["strategy", "symbols", "open_positions", "orders", "pnl", "exposure", "win_rate", "tone"]
    by_strategy = {row["strategy"]: row for row in rows.to_dict("records")}
    assert by_strategy["Pullback"]["symbols"] == "AAPL"
    assert by_strategy["Pullback"]["open_positions"] == 1
    assert by_strategy["Pullback"]["orders"] == 1
    assert by_strategy["Pullback"]["pnl"] == 12.0
    assert by_strategy["Pullback"]["win_rate"] == 1.0
    assert by_strategy["Canal alcista"]["tone"] == "avoid"
    assert by_strategy["Breakout"]["orders"] == 1
    assert by_strategy["Breakout"]["open_positions"] == 0


def test_alpaca_paper_chart_markers_places_filled_orders_on_chart():
    chart_window = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2026-06-11T10:00:00", "2026-06-11T10:05:00", "2026-06-11T10:10:00"]),
            "close": [100.0, 101.5, 102.0],
        }
    )
    snapshot = {
        "orders": [
            {
                "symbol": "AAPL",
                "side": "BUY",
                "status": "FILLED",
                "filled_at": "2026-06-11T10:05:00",
                "filled_avg_price": 101.25,
            },
            {
                "symbol": "AAPL",
                "side": "SELL",
                "status": "FILLED",
                "filled_at": "2026-06-11T10:10:00",
                "filled_avg_price": 102.0,
            },
            {
                "symbol": "MSFT",
                "side": "BUY",
                "status": "FILLED",
                "filled_at": "2026-06-11T10:05:00",
                "filled_avg_price": 300.0,
            },
        ],
        "positions": [],
    }

    markers = alpaca_paper_chart_markers(snapshot, chart_window, "AAPL")

    assert markers[["event", "side", "price", "tone"]].to_dict("records") == [
        {"event": "Paper entrada", "side": "BUY", "price": 101.25, "tone": "buy"},
        {"event": "Paper salida", "side": "SELL", "price": 102.0, "tone": "avoid"},
    ]
    assert markers["label"].tolist() == ["Paper entrada AAPL 101.25", "Paper salida AAPL 102.00"]
