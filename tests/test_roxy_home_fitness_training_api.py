"""HTTP boundaries for editorial sessions and private, read-only date proposals."""
from copy import deepcopy

import pytest

from roxy_os.fitness import router, training_selection
from roxy_os.fitness.training_content import TrainingContentError, training_catalog
from tools import roxy_home_service as service
from test_roxy_home_fitness_api import api, grant, headers, private_cache, PREFIX
from test_roxy_home_fitness_activity_plan import CONSENT as PLAN_CONSENT
from test_roxy_home_fitness_training_selection import NOW, PROGRAM, profile, confirmed

PREVIEW = PREFIX + "/me/training/preview"
CATALOG = PREFIX + "/training/programs"
PLAN = PREFIX + "/me/activity-plan"


def payload(**changes):
    return {"program_id": PROGRAM, "confirmed_requirements": confirmed(), "start_date": "2026-09-14", **changes}


@pytest.fixture
def enabled(api, monkeypatch):
    api.db.tables.extend({"relname": name, "relrowsecurity": True, "relforcerowsecurity": True, "is_owner": False} for name in ("activity_plan_state", "activity_plan_idempotency"))
    real_preview = training_selection.preview_training
    monkeypatch.setattr(training_selection, "preview_training", lambda *args, **kwargs: real_preview(*args, **kwargs, now=NOW))
    return api


def save_profile(api, value=None):
    grant(api)
    response = api.client.patch(PREFIX + "/me/profile", headers=headers(key="training-profile-213"), json={"expected_version": 1, "profile": value or profile()})
    assert response.status_code == 200, response.text
    return response.json()


def plan_consent(api):
    response = api.client.post(PLAN + "/consent", headers=headers(key="training-plan-consent-213"), json={"expected_version": 0, "consent": PLAN_CONSENT})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("mode", ["member", "legacy", "bearer"])
def test_catalog_and_details_read_without_private_storage_or_approval_claims(api, monkeypatch, mode):
    api.identity = service.AuthContext(mode, "shared-household", "member-a" if mode == "member" else None)
    monkeypatch.setattr(router, "repository", lambda: pytest.fail("Public routine read accessed personal storage"))
    response = api.client.get(CATALOG)
    assert response.status_code == 200
    private_cache(response)
    result = response.json()
    assert result["total"] == 6 and result["clinical_approval"] is False
    for row in result["programs"]:
        detail = api.client.get(CATALOG + "/" + row["id"], params={"clinical_approval": "true", "member_id": "member-b"})
        assert detail.status_code == 200
        private_cache(detail)
        assert detail.json()["id"] == row["id"]
        assert detail.json()["clinical_approval"] is False
        assert detail.json()["exercises"]
        assert all(e["media"] is None for e in detail.json()["exercises"])
    assert api.db.calls == []


@pytest.mark.parametrize("path", [CATALOG, CATALOG + "/" + PROGRAM])
def test_routine_catalog_is_still_authenticated(api, monkeypatch, path):
    monkeypatch.delitem(service.app.dependency_overrides, service._authenticate)
    response = api.client.get(path)
    assert response.status_code == 401
    private_cache(response)
    assert api.db.calls == []


def test_unknown_or_unreviewed_content_returns_clear_non_success(api, monkeypatch):
    unknown = api.client.get(CATALOG + "/not-a-routine")
    assert unknown.status_code == 404
    private_cache(unknown)
    def fail(*args):
        raise TrainingContentError("Synthetic audit failure")
    monkeypatch.setattr(router, "training_catalog", fail)
    monkeypatch.setattr(router, "training_detail", fail)
    for path in (CATALOG, CATALOG + "/" + PROGRAM):
        response = api.client.get(path)
        assert response.status_code == 503
        private_cache(response)
        assert "Synthetic" not in response.text
    assert api.db.calls == []


@pytest.mark.parametrize("mode", ["legacy", "bearer"])
def test_shared_identity_cannot_generate_personal_proposal(enabled, mode):
    enabled.identity = service.AuthContext(mode, "shared-household", None)
    response = enabled.client.post(PREVIEW, headers=headers(), json=payload())
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "personal_login_required"
    private_cache(response)
    assert enabled.db.calls == []


@pytest.mark.parametrize("asserted", [None, "member-b", "shared-household"])
def test_proposal_member_header_only_asserts_the_active_member(enabled, asserted):
    h = headers()
    if asserted is None:
        h.pop("X-Roxy-Fitness-Member")
    else:
        h["X-Roxy-Fitness-Member"] = asserted
    response = enabled.client.post(PREVIEW, headers=h, json=payload())
    assert response.status_code == 409
    private_cache(response)
    assert enabled.db.calls == []


@pytest.mark.parametrize("missing", ["Origin", "X-Roxy-Fitness-Request", "Idempotency-Key"])
def test_proposal_requires_explicit_same_origin_request(enabled, missing):
    h = headers(); h.pop(missing)
    response = enabled.client.post(PREVIEW, headers=h, json=payload())
    assert response.status_code == (422 if missing == "Idempotency-Key" else 403)
    private_cache(response)
    assert enabled.db.calls == []


