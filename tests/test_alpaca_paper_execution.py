import pandas as pd

from streamlit_app import (
    alpaca_paper_order_candidates,
    focused_opportunity_table,
    submit_alpaca_paper_bracket_order,
)


def test_alpaca_paper_order_candidates_builds_bracket_from_ready_setups():
    table = focused_opportunity_table(
        {
            "opportunities": [
                {
                    "ai_action": "ALERT",
                    "symbol": "WMT",
                    "market": "stock",
                    "ai_score": 94,
                    "signal": "BUY",
                    "trade_decision": "TRADE_FOR_2PCT",
                    "entry": 120.0,
                    "stop": 118.0,
                    "recommended_target_pct": 0.04,
                    "reason": "Canal alcista confirmado.",
                },
                {
                    "ai_action": "WATCH",
                    "symbol": "MSFT",
                    "market": "stock",
                    "signal": "WATCH",
                    "trade_decision": "WAIT",
                    "entry": 300.0,
                    "stop": 295.0,
                    "recommended_target_pct": 0.03,
                },
            ]
        }
    )

    rows = alpaca_paper_order_candidates(table, account_equity=500.0, risk_pct=0.01)

    assert rows.columns.tolist() == ["symbol", "side", "qty", "entry", "stop", "take_profit", "risk_dollars", "notional", "reason"]
    assert len(rows) == 1
    assert rows.iloc[0]["symbol"] == "WMT"
    assert rows.iloc[0]["qty"] == 2
    assert rows.iloc[0]["take_profit"] == 124.8
    assert rows.iloc[0]["risk_dollars"] == 4.0


def test_alpaca_paper_order_candidates_skip_crypto_and_missing_levels():
    table = pd.DataFrame(
        [
            {"action": "ALERT", "symbol": "BTC/USD", "market": "crypto", "signal": "BUY", "decision": "TRADE_FOR_2PCT", "entry": 1, "stop": 0.9, "target_price": 1.1},
            {"action": "ALERT", "symbol": "AAPL", "market": "stock", "signal": "BUY", "decision": "TRADE_FOR_2PCT", "entry": 180.0, "stop": None, "target_price": 185.0},
        ]
    )

    assert alpaca_paper_order_candidates(table).empty


def test_submit_alpaca_paper_bracket_order_blocks_live_env_before_client_call():
    called = False

    def factory(api_key, secret_key):
        nonlocal called
        called = True
        raise AssertionError("should not create client for live env")

    result = submit_alpaca_paper_bracket_order(
        {"symbol": "WMT", "qty": 1, "stop": 118.0, "take_profit": 124.0},
        env={
            "ALPACA_API_KEY": "live-key-value",
            "ALPACA_API_SECRET": "live-secret-value",
            "ALPACA_PAPER": "false",
            "ALPACA_BASE_URL": "https://api.alpaca.markets",
        },
        client_factory=factory,
    )

    assert called is False
    assert result["submitted"] is False
    assert result["status"] == "blocked"
    assert "live-key-value" not in str(result)
    assert "live-secret-value" not in str(result)


def test_submit_alpaca_paper_bracket_order_submits_with_fake_paper_client():
    submitted = {}

    class FakeClient:
        def submit_order(self, order_data):
            submitted.update(order_data)
            return {"id": "paper-order-1"}

    def factory(api_key, secret_key):
        submitted["api_key_seen"] = api_key
        submitted["secret_seen"] = secret_key
        return FakeClient()

    result = submit_alpaca_paper_bracket_order(
        {"symbol": "WMT", "qty": 2, "stop": 118.0, "take_profit": 124.0},
        env={"ALPACA_API_KEY": "paper-key-value", "ALPACA_API_SECRET": "paper-secret-value"},
        client_factory=factory,
    )

    assert result["submitted"] is True
    assert result["status"] == "submitted"
    assert result["order_id"] == "paper-order-1"
    assert submitted["symbol"] == "WMT"
    assert submitted["qty"] == 2
    assert submitted["order_class"] == "bracket"
    assert submitted["take_profit"] == 124.0
    assert submitted["stop_loss"] == 118.0
    assert "paper-key-value" not in str(result)
    assert "paper-secret-value" not in str(result)
