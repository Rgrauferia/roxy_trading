import pytest
from tools.roxy_home_service import _assistant_shopping_intent


@pytest.mark.parametrize("text", [
    "Explícame cómo me acompañas paso a paso al cocinar, sin cambiar mi lista ni mi plan.",
    "Cuéntame cómo funciona la guía para cocinar paso a paso.",
    "¿Qué puedes hacer para agregar ingredientes?",
    "Hola Roxy. ¿Qué puedo hacer contigo? Sólo quiero información.",
])
def test_capability_questions_do_not_authorize_mutations(text):
    assert _assistant_shopping_intent(text) == "general"


@pytest.mark.parametrize("text,intent", [
    ("Guíame paso a paso", "cooking_start"),
    ("Quiero cocinar paso a paso", "cooking_start"),
    ("Dame una receta de pasta", "recipe_generate"),
    ("Agrega leche", "shopping_add"),
    ("Pon un temporizador de 5 minutos", "cooking_timer_set"),
])
def test_explicit_actions_keep_existing_routes(text, intent):
    assert _assistant_shopping_intent(text) == intent
