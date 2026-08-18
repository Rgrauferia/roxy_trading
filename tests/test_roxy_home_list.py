from fastapi.testclient import TestClient

from roxy_os.shopping_list import ShoppingListStore


def test_roxy_home_list_pwa_shell_is_installable_and_offline_capable():
    from tools import roxy_home_service

    client = TestClient(roxy_home_service.app)
    page = client.get("/lista")
    manifest = client.get("/lista-manifest.json")
    worker = client.get("/lista-sw.js")
    script = client.get("/assets/roxy_list.js")

    assert page.status_code == 200
    assert 'href="/lista-manifest.json"' in page.text
    assert 'src="/assets/roxy_list.js?v=9"' in page.text
    assert '/assets/roxy_list.js?v=9' in worker.text
    assert "unsafe-inline" not in page.headers["content-security-policy"]
    assert manifest.json()["start_url"] == "/home"
    assert manifest.json()["scope"] == "/home"
    assert manifest.json()["display"] == "standalone"
    assert worker.headers["service-worker-allowed"] == "/lista"
    assert "indexedDB" in script.text
    assert "navigator.share" in script.text
    assert "startRoxyVoice" in script.text
    assert "Conversation.startSession" in script.text
    assert "connectionType:'websocket'" in script.text
    assert "permissionStream" not in script.text
    assert "Roxy te está escuchando" in script.text
    assert "@elevenlabs/client@1.8.1" in script.text
    assert "La aplicación actual es Roxy Home" in script.text
    assert "sendCommandToRoxyOS" in script.text
    assert 'id="roxyVoiceLauncher"' in page.text
    assert "microphone=(self)" in page.headers["permissions-policy"]
    assert "https://*.elevenlabs.io" in page.headers["content-security-policy"]
    assert "worker-src 'self' blob:" in page.headers["content-security-policy"]
    assert "script-src 'self' blob:" in page.headers["content-security-policy"]
    assert "localStorage.setItem('roxyShoppingUser'" in script.text
    assert "localStorage.setItem('apiToken'" not in script.text


def test_shopping_api_crud_complete_history_and_user_isolation(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "shopping-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer shopping-test-key"}

    created = client.post(
        "/v1/shopping/robert",
        headers=headers,
        json={"name": "Leche", "quantity": 1, "unit": "litro", "category": "FOOD"},
    )
    item_id = created.json()["item"]["id"]
    updated = client.patch(f"/v1/shopping/robert/{item_id}", headers=headers, json={"quantity": 3})
    private = client.post("/v1/shopping/alice", headers=headers, json={"name": "Privado"})
    completed = client.post("/v1/shopping/robert/complete", headers=headers)
    snapshot = client.get("/v1/shopping/robert", headers=headers)
    alice = client.get("/v1/shopping/alice", headers=headers)

    assert created.status_code == 201
    assert updated.json()["item"]["quantity"] == 3
    assert private.status_code == 201
    assert completed.json()["count"] == 1
    assert snapshot.json()["items"] == []
    assert snapshot.json()["history"][0]["items"][0]["name"] == "Leche"
    assert alice.json()["items"][0]["name"] == "Privado"


def test_mobile_session_cookie_is_httponly_secure_and_bound_to_user(monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "shopping-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")

    paired = client.post(
        "/v1/shopping/session/robert",
        headers={"Authorization": "Bearer shopping-test-key"},
    )
    denied = client.get("/v1/shopping/alice")

    cookie = paired.headers["set-cookie"]
    assert paired.status_code == 200
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert "Max-Age=31536000" in cookie
    assert "shopping-test-key" not in cookie
    assert denied.status_code == 403


def test_roxy_home_is_a_separate_app_surface(monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "shopping-test-key")
    client = TestClient(roxy_home_service.app)

    assert client.get("/", follow_redirects=False).headers["location"] == "/home"
    assert client.get("/home").status_code == 200
    assert client.get("/home-sw.js").headers["service-worker-allowed"] == "/home"
    assert client.get("/health").json()["service"] == "roxy-home"
    assert client.get("/_stcore/health").status_code == 404
    assert client.get("/roxy-mobile").status_code == 404


def test_roxy_home_shared_elevenlabs_agent_can_read_and_update_shopping_list(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "shopping-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "agent_shared_roxy")
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    client.post(
        "/v1/shopping/session/robert",
        headers={"Authorization": "Bearer shopping-test-key"},
    )

    session = client.get("/v1/assistant/session/robert")
    command = client.post(
        "/v1/assistant/command/robert",
        json={"text": "agrega pan a mi lista de compra"},
    )
    shopping = client.get("/v1/shopping/robert")

    assert session.status_code == 200
    assert session.json()["provider"] == "ElevenLabs"
    assert session.json()["agent_id"] == "agent_shared_roxy"
    assert session.json()["voice_mode"] == "public_websocket"
    assert session.json()["connection_type"] == "websocket"
    assert command.status_code == 200
    assert command.json()["ok"] is True
    assert command.json()["agent"] == "shopping"
    assert "pan" in command.json()["message"].lower()
    assert shopping.json()["items"][0]["name"].lower() == "pan"
