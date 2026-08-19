import json
from types import SimpleNamespace

import pytest

from roxy_os.home_ai import (
    HomeAIBudgetExceeded,
    HomeAIConfig,
    HomeAIConfigurationError,
    RoxyHomeAI,
)


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        is_safety = "tool_choice" in kwargs
        output = []
        if is_safety:
            output = [
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {"title": "FDA Recall", "url": "https://www.fda.gov/safety/recalls"}
                        ]
                    },
                }
            ]
            payload = {"answer": "Consulta vigente", "checked_at": "2026-08-19", "sources": []}
        else:
            payload = {
                "title": "Sopa",
                "servings": 2,
                "ingredients": [{"name": "Agua", "quantity": 2, "unit": "taza"}],
                "steps": ["Hervir"],
            }
        return SimpleNamespace(
            output_text=json.dumps(payload),
            output=output,
            usage=SimpleNamespace(output_tokens=25),
        )


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


def config(tmp_path, **changes):
    values = {
        "api_key": "home-only-key",
        "budget_path": str(tmp_path / "budget.json"),
        "daily_request_limit": 10,
        "daily_output_token_limit": 1000,
    }
    values.update(changes)
    return HomeAIConfig(**values)


def test_config_requires_dedicated_home_key_and_never_falls_back(monkeypatch):
    monkeypatch.delenv("ROXY_HOME_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "generic-study-key")
    with pytest.raises(HomeAIConfigurationError):
        HomeAIConfig.from_env()

    monkeypatch.setenv("ROXY_HOME_OPENAI_API_KEY", "dedicated-home-key")
    loaded = HomeAIConfig.from_env()
    assert loaded.api_key == "dedicated-home-key"
    assert loaded.routine_model == "gpt-5.6-luna"
    assert loaded.deep_model == "gpt-5.6-terra"


def test_routine_uses_luna_store_false_and_only_home_context(tmp_path):
    client = FakeClient()
    ai = RoxyHomeAI(config(tmp_path), client=client)
    snapshot = {
        "profile": {"allergies": ["Nueces"]},
        "pantry": [{"name": "Arroz", "quantity": 1, "unit": "taza"}],
        "recipes": [{"private": "not-sent"}],
        "trading": {"positions": ["secret"]},
    }
    result = ai.generate_recipe("una sopa", snapshot)
    call = client.responses.calls[0]

    assert result["model_profile"] == "luna"
    assert call["model"] == "gpt-5.6-luna"
    assert call["store"] is False
    assert "tools" not in call
    assert "Nueces" in call["input"]
    assert "positions" not in call["input"]
    assert "not-sent" not in call["input"]


def test_current_food_safety_forces_terra_required_web_search_and_sources(tmp_path):
    client = FakeClient()
    ai = RoxyHomeAI(config(tmp_path), client=client)
    result = ai.food_safety("retiros activos", {"profile": {}, "pantry": []})
    call = client.responses.calls[0]

    assert call["model"] == "gpt-5.6-terra"
    assert call["tools"] == [{"type": "web_search"}]
    assert call["tool_choice"] == "required"
    assert result["used_current_web_search"] is True
    assert result["sources"][0]["url"] == "https://www.fda.gov/safety/recalls"


def test_home_budget_is_enforced_independently(tmp_path):
    client = FakeClient()
    ai = RoxyHomeAI(config(tmp_path, daily_request_limit=1), client=client)
    ai.generate_recipe("primera", {"profile": {}, "pantry": []})
    with pytest.raises(HomeAIBudgetExceeded):
        ai.generate_recipe("segunda", {"profile": {}, "pantry": []})
    assert len(client.responses.calls) == 1
    assert ai.budget.snapshot()["output_tokens"] == 25
