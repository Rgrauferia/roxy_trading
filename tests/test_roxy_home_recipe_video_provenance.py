"""Recipe media cannot bypass editorial/source review through old API URLs."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from roxy_os.home_food import HomeFoodStore
from roxy_os.home_recipe_fallback import local_recipe_by_key
from roxy_os.home_recipe_videos import HomeRecipeVideoConfig, HomeRecipeVideoStore
from tools import roxy_home_service as service


USER = "video_qa"
BASE = f"/v1/home-food/{USER}"


@pytest.fixture
def qa(tmp_path, monkeypatch):
    food = HomeFoodStore(tmp_path / "food.json")
    videos = HomeRecipeVideoStore(tmp_path / "videos.json")
    config = HomeRecipeVideoConfig(enabled=True, api_key="synthetic-video-key", clip_count=1,
        clip_seconds=6, price_per_clip_usd=0.5, monthly_budget_usd=20, max_recipe_cost_usd=1.5,
        media_dir=tmp_path / "media", admin_key="synthetic-review-key",
        roxy_reference_url="https://example.org/roxy.jpg")
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-video-api-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", USER)
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.setattr(service, "_home_food_store", lambda: food)
    monkeypatch.setattr(service, "_recipe_video_store", lambda: videos)
    monkeypatch.setattr(service, "_recipe_video_config", lambda: config)
    monkeypatch.setattr(service, "_recipe_video_public_status", lambda: {})
    monkeypatch.setattr(service, "_recipe_video_provider", lambda *a: pytest.fail("Unexpected video generation/polling"))
    monkeypatch.setattr("requests.get", lambda *a, **k: pytest.fail("Unexpected network call"))
    monkeypatch.setattr("requests.post", lambda *a, **k: pytest.fail("Unexpected network call"))
    service._RATE_STATE.clear()
    client = TestClient(service.app, base_url="https://video.test")
    client.headers["Authorization"] = "Bearer synthetic-video-api-key"
    yield SimpleNamespace(food=food, videos=videos, config=config, client=client, root=tmp_path)
    client.close()


def save_recipe(qa, kind):
    if kind == "pet":
        pet = qa.food.upsert_pet(USER, name="Synthetic Luna", species="ferret", life_stage="adult")
        raw = {**local_recipe_by_key("ferret_turkey_medallions", {}), "pet_id": pet["id"]}
    else:
        raw = {"title": "Synthetic reviewed human recipe", "kind": "meal", "audience": "human",
               "generation_source": "import_text", "servings": 1,
               "ingredients": [{"name": "Synthetic ingredient", "quantity": 1, "unit": "test unit"}],
               "steps": ["Synthetic original instruction, not a feeding recommendation."],
               "editorial_status": "needs_canonical_review" if kind == "draft" else "reviewed"}
    saved = qa.food.save_recipe(USER, raw)
    return qa.food.get_recipe(USER, saved["id"])


def prepare_media(qa, recipe, status="READY", visibility="household"):
    video, _ = qa.videos.create_or_reuse(USER, recipe, qa.config, visibility=visibility)
    path = qa.root / "media" / "synthetic-clip.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic video fixture")
    def set_media(row):
        row["status"] = status
        for clip in row["clips"]:
            clip.update(media_path=str(path), status="COMPLETED")
    return qa.videos.update(video["id"], set_media)


def stored_bytes(qa):
    return {path.name: path.read_bytes() for path in (qa.food.path, qa.videos.path) if path.exists()}


@pytest.mark.parametrize("kind", ["pet", "draft"])
@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("existing", [False, True])
def test_recipe_video_source_gate_runs_before_lookup_reuse_or_generation(qa, monkeypatch, kind, method, existing):
    recipe = save_recipe(qa, kind)
    if existing:
        prepare_media(qa, recipe)
    before = stored_bytes(qa)
    monkeypatch.setattr(qa.videos, "find_for_recipe", lambda *a: pytest.fail("Review gate must precede video lookup"))
    monkeypatch.setattr(qa.videos, "create_or_reuse", lambda *a, **k: pytest.fail("Blocked recipe created media"))
    response = qa.client.request(method, f"{BASE}/recipes/{recipe['id']}/video", **({"json": {"confirmed": True}} if method == "POST" else {}))
    assert response.status_code == 422
    assert "original" in response.json()["detail"]
    assert stored_bytes(qa) == before


@pytest.mark.parametrize("kind", ["pet", "draft"])
@pytest.mark.parametrize("operation", ["sync", "clip", "approve"])
def test_old_video_urls_cannot_play_poll_or_approve_quarantined_recipes(qa, kind, operation):
    recipe = save_recipe(qa, kind)
    video = prepare_media(qa, recipe, status="REVIEW" if operation == "approve" else "PROCESSING")
    before = stored_bytes(qa)
    base = f"{BASE}/recipe-videos/{video['id']}"
    if operation == "clip":
        response = qa.client.get(base + "/clips/0")
    elif operation == "approve":
        response = qa.client.post(base + "/review", json={"approved": True}, headers={"X-Roxy-Video-Admin-Key": qa.config.admin_key})
    else:
        response = qa.client.post(base + "/sync")
    assert response.status_code == 422
    assert "original" in response.json()["detail"]
    assert stored_bytes(qa) == before


def test_reviewed_human_recipe_media_remains_available_without_new_generation(qa):
    recipe = save_recipe(qa, "reviewed")
    video = prepare_media(qa, recipe)
    before = stored_bytes(qa)
    recipe_url = f"{BASE}/recipes/{recipe['id']}/video"
    video_url = f"{BASE}/recipe-videos/{video['id']}"
    assert qa.client.get(recipe_url).json()["status"] == "READY"
    assert qa.client.post(recipe_url, json={"confirmed": False}).json()["status"] == "REUSED"
    assert qa.client.post(video_url + "/sync").json()["status"] == "READY"
    clip = qa.client.get(video_url + "/clips/0")
    assert clip.status_code == 200 and clip.content == b"synthetic video fixture"
    assert stored_bytes(qa) == before


def test_changed_recipe_video_fails_closed_without_erasing_existing_media(qa):
    recipe = save_recipe(qa, "reviewed")
    video = prepare_media(qa, recipe)
    qa.food._mutate(lambda data: data["users"][USER]["recipes"][0].update(steps=["Changed preparation."]))
    before = stored_bytes(qa)
    response = qa.client.get(f"{BASE}/recipe-videos/{video['id']}/clips/0")
    assert response.status_code == 422 and "vigente" in response.json()["detail"]
    assert stored_bytes(qa) == before


def test_shared_video_needs_current_matching_recipe_in_requesting_home(qa, monkeypatch):
    recipe = save_recipe(qa, "reviewed")
    video = prepare_media(qa, recipe, visibility="shared")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", USER + ",other_video_home")
    before = stored_bytes(qa)
    response = qa.client.get(f"/v1/home-food/other_video_home/recipe-videos/{video['id']}/clips/0")
    assert response.status_code == 422
    assert stored_bytes(qa) == before
    qa.food.save_recipe("other_video_home", recipe)
    assert qa.client.get(f"/v1/home-food/other_video_home/recipe-videos/{video['id']}/clips/0").status_code == 200


def test_admin_can_reject_unverified_media_without_reactivating_it(qa):
    video = prepare_media(qa, save_recipe(qa, "pet"), status="REVIEW")
    response = qa.client.post(f"{BASE}/recipe-videos/{video['id']}/review", json={"approved": False},
                              headers={"X-Roxy-Video-Admin-Key": qa.config.admin_key})
    assert response.status_code == 200 and response.json()["status"] == "REJECTED"


@pytest.mark.parametrize("visibility", ["household", "shared"])
def test_video_playback_cannot_cache_around_current_household_eligibility(qa, visibility):
    video = prepare_media(qa, save_recipe(qa, "reviewed"), visibility=visibility)
    response = qa.client.get(f"{BASE}/recipe-videos/{video['id']}/clips/0")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"


def test_admin_can_reject_an_orphaned_video_without_a_current_recipe(qa):
    recipe = save_recipe(qa, "reviewed")
    video = prepare_media(qa, recipe, status="REVIEW")
    qa.food.delete_recipe(USER, recipe["id"])
    response = qa.client.post(f"{BASE}/recipe-videos/{video['id']}/review", json={"approved": False},
                              headers={"X-Roxy-Video-Admin-Key": qa.config.admin_key})
    assert response.status_code == 200 and response.json()["status"] == "REJECTED"


def test_server_owned_action_pilots_remain_reviewable_without_a_recipe(qa):
    path = qa.root / "media" / "pilot.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic pilot")
    video = qa.videos.register_action_pilot(USER, [{"action_key": "mix_dry", "media_path": str(path)}],
        provider="synthetic", model="synthetic", estimated_cost_usd=0)
    response = qa.client.post(f"{BASE}/recipe-videos/{video['id']}/review", json={"approved": True},
                              headers={"X-Roxy-Video-Admin-Key": qa.config.admin_key})
    assert response.status_code == 200 and response.json()["status"] == "READY"
    assert qa.client.get(f"{BASE}/recipe-videos/{video['id']}/clips/0").status_code == 200
