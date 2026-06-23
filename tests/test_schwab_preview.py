import pytest

from platform_execution import LIVE_EXECUTION_FLAG, build_order_preview
from platform_router import build_platform_ticket
from schwab_preview import build_schwab_limit_order_payload, build_schwab_preview, schwab_whole_quantity


SCHWAB_ENV = {
    LIVE_EXECUTION_FLAG: "1",
    "SCHWAB_CLIENT_ID": "id",
    "SCHWAB_CLIENT_SECRET": "secret",
    "SCHWAB_REDIRECT_URI": "http://localhost/callback",
    "SCHWAB_ACCESS_TOKEN": "token",
    "SCHWAB_ACCOUNT_HASH": "hash",
}


def test_schwab_stock_payload_is_single_limit_equity_order():
    ticket = build_platform_ticket(
        {"market": "stock", "symbol": "AAPL", "signal": "BUY", "decision": "TRADE_FOR_2PCT", "entry": 200, "stop": 195},
        account_equity=500,
        risk_per_trade_pct=0.01,
    )

    payload = build_schwab_limit_order_payload(ticket)

    assert payload["session"] == "NORMAL"
    assert payload["duration"] == "DAY"
    assert payload["orderType"] == "LIMIT"
    assert payload["price"] == "200.00"
    assert payload["orderStrategyType"] == "SINGLE"
    assert payload["orderLegCollection"][0]["instrument"] == {"symbol": "AAPL", "assetType": "EQUITY"}
    assert payload["orderLegCollection"][0]["quantity"] == 1


def test_schwab_option_payload_uses_contract_symbol_and_option_asset_type():
    ticket = build_platform_ticket(
        {
            "market": "stock",
            "symbol": "AAPL",
            "contractSymbol": "AAPL260619C00220000",
            "signal": "BUY",
            "decision": "TRADE_FOR_2PCT",
            "entry": 5,
            "stop": 4,
        },
        preferred_product="option",
        account_equity=500,
        risk_per_trade_pct=0.01,
    )

    payload = build_schwab_limit_order_payload(ticket)

    assert payload["price"] == "5.00"
    assert payload["orderLegCollection"][0]["instrument"] == {
        "symbol": "AAPL260619C00220000",
        "assetType": "OPTION",
    }
    assert payload["orderLegCollection"][0]["quantity"] == 5


def test_schwab_preview_rounds_fractional_stock_quantity_and_blocks_api_ready():
    ticket = build_platform_ticket(
        {"market": "stock", "symbol": "NVDA", "signal": "BUY", "decision": "TRADE_FOR_2PCT", "entry": 100, "stop": 97},
        account_equity=500,
        risk_per_trade_pct=0.01,
    )
    ticket["quantity"] = 1.666667
    order_preview = build_order_preview(ticket, env=SCHWAB_ENV)

    preview = build_schwab_preview(ticket, order_preview=order_preview)

    assert preview["applicable"] is True
    assert preview["payload"]["orderLegCollection"][0]["quantity"] == 1
    assert preview["api_preview_ready"] is False
    assert "rounded 1.666667 to 1" in " ".join(preview["blockers"])


def test_schwab_preview_can_be_ready_when_payload_and_gate_are_clean():
    ticket = build_platform_ticket(
        {"market": "stock", "symbol": "AAPL", "signal": "BUY", "decision": "TRADE_FOR_2PCT", "entry": 200, "stop": 195},
        account_equity=500,
        risk_per_trade_pct=0.01,
    )
    order_preview = build_order_preview(ticket, env=SCHWAB_ENV)

    preview = build_schwab_preview(ticket, order_preview=order_preview)

    assert preview["api_preview_ready"] is True
    assert preview["preview_endpoint"].endswith("/accounts/{accountHash}/previewOrder")
    assert "token" not in str(preview)
    assert "hash" not in str(preview)


def test_schwab_preview_not_applicable_for_crypto():
    ticket = build_platform_ticket({"market": "crypto", "symbol": "BTC/USD", "signal": "WATCH", "entry": 65000, "stop": 64000})

    preview = build_schwab_preview(ticket)

    assert preview["applicable"] is False


def test_schwab_preview_blocks_no_trade_even_with_credentials():
    ticket = build_platform_ticket({"market": "stock", "symbol": "AMD", "signal": "AVOID", "decision": "NO_TRADE", "entry": 100, "stop": 98})
    order_preview = build_order_preview(ticket, env=SCHWAB_ENV)

    preview = build_schwab_preview(ticket, order_preview=order_preview)

    assert preview["api_preview_ready"] is False
    assert preview["blockers"][0].startswith("Roxy status is NO_TRADE")


def test_schwab_whole_quantity_rejects_sub_one_quantity():
    with pytest.raises(ValueError):
        schwab_whole_quantity(0.5)
