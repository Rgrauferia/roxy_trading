from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from durable_storage import atomic_write_text
from roxy_os import RoxyOrchestrator
from roxy_os.shopping_list import ShoppingListStore


CONTRACT_VERSION = "roxy-shopping-list/1.0.0"
DEFAULT_REPORT_PATH = Path("alerts/shopping_list_check.json")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_shopping_list_check(root: str | Path = ".") -> dict[str, Any]:
    base = Path(root)
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="roxy-shopping-check-") as directory:
        temp = Path(directory)
        store = ShoppingListStore(temp / "shopping.json")
        item = store.add("probe_user", "Cafe", quantity=1, unit="bolsa", source="diagnostic")
        merged = store.add("probe_user", "café", quantity=2, unit="bolsa", source="diagnostic")
        store.add("other_user", "Privado", source="diagnostic")
        isolated = ShoppingListStore(temp / "shopping.json").list_items("probe_user")
        checks.append({
            "name": "durability_isolation_deduplication",
            "status": "OK" if len(isolated) == 1 and merged.get("id") == item.get("id") and merged.get("quantity") == 3 else "ERROR",
        })
        purchased = store.transition("probe_user", item["id"], "PURCHASED")
        checks.append({"name": "recoverable_lifecycle", "status": "OK" if purchased.get("purchased_at") else "ERROR"})

        roxy = RoxyOrchestrator(memory_path=temp / "memory.json")
        response = roxy.handle("Roxy acuerdame comprar pan y leche", user_id="probe_user")
        voice_items = ShoppingListStore(temp / "roxy_shopping_list.json").list_items("probe_user")
        checks.append({
            "name": "voice_shared_store",
            "status": "OK" if len(voice_items) == 2 and len(response.data.get("items") or []) == 2 else "ERROR",
        })

    try:
        source = (base / "streamlit_app.py").read_text(encoding="utf-8")
    except OSError:
        source = ""
    ui_ok = all(marker in source for marker in (
        '"ecosystem.shopping": {"view": "Compras"',
        'elif selected_page == "Compras":',
        "show_shopping_list_screen()",
        '"shopping_list_snapshot": shopping_list_snapshot',
        "LOCAL_ONLY",
    ))
    checks.append({"name": "ui_route_and_context", "status": "OK" if ui_ok else "ERROR"})
    probes = [
        _read_json(base / "alerts" / "shopping_list_desktop_probe.json"),
        _read_json(base / "alerts" / "shopping_list_mobile_probe.json"),
    ]
    runtime_ok = all(
        str(report.get("status") or "").upper() == "OK"
        and int(report.get("blocking_console_error_count") or 0) == 0
        and int(report.get("blocking_page_error_count") or 0) == 0
        for report in probes
    )
    checks.append({"name": "desktop_mobile_runtime", "status": "OK" if runtime_ok else "ERROR"})
    status = "OK" if all(check["status"] == "OK" for check in checks) else "ERROR"
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "source": "local_durable",
        "sync_state": "LOCAL_ONLY",
        "checks": checks,
        "production_data_mutated": False,
        "runtime_evidence": [
            "alerts/shopping_list_desktop_probe.json",
            "alerts/shopping_list_mobile_probe.json",
        ],
    }


def write_report(payload: dict[str, Any], path: str | Path = DEFAULT_REPORT_PATH) -> Path:
    target = Path(path)
    atomic_write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica la lista de compras durable y compartida de Roxy.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    payload = build_shopping_list_check(args.root)
    write_report(payload, args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
