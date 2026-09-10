import pytest
from fastapi.testclient import TestClient
from roxy_os.home_accounts import HomeAccountStore


@pytest.fixture
def context(tmp_path, monkeypatch):
    for key, filename in {
        "ROXY_HOME_ACCOUNTS_PATH": "accounts.json", "ROXY_HOME_FAMILY_PATH": "family.json",
        "ROXY_HOME_COMMERCE_PATH": "commerce.json", "ROXY_SHOPPING_LIST_PATH": "shopping.json",
        "ROXY_HOME_MEMORY_PATH": "food.json",
    }.items():
        monkeypatch.setenv(key, str(tmp_path / filename))
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-storage-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "storageqa")
    from tools import roxy_home_service as service
    service._RATE_STATE.clear()
    service._LOGIN_RATE_STATE.clear()
    HomeAccountStore(tmp_path / "accounts.json").bootstrap(
        "storageqa", household_name="QA only", username="storageqa", display_name="QA", password="synthetic-password",
    )
    client = TestClient(service.app, base_url="https://roxy.test")
    assert client.post("/v1/home-account/login", json={"username": "storageqa", "password": "synthetic-password"}).status_code == 200
    return client, service, tmp_path


@pytest.mark.parametrize("filename,url", [
    ("family.json", "/v1/home-family"),
    ("commerce.json", "/v1/home-commerce/storageqa"),
    ("commerce.json", "/v1/home-commerce/storageqa/recommendations"),
])
@pytest.mark.parametrize("raw", [b'{"broken":', b'{"households":[],"profiles":[]}', b'\xff'])
def test_public_get_fails_closed_without_disclosing_path_or_overwriting(context, filename, url, raw):
    client, _, directory = context
    path = directory / filename
    path.write_bytes(raw)
    response = client.get(url)
    assert response.status_code == 503
    assert response.json()["code"] == "HOME_STORAGE_UNAVAILABLE"
    assert str(directory) not in response.text
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["retry-after"] == "30"
    assert path.read_bytes() == raw


@pytest.mark.parametrize("filename,url", [("family.json", "/v1/home-family"), ("commerce.json", "/v1/home-commerce/storageqa")])
def test_storage_error_does_not_bypass_authentication(context, filename, url):
    _, service, directory = context
    (directory / filename).write_bytes(b'broken')
    response = TestClient(service.app, base_url="https://roxy.test").get(url)
    assert response.status_code == 401


def test_api_rejects_numeric_unit_without_erasing_other_inventory(context):
    client, service, directory = context
    store = service._home_food_store()
    store.replace_pantry("storageqa", [{"name": "Arroz QA", "quantity": 2, "unit": "kg"}])
    before = store.path.read_bytes()
    response = client.put("/v1/home-food/storageqa/pantry", json={"items": [{"name": "Leche", "quantity": 1, "unit": "5"}]})
    assert response.status_code == 422
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("quantity", [True, False])
def test_api_rejects_boolean_before_numeric_coercion_without_erasing_inventory(context, quantity):
    client, service, _ = context
    store = service._home_food_store()
    store.replace_pantry("storageqa", [{"name": "Arroz QA", "quantity": 2, "unit": "kg"}])
    before = store.path.read_bytes()
    response = client.put("/v1/home-food/storageqa/pantry", json={"items": [{"name": "Leche", "quantity": quantity, "unit": "litros"}]})
    assert response.status_code == 422
    assert store.path.read_bytes() == before
