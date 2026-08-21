from pathlib import Path

from fastapi.testclient import TestClient

from roxy_os.home_food import HomeFoodStore
from roxy_os.home_recipe_videos import (
    FalHailuoVideoProvider,
    HomeRecipeVideoConfig,
    HomeRecipeVideoStore,
    recipe_fingerprint,
)


def sample_recipe(title="Pan casero"):
    return {
        "title": title,
        "description": "Pan familiar",
        "kind": "bread",
        "servings": 4,
        "ingredients": [
            {"name": "Harina", "quantity": 500, "unit": "gramo", "notes": ""},
            {"name": "Agua", "quantity": 325, "unit": "mililitro", "notes": "tibia"},
        ],
        "steps": ["Mezcla y amasa.", "Deja crecer.", "Hornea hasta dorar."],
        "favorite": True,
        "user_notes": "La receta de Robert",
        "photo_data_url": "data:image/png;base64,aGVsbG8=",
    }


def video_config(tmp_path):
    return HomeRecipeVideoConfig(
        enabled=True,
        api_key="home-fal-secret",
        clip_count=3,
        clip_seconds=6,
        price_per_second_usd=0.045,
        monthly_budget_usd=20,
        max_recipe_cost_usd=1,
        media_dir=tmp_path / "media",
        admin_key="review-secret",
    )


def test_recipe_fingerprint_excludes_private_personalization():
    first = sample_recipe()
    second = {**sample_recipe(), "favorite": False, "user_notes": "Otro hogar", "photo_data_url": ""}
    changed = sample_recipe()
    changed["ingredients"] = [{**changed["ingredients"][0], "quantity": 600}]

    assert recipe_fingerprint(first) == recipe_fingerprint(second)
    assert recipe_fingerprint(first) != recipe_fingerprint(changed)


def test_video_prompts_require_a_visible_instructional_action(tmp_path):
    store = HomeRecipeVideoStore(tmp_path / "library.json")
    recipe = sample_recipe()
    recipe["steps"][0] = "Mezcla la harina con la levadura y la sal."

    created, reused = store.create_or_reuse("robert", recipe, video_config(tmp_path), visibility="shared")
    prompt = created["clips"][0]["prompt"]

    assert reused is False
    assert "poured one by one" in prompt
    assert "actively stirring" in prompt
    assert "not merely show ingredients or finished food" in prompt
    assert "No static hero shot" in prompt
    assert "Harina" in prompt


def test_new_prompt_version_does_not_reuse_old_decorative_video(tmp_path):
    store = HomeRecipeVideoStore(tmp_path / "library.json")
    recipe = sample_recipe()
    created, _ = store.create_or_reuse("robert", recipe, video_config(tmp_path), visibility="shared")
    store.update(created["id"], lambda row: row.update(prompt_version=1, status="READY"))

    assert store.find_for_recipe("robert", recipe) is None
    regenerated, reused = store.create_or_reuse("robert", recipe, video_config(tmp_path), visibility="shared")

    assert reused is False
    assert regenerated["id"] != created["id"]
    assert regenerated["prompt_version"] == 2


def test_provider_does_not_replace_instructional_choreography(tmp_path):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"request_id": "request-1"}

    class Session:
        def post(self, _url, **kwargs):
            captured.update(kwargs)
            return Response()

    FalHailuoVideoProvider(video_config(tmp_path), session=Session()).submit("show hands mixing")

    assert captured["json"]["prompt_optimizer"] is False


