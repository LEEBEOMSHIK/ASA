import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from test_registry_db import KEY, login
from test_registry_db import client as client_fixture
from test_registry_db import db as database_fixture

from asa.api import create_app
from asa.config import Settings

db = database_fixture
client = client_fixture


def test_region_apply_checks_auth_revision_and_keeps_policy(db, monkeypatch):
    cfg = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                   environment='development', owner_access_key=KEY,
                   allowed_origins=['http://testserver'], wan_api_key='sg-key',
                   wan_workspace_id='sg', wan_tokyo_api_key='tokyo-key',
                   wan_tokyo_workspace_id='tokyo')
    calls = []
    result = {'status': 403}

    def get(url, **kwargs):
        calls.append((url, kwargs['headers']['Authorization']))
        return httpx.Response(result['status'], json={'data': []})

    monkeypatch.setattr(httpx, 'get', get)
    with TestClient(create_app(cfg)) as client:
        headers = login(client)
        path = '/api/v1/video-management'
        state = client.get(path).json()
        assert state['wan_regions']['active_region'] == 'ap-southeast-1'
        payload = {'region': 'ap-northeast-1', 'revision': 0}
        assert client.put(path + '/wan-region', json=payload).status_code == 403
        assert client.put(path + '/wan-region', headers=headers, json=payload).status_code == 409
        assert client.get(path).json()['wan_regions']['revision'] == 0
        result['status'] = 200
        applied = client.put(path + '/wan-region', headers=headers, json=payload)
        assert applied.status_code == 200, applied.text
        data = applied.json()
        assert data['wan_regions']['active_region'] == 'ap-northeast-1'
        assert data['wan_regions']['revision'] == 1
        assert data['revision'] == state['revision']
        assert data['enabled'] == state['enabled']
        assert 'tokyo-key' not in applied.text and 'sg-key' not in applied.text
        assert client.put(path + '/wan-region', headers=headers, json=payload).status_code == 409
        client.post('/api/v1/video-planning/provider-connection/alibaba', headers=headers)
        assert calls[-1] == ('https://tokyo.ap-northeast-1.maas.aliyuncs.com/api/v1/tasks',
                             'Bearer tokyo-key')


@pytest.mark.parametrize('role,foreign', [('viewer', False), ('admin', True)])
def test_region_admin_workspace_guard(db, monkeypatch, role, foreign):
    from uuid import uuid4

    from asa.auth.session import OwnerSessions, Principal

    monkeypatch.setattr(OwnerSessions, 'principal', lambda self: Principal(
        'u', uuid4() if foreign else db[1], (role,)))
    cfg = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                   environment='development')
    with TestClient(create_app(cfg)) as api:
        path = '/api/v1/video-management'
        assert api.post(path + '/wan-regions/ap-northeast-1/check').status_code == 403
        assert api.put(path + '/wan-region', json={
            'region': 'ap-northeast-1', 'revision': 0}).status_code == 403


def test_switch_preserves_queued_running_jobs_and_frozen_credentials(client, db, monkeypatch):
    from psycopg.rows import dict_row
    from test_registry_db import test_wan_queue_worker_lifecycle as seed

    from asa import video_worker

    seed(client, db, monkeypatch, 'success')
    cfg = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                   environment='development', owner_access_key=KEY,
                   allowed_origins=['http://testserver'], video_ai_enabled=True,
                   wan_api_key='test-wan', wan_workspace_id='ws-test',
                   wan_tokyo_api_key='tokyo-key', wan_tokyo_workspace_id='tokyo')
    monkeypatch.setattr(httpx, 'get', lambda *a, **kw: httpx.Response(200, json={'data': []}))
    calls = []

    def respond(request):
        calls.append((request.method, request.url.host, request.headers['Authorization']))
        return httpx.Response(200, json={'output': {
            'task_id': 'original-task', 'task_status': 'RUNNING'}})

    with psycopg.connect(db[0], autocommit=True, row_factory=dict_row) as conn:
        conn.execute("UPDATE video_clip_jobs SET status='queued',next_poll=now()")
        before = conn.execute('SELECT * FROM video_clip_jobs').fetchall()
        with TestClient(create_app(cfg)) as api:
            headers = login(api)
            path = '/api/v1/video-management/wan-region'
            assert api.put(path, headers=headers, json={
                'region': 'ap-northeast-1', 'revision': 0}).status_code == 200
            assert conn.execute('SELECT * FROM video_clip_jobs').fetchall() == before
            with httpx.Client(transport=httpx.MockTransport(respond)) as http:
                assert video_worker.process(conn, http, db[1], cfg)
                running = conn.execute('SELECT * FROM video_clip_jobs').fetchall()
                assert running[0]['status'] == 'running'
                assert api.put(path, headers=headers, json={
                    'region': 'ap-southeast-1', 'revision': 1}).status_code == 200
                assert conn.execute('SELECT * FROM video_clip_jobs').fetchall() == running
                assert api.put(path, headers=headers, json={
                    'region': 'ap-northeast-1', 'revision': 2}).status_code == 200
                conn.execute('UPDATE video_clip_jobs SET next_poll=now()')
                assert video_worker.process(conn, http, db[1], cfg)
            # Remove only this isolated fixture's completed scenario to exercise fresh enqueue.
            conn.execute('DELETE FROM video_clip_jobs WHERE workspace_id=%s', (db[1],))
            rid = before[0]['request_id']
            clip_path = f'/api/v1/video-clips/{rid}/1'
            approval = api.get(clip_path).json()['plan_approvals']['clip1']
            assert api.post(clip_path + '/plan-approve', headers=headers, json={
                'clip_ids': ['clip1'], 'fingerprints': {
                    'clip1': approval['fingerprint']}}).status_code == 200
            response = api.post(f'/api/v1/video-clips/{rid}/1', headers=headers,
                                json={'clip_ids': ['clip1']})
            assert response.status_code == 200, response.text
            assert response.json() == {'queued': 1}
            fresh = conn.execute("SELECT model_snapshot FROM video_clip_jobs "
                                 "WHERE status='queued'").fetchone()
            assert fresh is not None
            assert fresh['model_snapshot']['provider_endpoint'] == (
                'https://tokyo.ap-northeast-1.maas.aliyuncs.com/api/v1')
            # Resume uses this frozen Tokyo profile, even if Singapore is now active.
            conn.execute("UPDATE video_clip_jobs SET paused=true WHERE status='queued'")
            assert api.put(path, headers=headers, json={
                'region': 'ap-southeast-1', 'revision': 3}).status_code == 200
            missing_tokyo = cfg.model_copy(update={'wan_tokyo_api_key': cfg.runway_api_key})
            with TestClient(create_app(missing_tokyo)) as missing_api:
                missing_headers = login(missing_api)
                assert missing_api.post('/api/v1/video-management/resume',
                                        headers=missing_headers).status_code == 200
            assert conn.execute("SELECT paused FROM video_clip_jobs WHERE status='queued'"
                                ).fetchone()['paused']
            assert api.post('/api/v1/video-management/resume', headers=headers).status_code == 200
            assert not conn.execute("SELECT paused FROM video_clip_jobs WHERE status='queued'"
                                    ).fetchone()['paused']
    assert calls == [(method, 'ws-test.ap-southeast-1.maas.aliyuncs.com', 'Bearer test-wan')
                     for method in ['POST', 'GET']]
