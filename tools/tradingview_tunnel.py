#!/usr/bin/env python3
"""Diagnose public tunnel readiness for TradingView webhook delivery.

The dashboard stays on http://localhost:3000. TradingView only needs a public
HTTPS URL that forwards to the local bridge on http://127.0.0.1:8001.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from typing import Any, Callable, Mapping
from urllib.parse import urlparse


PUBLIC_URL_ENV = "TRADINGVIEW_PUBLIC_WEBHOOK_URL"
DEFAULT_LOCAL_BRIDGE_URL = "http://127.0.0.1:8001"
WEBHOOK_PATH = "/tradingview/webhook"


def normalize_public_webhook_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    raw = raw.rstrip("/")
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw
    if parsed.path.rstrip("/") == WEBHOOK_PATH:
        return raw
    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
    return f"{base}{WEBHOOK_PATH}"


def _safe_url(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    host = parsed.netloc
    if len(host) > 10:
        host = f"{host[:4]}...{host[-6:]}"
    return f"{parsed.scheme}://{host}{parsed.path}"


def tradingview_tunnel_readiness(
    *,
    env: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    source_env = env if env is not None else os.environ
    which_fn = which or shutil.which
    public_url = normalize_public_webhook_url(source_env.get(PUBLIC_URL_ENV))
    parsed = urlparse(public_url)
    https_ok = parsed.scheme == "https" and bool(parsed.netloc)
    cloudflared = bool(which_fn("cloudflared"))
    ngrok = bool(which_fn("ngrok"))
    blockers: list[str] = []
    if not public_url:
        blockers.append(f"{PUBLIC_URL_ENV} no configurado")
    elif not https_ok:
        blockers.append("URL publica debe ser HTTPS")
    if not cloudflared and not ngrok and not public_url:
        blockers.append("instalar cloudflared o ngrok, o configurar URL publica manual")
    recommended_tool = "cloudflared" if cloudflared else "ngrok" if ngrok else "manual"
    if recommended_tool == "cloudflared":
        suggested_command = "cloudflared tunnel --url http://127.0.0.1:8001"
    elif recommended_tool == "ngrok":
        suggested_command = "ngrok http 8001"
    else:
        suggested_command = "Configurar un tunnel HTTPS hacia http://127.0.0.1:8001"
    ready = bool(public_url and https_ok)
    next_action = (
        "Pegar la URL publica HTTPS en TradingView como webhook URL."
        if ready
        else "Crear tunnel HTTPS hacia el bridge local y guardar TRADINGVIEW_PUBLIC_WEBHOOK_URL."
    )
    return {
        "ready": ready,
        "status": "READY" if ready else "NEEDS_TUNNEL",
        "public_url_configured": bool(public_url),
        "public_webhook_url": public_url,
        "public_webhook_url_safe": _safe_url(public_url) if public_url else "",
        "https_ok": https_ok,
        "cloudflared_available": cloudflared,
        "ngrok_available": ngrok,
        "recommended_tool": recommended_tool,
        "suggested_command": suggested_command,
        "local_bridge_url": DEFAULT_LOCAL_BRIDGE_URL,
        "local_webhook_path": WEBHOOK_PATH,
        "blockers": blockers,
        "next_action": next_action,
        "paper_only": True,
        "real_orders_enabled": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Roxy TradingView tunnel readiness.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    status = tradingview_tunnel_readiness()
    if args.json:
        print(json.dumps(status, indent=2))
        raise SystemExit(0 if status["ready"] else 1)
    print(f"status={status['status']}")
    print(f"local_bridge={status['local_bridge_url']}")
    print(f"public_webhook={status['public_webhook_url_safe'] or '-'}")
    print(f"tool={status['recommended_tool']}")
    print(f"command={status['suggested_command']}")
    print(f"next={status['next_action']}")
    raise SystemExit(0 if status["ready"] else 1)


if __name__ == "__main__":
    main()
