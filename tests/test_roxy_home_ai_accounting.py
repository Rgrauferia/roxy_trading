"""Usage and member quotas with synthetic providers and temporary Home state."""
from datetime import date, timedelta
import json
from types import SimpleNamespace

import pytest

import roxy_os.home_ai as module
from roxy_os.home_ai import HomeAIConfig, HomeAIBudgetExceeded, HomeAIBudgetLedger, HomeAIBudgetStorageError, RoxyHomeAI


class Provider:
    def __init__(self, *, model="gpt-5.6-luna", incoming=100, outgoing=25, cached=0, reasoning=5, payload=None):
        self.calls = []
        self.response = SimpleNamespace(
            model=model, output_text=json.dumps(payload or {"answer": "Respuesta de prueba"}), output=[],
            usage=SimpleNamespace(input_tokens=incoming, output_tokens=outgoing,
                                  input_tokens_details=SimpleNamespace(cached_tokens=cached),
                                  output_tokens_details=SimpleNamespace(reasoning_tokens=reasoning)),
        )

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def ai(tmp_path, provider=None, **changes):
    settings = {"api_key": "synthetic-home-only", "budget_path": str(tmp_path / "budget.json")}
    settings.update(changes)
    provider = provider or Provider()
    return RoxyHomeAI(HomeAIConfig(**settings), client=SimpleNamespace(responses=provider)), provider


def call(assistant, *, actor=None, deep=False, cap=None):
    return assistant._respond("Consulta sintética", {}, deep=deep, actor_key=actor, max_output_tokens=cap)


