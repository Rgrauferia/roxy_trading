from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from roxy_os.home_recipe_photos import RecipePhotoStore, recipe_photo_query


class _Response:
    def __init__(self, *, payload=None, content=b"", content_type="application/json"):
        self._payload = payload
        self.content = content
        self.headers = {"content-type": content_type}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_recipe_photo_query_translates_common_recipe_terms():
    assert "garlic shrimp" in recipe_photo_query("Camarones al ajillo")
    assert "overnight oats" in recipe_photo_query("Avena nocturna con frutas")
    assert "beef steak with onions" in recipe_photo_query("Bistec encebollado")


def test_recipe_photo_store_downloads_real_match_once_and_caches(tmp_path, monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if url.endswith("/v1/images/"):
            return _Response(
                payload={
                    "results": [
                        {
                            "id": "real-shrimp-photo",
                            "title": "Garlic shrimp dinner",
                            "thumbnail": "https://api.openverse.org/v1/images/real-shrimp-photo/thumb/",
                            "creator": "Food photographer",
                            "license": "by",
                            "license_url": "https://creativecommons.org/licenses/by/4.0/",
                            "foreign_landing_url": "https://example.test/photo",
                            "width": 1200,
                            "height": 800,
                            "tags": [{"name": "garlic"}, {"name": "shrimp"}, {"name": "food"}],
                        }
                    ]
                }
            )
        return _Response(content=b"\xff\xd8\xff\xe0real-jpeg", content_type="image/jpeg")

    monkeypatch.setattr("roxy_os.home_recipe_photos.requests.get", fake_get)
    store = RecipePhotoStore(tmp_path)
    first = store.resolve("Camarones al ajillo")
    second = store.resolve("Camarones al ajillo")

    assert first is not None
    assert second is not None
    assert first[0] == second[0]
    assert first[0].read_bytes().startswith(b"\xff\xd8")
    assert first[1]["openverse_id"] == "real-shrimp-photo"
    assert len(calls) == 3


def test_recipe_photo_store_rejects_wrong_protein(tmp_path, monkeypatch):
    def fake_get(url, **kwargs):
        return _Response(
            payload={
                "results": [
                    {
                        "id": "wrong-fish",
                        "title": "Garlic fish dinner",
                        "thumbnail": "https://api.openverse.org/v1/images/wrong-fish/thumb/",
                        "width": 1200,
                        "height": 800,
                        "tags": [{"name": "garlic"}, {"name": "fish"}],
                    }
                ]
            }
        )

    monkeypatch.setattr("roxy_os.home_recipe_photos.requests.get", fake_get)
    assert RecipePhotoStore(tmp_path).resolve("Camarones al ajillo") is None


def test_public_recipe_photo_endpoint_serves_cached_image(tmp_path, monkeypatch):
    from tools import roxy_home_service

    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"\xff\xd8\xff\xe0cached")

    class _Store:
        def resolve(self, title):
            assert title == "Camarones al ajillo"
            return photo, {"media_type": "image/jpeg", "license": "by"}

    monkeypatch.setattr(roxy_home_service, "_recipe_photo_store", lambda: _Store())
    roxy_home_service._RATE_STATE.clear()
    response = TestClient(roxy_home_service.app).get(
        "/v1/home-food/recipe-photo", params={"title": "Camarones al ajillo"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.headers["x-roxy-photo-source"] == "Openverse"
    assert response.content.startswith(b"\xff\xd8")
