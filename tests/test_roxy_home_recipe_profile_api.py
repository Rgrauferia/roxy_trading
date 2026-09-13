"""Synthetic members only; private preferences never go to recipe providers."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_demo import trial_access_mode
from tools import roxy_home_service as service


def profile(**changes):
    return {"schema_version": 1, "completed": True, "consent": True, "language": "es",
            "country_of_origin": "Cuba", "cuisine_mode": "mixed", "cuisines": [],
            "favorite_foods": ["pasta"], "diet": "omnivore", "allergy_status": "listed",
            "allergies": ["milk"], "other_allergies": "", "dislikes": [],
            "max_minutes": None, "skill": "beginner", **changes}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-recipe-profile-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "private-profile-test")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    store = HomeAccountStore(tmp_path / "accounts.json")
    a = store.bootstrap("private-profile-test", household_name="Test household", username="profile-a",
                        display_name="Test A", password="Synthetic-Test-2026")
    b = store.add_member(a["id"], username="profile-b", display_name="Test B", password="Synthetic-Test-2026")
    client = TestClient(service.app, base_url="https://profile.test")
    client.post("/v1/home-account/login", json={"username": "profile-a", "password": "Synthetic-Test-2026"})
    return client, store, a, b


def headers(member):
    return {"X-Roxy-Recipe-Member": member["id"], "Origin": "https://profile.test"}


def save(client, member, **overrides):
    return client.put("/v1/home-account/recipe-profile", headers=headers(member),
                      json={"member_id": member["id"], "expected_revision": 0, "profile": profile(), **overrides})


def test_new_member_profile_roundtrip_private_and_discovery(setup):
    client, store, a, b = setup
    initial = client.get("/v1/home-account/recipe-profile", headers=headers(a))
    assert initial.status_code == 200
    assert initial.json()["required"] is True
    assert initial.json()["profile"] is None
    assert initial.json()["revision"] == 0
    result = save(client, a)
    assert result.status_code == 200
    data = result.json()
    assert data["profile"] == profile()
    assert data["required"] is False
    assert data["revision"] == 1
    assert any(row["query"] == "pasta" for row in data["discovery"]["presets"])
    assert "no-store" in result.headers["cache-control"]
    assert store.get_recipe_profile(b["id"])["profile"] is None
    for path in ("/v1/home-account/me", "/v1/home-account/members"):
        public = client.get(path)
        assert public.status_code == 200
        assert "Cuba" not in public.text
        assert '"allergies"' not in public.text


@pytest.mark.parametrize("request_headers", [{}, {"X-Roxy-Recipe-Member": "another-member"}])
def test_read_binding_required(setup, request_headers):
    client, _, _, _ = setup
    assert client.get("/v1/home-account/recipe-profile", headers=request_headers).status_code == 409


def test_write_binding_origin_revision_and_validation(setup):
    client, store, a, b = setup
    body = {"member_id": a["id"], "expected_revision": 0, "profile": profile()}
    assert client.put("/v1/home-account/recipe-profile", json=body, headers={"X-Roxy-Recipe-Member": a["id"]}).status_code == 403
    assert save(client, a, member_id=b["id"]).status_code == 409
    assert save(client, a, expected_revision=True).status_code == 422
    assert save(client, a, profile=profile(consent=False)).status_code == 422
    assert store.get_recipe_profile(a["id"])["revision"] == 0
    assert save(client, a).status_code == 200
    assert save(client, a).status_code == 409
    assert store.get_recipe_profile(a["id"])["revision"] == 1


def test_other_login_cannot_read_old_members_profile(setup):
    client, _, a, b = setup
    assert save(client, a).status_code == 200
    client.post("/v1/home-account/login", json={"username": "profile-b", "password": "Synthetic-Test-2026"})
    assert client.get("/v1/home-account/recipe-profile", headers=headers(a)).status_code == 409
    result = client.get("/v1/home-account/recipe-profile", headers=headers(b)).json()
    assert result["profile"] is None


def test_myplate_private_assessment_never_passes_preferences_to_provider(setup, monkeypatch):
    client, _, a, _ = setup
    assert save(client, a).status_code == 200
    calls = []
    original = {"recipe": {"title": "Synthetic source", "ingredients": [{"text": "1 cup milk", "note": None}]}}
    def upstream(slug):
        calls.append(slug)
        return deepcopy(original)
    monkeypatch.setattr(service.myplate_recipes, "get_recipe", upstream)
    path = "/v1/home-food/private-profile-test/myplate-recipes/synthetic?requested=true"
    result = client.get(path, headers=headers(a))
    assert result.status_code == 200
    assert result.json()["recipe"]["personal_fit"]["status"] == "conflict"
    assert calls == ["synthetic"]
    assert "personal_fit" not in original["recipe"]
    legacy = client.get(path)
    assert legacy.status_code == 200
    assert "personal_fit" not in legacy.json()["recipe"]
    assert client.get(path, headers={"X-Roxy-Recipe-Member": "wrong"}).status_code == 409
    assert calls == ["synthetic", "synthetic"]


def test_profile_read_and_save_are_free_local_demo_operations():
    assert trial_access_mode("GET", "/v1/home-account/recipe-profile") == "local"
    assert trial_access_mode("PUT", "/v1/home-account/recipe-profile") == "local"
    assert trial_access_mode("POST", "/v1/home-account/recipe-profile") == "unavailable"


def test_catalog_hides_obvious_conflicts_without_leaking_profile_or_inventing_totals(setup, monkeypatch):
    client, _, a, _ = setup
    assert save(client, a, profile=profile(diet="vegetarian")).status_code == 200
    source = {"recipes": [{"slug": "steak-salad", "title": "Italian Steak Salad", "description": "Test"},
                          {"slug": "bean-soup", "title": "Italian Bean Soup", "description": "Test"}],
              "total": 30, "offset": 0, "limit": 24, "next_offset": 24}
    calls = []
    def upstream(**kwargs):
        calls.append(kwargs)
        return deepcopy(source)
    monkeypatch.setattr(service.myplate_recipes, "search_recipes", upstream)
    path = "/v1/home-food/private-profile-test/myplate-recipes?requested=true&q=Italian"
    result = client.get(path, headers=headers(a))
    assert result.status_code == 200
    body = result.json()
    assert [row["slug"] for row in body["recipes"]] == ["bean-soup"]
    assert body["hidden_in_page"] == 1
    assert body["total"] == 30 and body["next_offset"] == 24
    assert body["personal_notice"]
    assert calls == [{"q": "Italian", "category": "", "offset": 0, "limit": 24}]
    assert len(source["recipes"]) == 2
    assert client.get(path, headers={"X-Roxy-Recipe-Member": "wrong"}).status_code == 409
    assert len(calls) == 1
    legacy = client.get(path).json()
    assert len(legacy["recipes"]) == 2 and "hidden_in_page" not in legacy
