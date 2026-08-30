from fastapi.testclient import TestClient

from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_family import HomeFamilyStore


def test_family_store_keeps_presence_private_and_scoped_to_household(tmp_path):
    store = HomeFamilyStore(tmp_path / "family.json")
    members = [
        {"id": "robert", "display_name": "Robert", "role": "OWNER"},
        {"id": "roxy", "display_name": "Roxy", "role": "MEMBER"},
    ]

    store.update_location("casa-1", "robert", latitude=28.5383, longitude=-81.3792, accuracy_m=20, consent=True)
    shared = store.snapshot("casa-1", members, "robert")
    private = store.snapshot("casa-2", members, "robert")

    assert shared["members"][0]["sharing_enabled"] is True
    assert shared["members"][0]["location"]["latitude"] == 28.5383
    assert private["members"][0]["location"] is None
    store.stop_sharing("casa-1", "robert")
    assert store.snapshot("casa-1", members, "robert")["members"][0]["location"] is None


def test_family_store_records_route_telemetry_and_erases_it_on_stop(tmp_path):
    store = HomeFamilyStore(tmp_path / "family.json")
    members = [{"id": "robert", "display_name": "Robert", "role": "OWNER"}]
    store.update_location(
        "casa-1", "robert", latitude=28.538300, longitude=-81.379200,
        accuracy_m=8, speed_mps=4.5, heading_deg=361, altitude_m=31.2,
        recorded_at="2026-08-29T12:00:00Z", consent=True,
    )
    points = store.history("casa-1", "robert")
    assert len(points) == 1
    assert points[0]["speed_mps"] == 4.5
    assert points[0]["heading_deg"] == 1.0
    assert points[0]["source"] == "FOREGROUND_WEB"
    assert store.history("otra-casa", "robert") == []
    store.stop_sharing("casa-1", "robert")
    assert store.history("casa-1", "robert") == []


def test_family_sharing_preference_survives_reopening_until_manual_stop(tmp_path):
    path = tmp_path / "family.json"
    members = [{"id": "robert", "display_name": "Robert", "role": "OWNER"}]
    HomeFamilyStore(path).update_location(
        "casa-1", "robert", latitude=28.5383, longitude=-81.3792, accuracy_m=10, consent=True
    )

    reopened = HomeFamilyStore(path)
    viewer = reopened.snapshot("casa-1", members, "robert")["members"][0]
    assert viewer["sharing_enabled"] is True
    assert viewer["location"] is not None

    reopened.stop_sharing("casa-1", "robert")
    stopped = HomeFamilyStore(path).snapshot("casa-1", members, "robert")["members"][0]
    assert stopped["sharing_enabled"] is False
    assert stopped["location"] is None


def test_external_invitation_is_single_use_and_scoped_only_to_nexo(tmp_path):
    store = HomeFamilyStore(tmp_path / "family.json")
    store.remember_household_members("casa-1", [{"id": "owner", "display_name": "Robert", "role": "OWNER"}])
    invitation = store.create_invitation(
        "casa-1", actor_id="owner", display_name="Amiga", relationship="Persona de confianza"
    )
    guest = {"id": "guest", "display_name": "Ana", "role": "OWNER", "preferences": {}}
    accepted = store.redeem_invitation(invitation["token"], guest)

    assert accepted["access_scope"] == "NEXO_ONLY"
    assert store.resolve_household("casa-2", "guest") == ("casa-1", "NEXO_ONLY")
    snapshot = store.snapshot("casa-1", [], "guest")
    external = next(row for row in snapshot["members"] if row["id"] == "guest")
    assert external["external"] is True
    assert external["relationship"] == "Persona de confianza"
    try:
        store.redeem_invitation(invitation["token"], guest)
    except ValueError as exc:
        assert "utilizada" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected a single-use invitation")


def test_family_store_rejects_unusable_accuracy(tmp_path):
    store = HomeFamilyStore(tmp_path / "family.json")
    try:
        store.update_location("casa-1", "robert", latitude=28, longitude=-81, accuracy_m=9000, consent=True)
    except ValueError as exc:
        assert "imprecisa" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected inaccurate location to be rejected")


def test_family_store_creates_shopping_reminder_after_leaving_work(tmp_path):
    store = HomeFamilyStore(tmp_path / "family.json")
    store.save_place("casa-1", name="Trabajo", kind="WORK", latitude=28.5000, longitude=-81.3000, radius_m=200)
    store.update_location("casa-1", "robert", latitude=28.5000, longitude=-81.3000, accuracy_m=15, consent=True)
    result = store.update_location(
        "casa-1", "robert", latitude=28.5100, longitude=-81.3100, accuracy_m=18, consent=True, shopping_pending=4
    )

    assert result["alert"]["kind"] == "SHOPPING_AFTER_WORK"
    assert "4 artículos" in result["alert"]["message"]


