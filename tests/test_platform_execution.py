from platform_execution import (
    LIVE_EXECUTION_FLAG,
    broker_adapter_status,
    build_order_preview,
    platform_connection_status,
    preview_readiness_score,
    required_credentials_table,
)
from platform_router import build_platform_ticket


def ready_stock_ticket():
    return build_platform_ticket(
        {"market": "stock", "symbol": "AAPL", "signal": "BUY", "decision": "TRADE_FOR_2PCT", "entry": 200, "stop": 195},
        account_equity=500,
        risk_per_trade_pct=0.01,
    )


def test_missing_credentials_keep_preview_blocked():
    preview = build_order_preview(ready_stock_ticket(), env={})

    assert preview["mode"] == "NEEDS_CREDENTIALS"
    assert preview["preview_payload_ready"] is True
    assert preview["credential_gate_ready"] is False
    assert preview["api_send_allowed"] is False
    assert preview["live_send_ready"] is False
    assert preview["readiness_score"] == 65
    assert "Platform credentials are missing." in preview["send_blockers"]
    assert f"{LIVE_EXECUTION_FLAG}=1 is not set." in preview["send_blockers"]


def test_credentials_without_live_flag_stay_preview_only():
    env = {
        "SCHWAB_CLIENT_ID": "id",
        "SCHWAB_CLIENT_SECRET": "secret",
        "SCHWAB_REDIRECT_URI": "http://localhost/callback",
        "SCHWAB_ACCESS_TOKEN": "token",
        "SCHWAB_ACCOUNT_HASH": "hash",
    }

    preview = build_order_preview(ready_stock_ticket(), env=env)

    assert preview["mode"] == "PREVIEW_ONLY"
    assert preview["credential_status"]["configured"] is True
    assert preview["api_send_allowed"] is False
    assert f"{LIVE_EXECUTION_FLAG}=1 is not set." in preview["send_blockers"]


def test_live_flag_and_credentials_can_arm_preview_gate():
    env = {
        LIVE_EXECUTION_FLAG: "1",
        "SCHWAB_CLIENT_ID": "id",
        "SCHWAB_CLIENT_SECRET": "secret",
        "SCHWAB_REDIRECT_URI": "http://localhost/callback",
        "SCHWAB_ACCESS_TOKEN": "token",
        "SCHWAB_ACCOUNT_HASH": "hash",
    }

    preview = build_order_preview(ready_stock_ticket(), env=env)

    assert preview["mode"] == "LIVE_ARMED"
    assert preview["credential_gate_ready"] is True
    assert preview["api_send_allowed"] is False
    assert preview["live_send_ready"] is False
    assert preview["adapter_status"]["status"] == "PREVIEW_ONLY"
    assert preview["manual_order"]["symbol"] == "AAPL"
    assert preview["manual_order"]["limit_price"] == 200


def test_order_preview_accepts_connection_status_override():
    status = {
        "platform_id": "schwab",
        "platform": "Charles Schwab",
        "configured": True,
        "live_enabled": False,
        "missing_keys": [],
        "mode": "PREVIEW_ONLY",
    }

    preview = build_order_preview(ready_stock_ticket(), connection_status=status)

    assert preview["mode"] == "PREVIEW_ONLY"
    assert preview["credential_status"]["configured"] is True
    assert "Platform credentials are missing." not in preview["send_blockers"]


def test_no_trade_ticket_stays_blocked_even_with_credentials():
    ticket = build_platform_ticket({"symbol": "AMD", "signal": "AVOID", "decision": "NO_TRADE", "entry": 100, "stop": 98})
    env = {
        LIVE_EXECUTION_FLAG: "1",
        "SCHWAB_CLIENT_ID": "id",
        "SCHWAB_CLIENT_SECRET": "secret",
        "SCHWAB_REDIRECT_URI": "http://localhost/callback",
        "SCHWAB_ACCESS_TOKEN": "token",
        "SCHWAB_ACCOUNT_HASH": "hash",
    }

    preview = build_order_preview(ticket, env=env)

    assert preview["api_send_allowed"] is False
    assert preview["send_blockers"][0].startswith("Roxy status is NO_TRADE")


def test_context_blocked_ticket_is_not_preview_ready_even_with_credentials():
    ticket = build_platform_ticket(
        {"market": "stock", "symbol": "AAPL", "signal": "BUY", "decision": "TRADE_FOR_2PCT", "entry": 200, "stop": 195},
        market_session={"stock_session": "Cerrado", "stock_alerts_allowed": False},
    )
    env = {
        LIVE_EXECUTION_FLAG: "1",
        "SCHWAB_CLIENT_ID": "id",
        "SCHWAB_CLIENT_SECRET": "secret",
        "SCHWAB_REDIRECT_URI": "http://localhost/callback",
        "SCHWAB_ACCESS_TOKEN": "token",
        "SCHWAB_ACCOUNT_HASH": "hash",
    }

    preview = build_order_preview(ticket, env=env)

    assert ticket["status"] == "BLOCKED_MARKET_CLOSED"
    assert preview["preview_payload_ready"] is False
    assert preview["credential_gate_ready"] is False
    assert preview["send_blockers"][0].startswith("Roxy status is BLOCKED_MARKET_CLOSED")


def test_required_credentials_table_masks_values_and_lists_missing_names():
    env = {"CRYPTO_COM_API_KEY": "key"}

    rows = required_credentials_table(env=env)
    crypto = next(row for row in rows if row["platform"] == "Crypto.com")

    assert crypto["configured"] is False
    assert "CRYPTO_COM_API_SECRET" in crypto["missing"]
    assert "key" not in str(rows)


def test_platform_status_reports_present_without_secret_values():
    status = platform_connection_status("webull", env={"WEBULL_APP_KEY": "abc"})

    assert status["present_keys"] == ["WEBULL_APP_KEY"]
    assert "abc" not in str(status)


def test_broker_adapter_status_keeps_live_send_off_until_implemented():
    status = broker_adapter_status("schwab")

    assert status["implemented"] is False
    assert status["status"] == "PREVIEW_ONLY"
    assert "manual and preview payloads only" in status["reason"]


def test_preview_readiness_score_rewards_credentials_and_live_flag():
    ticket = ready_stock_ticket()
    base = platform_connection_status("schwab", env={})
    armed = platform_connection_status(
        "schwab",
        env={
            LIVE_EXECUTION_FLAG: "1",
            "SCHWAB_CLIENT_ID": "id",
            "SCHWAB_CLIENT_SECRET": "secret",
            "SCHWAB_REDIRECT_URI": "http://localhost/callback",
            "SCHWAB_ACCESS_TOKEN": "token",
            "SCHWAB_ACCOUNT_HASH": "hash",
        },
    )

    assert preview_readiness_score(ticket, base) == 65
    assert preview_readiness_score(ticket, armed) == 100
