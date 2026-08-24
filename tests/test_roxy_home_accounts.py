import json

from fastapi.testclient import TestClient

from roxy_os.home_accounts import HomeAccountStore, verify_password


def test_account_store_hashes_passwords_and_limits_member_creation_to_owner(tmp_path):
    path = tmp_path / "accounts.json"
    store = HomeAccountStore(path)
    owner = store.bootstrap(
        "local_user",
        household_name="Nuestro hogar",
        username="robert",
        display_name="Robert",
        password="una-clave-segura",
    )
    partner = store.add_member(
        owner["id"], username="roxy", display_name="Roxy", password="otra-clave-segura"
    )

    raw = json.loads(path.read_text(encoding="utf-8"))
    members_by_username = {row["username"]: row for row in raw["members"].values()}
    password_hashes = [row["password_hash"] for row in members_by_username.values()]

    assert owner["storage_user_id"] == partner["storage_user_id"] == "local_user"
    assert owner["household_id"] == partner["household_id"]
    assert "una-clave-segura" not in path.read_text(encoding="utf-8")
    assert all(value.startswith("pbkdf2_sha256$600000$") for value in password_hashes)
    assert verify_password("una-clave-segura", members_by_username["robert"]["password_hash"])
    assert store.authenticate("ROBERT", "una-clave-segura")["display_name"] == "Robert"
    assert store.authenticate("robert", "incorrecta") is None
    assert owner["preferences"]["theme"] == "classic"

    try:
        store.add_member(partner["id"], username="third", display_name="Third", password="third-password")
    except PermissionError:
        pass
    else:  # pragma: no cover
        raise AssertionError("A non-owner created a household member")


def test_personalization_is_private_but_household_name_is_owner_managed(tmp_path):
    store = HomeAccountStore(tmp_path / "accounts.json")
    owner = store.bootstrap(
        "local_user", household_name="Nuestro hogar", username="robert", display_name="Robert", password="owner-password"
    )
    partner = store.add_member(
        owner["id"], username="partner", display_name="Roxy", password="partner-password"
    )

    updated_owner = store.update_personalization(
        owner["id"],
        display_name="Roberto",
        household_name="Casa Grau",
        preferences={"theme": "coastal", "background": "linen", "avatar": "home", "response_style": "brief", "text_scale": "large"},
    )
    updated_partner = store.update_personalization(
        partner["id"],
        display_name="Roxy",
        preferences={"theme": "terracotta", "background": "warm", "avatar": "professional", "response_style": "close", "text_scale": "standard"},
    )

    assert updated_owner["household_name"] == updated_partner["household_name"] == "Casa Grau"
    assert updated_owner["preferences"]["theme"] == "coastal"
    assert updated_partner["preferences"]["theme"] == "terracotta"
    assert store.authenticate("robert", "owner-password")["display_name"] == "Roberto"

    try:
        store.update_personalization(
            partner["id"], display_name="Roxy", household_name="Otra casa", preferences=updated_partner["preferences"]
        )
    except PermissionError:
        pass
    else:  # pragma: no cover
        raise AssertionError("A non-owner changed the shared household name")


def test_personalization_api_persists_for_the_signed_in_member(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-account-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "local_user")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    store = HomeAccountStore(tmp_path / "accounts.json")
    store.bootstrap(
        "local_user", household_name="Nuestro hogar", username="robert", display_name="Robert", password="owner-password"
    )
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    assert client.post("/v1/home-account/login", json={"username": "robert", "password": "owner-password"}).status_code == 200

    response = client.put(
        "/v1/home-account/preferences",
        json={
            "display_name": "Roberto",
            "household_name": "Casa Grau",
            "theme": "olive",
            "background": "clean",
            "avatar": "monogram",
            "response_style": "explanatory",
            "text_scale": "large",
        },
    )
    current = client.get("/v1/home-account/me")

    assert response.status_code == 200
    assert current.json()["display_name"] == "Roberto"
    assert current.json()["household_name"] == "Casa Grau"
    assert current.json()["preferences"] == response.json()["preferences"]


def test_two_personal_sessions_share_existing_home_data_and_personalize_roxy(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-account-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "local_user")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "food.json"))
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "agent_home_test")
    roxy_home_service._RATE_STATE.clear()
    roxy_home_service._LOGIN_RATE_STATE.clear()

    owner_client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    paired = owner_client.post(
        "/v1/shopping/session/local_user",
        headers={"Authorization": "Bearer home-account-test-key"},
    )
    existing = owner_client.post(
        "/v1/shopping/local_user",
        json={"name": "Leche existente", "quantity": 1, "unit": "litro", "category": "FOOD"},
    )
    bootstrap = owner_client.post(
        "/v1/home-account/bootstrap",
        json={
            "storage_user_id": "local_user",
            "household_name": "Nuestro hogar",
            "username": "robert",
            "display_name": "Robert",
            "password": "robert-clave-segura",
        },
    )
    partner = owner_client.post(
        "/v1/home-account/members",
        json={"username": "roxy", "display_name": "Roxy", "password": "roxy-clave-segura"},
    )

    partner_client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    login = partner_client.post(
        "/v1/home-account/login",
        json={"username": "roxy", "password": "roxy-clave-segura"},
    )
    shared_before = partner_client.get("/v1/shopping/local_user")
    personalized = partner_client.post(
        "/v1/assistant/command/local_user", json={"text": "agrega pan a mi lista"}
    )
    owner_after = owner_client.get("/v1/shopping/local_user")
    owner_voice = owner_client.get("/v1/assistant/session/local_user")
    partner_cannot_invite = partner_client.post(
        "/v1/home-account/members",
        json={"username": "third", "display_name": "Third", "password": "third-clave-segura"},
    )
    legacy_after_migration = TestClient(roxy_home_service.app, base_url="https://roxy.test").post(
        "/v1/shopping/session/local_user",
        headers={"Authorization": "Bearer home-account-test-key"},
    )

    assert paired.status_code == 200
    assert existing.status_code == 201
    assert bootstrap.status_code == 201
    assert "HttpOnly" in bootstrap.headers["set-cookie"]
    assert "Secure" in bootstrap.headers["set-cookie"]
    assert partner.status_code == 201
    assert login.status_code == 200
    assert login.json()["display_name"] == "Roxy"
    assert shared_before.json()["items"][0]["name"] == "Leche existente"
    assert personalized.json()["message"].startswith("Claro, Roxy.")
    assert {row["name"] for row in owner_after.json()["items"]} == {"Leche existente", "pan"}
    assert owner_voice.json()["dynamic_variables"]["user_name"] == "Robert"
    assert partner_cannot_invite.status_code == 403
    assert legacy_after_migration.status_code == 409


def test_login_rejects_wrong_password_without_exposing_account(tmp_path, monkeypatch):
    from tools import roxy_home_service

    store = HomeAccountStore(tmp_path / "accounts.json")
    store.bootstrap(
        "local_user",
        household_name="Casa",
        username="robert",
        display_name="Robert",
        password="correct-password",
    )
    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-account-test-key")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    roxy_home_service._LOGIN_RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")

    response = client.post(
        "/v1/home-account/login", json={"username": "robert", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Usuario o contraseña incorrectos"
