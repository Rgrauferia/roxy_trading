"""Repeat references assert own current history without writing results or plans."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from roxy_os.fitness import router, training_selection
from tools import roxy_home_service as service
from test_roxy_home_fitness_api import api, headers, private_cache, PREFIX
from test_roxy_home_fitness_training_plan import storage, save, selected, PROGRAM, SESSION
from test_roxy_home_fitness_training_targets_plan import targets, record

PREVIEW = PREFIX + "/me/training/preview"


@pytest.fixture
def repeat_api(api, storage, monkeypatch):
    agenda, base, db = storage
    save(agenda)
    logs, actual = record(base)
    monkeypatch.setattr(router, "repository", lambda: base)
    real = training_selection.preview_training
    monkeypatch.setattr(training_selection, "preview_training", lambda *a, **kw: real(*a, **kw, now=datetime(2026, 9, 14, tzinfo=timezone.utc)))
    api.repository, api.db, api.agenda = base, db, agenda
    return api


def payload(**changes):
    return {"program_id": PROGRAM, "confirmed_requirements": selected()["confirmed_requirements"],
        "start_date": "2026-09-14", "source_session_id": SESSION, "expected_logs_version": 2, **changes}


def state(api):
    return deepcopy((api.db.states, api.db.requests, api.db.plan_states, api.db.plan_requests,
                     api.db.log_states, api.db.log_requests))


@pytest.mark.parametrize("chosen", [None, True])
def test_repeat_preview_keeps_goals_optional_and_never_writes_history(repeat_api, chosen):
    before = state(repeat_api)
    data = payload(**({"training_targets": targets()} if chosen else {}))
    response = repeat_api.client.post(PREVIEW, headers=headers(), json=data)
    assert response.status_code == 200, response.text
    private_cache(response)
    rows = response.json()["proposal"]["sessions"]
    assert rows
    for row in rows:
        assert row.get("training_targets") == (targets() if chosen else None)
        assert "source_session_id" not in row
    assert state(repeat_api) == before


@pytest.mark.parametrize("version", [0, 1, 3])
def test_stale_repeat_source_returns_private_conflict_without_writes(repeat_api, version):
    before = state(repeat_api)
    response = repeat_api.client.post(PREVIEW, headers=headers(), json=payload(expected_logs_version=version))
    assert response.status_code == 409, response.text
    private_cache(response)
    assert state(repeat_api) == before


def test_missing_source_returns_private_422_without_creating_agenda(repeat_api):
    before = state(repeat_api)
    response = repeat_api.client.post(PREVIEW, headers=headers(), json=payload(source_session_id=str(uuid4())))
    assert response.status_code == 422, response.text
    private_cache(response)
    assert state(repeat_api) == before


def test_another_member_cannot_repeat_a_foreign_record_via_query(repeat_api):
    before = state(repeat_api)
    repeat_api.identity = service.AuthContext("member", "shared-household", "member-b")
    response = repeat_api.client.post(PREVIEW + "?member_id=member-a", headers=headers(member="member-b"),
        json=payload(expected_logs_version=0))
    assert response.status_code == 422, response.text
    private_cache(response)
    assert SESSION not in response.text
    assert state(repeat_api) == before


@pytest.mark.parametrize("missing", ["source_session_id", "expected_logs_version"])
def test_repeat_source_and_version_are_required_together_before_storage(repeat_api, missing):
    data = payload(); data.pop(missing)
    repeat_api.db.calls.clear()
    response = repeat_api.client.post(PREVIEW, headers=headers(), json=data)
    assert response.status_code == 422
    private_cache(response)
    assert repeat_api.db.calls == []
