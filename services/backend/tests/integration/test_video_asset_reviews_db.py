from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_registry_db import db as database_fixture
from test_registry_db import definition

from asa.config import Settings
from asa.registry import video_asset_reviews as reviews
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import AgentDraft, RegistryError

db = database_fixture


@pytest.fixture
def seeded(db, monkeypatch):
    repo = RegistryRepository(*db)
    agent = repo.create(AgentDraft.model_validate(definition()))
    repo.publish(agent['id'], 1)
    aid = UUID(agent['id'])
    rid, jid = uuid4(), uuid4()
    cfg = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                   script_ai_enabled=True, ai_model='test-model', ai_models=['test-model'],
                   ai_api_key='test-only-key')
    monkeypatch.setattr(reviews, 'effective_settings', lambda settings, conn=None: settings)
    monkeypatch.setattr(reviews, 'validate_review_model', lambda *args: None)
    spec = {'prompt': 'frozen prompt', 'duration_seconds': 3,
            'voice_direction_prompt': 'frozen voice', 'visual_style': 'frozen style'}
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        conn.execute('INSERT INTO customer_requests(workspace_id,id,agent_id,version,input) '
                     'VALUES (%s,%s,%s,1,%s)', (db[1], rid, aid, Jsonb({'topic': 'test'})))
        conn.execute('INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)',
                     (db[1], rid))
        conn.execute('INSERT INTO script_versions(workspace_id,request_id,version,operation_id,'
                     "title,narration,source) VALUES (%s,%s,1,%s,'test','test','manual')",
                     (db[1], rid, uuid4()))
        conn.execute('INSERT INTO video_clip_jobs('
                     'workspace_id,id,request_id,answer_version,clip_id,'
                     "model_snapshot,generation_input,status,video) VALUES (%s,%s,%s,1,'c1',%s,%s,"
                     "'review',%s)", (db[1], jid, rid, Jsonb({}), Jsonb(spec), b'frozen-video'))
        saved_definition = dict(conn.execute('SELECT definition FROM registry_versions '
            'WHERE workspace_id=%s AND agent_id=%s', (db[1], aid)).fetchone()['definition'])
        saved_definition['after_tasks'] = {'video_review': {'agent_ref': f'agent:{aid}:1',
                                                           'mode': 'manual'}}
        conn.execute('INSERT INTO registry_versions(workspace_id,agent_id,version,source_revision,'
                     "definition,digest) VALUES (%s,%s,2,2,%s,'test')",
                     (db[1], aid, Jsonb(saved_definition)))
    return cfg, aid, jid, spec


def test_review_snapshot_idempotency_isolation_disabled_history(db, seeded):
    cfg, aid, jid, spec = seeded
    review_id = uuid4()
    with psycopg.connect(db[0], row_factory=dict_row, autocommit=True) as conn:
        with conn.transaction():
            assert reviews.enqueue(conn, db[1], jid, review_id, cfg)['status'] == 'queued'
        row = conn.execute('SELECT * FROM video_asset_reviews').fetchone()
        assert row['generation_input'] == spec
        assert row['agent_ref'] == f'agent:{aid}:2'
        assert row['definition']['model'] == 'test-model'
        with conn.transaction():
            assert reviews.enqueue(conn, db[1], jid, review_id, cfg)['id'] == str(review_id)
        with pytest.raises(RegistryError, match='review_already_running'):
            with conn.transaction():
                reviews.enqueue(conn, db[1], jid, uuid4(), cfg)
        with pytest.raises(RegistryError, match='video_job_missing'):
            with conn.transaction():
                reviews.enqueue(conn, uuid4(), jid, uuid4(), cfg)
        # Latest saved owner config is disabled, original request remains version 1.
        conn.execute('INSERT INTO registry_versions(workspace_id,agent_id,version,source_revision,'
                     "definition,digest) VALUES (%s,%s,3,3,%s,'disabled')",
                     (db[1], aid, Jsonb(definition())))
        assert reviews.process_review(conn, db[1], cfg)
        row = conn.execute('SELECT * FROM video_asset_reviews').fetchone()
        assert row['status'] == 'failed' and row['error_code'] == 'review_disabled'
        assert row['generation_input'] == spec
        with conn.transaction():
            assert reviews.enqueue(conn, db[1], jid, review_id, cfg)['status'] == 'failed'
        with pytest.raises(RegistryError, match='review_disabled'):
            with conn.transaction():
                reviews.enqueue(conn, db[1], jid, uuid4(), cfg)


