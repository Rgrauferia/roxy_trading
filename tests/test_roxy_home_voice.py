from pathlib import Path

import pytest

from roxy_os.home_voice import ElevenLabsHomeVoice, HomeVoiceConfig, HomeVoiceError


class FakeResponse:
    def __init__(self, *, payload=None, content=b""):
        self._payload = payload or {}
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.get_calls = []
        self.post_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return FakeResponse(payload={"conversation_config": {"tts": {"voice_id": "official-roxy-voice", "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.7}}}})

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse(content=b"I" * 2_048)


def voice_config(tmp_path: Path) -> HomeVoiceConfig:
    return HomeVoiceConfig(api_key="home-only-secret", agent_id="official-roxy-agent", voice_id="", model_id="eleven_multilingual_v2", cache_dir=tmp_path / "voice")


def test_home_voice_uses_official_agent_profile_and_caches_audio(tmp_path):
    session = FakeSession()
    voice = ElevenLabsHomeVoice(voice_config(tmp_path), session=session)
    first = voice.synthesize("Paso 1. Mezcla la harina.", user_id="robert")
    second = voice.synthesize("Paso 1. Mezcla la harina.", user_id="robert")
    assert first == second
    assert first.read_bytes() == b"I" * 2_048
    assert len(session.get_calls) == 1
    assert len(session.post_calls) == 1
    assert "/convai/agents/official-roxy-agent" in session.get_calls[0][0]
    assert "/text-to-speech/official-roxy-voice" in session.post_calls[0][0]
    assert session.post_calls[0][1]["json"]["voice_settings"] == {"stability": 0.7}


def test_home_voice_public_status_never_exposes_the_key(tmp_path):
    public = voice_config(tmp_path).public_status()
    assert public == {"enabled": True, "status": "CONFIGURED", "provider_health_verified": False, "provider": "ElevenLabs", "voice": "Roxy oficial"}
    assert "home-only-secret" not in str(public)


def test_home_voice_requires_a_separate_home_key(monkeypatch):
    monkeypatch.delenv("ROXY_HOME_ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "trading-secret-that-must-not-be-reused")
    config = HomeVoiceConfig.from_env()
    assert config.api_key == ""
    assert config.configured is False


def test_home_voice_never_inherits_a_shared_agent(monkeypatch):
    monkeypatch.delenv("ROXY_HOME_ELEVENLABS_AGENT_ID", raising=False)
    monkeypatch.delenv("ROXY_HOME_ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "shared-product-agent")
    monkeypatch.setenv("ROXY_HOME_ELEVENLABS_API_KEY", "synthetic-home-key")
    config = HomeVoiceConfig.from_env()
    assert config.agent_id == ""
    assert config.configured is False
    assert config.public_status()["provider_health_verified"] is False


def test_home_tts_can_use_an_explicit_home_voice_without_a_conversation_agent(tmp_path):
    config = HomeVoiceConfig(api_key="home-only-secret", agent_id="", voice_id="home-only-voice", model_id="eleven_multilingual_v2", cache_dir=tmp_path)
    session = FakeSession()
    audio = ElevenLabsHomeVoice(config, session=session).synthesize("Paso 1 completo.", user_id="synthetic-user")
    assert audio.is_file()
    assert session.get_calls == []
    assert session.post_calls[0][0].endswith("/home-only-voice?output_format=mp3_44100_128")


def test_home_voice_rejects_long_steps_before_calling_provider_instead_of_truncating(tmp_path):
    session = FakeSession()
    voice = ElevenLabsHomeVoice(voice_config(tmp_path), session=session)
    with pytest.raises(ValueError, match="texto|completo"):
        voice.synthesize("Paso completo " * 100, user_id="synthetic-user")
    assert session.get_calls == []
    assert session.post_calls == []


def test_voice_budget_reserves_characters_once_and_cached_replay_is_free(tmp_path):
    import json
    from dataclasses import replace
    config = replace(voice_config(tmp_path), daily_characters=15, daily_requests=1)
    session = FakeSession()
    voice = ElevenLabsHomeVoice(config, session=session)
    voice.synthesize("Paso exacto.", user_id="member-a")
    voice.synthesize("Paso exacto.", user_id="member-a")
    usage = json.loads((config.cache_dir / "usage.json").read_text())
    assert usage["requests"] == 1 and usage["characters"] == len("Paso exacto.")
    assert "Paso exacto" not in str(usage) and len(session.post_calls) == 1
    with pytest.raises(HomeVoiceError, match="límite diario"):
        voice.synthesize("Otro paso.", user_id="member-a")
    assert len(session.post_calls) == 1


def test_voice_budget_corruption_never_resets_or_calls_provider(tmp_path):
    from roxy_os.home_private_storage import HomePrivateStorageError
    config = voice_config(tmp_path)
    config.cache_dir.mkdir()
    (config.cache_dir / "usage.json").write_text("{broken")
    session = FakeSession()
    with pytest.raises(HomePrivateStorageError):
        ElevenLabsHomeVoice(config, session=session).synthesize("Paso uno.", user_id="member-a")
    assert not session.post_calls
    assert (config.cache_dir / "usage.json").read_text() == "{broken"


def test_voice_payment_error_is_sanitized_and_reservation_kept(tmp_path):
    import json
    import requests
    class PaymentSession(FakeSession):
        def post(self, *args, **kwargs):
            self.post_calls.append((args, kwargs))
            response = requests.Response(); response.status_code = 401
            response._content = b'{"detail":{"status":"payment_issue","message":"do-not-expose-provider-secret"}}'
            raise requests.HTTPError("do-not-expose-provider-secret", response=response)
    config = voice_config(tmp_path); session = PaymentSession()
    with pytest.raises(HomeVoiceError) as caught:
        ElevenLabsHomeVoice(config, session=session).synthesize("Paso uno.", user_id="member-a")
    assert caught.value.code == "payment_issue"
    assert "do-not-expose" not in str(caught.value)
    assert json.loads((config.cache_dir / "usage.json").read_text())["requests"] == 1


def test_voice_rejects_path_traversal_before_using_provider(tmp_path):
    session = FakeSession()
    with pytest.raises(ValueError):
        ElevenLabsHomeVoice(voice_config(tmp_path), session=session).synthesize("Paso uno.", user_id="../other-home")
    assert not session.get_calls and not session.post_calls


def test_home_conversation_rejects_missing_home_agent_without_using_shared_agent(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from tools import roxy_home_service

    monkeypatch.setenv("ROXY_HOME_API_KEY", "synthetic-home-api-key")
    monkeypatch.setenv("ROXY_STATE_SYNC_USERS", "synthetic-user")
    monkeypatch.setenv("ROXY_SHOPPING_LIST_PATH", str(tmp_path / "shopping.json"))
    monkeypatch.delenv("ROXY_HOME_ELEVENLABS_AGENT_ID", raising=False)
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "shared-product-agent")
    roxy_home_service._RATE_STATE.clear()
    client = TestClient(roxy_home_service.app)
    response = client.get("/v1/assistant/session/synthetic-user", headers={"Authorization": "Bearer synthetic-home-api-key"})
    assert response.status_code == 503
    assert "exclusivo de Roxy Home" in response.json()["detail"]
    assert "shared-product-agent" not in response.text


def test_home_voice_does_not_reset_a_future_usage_ledger(tmp_path):
    import json
    config = voice_config(tmp_path)
    config.cache_dir.mkdir()
    ledger = config.cache_dir / 'usage.json'
    ledger.write_text(json.dumps({'date': '2999-01-01', 'requests': 1, 'characters': 10}))
    before = ledger.read_bytes()
    session = FakeSession()
    with pytest.raises(RuntimeError):
        ElevenLabsHomeVoice(config, session=session).synthesize('Paso intacto.', user_id='member')
    assert ledger.read_bytes() == before
    assert session.post_calls == []
