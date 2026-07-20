from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from roxy_trader.ui_state import UIStateStore, normalize_ui_state_user
from roxy_trader.watchlists import WatchlistStore, normalize_watchlist_user
from roxy_os.personal_tasks import PersonalTaskStore
from roxy_os.shopping_list import ShoppingListStore


DEVICE_SYNC_CONTRACT_VERSION = "roxy-device-sync/1.1.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def allowed_device_sync_users(env: Mapping[str, str] | None = None) -> set[str]:
    values = env if env is not None else os.environ
    configured = str(values.get("ROXY_STATE_SYNC_USERS") or "local_user")
    return {
        normalize_watchlist_user(item)
        for item in configured.split(",")
        if normalize_watchlist_user(item)
    }


def require_allowed_device_sync_user(user_id: Any, env: Mapping[str, str] | None = None) -> str:
    watchlist_user = normalize_watchlist_user(user_id)
    ui_user = normalize_ui_state_user(user_id)
    if watchlist_user != ui_user or watchlist_user not in allowed_device_sync_users(env):
        raise PermissionError("user_not_allowed_for_device_sync")
    return watchlist_user


def default_device_sync_stores(
    root: str | Path = ".",
) -> tuple[WatchlistStore, UIStateStore, PersonalTaskStore, ShoppingListStore]:
    base = Path(root)
    watchlist_path = Path(os.environ.get("ROXY_WATCHLIST_PATH") or base / "data" / "roxy_watchlists.json")
    ui_path = Path(os.environ.get("ROXY_UI_STATE_PATH") or base / "alerts" / "dashboard_ui_state.json")
    tasks_path = Path(os.environ.get("ROXY_PERSONAL_TASK_PATH") or base / "data" / "roxy_personal_tasks.json")
    shopping_path = Path(os.environ.get("ROXY_SHOPPING_LIST_PATH") or base / "data" / "roxy_shopping_list.json")
    return (
        WatchlistStore(watchlist_path),
        UIStateStore(ui_path),
        PersonalTaskStore(tasks_path),
        ShoppingListStore(shopping_path),
    )


def device_sync_snapshot(
    user_id: Any,
    *,
    watchlists: WatchlistStore,
    ui_state: UIStateStore,
    personal_tasks: PersonalTaskStore | None = None,
    shopping_list: ShoppingListStore | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    user = require_allowed_device_sync_user(user_id, env)
    watchlist_snapshot = watchlists.snapshot(user)
    ui_snapshot = ui_state.snapshot(user)
    result = {
        "contract_version": DEVICE_SYNC_CONTRACT_VERSION,
        "generated_at": _now_iso(),
        "status": "OK",
        "user_id": user,
        "watchlists": {
            key: value
            for key, value in watchlist_snapshot.items()
            if key not in {"source", "user_id", "updated_at"}
        },
        "ui_state": {
            "state": ui_snapshot.get("state") or {},
            "revision": int(ui_snapshot.get("revision") or 0),
            "updated_at": str(ui_snapshot.get("updated_at") or ""),
        },
    }
    if personal_tasks is not None:
        task_snapshot = personal_tasks.snapshot(user, limit=1000)
        result["personal_tasks"] = {
            "revision": int(task_snapshot.get("revision") or 0),
            "updated_at": str(task_snapshot.get("updated_at") or ""),
            "tasks": personal_tasks.list_tasks(user, include_archived=True, limit=1000),
        }
    if shopping_list is not None:
        shopping_snapshot = shopping_list.snapshot(user, limit=1000)
        result["shopping_list"] = {
            "revision": int(shopping_snapshot.get("revision") or 0),
            "updated_at": str(shopping_snapshot.get("updated_at") or ""),
            "items": shopping_list.list_items(user, include_archived=True, limit=1000),
        }
    return result


def apply_device_sync(
    user_id: Any,
    payload: dict[str, Any],
    *,
    watchlists: WatchlistStore,
    ui_state: UIStateStore,
    personal_tasks: PersonalTaskStore | None = None,
    shopping_list: ShoppingListStore | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    user = require_allowed_device_sync_user(user_id, env)
    incoming = payload if isinstance(payload, dict) else {}
    results: dict[str, Any] = {}
    watchlist_payload = incoming.get("watchlists")
    if isinstance(watchlist_payload, dict):
        results["watchlists"] = watchlists.replace_user_snapshot(
            user,
            watchlist_payload,
            expected_revision=max(0, int(watchlist_payload.get("expected_revision") or 0)),
        )
    ui_payload = incoming.get("ui_state")
    if isinstance(ui_payload, dict):
        results["ui_state"] = ui_state.replace(
            user,
            ui_payload.get("state") if isinstance(ui_payload.get("state"), dict) else {},
            expected_revision=max(0, int(ui_payload.get("expected_revision") or 0)),
        )
    task_payload = incoming.get("personal_tasks")
    if personal_tasks is not None and isinstance(task_payload, dict):
        results["personal_tasks"] = personal_tasks.replace_user_snapshot(
            user,
            task_payload,
            expected_revision=max(0, int(task_payload.get("expected_revision") or 0)),
        )
    shopping_payload = incoming.get("shopping_list")
    if shopping_list is not None and isinstance(shopping_payload, dict):
        results["shopping_list"] = shopping_list.replace_user_snapshot(
            user,
            shopping_payload,
            expected_revision=max(0, int(shopping_payload.get("expected_revision") or 0)),
        )
    if not results:
        return {
            "contract_version": DEVICE_SYNC_CONTRACT_VERSION,
            "generated_at": _now_iso(),
            "status": "NO_CHANGES",
            "user_id": user,
            "results": {},
        }
    conflict = any(bool(result.get("conflict")) for result in results.values() if isinstance(result, dict))
    return {
        "contract_version": DEVICE_SYNC_CONTRACT_VERSION,
        "generated_at": _now_iso(),
        "status": "CONFLICT" if conflict else "UPDATED",
        "user_id": user,
        "results": results,
    }
