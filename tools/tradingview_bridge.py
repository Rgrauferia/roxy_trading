#!/usr/bin/env python3
"""Run the fixed local TradingView webhook bridge.

This is intentionally separate from the Streamlit dashboard. The visible Roxy
web app stays on http://localhost:3000; this bridge listens on a fixed local
API port for TradingView webhook relays.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from urllib.error import URLError
from urllib.request import urlopen


DEFAULT_PORT = 8001
DEFAULT_HOST = "127.0.0.1"


def bridge_url(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST) -> str:
    return f"http://{host}:{int(port)}"


def health_url(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST) -> str:
    return f"{bridge_url(port, host)}/health"


def bridge_health_ok(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST, *, timeout: float = 1.5) -> bool:
    try:
        with urlopen(health_url(port, host), timeout=timeout) as response:
            return int(getattr(response, "status", 0) or 0) == 200
    except (OSError, URLError, TimeoutError, ValueError):
        return False


def ensure_tradingview_bridge(
    *,
    port: int = DEFAULT_PORT,
    host: str = DEFAULT_HOST,
    env: dict[str, str] | None = None,
) -> int:
    source_env = dict(env or os.environ)
    if bridge_health_ok(port, host):
        print(f"Roxy TradingView bridge already running: {bridge_url(port, host)}")
        return 0
    if not str(source_env.get("TRADINGVIEW_WEBHOOK_SECRET") or "").strip():
        print("TRADINGVIEW_WEBHOOK_SECRET is required before starting the TradingView bridge.", file=sys.stderr)
        return 2
    command_env = dict(os.environ)
    command_env.update(source_env)
    command_env["ADMIN_API_PORT"] = str(int(port))
    return subprocess.run([sys.executable, "tools/admin_api.py"], env=command_env, check=False).returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or reuse the fixed Roxy TradingView webhook bridge.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default=DEFAULT_HOST)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raise SystemExit(ensure_tradingview_bridge(port=args.port, host=args.host))


if __name__ == "__main__":
    main()
