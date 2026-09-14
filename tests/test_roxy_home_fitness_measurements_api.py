"""Private HTTP measurements contract using synthetic, member-isolated SQL.

Real PostgreSQL/RLS verification lives in the separate measurements PG suite.
"""
from copy import deepcopy
import json

import pytest

from roxy_os.fitness import router
from roxy_os.fitness.repository import PostgresFitnessRepository
from tools import roxy_home_service as service
from test_roxy_home_fitness_api import api, headers, private_cache, PREFIX, MEMBER
from test_roxy_home_fitness_measurements import (
    MeasurementsSyntheticDB, CONSENT, MEASUREMENT, RECORD_ID, adult,
)
from test_roxy_home_fitness_repository import DSN


BASE = PREFIX + "/me/measurements"
ROUTES = [
    ("GET", BASE, None),
    ("GET", BASE + "/export", None),
    ("PUT", BASE, {"expected_version": 0, "measurement": MEASUREMENT}),
    ("POST", BASE + "/consent", {"expected_version": 0, "consent": CONSENT}),
    ("DELETE", BASE + "/" + RECORD_ID, {"expected_version": 0, "confirm_delete": True}),
    ("DELETE", BASE, {"expected_version": 0, "confirm_delete": True}),
]
MUTATIONS = [route for route in ROUTES if route[0] != "GET"]


@pytest.fixture
def measurements_api(api, monkeypatch):
    db = MeasurementsSyntheticDB()
    repo = PostgresFitnessRepository(DSN, connection_factory=db.connect)
    monkeypatch.setattr(router, "repository", lambda: repo)
    api.db, api.repository = db, repo
    return api


def grant(api):
    adult(api.repository)
    result = api.client.post(BASE + "/consent", headers=headers(key="measure-grant-0001"),
                             json={"expected_version": 0, "consent": CONSENT})
    assert result.status_code == 200, result.text
    private_cache(result)
    return result.json()


def save(api, *, record=None, version=1, key="measure-save-0001"):
    result = api.client.put(BASE, headers=headers(key=key),
                            json={"expected_version": version, "measurement": record or MEASUREMENT})
    assert result.status_code == 200, result.text
    private_cache(result)
    return result.json()


@pytest.mark.parametrize("method,path,payload", ROUTES)
@pytest.mark.parametrize("asserted_member", [None, "member-b"])
def test_identity_assertion_on_every_measurements_endpoint(measurements_api, method, path, payload, asserted_member):
    supplied = headers(member=asserted_member or MEMBER)
    if asserted_member is None:
        supplied.pop("X-Roxy-Fitness-Member")
    response = measurements_api.client.request(method, path, headers=supplied, json=payload)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "identity_changed"
    private_cache(response)
    assert measurements_api.db.calls == []


@pytest.mark.parametrize("method,path,payload", ROUTES)
@pytest.mark.parametrize("mode", ["legacy", "bearer"])
def test_shared_identity_cannot_access_measurements(measurements_api, method, path, payload, mode):
    measurements_api.identity = service.AuthContext(mode, "shared-household", None)
    response = measurements_api.client.request(method, path, headers=headers(), json=payload)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "personal_login_required"
    private_cache(response)
    assert measurements_api.db.calls == []


@pytest.mark.parametrize("method,path,payload", ROUTES)
def test_unauthenticated_measurements_errors_are_private(measurements_api, monkeypatch, method, path, payload):
    monkeypatch.delitem(service.app.dependency_overrides, service._authenticate)
    response = measurements_api.client.request(method, path, headers=headers(), json=payload)
    assert response.status_code == 401
    private_cache(response)
    assert measurements_api.db.calls == []


