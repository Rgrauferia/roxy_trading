from __future__ import annotations

from tools.tradingview_tunnel import (
    WEBHOOK_PATH,
    normalize_public_webhook_url,
    tradingview_tunnel_readiness,
)


def test_normalize_public_webhook_url_appends_webhook_path():
    assert (
        normalize_public_webhook_url("https://abc.trycloudflare.com")
        == f"https://abc.trycloudflare.com{WEBHOOK_PATH}"
    )


def test_normalize_public_webhook_url_keeps_full_webhook_path():
    url = f"https://abc.trycloudflare.com{WEBHOOK_PATH}"
    assert normalize_public_webhook_url(url) == url


def test_readiness_blocks_when_public_url_and_tunnel_tool_are_missing():
    status = tradingview_tunnel_readiness(env={}, which=lambda _: None)

    assert status["ready"] is False
    assert status["status"] == "NEEDS_TUNNEL"
    assert "TRADINGVIEW_PUBLIC_WEBHOOK_URL no configurado" in status["blockers"]
    assert "instalar cloudflared o ngrok, o configurar URL publica manual" in status["blockers"]
    assert status["paper_only"] is True
    assert status["real_orders_enabled"] is False


def test_readiness_accepts_https_public_url():
    status = tradingview_tunnel_readiness(
        env={"TRADINGVIEW_PUBLIC_WEBHOOK_URL": "https://abcdef123456.trycloudflare.com"},
        which=lambda _: None,
    )

    assert status["ready"] is True
    assert status["public_webhook_url"].endswith(WEBHOOK_PATH)
    assert status["https_ok"] is True
    assert status["blockers"] == []


def test_readiness_rejects_http_public_url():
    status = tradingview_tunnel_readiness(
        env={"TRADINGVIEW_PUBLIC_WEBHOOK_URL": "http://example.com"},
        which=lambda _: None,
    )

    assert status["ready"] is False
    assert "URL publica debe ser HTTPS" in status["blockers"]


def test_readiness_recommends_cloudflared_before_ngrok():
    status = tradingview_tunnel_readiness(env={}, which=lambda name: f"/usr/bin/{name}")

    assert status["recommended_tool"] == "cloudflared"
    assert status["suggested_command"] == "cloudflared tunnel --url http://127.0.0.1:8001"


def test_readiness_recommends_ngrok_when_cloudflared_missing():
    def fake_which(name: str) -> str | None:
        return "/usr/bin/ngrok" if name == "ngrok" else None

    status = tradingview_tunnel_readiness(env={}, which=fake_which)

    assert status["recommended_tool"] == "ngrok"
    assert status["suggested_command"] == "ngrok http 8001"
