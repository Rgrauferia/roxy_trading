"""Render-friendly launcher for the Roxy stock stream bridge."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run(
        "tools.roxy_stock_stream_bridge:app",
        host="0.0.0.0",
        port=port,
        log_level=os.getenv("ROXY_STOCK_BRIDGE_LOG_LEVEL", "info"),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