@pytest.mark.parametrize("method,path,payload", MUTATIONS)
@pytest.mark.parametrize("defect", ["foreign_origin", "missing_origin", "missing_request_header"])
def test_measurement_mutations_require_explicit_same_origin(measurements_api, method, path, payload, defect):
    supplied = headers()
    if defect == "foreign_origin":
        supplied["Origin"] = "https://foreign.example"
    else:
        supplied.pop("Origin" if defect == "missing_origin" else "X-Roxy-Fitness-Request")
    response = measurements_api.client.request(method, path, headers=supplied, json=payload)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "csrf_rejected"
    private_cache(response)
    assert measurements_api.db.calls == []


def test_full_optional_measurement_consent_edit_export_and_delete_contract(measurements_api):
    client = measurements_api.client
    initial = client.get(BASE, headers=headers())
    assert initial.status_code == 200
    assert initial.json()["eligible"] is False
    assert initial.json()["measurements"] == []
    private_cache(initial)
    assert not measurements_api.db.measurements_states
    grant(measurements_api)
    first = save(measurements_api)
    entered = first["measurements"][0]
    assert first["version"] == 2 and first["eligible"] is True
    assert entered["weight"] == MEASUREMENT["weight"]
    assert entered["height"] == MEASUREMENT["height"]
    assert entered["weight_kg"] == 72.574779 and entered["height_cm"] == 173.99

    replay = save(measurements_api)
    assert replay["version"] == 2 and replay["idempotent_replay"] is True
    edited = save(measurements_api, record={**MEASUREMENT, "weight": None,
                  "height": {"value": 175, "unit": "cm"}}, version=2, key="measure-edit-0001")
    assert edited["version"] == 3 and len(edited["measurements"]) == 1
    assert edited["measurements"][0]["weight_kg"] is None
    assert edited["measurements"][0]["recorded_at"] == entered["recorded_at"]
    export = client.get(BASE + "/export", headers=headers())
    assert export.status_code == 200
    assert export.json()["scope"] == "authenticated_member_only"
    assert export.json()["self_reported_measurements"] is True
    assert export.json()["data"]["measurements"] == edited["measurements"]
    private_cache(export)

    deleted = client.request("DELETE", BASE + "/" + RECORD_ID, headers=headers(key="delete-one-0001"),
                              json={"expected_version": 3, "confirm_delete": True})
    assert deleted.status_code == 200 and deleted.json()["measurements"] == []
    assert deleted.json()["consent"]["granted"] is True
    private_cache(deleted)
    cleared = client.request("DELETE", BASE, headers=headers(key="delete-all-0001"),
                              json={"expected_version": 4, "confirm_delete": True})
    assert cleared.status_code == 200 and cleared.json()["consent"] is None
    assert cleared.json()["version"] == 5
    private_cache(cleared)


def test_saved_adult_profile_and_separate_measurement_consent_are_required(measurements_api):
    client = measurements_api.client
    no_profile = client.post(BASE + "/consent", headers=headers(),
                              json={"expected_version": 0, "consent": CONSENT})
    assert no_profile.status_code == 422
    private_cache(no_profile)
    assert not measurements_api.db.measurements_states
    adult(measurements_api.repository)
    no_consent = client.put(BASE, headers=headers(), json={"expected_version": 0, "measurement": MEASUREMENT})
    assert no_consent.status_code == 403
    assert no_consent.json()["detail"]["code"] == "consent_required"
    private_cache(no_consent)
    assert not measurements_api.db.measurements_states


def test_version_conflict_and_invalid_deletion_preserve_current_data(measurements_api):
    grant(measurements_api)
    saved = save(measurements_api)
    cases = [
        ("PUT", BASE, {"expected_version": 1, "measurement": {**MEASUREMENT, "weight": None}}, 409),
        ("DELETE", BASE, {"expected_version": 1, "confirm_delete": True}, 409),
        ("DELETE", BASE, {"expected_version": 2, "confirm_delete": False}, 422),
        ("DELETE", BASE + "/not-a-uuid", {"expected_version": 2, "confirm_delete": True}, 422),
    ]
    for index, (method, path, payload, expected) in enumerate(cases):
        response = measurements_api.client.request(method, path, headers=headers(key=f"invalid-change-{index:04}"), json=payload)
        assert response.status_code == expected
        private_cache(response)
    current = measurements_api.client.get(BASE, headers=headers())
    assert current.json()["version"] == saved["version"]
    assert current.json()["measurements"] == saved["measurements"]


