"""Private API boundaries using synthetic data; no live PostgreSQL verification."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from roxy_os.fitness import catalog, router
from roxy_os.fitness.repository import PostgresFitnessRepository
from roxy_os.home_demo import trial_access_mode
from tools import roxy_home_service as service
from test_roxy_home_fitness_repository import CONSENT, DSN, PROFILE, SyntheticDB


PREFIX = "/api/fitness/v1"
ORIGIN = "https://fitness.test"
MEMBER = "member-a"
PRIVATE_ROUTES = [
    ("GET", "/me/profile", None),
    ("GET", "/me/data", None),
    ("PATCH", "/me/profile", {"expected_version": 0, "profile": PROFILE}),
    ("POST", "/me/consents", {"expected_version": 0, "consent": CONSENT}),
    ("DELETE", "/me/data", {"expected_version": 0, "confirm_delete": True}),
    ("POST", "/plans/preview", {}),
]


def headers(member=MEMBER, key="request-0001"):
    return {"Origin": ORIGIN, "X-Roxy-Fitness-Member": member,
            "X-Roxy-Fitness-Request": "1", "Idempotency-Key": key,
            "Content-Type": "application/json"}


def private_cache(response):
    assert response.headers["cache-control"] == "private, no-store"
    assert {item.strip() for item in response.headers["vary"].split(",")} == {"Cookie", "Authorization"}


@pytest.fixture
def api(monkeypatch):
    db = SyntheticDB()
    repository = PostgresFitnessRepository(DSN, connection_factory=db.connect)
    state = SimpleNamespace(identity=service.AuthContext("member", "shared-household", MEMBER),
                            repository=repository, db=db)
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-home-api-key")
    monkeypatch.setattr(router, "repository", lambda: repository)
    monkeypatch.setattr(service, "_rate_limit", lambda request: None)
    monkeypatch.setattr(service, "_account_store", lambda: pytest.fail("Unexpected account-store access"))
    monkeypatch.setitem(service.app.dependency_overrides, service._authenticate, lambda: state.identity)
    with TestClient(service.app, base_url=ORIGIN) as client:
        state.client = client
        yield state


def grant(api, *, member=MEMBER):
    response = api.client.post(PREFIX + "/me/consents", headers=headers(member),
                               json={"expected_version": 0, "consent": CONSENT})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("method,path,payload", PRIVATE_ROUTES)
@pytest.mark.parametrize("mode", ["legacy", "bearer"])
def test_shared_access_cannot_read_or_write_personal_preferences(api, monkeypatch, method, path, payload, mode):
    monkeypatch.delitem(service.app.dependency_overrides, service._authenticate)
    request_headers = headers()
    if mode == "legacy":
        api.client.cookies.set(service.SESSION_COOKIE, service._session_cookie("shared-household"))
    else:
        request_headers["Authorization"] = "Bearer synthetic-home-api-key"
    response = api.client.request(method, PREFIX + path, headers=request_headers, json=payload)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "personal_login_required"
    private_cache(response)
    assert api.db.calls == []


@pytest.mark.parametrize("method,path,payload", PRIVATE_ROUTES)
@pytest.mark.parametrize("asserted_member", [None, "member-b", "shared-household"])
def test_identity_assertion_never_selects_another_member(api, method, path, payload, asserted_member):
    request_headers = headers()
    if asserted_member is None:
        request_headers.pop("X-Roxy-Fitness-Member")
    else:
        request_headers["X-Roxy-Fitness-Member"] = asserted_member
    response = api.client.request(method, PREFIX + path, headers=request_headers, json=payload)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "identity_changed"
    private_cache(response)
    assert api.db.calls == []


def test_member_is_derived_from_login_even_with_a_shared_household(api):
    grant(api)
    saved = api.client.patch(PREFIX + "/me/profile", headers=headers(key="save-a-0001"),
                             json={"expected_version": 1, "profile": PROFILE})
    assert saved.status_code == 200
    api.identity = service.AuthContext("member", "shared-household", "member-b")
    other = api.client.get(PREFIX + "/me/profile?member_id=member-a", headers=headers("member-b"))
    assert other.status_code == 200 and other.json()["profile"] is None
    exported = api.client.get(PREFIX + "/me/data?member_id=member-a", headers=headers("member-b"))
    assert exported.status_code == 200 and exported.json()["data"]["profile"] is None
    assert set(api.db.states) == {MEMBER}
    assert "shared-household" not in repr(api.db.calls)


@pytest.mark.parametrize("path", ["/status", "/me/profile", "/me/data", "/exercises", "/exercises/wger-91", "/programs", "/programs/gentle-strength"])
def test_unauthenticated_response_is_not_cached(api, monkeypatch, path):
    monkeypatch.delitem(service.app.dependency_overrides, service._authenticate)
    response = api.client.get(PREFIX + path)
    assert response.status_code == 401
    private_cache(response)
    assert api.db.calls == []


@pytest.mark.parametrize("mode", ["member", "legacy", "bearer"])
def test_status_reports_identity_and_pending_capabilities_without_private_reads(api, mode):
    api.identity = service.AuthContext(mode, "shared-household", MEMBER if mode == "member" else None)
    response = api.client.get(PREFIX + "/status")
    assert response.status_code == 200
    value = response.json()
    assert value["personal_login"] is (mode == "member")
    assert value["member_id"] == (MEMBER if mode == "member" else None)
    assert value["can_activate_plans"] is False
    assert value["clinical_review"] == "pending"
    assert value["storage"]["verified"] is False
    assert not any(value[key] for key in ("bookings_enabled", "wearables_enabled", "supplement_recommendations_enabled"))
    private_cache(response)
    assert api.db.calls == []
    assert "never-real" not in response.text


@pytest.mark.parametrize("mode", ["member", "legacy", "bearer"])
def test_source_programs_do_not_require_or_access_personal_storage(api, monkeypatch, mode):
    api.identity = service.AuthContext(mode, "shared-household", MEMBER if mode == "member" else None)
    monkeypatch.setattr(router, "repository", lambda: pytest.fail("Source guide accessed private storage"))
    response = api.client.get(PREFIX + "/programs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == len(data["programs"]) == 3
    assert sum(row["exercise_count"] for row in data["programs"]) == 16
    for field in ("active_training", "can_activate_plans", "clinical_approval", "can_persist"):
        assert data[field] is False
    for row in data["programs"]:
        detail = api.client.get(PREFIX + "/programs/" + row["id"])
        assert detail.status_code == 200
        program = detail.json()["program"]
        assert len(program["exercises"]) == row["exercise_count"]
        assert program["duration_seconds"] is None
        assert all(exercise["instructions_en"] and exercise["instructions_es"] for exercise in program["exercises"])
        private_cache(detail)
    private_cache(response)
    assert api.db.calls == []


def test_unknown_or_invalid_program_catalog_is_never_a_success(api, monkeypatch):
    missing = api.client.get(PREFIX + "/programs/not-a-plan")
    assert missing.status_code == 404
    private_cache(missing)
    def fail():
        raise router.ProgramCatalogUnavailable()
    monkeypatch.setattr(router, "program_catalog", fail)
    failure = api.client.get(PREFIX + "/programs")
    assert failure.status_code == 503
    assert failure.json()["detail"]["code"] == "program_catalog_unavailable"
    private_cache(failure)
    assert api.db.calls == []


@pytest.mark.parametrize("path", ["/programs", "/programs/gentle-strength", "/programs/gentle-balance", "/programs/gentle-flexibility"])
def test_trial_only_allows_reading_source_programs(path):
    assert trial_access_mode("GET", PREFIX + path) == "local"
    assert trial_access_mode("POST", PREFIX + path) != "local"
    assert trial_access_mode("GET", PREFIX + path + "/activate") != "local"


def test_catalog_api_returns_fixed_originals_and_attributed_images_without_private_storage(api, monkeypatch):
    monkeypatch.setattr(router, "repository", lambda: pytest.fail("Educational catalogue accessed private storage"))
    original = json.loads(catalog.CATALOG_PATH.read_text(encoding="utf-8"))
    expected = {entry["id"]: entry for entry in original["entries"]}
    response = api.client.get(PREFIX + "/exercises")  # No consent, profile or member assertion required.
    assert response.status_code == 200
    value = response.json()
    assert value["count"] == len(value["entries"]) == 21
    assert {entry["id"] for entry in value["entries"]} == set(expected)
    assert sum(len(entry["images"]) for entry in value["entries"]) == 44
    assert value["status"] == "education_only_professional_review_pending"
    assert value["review_status"] == "pending_professional_review"
    assert value["clinical_approval"] is False and value["can_activate_training"] is False
    assert "no es un plan personal" in value["notice"]
    for entry in value["entries"]:
        source = expected[entry["id"]]
        assert entry["instructions"] == source["instructions"]
        assert entry["language"] == source["language"]
        for field in ("authors", "license", "license_url", "source_license_id", "changes"):
            assert entry["attribution"][field] == source["attribution"][field]
        assert entry["source_url"] == source["source_url"]
        assert entry["instructions_sha256"] == source["instructions_sha256"]
        assert entry["clinical_approval"] is False and entry["can_activate_training"] is False
        assert entry["review_status"] == "pending_professional_review"
        source_images = {image["source_id"]: image for image in source["images"]}
        assert {image["source_id"] for image in entry["images"]} == set(source_images)
        for image in entry["images"]:
            for field in ("url", "source_url", "source_exercise_id", "kind", "author", "license", "license_url",
                          "sha256", "is_ai_generated", "changes"):
                assert image[field] == source_images[image["source_id"]][field]
        detail = api.client.get(PREFIX + "/exercises/" + entry["id"])
        assert detail.status_code == 200 and detail.json() == entry
        private_cache(detail)
    private_cache(response)
    assert api.db.calls == [] and api.db.states == {} and api.db.requests == {}


@pytest.mark.parametrize("mode", ["legacy", "bearer"])
@pytest.mark.parametrize("path", ["/exercises", "/exercises/wger-91"])
def test_shared_authenticated_access_can_read_education_only(api, monkeypatch, mode, path):
    monkeypatch.delitem(service.app.dependency_overrides, service._authenticate)
    monkeypatch.setattr(router, "repository", lambda: pytest.fail("Shared education accessed private storage"))
    request_headers = {}
    if mode == "legacy":
        api.client.cookies.set(service.SESSION_COOKIE, service._session_cookie("shared-household"))
    else:
        request_headers["Authorization"] = "Bearer synthetic-home-api-key"
    response = api.client.get(PREFIX + path, headers=request_headers)
    assert response.status_code == 200
    assert response.json()["clinical_approval"] is False
    assert response.json()["can_activate_training"] is False
    private_cache(response)
    personal = api.client.get(PREFIX + "/me/profile", headers=request_headers)
    assert personal.status_code == 403
    assert personal.json()["detail"]["code"] == "personal_login_required"
    private_cache(personal)
    assert api.db.calls == []


@pytest.mark.parametrize("path", ["/exercises", "/exercises/wger-91"])
def test_catalogue_request_cannot_claim_clinical_approval_or_activate_training(api, monkeypatch, path):
    monkeypatch.setattr(router, "repository", lambda: pytest.fail("Catalogue request accessed private storage"))
    baseline = api.client.get(PREFIX + path)
    response = api.client.get(PREFIX + path, params={"member_id": "member-b", "medical_clearance": "true",
                                                   "clinical_approval": "true", "can_activate_training": "true"},
                              headers={"X-Roxy-Fitness-Member": "member-b"})
    assert response.status_code == 200 and response.json() == baseline.json()
    private_cache(response)
    for method in ("POST", "PATCH", "PUT", "DELETE"):
        denied = api.client.request(method, PREFIX + path, headers=headers(), json={"clinical_approval": True})
        assert denied.status_code == 405
        private_cache(denied)
    assert api.client.post(PREFIX + "/plans/activate", headers=headers(), json={"exercise_id": "wger-91"}).status_code == 404
    assert api.db.calls == [] and api.db.states == {} and api.db.requests == {}


@pytest.mark.parametrize("exercise_id", ["wger-203", "wger-99999999", "wger-0", "91", "wger-not-a-source"])
def test_unknown_or_excluded_catalogue_entry_returns_private_404_without_storage(api, monkeypatch, exercise_id):
    monkeypatch.setattr(router, "repository", lambda: pytest.fail("Unknown catalogue ID accessed private storage"))
    response = api.client.get(PREFIX + "/exercises/" + exercise_id)
    assert response.status_code == 404
    assert response.json() == {"detail": "No existe esa ficha original."}
    private_cache(response)
    assert api.db.calls == []


def test_missing_catalogue_is_explicit_without_invented_entries_or_training(api, monkeypatch, tmp_path):
    monkeypatch.setattr(catalog, "CATALOG_PATH", tmp_path / "missing-catalogue.json")
    monkeypatch.setattr(router, "repository", lambda: pytest.fail("Missing catalogue accessed private storage"))
    response = api.client.get(PREFIX + "/exercises")
    assert response.status_code == 200
    assert response.json()["status"] == "catalogue_unavailable"
    assert response.json()["count"] == 0 and response.json()["entries"] == []
    assert response.json()["clinical_approval"] is response.json()["can_activate_training"] is False
    private_cache(response)
    missing = api.client.get(PREFIX + "/exercises/wger-91")
    assert missing.status_code == 404
    private_cache(missing)
    assert api.db.calls == []


@pytest.mark.parametrize("changed,value,status", [
    ("Origin", None, 403), ("Origin", "https://other.test", 403),
    ("Origin", "null", 403), ("Origin", ORIGIN + "/", 403),
    ("X-Roxy-Fitness-Request", None, 403), ("X-Roxy-Fitness-Request", "true", 403),
    ("Content-Type", "text/plain", 415),
    ("Idempotency-Key", None, 422), ("Idempotency-Key", "short", 422),
    ("Idempotency-Key", "has spaces", 422), ("Idempotency-Key", "a" * 129, 422),
])
@pytest.mark.parametrize("method,path,payload", [route for route in PRIVATE_ROUTES if route[0] != "GET"])
def test_mutations_require_same_origin_explicit_json_and_valid_request_key(api, changed, value, status, method, path, payload):
    request_headers = headers()
    if value is None:
        request_headers.pop(changed)
    else:
        request_headers[changed] = value
    response = api.client.request(method, PREFIX + path, headers=request_headers, json=payload)
    assert response.status_code == status, response.text
    private_cache(response)
    assert api.db.calls == []


@pytest.mark.parametrize("method,path,payload", [route for route in PRIVATE_ROUTES if route[0] not in {"GET"} and route[1] != "/plans/preview"])
@pytest.mark.parametrize("field", ["member_id", "storage_user_id", "household_id"])
def test_client_cannot_submit_a_private_data_owner(api, method, path, payload, field):
    response = api.client.request(method, PREFIX + path, headers=headers(),
                                  json={**payload, field: "member-b"})
    assert response.status_code == 422
    private_cache(response)
    assert api.db.calls == []


def test_profile_nested_identity_and_unknown_medical_fields_are_rejected(api):
    for field in ("member_id", "medical_clearance", "weight_kg", "diagnosis"):
        response = api.client.patch(PREFIX + "/me/profile", headers=headers(),
                                    json={"expected_version": 0, "profile": {**PROFILE, field: "untrusted"}})
        assert response.status_code == 422
        private_cache(response)
    assert api.db.calls == []


def test_consent_version_and_write_version_are_validated_before_storage(api):
    for version in (-1, True, "0", 2**53):
        response = api.client.post(PREFIX + "/me/consents", headers=headers(),
                                   json={"expected_version": version, "consent": CONSENT})
        assert response.status_code == 422
        private_cache(response)
    for consent in ({**CONSENT, "text_version": "old"}, {**CONSENT, "granted": "true"}):
        response = api.client.post(PREFIX + "/me/consents", headers=headers(),
                                   json={"expected_version": 0, "consent": consent})
        assert response.status_code == 422
    assert api.db.calls == []


def test_consent_is_required_and_retries_do_not_duplicate_changes(api):
    response = api.client.patch(PREFIX + "/me/profile", headers=headers(),
                                json={"expected_version": 0, "profile": PROFILE})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "consent_required"
    private_cache(response)
    assert api.db.states == {}
    assert grant(api)["version"] == 1
    replay = api.client.post(PREFIX + "/me/consents", headers=headers(),
                             json={"expected_version": 0, "consent": CONSENT})
    assert replay.status_code == 200 and replay.json()["idempotent_replay"] is True
    assert replay.json()["version"] == 1
    conflict = api.client.post(PREFIX + "/me/consents", headers=headers(),
                               json={"expected_version": 1, "consent": {**CONSENT, "granted": False}})
    assert conflict.status_code == 409
    stale = api.client.patch(PREFIX + "/me/profile", headers=headers(key="profile-0001"),
                             json={"expected_version": 0, "profile": PROFILE})
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "version_conflict"
    assert api.db.states[MEMBER]["version"] == 1
    assert api.db.states[MEMBER]["profile"] is None


def test_preview_cannot_activate_a_plan_or_mutate_preferences(api):
    grant(api)
    full_profile = {**PROFILE, "session_minutes": 30, "locations": ["home"],
                    "availability": [{"day": "mon", "windows": [{"start": "09:00", "end": "10:00"}]}]}
    saved = api.client.patch(PREFIX + "/me/profile", headers=headers(key="profile-0001"),
                             json={"expected_version": 1, "profile": full_profile})
    assert saved.status_code == 200
    before = deepcopy((api.db.states, api.db.requests))
    response = api.client.post(PREFIX + "/plans/preview", headers=headers(key="preview-0001"),
                               json={"can_activate": True, "medical_clearance": True, "member_id": "member-b"})
    assert response.status_code == 200
    value = response.json()
    assert value["status"] == "needs_professional_review"
    assert value["can_activate"] is False and value["medical_clearance"] is False
    assert value["sessions"] == value["prescriptions"] == []
    assert value["clinical_rule_version"] is None
    assert (api.db.states, api.db.requests) == before
    assert api.client.post(PREFIX + "/plans/activate", headers=headers(), json={}).status_code == 404
    private_cache(response)


def test_export_delete_and_replay_do_not_restore_erased_preferences(api):
    grant(api)
    api.client.patch(PREFIX + "/me/profile", headers=headers(key="profile-0001"),
                     json={"expected_version": 1, "profile": PROFILE})
    exported = api.client.get(PREFIX + "/me/data", headers=headers())
    assert exported.status_code == 200
    assert exported.json()["scope"] == "authenticated_member_only"
    assert exported.json()["data"]["profile"]["primary_goal"] == PROFILE["primary_goal"]
    private_cache(exported)
    for confirm in (False, 1, "true"):
        denied = api.client.request("DELETE", PREFIX + "/me/data", headers=headers(key="delete-0001"),
                                    json={"expected_version": 2, "confirm_delete": confirm})
        assert denied.status_code == 422
    deleted = api.client.request("DELETE", PREFIX + "/me/data", headers=headers(key="delete-0001"),
                                 json={"expected_version": 2, "confirm_delete": True})
    assert deleted.status_code == 200 and deleted.json()["version"] == 3
    assert deleted.json()["profile"] is None and deleted.json()["consent"] is None
    retry = api.client.request("DELETE", PREFIX + "/me/data", headers=headers(key="delete-0001"),
                               json={"expected_version": 2, "confirm_delete": True})
    assert retry.status_code == 200 and retry.json()["idempotent_replay"] is True
    old_save = api.client.patch(PREFIX + "/me/profile", headers=headers(key="profile-0001"),
                                json={"expected_version": 1, "profile": PROFILE})
    assert old_save.status_code == 409
    assert api.db.states[MEMBER]["profile"] is None


def test_missing_postgres_is_explicit_and_returns_no_secret_or_fake_success(api, monkeypatch):
    monkeypatch.delenv("ROXY_HOME_FITNESS_DATABASE_URL", raising=False)
    monkeypatch.setattr(router, "repository", PostgresFitnessRepository.from_env)
    status = api.client.get(PREFIX + "/status")
    assert status.status_code == 200
    assert status.json()["storage"]["status"] == "storage_not_configured"
    assert status.json()["storage"]["personal_data_fallback"] is False
    for method, path, payload in PRIVATE_ROUTES:
        response = api.client.request(method, PREFIX + path, headers=headers(), json=payload)
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "private_storage_unavailable"
        assert "postgresql://" not in response.text and "never-real" not in response.text
        private_cache(response)
    assert api.db.calls == []


def test_connection_error_is_sanitized(api, monkeypatch):
    def failed_connection(_dsn):
        raise RuntimeError("postgresql://synthetic:never-real@example.invalid private SQL member-a")
    repo = PostgresFitnessRepository(DSN, connection_factory=failed_connection)
    monkeypatch.setattr(router, "repository", lambda: repo)
    response = api.client.get(PREFIX + "/me/profile", headers=headers())
    assert response.status_code == 503
    assert "never-real" not in response.text and "private SQL" not in response.text
    private_cache(response)


def test_demo_allowlist_contains_only_the_exact_preference_routes():
    allowed = {(method, PREFIX + path) for method, path, _ in PRIVATE_ROUTES}
    allowed.add(("GET", PREFIX + "/status"))
    for method, path in allowed:
        assert trial_access_mode(method, path) == "local"
        assert trial_access_mode(method, path + "/anything") == "unavailable"
        for other_method in {"GET", "POST", "PATCH", "DELETE", "PUT"} - {method}:
            if (other_method, path) not in allowed:
                assert trial_access_mode(other_method, path) == "unavailable"
    for path in ("/plans/activate", "/bookings", "/wearables", "/supplements", "/members/member-b"):
        assert trial_access_mode("POST", PREFIX + path) == "unavailable"


def test_expired_demo_can_export_and_delete_but_not_save_or_preview(api, monkeypatch):
    grant(api)
    monkeypatch.delitem(service.app.dependency_overrides, service._authenticate)
    expired = service.AuthContext("member", "shared-household", MEMBER, {"status": "EXPIRED"})
    monkeypatch.setattr(service, "_cookie_auth", lambda value: expired)
    assert api.client.get(PREFIX + "/me/data", headers=headers()).status_code == 200
    before = deepcopy(api.db.states)
    for method, path, payload in PRIVATE_ROUTES:
        if method in {"GET", "DELETE"}:
            continue
        response = api.client.request(method, PREFIX + path, headers=headers(), json=payload)
        assert response.status_code == 403
        private_cache(response)
    assert api.db.states == before
    deleted = api.client.request("DELETE", PREFIX + "/me/data", headers=headers(key="delete-0001"),
                                 json={"expected_version": 1, "confirm_delete": True})
    assert deleted.status_code == 200
    assert deleted.json()["consent"] is None
    assert deleted.json()["profile"] is None
