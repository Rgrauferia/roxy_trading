"""Duration suggestions retain source meaning; no real timers are created."""

import pytest

from roxy_os.home_food import cooking_step_timer_seconds


@pytest.mark.parametrize("text, seconds", [
    ("Deja reposar 30 minutos mientras calientas el horno a 220 °C.", 1800),
    ("Hornea 1 hora y 15 minutos.", 4500),
    ("Espera 1 hora 15 minutos 30 segundos.", 4530),
    ("Espera 2 h y 5 min y 10 s.", 7510),
    ("Cocina 1.5 minutos.", 90),
    ("Cocina 1,5 minutos.", 90),
    ("Espera 0,5 horas.", 1800),
    ("Espera 15seg.", 15),
    ("Espera 10min.", 600),
    ("Mezcla 1/2 taza de agua y deja reposar 5 minutos.", 300),
    ("Calienta hasta que hierva. Reposa 5 minutos.", 300),
    ("Conserva durante 24 horas.", 86400),
])
def test_single_literal_duration_or_contiguous_compound(text, seconds):
    assert cooking_step_timer_seconds(text) == seconds


@pytest.mark.parametrize("text", [
    "Cocina 2–3 minutos.", "Cocina 2 – 3 minutos.",
    "Cocina 2—3 minutos.", "Cocina 2-3 minutos.", "Cocina 2 - 3 minutos.",
    "Cocina de 2 a 3 minutos.", "Cocina entre 2 y 3 minutos.",
    "Cocina 2 o 3 minutos.", "Cocina 2 hasta 3 minutos.",
    "Cocina 2 minutos a 3 minutos.", "Espera 1 hora o 15 minutos.",
    "Cocina 1/2 minuto.", "Cocina 1 / 2 minuto.", "Cocina ½ minuto.",
    "Cocina 1½ minutos.", "Cocina 1⁄2 minuto y luego 5 segundos.",
    "Cocina media hora y luego 5 minutos.", "Cocina 1 hora y media.",
    "Cocina 2 minutos; voltea y cocina 1 minuto más.",
    "Hornea 1 hora. Reposa 15 minutos.",
    "Hornea 1 hora y reposa 15 minutos.",
    "Hornea 15 minutos y 1 hora.",
    "Cocina unos 5 minutos.", "Espera aproximadamente 5 minutos.",
    "Espera aprox. 5 minutos.", "Espera al menos 5 minutos.",
    "Espera hasta 5 minutos.", "Espera más de 5 minutos.",
    "Revisa cada 5 minutos.", "Cocina 5 minutos por lado.",
    "Cocina 5 minutos más.", "Cocina -5 minutos.", "Cocina − 5 minutos.",
    "Espera > 5 minutos.", "Espera 0 minutos.",
    "Espera 24 horas y 1 segundo.", "Espera 999999999999999999999 horas.",
    "Mezcla hasta formar una masa uniforme.", "", None,
])
def test_ambiguous_or_unsupported_duration_requires_manual_choice(text):
    assert cooking_step_timer_seconds(text) == 0


@pytest.mark.parametrize("key, index", [
    ("pancakes", 3), ("brownies", 4), ("cookies", 3),
    ("manhattan", 0), ("chicken", 2), ("bread", 3),
])
def test_existing_local_recipe_ranges_never_turn_into_concatenated_numbers(key, index):
    from roxy_os.home_recipe_fallback import local_recipe_by_key

    original = local_recipe_by_key(key, {})["steps"][index]
    assert "–" in original
    assert cooking_step_timer_seconds(original) == 0
    assert local_recipe_by_key(key, {})["steps"][index] == original


def test_exact_pancakes_source_never_becomes_a_35_minute_timer():
    source = (
        "Cocina unos 2–3 minutos hasta que los bordes estén firmes y aparezcan burbujas. "
        "Voltea con una espátula y cocina 1–2 minutos más."
    )
    assert cooking_step_timer_seconds(source) == 0


def test_session_response_clears_suggestion_on_range_without_altering_recipe_or_starting_a_timer(tmp_path):
    from roxy_os.home_food import HomeFoodStore
    from roxy_os.home_recipe_fallback import local_recipe_by_key

    store = HomeFoodStore(tmp_path / "synthetic-home.json")
    original = local_recipe_by_key("pancakes", {})
    recipe = store.save_recipe("timer-fixture", original)
    session = store.start_cooking_session("timer-fixture", recipe["id"])
    assert store.cooking_session_detail("timer-fixture", session["id"])["suggested_timer_seconds"] == 300
    for _ in range(3):
        store.update_cooking_session("timer-fixture", session["id"], "next")
    view = store.cooking_session_detail("timer-fixture", session["id"])
    assert view["step_number"] == 4
    assert view["suggested_timer_seconds"] == 0
    assert view["current_step"] == original["steps"][3]
    assert view["recipe"]["steps"] == original["steps"]
    assert view["session"].get("timers", []) == []
