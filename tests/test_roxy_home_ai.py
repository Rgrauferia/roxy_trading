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
        is_recipe_review = "text" in kwargs and "tool_choice" in kwargs
        is_conversation = "text" in kwargs and "tool_choice" not in kwargs
        is_safety = "tool_choice" in kwargs
        output = []
        if is_recipe_review:
            output = [{"type": "web_search_call", "action": {"sources": [{"title": "Fuente culinaria", "url": "https://example.com/recipe"}]}}]
            payload = {
                "title": "Café cubano", "description": "Versión canónica", "kind": "drink",
                "drink_type": "non_alcoholic", "category": "coffee_hot", "subcategory": "Cafés calientes",
                "servings": 4,
                "ingredients": [
                    {"name": "Agua", "quantity": 1.25, "unit": "taza", "notes": ""},
                    {"name": "Café", "quantity": .33, "unit": "taza", "notes": ""},
                    {"name": "Azúcar", "quantity": .25, "unit": "taza", "notes": ""},
                ],
                "steps": ["Paso 1 durante 2 minutos.", "Paso 2 durante 2 minutos.", "Paso 3 durante 2 minutos.", "Paso 4 durante 2 minutos.", "Paso 5 durante 2 minutos."],
                "allergen_notes": [],
            }
        elif is_safety:
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
        elif is_conversation:
            payload = {
                "answer": "Usaría primero el pollo que ya tienes.",
                "reasoning_summary": "Aprovecha la despensa y evita una compra innecesaria.",
                "recommendation": "Prepáralo al ajo con arroz.",
                "follow_up": "¿Quieres una versión rápida?",
                "confidence": "high",
            }
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
    assert call["reasoning"] == {"effort": "low"}
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


def test_recipe_curation_uses_terra_required_search_and_strict_schema(tmp_path):
    client = FakeClient()
    ai = RoxyHomeAI(config(tmp_path), client=client)
    result = ai.curate_recipe("Café cubano", {"profile": {}, "pantry": []})
    call = client.responses.calls[0]

    assert call["model"] == "gpt-5.6-terra"
    assert call["tools"] == [{"type": "web_search"}]
    assert call["tool_choice"] == "required"
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True
    assert result["sources"][0]["url"] == "https://example.com/recipe"


def test_conversation_synthesizes_home_context_and_recent_turns(tmp_path):
    client = FakeClient()
    ai = RoxyHomeAI(config(tmp_path), client=client)
    result = ai.converse(
        "¿Qué me recomiendas para cenar y por qué?",
        {
            "profile": {"diet": "normal"},
            "pantry": [{"name": "Pollo", "quantity": 1, "unit": "paquete"}],
            "shopping": [{"name": "Arroz", "quantity": 1, "unit": "bolsa"}],
            "today_meals": [],
            "calendar": [],
            "trading": {"positions": ["secret"]},
        },
        history=[{"role": "user", "content": "No quiero pasta"}],
        display_name="Robert",
        deep=True,
    )
    call = client.responses.calls[0]

    assert result["recommendation"] == "Prepáralo al ajo con arroz."
    assert call["model"] == "gpt-5.6-terra"
    assert call["reasoning"] == {"effort": "high"}
    assert call["store"] is False
    assert call["text"]["format"]["strict"] is True
    assert "No quiero pasta" in call["input"]
    assert "Pollo" in call["input"]
    assert "positions" not in call["input"]


def test_home_budget_is_enforced_independently(tmp_path):
    client = FakeClient()
    ai = RoxyHomeAI(config(tmp_path, daily_request_limit=1), client=client)
    ai.generate_recipe("primera", {"profile": {}, "pantry": []})
    with pytest.raises(HomeAIBudgetExceeded):
        ai.generate_recipe("segunda", {"profile": {}, "pantry": []})
    assert len(client.responses.calls) == 1
    assert ai.budget.snapshot()["output_tokens"] == 25
