from __future__ import annotations

from roxy_academy_knowledge import (
    ADVANCED_ORIGIN_TERMS,
    academy_planet_knowledge,
    enrich_academy_lesson,
    planet_curriculum_lessons,
)


def test_origin_profile_stays_beginner_safe() -> None:
    context = academy_planet_knowledge(
        "origen",
        "Que es el trading?",
        "El trading es comprar y vender activos financieros.",
    )
    text = " ".join(context["points"] + context["practice"]).lower()
    assert "activo" in text or "activos" in text
    assert "riesgo" in text
    assert not any(term in text for term in ADVANCED_ORIGIN_TERMS)


def test_planet_profiles_are_different() -> None:
    origin = academy_planet_knowledge("origen")
    crypto = academy_planet_knowledge("cripto")
    analysis = academy_planet_knowledge("analisis")
    assert origin["role"] != crypto["role"]
    assert "crypto" in crypto["query"].lower() or "cryptocurrency" in crypto["query"].lower()
    assert "chart" in analysis["query"].lower() or "candlestick" in analysis["query"].lower()


def test_enrich_lesson_preserves_quiz_and_adds_context() -> None:
    lesson = {
        "id": "sample",
        "title": "Que es comprar?",
        "explanation": "Comprar es adquirir un activo.",
        "study": "Meta basica.",
        "mission": "Explicalo simple.",
        "question": "Que es comprar?",
        "options": ("Adquirir un activo.", "Adivinar.", "Ignorar riesgo."),
        "answer": 0,
    }
    enriched = enrich_academy_lesson("origen", lesson)
    assert enriched["answer"] == lesson["answer"]
    assert enriched["options"] == lesson["options"]
    assert enriched["knowledge_context"]["planet"] == "origen"
    assert len(enriched["deep_points"]) >= 3
    assert len(enriched["practice_steps"]) >= 3


def test_each_planet_has_its_own_curriculum() -> None:
    crypto_lessons = planet_curriculum_lessons("cripto")
    analysis_lessons = planet_curriculum_lessons("analisis")
    strategy_lessons = planet_curriculum_lessons("estrategia")
    assert any("blockchain" in item.lower() for item in crypto_lessons)
    assert any("velas" in item.lower() or "grafico" in item.lower() for item in analysis_lessons)
    assert any("stop" in item.lower() or "riesgo" in item.lower() for item in strategy_lessons)
    assert crypto_lessons != analysis_lessons
