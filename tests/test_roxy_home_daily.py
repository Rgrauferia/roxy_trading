from datetime import datetime, timezone

from fastapi.testclient import TestClient

from roxy_os.home_daily import build_home_daily_brief
from roxy_os.home_food import HomeFoodStore


def test_daily_brief_prioritizes_real_home_data():
    brief = build_home_daily_brief(
        display_name="Robert",
        shopping={
            "items": [
                {"name": "Leche", "status": "PENDING"},
                {"name": "Café", "status": "PENDING"},
            ]
        },
        food={
            "pantry": [{"name": "Arroz", "quantity": 1, "unit": "bolsa"}],
            "weekly_plans": [
                {
                    "days": [
                        {
                            "date": "2026-08-24",
                            "meals": [{"meal_type": "dinner", "title": "Pollo al ajo", "minutes": 25}],
                        }
                    ]
                }
            ],
        },
        calendar={
            "events": [
                {
                    "title": "Llamada del trabajo",
                    "starts_at": "2026-08-24T17:00:00+00:00",
                    "ends_at": "2026-08-24T18:00:00+00:00",
                }
            ]
        },
        now=datetime(2026, 8, 24, 12, tzinfo=timezone.utc),
    )

    assert brief["summary"].startswith("Robert,")
    assert [card["kind"] for card in brief["cards"]] == ["calendar", "meal", "shopping", "pantry"]
    assert brief["counts"] == {"shopping_pending": 2, "pantry": 1, "events_upcoming": 1, "meals_today": 1, "pet_tasks": 0, "pet_followups": 0}
    assert brief["today_meals"][0]["title"] == "Pollo al ajo"


def test_daily_brief_includes_pet_care_and_followup():
    brief = build_home_daily_brief(
        display_name="Robert",
        shopping={"items": []},
        food={
            "pantry": [], "weekly_plans": [],
            "pets": [{
                "id": "pet-1", "name": "Luna", "species": "ferret", "exact_species": "Hurón doméstico",
                "care_log": [],
                "medical_history": [{"title": "Control anual", "next_due_on": "2026-09-05"}],
            }],
        },
        calendar={"events": []},
        now=datetime(2026, 9, 1, 12, tzinfo=timezone.utc),
    )

    pet_cards = [card for card in brief["cards"] if card["kind"] == "pet"]
    assert [card["id"] for card in pet_cards] == ["pet-followup", "pet-care"]
    assert pet_cards[0]["action"] == {"panel": "recipes", "audience": "pet", "pet_id": "pet-1", "tab": "medical"}
    assert brief["counts"]["pet_tasks"] == 4
    assert brief["counts"]["pet_followups"] == 1


def test_pantry_voice_memory_adds_merges_and_removes_items(tmp_path):
    store = HomeFoodStore(tmp_path / "home.json")

    store.upsert_pantry("robert", [{"name": "Leche", "quantity": 1, "unit": "litro"}])
    pantry = store.upsert_pantry("robert", [{"name": "leche", "quantity": 2, "unit": "litro"}])
    removed, missing = store.remove_pantry("robert", ["Leche", "Café"])

    assert pantry[0]["quantity"] == 3
    assert removed[0]["name"].casefold() == "leche"
    assert missing == ["Café"]
    assert store.snapshot("robert")["pantry"] == []


def test_unified_voice_router_updates_and_reads_pantry(tmp_path, monkeypatch):
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "daily-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "food.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setenv("ROXY_HOME_CALENDAR_PATH", str(tmp_path / "calendar.json"))
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer daily-test-key"}

    added = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "Compré dos litros de leche"},
    )
    queried = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "¿Qué hay en la despensa?"},
    )
    daily = client.get("/v1/home-daily/robert", headers=headers)
    spoken_daily = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "¿Qué tengo hoy?"},
    )

    assert added.status_code == 200
    assert added.json()["intent"] == "pantry_add"
    assert queried.json()["intent"] == "pantry_query"
    assert "2 litro de leche" in queried.json()["message"].lower()
    assert daily.status_code == 200
    assert daily.json()["counts"]["pantry"] == 1
    assert spoken_daily.status_code == 200
    assert spoken_daily.json()["intent"] == "daily_query"
    assert spoken_daily.json()["agent"] == "home_daily"
    assert spoken_daily.json()["data"]["daily_brief"]["counts"]["pantry"] == 1


def test_voice_router_recognizes_cooking_from_saved_pantry():
    from tools.roxy_home_service import _assistant_shopping_intent

    assert _assistant_shopping_intent("¿Qué podemos cocinar con lo que hay?") == "weekly_from_pantry"


def test_open_question_uses_private_conversational_brain_and_remembers_context(tmp_path, monkeypatch):
    from tools import roxy_home_service

    class FakeBrain:
        def __init__(self):
            self.calls = []

        def converse(self, prompt, snapshot, *, history, display_name, deep):
            self.calls.append({"prompt": prompt, "snapshot": snapshot, "history": history, "deep": deep})
            return {
                "answer": "Yo elegiría una cena ligera.",
                "reasoning_summary": "Tienes poco tiempo y ya hay pollo en la despensa.",
                "recommendation": "Haz un bowl de pollo y vegetales.",
                "follow_up": "¿Quieres que adapte una receta?",
                "confidence": "high",
                "model_profile": "terra" if deep else "luna",
            }

    brain = FakeBrain()
    monkeypatch.setenv("ROXY_HOME_API_KEY", "conversation-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(tmp_path / "food.json"))
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.setenv("ROXY_HOME_CALENDAR_PATH", str(tmp_path / "calendar.json"))
    monkeypatch.setenv("ROXY_HOME_CONVERSATION_PATH", str(tmp_path / "conversation.json"))
    monkeypatch.setattr(roxy_home_service, "_home_ai", lambda: brain)
    roxy_home_service._RATE_STATE.clear()
    roxy_home_service._home_food_store().upsert_pantry(
        "robert", [{"name": "Pollo", "quantity": 1, "unit": "paquete"}]
    )
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer conversation-test-key"}

    first = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "¿Qué cena me recomiendas y por qué?"},
    )
    second = client.post(
        "/v1/assistant/command/robert",
        headers=headers,
        json={"text": "¿Y si quiero algo más rápido?"},
    )

    assert first.status_code == 200
    assert first.json()["intent"] == "general"
    assert first.json()["agent"] == "home_ai"
    assert first.json()["message"].startswith("Yo elegiría")
    assert first.json()["data"]["conversation"]["confidence"] == "high"
    assert brain.calls[0]["deep"] is True
    assert brain.calls[0]["snapshot"]["pantry"][0]["name"] == "Pollo"
    assert second.status_code == 200
    assert brain.calls[1]["history"][-2]["content"] == "¿Qué cena me recomiendas y por qué?"
