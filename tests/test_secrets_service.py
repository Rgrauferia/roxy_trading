import os
import json
import tempfile
from fastapi.testclient import TestClient

import tools.voice_service as vs


def setup_env(tmpdir):
    os.environ['FERNET_KEY'] = __import__('cryptography').fernet.Fernet.generate_key().decode()
    os.environ['ADMIN_TOKEN'] = 'test-admin-token'
    import tools.secrets_service as ss

    ss.DB_PATH = os.path.join(str(tmpdir), "db", "roxy.db")
    ss.ensure_tables()


def test_create_and_reveal_secret(tmp_path, monkeypatch):
    setup_env(tmp_path)
    client = TestClient(vs.app)

    # create secret
    r = client.post('/api/secrets', headers={'Authorization': 'Bearer test-admin-token'}, json={
        'name': 'TEST_SECRET', 'value': 's3cr3t', 'provider': 'test'
    })
    assert r.status_code == 201

    # reveal
    r2 = client.get('/api/secrets/TEST_SECRET/reveal', headers={'Authorization': 'Bearer test-admin-token'})
    assert r2.status_code == 200
    assert r2.json().get('value') == 's3cr3t'


def test_api_key_create_and_rotate(tmp_path):
    setup_env(tmp_path)
    client = TestClient(vs.app)

    r = client.post('/api/api-keys', headers={'Authorization': 'Bearer test-admin-token'}, json={'name': 'svc1', 'owner': 'tests', 'scopes': ['secrets:reveal']})
    assert r.status_code == 200
    jd = r.json()
    assert 'plain_key' in jd
    plain = jd['plain_key']

    # rotate
    kid = jd['id']
    r2 = client.post(f'/api/api-keys/{kid}/rotate', headers={'Authorization': 'Bearer test-admin-token'})
    assert r2.status_code == 200
    assert 'plain_key' in r2.json()