def test_cross_origin_and_non_json_proposals_never_read_private_data(enabled):
    h = headers(); h["Origin"] = "https://foreign.example"
    response = enabled.client.post(PREVIEW, headers=h, json=payload())
    assert response.status_code == 403
    h = headers(); h["Content-Type"] = "text/plain"
    response = enabled.client.post(PREVIEW, headers=h, content="{}")
    assert response.status_code == 415
    assert enabled.db.calls == []


def test_missing_profile_and_missing_migration_are_explicit(enabled, api):
    response = enabled.client.post(PREVIEW, headers=headers(), json=payload())
    assert response.status_code == 422
    assert "preferencias" in response.text
    private_cache(response)
    enabled.db.tables[:] = [row for row in enabled.db.tables if not row["relname"].startswith("activity_plan")]
    response = enabled.client.post(PREVIEW, headers=headers(), json=payload())
    assert response.status_code == 503
    private_cache(response)


def test_preview_only_reads_and_returns_versions_for_later_confirmation(enabled):
    saved = save_profile(enabled)
    before = deepcopy((enabled.db.states, enabled.db.requests, enabled.db.plan_states, enabled.db.plan_requests))
    response = enabled.client.post(PREVIEW, headers=headers(key="training-preview-213"), json=payload())
    assert response.status_code == 200, response.text
    private_cache(response)
    result = response.json()
    assert result["profile_version"] == saved["version"] == 2
    assert result["activity_plan_version"] == 0
    assert result["proposal"]["status"] == "ready"
    assert len(result["proposal"]["sessions"]) == 4
    assert "member-b" not in response.text
    assert (enabled.db.states, enabled.db.requests, enabled.db.plan_states, enabled.db.plan_requests) == before


@pytest.mark.parametrize("extra", [{"member_id": "member-b"}, {"clinical_approval": True}, {"weight_kg": 65}, {"dose": {"sets": 99}}])
def test_browser_cannot_supply_health_prescription_or_another_member(enabled, extra):
    response = enabled.client.post(PREVIEW, headers=headers(), json={**payload(), **extra})
    assert response.status_code == 422
    private_cache(response)
    assert enabled.db.calls == []


@pytest.mark.parametrize("changes", [{"age_band": None}, {"session_minutes": 20}, {"experience": "prefer_not_to_say"}, {"locations": ["outdoors"]}])
def test_incompatible_saved_profile_never_yields_ready(enabled, changes):
    save_profile(enabled, profile(**changes))
    response = enabled.client.post(PREVIEW, headers=headers(), json=payload())
    assert response.status_code == 422
    private_cache(response)
    assert enabled.db.plan_states == {}


@pytest.mark.parametrize("changes", [{"program_id": "unknown"}, {"confirmed_requirements": {"equipment": [], "capabilities": []}}, {"start_date": ""}, {"start_date": "2026-09-13"}])
def test_invalid_proposal_content_cannot_create_an_agenda(enabled, changes):
    save_profile(enabled)
    response = enabled.client.post(PREVIEW, headers=headers(), json=payload(**changes))
    assert response.status_code == 422
    private_cache(response)
    assert enabled.db.plan_states == {}


def test_save_requires_current_profile_then_replay_does_not_duplicate_rows(enabled):
    save_profile(enabled)
    proposal = enabled.client.post(PREVIEW, headers=headers(key="proposal-save-213"), json=payload()).json()
    consent = plan_consent(enabled)
    body = {"expected_version": consent["version"], "expected_profile_version": 1,
            "plan": {"title": "Rutinas sintéticas 213", "timezone": "America/New_York", "sessions": proposal["proposal"]["sessions"]}}
    stale = enabled.client.put(PLAN, headers=headers(key="save-stale-training-213"), json=body)
    assert stale.status_code == 409, stale.text
    assert enabled.db.plan_states["member-a"]["plan"] is None
    body["expected_profile_version"] = proposal["profile_version"]
    h = headers(key="save-training-213")
    saved = enabled.client.put(PLAN, headers=h, json=body)
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["plan"]["sessions"]) == 4
    assert saved.json()["progress"]["completed"] == 0
    replay = enabled.client.put(PLAN, headers=h, json=body)
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["plan"] == saved.json()["plan"]
    private_cache(replay)


def test_another_member_cannot_see_a_previous_members_profile_in_preview(enabled):
    save_profile(enabled)
    enabled.identity = service.AuthContext("member", "shared-household", "member-b")
    response = enabled.client.post(PREVIEW + "?member_id=member-a", headers=headers(member="member-b"), json=payload())
    assert response.status_code == 422
    assert "preferencias" in response.text
    private_cache(response)
    assert "member-b" not in enabled.db.states


def test_dst_ambiguous_end_of_manual_save_is_422_not_503(enabled):
    p = profile(session_minutes=60, travel_minutes=0, availability=[{"day": "sun", "windows": [{"start": "00:00", "end": "04:00"}]}])
    save_profile(enabled, p)
    plan_consent(enabled)
    row = training_selection.preview_training(p, PROGRAM, confirmed(), start_date="2026-11-01")["sessions"][0]
    row["time"] = "00:30"
    response = enabled.client.put(PLAN, headers=headers(key="dst-end-training-213"), json={"expected_version": 1, "expected_profile_version": 2,
        "plan": {"title": "Prueba DST", "timezone": "America/New_York", "sessions": [row]}})
    assert response.status_code == 422, response.text
    assert "ambiguo" in response.text
    assert enabled.db.plan_states["member-a"]["plan"] is None
