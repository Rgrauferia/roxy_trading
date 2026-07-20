"""Render-friendly launcher for the Roxy stock stream bridge."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port = int(os.getenv("PORT", "10000"))
    host = os.getenv("ROXY_STOCK_BRIDGE_HOST", "127.0.0.1").strip() or "127.0.0.1"
    trusted_proxies = os.getenv("ROXY_STOCK_BRIDGE_TRUSTED_PROXIES", "127.0.0.1").strip() or "127.0.0.1"
    uvicorn.run(
        "tools.roxy_stock_stream_bridge:app",
        host=host,
        port=port,
        log_level=os.getenv("ROXY_STOCK_BRIDGE_LOG_LEVEL", "info"),
        proxy_headers=True,
        forwarded_allow_ips=trusted_proxies,
    )


if __name__ == "__main__":
    main()
