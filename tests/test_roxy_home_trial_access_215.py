"""Trial accounts can reach manual fitness features without weakening privacy."""
from datetime import datetime, timedelta, timezone

import pytest

from roxy_os.home_accounts import HomeAccountStore
from roxy_os.home_demo import trial_access_mode
from roxy_os.fitness import router as fitness_router
from roxy_os.fitness.measurements import MeasurementsRepository
from roxy_os.fitness.training_logs import TrainingLogsRepository
from test_roxy_home_public_demo import demo, client, signup

BASE = '/api/fitness/v1'
RECORD_ID = '9d649df3-6f24-4cc6-ae58-a1224cd3270b'
PRIVATE_READS = ['/me/measurements', '/me/measurements/export', '/me/training-logs',
                 '/me/training-logs/export', '/me/training-progress']
MUTATIONS = [('POST', '/me/activity-plan/proposal'), ('POST', '/me/training/preview')]
for collection in ('measurements', 'training-logs'):
    MUTATIONS.extend([('PUT', f'/me/{collection}'), ('POST', f'/me/{collection}/consent'),
                      ('DELETE', f'/me/{collection}'), ('DELETE', f'/me/{collection}/{RECORD_ID}')])


def expire(store, member):
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    store._mutate(lambda data: data['households'][member['household_id']]['trial'].update(expires_at=expired))


def headers(member):
    return {'Origin': 'https://roxy.test', 'X-Roxy-Fitness-Member': member['id'],
            'X-Roxy-Fitness-Request': '1', 'Idempotency-Key': 'home-trial-access-215'}


@pytest.mark.parametrize('method,path', [('GET', p) for p in PRIVATE_READS] + MUTATIONS)
def test_manual_fitness_routes_are_exactly_allowlisted(method, path):
    assert trial_access_mode(method, BASE + path) == 'local'
    for suffix in ('/activate', '/purchase', '/generate', '/other', '/..', '%2fother'):
        assert trial_access_mode(method, BASE + path + suffix) == 'unavailable'


@pytest.mark.parametrize('path', [
    '/training/programs/unknown', '/training/programs/yoga',
    '/training/programs/yoga-gentle-start/speech', '/training/programs/../me/profile',
    '/me/measurements/not-a-uuid', '/me/training-logs/not-a-uuid',
    '/me/measurements/' + RECORD_ID.upper(), '/me/training-logs/' + RECORD_ID.upper(),
    '/me/training-logs/data', '/me/measurements/data', '/me/training-progress/export',
    '/me/training/activate', '/me/training/generate', '/me/activity-plan/proposals',
])
def test_unreviewed_aliases_and_invalid_identifiers_are_denied(path):
    for method in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE'):
        assert trial_access_mode(method, BASE + path) == 'unavailable'


@pytest.mark.parametrize('expired', [False, True])
def test_trial_reads_all_six_editorial_routines_without_pg_or_ai(demo, monkeypatch, expired):
    tester = client()
    member = signup(tester).json()
    if expired:
        expire(demo, member)
    before = demo.path.read_bytes()
    monkeypatch.setattr(fitness_router, 'repository', lambda: pytest.fail('Catalogue opened private storage'))
    monkeypatch.setattr(HomeAccountStore, 'reserve_trial_request', lambda *_: pytest.fail('Catalogue spent AI quota'))
    response = tester.get(BASE + '/training/programs')
    assert response.status_code == 200, response.text
    rows = response.json()['programs']
    assert len(rows) == 6
    for row in rows:
        path = BASE + '/training/programs/' + row['id']
        detail = tester.get(path)
        assert detail.status_code == 200, detail.text
        assert detail.json()['id'] == row['id']
        assert detail.headers['cache-control'] == 'private, no-store'
        for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            assert trial_access_mode(method, path) == 'unavailable'
    assert demo.path.read_bytes() == before


