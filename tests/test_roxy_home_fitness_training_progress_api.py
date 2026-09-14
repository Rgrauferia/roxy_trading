"""HTTP access to a read-only projection of real synthetic private records."""
from copy import deepcopy

import pytest

from roxy_os.fitness import training_progress as progress_module
from roxy_os.fitness.training_content import TrainingContentError
from roxy_os.fitness.training_logs import TrainingLogsRepository
from tools import roxy_home_service as service
from test_roxy_home_fitness_api import api, headers, private_cache, PREFIX, MEMBER
from test_roxy_home_fitness_repository import CONSENT as PROFILE_CONSENT
from test_roxy_home_fitness_training_logs import content, LOG, DETAIL, SESSION_ID
from test_roxy_home_fitness_training_logs_api import logs_api, setup, save

PROGRESS = PREFIX + "/me/training-progress"


def persisted(api):
    return deepcopy((api.db.states, api.db.requests, api.db.plan_states, api.db.plan_requests,
                     api.db.log_states, api.db.log_requests))


@pytest.mark.parametrize("asserted", [None, "member-b", "shared-household"])
def test_progress_header_asserts_identity_and_never_selects_another_member(logs_api, asserted):
    supplied = headers()
    if asserted is None:
        supplied.pop("X-Roxy-Fitness-Member")
    else:
        supplied["X-Roxy-Fitness-Member"] = asserted
    response = logs_api.client.get(PROGRESS, headers=supplied)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "identity_changed"
    private_cache(response)
    assert logs_api.db.calls == []


@pytest.mark.parametrize("mode", ["legacy", "bearer"])
def test_progress_rejects_shared_household_access(logs_api, mode):
    logs_api.identity = service.AuthContext(mode, "shared-household", None)
    response = logs_api.client.get(PROGRESS, headers=headers())
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "personal_login_required"
    private_cache(response)
    assert logs_api.db.calls == []


def test_progress_unauthenticated_error_is_private_and_does_not_access_storage(logs_api, monkeypatch):
    monkeypatch.delitem(service.app.dependency_overrides, service._authenticate)
    response = logs_api.client.get(PROGRESS, headers=headers())
    assert response.status_code == 401
    private_cache(response)
    assert logs_api.db.calls == []


def test_empty_progress_does_not_create_state_or_request_write_headers(logs_api):
    before = persisted(logs_api)
    response = logs_api.client.get(PROGRESS, headers={"X-Roxy-Fitness-Member": MEMBER})
    assert response.status_code == 200, response.text
    private_cache(response)
    result = response.json()
    assert result["logs_version"] == 0 and result["updated_at"] is None
    assert result["summary"]["recorded_sessions"] == 0
    assert result["summary"]["duration"]["total_minutes"] is None
    assert result["workouts"] == result["exercises"] == []
    assert persisted(logs_api) == before
    assert not any(sql.startswith(("INSERT", "UPDATE", "DELETE")) for sql, _ in logs_api.db.calls)


def test_saved_records_are_summarized_without_writing_or_exposing_profile(logs_api):
    setup(logs_api)
    saved = save(logs_api)
    before = persisted(logs_api)
    logs_api.db.calls.clear()
    response = logs_api.client.get(PROGRESS, headers=headers())
    assert response.status_code == 200, response.text
    private_cache(response)
    result = response.json()
    assert result["logs_version"] == saved["version"]
    assert result["updated_at"] == saved["updated_at"]
    assert result["self_reported"] is True and result["clinical_approval"] is False
    assert result["summary"]["recorded_sessions"] == 1
    assert result["summary"]["performed_exercise_entries"] == 1
    assert result["summary"]["skipped_exercise_entries"] == 1
    assert result["summary"]["duration"] == {"reported_sessions": 1, "unreported_sessions": 0, "total_minutes": 20}
    workout = result["workouts"][0]
    assert workout["session_id"] == SESSION_ID and workout["can_repeat"] is False
    entry = next(row for row in result["exercises"] if row["exercise_id"] == "test-reps")
    assert entry["latest"]["sets"] == saved["logs"][0]["exercises"][0]["sets"]
    assert entry["latest"]["sets"][0]["load"] == {"value": 10, "unit": "lb"}
    assert entry["latest"]["sets"][0]["load_kg"] == 4.535924
    assert entry["comparison"] is None and entry["comparison_reason"] == "no_previous_day"
    assert not {"profile", "consent", "age_band", "primary_goal", "eligible", "member_id"}.intersection(result)
    assert persisted(logs_api) == before
    assert not any(sql.startswith(("INSERT", "UPDATE", "DELETE")) for sql, _ in logs_api.db.calls)


