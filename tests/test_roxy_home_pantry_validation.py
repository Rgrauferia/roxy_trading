import pytest

from roxy_os.home_food import HomeFoodStore


@pytest.fixture
def store(tmp_path):
    value = HomeFoodStore(tmp_path / "food.json")
    value.replace_pantry("home", [{"name": "Arroz QA", "quantity": 2, "unit": "kg"}])
    return value


@pytest.mark.parametrize("method", ["replace_pantry", "upsert_pantry"])
@pytest.mark.parametrize("bad", [None, {}, {"name": ""}, {"name": " "}, {"name": "x" * 121},
    {"name": "Leche", "quantity": 0}, {"name": "Leche", "quantity": None},
    {"name": "Leche", "quantity": False}, {"name": "Leche", "quantity": 0.00001},
    {"name": "Leche", "quantity": float("nan")}, {"name": "Leche", "quantity": float("inf")},
    {"name": "Leche", "unit": "5"}, {"name": "Leche", "unit": " "}, {"name": "Leche", "unit": "g" * 33}])
def test_invalid_edit_rejects_entire_list_and_preserves_bytes(store, method, bad):
    before = store.path.read_bytes()
    with pytest.raises(ValueError):
        getattr(store, method)("home", [{"name": "Huevos", "quantity": 6, "unit": "unidades"}, bad])
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("method,limit", [("replace_pantry", 500), ("upsert_pantry", 100)])
def test_overflow_is_rejected_not_truncated(store, method, limit):
    before = store.path.read_bytes()
    with pytest.raises(ValueError):
        getattr(store, method)("home", [{"name": "Arroz", "quantity": 1, "unit": "g"}] * (limit + 1))
    assert store.path.read_bytes() == before


def test_valid_decimal_preserved_and_other_household_untouched(store):
    rows = store.replace_pantry("second", [{"name": "Leche QA", "quantity": 1.5, "unit": "litros"}])
    assert rows[0]["quantity"] == 1.5
    assert store.snapshot("home")["pantry"][0]["name"] == "Arroz QA"


def test_explicit_empty_list_can_clear_inventory(store):
    assert store.replace_pantry("home", []) == []
