from pathlib import Path

from roxy_os.home_voice import ElevenLabsHomeVoice, HomeVoiceConfig


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
    assert public == {"enabled": True, "provider": "ElevenLabs", "voice": "Roxy oficial"}
    assert "home-only-secret" not in str(public)


def test_home_voice_requires_a_separate_home_key(monkeypatch):
    monkeypatch.delenv("ROXY_HOME_ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "trading-secret-that-must-not-be-reused")
    config = HomeVoiceConfig.from_env()
    assert config.api_key == ""
    assert config.configured is False
