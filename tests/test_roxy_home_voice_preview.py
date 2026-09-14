"""No real provider, credential or household access."""
import json
import os
from pathlib import Path
import pytest
import requests
from tools.roxy_home_login_preview import consume_voice_config, preview_transport
from roxy_os.home_tour import speech_for

VOICE = {'ROXY_HOME_ELEVENLABS_API_KEY': 'synthetic-home-only', 'ROXY_HOME_ELEVENLABS_VOICE_ID': 'syntheticvoice', 'ROXY_HOME_ELEVENLABS_MODEL_ID': 'eleven_multilingual_v2'}
URL = 'https://api.elevenlabs.io/v1/text-to-speech/syntheticvoice?output_format=mp3_44100_128'
BODY = {'text': speech_for('world-fitness'), 'model_id': VOICE['ROXY_HOME_ELEVENLABS_MODEL_ID']}


def test_temporary_voice_file_is_consumed_and_contains_only_home_keys(tmp_path):
    path = tmp_path / 'voice.json'; path.write_text(json.dumps(VOICE)); path.chmod(0o600)
    assert consume_voice_config(path) == VOICE
    assert not path.exists()


@pytest.mark.parametrize('kind', ['permissions', 'foreign-key', 'empty', 'symlink'])
def test_unsafe_or_other_product_configuration_is_rejected_without_echo(tmp_path, kind):
    path = tmp_path / 'voice.json'; values = VOICE.copy()
    if kind == 'foreign-key': values['ROXY_TRADING_API_KEY'] = 'must-not-leak'
    if kind == 'empty': values['ROXY_HOME_ELEVENLABS_API_KEY'] = ''
    path.write_text(json.dumps(values)); path.chmod(0o644 if kind == 'permissions' else 0o600)
    if kind == 'symlink':
        link = tmp_path / 'link.json'; link.symlink_to(path); path = link
    with pytest.raises(ValueError) as error: consume_voice_config(path)
    assert 'must-not-leak' not in str(error.value)
    assert path.exists()


def test_default_fixture_remains_offline():
    request = preview_transport(lambda *a, **k: pytest.fail('Network escaped'), {})
    with pytest.raises(requests.ConnectionError): request(None, 'POST', URL, json=BODY)


def test_only_exact_home_voice_fixed_script_request_passes_and_redirects_are_disabled():
    calls = []
    request = preview_transport(lambda *a, **kw: calls.append((a, kw)) or 'audio', VOICE)
    assert request(None, 'post', URL, json=BODY, allow_redirects=True) == 'audio'
    assert len(calls) == 1 and calls[0][1]['allow_redirects'] is False


@pytest.mark.parametrize('method,url,body', [
    ('GET', URL, BODY), ('POST', URL.replace('api.elevenlabs.io', 'elsewhere.test'), BODY),
    ('POST', URL.replace('syntheticvoice', 'another-product'), BODY),
    ('POST', 'https://api.openai.com/v1/responses', BODY),
    ('POST', URL, {**BODY, 'text': 'Private household answer'}),
    ('POST', URL, {**BODY, 'model_id': 'another-model'}),
])
def test_other_providers_voices_and_private_text_never_leave_fixture(method, url, body):
    request = preview_transport(lambda *a, **k: pytest.fail('Network escaped'), VOICE)
    with pytest.raises(requests.ConnectionError): request(None, method, url, json=body)
