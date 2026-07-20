from fastapi.testclient import TestClient

from roxy_trader.device_sync import (
    DEVICE_SYNC_CONTRACT_VERSION,
    apply_device_sync,
    device_sync_snapshot,
)
from roxy_trader.ui_state import UIStateStore
from roxy_trader.watchlists import WatchlistStore
from roxy_os.personal_tasks import PersonalTaskStore
from roxy_os.shopping_list import ShoppingListStore


def stores(tmp_path):
    return WatchlistStore(tmp_path / "watchlists.json"), UIStateStore(tmp_path / "ui.json")


def personal_stores(tmp_path):
    return PersonalTaskStore(tmp_path / "tasks.json"), ShoppingListStore(tmp_path / "shopping.json")


def test_device_sync_snapshot_is_revisioned_and_user_scoped(tmp_path):
    watchlists, ui_state = stores(tmp_path)
    watchlists.add_asset("local_user", "Principal", "AAPL", "stock")
    ui_state.write("local_user", {"symbol": "AAPL", "market": "stock", "timeframe": "15m", "page": "Activo"})

    snapshot = device_sync_snapshot(
        "local_user",
        watchlists=watchlists,
        ui_state=ui_state,
        env={"ROXY_STATE_SYNC_USERS": "local_user"},
    )

    assert snapshot["contract_version"] == DEVICE_SYNC_CONTRACT_VERSION
    assert snapshot["watchlists"]["revision"] == 1
    assert snapshot["ui_state"]["revision"] == 1
    assert snapshot["watchlists"]["lists"]["Principal"]["items"][0]["symbol"] == "AAPL"


def test_device_sync_detects_stale_device_revision_without_overwriting(tmp_path):
    watchlists, ui_state = stores(tmp_path)
    watchlists.add_asset("local_user", "Principal", "AAPL", "stock")
    initial = watchlists.snapshot("local_user")
    watchlists.add_asset("local_user", "Principal", "MSFT", "stock")

    result = apply_device_sync(
        "local_user",
        {"watchlists": {**initial, "expected_revision": initial["revision"]}},
        watchlists=watchlists,
        ui_state=ui_state,
        env={"ROXY_STATE_SYNC_USERS": "local_user"},
    )

    assert result["status"] == "CONFLICT"
    assert result["results"]["watchlists"]["current_revision"] == 2
    assert [row["symbol"] for row in watchlists.snapshot("local_user")["lists"]["Principal"]["items"]] == [
        "AAPL",
        "MSFT",
    ]


def test_device_sync_cannot_roll_back_durable_notification_delivery(tmp_path):
    watchlists, ui_state = stores(tmp_path)
    created = watchlists.create_price_alert(
        "local_user", symbol="BTC/USD", market="crypto", alert_type="price_above", threshold=100
    )["alert"]
    watchlists.evaluate_price_alerts("local_user", {"BTC/USD": 101})
    pending_device = watchlists.snapshot("local_user")
    assert pending_device["alerts"][0]["notification_status"] == "PENDING"
    watchlists.record_alert_notification_state(
        "local_user", created["id"], delivered=True, detail="recorded_local", channels=[]
    )
    assert watchlists.snapshot("local_user")["revision"] == pending_device["revision"]

    result = apply_device_sync(
        "local_user",
        {"watchlists": {**pending_device, "expected_revision": pending_device["revision"]}},
        watchlists=watchlists,
        ui_state=ui_state,
        env={"ROXY_STATE_SYNC_USERS": "local_user"},
    )

    assert result["status"] == "UPDATED"
    alert = watchlists.snapshot("local_user")["alerts"][0]
    assert alert["status"] == "Activada"
    assert alert["notification_status"] == "DELIVERED"
    assert alert["notification_attempts"] == 1
    assert alert["notified_at"]


def test_device_sync_rejects_users_outside_explicit_allowlist(tmp_path):
    watchlists, ui_state = stores(tmp_path)
    try:
        device_sync_snapshot(
            "other-user",
            watchlists=watchlists,
            ui_state=ui_state,
            env={"ROXY_STATE_SYNC_USERS": "local_user"},
        )
    except PermissionError as exc:
        assert "user_not_allowed" in str(exc)
    else:
        raise AssertionError("A remote device must not select an arbitrary user namespace")


