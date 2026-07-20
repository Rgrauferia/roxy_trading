import pytest

from roxy_os.shopping_list import ShoppingListStore


def test_shopping_list_is_durable_isolated_and_deduplicates_pending_items(tmp_path):
    path = tmp_path / "shopping.json"
    store = ShoppingListStore(path)
    first = store.add("Robert", "Café", quantity=1, unit="bolsa", category="FOOD")
    merged = store.add("robert", "cafe", quantity=2, unit="bolsa")
    store.add("alice", "Articulo privado")

    reopened = ShoppingListStore(path)
    robert = reopened.list_items("robert")

    assert len(robert) == 1
    assert robert[0]["id"] == first["id"] == merged["id"]
    assert robert[0]["quantity"] == 3
    assert reopened.list_items("alice")[0]["name"] == "Articulo privado"


def test_shopping_list_lifecycle_is_recoverable(tmp_path):
    store = ShoppingListStore(tmp_path / "shopping.json")
    item = store.add("robert", "Leche")

    purchased = store.transition("robert", item["id"], "PURCHASED")
    archived = store.transition("robert", item["id"], "ARCHIVED")
    restored = store.transition("robert", item["id"], "PENDING")

    assert purchased["purchased_at"]
    assert archived["status"] == "ARCHIVED"
    assert restored["status"] == "PENDING"
    assert restored["purchased_at"] is None


def test_shopping_list_rejects_invalid_input_and_cross_user_mutation(tmp_path):
    store = ShoppingListStore(tmp_path / "shopping.json")
    item = store.add("robert", "Pan")

    with pytest.raises(KeyError):
        store.transition("alice", item["id"], "PURCHASED")
    with pytest.raises(ValueError):
        store.add("robert", "")
    with pytest.raises(ValueError):
        store.add("robert", "Pan", quantity=0)
    with pytest.raises(ValueError):
        store.add("robert", "Pan", category="UNKNOWN")


def test_shopping_snapshot_reports_honest_local_sync_state(tmp_path):
    store = ShoppingListStore(tmp_path / "shopping.json")
    first = store.add("robert", "Pan")
    store.add("robert", "Leche")
    store.transition("robert", first["id"], "PURCHASED")

    snapshot = store.snapshot("robert")

    assert snapshot["source"] == "local_durable"
    assert snapshot["sync_state"] == "LOCAL_ONLY"
    assert snapshot["pending_count"] == 1
    assert snapshot["purchased_count"] == 1


def test_shopping_revision_rejects_stale_device_replace(tmp_path):
    store = ShoppingListStore(tmp_path / "shopping.json")
    store.add("robert", "Pan")
    stale = store.snapshot("robert")
    store.add("robert", "Leche")

    conflict = store.replace_user_snapshot("robert", stale, expected_revision=stale["revision"])

    assert conflict["conflict"] is True
    assert conflict["current_revision"] == 2
    assert [row["name"] for row in store.list_items("robert")] == ["Leche", "Pan"]


def test_shopping_device_replace_forces_user_namespace(tmp_path):
    store = ShoppingListStore(tmp_path / "shopping.json")
    result = store.replace_user_snapshot(
        "robert",
        {"items": [{"id": "b" * 32, "user_id": "alice", "name": "Cafe", "quantity": 2}]},
        expected_revision=0,
    )
    assert result["conflict"] is False
    assert store.list_items("alice") == []
    assert store.list_items("robert")[0]["user_id"] == "robert"
