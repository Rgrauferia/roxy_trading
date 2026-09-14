"""End-to-end HTTP contract against synthetic member-isolated PostgreSQL double."""
import pytest
from test_roxy_home_fitness_api import api, headers, private_cache, PREFIX
from test_roxy_home_fitness_activity_plan import CONSENT, PLAN, SESSION_ID

BASE = PREFIX + "/me/activity-plan"


@pytest.fixture
def enabled(api):
    api.db.tables.extend({"relname": name, "relrowsecurity": True, "relforcerowsecurity": True, "is_owner": False} for name in ("activity_plan_state", "activity_plan_idempotency"))
    return api


def consent(api):
    response = api.client.post(BASE + "/consent", headers=headers(key="plan-consent-0001"), json={"expected_version": 0, "consent": CONSENT})
    assert response.status_code == 200, response.text


def plan(api):
    response = api.client.put(BASE, headers=headers(key="save-plan-0001"), json={"expected_version": 1, "plan": PLAN})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("method,path,payload", [
    ("GET", BASE, None), ("GET", BASE + "/data", None),
    ("PUT", BASE, {"expected_version": 0, "plan": PLAN}),
    ("POST", BASE + "/consent", {"expected_version": 0, "consent": CONSENT}),
    ("PATCH", BASE + "/sessions/" + SESSION_ID, {"expected_version": 0, "status": "completed"}),
    ("DELETE", BASE + "/data", {"expected_version": 0, "confirm_delete": True}),
])
def test_identity_assertion_applies_to_every_private_plan_endpoint(enabled, method, path, payload):
    response = enabled.client.request(method, path, headers=headers(member="another-member"), json=payload)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "identity_changed"
    private_cache(response)
    assert not enabled.db.plan_states


@pytest.mark.parametrize("method,path,payload", [
    ("PUT", BASE, {"expected_version": 0, "plan": PLAN}),
    ("POST", BASE + "/consent", {"expected_version": 0, "consent": CONSENT}),
    ("PATCH", BASE + "/sessions/" + SESSION_ID, {"expected_version": 0, "status": "completed"}),
    ("DELETE", BASE + "/data", {"expected_version": 0, "confirm_delete": True}),
])
def test_mutations_require_same_origin(enabled, method, path, payload):
    supplied = headers(); supplied["Origin"] = "https://foreign.example"
    response = enabled.client.request(method, path, headers=supplied, json=payload)
    assert response.status_code == 403
    assert not enabled.db.plan_states


def test_full_plan_consent_calendar_progress_export_delete_contract(enabled):
    initial = enabled.client.get(BASE, headers=headers())
    assert initial.status_code == 200 and initial.json()["plan"] is None
    private_cache(initial)
    consent(enabled)
    saved = plan(enabled)
    assert saved["progress"]["planned"] == 1 and saved["plan"]["sessions"][0]["starts_at"]
    done = enabled.client.patch(BASE + "/sessions/" + SESSION_ID, headers=headers(key="mark-done-0001"), json={"expected_version": 2, "status": "completed"})
    assert done.status_code == 200 and done.json()["progress"]["completed"] == 1
    own = enabled.client.get(BASE + "/data", headers=headers()).json()
    assert own["data"]["plan"]["sessions"][0]["status"] == "completed"
    full = enabled.client.get(PREFIX + "/me/data", headers=headers()).json()
    assert full["activity_plan"]["plan"]["sessions"][0]["status"] == "completed"
    deleted = enabled.client.request("DELETE", PREFIX + "/me/data", headers=headers(key="global-delete-0001"), json={"expected_version": 0, "confirm_delete": True})
    assert deleted.status_code == 200
    assert enabled.client.get(BASE, headers=headers()).json()["plan"] is None


def test_missing_migration_is_explicit_503(api):
    response = api.client.get(BASE, headers=headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "private_storage_unavailable"


def test_invalid_session_and_dst_never_create_activity(enabled):
    consent(enabled)
    response = enabled.client.patch(BASE + "/sessions/not-a-uuid", headers=headers(), json={"expected_version": 1, "status": "completed"})
    assert response.status_code == 422
    ambiguous = {**PLAN, "sessions": [{**PLAN["sessions"][0], "date": "2026-11-01", "time": "01:30"}]}
    response = enabled.client.put(BASE, headers=headers(), json={"expected_version": 1, "plan": ambiguous})
    assert response.status_code == 422
    assert enabled.db.plan_states["member-a"]["plan"] is None
