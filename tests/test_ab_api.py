import os
from fastapi.testclient import TestClient

import tools.voice_service as vs


def setup_env(tmpdir):
    os.environ['FERNET_KEY'] = __import__('cryptography').fernet.Fernet.generate_key().decode()
    os.environ['ADMIN_TOKEN'] = 'test-admin-token'
    import tools.secrets_service as ss

    ss.DB_PATH = os.path.join(str(tmpdir), "db", "roxy.db")
    ss.ensure_tables()


def test_ab_api_scope_checks(tmp_path):
    setup_env(tmp_path)
    client = TestClient(vs.app)

    # create an A/B test directly
    from tools import ab_test

    ab_test.create_test('t_canary', {'control': 1, 'canary': 1})

    # create API key WITHOUT ab:execute scope
    r = client.post('/api/api-keys', headers={'Authorization': 'Bearer test-admin-token'}, json={'name': 'nokey', 'owner': 'tests', 'scopes': ['secrets:reveal']})
    assert r.status_code == 200
    plain1 = r.json()['plain_key']

    payload = {
        'test_name': 't_canary',
        'actor': 'tester',
        'symbol': 'AAPL',
        'side': 'BUY',
        'qty': 1.0,
        'price': 100.0,
    }

    # should be forbidden due to missing scope
    r2 = client.post('/api/ab/execute', headers={'Authorization': f'Bearer {plain1}'}, json=payload)
    assert r2.status_code == 403

    # create API key WITH ab:execute scope
    r3 = client.post('/api/api-keys', headers={'Authorization': 'Bearer test-admin-token'}, json={'name': 'canary', 'owner': 'tests', 'scopes': ['ab:execute']})
    assert r3.status_code == 200
    plain2 = r3.json()['plain_key']

    # now request should succeed (may return executed or error depending on env)
    r4 = client.post('/api/ab/execute', headers={'Authorization': f'Bearer {plain2}'}, json=payload)
    assert r4.status_code in (200, 201)
    jd = r4.json()
    assert jd.get('test') == 't_canary'
