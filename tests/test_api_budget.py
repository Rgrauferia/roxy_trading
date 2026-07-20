from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import sqlite3

import pytest

from roxy_trader.api_budget import (
    API_BUDGET_VERSION,
    ApiBudgetBlockedError,
    ApiUsageLedger,
    api_budget_contract,
    api_budget_issues,
    api_budget_policy,
    observe_api_call,
)


def test_api_budget_contract_is_versioned_and_protects_real_rate_limits():
    contract = api_budget_contract({})

    assert contract["version"] == API_BUDGET_VERSION
    assert contract["mode"] == "protect"
    assert contract["policy_count"] == 14
    assert all(row["enforcement"] == "protect" for row in contract["policies"])
    assert "provider plan limits" in contract["disclaimer"]


def test_api_budget_override_is_bounded_and_invalid_falls_back():
    key = api_budget_policy("alpaca", {}).env_key

    assert api_budget_policy("alpaca", {key: "250"}).requests_per_window == 250
    assert api_budget_policy("alpaca", {key: "0"}).requests_per_window == 1
    assert api_budget_policy("alpaca", {key: "invalid"}).requests_per_window == 180
    assert api_budget_issues({key: "invalid"}) == [
        {"provider": "alpaca", "env_key": key, "state": "invalid"}
    ]
    assert api_budget_issues({key: "0"}) == [
        {"provider": "alpaca", "env_key": key, "state": "clamped"}
    ]


def test_unknown_api_budget_provider_fails_closed():
    with pytest.raises(KeyError):
        api_budget_policy("mystery")


def test_api_usage_ledger_reports_usage_errors_and_rate_limits(tmp_path):
    ledger = ApiUsageLedger(tmp_path / "usage.sqlite")
    now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
    ledger.record(provider="polygon", operation="candles", status="OK", latency_ms=20, occurred_at=now)
    ledger.record(
        provider="polygon",
        operation="candles",
        status="ERROR",
        http_status=429,
        latency_ms=40,
        occurred_at=now,
    )

    summary = ledger.provider_summary("polygon", now=now + timedelta(seconds=10))

    assert summary["state"] == "RATE_LIMITED"
    assert summary["requests"] == 2
    assert summary["rate_limited"] == 1
    assert summary["errors"] == 1
    assert summary["average_latency_ms"] == 30.0
    assert summary["remaining"] == 2
    assert summary["requests_24h"] == 2
    assert summary["rate_limited_24h"] == 1
    assert summary["errors_24h"] == 1


def test_api_usage_ledger_excludes_old_events_and_prunes(tmp_path):
    ledger = ApiUsageLedger(tmp_path / "usage.sqlite")
    now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
    ledger.record(provider="coingecko", operation="identity", status="OK", occurred_at=now - timedelta(hours=2))
    ledger.record(provider="coingecko", operation="identity", status="OK", occurred_at=now)

    assert ledger.provider_summary("coingecko", now=now)["requests"] == 1
    assert ledger.prune(before=now - timedelta(hours=1)) == 1


def test_api_usage_schema_has_no_secret_or_url_columns(tmp_path):
    ledger = ApiUsageLedger(tmp_path / "usage.sqlite")
    ledger.record(provider="alpaca", operation="latest_trade", status="OK")
    with sqlite3.connect(ledger.path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(api_usage_events)")}

    assert "url" not in columns
    assert "headers" not in columns
    assert "secret" not in columns
    assert columns == {
        "id",
        "provider",
        "operation",
        "occurred_at",
        "latency_ms",
        "status",
        "http_status",
        "rate_limited",
    }
    assert os.stat(ledger.path).st_mode & 0o777 == 0o600


def test_observe_api_call_records_success_when_explicitly_enabled(tmp_path):
    path = tmp_path / "usage.sqlite"
    with observe_api_call(
        "binanceus",
        "ticker",
        path=path,
        env={"ROXY_API_TELEMETRY_ENABLED": "1"},
    ):
        pass

    assert ApiUsageLedger(path).provider_summary("binanceus")["requests"] == 1


def test_observe_api_call_records_429_and_preserves_exception(tmp_path):
    class RateLimitError(RuntimeError):
        code = 429

    path = tmp_path / "usage.sqlite"
    with pytest.raises(RateLimitError):
        with observe_api_call(
            "coingecko",
            "identity",
            path=path,
            env={"ROXY_API_TELEMETRY_ENABLED": "1"},
        ):
            raise RateLimitError("limited")

    summary = ApiUsageLedger(path).provider_summary("coingecko")
    assert summary["rate_limited"] == 1
    assert summary["errors"] == 1


def test_observe_api_call_records_returned_http_error_without_requiring_exception(tmp_path):
    path = tmp_path / "usage.sqlite"
    with observe_api_call(
        "elevenlabs",
        "conversation_token",
        path=path,
        env={"ROXY_API_TELEMETRY_ENABLED": "1"},
    ) as observation:
        observation.set_http_status(429)

    summary = ApiUsageLedger(path).provider_summary("elevenlabs")
    assert summary["state"] == "RATE_LIMITED"
    assert summary["rate_limited"] == 1


def test_observe_api_call_is_disabled_during_tests_by_default(tmp_path, monkeypatch):
    path = tmp_path / "usage.sqlite"
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "active")

    with observe_api_call("alpaca", "latest_trade", path=path):
        pass

    assert not path.exists()


def test_protect_mode_blocks_followup_during_real_429_cooldown(tmp_path):
    path = tmp_path / "usage.sqlite"
    ledger = ApiUsageLedger(path)
    ledger.record(provider="coingecko", operation="identity", status="RATE_LIMITED", http_status=429)

    with pytest.raises(ApiBudgetBlockedError) as error:
        with observe_api_call(
            "coingecko",
            "identity",
            path=path,
            env={"ROXY_API_TELEMETRY_ENABLED": "1", "ROXY_API_BUDGET_MODE": "protect"},
        ):
            raise AssertionError("outbound call must not execute during cooldown")

    assert error.value.reason == "rate_limit_cooldown"
    summary = ledger.provider_summary("coingecko")
    assert summary["requests"] == 1
    assert summary["blocks"] == 1


def test_observe_mode_does_not_block_after_429(tmp_path):
    path = tmp_path / "usage.sqlite"
    ledger = ApiUsageLedger(path)
    ledger.record(provider="coingecko", operation="identity", status="RATE_LIMITED", http_status=429)

    with observe_api_call(
        "coingecko",
        "identity",
        path=path,
        env={"ROXY_API_TELEMETRY_ENABLED": "1", "ROXY_API_BUDGET_MODE": "observe"},
    ):
        pass

    assert ledger.provider_summary("coingecko")["requests"] == 2


def test_enforce_mode_blocks_when_operational_budget_is_exhausted(tmp_path):
    path = tmp_path / "usage.sqlite"
    ledger = ApiUsageLedger(path)
    env = {
        "ROXY_API_TELEMETRY_ENABLED": "1",
        "ROXY_API_BUDGET_MODE": "enforce",
        "ROXY_API_BUDGET_POLYGON_PER_MINUTE": "1",
    }
    ledger.record(provider="polygon", operation="aggregates", status="OK")

    with pytest.raises(ApiBudgetBlockedError) as error:
        with observe_api_call("polygon", "aggregates", path=path, env=env):
            raise AssertionError("budget-exhausted call must not execute")

    assert error.value.reason == "operational_budget"
    assert ledger.provider_summary("polygon", env=env)["blocks"] == 1
