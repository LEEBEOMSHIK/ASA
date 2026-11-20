import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from test_registry_db import KEY, definition, login
from test_registry_db import client as client_fixture
from test_registry_db import db as database_fixture

from asa.api import create_app
from asa.config import Settings

db = database_fixture
client = client_fixture


def test_details_policy_revision_admin_and_legacy_client(db, monkeypatch):
    from asa.worker_control import WorkerControl
    monkeypatch.setattr(WorkerControl, 'status', lambda *a: {'state': 'stopped', 'busy': False})
    cfg = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                   environment='development', owner_access_key=KEY,
                   allowed_origins=['http://testserver'])
    with TestClient(create_app(cfg)) as client:
        headers = login(client)
        path = '/api/v1/video-management'
        original = client.get(path).json()
        assert original['user_details_enabled'] is False
        payload = {key: original[key] for key in ['enabled', 'providers', 'revision']}
        payload['user_details_enabled'] = True
        assert client.put(path, json=payload).status_code == 403
        response = client.put(path, headers=headers, json=payload)
        assert response.status_code == 200, response.text
        state = response.json()
        assert state['user_details_enabled'] is True
        assert state['enabled'] == original['enabled']
        assert client.get('/api/v1/video-planning/models').json()['user_details_enabled'] is True
        assert client.put(path, headers=headers, json=payload).status_code == 409
        legacy = {key: state[key] for key in ['enabled', 'providers', 'revision']}
        assert client.put(path, headers=headers, json=legacy).json()['user_details_enabled'] is True


@pytest.mark.parametrize('enabled,expected_key,expected_duration', [
    (False, 'hf-wan3-1080p', 5), (True, 'hf-wan3-480p', 8)])
def test_queue_freezes_applied_settings_and_preserves_submitted_input(
    client, db, enabled, expected_key, expected_duration
):
    from asa.registry.script_stage import GenerateScript, ScriptRepository
    from asa.registry.video_planning import planner_constraints
    headers = login(client)
    agent = definition()
    agent['input_schema']['properties']['video_model'] = {
        'type': 'string', 'x-video-model': True, 'enum': ['wan3', 'hf-wan3']}
    saved = client.post('/api/v1/agents/save', headers=headers, json=agent).json()
    rid, attempt = uuid4(), uuid4()
    submitted = {'topic': '원본 대본', 'video_model': 'hf-wan3-480p', 'video_duration_seconds': 8}
    response = client.post('/api/v1/work-requests', headers=headers, json={
        'id': str(rid), 'agent_id': saved['id'], 'version': 1, 'input': submitted})
    assert response.status_code == 201, response.text
    repo = ScriptRepository(*db)
    with repo._connect() as conn:
        conn.execute('INSERT INTO video_generation_controls '
                     '(workspace_id,enabled,providers,revision,'
                     'user_details_enabled,model_defaults) '
                     'VALUES (%s,false,%s,1,%s,%s)', (db[1], Jsonb({}), enabled, Jsonb({
                         'higgsfield:alibaba/wan-3.0': {
                             'model_key': 'hf-wan3-1080p', 'duration_seconds': 5}})))
    repo.queue(str(rid), GenerateScript(id=attempt, expected_revision=0, base_version=0,
                                       instruction='기존 대본으로 계획'))
    with repo._connect() as conn:
        row = conn.execute('SELECT prompt FROM script_attempts WHERE id=%s', (attempt,)).fetchone()
        snapshot = json.loads(row['prompt'])
        assert snapshot['submitted_request'] == submitted
        assert snapshot['original_request']['video_model'] == expected_key
        assert snapshot['original_request']['video_duration_seconds'] == expected_duration
        conn.execute('UPDATE video_generation_controls SET model_defaults=%s', (Jsonb({}),))
        assert conn.execute('SELECT prompt FROM script_attempts WHERE id=%s',
                            (attempt,)).fetchone()['prompt'] == row['prompt']
        assert conn.execute('SELECT input FROM customer_requests WHERE id=%s',
                            (rid,)).fetchone()['input'] == submitted
    assert f'{expected_duration}초' in planner_constraints(Settings(_env_file=None), snapshot)
