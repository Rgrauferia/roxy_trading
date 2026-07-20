from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from durable_storage import atomic_write_text
from roxy_trader.device_sync import DEVICE_SYNC_CONTRACT_VERSION
from system_diagnostics import device_sync_configuration_check


CONTRACT_VERSION = "roxy-mobile-client/1.0.0"
DEFAULT_REPORT_PATH = Path("alerts/mobile_client_check.json")


def build_mobile_client_check(
    root: str | Path = ".", *, env: Mapping[str, str] | None = None
) -> dict[str, Any]:
    base = Path(root)
    assets = base / "assets"
    html_path = assets / "roxy_mobile.html"
    js_path = assets / "roxy_mobile.js"
    css_path = assets / "roxy_mobile.css"
    worker_path = assets / "roxy_mobile_sw.js"
    voice_path = base / "tools" / "voice_service.py"
    checks: list[dict[str, Any]] = []
    try:
        html = html_path.read_text(encoding="utf-8")
        js = js_path.read_text(encoding="utf-8")
        css = css_path.read_text(encoding="utf-8")
        worker = worker_path.read_text(encoding="utf-8")
        voice = voice_path.read_text(encoding="utf-8")
    except OSError:
        html = js = css = worker = voice = ""
    assets_ok = all((html, js, css, worker)) and all(
        marker in html for marker in ("roxy-mobile-manifest.json", "roxy_mobile.js", "roxy_mobile.css")
    )
    checks.append({"name": "installable_shell_assets", "status": "OK" if assets_ok else "ERROR"})
    scopes_ok = all(scope in js for scope in ("watchlists", "ui_state", "personal_tasks", "shopping_list"))
    conflict_ok = "response.status===409" in js and "await load()" in js
    checks.append({"name": "four_scope_conflict_client", "status": "OK" if scopes_ok and conflict_ok else "ERROR"})
    security_ok = all(marker in js for marker in ("secureTransport", "Transporte inseguro", "cache:'no-store'")) and all(
        forbidden not in js for forbidden in ("localStorage", "sessionStorage")
    ) and "url.pathname.startsWith('/v1/')" in worker
    checks.append({"name": "transport_token_and_cache_policy", "status": "OK" if security_ok else "ERROR"})
    physical_proof_ok = all(marker in js for marker in (
        "remoteNetworkClient", "/v1/mobile/physical-proof/", "dispositivo remoto verificado"
    )) and '@app.post("/v1/mobile/physical-proof/{user_id}")' in voice
    checks.append({"name": "remote_physical_proof", "status": "OK" if physical_proof_ok else "ERROR"})
    routes_ok = all(marker in voice for marker in (
        '@app.get("/roxy-mobile"', '@app.get("/roxy-mobile-manifest.json"', '@app.get("/roxy-mobile-sw.js"',
        '@app.get("/roxy-mobile-ca.mobileconfig"',
        '"Content-Security-Policy"', '"Service-Worker-Allowed"',
    ))
    checks.append({"name": "server_routes_and_headers", "status": "OK" if routes_ok else "ERROR"})
    node = shutil.which("node")
    syntax_ok = False
    if node and js_path.exists() and worker_path.exists():
        syntax_ok = all(
            subprocess.run([node, "--check", str(path)], capture_output=True, text=True, timeout=10).returncode == 0
            for path in (js_path, worker_path)
        )
    checks.append({"name": "javascript_syntax", "status": "OK" if syntax_ok else "ERROR"})
    screenshots = [
        base / "output" / "playwright" / "roxy_mobile_desktop.png",
        base / "output" / "playwright" / "roxy_mobile_phone.png",
    ]
    browser_ok = all(path.is_file() and path.stat().st_size > 1_000 for path in screenshots)
    checks.append({"name": "desktop_phone_browser_evidence", "status": "OK" if browser_ok else "ERROR"})
    contract_ok = all(check["status"] == "OK" for check in checks)
    remote = device_sync_configuration_check(env if env is not None else os.environ)
    remote_ready = remote.status == "CONNECTED"
    gateway_ready = False
    try:
        gateway = json.loads((base / "alerts" / "mobile_gateway_check.json").read_text(encoding="utf-8"))
        gateway_status = str(gateway.get("gateway_status") or "").upper() if isinstance(gateway, dict) else ""
        gateway_physical = str(gateway.get("physical_reachability") or "").upper() == "VERIFIED_REMOTE_CLIENT" if isinstance(gateway, dict) else False
        gateway_ready = (
            isinstance(gateway, dict)
            and str(gateway.get("contract_status") or "").upper() == "OK"
            and gateway_status in {"READY_FOR_PHYSICAL_TEST", "CONNECTED_PHYSICAL"}
        )
    except (OSError, ValueError, TypeError):
        gateway = {}
        gateway_ready = False
        gateway_physical = False
    remote_status = "CONNECTED" if remote_ready or (gateway_ready and gateway_physical) else "READY_FOR_PHYSICAL_TEST" if gateway_ready else "NOT_CONFIGURED"
    remote_detail = (
        "Cliente remoto autenticado por HTTPS y ligado a la CA/Bearer actuales."
        if gateway_ready and gateway_physical
        else "Gateway HTTPS/Bearer/allowlist verificado localmente; falta confiar la CA y validar un dispositivo fisico."
        if gateway_ready
        else remote.detail
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "sync_contract_version": DEVICE_SYNC_CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if contract_ok and remote_ready else "WARN" if contract_ok else "ERROR",
        "contract_status": "OK" if contract_ok else "ERROR",
        "client_status": "READY_LOCAL" if contract_ok else "ERROR",
        "remote_status": remote_status,
        "pwa_installable": assets_ok and syntax_ok and routes_ok,
        "stores_sensitive_state": False,
        "api_cache_enabled": False,
        "scopes": ["watchlists", "ui_state", "personal_tasks", "shopping_list"],
        "checks": checks,
        "remote_detail": remote_detail,
        "runtime_evidence": [str(path.relative_to(base)) for path in screenshots],
    }


def write_report(payload: Mapping[str, Any], path: str | Path = DEFAULT_REPORT_PATH) -> Path:
    target = Path(path)
    atomic_write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica el cliente movil PWA y su contrato de sincronizacion.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    payload = build_mobile_client_check(args.root)
    write_report(payload, args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
