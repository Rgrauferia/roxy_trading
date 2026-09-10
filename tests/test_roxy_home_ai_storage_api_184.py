from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from roxy_os.home_ai import HomeAIBudgetExceeded, HomeAIBudgetStorageError
from tools import roxy_home_service as service


def fail(error):
    raise error


@pytest.mark.parametrize("committed", [False, True])
def test_ai_wrapper_preserves_storage_error_and_uncertain_commit(committed):
    error = HomeAIBudgetStorageError("commit_confirmation_failed" if committed else "invalid_json")
    error.committed = committed
    with pytest.raises(HomeAIBudgetStorageError) as caught:
        service._ai_call(lambda: fail(error))
    assert caught.value is error
    assert caught.value.committed is committed


def test_unrelated_provider_exception_remains_sanitized():
    with pytest.raises(HTTPException) as caught:
        service._ai_call(lambda: fail(RuntimeError("secret-token-and-internal-path")))
    assert caught.value.status_code == 502
    assert "secret-token" not in caught.value.detail


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-ledger-qa")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "ledgerqa")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    service._RATE_STATE.clear()
    with TestClient(service.app, base_url="https://ledger.test",
                    headers={"Authorization": "Bearer synthetic-ledger-qa"}) as value:
        yield value


@pytest.mark.parametrize("committed", [False, True])
def test_identification_storage_failure_is_private_503_not_provider_502(client, monkeypatch, committed):
    error = HomeAIBudgetStorageError("commit_confirmation_failed" if committed else "invalid_json")
    error.committed = committed
    monkeypatch.setattr(service.HomePlantIdentifier, "from_env", lambda: SimpleNamespace(identify=lambda _: fail(error)))
    response = client.post("/v1/home-plants/ledgerqa/identify", json={"photo_data_url": "data:image/jpeg;base64," + "A" * 32})
    assert response.status_code == 503
    assert response.json()["code"] == "HOME_STORAGE_UNAVAILABLE"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["retry-after"] == "30"


def test_identification_budget_exhaustion_is_429(client, monkeypatch):
    monkeypatch.setattr(service.HomePlantIdentifier, "from_env", lambda: SimpleNamespace(identify=lambda _: fail(HomeAIBudgetExceeded("Límite alcanzado"))))
    response = client.post("/v1/home-plants/ledgerqa/identify", json={"photo_data_url": "data:image/jpeg;base64," + "A" * 32})
    assert response.status_code == 429
    assert response.json()["detail"] == "Límite alcanzado"
