from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from roxy_os.home_recipe_photos import RecipePhotoStore, recipe_photo_prompt


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
