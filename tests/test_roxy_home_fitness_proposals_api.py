"""Authenticated, read-only scheduling proposals using saved preferences."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from roxy_os.fitness import router
from tools import roxy_home_service as service
from test_roxy_home_fitness_api import api, headers, private_cache, PREFIX, MEMBER
from test_roxy_home_fitness_repository import CONSENT, PROFILE
from test_roxy_home_fitness_activity_plan import CONSENT as PLAN_CONSENT, PLAN


BASE = PREFIX + "/me/activity-plan"
URL = BASE + "/proposal"
PAYLOAD = {"expected_version": 0, "start_date": "2026-09-21", "program_ids": ["gentle-strength", "gentle-balance"]}
SCHEDULE_PROFILE = {**PROFILE, "session_minutes": 20, "travel_minutes": 10,
                    "availability": [{"day": day, "windows": [{"start": "09:00", "end": "10:00"}]}
                                     for day in ("mon", "wed", "fri")]}


@pytest.fixture
def proposals_api(api, monkeypatch):
    api.db.tables.extend({"relname": name, "relrowsecurity": True, "relforcerowsecurity": True, "is_owner": False}
                         for name in ("activity_plan_state", "activity_plan_idempotency"))
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(router, "datetime", Clock)
    return api


def profile(api, value=None):
    api.repository.set_consent(MEMBER, CONSENT, expected_version=0, idempotency_key="proposal-pref-consent")
    return api.repository.save_profile(MEMBER, value or SCHEDULE_PROFILE, expected_version=1, idempotency_key="proposal-pref-save")


def plan(api, value=None):
    response = api.client.post(BASE + "/consent", headers=headers(key="proposal-plan-consent"),
                               json={"expected_version": 0, "consent": PLAN_CONSENT})
    assert response.status_code == 200, response.text
    response = api.client.put(BASE, headers=headers(key="proposal-plan-save"),
                              json={"expected_version": 1, "plan": value or PLAN})
    assert response.status_code == 200, response.text
    return response.json()


def persisted(db):
    return deepcopy((db.states, db.requests, db.plan_states, db.plan_requests))


@pytest.mark.parametrize("identity", [None, "member-b"])
def test_proposal_requires_current_member_assertion(proposals_api, identity):
    supplied = headers(member=identity or MEMBER)
    if identity is None:
        supplied.pop("X-Roxy-Fitness-Member")
    response = proposals_api.client.post(URL, headers=supplied, json=PAYLOAD)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "identity_changed"
    private_cache(response)
    assert proposals_api.db.calls == []


@pytest.mark.parametrize("mode", ["legacy", "bearer"])
def test_shared_access_cannot_generate_personal_proposals(proposals_api, mode):
    proposals_api.identity = service.AuthContext(mode, "shared-household", None)
    response = proposals_api.client.post(URL, headers=headers(), json=PAYLOAD)
    assert response.status_code == 403 and response.json()["detail"]["code"] == "personal_login_required"
    private_cache(response)
    assert proposals_api.db.calls == []


def test_unauthenticated_proposal_is_private(proposals_api, monkeypatch):
    monkeypatch.delitem(service.app.dependency_overrides, service._authenticate)
    response = proposals_api.client.post(URL, headers=headers(), json=PAYLOAD)
    assert response.status_code == 401
    private_cache(response)
    assert proposals_api.db.calls == []


@pytest.mark.parametrize("defect", ["foreign_origin", "missing_origin", "missing_request_header"])
def test_even_read_only_proposal_requires_csrf_contract(proposals_api, defect):
    supplied = headers()
    if defect == "foreign_origin":
        supplied["Origin"] = "https://foreign.example"
    else:
        supplied.pop("Origin" if defect == "missing_origin" else "X-Roxy-Fitness-Request")
    response = proposals_api.client.post(URL, headers=supplied, json=PAYLOAD)
    assert response.status_code == 403 and response.json()["detail"]["code"] == "csrf_rejected"
    private_cache(response)
    assert proposals_api.db.calls == []


def test_saved_preferences_produce_reviewable_dates_without_persisting(proposals_api):
    profile(proposals_api)
    before = persisted(proposals_api.db)
    proposals_api.db.calls.clear()
    response = proposals_api.client.post(URL, headers=headers(), json=PAYLOAD)
    assert response.status_code == 200, response.text
    private_cache(response)
    value = response.json()
    assert value["profile_version"] == 2 and value["activity_plan_version"] == 0
    proposal = value["proposal"]
    assert proposal["status"] == "ready"
    assert [(row["date"], row["time"], row["program_id"]) for row in proposal["sessions"]] == [
        ("2026-09-21", "09:00", "gentle-strength"),
        ("2026-09-23", "09:00", "gentle-balance"),
        ("2026-09-25", "09:00", "gentle-strength"),
    ]
    assert proposal["source_duration_minutes"] is None
    assert proposal["allocated_minutes"] == 20 and proposal["travel_minutes"] == 10
    assert proposal["clinical_approval"] is False and proposal["can_activate_training"] is False
    assert persisted(proposals_api.db) == before
    assert not any(sql.startswith(("INSERT", "UPDATE", "DELETE")) for sql, _ in proposals_api.db.calls)
    repeated = proposals_api.client.post(URL, headers=headers(), json=PAYLOAD)
    assert repeated.status_code == 200 and repeated.json() == value
    assert persisted(proposals_api.db) == before


def test_missing_saved_profile_is_actionable_422_without_creating_state(proposals_api):
    response = proposals_api.client.post(URL, headers=headers(), json=PAYLOAD)
    assert response.status_code == 422 and "preferencias" in response.json()["detail"]
    private_cache(response)
    assert not proposals_api.db.states and not proposals_api.db.plan_states
    assert not proposals_api.db.requests and not proposals_api.db.plan_requests


def test_stale_plan_version_never_produces_or_saves_a_proposal(proposals_api):
    profile(proposals_api)
    plan(proposals_api)
    before = persisted(proposals_api.db)
    response = proposals_api.client.post(URL, headers=headers(), json=PAYLOAD)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "version_conflict"
    private_cache(response)
    assert persisted(proposals_api.db) == before


def test_existing_plan_timezone_must_match_saved_preferences(proposals_api):
    profile(proposals_api, {**SCHEDULE_PROFILE, "timezone": "Europe/Madrid"})
    plan(proposals_api)
    before = persisted(proposals_api.db)
    response = proposals_api.client.post(URL, headers=headers(), json={**PAYLOAD, "expected_version": 2})
    assert response.status_code == 422 and "zona horaria" in response.json()["detail"]
    private_cache(response)
    assert persisted(proposals_api.db) == before


def test_proposal_preserves_existing_sessions_and_their_status(proposals_api):
    profile(proposals_api)
    existing = {**PLAN, "sessions": [{**PLAN["sessions"][0], "date": "2026-09-21"}]}
    saved = plan(proposals_api, existing)
    before = persisted(proposals_api.db)
    response = proposals_api.client.post(URL, headers=headers(), json={**PAYLOAD, "expected_version": saved["version"]})
    assert response.status_code == 200, response.text
    private_cache(response)
    proposal = response.json()["proposal"]
    assert "2026-09-21" not in {row["date"] for row in proposal["sessions"]}
    assert {"date": "2026-09-21", "reason_code": "existing_activity",
            "message_es": "Ya tienes una actividad pendiente o realizada ese día; se conserva."} in proposal["excluded_days"]
    assert persisted(proposals_api.db) == before


@pytest.mark.parametrize("change", [
    {"expected_version": True}, {"start_date": "2026-02-30"}, {"start_date": "2026-09-19"},
    {"program_ids": []}, {"program_ids": ["gentle-strength", "gentle-strength"]},
    {"program_ids": ["untrusted-private-id"]}, {"member_id": "member-b"},
])
def test_invalid_proposal_inputs_never_write_private_state(proposals_api, change):
    profile(proposals_api)
    before = persisted(proposals_api.db)
    response = proposals_api.client.post(URL, headers=headers(), json={**PAYLOAD, **change})
    assert response.status_code == 422
    assert "untrusted-private-id" not in response.text
    private_cache(response)
    assert persisted(proposals_api.db) == before


def test_no_fitting_time_returns_empty_proposal_without_inventing_activity(proposals_api):
    profile(proposals_api, {**SCHEDULE_PROFILE, "session_minutes": 90})
    before = persisted(proposals_api.db)
    response = proposals_api.client.post(URL, headers=headers(), json=PAYLOAD)
    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["status"] == "no_slots" and proposal["sessions"] == []
    assert any(day["reason_code"] == "window_too_short" for day in proposal["excluded_days"])
    private_cache(response)
    assert persisted(proposals_api.db) == before


def test_missing_plan_migration_cannot_return_a_successful_proposal(api):
    profile(api)
    response = api.client.post(URL, headers=headers(), json=PAYLOAD)
    assert response.status_code == 503 and response.json()["detail"]["code"] == "private_storage_unavailable"
    private_cache(response)
