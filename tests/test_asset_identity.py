from datetime import timedelta

import pytest

import asset_identity
from asset_identity import (
    AssetIdentity,
    identity_status,
    normalize_market,
    normalize_symbol,
    resolve_asset_identity,
)


def test_crypto_identity_catalog_covers_current_operational_universe():
    current = {
        "BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "AVAX", "LTC", "LINK",
        "MATIC", "PEPE", "RNDR", "BONK", "DOT", "FET", "FLOKI", "GLM", "GRT", "NEAR",
        "OCEAN", "RLC", "SHIB", "TRAC", "WIF",
    }

    assert current <= set(asset_identity.CRYPTO_IDENTITIES)
    assert all(asset_identity.CRYPTO_IDENTITIES[symbol].get("coingecko_id") for symbol in current)
    assert all(asset_identity.CRYPTO_IDENTITIES[symbol].get("logo_url") for symbol in current - {"BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "AVAX", "LTC", "LINK"})
    assert asset_identity.CRYPTO_IDENTITIES["MATIC"]["coingecko_id"] == "matic-network"
    assert asset_identity.CRYPTO_IDENTITIES["RNDR"]["coingecko_id"] == "render-token"


def test_static_coingecko_cdn_logo_survives_profile_rate_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(asset_identity, "_coingecko_profile", lambda _symbol: {})
    requested = []

    def fake_request(url, **_kwargs):
        requested.append(url)
        return b"png", "image/png"

    monkeypatch.setattr(asset_identity, "_request_bytes", fake_request)
    identity = resolve_asset_identity("FET/USD", "crypto", cache_dir=tmp_path)

    assert requested[0] == asset_identity.CRYPTO_IDENTITIES["FET"]["logo_url"]
    assert identity.logo_source == "coingecko"
    assert identity.logo_fallback is False
    assert not [path for path in tmp_path.iterdir() if path.name.endswith(".tmp")]


def test_asset_symbol_and_market_normalization():
    assert normalize_market("", "BTC/USD") == "crypto"
    assert normalize_symbol("btc-usd", "crypto") == "BTC"
    assert normalize_symbol("BRK.B", "stock") == "BRK.B"


def test_unknown_asset_uses_non_alphabetic_generic_fallback(tmp_path):
    identity = resolve_asset_identity(
        "ZZZZ",
        "stock",
        cache_dir=tmp_path,
        allow_network=False,
    )

    assert identity.symbol == "ZZZZ"
    assert identity.logo_source == "fallback_generic"
    assert identity.logo_fallback is True
    assert identity.logo_data_uri.startswith("data:image/svg+xml;base64,")
    assert identity.provider_status == "NOT_CONFIGURED"
    assert "ZZZZ" not in identity.logo_data_uri


def test_known_stock_logo_is_downloaded_once_and_served_from_disk_cache(tmp_path, monkeypatch):
    requests = []

    def fake_request_bytes(url, **_kwargs):
        requests.append(url)
        return b"fake-png", "image/png"

    monkeypatch.setattr(asset_identity, "_request_bytes", fake_request_bytes)
    first = resolve_asset_identity("AAPL", "stock", cache_dir=tmp_path)

    assert first.name == "Apple Inc."
    assert first.exchange == "NASDAQ"
    assert first.logo_source == "simple_icons"
    assert first.logo_cached is True
    assert first.logo_fallback is False
    assert requests == ["https://cdn.simpleicons.org/apple/ffffff"]

    monkeypatch.setattr(
        asset_identity,
        "_request_bytes",
        lambda *_args, **_kwargs: pytest.fail("fresh cache should avoid a network request"),
    )
    second = resolve_asset_identity("AAPL", "stock", cache_dir=tmp_path)

    assert second == first
    assert identity_status(second)["logo_cached"] is True


def test_crypto_prefers_coingecko_identity_and_caches_provider_image(tmp_path, monkeypatch):
    monkeypatch.setattr(
        asset_identity,
        "_coingecko_profile",
        lambda _base: {
            "name": "Bitcoin",
            "image": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png",
        },
    )
    monkeypatch.setattr(asset_identity, "_request_bytes", lambda *_args, **_kwargs: (b"png", "image/png"))

    identity = resolve_asset_identity("BTC/USD", "crypto", cache_dir=tmp_path)

    assert identity.symbol == "BTC"
    assert identity.name == "Bitcoin"
    assert identity.logo_source == "coingecko"
    assert identity.logo_cached is True
    assert identity.provider_status == "CONNECTED"


def test_expired_cache_refreshes_logo(tmp_path, monkeypatch):
    calls = 0

    def fake_request_bytes(_url, **_kwargs):
        nonlocal calls
        calls += 1
        return f"png-{calls}".encode(), "image/png"

    monkeypatch.setattr(asset_identity, "_request_bytes", fake_request_bytes)
    resolve_asset_identity("MSFT", "stock", cache_dir=tmp_path)
    refreshed = resolve_asset_identity(
        "MSFT",
        "stock",
        cache_dir=tmp_path,
        cache_ttl=timedelta(seconds=-1),
    )

    assert calls == 2
    assert "cG5nLTI=" in refreshed.logo_data_uri


def test_image_download_rejects_untrusted_hosts():
    with pytest.raises(ValueError, match="allowlisted"):
        asset_identity._request_bytes("https://example.com/logo.png")


def test_identity_dataclass_exposes_operational_provenance():
    identity = AssetIdentity(symbol="AAPL", market="stock", name="Apple", logo_source="finnhub")
    status = identity_status(identity)

    assert status["symbol"] == "AAPL"
    assert status["logo_source"] == "finnhub"
    assert status["provider_status"] == "FALLBACK"