def test_worker_uses_snapshot_and_never_changes_video_or_retries(db, seeded, monkeypatch):
    cfg, aid, jid, spec = seeded
    rid = uuid4()
    calls = []
    def fake_review(settings, review, video):
        calls.append((review['generation_input'], video, review['definition']))
        return {'summary': 'observed', 'checks': [], 'limitations': ['sampled']}
    monkeypatch.setattr(reviews, 'review_video', fake_review)
    with psycopg.connect(db[0], row_factory=dict_row, autocommit=True) as conn:
        with conn.transaction():
            reviews.enqueue(conn, db[1], jid, rid, cfg)
        conn.execute('UPDATE video_clip_jobs SET generation_input=%s WHERE id=%s',
                     (Jsonb({'prompt': 'later mutable value'}), jid))
        assert reviews.process_review(conn, db[1], cfg)
        assert not reviews.process_review(conn, db[1], cfg)
        assert len(calls) == 1 and calls[0][0] == spec and calls[0][1] == b'frozen-video'
        row = conn.execute('SELECT * FROM video_asset_reviews').fetchone()
        assert row['status'] == 'succeeded'
        assert conn.execute('SELECT status FROM video_clip_jobs').fetchone()['status'] == 'review'
        assert conn.execute("SELECT count(*) AS n FROM ai_usage_events WHERE step_name="
                            "'생성 영상 AI 검수'").fetchone()['n'] == 1
        with conn.transaction():
            reviews.enqueue(conn, db[1], jid, uuid4(), cfg)
        def failure(*args):
            raise RuntimeError('provider response lost')
        monkeypatch.setattr(reviews, 'review_video', failure)
        assert reviews.process_review(conn, db[1], cfg)
        assert not reviews.process_review(conn, db[1], cfg)


def test_daily_limit_and_disabled_ai_block_without_enqueue(db, seeded):
    cfg, _, jid, _ = seeded
    with psycopg.connect(db[0], row_factory=dict_row, autocommit=True) as conn:
        with pytest.raises(RegistryError, match='script_ai_disabled'):
            with conn.transaction():
                reviews.enqueue(conn, db[1], jid, uuid4(),
                                cfg.model_copy(update={'script_ai_enabled': False}))
        assert conn.execute('SELECT count(*) AS n FROM video_asset_reviews').fetchone()['n'] == 0
        with conn.transaction():
            reviews.enqueue(conn, db[1], jid, uuid4(), cfg)
        conn.execute("UPDATE video_asset_reviews SET status='failed'")
        with pytest.raises(RegistryError, match='review_daily_limit'):
            with conn.transaction():
                reviews.enqueue(conn, db[1], jid, uuid4(),
                                cfg.model_copy(update={'script_daily_ai_calls': 1}))


def test_continuation_reference_matches_saved_hash_and_recovery_is_scoped(db, seeded):
    import hashlib
    cfg, _, jid, spec = seeded
    rid = uuid4()
    with psycopg.connect(db[0], row_factory=dict_row, autocommit=True) as conn:
        spec.update(connection_type='continue', source_job_id=str(jid),
                    source_video_sha256=hashlib.sha256(b'frozen-video').hexdigest())
        conn.execute('UPDATE video_clip_jobs SET generation_input=%s', (Jsonb(spec),))
        with conn.transaction():
            reviews.enqueue(conn, db[1], jid, rid, cfg)
        row = conn.execute('SELECT * FROM video_asset_reviews').fetchone()
        assert bytes(row['source_video']) == b'frozen-video'
        assert row['reference_image'] is None
        conn.execute("UPDATE video_asset_reviews SET status='running'")
        reviews.recover_reviews(conn, uuid4())
        row = conn.execute('SELECT status FROM video_asset_reviews').fetchone()
        assert row['status'] == 'running'
        reviews.recover_reviews(conn, db[1])
        row = conn.execute('SELECT * FROM video_asset_reviews').fetchone()
        assert row['status'] == 'unknown' and row['error_code'] == 'worker_interrupted'
        assert not reviews.process_review(conn, db[1], cfg)
        spec['source_video_sha256'] = 'different-hash'
        conn.execute('UPDATE video_clip_jobs SET generation_input=%s', (Jsonb(spec),))
        second_id = uuid4()
        with conn.transaction():
            reviews.enqueue(conn, db[1], jid, second_id, cfg)
        row = conn.execute('SELECT source_video FROM video_asset_reviews WHERE id=%s',
                           (second_id,)).fetchone()
        assert row['source_video'] is None