def test_global_export_delete_includes_measurements_and_is_member_scoped(measurements_api):
    grant(measurements_api)
    save(measurements_api)
    # A second synthetic person's data must survive the first person's erase.
    from roxy_os.fitness.measurements import MeasurementsRepository
    second = MeasurementsRepository(measurements_api.repository)
    adult(measurements_api.repository, "member-b")
    second.consent("member-b", CONSENT, expected_version=0, idempotency_key="second-consent-0001")
    second.save("member-b", MEASUREMENT, expected_version=1, idempotency_key="second-record-0001")
    other_before = deepcopy(measurements_api.db.measurements_states["member-b"])

    exported = measurements_api.client.get(PREFIX + "/me/data", headers=headers())
    assert exported.status_code == 200
    assert exported.json()["measurements"]["measurements"][0]["id"] == RECORD_ID
    private_cache(exported)
    deleted = measurements_api.client.request("DELETE", PREFIX + "/me/data", headers=headers(key="global-erase-0001"),
                                                json={"expected_version": 2, "confirm_delete": True})
    assert deleted.status_code == 200 and deleted.json()["profile"] is None
    private_cache(deleted)
    current = measurements_api.client.get(BASE, headers=headers()).json()
    assert current["measurements"] == [] and current["consent"] is None
    assert current["eligible"] is False and current["version"] == 3
    assert measurements_api.db.measurements_states["member-b"] == other_before
    replay = measurements_api.client.put(BASE, headers=headers(key="measure-save-0001"),
                                          json={"expected_version": 1, "measurement": MEASUREMENT})
    assert replay.status_code == 409
    private_cache(replay)


def test_query_member_id_cannot_select_another_person(measurements_api):
    grant(measurements_api)
    save(measurements_api)
    measurements_api.identity = service.AuthContext("member", "shared-household", "member-b")
    for path in (BASE, BASE + "/export"):
        response = measurements_api.client.get(path + "?member_id=member-a", headers=headers(member="member-b"))
        assert response.status_code == 200
        body = response.json()
        assert body.get("data", body)["measurements"] == []
        private_cache(response)
    assert measurements_api.db.measurements_states[MEMBER]["measurements"]


@pytest.mark.parametrize("number", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("field", ["weight", "height"])
def test_nonfinite_raw_json_is_422_without_echo_or_server_error(measurements_api, number, field):
    record = {**MEASUREMENT, field: {"value": number, "unit": "kg" if field == "weight" else "cm"}}
    raw = json.dumps({"expected_version": 0, "measurement": record})
    response = measurements_api.client.put(BASE, headers=headers(), content=raw)
    assert response.status_code == 422
    private_cache(response)
    assert all(set(error) == {"loc", "type", "msg"} for error in response.json()["detail"])
    assert "NaN" not in response.text and "Infinity" not in response.text
    assert RECORD_ID not in response.text and "160" not in response.text
    assert measurements_api.db.calls == []


def test_invalid_sensitive_input_is_not_reflected_in_validation_error(measurements_api):
    secret = "synthetic-private-measurement-do-not-reflect"
    record = {**MEASUREMENT, "weight": {"value": secret, "unit": "kg"}}
    response = measurements_api.client.put(BASE, headers=headers(), json={"expected_version": 0, "measurement": record})
    assert response.status_code == 422 and secret not in response.text
    assert all(set(error) == {"loc", "type", "msg"} for error in response.json()["detail"])
    private_cache(response)
    assert measurements_api.db.calls == []


def test_measurements_missing_migration_fails_explicitly_without_cached_success(api):
    response = api.client.get(BASE, headers=headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "private_storage_unavailable"
    private_cache(response)
