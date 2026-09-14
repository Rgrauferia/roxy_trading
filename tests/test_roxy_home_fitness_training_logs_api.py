"""Authenticated private HTTP contract for manually entered exercise results."""
from copy import deepcopy
import json

import pytest

from roxy_os.fitness import router
from roxy_os.fitness.repository import PostgresFitnessRepository
from roxy_os.fitness.training_logs import TrainingLogsRepository
from tools import roxy_home_service as service
from test_roxy_home_fitness_api import api, headers, private_cache, PREFIX, MEMBER
from test_roxy_home_fitness_training_logs import (LogsSyntheticDB, LOG, CONSENT, SESSION_ID,
                                                 prepare, content)
from test_roxy_home_fitness_repository import DSN

BASE = PREFIX + "/me/training-logs"
ROUTES = [
    ("GET", BASE, None), ("GET", BASE + "/export", None),
    ("PUT", BASE, {"expected_version": 0, "log": LOG}),
    ("POST", BASE + "/consent", {"expected_version": 0, "consent": CONSENT}),
    ("DELETE", BASE + "/" + SESSION_ID, {"expected_version": 0, "confirm_delete": True}),
    ("DELETE", BASE, {"expected_version": 0, "confirm_delete": True}),
]
MUTATIONS = [item for item in ROUTES if item[0] != "GET"]


@pytest.fixture
def logs_api(api, monkeypatch, content):
    db = LogsSyntheticDB()
    repo = PostgresFitnessRepository(DSN, connection_factory=db.connect)
    monkeypatch.setattr(router, "repository", lambda: repo)
    api.db, api.repository = db, repo
    return api


def setup(api):
    prepare(api.repository)
    response = api.client.post(BASE + "/consent", headers=headers(key="training-grant"),
                               json={"expected_version": 0, "consent": CONSENT})
    assert response.status_code == 200, response.text
    private_cache(response)


def save(api, *, payload=None, version=1, key="training-save"):
    response = api.client.put(BASE, headers=headers(key=key),
                              json={"expected_version": version, "log": payload or LOG})
    assert response.status_code == 200, response.text
    private_cache(response)
    return response.json()


@pytest.mark.parametrize("method,path,payload", ROUTES)
@pytest.mark.parametrize("member", [None, "other-member"])
def test_all_routes_assert_current_identity(logs_api, method, path, payload, member):
    supplied = headers(member=member or MEMBER)
    if member is None:
        supplied.pop("X-Roxy-Fitness-Member")
    response = logs_api.client.request(method, path, headers=supplied, json=payload)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "identity_changed"
    private_cache(response)
    assert logs_api.db.calls == []


@pytest.mark.parametrize("method,path,payload", ROUTES)
@pytest.mark.parametrize("mode", ["legacy", "bearer"])
def test_shared_household_credentials_do_not_access_results(logs_api, method, path, payload, mode):
    logs_api.identity = service.AuthContext(mode, "shared-household", None)
    response = logs_api.client.request(method, path, headers=headers(), json=payload)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "personal_login_required"
    private_cache(response)
    assert logs_api.db.calls == []


@pytest.mark.parametrize("method,path,payload", ROUTES)
def test_unauthenticated_requests_return_private_errors(logs_api, monkeypatch, method, path, payload):
    monkeypatch.delitem(service.app.dependency_overrides, service._authenticate)
    response = logs_api.client.request(method, path, headers=headers(), json=payload)
    assert response.status_code == 401
    private_cache(response)
    assert logs_api.db.calls == []


@pytest.mark.parametrize("method,path,payload", MUTATIONS)
@pytest.mark.parametrize("defect", ["foreign_origin", "missing_origin", "missing_request_header"])
def test_mutation_requires_same_origin_intent(logs_api, method, path, payload, defect):
    supplied = headers()
    if defect == "foreign_origin":
        supplied["Origin"] = "https://foreign.example"
    else:
        supplied.pop("Origin" if defect == "missing_origin" else "X-Roxy-Fitness-Request")
    response = logs_api.client.request(method, path, headers=supplied, json=payload)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "csrf_rejected"
    private_cache(response)
    assert logs_api.db.calls == []


