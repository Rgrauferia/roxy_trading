"""Saving a recipe must neither shorten instructions nor invent missing measures."""
from copy import deepcopy

import pytest

from roxy_os.home_food import HomeFoodStore


def original():
    return {"title": "Original de prueba de conservación", "servings": 2,
            "ingredients": [{"name": "Ingrediente de prueba", "quantity": 2, "unit": "taza", "notes": "Nota original " * 30}],
            "steps": ["Párrafo original largo. " * 30, "Acción que se repite", "Acción que se repite"]}


def test_long_steps_and_repetition_survive_save_reload_and_guided_reading(tmp_path):
    path = tmp_path / "home.json"
    store = HomeFoodStore(path)
    source = original()
    saved = store.save_recipe("qa", source)
    expected = [step.strip() for step in source["steps"]]
    assert saved["steps"] == expected
    assert saved["ingredients"][0]["notes"] == source["ingredients"][0]["notes"].strip()
    restarted = HomeFoodStore(path)
    assert restarted.get_recipe("qa", saved["id"])["steps"] == expected
    session = restarted.start_cooking_session("qa", saved["id"])
    for step in expected:
        assert restarted.cooking_session_detail("qa", session["id"])["current_step"] == step
        restarted.update_cooking_session("qa", session["id"], "next")
    assert restarted.snapshot("other")["recipes"] == []


@pytest.mark.parametrize("field", ["servings", "quantity", "unit"])
def test_missing_original_measure_is_rejected_without_default_or_mutation(tmp_path, field):
    store = HomeFoodStore(tmp_path / "home.json")
    store.save_recipe("qa", original())
    before = store.snapshot("qa")
    incomplete = deepcopy(original())
    del (incomplete if field == "servings" else incomplete["ingredients"][0])[field]
    with pytest.raises(ValueError):
        store.save_recipe("qa", incomplete)
    assert store.snapshot("qa") == before


@pytest.mark.parametrize("steps", [[], "not a list", [None], [""], ["x" * 4001], ["x"] * 101, ["x" * 4000] * 21])
def test_malformed_or_oversize_steps_are_rejected_instead_of_silently_shortened(tmp_path, steps):
    store = HomeFoodStore(tmp_path / "home.json")
    before = store.snapshot("qa")
    with pytest.raises(ValueError, match="no se ha recortado"):
        store.save_recipe("qa", {**original(), "steps": steps})
    assert store.snapshot("qa") == before
