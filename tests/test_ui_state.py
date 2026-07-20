import json

from roxy_trader.ui_state import UI_STATE_SCHEMA_VERSION, UIStateStore


def test_ui_state_is_isolated_by_user_and_durable(tmp_path):
    path = tmp_path / "dashboard_ui_state.json"
    store = UIStateStore(path)

    store.write("alice@example.com", {"symbol": "AAPL", "market": "stock", "timeframe": "15m", "page": "Activo"})
    store.write("bob@example.com", {"symbol": "BTC/USD", "market": "crypto", "timeframe": "1h", "page": "Alertas"})

    assert UIStateStore(path).read("alice@example.com")["symbol"] == "AAPL"
    assert UIStateStore(path).read("bob@example.com")["symbol"] == "BTC/USD"
    assert UIStateStore(path).read("missing@example.com") == {}
    assert json.loads(path.read_text())["schema_version"] == UI_STATE_SCHEMA_VERSION


def test_legacy_global_state_migrates_only_to_local_user(tmp_path):
    path = tmp_path / "dashboard_ui_state.json"
    path.write_text(json.dumps({"symbol": "MSFT", "market": "stock", "timeframe": "4h", "page": "Activo"}))

    store = UIStateStore(path)

    assert store.read("local_user")["symbol"] == "MSFT"
    assert store.read("alice@example.com") == {}


def test_ui_state_normalizes_user_key_and_replaces_state_atomically(tmp_path):
    path = tmp_path / "dashboard_ui_state.json"
    store = UIStateStore(path)
    store.write("Alice Smith", {"symbol": "eth/usd", "market": "crypto", "timeframe": "1h", "page": "Activo"})
    store.write("Alice Smith", {"symbol": "link/usd", "market": "crypto", "timeframe": "2h", "page": "Alertas"})

    assert store.read("alice_smith") == {
        "symbol": "LINK/USD",
        "market": "crypto",
        "timeframe": "2h",
        "page": "Alertas",
    }
    assert not list(tmp_path.glob("*.tmp"))


def test_ui_state_revision_is_stable_for_same_value_and_rejects_stale_replace(tmp_path):
    store = UIStateStore(tmp_path / "state.json")
    state = {"symbol": "AAPL", "market": "stock", "timeframe": "15m", "page": "Activo"}
    store.write("user", state)
    store.write("user", state)
    assert store.snapshot("user")["revision"] == 1

    store.write("user", {**state, "symbol": "MSFT"})
    conflict = store.replace("user", state, expected_revision=1)
    assert conflict["conflict"] is True
    assert store.read("user")["symbol"] == "MSFT"
