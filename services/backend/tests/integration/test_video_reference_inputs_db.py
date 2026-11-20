from uuid import uuid4

import httpx
import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_registry_db import client as client_fixture
from test_registry_db import db as database_fixture
from test_registry_db import test_wan_queue_worker_lifecycle as seed

from asa.config import Settings
from asa.registry.schemas import RegistryError
from asa.video_references import freeze, image_bytes, resolve_media
from asa.video_worker import process

db = database_fixture
client = client_fixture


def test_reference_image_freeze_scope_approval_and_worker_guard(client, db, monkeypatch):
    seed(client, db, monkeypatch, 'success')
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        video_ai_enabled=True, wan_api_key='test-wan', wan_workspace_id='ws-test')
    with psycopg.connect(db[0], row_factory=dict_row, autocommit=True) as conn:
        job = conn.execute('SELECT * FROM video_clip_jobs').fetchone()
        image = job['generation_input']['start_image_id']
        with pytest.raises(RegistryError):
            image_bytes(conn, db[1], image)  # Successful bytes alone are not approval.
        conn.execute('UPDATE character_projects SET approved=%s', (Jsonb({'a': image}),))
        with pytest.raises(RegistryError):
            image_bytes(conn, uuid4(), image)
        spec = {**job['generation_input'], 'reference_inputs': {
            'character_image_ids': [], 'audio': []}}
        freeze(conn, settings, db[1], job['request_id'], spec, {'scenes': []})
        job['generation_input'] = spec
        data, media = resolve_media(conn, settings, db[1], job)
        assert data and media == []
        assert spec['reference_images'][0]['role'] == 'scene'
        conn.execute("UPDATE video_clip_jobs SET generation_input=%s,status='queued',"
                     "provider_task=NULL,next_poll=now() WHERE id=%s", (Jsonb(spec), job['id']))
        conn.execute("UPDATE character_projects SET approved='{}'")
        with httpx.Client(transport=httpx.MockTransport(
            lambda request: pytest.fail('ineligible reference must never reach provider')),
        ) as http:
            assert process(conn, http, db[1], settings)
        failed = conn.execute('SELECT status,error_code FROM video_clip_jobs WHERE id=%s',
                              (job['id'],)).fetchone()
        assert failed['status'] == 'failed'
        assert failed['error_code'] == 'input_invalid'


def test_higgsfield_frozen_video_reference_upload_submit_and_poll(client, db, monkeypatch):
    seed(client, db, monkeypatch, 'success')
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        video_ai_enabled=True, higgsfield_api_key='test-higgsfield')
    model = next(m for m in settings.video_model_profiles.values() if m.provider == 'higgsfield')
    ident = uuid4()
    with psycopg.connect(db[0], row_factory=dict_row, autocommit=True) as conn:
        original = conn.execute('SELECT * FROM video_clip_jobs').fetchone()
        image = original['generation_input']['start_image_id']
        conn.execute('UPDATE character_projects SET approved=%s', (Jsonb({'a': image}),))
        spec = {**original['generation_input'], 'reference_inputs': {
            'character_image_ids': [], 'audio': [], 'video': [{'job_id': str(original['id'])}]}}
        freeze(conn, settings, db[1], original['request_id'], spec, {'scenes': []}, 'higgsfield')
        assert spec['reference_video']['source_sha256']
        conn.execute('INSERT INTO video_clip_jobs(workspace_id,id,request_id,answer_version,'
                     'clip_id,model_snapshot,generation_input,status) '
                     "VALUES(%s,%s,%s,1,'hf-clip',%s,%s,'queued')",
                     (db[1], ident, original['request_id'], Jsonb(model.model_dump()), Jsonb(spec)))
        uploads = []

        def upload(cfg, snapshot, data, mime):
            state = conn.execute('SELECT status FROM video_clip_jobs WHERE id=%s',
                                 (ident,)).fetchone()
            assert state['status'] == 'submitting'
            uploads.append((data, mime))
            return 'https://media.example/' + ('source.mp4' if mime == 'video/mp4' else 'image.png')

        monkeypatch.setattr('asa.higgsfield_provider.upload_media', upload)
        requests = []

        def respond(request):
            requests.append(request)
            if request.method == 'POST':
                import json
                assert request.headers['Idempotency-Key'] == str(ident)
                assert json.loads(request.content)['video_urls'] == ['https://media.example/source.mp4']
                return httpx.Response(200, json={'request_id': 'hf-task'})
            assert request.url.path == '/requests/hf-task/status'
            return httpx.Response(200, json={'status': 'completed',
                                            'video': {'url': 'https://media.example/result.mp4'}})

        with httpx.Client(transport=httpx.MockTransport(respond)) as http:
            assert process(conn, http, db[1], settings)
            conn.execute('UPDATE video_clip_jobs SET next_poll=now() WHERE id=%s', (ident,))
            assert process(conn, http, db[1], settings)
        assert [r.method for r in requests] == ['POST', 'GET']
        assert [m for _, m in uploads] == ['image/png', 'video/mp4']
        assert uploads[1][0] == bytes(original['video'])
        assert conn.execute('SELECT status FROM video_clip_jobs WHERE id=%s',
                            (ident,)).fetchone()['status'] == 'review'
        kept = conn.execute('SELECT model_snapshot,video FROM video_clip_jobs WHERE id=%s',
                            (original['id'],)).fetchone()
        assert kept['model_snapshot']['provider'] == 'alibaba'
        assert kept['video'] == original['video']