def test_identity_switch_with_member_query_cannot_return_previous_members_progress(logs_api):
    setup(logs_api); save(logs_api)
    before = persisted(logs_api)
    logs_api.identity = service.AuthContext("member", "shared-household", "member-b")
    response = logs_api.client.get(PROGRESS + "?member_id=member-a", headers=headers(member="member-b"))
    assert response.status_code == 200
    private_cache(response)
    assert response.json()["summary"]["recorded_sessions"] == 0
    assert response.json()["workouts"] == response.json()["exercises"] == []
    assert SESSION_ID not in response.text and "test-reps" not in response.text
    assert persisted(logs_api) == before


def test_revoking_profile_preserves_previously_consented_history_visibility(logs_api):
    setup(logs_api); save(logs_api)
    first = logs_api.client.get(PROGRESS, headers=headers())
    assert first.status_code == 200
    logs_api.repository.set_consent(MEMBER, {**PROFILE_CONSENT, "granted": False}, expected_version=2,
                                    idempotency_key="revoke-only-profile")
    assert logs_api.repository.snapshot(MEMBER)["profile"] is None
    assert TrainingLogsRepository(logs_api.repository).snapshot(MEMBER)["eligible"] is False
    before = persisted(logs_api)
    response = logs_api.client.get(PROGRESS, headers=headers())
    assert response.status_code == 200 and response.json() == first.json()
    private_cache(response)
    assert persisted(logs_api) == before


def test_repeat_flag_tracks_current_content_without_rewriting_historical_records(logs_api, monkeypatch):
    setup(logs_api); save(logs_api)
    current = {"id": LOG["program_id"], "title": "Rutina sintética actual", **deepcopy(DETAIL)}
    for exercise in current["exercises"]:
        exercise.update(name="Movimiento sintético " + exercise["id"], dose={"per_side": False},
                        source_links=[{"title": "Fuente sintética", "url": "https://example.org/source"}])
    monkeypatch.setattr(progress_module, "training_catalog", lambda: {"programs": [{"id": current["id"]}]})
    monkeypatch.setattr(progress_module, "training_detail", lambda _: deepcopy(current))
    before = persisted(logs_api)
    response = logs_api.client.get(PROGRESS, headers=headers())
    assert response.status_code == 200
    private_cache(response)
    assert response.json()["workouts"][0]["can_repeat"] is True
    assert all(row["current_content_available"] for row in response.json()["exercises"])
    current["content_version"] = "test-v2"
    stale = logs_api.client.get(PROGRESS, headers=headers())
    assert stale.status_code == 200
    private_cache(stale)
    assert stale.json()["workouts"][0]["can_repeat"] is False
    assert stale.json()["summary"] == response.json()["summary"]
    assert not any(row["current_content_available"] for row in stale.json()["exercises"])
    assert persisted(logs_api) == before


def test_invalid_source_returns_sanitized_private_503_and_preserves_records(logs_api, monkeypatch):
    setup(logs_api); save(logs_api)
    before = persisted(logs_api)
    def unavailable():
        raise TrainingContentError("Synthetic private failure must never be reflected")
    monkeypatch.setattr(progress_module, "training_catalog", unavailable)
    response = logs_api.client.get(PROGRESS, headers=headers())
    assert response.status_code == 503
    private_cache(response)
    assert "Synthetic" not in response.text and SESSION_ID not in response.text
    assert persisted(logs_api) == before


def test_missing_storage_does_not_present_an_empty_successful_history(api):
    response = api.client.get(PROGRESS, headers=headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "private_storage_unavailable"
    private_cache(response)
