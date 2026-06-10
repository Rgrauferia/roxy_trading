from platform_router import build_platform_ticket, execution_context_gate, infer_asset_type, position_size_from_risk, route_platform


def test_crypto_routes_to_crypto_com_by_default():
    row = {"market": "crypto", "symbol": "BTC/USD", "signal": "WATCH", "entry": 65000, "stop": 63700}

    ticket = build_platform_ticket(row, account_equity=500, risk_per_trade_pct=0.01)

    assert infer_asset_type(row) == "crypto"
    assert ticket["platform_id"] == "crypto_com"
    assert ticket["platform"] == "Crypto.com"
    assert ticket["time_in_force"] == "GTC"


def test_stock_routes_to_schwab_by_default():
    row = {"market": "stock", "symbol": "AAPL", "signal": "BUY", "decision": "TRADE_FOR_2PCT", "entry": 200, "stop": 195}

    ticket = build_platform_ticket(row, account_equity=500, risk_per_trade_pct=0.01)

    assert infer_asset_type(row) == "stock"
    assert ticket["platform_id"] == "schwab"
    assert ticket["status"] == "READY_TO_PREVIEW"
    assert ticket["risk_dollars"] == 5
    assert ticket["quantity"] == 1


def test_option_routes_to_schwab_and_uses_contract_symbol():
    row = {
        "market": "stock",
        "symbol": "AAPL",
        "contractSymbol": "AAPL260619C00220000",
        "signal": "WATCH",
        "entry": 5,
        "stop": 3.75,
    }

    ticket = build_platform_ticket(row, account_equity=500, risk_per_trade_pct=0.01, preferred_product="option")

    assert ticket["asset_type"] == "option"
    assert ticket["platform_id"] == "schwab"
    assert ticket["order_symbol"] == "AAPL260619C00220000"
    assert ticket["quantity"] == 4


def test_user_can_prefer_webull_for_supported_assets():
    stock = {"market": "stock", "symbol": "NVDA", "signal": "WATCH", "entry": 120, "stop": 117.5}
    option = {
        "market": "stock",
        "symbol": "NVDA",
        "contractSymbol": "NVDA260619C00130000",
        "signal": "WATCH",
        "entry": 4,
        "stop": 3,
    }

    assert route_platform(stock, preferred_stock="webull") == "webull"
    assert build_platform_ticket(option, preferred_product="option", preferred_option="webull")["platform_id"] == "webull"


def test_statuses_separate_ready_wait_and_no_trade():
    ready = {"symbol": "AMD", "signal": "BUY", "decision": "TRADE_FOR_5PCT", "entry": 100, "stop": 95}
    waiting = {"symbol": "AMD", "signal": "WATCH", "decision": "WAIT_FOR_ENTRY", "entry": 100, "stop": 95}
    avoid = {"symbol": "AMD", "signal": "AVOID", "decision": "NO_TRADE", "entry": 100, "stop": 95}

    assert build_platform_ticket(ready)["status"] == "READY_TO_PREVIEW"
    assert build_platform_ticket(waiting)["status"] == "WAIT_FOR_CONFIRMATION"
    assert build_platform_ticket(avoid)["status"] == "NO_TRADE"


def test_position_size_respects_risk_budget():
    assert position_size_from_risk(100, 95, 5, allow_fractional=False) == 1
    assert position_size_from_risk(100, 97, 5, allow_fractional=True) == 1.666667
    assert position_size_from_risk(100, 100, 5, allow_fractional=True) is None


def test_stock_ticket_uses_whole_share_quantity():
    row = {"market": "stock", "symbol": "TTEK", "signal": "BUY", "decision": "TRADE_FOR_2PCT", "entry": 27.94, "stop": 27.51}

    ticket = build_platform_ticket(row, account_equity=500, risk_per_trade_pct=0.01)

    assert ticket["asset_type"] == "stock"
    assert ticket["quantity"] == 11


def test_execution_context_blocks_stock_preview_when_market_closed():
    row = {"market": "stock", "symbol": "AAPL", "signal": "BUY", "decision": "TRADE_FOR_2PCT", "entry": 200, "stop": 195}

    ticket = build_platform_ticket(
        row,
        market_session={"stock_session": "Cerrado", "stock_alerts_allowed": False},
    )

    assert execution_context_gate("stock", market_session={"stock_alerts_allowed": False})[0] == "BLOCKED_MARKET_CLOSED"
    assert ticket["status"] == "BLOCKED_MARKET_CLOSED"
    assert ticket["execution_enabled"] is False


def test_execution_context_allows_crypto_when_stock_market_closed():
    row = {"market": "crypto", "symbol": "BTC/USD", "signal": "BUY", "decision": "TRADE_FOR_2PCT", "entry": 65000, "stop": 63700}

    ticket = build_platform_ticket(
        row,
        market_session={"stock_session": "Cerrado", "stock_alerts_allowed": False, "crypto_session": "24h"},
    )

    assert ticket["asset_type"] == "crypto"
    assert ticket["status"] == "READY_TO_PREVIEW"
    assert ticket["execution_enabled"] is True


def test_execution_context_blocks_stale_data_for_all_assets():
    row = {"market": "crypto", "symbol": "ETH/USD", "signal": "BUY", "decision": "TRADE_FOR_2PCT", "entry": 3000, "stop": 2940}

    ticket = build_platform_ticket(
        row,
        source_freshness={"status": "STALE", "alerts_allowed": False},
    )

    assert ticket["status"] == "BLOCKED_STALE_DATA"
    assert ticket["execution_gate"] == "BLOCKED_STALE_DATA"