def test_review_api_authentication_history_and_no_generation_changes(db, seeded, monkeypatch):
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from test_registry_db import KEY, login

    from asa.api import create_app
    cfg, _, jid, _ = seeded
    cfg = cfg.model_copy(update={'owner_access_key': SecretStr(KEY),
                                 'allowed_origins': ['http://testserver']})
    path = f'/api/v1/video-clips/jobs/{jid}/reviews'
    with TestClient(create_app(cfg)) as client:
        assert client.get(path).status_code == 401
        headers = login(client)
        # Polling must not load the generated video or immutable reference bytes.
        def no_video_load(*args):
            raise AssertionError('GET must not load full video')
        with monkeypatch.context() as lightweight:
            lightweight.setattr(reviews, 'load_job', no_video_load)
            data = client.get(path).json()
        assert data['configured'] and data['available'] and data['reviews'] == []
        assert client.post(path, json={'id': str(uuid4())}).status_code == 403
        body = {'id': str(uuid4())}
        first = client.post(path, json=body, headers=headers)
        assert first.status_code == 200, first.text
        assert client.post(path, json=body, headers=headers).json() == first.json()
        data = client.get(path).json()
        assert len(data['reviews']) == 1 and data['reviews'][0]['status'] == 'queued'
        assert 'definition' not in data['reviews'][0]
        assert client.get(f'/api/v1/video-clips/jobs/{uuid4()}/reviews').status_code == 404


def test_preview_media_serves_byte_ranges_without_changing_assets(db, seeded):
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from test_registry_db import KEY, login

    from asa.api import create_app

    cfg, _, jid, _ = seeded
    cfg = cfg.model_copy(update={'owner_access_key': SecretStr(KEY),
                                 'allowed_origins': ['http://testserver']})
    audio_id, retained_id, deleted_id = uuid4(), uuid4(), uuid4()
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "INSERT INTO audio_jobs(workspace_id,id,request_id,answer_version,kind,fingerprint,"
            "input,status,media) SELECT workspace_id,%s,request_id,answer_version,'speech',"
            "'preview-audio',%s,'review',%s FROM video_clip_jobs WHERE id=%s",
            (audio_id, Jsonb({}), b'frozen-audio', jid),
        )
        conn.execute(
            "INSERT INTO work_deletions(workspace_id,request_id,name,actor,summary) "
            "VALUES (%s,%s,'fixture','fixture',%s)",
            (db[1], deleted_id, Jsonb({})),
        )
        conn.execute(
            "INSERT INTO retained_work_videos(workspace_id,id,request_id,clip_id,answer_version,"
            "video) VALUES (%s,%s,%s,'c1',1,%s)",
            (db[1], retained_id, deleted_id, b'retained-video'),
        )
    cases = (
        (f'/api/v1/video-clips/asset/{jid}/video', b'frozen-video', 'video/mp4'),
        (f'/api/v1/video-clips/asset/{retained_id}/video', b'retained-video', 'video/mp4'),
        (f'/api/v1/audio/jobs/{audio_id}/media', b'frozen-audio', 'audio/wav'),
    )
    with TestClient(create_app(cfg)) as client:
        assert client.get(cases[0][0], headers={'Range': 'bytes=0-3'}).status_code == 401
        assert client.get(cases[2][0], headers={'Range': 'bytes=0-3'}).status_code == 401
        login(client)
        for path, source, media_type in cases:
            for header, start, end in (
                ('bytes=2-4', 2, 4),
                ('bytes=3-', 3, len(source) - 1),
                ('bytes=-3', len(source) - 3, len(source) - 1),
            ):
                part = client.get(path, headers={'Range': header})
                assert part.status_code == 206
                assert part.headers['content-range'] == f'bytes {start}-{end}/{len(source)}'
                assert part.headers['content-type'] == media_type
                assert part.content == source[start:end + 1]
            invalid = client.get(path, headers={'Range': 'bytes=999-'})
            assert invalid.status_code == 416
            assert invalid.headers['content-range'] == f'bytes */{len(source)}'
            full = client.get(path)
            assert full.status_code == 200 and full.content == source
            assert full.headers['accept-ranges'] == 'bytes'
        missing = client.get(
            f'/api/v1/video-clips/asset/{uuid4()}/video', headers={'Range': 'bytes=999-'},
        )
        assert missing.status_code == 404
