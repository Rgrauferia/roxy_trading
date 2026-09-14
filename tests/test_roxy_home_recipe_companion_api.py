"""Member-isolated recipe companion. No real account, keys or provider calls."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_demo import trial_access_mode
from tools import roxy_home_service as service


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "_LOGIN_RATE_STATE", {})
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-companion-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "companion-test")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "food.json"))
    accounts = HomeAccountStore(tmp_path / "accounts.json")
    a = accounts.bootstrap("companion-test", household_name="Synthetic home", username="companion-a",
                           display_name="A", password="Synthetic-Only-2026")
    b = accounts.add_member(a["id"], username="companion-b", display_name="B", password="Synthetic-Only-2026")
    client = TestClient(service.app, base_url="https://companion.test")
    assert client.post("/v1/home-account/login", json={"username": "companion-a", "password": "Synthetic-Only-2026"}).status_code == 200
    calls = []
    def ask(question, context, *, actor_key):
        calls.append((question, deepcopy(context), actor_key))
        return {"answer": "Bate con movimientos continuos para integrar la mezcla del paso.",
                "supporting_steps": [1], "needs_clarification": False, "usage": {"internal": True}}
    monkeypatch.setattr(service, "_home_ai", lambda: SimpleNamespace(recipe_companion=ask))
    drink = service.drink_detail("vietnamese-coffee")["drink"]
    payload = {"source": "drink", "recipe_id": drink["id"], "recipe_version": drink["source_sha256"],
               "step_index": 0, "question": "¿Me explicas la técnica de este paso?", "language": "es"}
    headers = {"Origin": "https://companion.test", "X-Roxy-Recipe-Member": a["id"]}
    return client, accounts, a, b, calls, payload, headers


def post(setup, **changes):
    client, _, _, _, _, payload, headers = setup
    return client.post("/v1/home-food/companion-test/recipe-companion", json={**payload, **changes}, headers=headers)


def preferences():
    return {"schema_version": 1, "completed": True, "consent": True, "language": "es",
            "country_of_origin": "Cuba", "cuisine_mode": "mixed", "cuisines": [],
            "favorite_foods": ["pasta"], "diet": "omnivore", "allergy_status": "none",
            "allergies": [], "other_allergies": "", "dislikes": [], "max_minutes": None, "skill": "beginner"}


def speech_request(setup, **changes):
    client, _, _, _, _, payload, headers = setup
    body = {key: value for key, value in payload.items() if key != "question"}
    return client.post("/v1/home-food/companion-test/recipe-speech", json={**body, **changes}, headers=headers)


def test_official_guide_voice_uses_canonical_step_and_member_scope(setup, monkeypatch):
    from fastapi.responses import Response
    calls = []
    monkeypatch.setattr(service, "_official_voice_response", lambda text, user: (calls.append((text, user)) or Response(b"synthetic-audio", media_type="audio/mpeg")))
    result = speech_request(setup)
    assert result.status_code == 200
    assert result.headers["content-type"] == "audio/mpeg"
    assert "no-store" in result.headers["cache-control"]
    assert calls == [(service.drink_detail("vietnamese-coffee")["drink"]["steps_es"][0], setup[2]["id"])]
    assert not setup[4], "Narration does not invoke OpenAI"


def test_official_guide_voice_can_read_a_displayed_reply_without_editing_recipe(setup, monkeypatch):
    from fastapi.responses import Response
    calls = []
    before = service.drink_detail("vietnamese-coffee")
    monkeypatch.setattr(service, "_official_voice_response", lambda text, user: (calls.append(text) or Response(b"audio", media_type="audio/mpeg")))
    assert speech_request(setup, kind="response", text="El phin es el filtro de esta receta.").status_code == 200
    assert calls == ["El phin es el filtro de esta receta."]
    assert service.drink_detail("vietnamese-coffee") == before
    assert not setup[4]


@pytest.mark.parametrize("change", [{"text": "Injected step"}, {"kind": "response", "text": " "},
                                    {"kind": "response", "text": "private" * 201}, {"step_index": 127},
                                    {"recipe_version": "0" * 64}, {"kind": "arbitrary"}, {"include_preferences": True}])
def test_voice_rejects_invalid_or_stale_scope_before_synthesis(setup, monkeypatch, change):
    calls = []
    monkeypatch.setattr(service, "_official_voice_response", lambda *args: calls.append(args))
    result = speech_request(setup, **change)
    assert result.status_code in (409, 422)
    assert not calls
    assert "Injected step" not in result.text and "privateprivate" not in result.text


def test_official_voice_requires_origin_and_current_member_and_keeps_trial_gate(setup, monkeypatch):
    calls = []
    monkeypatch.setattr(service, "_official_voice_response", lambda *args: calls.append(args))
    client, _, _, other, _, payload, headers = setup
    body = {k: v for k, v in payload.items() if k != "question"}
    path = "/v1/home-food/companion-test/recipe-speech"
    for changed in ({}, {**headers, "Origin": "https://evil.test"}, {**headers, "X-Roxy-Recipe-Member": other["id"]}):
        assert client.post(path, json=body, headers=changed).status_code in (403, 409)
    assert trial_access_mode("POST", path) == "unavailable"
    assert not calls


def test_official_voice_discards_audio_after_account_revocation(setup, monkeypatch):
    from fastapi.responses import Response
    client, accounts, member, _, _, _, _ = setup
    original = service._account_store
    def revoke(*_):
        monkeypatch.setattr(service, "_account_store", lambda: SimpleNamespace(member=lambda _id: None))
        return Response(b"should-not-be-served", media_type="audio/mpeg")
    monkeypatch.setattr(service, "_official_voice_response", revoke)
    result = speech_request(setup)
    assert result.status_code == 409
    assert "should-not-be-served" not in result.text


def test_exact_source_step_without_other_household_context(setup):
    client, accounts, a, b, calls, payload, _ = setup
    accounts.update_recipe_profile(a["id"], profile=preferences(), expected_revision=0)
    response = post(setup)
    assert response.status_code == 200, response.text
    assert response.json()["mode"] == "ai_explanation"
    assert response.json()["preferences_used"] is False
    assert "no-store" in response.headers["cache-control"]
    assert len(calls) == 1 and calls[0][2] == a["id"]
    context = calls[0][1]
    assert context["steps"] == service.drink_detail(payload["recipe_id"])["drink"]["steps_es"]
    assert context["step_index"] == 0
    assert not {"preferences", "profile", "pantry", "shopping", "today_meals", "person"} & context.keys()
    assert "usage" not in response.json()
    assert accounts.get_recipe_profile(b["id"])["profile"] is None


def test_explicit_preference_opt_in_only_reads_own_minimal_profile(setup):
    _, accounts, a, b, calls, _, _ = setup
    accounts.update_recipe_profile(a["id"], profile=preferences(), expected_revision=0)
    accounts.update_recipe_profile(b["id"], profile={**preferences(), "dislikes": ["OTHER_MEMBER_SECRET"]}, expected_revision=0)
    response = post(setup, include_preferences=True)
    assert response.status_code == 200, response.text
    assert response.json()["preferences_used"] is True
    context = calls[0][1]
    assert context["preferences"]["skill"] == "beginner"
    assert "country_of_origin" not in context["preferences"]
    assert "OTHER_MEMBER_SECRET" not in str(context)


def test_opt_in_requires_saved_preferences(setup):
    assert post(setup, include_preferences=True).status_code == 422
    assert not setup[4]


@pytest.mark.parametrize("change", [{"step_index": True}, {"step_index": -1}, {"step_index": 127},
                                   {"recipe_version": "0" * 64}, {"question": "x" * 601},
                                   {"ingredients": ["Injected recipe body"]}, {"include_preferences": "true"}])
def test_invalid_and_stale_requests_do_not_call_ai(setup, change):
    result = post(setup, **change)
    assert result.status_code in (409, 422)
    assert not setup[4]
    assert "Injected recipe body" not in result.text


def test_origin_member_and_user_binding(setup):
    client, _, a, b, calls, payload, headers = setup
    path = "/v1/home-food/companion-test/recipe-companion"
    for override, status in [({}, 409), ({"X-Roxy-Recipe-Member": b["id"]}, 409),
                             ({"X-Roxy-Recipe-Member": a["id"]}, 403),
                             ({**headers, "Origin": "https://evil.test"}, 403)]:
        assert client.post(path, json=payload, headers=override).status_code == status
    assert client.post(path.replace("companion-test", "different-house"), json=payload, headers=headers).status_code == 403
    client.post("/v1/home-account/login", json={"username": "companion-b", "password": "Synthetic-Only-2026"})
    assert client.post(path, json=payload, headers=headers).status_code == 409
    assert not calls


def test_unknown_recipe_does_not_invent_one(setup):
    assert post(setup, recipe_id="does-not-exist").status_code == 404
    assert not setup[4]


def test_myplate_live_rechecks_version_without_storing_or_sending_preferences_to_source(setup, monkeypatch):
    upstream_calls = []
    recipe = {"slug": "synthetic-source", "title": "Source recipe", "source_url": "https://myplate.food/recipes/synthetic-source",
              "ingredients": [{"text": "1 cup water", "note": None}], "source_steps": ["Stir the mixture gently."],
              "directions": "Stir the mixture gently."}
    def upstream(slug):
        upstream_calls.append(slug)
        return {"recipe": deepcopy(recipe)}
    monkeypatch.setattr(service.myplate_recipes, "get_recipe", upstream)
    version = service._companion_version(service._myplate_companion_context(recipe))
    response = post(setup, source="myplate", recipe_id="synthetic-source", recipe_version=version, language="en")
    assert response.status_code == 200, response.text
    assert upstream_calls == ["synthetic-source"]
    assert setup[4][0][1]["steps"] == recipe["source_steps"]
    recipe["source_steps"] = ["Changed original."]
    assert post(setup, source="myplate", recipe_id="synthetic-source", recipe_version=version, language="en").status_code == 409
    assert len(setup[4]) == 1


def test_safety_question_is_free_no_shopping_actions(setup):
    response = post(setup, question="¿Es seguro para mi alergia a la leche?")
    assert response.status_code == 200, response.text
    assert response.json()["mode"] == "safety_notice"
    assert not setup[4]


def test_saved_session_resolves_stored_recipe_and_stale_step_is_blocked(setup, monkeypatch):
    detail = {"session": {"id": "session", "status": "ACTIVE"}, "step_number": 1,
              "recipe": {"id": "stored", "title": "Original", "steps": ["Bate la mezcla.", "Sirve."],
                         "ingredients": [{"quantity": 1, "unit": "taza", "name": "agua"}]}}
    monkeypatch.setattr(service, "_home_food_store", lambda: SimpleNamespace(cooking_session_detail=lambda user, sid: deepcopy(detail)))
    response = post(setup, source="saved", recipe_id="stored", recipe_version="", session_id="session")
    assert response.status_code == 200, response.text
    assert setup[4][0][1]["ingredients"] == ["1 taza agua"]
    assert post(setup, source="saved", recipe_id="stored", recipe_version="", session_id="session", step_index=1).status_code == 409
    assert len(setup[4]) == 1


def test_demo_admitted_only_to_route_that_reserves_ai_after_validation():
    assert trial_access_mode("POST", "/v1/home-food/synthetic/recipe-companion") == "local"
    assert trial_access_mode("GET", "/v1/home-food/synthetic/recipe-companion") == "unavailable"


def test_recipe_edited_while_answering_discards_paid_but_stale_reply(setup, monkeypatch):
    detail = {"session": {"id": "session", "status": "ACTIVE"}, "step_number": 1,
              "recipe": {"id": "stored", "title": "Original", "steps": ["Bate la mezcla."],
                         "ingredients": [{"quantity": 1, "unit": "taza", "name": "agua"}]}}
    monkeypatch.setattr(service, "_home_food_store", lambda: SimpleNamespace(cooking_session_detail=lambda user, sid: deepcopy(detail)))
    def edit(question, context, *, actor_key):
        detail["recipe"]["steps"] = ["Otra preparación."]
        return {"answer": "No debe mostrarse.", "supporting_steps": [1], "needs_clarification": False}
    monkeypatch.setattr(service, "_home_ai", lambda: SimpleNamespace(recipe_companion=edit))
    response = post(setup, source="saved", recipe_id="stored", recipe_version="", session_id="session")
    assert response.status_code == 409
    assert "No debe mostrarse" not in response.text


def test_private_preferences_changed_during_answer_discard_reply(setup, monkeypatch):
    _, accounts, a, _, _, _, _ = setup
    accounts.update_recipe_profile(a["id"], profile=preferences(), expected_revision=0)
    def edit(question, context, *, actor_key):
        accounts.update_recipe_profile(a["id"], profile={**preferences(), "skill": "confident"}, expected_revision=1)
        return {"answer": "No debe mostrarse.", "supporting_steps": [1], "needs_clarification": False}
    monkeypatch.setattr(service, "_home_ai", lambda: SimpleNamespace(recipe_companion=edit))
    response = post(setup, include_preferences=True)
    assert response.status_code == 409
    assert "No debe mostrarse" not in response.text


def test_original_english_can_receive_spanish_explanation_without_changing_steps(setup):
    response = post(setup, language="en")
    assert response.status_code == 200
    assert response.json()["language"] == "es"
    assert setup[4][0][1]["language"] == "es"
    assert setup[4][0][1]["steps"][0].startswith("Boil water.")
