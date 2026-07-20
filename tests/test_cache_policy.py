import ast
from pathlib import Path

import pytest

from roxy_trader.cache_policy import (
    CACHE_POLICY_VERSION,
    cache_age_status,
    cache_policy,
    cache_policy_contract,
    cache_policy_issues,
    cache_ttl,
)


def test_cache_policy_is_versioned_and_covers_operational_data_classes():
    contract = cache_policy_contract({})
    keys = {row["key"] for row in contract["policies"]}

    assert contract["version"] == CACHE_POLICY_VERSION
    assert {"stock_quote", "live_price", "crypto_market", "chart", "news", "asset_identity_disk"} <= keys
    assert "email_metadata" in keys
    assert cache_policy("stock_quote").failure_mode == "never_serve_unlabeled_stale"


def test_cache_ttl_override_is_bounded_and_invalid_values_fall_back():
    key = cache_policy("live_price").env_key

    assert cache_ttl("live_price", {key: "9"}) == 9
    assert cache_ttl("live_price", {key: "999"}) == 15
    assert cache_ttl("live_price", {key: "bad"}) == 5
    assert [row["override_state"] for row in cache_policy_issues({key: "999"})] == ["clamped"]
    assert [row["override_state"] for row in cache_policy_issues({key: "bad"})] == ["invalid"]


def test_cache_age_status_distinguishes_fresh_stale_expired_and_missing():
    assert cache_age_status("news", None, {}) == "NO_DATA"
    assert cache_age_status("news", 300, {}) == "FRESH"
    assert cache_age_status("news", 301, {}) == "STALE"
    assert cache_age_status("news", 601, {}) == "EXPIRED"
    assert cache_age_status("stock_quote", 2, {}) == "EXPIRED"


def test_unknown_cache_policy_fails_closed():
    with pytest.raises(KeyError):
        cache_ttl("not-a-real-cache", {})


def test_streamlit_cache_decorators_never_use_unclassified_numeric_ttl():
    root = Path(__file__).resolve().parents[1]
    for relative in ("streamlit_app.py", "dashboard.py"):
        tree = ast.parse((root / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or "cache_data" not in ast.unparse(decorator.func):
                    continue
                ttl = next((item.value for item in decorator.keywords if item.arg == "ttl"), None)
                assert ttl is not None, f"{relative}:{node.name} lacks an explicit TTL policy"
                assert not isinstance(ttl, ast.Constant), f"{relative}:{node.name} uses an unclassified literal TTL"


def test_non_streamlit_disk_caches_use_the_same_policy_module():
    root = Path(__file__).resolve().parents[1]
    assert 'cache_ttl("asset_identity_disk")' in (root / "asset_identity.py").read_text(encoding="utf-8")
    assert 'policy_cache_ttl("news")' in (root / "news.py").read_text(encoding="utf-8")
    living = (root / "living_market.py").read_text(encoding="utf-8")
    assert 'cache_ttl("live_price")' in living
    assert 'cache_ttl("opportunity")' in living


def test_stock_and_crypto_consumers_share_cached_provider_routes():
    root = Path(__file__).resolve().parents[1]
    source = (root / "streamlit_app.py").read_text(encoding="utf-8")
    live_block = source[source.index("def cached_live_price_snapshot") : source.index("def cached_alpaca_market_data_diagnostic")]
    stock_block = source[source.index("def roxy_stock_quote_snapshot") : source.index("def roxy_stock_live_plan_seed")]

    assert "cached_stock_provider_snapshot(symbol)" in live_block
    assert "cached_stock_provider_snapshot(clean_symbol)" in stock_block
    assert 'build_live_price_snapshot(clean_symbol, "stock")' not in stock_block
    assert 'roxy_crypto_history_for_signal(symbol, timeframe="1h", limit=120)' in source
    assert 'roxy_crypto_history_for_signal(str(symbol), timeframe="1m", limit=80)' in source


def test_stock_provider_request_is_coalesced_across_live_and_quote_consumers(monkeypatch):
    import streamlit_app

    calls = []
    streamlit_app.cached_stock_provider_snapshot.clear()
    streamlit_app.cached_live_price_snapshot.clear()
    streamlit_app.roxy_stock_quote_snapshot.clear()
    monkeypatch.setattr(
        streamlit_app,
        "build_live_price_snapshot",
        lambda symbol, market: calls.append((symbol, market))
        or {
            "symbol": symbol,
            "market": market,
            "price": 101.0,
            "previous_close": 100.0,
            "change_pct": 0.01,
            "source": "test-provider",
        },
    )

    live = streamlit_app.cached_live_price_snapshot("aapl", "stock")
    quote = streamlit_app.roxy_stock_quote_snapshot("AAPL")

    assert live["price"] == 101.0
    assert quote["price"] == 101.0
    assert calls == [("AAPL", "stock")]
    streamlit_app.cached_stock_provider_snapshot.clear()
    streamlit_app.cached_live_price_snapshot.clear()
    streamlit_app.roxy_stock_quote_snapshot.clear()