def test_sdk_automatic_retries_are_disabled_for_one_reservation_one_attempt(tmp_path, monkeypatch):
    import openai
    captured = {}
    def create_client(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(responses=Provider())
    monkeypatch.setattr(openai, "OpenAI", create_client)
    RoxyHomeAI(HomeAIConfig(api_key="synthetic-home", budget_path=str(tmp_path / "budget.json")))
    assert captured["max_retries"] == 0


def test_known_text_usage_is_persisted_once_without_double_billing_reasoning(tmp_path):
    assistant, provider = ai(tmp_path)
    result = call(assistant)
    usage = result["usage"]
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 25
    assert usage["cached_input_tokens"] == 0
    assert usage["reasoning_output_tokens"] == 5
    assert usage["estimated_text_cost_usd"] == pytest.approx(0.00005)
    assert usage["estimate_status"] == "complete"
    raw = json.loads(assistant.budget.path.read_text())
    receipt_id, receipt = next(iter(raw["settled_requests"].items()))
    assert receipt["usage"] == usage
    assistant.budget.record_output_tokens(25, reservation_id=receipt_id, usage=usage)
    summary = assistant.budget.snapshot()["usage_summary"]
    assert summary["known_input_tokens"] == 100
    assert summary["known_estimated_text_cost_usd"] == pytest.approx(0.00005)
    assert len(provider.calls) == 1


def test_terra_uses_approved_rate_and_cache_is_explicitly_incomplete(tmp_path):
    assistant, _ = ai(tmp_path, Provider(model="gpt-5.6-terra", cached=30))
    usage = call(assistant, deep=True)["usage"]
    assert usage["estimated_text_cost_usd"] == pytest.approx(0.0005)
    assert usage["estimate_status"] == "incomplete"
    assert usage["cached_input_tokens"] == 30
    assert "cached_input_discount_unknown_regular_rate_used" in usage["estimate_notes"]


@pytest.mark.parametrize("model", [None, "", "gpt-unpriced", "gpt-5.6-luna-2099-01-01"])
def test_missing_or_unpriced_returned_model_never_invents_cost(tmp_path, model):
    assistant, _ = ai(tmp_path, Provider(model=model))
    usage = call(assistant)["usage"]
    assert usage["estimated_text_cost_usd"] is None
    assert usage["estimate_status"] == "unknown"
    assert usage["requested_model"] == "gpt-5.6-luna"
    assert assistant.budget.snapshot()["usage_summary"]["requests_with_unknown_text_cost"] == 1


def test_legacy_provider_output_only_keeps_unknown_fields_unknown(tmp_path):
    provider = Provider()
    provider.response.usage = SimpleNamespace(output_tokens=25)
    assistant, _ = ai(tmp_path, provider)
    usage = call(assistant)["usage"]
    assert all(usage[key] is None for key in ("input_tokens", "cached_input_tokens", "reasoning_output_tokens"))
    assert usage["estimated_text_cost_usd"] is None
    assert assistant.budget.snapshot()["output_tokens"] == 25
    assert assistant.budget.snapshot()["pending_request"] is None


def test_unknown_web_cost_and_image_price_are_never_complete_totals(tmp_path):
    provider = Provider(model="gpt-5.6-terra")
    provider.response.output = [{"type": "web_search_call", "action": {"sources": []}}]
    assistant, _ = ai(tmp_path, provider)
    web = assistant._respond("consulta", {}, deep=True, current=True)["usage"]
    assert web["estimated_text_cost_usd"] == pytest.approx(0.0005)
    assert web["tool_cost_usd"] is None and web["estimate_status"] == "incomplete"
    assert "tool_cost_unknown" in web["estimate_notes"]
    image = assistant.import_recipe("data:image/png;base64,synthetic", {}, source_type="image")["usage"]
    assert image["estimated_text_cost_usd"] is None
    assert "non_text_input_price_unknown" in image["estimate_notes"]


def test_legacy_usage_is_preserved_and_missing_input_is_not_reported_as_complete(tmp_path):
    assistant, _ = ai(tmp_path)
    old = {"date": date.today().isoformat(), "requests": 7, "output_tokens": 333, "costs": {"prior_usd": 2.5}}
    assistant.budget.path.write_text(json.dumps(old))
    call(assistant)
    snapshot = assistant.budget.snapshot()
    assert snapshot["requests"] == 8 and snapshot["output_tokens"] == 358
    assert snapshot["costs"] == old["costs"]
    summary = snapshot["usage_summary"]
    assert summary["requests_without_detailed_usage"] == 7
    assert summary["known_input_tokens"] == 100
    assert summary["requests_without_input_tokens"] == 7
    assert summary["estimate_status"] == "incomplete"


def test_legacy_extra_output_without_request_receipt_keeps_cost_incomplete(tmp_path):
    assistant, _ = ai(tmp_path)
    call(assistant)
    assistant.budget.record_output_tokens(17)
    summary = assistant.budget.snapshot()["usage_summary"]
    assert summary["output_tokens"] == 42
    assert summary["output_tokens_without_detailed_usage"] == 17
    assert summary["estimate_status"] == "incomplete"


def test_actor_cap_is_personal_durable_and_uses_only_opaque_digest(tmp_path):
    assistant, provider = ai(tmp_path, companion_daily_request_limit=2)
    call(assistant, actor="member:synthetic-a")
    call(assistant, actor="member:synthetic-a")
    restarted, _ = ai(tmp_path, provider, companion_daily_request_limit=2)
    with pytest.raises(HomeAIBudgetExceeded):
        call(restarted, actor="member:synthetic-a")
    call(restarted, actor="member:synthetic-b")
    call(restarted)
    assert len(provider.calls) == 4
    serialized = assistant.budget.path.read_text()
    assert "member:" not in serialized and "synthetic-a" not in serialized
    assert "member:" not in json.dumps(provider.calls)
    counts = json.loads(serialized)["actor_requests"]
    assert sorted(counts.values()) == [1, 2]
    assert all(len(key) == 64 for key in counts)


def test_default_actor_cap_is_twenty_and_enforced_before_provider_call(tmp_path):
    assistant, provider = ai(tmp_path)
    for _ in range(20):
        call(assistant, actor="member:synthetic")
    with pytest.raises(HomeAIBudgetExceeded):
        call(assistant, actor="member:synthetic")
    assert len(provider.calls) == 20


def test_provider_failure_keeps_pending_reservation_and_actor_spend(tmp_path):
    assistant, provider = ai(tmp_path)
    def unavailable(**kwargs):
        provider.calls.append(kwargs)
        raise RuntimeError("synthetic timeout")
    provider.create = unavailable
    with pytest.raises(RuntimeError):
        call(assistant, actor="member:synthetic")
    snapshot = assistant.budget.snapshot()
    assert snapshot["requests"] == 1 and list(snapshot["actor_requests"].values()) == [1]
    assert snapshot["pending_request"] is not None
    with pytest.raises(HomeAIBudgetStorageError, match="pendiente"):
        call(assistant, actor="member:synthetic")
    assert len(provider.calls) == 1


def test_invalid_answer_still_settles_known_spend_and_does_not_refund_actor(tmp_path):
    provider = Provider()
    provider.response.output_text = "invalid JSON"
    assistant, _ = ai(tmp_path, provider, companion_daily_request_limit=1)
    with pytest.raises(ValueError):
        call(assistant, actor="member:synthetic")
    assert assistant.budget.snapshot()["pending_request"] is None
    with pytest.raises(HomeAIBudgetExceeded):
        call(assistant, actor="member:synthetic")
    assert len(provider.calls) == 1


@pytest.mark.parametrize("damage", ["actor_count", "actor_map", "usage_count", "usage_missing"])
def test_corrupt_new_accounting_fails_closed_without_changing_disk(tmp_path, damage):
    assistant, _ = ai(tmp_path)
    call(assistant, actor="member:synthetic")
    raw = json.loads(assistant.budget.path.read_text())
    if damage == "actor_count":
        raw["actor_requests"][next(iter(raw["actor_requests"]))] = 0
    elif damage == "actor_map":
        raw.pop("actor_requests")
    elif damage == "usage_count":
        next(iter(raw["settled_requests"].values()))["usage"]["input_tokens"] = -1
    else:
        next(iter(raw["settled_requests"].values()))["usage"].pop("input_tokens")
    assistant.budget.path.write_text(json.dumps(raw))
    before = assistant.budget.path.read_bytes()
    with pytest.raises(HomeAIBudgetStorageError):
        assistant.budget.reserve_request(actor_key="member:synthetic", actor_request_limit=20)
    assert assistant.budget.path.read_bytes() == before


def test_new_day_resets_personal_cap_but_preserves_receipts_and_cost_history(tmp_path, monkeypatch):
    class Clock(date):
        current = date(2026, 9, 10)
        @classmethod
        def today(cls):
            return cls.current
    monkeypatch.setattr(module, "date", Clock)
    assistant, _ = ai(tmp_path, companion_daily_request_limit=1)
    call(assistant, actor="member:synthetic")
    prior = assistant.budget.snapshot()["settled_requests"]
    Clock.current += timedelta(days=1)
    call(assistant, actor="member:synthetic")
    snapshot = assistant.budget.snapshot()
    assert snapshot["requests"] == 1 and list(snapshot["actor_requests"].values()) == [1]
    assert all(snapshot["settled_requests"][key] == value for key, value in prior.items())
    assert snapshot["usage_summary"]["recorded_requests"] == 1


def test_output_cap_respects_member_call_and_remaining_global_allowance(tmp_path):
    assistant, provider = ai(tmp_path, daily_output_token_limit=40)
    call(assistant, actor="member:synthetic", cap=1200)
    assert provider.calls[-1]["max_output_tokens"] == 40
    call(assistant, actor="member:synthetic", cap=1200)
    assert provider.calls[-1]["max_output_tokens"] == 15


def test_companion_defaults_can_be_configured_only_from_home_environment(monkeypatch):
    monkeypatch.setenv("ROXY_HOME_OPENAI_API_KEY", "synthetic-home")
    monkeypatch.delenv("ROXY_HOME_COMPANION_DAILY_REQUEST_LIMIT", raising=False)
    monkeypatch.delenv("ROXY_HOME_COMPANION_MAX_OUTPUT_TOKENS", raising=False)
    defaults = HomeAIConfig.from_env()
    assert defaults.companion_daily_request_limit == 20 and defaults.companion_max_output_tokens == 1200
    monkeypatch.setenv("ROXY_HOME_COMPANION_DAILY_REQUEST_LIMIT", "8")
    monkeypatch.setenv("ROXY_HOME_COMPANION_MAX_OUTPUT_TOKENS", "700")
    selected = HomeAIConfig.from_env()
    assert selected.companion_daily_request_limit == 8 and selected.companion_max_output_tokens == 700


def recipe_context():
    return {"title": "Huevos de prueba", "ingredients": ["2 huevos"],
            "steps": ["Mezcla suavemente los huevos."], "step_index": 0, "language": "es",
            "source": "Receta sintética", "source_url": "",
            "history": [{"role": "user", "content": "No entiendo esta técnica."}],
            "member_id": "private-member-must-not-send", "location": "private-location-must-not-send"}


def test_companion_luna_uses_strict_domain_and_bounded_private_context(tmp_path):
    provider = Provider(payload={"answer": "Mueve la mezcla suavemente desde abajo hacia arriba.",
                                 "supporting_steps": [1], "needs_clarification": False})
    assistant, _ = ai(tmp_path, provider)
    result = assistant.recipe_companion("¿Cómo lo mezclo?", recipe_context(), actor_key="member:private-actor")
    request = provider.calls[0]
    assert request["model"] == "gpt-5.6-luna"
    assert request["max_output_tokens"] == 1200
    assert request["store"] is False and "tools" not in request
    schema = request["text"]["format"]
    assert schema["type"] == "json_schema" and schema["strict"] is True
    assert schema["schema"]["additionalProperties"] is False
    sent = json.loads(request["input"])
    assert sent["home_context"] == {}
    assert "2 huevos" in sent["task"] and "No entiendo" in sent["task"]
    assert "private-" not in request["input"]
    assert result["answer"] == "Mueve la mezcla suavemente desde abajo hacia arriba."
    assert result["supporting_steps"] == [1]
    assert result["usage"]["output_tokens"] == 25


def test_companion_invalid_source_blocks_before_spending_or_creating_ledger(tmp_path):
    assistant, provider = ai(tmp_path)
    context = recipe_context()
    context["step_index"] = 3
    with pytest.raises(ValueError):
        assistant.recipe_companion("¿Cómo lo mezclo?", context, actor_key="member:synthetic")
    assert provider.calls == []
    assert not assistant.budget.path.exists()


def test_companion_invalid_answer_keeps_valid_usage_and_member_charge(tmp_path):
    provider = Provider(payload={"answer": "Cocina 999 minutos.", "supporting_steps": [1], "needs_clarification": False})
    assistant, _ = ai(tmp_path, provider, companion_daily_request_limit=1)
    with pytest.raises(ValueError):
        assistant.recipe_companion("¿Cómo lo mezclo?", recipe_context(), actor_key="member:synthetic")
    snapshot = assistant.budget.snapshot()
    assert snapshot["pending_request"] is None and snapshot["output_tokens"] == 25
    assert snapshot["usage_summary"]["recorded_requests"] == 1
    with pytest.raises(HomeAIBudgetExceeded):
        assistant.recipe_companion("¿Cómo lo mezclo?", recipe_context(), actor_key="member:synthetic")
    assert len(provider.calls) == 1


class ProviderFailure(RuntimeError):
    def __init__(self, status=400, code="unsupported_value", param="reasoning.effort", request_id="req_synthetic199"):
        super().__init__("SECRET message with question, household, bearer and raw response")
        self.status_code = status
        self.code = code
        self.param = param
        self.request_id = request_id
        self.body = {"error": {"message": "SECRET body", "code": code, "param": param}}


@pytest.mark.parametrize("status", [400, 401, 403, 404, 408, 409, 422, 429, 500, 502, 503])
def test_provider_failure_persists_minimal_diagnostics_without_releasing_quota(tmp_path, status):
    assistant, provider = ai(tmp_path)
    error = ProviderFailure(status=status)
    def reject(**kwargs):
        provider.calls.append(kwargs)
        raise error
    provider.create = reject
    with pytest.raises(ProviderFailure) as caught:
        call(assistant, actor="member:synthetic", cap=1200)
    assert caught.value is error
    snapshot = assistant.budget.snapshot()
    failure = snapshot["pending_request"]["provider_failure"]
    assert failure == {"status_code": status, "code": "unsupported_value", "param": "reasoning.effort",
                       "request_id": "req_synthetic199", "requested_model": "gpt-5.6-luna",
                       "max_output_tokens": 1200, "usage_verified": False, "disposition": "pending_review"}
    assert snapshot["requests"] == 1 and snapshot["output_tokens"] == 0
    assert list(snapshot["actor_requests"].values()) == [1]
    assert "SECRET" not in assistant.budget.path.read_text()
    with pytest.raises(HomeAIBudgetStorageError):
        call(assistant, actor="member:synthetic")
    assert len(provider.calls) == 1


def test_unstructured_timeout_leaves_unknown_diagnostics_pending(tmp_path):
    assistant, provider = ai(tmp_path)
    provider.create = lambda **_: (_ for _ in ()).throw(TimeoutError("SECRET URL and input"))
    with pytest.raises(TimeoutError):
        call(assistant)
    failure = assistant.budget.snapshot()["pending_request"]["provider_failure"]
    assert all(failure[key] is None for key in ("status_code", "code", "param", "request_id"))
    assert failure["usage_verified"] is False
    assert "SECRET" not in assistant.budget.path.read_text()


def test_untrusted_diagnostic_strings_are_omitted_and_body_messages_never_stored(tmp_path):
    assistant, provider = ai(tmp_path)
    error = ProviderFailure(status=True, code="sk-secret-value", param="question SECRET", request_id="https://secret.test")
    provider.create = lambda **_: (_ for _ in ()).throw(error)
    with pytest.raises(ProviderFailure):
        call(assistant)
    failure = assistant.budget.snapshot()["pending_request"]["provider_failure"]
    assert all(failure[key] is None for key in ("status_code", "code", "param", "request_id"))
    raw = assistant.budget.path.read_text()
    assert "SECRET" not in raw and "sk-secret" not in raw and "https://" not in raw


def test_manual_conservative_settlement_retains_failure_and_marks_usage_incomplete(tmp_path):
    assistant, provider = ai(tmp_path)
    provider.create = lambda **_: (_ for _ in ()).throw(ProviderFailure())
    with pytest.raises(ProviderFailure):
        call(assistant, actor="member:synthetic", cap=1200)
    before = assistant.budget.snapshot()
    reservation_id = before["pending_request"]["id"]
    # Only a deliberate operator reconciliation supplies this known upper bound.
    assistant.budget.record_output_tokens(1200, reservation_id=reservation_id)
    settled = assistant.budget.snapshot()
    assert settled["pending_request"] is None
    assert settled["requests"] == 1 and settled["output_tokens"] == 1200
    assert settled["actor_requests"] == before["actor_requests"]
    assert settled["settled_requests"][reservation_id]["provider_failure"] == before["pending_request"]["provider_failure"]
    assert settled["usage_summary"]["estimate_status"] == "incomplete"
    assert settled["usage_summary"]["requests_without_detailed_usage"] == 1


def test_diagnostics_cannot_overwrite_another_or_already_diagnosed_reservation(tmp_path):
    assistant, _ = ai(tmp_path)
    reservation = assistant.budget.reserve_request()
    with pytest.raises(HomeAIBudgetStorageError):
        assistant.budget.record_provider_failure(ProviderFailure(), reservation_id="0" * 32,
                                                requested_model="gpt-5.6-luna", max_output_tokens=1200)
    identifier = reservation["reservation_id"]
    first = assistant.budget.record_provider_failure(ProviderFailure(), reservation_id=identifier,
                                                     requested_model="gpt-5.6-luna", max_output_tokens=1200)
    with pytest.raises(HomeAIBudgetStorageError):
        assistant.budget.record_provider_failure(ProviderFailure(status=503), reservation_id=identifier,
                                                requested_model="gpt-5.6-luna", max_output_tokens=1200)
    assert assistant.budget.snapshot()["pending_request"]["provider_failure"] == first


def test_corrupt_failure_receipt_blocks_without_resetting_pending(tmp_path):
    assistant, provider = ai(tmp_path)
    provider.create = lambda **_: (_ for _ in ()).throw(ProviderFailure())
    with pytest.raises(ProviderFailure):
        call(assistant)
    raw = json.loads(assistant.budget.path.read_text())
    raw["pending_request"]["provider_failure"]["usage_verified"] = True
    assistant.budget.path.write_text(json.dumps(raw))
    before = assistant.budget.path.read_bytes()
    with pytest.raises(HomeAIBudgetStorageError):
        assistant.budget.reserve_request()
    assert assistant.budget.path.read_bytes() == before


def test_confirmed_credit_exhaustion_has_curated_message_and_blocks_further_calls(tmp_path):
    assistant, provider = ai(tmp_path)
    def reject(**kwargs):
        provider.calls.append(kwargs)
        raise ProviderFailure(status=429, code="credit_balance_exhausted", param=None)
    provider.create = reject
    with pytest.raises(module.HomeAIConfigurationError, match="no tiene saldo de IA") as first:
        call(assistant, actor="member:synthetic")
    assert "SECRET" not in str(first.value)
    snapshot = assistant.budget.snapshot()
    assert snapshot["requests"] == 1 and snapshot["output_tokens"] == 0
    assert snapshot["pending_request"]["provider_failure"]["code"] == "credit_balance_exhausted"
    with pytest.raises(HomeAIBudgetStorageError, match="no tiene saldo de IA") as next_attempt:
        call(assistant, actor="member:synthetic")
    assert next_attempt.value.code == "provider_credit_exhausted"
    assert len(provider.calls) == 1


def test_credit_code_without_matching_429_does_not_claim_billing_cause(tmp_path):
    assistant, provider = ai(tmp_path)
    provider.create = lambda **_: (_ for _ in ()).throw(ProviderFailure(status=503, code="credit_balance_exhausted"))
    with pytest.raises(ProviderFailure):
        call(assistant)
    with pytest.raises(HomeAIBudgetStorageError) as caught:
        call(assistant)
    assert caught.value.code == "pending_usage"
    assert "saldo" not in str(caught.value)
