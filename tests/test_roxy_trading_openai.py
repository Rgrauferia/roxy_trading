import json
from types import SimpleNamespace

import httpx
from openai import OpenAI

from roxy_trader.openai_brain import (
    DEEP_TIER,
    RoxyOpenAIConfig,
    RoxyOpenAIUsageLedger,
    RoxyTradingOpenAIBrain,
    route_tier,
)


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text="La señal sigue en WATCH; falta confirmar volumen.",
            model=kwargs["model"],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200, total_tokens=1200),
        )


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


def configured(tmp_path, **overrides):
    values = dict(
        api_key="trading-only-secret",
        enabled=True,
        monthly_budget_usd=10.0,
        max_call_reserve_usd=0.25,
        ledger_path=tmp_path / "usage.sqlite",
    )
    values.update(overrides)
    return RoxyOpenAIConfig(**values)


def test_config_never_falls_back_to_generic_or_study_key():
    config = RoxyOpenAIConfig.from_env(
        {
            "OPENAI_API_KEY": "generic-secret",
            "ROXY_STUDY_OPENAI_API_KEY": "study-secret",
            "ROXY_TRADING_OPENAI_ENABLED": "1",
        }
    )

    assert config.api_key == ""
    assert config.public_status()["configured"] is False
    assert "api_key" not in config.public_status()


def test_router_uses_terra_for_current_research():
    assert route_tier("Investiga las noticias y escenarios de NVDA") == DEEP_TIER


def test_current_market_question_requires_sources(tmp_path):
    client = FakeClient()
    answer = RoxyTradingOpenAIBrain(configured(tmp_path), client=client).answer(
        "¿Cuál es el precio actual de AAPL?", market_context={"symbol": "AAPL"}
    )

    assert answer.blocked_reason == "missing_market_sources"
    assert answer.execution_allowed is False
    assert client.responses.calls == []


def test_sensitive_action_requires_confirmation_and_never_executes(tmp_path):
    client = FakeClient()
    brain = RoxyTradingOpenAIBrain(configured(tmp_path), client=client)
    context = {"sources": [{"name": "Alpaca IEX"}], "data_as_of": "2026-08-19T14:31:00Z"}

    blocked = brain.answer("Compra AAPL ahora", market_context=context)
    preview = brain.answer("Compra AAPL ahora", market_context=context, confirmed=True)

    assert blocked.requires_confirmation is True
    assert blocked.execution_allowed is False
    assert preview.status == "ok"
    assert preview.execution_allowed is False
    assert len(client.responses.calls) == 1
    assert client.responses.calls[0]["store"] is False
    assert client.responses.calls[0]["reasoning"] == {"effort": "low"}


def test_responses_usage_sources_cost_and_budget_are_reported(tmp_path):
    client = FakeClient()
    config = configured(
        tmp_path,
        routine_input_usd_per_mtoken=2.0,
        routine_output_usd_per_mtoken=8.0,
    )
    answer = RoxyTradingOpenAIBrain(config, client=client).answer(
        "Explica la señal de AAPL",
        market_context={
            "symbol": "AAPL",
            "signal": "WATCH",
            "data_as_of": "2026-08-19T14:31:00Z",
            "sources": [{"name": "Finviz Elite", "as_of": "2026-08-19T14:30:00Z"}],
            "api_key": "must-not-leave-context",
        },
    )

    assert answer.status == "ok"
    assert answer.sources[0].name == "Finviz Elite"
    assert answer.usage.total_tokens == 1200
    assert answer.usage.estimated_cost_usd == 0.0036
    assert answer.usage.monthly_spend_usd == 0.0036
    assert "must-not-leave-context" not in client.responses.calls[0]["input"]
    assert client.responses.calls[0]["model"] == "gpt-5.6-luna"


def test_budget_reservation_blocks_parallel_overspend(tmp_path):
    config = configured(tmp_path, monthly_budget_usd=0.25, max_call_reserve_usd=0.25)
    ledger = RoxyOpenAIUsageLedger(config.ledger_path)
    first = ledger.reserve(model=config.routine_model, tier="routine", amount_usd=0.25, budget_usd=0.25)
    second = ledger.reserve(model=config.routine_model, tier="routine", amount_usd=0.25, budget_usd=0.25)

    assert first
    assert second is None


def test_public_explain_contract_never_exposes_key(monkeypatch, tmp_path):
    from tools.llm_agent import ExplainRequest, explain_verified_context

    monkeypatch.setenv("ROXY_TRADING_OPENAI_ENABLED", "0")
    monkeypatch.setenv("ROXY_TRADING_OPENAI_API_KEY", "server-only-secret")
    monkeypatch.setenv("ROXY_TRADING_OPENAI_USAGE_DB", str(tmp_path / "route.sqlite"))
    response = explain_verified_context(
        ExplainRequest(question="Explica medias móviles"),
        caller={"type": "admin"},
    )
    payload = response.model_dump()

    assert payload["status"] == "blocked"
    assert payload["execution_allowed"] is False
    assert "server-only-secret" not in str(payload)


def test_installed_sdk_serializes_supported_responses_payload_without_network(tmp_path):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "resp_local_mock",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "gpt-5.6-luna",
                "output": [],
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            },
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        sdk_client = OpenAI(
            api_key="dummy-local-test-key",
            base_url="https://sdk-serialization.invalid/v1",
            http_client=http_client,
        )
        answer = RoxyTradingOpenAIBrain(
            configured(tmp_path),
            client=sdk_client,
        ).answer("Explica cómo funcionan las medias móviles")

    assert answer.status == "empty_response"
    assert captured["payload"]["reasoning"] == {"effort": "low"}
    assert captured["payload"]["store"] is False
    assert "context" not in captured["payload"]["reasoning"]


def test_deep_current_research_requires_web_search_and_returns_sources(tmp_path):
    class WebResponses:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                output_text="El catalizador debe evaluarse junto al riesgo técnico.",
                model=kwargs["model"],
                usage=SimpleNamespace(input_tokens=100, output_tokens=50, total_tokens=150),
                output=[
                    {
                        "type": "web_search_call",
                        "action": {
                            "sources": [
                                {"title": "Fuente oficial", "url": "https://example.test/current"}
                            ]
                        },
                    }
                ],
            )

    client = SimpleNamespace(responses=WebResponses())
    answer = RoxyTradingOpenAIBrain(configured(tmp_path), client=client).answer(
        "Investiga las noticias y catalizadores actuales de AAPL",
        market_context={
            "symbol": "AAPL",
            "data_as_of": "2026-08-19T14:31:00Z",
            "sources": [{"name": "Alpaca IEX"}],
        },
    )

    assert answer.status == "ok"
    assert client.responses.calls[0]["tools"] == [{"type": "web_search"}]
    assert client.responses.calls[0]["tool_choice"] == "required"
    assert answer.sources[-1].url == "https://example.test/current"