def test_full_optional_log_correction_export_and_deletion_flow(logs_api):
    initial = logs_api.client.get(BASE, headers=headers())
    assert initial.status_code == 200 and initial.json()["logs"] == []
    private_cache(initial)
    assert not logs_api.db.log_states
    setup(logs_api)
    row = save(logs_api)["logs"][0]
    assert row["exercises"][0]["sets"][0]["load_kg"] == 4.535924
    assert save(logs_api)["idempotent_replay"] is True
    edited = save(logs_api, payload={**LOG, "duration_minutes": None}, version=2, key="correct-log")
    assert edited["logs"][0]["recorded_at"] == row["recorded_at"]
    assert edited["logs"][0]["duration_minutes"] is None
    export = logs_api.client.get(BASE + "/export", headers=headers())
    assert export.status_code == 200 and export.json()["data"] == edited
    assert export.json()["scope"] == "authenticated_member_only"
    private_cache(export)
    deleted = logs_api.client.request("DELETE", BASE + "/" + SESSION_ID, headers=headers(key="remove-one-log"),
                                      json={"expected_version": 3, "confirm_delete": True})
    assert deleted.status_code == 200 and deleted.json()["logs"] == []
    assert deleted.json()["consent"]["granted"] is True
    private_cache(deleted)
    cleared = logs_api.client.request("DELETE", BASE, headers=headers(key="remove-all-logs"),
                                      json={"expected_version": 4, "confirm_delete": True})
    assert cleared.status_code == 200 and cleared.json()["consent"] is None
    private_cache(cleared)


def test_no_adult_no_consent_or_no_agenda_are_explicit_errors(logs_api):
    no_adult = logs_api.client.post(BASE + "/consent", headers=headers(), json={"expected_version": 0, "consent": CONSENT})
    assert no_adult.status_code == 422
    private_cache(no_adult)
    prepare(logs_api.repository)
    no_consent = logs_api.client.put(BASE, headers=headers(), json={"expected_version": 0, "log": LOG})
    assert no_consent.status_code == 403 and no_consent.json()["detail"]["code"] == "consent_required"
    private_cache(no_consent)
    assert not logs_api.db.log_states


def test_version_conflict_and_false_deletion_confirmation_preserve_log(logs_api):
    setup(logs_api); saved = save(logs_api)
    for index, (method, path, payload, expected) in enumerate([
        ("PUT", BASE, {"expected_version": 1, "log": {**LOG, "duration_minutes": 22}}, 409),
        ("DELETE", BASE, {"expected_version": 2, "confirm_delete": False}, 422),
        ("DELETE", BASE + "/bad-id", {"expected_version": 2, "confirm_delete": True}, 422),
    ]):
        response = logs_api.client.request(method, path, headers=headers(key=f"invalid-case-{index}"), json=payload)
        assert response.status_code == expected, response.text
        private_cache(response)
    assert logs_api.client.get(BASE, headers=headers()).json() == saved


def test_query_member_cannot_select_others_and_cross_member_remove_is_rejected(logs_api):
    setup(logs_api); save(logs_api)
    logs_api.identity = service.AuthContext("member", "shared-household", "member-b")
    for path in (BASE, BASE + "/export"):
        response = logs_api.client.get(path + "?member_id=member-a", headers=headers(member="member-b"))
        assert response.status_code == 200
        body = response.json()
        assert body.get("data", body)["logs"] == []
        private_cache(response)
    response = logs_api.client.request("DELETE", BASE + "/" + SESSION_ID, headers=headers(member="member-b"),
                                       json={"expected_version": 0, "confirm_delete": True})
    assert response.status_code == 422
    private_cache(response)
    assert logs_api.db.log_states[MEMBER]["logs"]


