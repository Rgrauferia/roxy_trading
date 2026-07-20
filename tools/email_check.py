from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from durable_storage import atomic_write_text
from roxy_os.email_service import (
    EMAIL_CONTRACT,
    GmailReadonlyClient,
    OutlookReadonlyClient,
    configured_email_provider,
)


DEFAULT_REPORT_PATH = Path("alerts/email_check.json")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_email_check(
    root: str | Path = ".",
    *,
    client: GmailReadonlyClient | None = None,
    outlook_client: OutlookReadonlyClient | None = None,
) -> dict[str, Any]:
    base = Path(root)
    gmail = (client or GmailReadonlyClient()).status()
    outlook = (outlook_client or OutlookReadonlyClient()).status()
    selected_provider = configured_email_provider()
    provider = outlook if selected_provider == "outlook" else gmail
    provider_status = str(provider.get("status") or "ERROR").upper()
    try:
        source = (base / "streamlit_app.py").read_text(encoding="utf-8")
    except OSError:
        source = ""
    ui_ok = all(marker in source for marker in (
        '"ecosystem.email": {"view": "Correo"',
        'elif selected_page == "Correo":',
        "show_email_screen()",
        "Envio deshabilitado",
        "ROXY_OUTLOOK_ACCESS_TOKEN",
        "Mail.Read",
    ))
    probes = [
        _read_json(base / "alerts" / "email_desktop_probe.json"),
        _read_json(base / "alerts" / "email_mobile_probe.json"),
    ]
    runtime_ok = all(
        str(report.get("status") or "").upper() == "OK"
        and int(report.get("blocking_console_error_count") or 0) == 0
        and int(report.get("blocking_page_error_count") or 0) == 0
        for report in probes
    )
    known_state = provider_status in {
        "CONNECTED", "SERVICE_NOT_CONFIGURED", "AUTH_INVALID", "RATE_LIMITED", "UNAVAILABLE", "ERROR"
    }
    outlook_status = str(outlook.get("status") or "ERROR").upper()
    outlook_known = outlook_status in {
        "CONNECTED", "SERVICE_NOT_CONFIGURED", "AUTH_INVALID", "RATE_LIMITED", "UNAVAILABLE", "ERROR"
    }
    contract_ok = (
        ui_ok and runtime_ok and known_state and outlook_known
        and provider.get("send_enabled") is False and outlook.get("send_enabled") is False
    )
    connected = provider_status == "CONNECTED"
    return {
        "contract_version": EMAIL_CONTRACT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if contract_ok and connected else "WARN" if contract_ok else "ERROR",
        "contract_status": "OK" if contract_ok else "ERROR",
        "provider": selected_provider,
        "provider_status": provider_status,
        "connected": connected,
        "read_only": True,
        "send_enabled": False,
        "body_loading_enabled": False,
        "gmail_status": str(gmail.get("status") or "ERROR").upper(),
        "outlook_status": outlook_status,
        "providers": {
            "gmail": {"status": str(gmail.get("status") or "ERROR").upper(), "read_only": True},
            "outlook": {"status": outlook_status, "read_only": True},
        },
        "detail": str(provider.get("detail") or ""),
        "secrets_exposed": False,
        "runtime_evidence": ["alerts/email_desktop_probe.json", "alerts/email_mobile_probe.json"],
    }


def write_report(payload: dict[str, Any], path: str | Path = DEFAULT_REPORT_PATH) -> Path:
    target = Path(path)
    atomic_write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica los adaptadores Gmail y Outlook de solo lectura de Roxy.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    payload = build_email_check(args.root)
    write_report(payload, args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["contract_status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