def test_shared_video_is_generated_once_then_reused_without_leaking_owner(tmp_path):
    store = HomeRecipeVideoStore(tmp_path / "library.json")
    config = video_config(tmp_path)
    recipe = sample_recipe()

    created, reused = store.create_or_reuse("robert", recipe, config, visibility="shared")
    duplicate, duplicate_reused = store.create_or_reuse("alice", recipe, config, visibility="shared")

    assert reused is False
    assert duplicate_reused is True
    assert duplicate["id"] == created["id"]
    assert store.find_for_recipe("alice", recipe) is None
    assert "owner_user_id" not in store.find_for_recipe("robert", recipe)
    assert "prompt" not in store.find_for_recipe("robert", recipe)["clips"][0]

    def ready_for_review(row):
        row["status"] = "REVIEW"
        for index, clip in enumerate(row["clips"]):
            path = config.media_dir / row["id"] / f"clip-{index + 1}.mp4"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"video")
            clip.update(status="COMPLETED", media_path=str(path.resolve()), bytes=5)

    store.update(created["id"], ready_for_review)
    assert store.find_for_recipe("alice", recipe) is None
    store.approve(created["id"], approved=True, notes="Pasos verificados")
    public = store.find_for_recipe("alice", recipe)

    assert public["status"] == "READY"
    assert public["visibility"] == "shared"
    assert public["can_preview"] is True
    assert public["clips"][0]["playback_url"].startswith("/v1/home-food/alice/")


def test_household_video_never_becomes_visible_to_another_household(tmp_path):
    store = HomeRecipeVideoStore(tmp_path / "library.json")
    config = video_config(tmp_path)
    recipe = sample_recipe()
    created, _ = store.create_or_reuse("robert", recipe, config, visibility="household")

    store.update(created["id"], lambda row: row.update(status="REVIEW"))
    store.approve(created["id"], approved=True)

    assert store.find_for_recipe("robert", recipe)["status"] == "READY"
    assert store.find_for_recipe("alice", recipe) is None


def test_public_config_never_exposes_provider_or_admin_secrets(tmp_path):
    public = video_config(tmp_path).public_status()

    assert public["enabled"] is True
    assert public["state"] == "ready"
    assert public["estimated_recipe_cost_usd"] == 0.81
    assert "home-fal-secret" not in str(public)
    assert "review-secret" not in str(public)


def test_public_config_explains_why_video_is_not_ready(tmp_path):
    config = video_config(tmp_path)
    missing_key = HomeRecipeVideoConfig(**{**config.__dict__, "api_key": ""})
    missing_budget = HomeRecipeVideoConfig(**{**config.__dict__, "monthly_budget_usd": 0})

    assert missing_key.public_status()["state"] == "missing_key"
    assert "clave" in missing_key.public_status()["message"]
    assert missing_budget.public_status()["state"] == "missing_budget"
    assert "presupuesto" in missing_budget.public_status()["message"]