@pytest.mark.parametrize('expired', [False, True])
def test_trial_private_reads_require_current_identity_and_keep_scope(demo, monkeypatch, expired):
    tester = client()
    member = signup(tester).json()
    if expired:
        expire(demo, member)
    calls = []
    def snapshot(_self, member_id):
        calls.append(member_id)
        return {'version': 0, 'logs': [], 'consent': None, 'updated_at': None}
    for cls in (MeasurementsRepository, TrainingLogsRepository):
        monkeypatch.setattr(cls, 'snapshot', snapshot)
        monkeypatch.setattr(cls, 'export_data', snapshot)
    monkeypatch.setattr(HomeAccountStore, 'reserve_trial_request', lambda *_: pytest.fail('Private read spent AI quota'))
    for suffix in PRIVATE_READS:
        path = BASE + suffix
        assert tester.get(path).status_code == 409
        assert tester.get(path, headers={'X-Roxy-Fitness-Member': 'another-member'}).status_code == 409
        before = len(calls)
        response = tester.get(path, headers=headers(member))
        assert response.status_code == 200, response.text
        assert calls[before:] == [member['id']]
        assert response.headers['cache-control'] == 'private, no-store'
        assert client().get(path, headers=headers(member)).status_code == 401
    assert set(calls) == {member['id']}


@pytest.mark.parametrize('method,suffix', MUTATIONS)
def test_active_trial_mutations_retain_origin_identity_and_input_guards(demo, monkeypatch, method, suffix):
    tester = client()
    member = signup(tester).json()
    monkeypatch.setattr(fitness_router, 'repository', lambda: pytest.fail('Invalid request reached storage'))
    path = BASE + suffix
    assert tester.request(method, path, json={}).status_code == 409
    assert tester.request(method, path, json={}, headers={**headers(member), 'Origin': 'https://foreign.test'}).status_code == 403
    assert tester.request(method, path, json={}, headers={**headers(member), 'X-Roxy-Fitness-Request': '0'}).status_code == 403
    assert tester.request(method, path, json={}, headers=headers(member)).status_code == 422
    expire(demo, member)
    if method != 'DELETE':
        response = tester.request(method, path, json={}, headers=headers(member))
        assert response.status_code == 403
        assert 'terminaron' in response.json()['detail']


@pytest.mark.parametrize('collection,cls', [('measurements', MeasurementsRepository), ('training-logs', TrainingLogsRepository)])
@pytest.mark.parametrize('single', [False, True])
def test_expired_trial_can_erase_own_records_only_with_explicit_valid_intent(demo, monkeypatch, collection, cls, single):
    tester = client()
    member = signup(tester).json()
    expire(demo, member)
    calls = []
    def erase(_self, member_id, *args, **kwargs):
        calls.append((member_id, args, kwargs))
        return {'version': 1, 'consent': None}
    monkeypatch.setattr(cls, 'remove' if single else 'delete_data', erase)
    path = BASE + '/me/' + collection + ('/' + RECORD_ID if single else '')
    payload = {'expected_version': 0, 'confirm_delete': True}
    for supplied, body, expected in [
        ({**headers(member), 'X-Roxy-Fitness-Member': 'another-member'}, payload, 409),
        ({**headers(member), 'Origin': 'https://foreign.test'}, payload, 403),
        ({**headers(member), 'X-Roxy-Fitness-Request': '0'}, payload, 403),
        (headers(member), {**payload, 'confirm_delete': False}, 422),
        (headers(member), {**payload, 'expected_version': -1}, 422),
    ]:
        assert tester.request('DELETE', path, json=body, headers=supplied).status_code == expected
        assert calls == []
    result = tester.request('DELETE', path, json=payload, headers=headers(member))
    assert result.status_code == 200, result.text
    assert result.headers['cache-control'] == 'private, no-store'
    assert calls == [(member['id'], (RECORD_ID,) if single else (),
                      {'expected_version': 0, 'idempotency_key': 'home-trial-access-215'})]
