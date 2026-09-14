"""Actual app routes, synthetic members, no provider calls or household edits."""
from pathlib import Path
import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_demo import trial_access_mode
from roxy_os.home_tour import CHAPTERS, EXTRA_SCRIPTS, speech_for
from tools import roxy_home_service as service


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "_LOGIN_RATE_STATE", {})
    monkeypatch.setattr(service, "_RATE_STATE", {})
    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-tour-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "tour-test")
    monkeypatch.setenv("ROXY_HOME_ACCOUNTS_PATH", str(tmp_path / "accounts.json"))
    monkeypatch.delenv("ROXY_HOME_PUBLIC_ORIGIN", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    store = HomeAccountStore(tmp_path / "accounts.json")
    a = store.bootstrap("tour-test", household_name="Synthetic", username="tour-a",
                        display_name="Test A", password="Synthetic-Tour-2026")
    b = store.add_member(a["id"], username="tour-b", display_name="Test B", password="Synthetic-Tour-2026")
    client = TestClient(service.app, base_url="https://tour.test")
    client.post("/v1/home-account/login", json={"username": "tour-a", "password": "Synthetic-Tour-2026"})
    return client, store, a, b


def headers(member):
    return {"X-Roxy-Member-Id": member["id"], "X-Roxy-Session-Version": str(member["session_version"]), "Origin": "https://tour.test"}


def save(client, a, **changes):
    body = {"expected_revision": 0, "progress": {"version": 1, "chapter": "calendar", "completed": True}, **changes}
    return client.put("/v1/home-tour", json=body, headers=headers(a))


def test_tour_roundtrip_does_not_complete_or_change_culinary_profile(setup):
    client, store, a, b = setup
    read = client.get("/v1/home-tour", headers=headers(a))
    assert read.status_code == 200 and len(read.json()["chapters"]) == 13
    assert read.json()["progress"] is None
    assert "no-store" in read.headers["cache-control"]
    assert save(client, a).status_code == 200
    assert HomeAccountStore(store.path).get_home_tour(a["id"])["progress"]["completed"]
    assert store.get_home_tour(b["id"])["progress"] is None
    assert store.get_recipe_profile(a["id"])["profile"] is None
    assert store.member(a["id"])["recipe_onboarding_required"] is True
    assert client.get("/v1/home-account/me").json()["home_tour_completed"] is True
    assert save(client, a).status_code == 409


@pytest.mark.parametrize("extra", [{"version": 2}, {"completed": "true"}, {"chapter": "no-such-chapter"}, {"private": "my-medical-history"}])
def test_progress_validation_never_stores_arbitrary_information(setup, extra):
    client, store, a, _ = setup
    response = save(client, a, progress={"version": 1, "chapter": "welcome", "completed": False, **extra})
    assert response.status_code == 422
    assert store.get_home_tour(a["id"])["progress"] is None


@pytest.mark.parametrize("route,method,payload", [("/v1/home-tour", "get", None), ("/v1/home-tour", "put", {"expected_revision": 0, "progress": {}}), ("/v1/home-tour/speech", "post", {"chapter": "welcome"})])
def test_all_routes_bind_the_visible_member_and_session(setup, route, method, payload):
    client, _, a, b = setup
    for values in ({}, headers(b), {**headers(a), "X-Roxy-Session-Version": "999"}):
        kwargs = {"headers": values}
        if payload is not None: kwargs["json"] = payload
        assert getattr(client, method)(route, **kwargs).status_code == 409
    client.cookies.clear()
    kwargs = {"json": payload} if payload is not None else {}
    assert getattr(client, method)(route, **kwargs).status_code == 401


def test_mutations_reject_cross_origin_without_any_write(setup):
    client, store, a, _ = setup
    for origin in ("", "https://evil.test", "http://tour.test"):
        response = client.post("/v1/home-tour/speech", json={"chapter": "welcome"}, headers={**headers(a), "Origin": origin})
        assert response.status_code == 403
    assert store.get_home_tour(a["id"])["revision"] == 0


def test_proxy_origin_uses_trusted_render_host(setup, monkeypatch):
    client, _, a, _ = setup
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://tour.test")
    with TestClient(service.app, base_url="http://tour.test") as proxy:
        proxy.cookies.update(client.cookies)
        # Secure cookie won't be sent to HTTP by the test client: use its header
        # to simulate the trusted TLS terminator forwarding the original cookie.
        cookie = "; ".join(f"{k}={v}" for k, v in client.cookies.items())
        response = proxy.put("/v1/home-tour", json={"expected_revision": 0, "progress": {"version": 1, "chapter": "welcome", "completed": False}}, headers={**headers(a), "Cookie": cookie})
        assert response.status_code == 200


def test_audio_is_fixed_script_shared_cache_and_unknown_text_never_reaches_voice(setup, monkeypatch):
    client, _, a, _ = setup
    calls = []
    # Router captured _official_voice_response; patch the synthesizer it uses.
    class Config:
        configured = True
    class Voice:
        def __init__(self, config): pass
        def synthesize(self, text, *, user_id):
            calls.append((text, user_id))
            return Path(__file__)  # Synthetic file; not evidence of actual audio.
    monkeypatch.setattr(service, "_home_voice_config", lambda: Config())
    monkeypatch.setattr(service, "ElevenLabsHomeVoice", Voice)
    good = client.post("/v1/home-tour/speech", json={"chapter": "welcome"}, headers=headers(a))
    assert good.status_code == 200 and good.headers["content-type"] == "audio/mpeg"
    assert calls == [(speech_for("welcome"), "home-tutorial-v1")]
    assert client.post("/v1/home-tour/speech", json={"chapter": "welcome", "text": "untrusted arbitrary speech"}, headers=headers(a)).status_code == 422
    assert client.post("/v1/home-tour/speech", json={"chapter": "../../secrets"}, headers=headers(a)).status_code == 404
    assert len(calls) == 1


def test_curated_chapters_have_real_local_media_and_fit_existing_voice_budget():
    root = Path(__file__).resolve().parents[1]
    assert len({row["id"] for row in CHAPTERS}) == 13
    for row in CHAPTERS:
        assert 30 < len(row["speech"]) <= 1200
        assert len(row["steps"]) >= 3
        for field in ("image", "video"):
            if row[field]:
                assert row[field].startswith("/assets/")
                assert (root / row[field].lstrip("/")).is_file()
    assert all(30 < len(text) <= 1200 for text in EXTRA_SCRIPTS.values())
    assert sum(len(row["speech"]) for row in CHAPTERS) + sum(map(len, EXTRA_SCRIPTS.values())) < 20000


def test_demo_only_opens_allowlisted_tutorial_voice():
    for method, route in [("GET", "/v1/home-tour"), ("PUT", "/v1/home-tour"), ("POST", "/v1/home-tour/speech")]:
        assert trial_access_mode(method, route) == "local"
    for route in ("/v1/home-tour/anything", "/v1/assistant/speech/user", "/v1/assistant/session/user"):
        assert trial_access_mode("POST", route) == "unavailable"


def test_exercise_narration_only_reads_exact_bundled_source_movements():
    from roxy_os.fitness.programs import program_detail
    for kind in ("strength", "balance", "flexibility"):
        program = program_detail("gentle-" + kind)["program"]
        for index, exercise in enumerate(program["exercises"]):
            spoken = speech_for(f"fitness:{kind}:{index}")
            assert len(spoken) <= 1200
            for line in exercise["instructions_es"]:
                assert line in spoken
        assert speech_for(f"fitness:{kind}:9") is None
    for invalid in ("fitness:strength:00", "fitness:other:0", "fitness:strength:-1"):
        assert speech_for(invalid) is None