def test_recipe_video_api_requires_confirmation_reuses_and_reviews_before_sharing(tmp_path, monkeypatch):
    from tools import roxy_home_service

    config = video_config(tmp_path)

    class FakeProvider:
        def submit(self, prompt):
            number = abs(hash(prompt))
            return {
                "request_id": f"request-{number}",
                "status_url": f"https://queue.fal.run/status/{number}",
                "response_url": f"https://queue.fal.run/result/{number}",
            }

        def poll(self, _clip):
            return {"status": "COMPLETED", "media_url": "https://v3.fal.media/clip.mp4"}

        def download(self, _url, destination: Path):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"0" * 2_048)
            return destination.stat().st_size

    memory_path = tmp_path / "food.json"
    library_path = tmp_path / "videos.json"
    food = HomeFoodStore(memory_path)
    robert_recipe = food.save_recipe("robert", sample_recipe())
    alice_recipe = food.save_recipe("alice", sample_recipe())

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(memory_path))
    monkeypatch.setenv("ROXY_HOME_VIDEO_LIBRARY_PATH", str(library_path))
    monkeypatch.setattr(roxy_home_service, "_recipe_video_config", lambda: config)
    monkeypatch.setattr(roxy_home_service, "_recipe_video_provider", lambda _config: FakeProvider())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    empty = client.get(f"/v1/home-food/robert/recipes/{robert_recipe['id']}/video", headers=headers)
    blocked = client.post(
        f"/v1/home-food/robert/recipes/{robert_recipe['id']}/video",
        headers=headers,
        json={"visibility": "shared", "confirmed": False},
    )
    created = client.post(
        f"/v1/home-food/robert/recipes/{robert_recipe['id']}/video",
        headers=headers,
        json={"visibility": "shared", "confirmed": True},
    )
    video_id = created.json()["video"]["id"]
    reused = client.post(
        f"/v1/home-food/robert/recipes/{robert_recipe['id']}/video",
        headers=headers,
        json={"visibility": "shared", "confirmed": True},
    )
    synced = client.post(f"/v1/home-food/robert/recipe-videos/{video_id}/sync", headers=headers, json={})
    private_preview = client.get(
        f"/v1/home-food/robert/recipe-videos/{video_id}/clips/0", headers=headers
    )
    hidden_from_alice = client.get(
        f"/v1/home-food/alice/recipe-videos/{video_id}/clips/0", headers=headers
    )
    forbidden_review = client.post(
        f"/v1/home-food/robert/recipe-videos/{video_id}/review",
        headers=headers,
        json={"approved": True, "notes": "revisado"},
    )
    approved = client.post(
        f"/v1/home-food/robert/recipe-videos/{video_id}/review",
        headers={**headers, "X-Roxy-Video-Admin-Key": "review-secret"},
        json={"approved": True, "notes": "revisado"},
    )
    shared = client.get(f"/v1/home-food/alice/recipes/{alice_recipe['id']}/video", headers=headers)
    shared_clip = client.get(
        f"/v1/home-food/alice/recipe-videos/{video_id}/clips/0", headers=headers
    )

    assert empty.json()["video"] is None
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "CONFIRMATION_REQUIRED"
    assert created.status_code == 202
    assert created.json()["status"] == "PROCESSING"
    assert reused.json()["status"] == "REUSED"
    assert synced.json()["status"] == "REVIEW"
    assert private_preview.status_code == 200
    assert hidden_from_alice.status_code == 404
    assert forbidden_review.status_code == 403
    assert approved.json()["status"] == "READY"
    assert shared.json()["video"]["id"] == video_id
    assert shared.json()["video"]["reused"] is False
    assert shared_clip.status_code == 200


def test_starting_recipe_automatically_queues_one_shared_video_for_all_users(tmp_path, monkeypatch):
    from tools import roxy_home_service

    config = video_config(tmp_path)
    submitted = []

    class FakeProvider:
        def submit(self, prompt):
            submitted.append(prompt)
            number = len(submitted)
            return {
                "request_id": f"request-{number}",
                "status_url": f"https://queue.fal.run/status/{number}",
                "response_url": f"https://queue.fal.run/result/{number}",
            }

    memory_path = tmp_path / "food.json"
    library_path = tmp_path / "videos.json"
    food = HomeFoodStore(memory_path)
    robert_recipe = food.save_recipe("robert", sample_recipe())
    alice_recipe = food.save_recipe("alice", sample_recipe())

    monkeypatch.setenv("ROXY_HOME_API_KEY", "home-test-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "robert,alice")
    monkeypatch.setenv("ROXY_HOME_MEMORY_PATH", str(memory_path))
    monkeypatch.setenv("ROXY_HOME_VIDEO_LIBRARY_PATH", str(library_path))
    monkeypatch.setattr(roxy_home_service, "_recipe_video_config", lambda: config)
    monkeypatch.setattr(roxy_home_service, "_recipe_video_provider", lambda _config: FakeProvider())
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    headers = {"Authorization": "Bearer home-test-key"}

    first = client.post(
        f"/v1/home-food/robert/recipes/{robert_recipe['id']}/cooking-sessions",
        headers=headers,
    )
    second = client.post(
        f"/v1/home-food/alice/recipes/{alice_recipe['id']}/cooking-sessions",
        headers=headers,
    )

    assert first.status_code == 201
    assert first.json()["recipe_video_status"] == "QUEUED"
    assert first.json()["recipe_video"]["visibility"] == "shared"
    assert second.status_code == 201
    assert second.json()["recipe_video_status"] == "REUSED"
    assert second.json()["recipe_video"]["id"] == first.json()["recipe_video"]["id"]
    assert len(submitted) == config.clip_count
