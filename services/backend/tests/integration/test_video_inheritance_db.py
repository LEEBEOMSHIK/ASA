from copy import deepcopy
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_registry_db import KEY, login
from test_registry_db import client as client_fixture
from test_registry_db import db as database_fixture
from test_registry_db import test_wan_queue_worker_lifecycle as seed

from asa.api import create_app
from asa.config import Settings

db = database_fixture
client = client_fixture


@pytest.mark.parametrize('changed', ['', 'prompt', 'image', 'audio', 'snapshot'])
def test_new_version_reuses_only_unchanged_video(client, db, monkeypatch, changed):
    seed(client, db, monkeypatch, 'success')
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        owner_access_key=KEY, allowed_origins=['http://testserver'],
                        video_ai_enabled=True, wan_api_key='test-wan', wan_workspace_id='ws-test')
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        job = conn.execute('SELECT * FROM video_clip_jobs').fetchone()
        row = conn.execute('SELECT * FROM script_versions WHERE version=1').fetchone()
        answer = deepcopy(row['answer'])
        if changed == 'prompt':
            answer['clips'][0]['prompt'] = 'A fox runs'
        elif changed == 'image':
            answer['clips'][0]['image_id'] = str(uuid4())
        elif changed == 'audio':
            answer['audio'] = True
        elif changed == 'snapshot':
            conn.execute("UPDATE video_clip_jobs SET generation_input="
                         "jsonb_set(generation_input,'{voice_direction_prompt}',%s)",
                         (Jsonb('different saved voice'),))
        conn.execute('INSERT INTO script_versions(workspace_id,request_id,version,operation_id,'
                     'title,narration,'
                     'answer,source,base_version) VALUES(%s,%s,4,%s,%s,%s,%s,%s,1)',
                     (db[1], job['request_id'], uuid4(), row['title'], row['narration'],
                      Jsonb(answer),
                      row['source']))
        conn.execute('UPDATE script_stages SET head_version=4')
    path = f"/api/v1/video-clips/{job['request_id']}/4"
    with TestClient(create_app(settings)) as api:
        headers = login(api)
        result = api.get(path)
        assert result.status_code == 200, result.text
        data = result.json()
        if changed:
            assert data['jobs'] == []
            assert data['changed_clips'] == [job['clip_id']]
            assert data['previous_attempts'][0]['id'] == str(job['id'])
            assert api.post(path+'/approve', headers=headers, json={
                'clip_ids': [job['clip_id']]}).status_code == 409
        else:
            assert len(data['jobs']) == 1
            assert data['jobs'][0]['id'] == str(job['id'])
            assert data['jobs'][0]['answer_version'] == 1
            assert data['jobs'][0]['inherited'] is True
            assert api.post(path, headers=headers, json={
                'clip_ids': [job['clip_id']]}).json() == {'queued': 0}
            assert api.post(path+'/approve', headers=headers, json={
                'clip_ids': [job['clip_id']]}).status_code == 200
            assert api.get(path).json()['jobs'][0]['status'] == 'approved'
            from asa.registry.video_inheritance import resolve
            from asa.video_continuity import approved_source
            with psycopg.connect(db[0], row_factory=dict_row) as conn:
                assert approved_source(conn, db[1], job['request_id'], 4,
                                       job['clip_id'])['source_job_id'] == str(job['id'])
                for state in ['queued', 'submitting', 'running', 'unknown', 'failed']:
                    conn.execute('UPDATE video_clip_jobs SET status=%s', (state,))
                    resolved = resolve(conn, db[1], job['request_id'], 4)
                    assert resolved['jobs'][0]['status'] == state
                    assert resolved['jobs'][0]['id'] == job['id']
                conn.rollback()
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        jobs = conn.execute('SELECT * FROM video_clip_jobs').fetchall()
        assert len(jobs) == 1
        assert jobs[0]['video'] == job['video']
        assert jobs[0]['answer_version'] == 1


def test_inherited_continuation_requires_same_approved_parent(client, db, monkeypatch):
    from hashlib import sha256

    from asa.registry.video_inheritance import resolve
    from asa.video_continuity import source_video

    seed(client, db, monkeypatch, 'success', continuation=True)
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        parent = conn.execute('SELECT * FROM video_clip_jobs').fetchone()
        row = conn.execute('SELECT * FROM script_versions WHERE version=1').fetchone()
        conn.execute("UPDATE video_clip_jobs SET status='approved'")
        conn.execute('INSERT INTO script_versions(workspace_id,request_id,version,operation_id,'
                     'title,narration,answer,source) VALUES(%s,%s,4,%s,%s,%s,%s,%s)',
                     (db[1], parent['request_id'], uuid4(), row['title'], row['narration'],
                      Jsonb(row['answer']), row['source']))
        child_id = uuid4()
        spec = {**parent['generation_input'], 'connection_type': 'continue',
                'previous_clip_id': 'clip1', 'source_job_id': str(parent['id']),
                'source_video_sha256': sha256(bytes(parent['video'])).hexdigest()}
        conn.execute('INSERT INTO video_clip_jobs(workspace_id,id,request_id,answer_version,'
                     'clip_id,model_snapshot,generation_input,status,video) '
                     "VALUES(%s,%s,%s,1,'clip2',%s,%s,'review',%s)",
                     (db[1], child_id, parent['request_id'], Jsonb(parent['model_snapshot']),
                      Jsonb(spec), b'child-video'))
        linked = resolve(conn, db[1], parent['request_id'], 4)
        assert [r['id'] for r in linked['jobs']] == [parent['id'], child_id]
        assert all(r['inherited'] for r in linked['jobs'])
        child = {**linked['jobs'][1], 'answer_version': 4}
        assert source_video(conn, db[1], child) == parent['video']
        conn.execute('UPDATE video_clip_jobs SET video=%s WHERE id=%s',
                     (b'changed-parent', parent['id']))
        linked = resolve(conn, db[1], parent['request_id'], 4)
        assert [r['id'] for r in linked['jobs']] == [parent['id']]
        assert 'clip2' in linked['changed_clips']
        with pytest.raises(ValueError, match='reference_changed'):
            source_video(conn, db[1], child)
