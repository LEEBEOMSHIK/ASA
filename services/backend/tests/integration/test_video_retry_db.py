from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from test_registry_db import KEY, login
from test_registry_db import client as client_fixture
from test_registry_db import db as database_fixture
from test_registry_db import test_wan_queue_worker_lifecycle as seed

from asa.api import create_app
from asa.config import Settings

db = database_fixture
client = client_fixture


@pytest.mark.parametrize('state', ['failed', 'unknown'])
def test_retry_preserves_history_and_serializes_double_click(client, db, monkeypatch, state):
    seed(client, db, monkeypatch, 'success')
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        owner_access_key=KEY, allowed_origins=['http://testserver'],
                        video_ai_enabled=True, wan_api_key='test-wan', wan_workspace_id='ws-test')
    from asa import video_connection
    calls = []
    def check(*args):
        calls.append(args[0].wan_region)
        return {'status': 'authenticated'}
    monkeypatch.setattr(video_connection, 'check', check)
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        conn.execute('UPDATE video_clip_jobs SET status=%s,provider_task=NULL,video=NULL', (state,))
        old = conn.execute('SELECT * FROM video_clip_jobs').fetchone()
    path = f"/api/v1/video-clips/{old['request_id']}/1"
    retry = f"{path}/jobs/{old['id']}/retry"
    payload = {'id': str(uuid4()), 'acknowledge_unknown': state == 'unknown'}
    with TestClient(create_app(settings)) as api:
        headers = login(api)
        state = api.get(path).json()
        approval = api.post(path + '/plan-approve', headers=headers, json={
            'clip_ids': [old['clip_id']], 'fingerprints': {
                old['clip_id']: state['plan_approvals'][old['clip_id']]['fingerprint']}})
        assert approval.status_code == 200, approval.text
        review = api.get(retry + '-review').json()
        assert review['eligible'], review
        payload['expected_target'] = review['target_fingerprint']
        assert calls == []
        # Invalid or stale targets never reach provider authentication or consume the slot.
        assert api.post(retry, headers=headers, json={
            **payload, 'expected_target': '0' * 64}).json()[
                'detail'] == 'video_retry_target_changed'
        with psycopg.connect(db[0]) as conn:
            conn.execute("UPDATE video_clip_jobs SET provider_task='existing-task'")
        assert api.post(retry, headers=headers, json=payload).json()[
            'detail'] == 'video_retry_recovery_required'
        with psycopg.connect(db[0]) as conn:
            conn.execute('UPDATE video_clip_jobs SET provider_task=NULL,video=%s', (b'asset',))
        assert api.post(retry, headers=headers, json=payload).json()[
            'detail'] == 'video_retry_not_eligible'
        with psycopg.connect(db[0]) as conn:
            conn.execute('UPDATE video_clip_jobs SET video=NULL')
        monkeypatch.setattr(video_connection, 'check', lambda *args: {'status': 'denied'})
        assert api.post(retry, headers=headers, json=payload).json()[
            'detail'] == 'video_retry_authentication_required'
        with psycopg.connect(db[0], row_factory=dict_row) as conn:
            assert conn.execute('SELECT count(*) AS n FROM video_clip_jobs').fetchone()['n'] == 1
            assert conn.execute('SELECT superseded_by FROM video_clip_jobs').fetchone()[
                'superseded_by'] is None
        monkeypatch.setattr(video_connection, 'check', check)
        assert calls == []
        assert api.post(retry, json=payload).status_code == 403
        if old['status'] == 'unknown':
            assert api.post(retry, headers=headers, json={
                **payload, 'acknowledge_unknown': False}).json()['detail'] == (
                    'video_retry_acknowledgment_required')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda _: api.post(retry, headers=headers, json=payload), range(2)))
        assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
        assert len(calls) == 1
        assert api.post(retry, headers=headers,
                        json={**payload, 'id': str(uuid4())}).status_code == 409
        result = api.get(path).json()
        assert len(result['jobs']) == 1
        assert len(result['previous_attempts']) == 1
        assert result['jobs'][0]['id'] == payload['id']
        assert result['previous_attempts'][0]['id'] == str(old['id'])
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        preserved = conn.execute('SELECT * FROM video_clip_jobs WHERE id=%s',
                                 (old['id'],)).fetchone()
        assert {k: v for k, v in preserved.items() if k != 'superseded_by'} == {
            k: v for k, v in old.items() if k != 'superseded_by'}
