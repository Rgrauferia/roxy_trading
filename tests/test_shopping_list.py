import pytest

from roxy_os.shopping_list import (
    ShoppingListStore,
    classify_shopping_category,
    normalize_shopping_item,
    normalize_shopping_name,
)


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
    assert [row["name"] for row in store.list_items("robert")] == ["Pan", "Leche"]


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


def test_shopping_quantity_delete_complete_and_history_are_user_scoped(tmp_path):
    store = ShoppingListStore(tmp_path / "shopping.json")
    milk = store.add("robert", "Leche", quantity=1, category="FOOD")
    store.add("robert", "Café", quantity=2, category="HOUSEHOLD")
    private = store.add("alice", "Privado")

    updated = store.set_quantity("robert", milk["id"], 3)
    deleted = store.delete_named("robert", "café")
    completed = store.complete_purchase("robert")

    assert updated["quantity"] == 3
    assert deleted["name"] == "Café"
    assert completed["completed"] is True
    assert completed["count"] == 1
    assert store.list_items("robert") == []
    assert store.history("robert")[0]["items"][0]["name"] == "Leche"
    assert store.history("alice") == []
    assert store.list_items("alice")[0]["id"] == private["id"]


def test_complete_purchase_is_idempotent_when_list_is_empty(tmp_path):
    store = ShoppingListStore(tmp_path / "shopping.json")

    result = store.complete_purchase("robert")

    assert result == {"completed": False, "trip": None, "count": 0, "total_quantity": 0.0}
    assert store.history("robert") == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("agrega pan a mi lista de compras", "pan"),
        ("gel de cejas a la lista", "gel de cejas"),
        ("por favor añade detergente en la lista de compra", "detergente"),
    ],
)
def test_shopping_name_removes_voice_destination_prefixes_and_suffixes(raw, expected):
    assert normalize_shopping_name(raw) == expected


def test_inline_voice_quantity_and_unit_are_structured_before_storage(tmp_path):
    assert normalize_shopping_item("dos paquetes de agua a mi lista") == ("agua", 2.0, "paquete")
    store = ShoppingListStore(tmp_path / "shopping.json")

    item = store.add("robert", "3 botellas de leche a la lista de compras")

    assert item["name"] == "leche"
    assert item["quantity"] == 3.0
    assert item["unit"] == "botella"


def test_explicit_recipe_measurement_is_never_overridden_by_name_parser(tmp_path):
    store = ShoppingListStore(tmp_path / "shopping.json")

    item = store.add("robert", "2 paquetes de levadura", quantity=500, unit="gramos")

    assert item["name"] == "2 paquetes de levadura"
    assert item["quantity"] == 500.0
    assert item["unit"] == "gramo"


@pytest.mark.parametrize(
    ("product", "expected"),
    [
        ("café", "BEVERAGES"), ("aceite de oliva", "PANTRY"), ("agua", "BEVERAGES"),
        ("tomates", "PRODUCE"), ("leche", "DAIRY_EGGS"), ("pollo", "MEAT_SEAFOOD"),
        ("pan cubano", "BAKERY"), ("helado", "FROZEN"), ("pañales", "BABY"),
        ("detergente de lavar", "CLEANING"), ("papel toalla", "CLEANING"),
        ("papel higiénico", "PERSONAL"), ("gel de cejas", "PERSONAL"),
        ("ibuprofeno", "HEALTH"), ("bombillos LED", "HOUSEHOLD"),
        ("cargador USB", "HOUSEHOLD"), ("destornillador", "HOUSEHOLD"),
        ("arena para gato", "PETS"),
        ("pass para Bella", "PETS"), ("pads para Luna", "PETS"),
        ("bolitas de olor", "CLEANING"),
    ],
)
def test_shopping_category_classifier_uses_product_meaning(product, expected):
    assert classify_shopping_category(product) == expected


def test_category_classifier_prefers_specific_product_over_stale_client_category():
    assert classify_shopping_category("detergente", "HOUSEHOLD") == "CLEANING"
    assert classify_shopping_category("café", "HOUSEHOLD") == "BEVERAGES"
    assert classify_shopping_category("organizador de zapatos", "HOUSEHOLD") == "HOUSEHOLD"
    assert classify_shopping_category("artículo desconocido") == "OTHER"


def test_existing_items_are_reclassified_without_losing_user_data(tmp_path):
    path = tmp_path / "shopping.json"
    path.write_text(
        '{"items": ['
        '{"id":"1","user_id":"robert","name":"Café","quantity":2,"unit":"bolsa","category":"HOUSEHOLD"},'
        '{"id":"2","user_id":"robert","name":"Detergente","quantity":1,"unit":"botella","category":"HOUSEHOLD"}'
        '], "trips": [], "product_memory": {}, "user_revisions": {}}',
        encoding="utf-8",
    )

    rows = ShoppingListStore(path).list_items("robert")

    assert [(row["name"], row["quantity"], row["category"]) for row in rows] == [
        ("Café", 2, "BEVERAGES"), ("Detergente", 1, "CLEANING")
    ]


def test_add_auto_classifies_voice_and_ui_products(tmp_path):
    store = ShoppingListStore(tmp_path / "shopping.json")

    soap = store.add("robert", "jabón de platos", source="voice_or_text")
    fruit = store.add("robert", "manzanas", category="GENERAL", source="roxy_home_pwa")

    assert soap["category"] == "CLEANING"
    assert fruit["category"] == "PRODUCE"


@pytest.mark.parametrize(
    ("spoken", "canonical"),
    [
        ("pad para Luna", "Empapadores absorbentes para mascota"),
        ("pass para Bella", "Empapadores absorbentes para mascota"),
        ("bolitas de olor", "Perlas aromáticas para ropa"),
    ],
)
def test_household_vocabulary_uses_real_product_names(spoken, canonical):
    assert normalize_shopping_name(spoken) == canonical


def test_private_product_aliases_are_learned_per_user(tmp_path):
    store = ShoppingListStore(tmp_path / "shopping.json")
    learned = store.learn_alias("robert", "las blancas", "Empapadores absorbentes para mascota", unit="paquete")
    robert_item = store.add("robert", "las blancas")
    other_item = store.add("otro", "las blancas")

    assert learned["source"] == "user_correction"
    assert robert_item["name"] == "Empapadores absorbentes para mascota"
    assert robert_item["category"] == "PETS"
    assert robert_item["unit"] == "paquete"
    assert other_item["name"] == "las blancas"


def test_known_household_nickname_is_saved_as_real_product(tmp_path):
    store = ShoppingListStore(tmp_path / "shopping.json")

    item = store.add("robert", "pad para Luna")

    assert item["name"] == "Empapadores absorbentes para mascota"
    assert item["category"] == "PETS"
    assert item["unit"] == "paquete"