def test_global_export_delete_and_old_retry_cannot_restore_results(logs_api):
    setup(logs_api); save(logs_api)
    prepare(logs_api.repository, "member-b")
    repo = TrainingLogsRepository(logs_api.repository)
    repo.consent("member-b", CONSENT, expected_version=0, idempotency_key="other-consent")
    repo.save("member-b", LOG, expected_version=1, idempotency_key="other-record")
    other = deepcopy(repo.snapshot("member-b"))
    exported = logs_api.client.get(PREFIX + "/me/data", headers=headers())
    assert exported.status_code == 200
    assert exported.json()["training_logs"]["logs"][0]["session_id"] == SESSION_ID
    private_cache(exported)
    deleted = logs_api.client.request("DELETE", PREFIX + "/me/data", headers=headers(key="delete-global"),
                                      json={"expected_version": 2, "confirm_delete": True})
    assert deleted.status_code == 200
    private_cache(deleted)
    assert repo.snapshot("member-a")["logs"] == []
    assert repo.snapshot("member-b") == other
    replay = logs_api.client.put(BASE, headers=headers(key="training-save"), json={"expected_version": 1, "log": LOG})
    assert replay.status_code == 409
    private_cache(replay)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_json_is_sanitized_without_echo(logs_api, number):
    raw = json.dumps({"expected_version": 0, "log": {**LOG, "duration_minutes": number}})
    response = logs_api.client.put(BASE, headers=headers(), content=raw)
    assert response.status_code == 422
    assert "NaN" not in response.text and "Infinity" not in response.text and SESSION_ID not in response.text
    assert all(set(error) == {"loc", "type", "msg"} for error in response.json()["detail"])
    private_cache(response)
    assert logs_api.db.calls == []


def test_private_input_not_reflected_in_validation_error(logs_api):
    secret = "synthetic-private-result-never-reflect"
    response = logs_api.client.put(BASE, headers=headers(), json={"expected_version": 0, "log": {**LOG, "duration_minutes": secret}})
    assert response.status_code == 422 and secret not in response.text
    private_cache(response)
    assert logs_api.db.calls == []


def test_missing_training_storage_is_explicitly_unavailable(api):
    response = api.client.get(BASE, headers=headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "private_storage_unavailable"
    private_cache(response)


def test_skipped_session_blocks_new_log_until_explicitly_returned_to_pending(logs_api):
    setup(logs_api)
    path = PREFIX + "/me/activity-plan/sessions/" + SESSION_ID
    skipped = logs_api.client.patch(path, headers=headers(key="skip-before-recording"),
                                     json={"expected_version": 2, "status": "skipped"})
    assert skipped.status_code == 200
    before = deepcopy(logs_api.db.log_states[MEMBER])
    rejected = logs_api.client.put(BASE, headers=headers(key="record-skipped-session"),
                                   json={"expected_version": 1, "log": LOG})
    assert rejected.status_code == 422 and "omitida" in rejected.text
    private_cache(rejected)
    assert logs_api.db.log_states[MEMBER] == before
    pending = logs_api.client.patch(path, headers=headers(key="return-before-record"),
                                     json={"expected_version": 3, "status": "planned"})
    assert pending.status_code == 200
    assert save(logs_api)["logs"]


def test_skipped_session_preserves_previous_logs_but_cannot_correct_them(logs_api):
    setup(logs_api); saved = save(logs_api)
    path = PREFIX + "/me/activity-plan/sessions/" + SESSION_ID
    skipped = logs_api.client.patch(path, headers=headers(key="skip-after-recording"),
                                     json={"expected_version": 2, "status": "skipped"})
    assert skipped.status_code == 200
    rejected = logs_api.client.put(BASE, headers=headers(key="correct-skipped-record"),
                                   json={"expected_version": 2, "log": {**LOG, "duration_minutes": 30}})
    assert rejected.status_code == 422 and "omitida" in rejected.text
    private_cache(rejected)
    assert logs_api.client.get(BASE, headers=headers()).json() == saved
    exported = logs_api.client.get(BASE + "/export", headers=headers())
    assert exported.json()["data"] == saved
    private_cache(exported)
    deleted = logs_api.client.request("DELETE", BASE + "/" + SESSION_ID,
                                      headers=headers(key="remove-while-skipped"),
                                      json={"expected_version": 2, "confirm_delete": True})
    assert deleted.status_code == 200 and deleted.json()["logs"] == []
    private_cache(deleted)
