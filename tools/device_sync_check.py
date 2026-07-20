from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from durable_storage import atomic_write_text
from roxy_os.personal_tasks import PersonalTaskStore
from roxy_os.shopping_list import ShoppingListStore
from roxy_trader.device_sync import DEVICE_SYNC_CONTRACT_VERSION, apply_device_sync, device_sync_snapshot
from roxy_trader.ui_state import UIStateStore
from roxy_trader.watchlists import WatchlistStore
from system_diagnostics import device_sync_configuration_check


CONTRACT_VERSION = "roxy-device-sync-check/1.0.0"
DEFAULT_REPORT_PATH = Path("alerts/device_sync_check.json")


def build_device_sync_check(
    root: str | Path = ".",
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    base = Path(root)
    values = dict(env if env is not None else os.environ)
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="roxy-device-sync-check-") as directory:
        temp = Path(directory)
        watchlists = WatchlistStore(temp / "watchlists.json")
        ui_state = UIStateStore(temp / "ui.json")
        tasks = PersonalTaskStore(temp / "tasks.json")
        shopping = ShoppingListStore(temp / "shopping.json")
        user = "probe_user"
        probe_env = {**values, "ROXY_STATE_SYNC_USERS": user}
        watchlists.add_asset(user, "Principal", "AAPL", "stock")
        ui_state.write(user, {"symbol": "AAPL", "page": "Activo"})
        tasks.create(user, "Tarea sincronizada", source="diagnostic")
        shopping.add(user, "Cafe", source="diagnostic")

        snapshot = device_sync_snapshot(
            user,
            watchlists=watchlists,
            ui_state=ui_state,
            personal_tasks=tasks,
            shopping_list=shopping,
            env=probe_env,
        )
        scope_names = {"watchlists", "ui_state", "personal_tasks", "shopping_list"}
        scope_ok = snapshot.get("contract_version") == DEVICE_SYNC_CONTRACT_VERSION and all(
            int((snapshot.get(name) or {}).get("revision") or 0) == 1 for name in scope_names
        )
        checks.append({"name": "revisioned_scopes", "status": "OK" if scope_ok else "ERROR"})

        stale_tasks = dict(snapshot["personal_tasks"])
        tasks.create(user, "Cambio nuevo", source="diagnostic")
        conflict = apply_device_sync(
            user,
            {"personal_tasks": {**stale_tasks, "expected_revision": stale_tasks["revision"]}},
            watchlists=watchlists,
            ui_state=ui_state,
            personal_tasks=tasks,
            shopping_list=shopping,
            env=probe_env,
        )
        conflict_ok = conflict.get("status") == "CONFLICT" and len(tasks.list_tasks(user)) == 2
        checks.append({"name": "stale_write_protection", "status": "OK" if conflict_ok else "ERROR"})

        before = {
            "watchlists": watchlists.snapshot(user)["revision"],
            "ui_state": ui_state.snapshot(user)["revision"],
            "shopping_list": shopping.snapshot(user)["revision"],
        }
        partial = apply_device_sync(
            user,
            {
                "personal_tasks": {
                    "expected_revision": tasks.snapshot(user)["revision"],
                    "tasks": tasks.list_tasks(user, include_archived=True),
                }
            },
            watchlists=watchlists,
            ui_state=ui_state,
            personal_tasks=tasks,
            shopping_list=shopping,
            env=probe_env,
        )
        after = {
            "watchlists": watchlists.snapshot(user)["revision"],
            "ui_state": ui_state.snapshot(user)["revision"],
            "shopping_list": shopping.snapshot(user)["revision"],
        }
        partial_ok = partial.get("status") == "UPDATED" and set(partial.get("results") or {}) == {
            "personal_tasks"
        } and before == after
        checks.append({"name": "partial_scope_isolation", "status": "OK" if partial_ok else "ERROR"})

    configuration = device_sync_configuration_check(values)
    remote_ready = configuration.status == "CONNECTED"
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
    contract_ok = all(check["status"] == "OK" for check in checks)
    remote_status = "CONNECTED" if remote_ready or (gateway_ready and gateway_physical) else "READY_FOR_PHYSICAL_TEST" if gateway_ready else "NOT_CONFIGURED"
    configuration_detail = (
        "Cliente remoto autenticado por HTTPS y ligado a la CA/Bearer actuales."
        if gateway_ready and gateway_physical
        else "Gateway HTTPS/Bearer/allowlist verificado localmente; falta confiar la CA y validar un dispositivo fisico."
        if gateway_ready
        else configuration.detail
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "sync_contract_version": DEVICE_SYNC_CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if contract_ok and remote_ready else "WARN" if contract_ok else "ERROR",
        "contract_status": "OK" if contract_ok else "ERROR",
        "remote_status": remote_status,
        "scopes": sorted(scope_names),
        "checks": checks,
        "configuration_detail": configuration_detail,
        "production_data_mutated": False,
    }


def write_report(payload: Mapping[str, Any], path: str | Path = DEFAULT_REPORT_PATH) -> Path:
    target = Path(path)
    atomic_write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica el contrato de sincronizacion revisionado de Roxy.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    payload = build_device_sync_check(args.root)
    write_report(payload, args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