def test_family_api_requires_member_and_shares_only_with_explicit_consent(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "family-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "local_user")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setenv("ROXY_HOME_FAMILY_PATH", str(tmp_path / "family.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    accounts = HomeAccountStore(tmp_path / "accounts.json")
    owner = accounts.bootstrap(
        "local_user", household_name="Nuestro hogar", username="robert", display_name="Robert", password="owner-password"
    )
    accounts.add_member(owner["id"], username="roxy", display_name="Roxy", password="partner-password")
    roxy_home_service._RATE_STATE.clear()
    roxy_home_service._LOGIN_RATE_STATE.clear()
    client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    assert client.post("/v1/home-account/login", json={"username": "robert", "password": "owner-password"}).status_code == 200

    before = client.get("/v1/home-family")
    refused = client.put(
        "/v1/home-family/location",
        json={"latitude": 28.5383, "longitude": -81.3792, "accuracy_m": 25, "consent": False},
    )
    shared = client.put(
        "/v1/home-family/location",
        json={"latitude": 28.5383, "longitude": -81.3792, "accuracy_m": 25, "consent": True},
    )
    after = client.get("/v1/home-family")

    assert before.status_code == 200 and len(before.json()["members"]) == 2
    assert refused.status_code == 403
    assert shared.status_code == 200
    assert next(row for row in after.json()["members"] if row["is_viewer"])["sharing_enabled"] is True


def test_family_api_syncs_two_household_profiles_and_one_nexo_only_connection(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "family-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "local_user,guest_user")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setenv("ROXY_HOME_FAMILY_PATH", str(tmp_path / "family.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    accounts = HomeAccountStore(tmp_path / "accounts.json")
    owner = accounts.bootstrap(
        "local_user", household_name="Nuestro hogar", username="robert", display_name="Robert", password="owner-password"
    )
    accounts.add_member(owner["id"], username="roxy", display_name="Roxy", password="partner-password")
    accounts.bootstrap(
        "guest_user", household_name="Casa invitada", username="ana", display_name="Ana", password="guest-password"
    )
    roxy_home_service._RATE_STATE.clear()
    roxy_home_service._LOGIN_RATE_STATE.clear()
    owner_client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    partner_client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    guest_client = TestClient(roxy_home_service.app, base_url="https://roxy.test")
    assert owner_client.post(
        "/v1/home-account/login", json={"username": "robert", "password": "owner-password"}
    ).status_code == 200
    assert partner_client.post(
        "/v1/home-account/login", json={"username": "roxy", "password": "partner-password"}
    ).status_code == 200
    assert guest_client.post(
        "/v1/home-account/login", json={"username": "ana", "password": "guest-password"}
    ).status_code == 200

    assert owner_client.put(
        "/v1/home-family/location",
        json={"latitude": 28.5383, "longitude": -81.3792, "accuracy_m": 10, "consent": True},
    ).status_code == 200
    assert partner_client.put(
        "/v1/home-family/location",
        json={"latitude": 28.5000, "longitude": -81.3000, "accuracy_m": 12, "consent": True},
    ).status_code == 200
    invitation = owner_client.post(
        "/v1/home-family/invitations",
        json={"display_name": "Ana", "relationship": "Amiga"},
    )
    assert invitation.status_code == 201
    token = invitation.json()["invitation"]["token"]
    accepted = guest_client.post("/v1/home-family/invitations/redeem", json={"token": token})
    assert accepted.status_code == 200
    assert accepted.json()["access_scope"] == "NEXO_ONLY"
    assert guest_client.put(
        "/v1/home-family/location",
        json={"latitude": 28.5500, "longitude": -81.3500, "accuracy_m": 14, "consent": True},
    ).status_code == 200

    owner_view = owner_client.get("/v1/home-family").json()
    guest_view = guest_client.get("/v1/home-family").json()
    assert owner_view["access_scope"] == "HOUSEHOLD"
    assert {row["display_name"] for row in owner_view["members"]} == {"Robert", "Roxy", "Ana"}
    assert guest_view["access_scope"] == "NEXO_ONLY"
    assert guest_view["can_manage_connections"] is False
    assert {row["display_name"] for row in guest_view["members"]} == {"Robert", "Roxy", "Ana"}
    assert all(row.get("location") for row in guest_view["members"])


def test_family_ui_is_wired_to_real_endpoints():
    html = open("assets/roxy_list.html", encoding="utf-8").read()
    js = open("assets/roxy_list.js", encoding="utf-8").read()

    assert 'id="familyPanel"' in html
    assert 'data-tab-link="family"' in html
    assert "/v1/home-family/location" in js
    assert "familyPlaceForm" in js
    assert "watchPosition" in js
    assert "resumeFamilyLocationIfEnabled" in js
    assert "window.addEventListener('pageshow'" in js
    assert "document.addEventListener('visibilitychange'" in js
    assert "Ubicación activada. Roxy la reanudará automáticamente" in js
    assert "Activar ubicación permanente" in html
    assert 'id="familyInviteForm"' in html
    assert "/v1/home-family/invitations" in js
    assert "acceso solo a Nexo" in js
    assert "/history?limit=500" in js
    assert 'id="familyMap"' in html
    assert "Nuestro Nexo" in html
    assert "Google Maps oficial" in html
    assert "disableDefaultUI:false" in js
    assert "mapTypeId:'roadmap'" in js


def test_home_page_csp_allows_only_google_maps_runtime_origins():
    from tools import roxy_home_service

    response = roxy_home_service.shopping_page()
    policy = response.headers["Content-Security-Policy"]

    assert "script-src 'self'" in policy
    assert "https://maps.googleapis.com" in policy
    assert "https://maps.gstatic.com" in policy
    assert "https://*.googleapis.com" in policy
    assert "https://*.gstatic.com" in policy
    assert "unsafe-eval" not in policy


def test_home_deployment_persists_family_state_and_keeps_maps_key_separate():
    dockerfile = open("Dockerfile.roxy-home", encoding="utf-8").read()
    render = open("render.yaml", encoding="utf-8").read()
    env_example = open(".env.example", encoding="utf-8").read()

    assert "ROXY_HOME_FAMILY_PATH=/var/data/roxy_home/family.json" in dockerfile
    assert "ROXY_HOME_FAMILY_PATH" in render
    assert "/var/data/roxy_home/family.json" in render
    assert "ROXY_HOME_GOOGLE_MAPS_BROWSER_KEY" in render
    assert "ROXY_HOME_GOOGLE_MAPS_BROWSER_KEY=" in env_example
    assert "Never reuse GOOGLE_MAPS_API_KEY" in env_example
