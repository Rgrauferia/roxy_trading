from __future__ import annotations

import base64
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from roxy_os.home_recipe_photos import (
    RecipePhotoGenerationConfig,
    RecipePhotoGenerationQueue,
    RecipePhotoStore,
    recipe_photo_prompt,
)


def test_recipe_photo_prompt_names_exact_dish_and_ingredients():
    prompt = recipe_photo_prompt(
        {"title": "Camarones al ajillo", "ingredients": [{"name": "Camarones"}, {"name": "Ajo"}]}
    )
    assert "Camarones al ajillo" in prompt
    assert "Camarones, Ajo" in prompt
    assert "prepared final result" in prompt
    assert "not a generic category platter" in prompt
    assert "no text" in prompt


def test_recipe_photo_prompt_distinguishes_cuban_bread():
    prompt = recipe_photo_prompt({"title": "Pan cubano"})
    assert "traditional Cuban bread" in prompt
    assert "not brioche" in prompt
    assert "not a soft sandwich loaf" in prompt


def test_store_never_searches_or_returns_a_generic_fallback(tmp_path):
    store = RecipePhotoStore(tmp_path, built_in_root=tmp_path / "built-ins")
    assert store.resolve("Camarones al ajillo") is None
    assert list(tmp_path.iterdir()) == []


def test_store_serves_only_exact_built_in_title(tmp_path):
    built_ins = tmp_path / "built-ins"
    built_ins.mkdir()
    photo = built_ins / "pan-cubano.jpg"
    photo.write_bytes(b"exact-cuban-bread")
    store = RecipePhotoStore(tmp_path / "generated", built_in_root=built_ins)
    exact = store.resolve("Pan cubano")
    assert exact is not None and exact[0] == photo
    assert store.resolve("Pan blanco") is None


def test_generated_photo_requires_approval_and_exact_title(tmp_path):
    png = b"\x89PNG\r\n\x1a\ncustom"
    store = RecipePhotoStore(tmp_path, built_in_root=tmp_path / "built-ins")
    store.save_generated("Pollo al ajo", base64.b64encode(png).decode("ascii"))
    assert store.resolve("Pollo al ajo") is None
    assert store.approve("Pollo al ajo") is True
    assert store.resolve("Pollo al ajo") is not None
    assert store.resolve("Pollo al ajo con arroz") is None


def test_generation_queue_creates_and_approves_exact_image_once(tmp_path):
    png = b"\x89PNG\r\n\x1a\ncustom"

    class _Responses:
        calls = 0

        def create(self, **kwargs):
            self.calls += 1
            assert "Pollo al ajo" in kwargs["input"]
            assert kwargs["tools"][0]["type"] == "image_generation"
            return SimpleNamespace(
                output=[SimpleNamespace(type="image_generation_call", result=base64.b64encode(png).decode("ascii"))]
            )

    responses = _Responses()
    client = SimpleNamespace(responses=responses)
    store = RecipePhotoStore(tmp_path, built_in_root=tmp_path / "built-ins")
    queue = RecipePhotoGenerationQueue(
        store,
        RecipePhotoGenerationConfig(api_key="home-only", enabled=True, daily_limit=2),
        client=client,
    )
    recipe = {"title": "Pollo al ajo", "ingredients": [{"name": "Pollo"}, {"name": "Ajo"}]}
    assert queue.schedule(recipe) == "PENDING"
    for _ in range(50):
        if store.resolve("Pollo al ajo"):
            break
        time.sleep(.01)
    assert store.resolve("Pollo al ajo") is not None
    assert queue.schedule(recipe) == "READY"
    assert responses.calls == 1
    assert queue.public_status()["generated_today"] == 1


def test_missing_catalog_photo_endpoint_starts_generation(monkeypatch):
    from tools import roxy_home_service

    class _MissingStore:
        def resolve(self, title):
            return None

    class _Queue:
        def schedule(self, recipe):
            assert recipe["title"] == "Camarones al ajillo"
            return "PENDING"

    monkeypatch.setattr(roxy_home_service, "_recipe_photo_store", lambda: _MissingStore())
    monkeypatch.setattr(roxy_home_service, "_recipe_photo_queue", lambda: _Queue())
    roxy_home_service._RATE_STATE.clear()
    response = TestClient(roxy_home_service.app).get(
        "/v1/home-food/recipe-photo", params={"title": "Camarones al ajillo"}
    )
    assert response.status_code == 202
    assert response.headers["retry-after"] == "5"
    assert response.json()["status"] == "GENERATING"


def test_public_recipe_photo_endpoint_serves_roxy_image(tmp_path, monkeypatch):
    from tools import roxy_home_service

    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xe0custom")

    class _Store:
        def resolve(self, title):
            assert title == "Café americano"
            return photo, {"media_type": "image/jpeg", "provider": "Roxy Home"}

    monkeypatch.setattr(roxy_home_service, "_recipe_photo_store", lambda: _Store())
    roxy_home_service._RATE_STATE.clear()
    response = TestClient(roxy_home_service.app).get(
        "/v1/home-food/recipe-photo", params={"title": "Café americano"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.headers["x-roxy-photo-source"] == "Roxy Home"
    assert response.content.startswith(b"\xff\xd8")
