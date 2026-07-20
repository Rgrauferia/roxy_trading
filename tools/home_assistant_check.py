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
from roxy_os.home_assistant import HOME_ASSISTANT_CONTRACT, HomeAssistantClient


DEFAULT_REPORT_PATH = Path("alerts/home_assistant_check.json")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_home_assistant_check(root: str | Path = ".", *, client: HomeAssistantClient | None = None) -> dict[str, Any]:
    base = Path(root)
    provider = (client or HomeAssistantClient()).entities()
    provider_status = str(provider.get("status") or "ERROR").upper()
    probes = [
        _read_json(base / "alerts" / "home_assistant_desktop_probe.json"),
        _read_json(base / "alerts" / "home_assistant_mobile_probe.json"),
    ]
    runtime_ok = all(
        str(report.get("status") or "").upper() == "OK"
        and int(report.get("blocking_console_error_count") or 0) == 0
        and int(report.get("blocking_page_error_count") or 0) == 0
        for report in probes
    )
    try:
        source = (base / "streamlit_app.py").read_text(encoding="utf-8")
    except OSError:
        source = ""
    ui_ok = all(marker in source for marker in (
        '"ecosystem.home": {"view": "Hogar"',
        'elif selected_page == "Hogar":',
        "show_roxy_home_screen()",
        "ROXY_HOME_CONTROL_ENABLED=0",
        "Confirmo esta entidad y accion exactas",
    ))
    contract_ok = runtime_ok and ui_ok and provider_status in {
        "CONNECTED", "SERVICE_NOT_CONFIGURED", "AUTH_INVALID", "UNAVAILABLE", "CONFIGURATION_ERROR", "ERROR"
    }
    operational = provider_status == "CONNECTED"
    return {
        "contract_version": HOME_ASSISTANT_CONTRACT,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if contract_ok and operational else "WARN" if contract_ok else "ERROR",
        "contract_status": "OK" if contract_ok else "ERROR",
        "provider_status": provider_status,
        "connected": operational,
        "control_enabled": bool(provider.get("control_enabled")),
        "entity_count": int(provider.get("entity_count") or 0),
        "detail": str(provider.get("detail") or ""),
        "runtime_evidence": [
            "alerts/home_assistant_desktop_probe.json",
            "alerts/home_assistant_mobile_probe.json",
        ],
        "secrets_exposed": False,
    }


def write_report(payload: dict[str, Any], path: str | Path = DEFAULT_REPORT_PATH) -> Path:
    target = Path(path)
    atomic_write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica la integracion fail-closed de Home Assistant.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    payload = build_home_assistant_check(args.root)
    write_report(payload, args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["contract_status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