def test_device_sync_snapshot_includes_revisioned_tasks_and_shopping(tmp_path):
    watchlists, ui_state = stores(tmp_path)
    tasks, shopping = personal_stores(tmp_path)
    tasks.create("local_user", "Llamar al cliente")
    shopping.add("local_user", "Cafe", quantity=2)

    snapshot = device_sync_snapshot(
        "local_user",
        watchlists=watchlists,
        ui_state=ui_state,
        personal_tasks=tasks,
        shopping_list=shopping,
        env={"ROXY_STATE_SYNC_USERS": "local_user"},
    )

    assert snapshot["personal_tasks"]["revision"] == 1
    assert snapshot["personal_tasks"]["tasks"][0]["title"] == "Llamar al cliente"
    assert snapshot["shopping_list"]["revision"] == 1
    assert snapshot["shopping_list"]["items"][0]["quantity"] == 2


def test_device_sync_stale_personal_state_cannot_overwrite_newer_changes(tmp_path):
    watchlists, ui_state = stores(tmp_path)
    tasks, shopping = personal_stores(tmp_path)
    tasks.create("local_user", "Primera")
    shopping.add("local_user", "Pan")
    stale_tasks = tasks.snapshot("local_user")
    stale_tasks["tasks"] = tasks.list_tasks("local_user", include_archived=True)
    stale_shopping = shopping.snapshot("local_user")
    stale_shopping["items"] = shopping.list_items("local_user", include_archived=True)
    tasks.create("local_user", "Segunda")
    shopping.add("local_user", "Leche")

    result = apply_device_sync(
        "local_user",
        {
            "personal_tasks": {**stale_tasks, "expected_revision": stale_tasks["revision"]},
            "shopping_list": {**stale_shopping, "expected_revision": stale_shopping["revision"]},
        },
        watchlists=watchlists,
        ui_state=ui_state,
        personal_tasks=tasks,
        shopping_list=shopping,
        env={"ROXY_STATE_SYNC_USERS": "local_user"},
    )

    assert result["status"] == "CONFLICT"
    assert result["results"]["personal_tasks"]["current_revision"] == 2
    assert result["results"]["shopping_list"]["current_revision"] == 2
    assert len(tasks.list_tasks("local_user")) == 2
    assert len(shopping.list_items("local_user")) == 2


def test_state_sync_http_requires_bearer_and_returns_conflict_as_409(tmp_path, monkeypatch):
    from tools import voice_service

    watchlists, ui_state = stores(tmp_path)
    watchlists.add_asset("local_user", "Principal", "AAPL", "stock")
    monkeypatch.setenv("VOICE_API_KEY", "sync-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "local_user")
    tasks, shopping = personal_stores(tmp_path)
    tasks.create("local_user", "Sync task")
    shopping.add("local_user", "Sync item")
    monkeypatch.setattr(
        voice_service,
        "default_device_sync_stores",
        lambda: (watchlists, ui_state, tasks, shopping),
    )
    voice_service._RATE_STATE.clear()
    client = TestClient(voice_service.app)

    denied = client.get("/v1/state-sync/local_user")
    accepted = client.get(
        "/v1/state-sync/local_user", headers={"Authorization": "Bearer sync-test-key"}
    )
    conflict = client.put(
        "/v1/state-sync/local_user",
        headers={"Authorization": "Bearer sync-test-key"},
        json={"watchlists": {"expected_revision": 0, "lists": {}}},
    )

    assert denied.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["auth_mode"] == "bearer"
    assert accepted.json()["watchlists"]["revision"] == 1
    assert accepted.json()["personal_tasks"]["revision"] == 1
    assert accepted.json()["shopping_list"]["revision"] == 1
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["status"] == "CONFLICT"


def test_state_sync_http_partial_update_does_not_touch_omitted_scopes(tmp_path, monkeypatch):
    from tools import voice_service

    watchlists, ui_state = stores(tmp_path)
    tasks, shopping = personal_stores(tmp_path)
    watchlists.add_asset("local_user", "Principal", "AAPL", "stock")
    ui_state.write("local_user", {"symbol": "AAPL", "page": "Activo"})
    shopping.add("local_user", "Cafe")
    monkeypatch.setenv("VOICE_API_KEY", "sync-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "local_user")
    monkeypatch.setattr(
        voice_service,
        "default_device_sync_stores",
        lambda: (watchlists, ui_state, tasks, shopping),
    )
    voice_service._RATE_STATE.clear()
    client = TestClient(voice_service.app)

    response = client.put(
        "/v1/state-sync/local_user",
        headers={"Authorization": "Bearer sync-test-key"},
        json={
            "personal_tasks": {
                "expected_revision": 0,
                "tasks": [{"title": "Solo esta tarea", "status": "PENDING"}],
            }
        },
    )

    assert response.status_code == 200
    assert set(response.json()["results"]) == {"personal_tasks"}
    assert watchlists.snapshot("local_user")["revision"] == 1
    assert ui_state.snapshot("local_user")["revision"] == 1
    assert shopping.snapshot("local_user")["revision"] == 1
