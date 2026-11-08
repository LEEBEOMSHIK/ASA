from uuid import uuid4

from psycopg.types.json import Jsonb
from test_registry_db import client as client_fixture
from test_registry_db import db as db_fixture
from test_registry_db import script_work

client = client_fixture
db = db_fixture


def test_audio_settings_revision_auth_and_speech_snapshot(client, db):
    headers, work, _ = script_work(client)
    import psycopg

    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)", (db[1], work["id"])
        )
        conn.execute(
            "INSERT INTO script_versions(workspace_id,request_id,version,operation_id,"
            "title,narration,source,answer) VALUES (%s,%s,1,%s,'test','test','ai',%s)",
            (db[1], work["id"], uuid4(), Jsonb({"result": "test"})),
        )
    path = f"/api/v1/audio/work/{work['id']}/1"
    initial = client.get(path)
    assert initial.status_code == 200
    assert initial.json()["revision"] == 0
    settings = {
        "enabled": True,
        "speakers": [{"id": "child", "name": "이루리"}],
        "cues": [{"id": "one", "speaker_id": "child", "text": "안녕", "start": 0, "end": 2}],
    }
    assert client.put(path, json={"revision": 0, "settings": settings}).status_code == 403
    saved = client.put(path, json={"revision": 0, "settings": settings}, headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1
    assert (
        client.put(path, json={"revision": 0, "settings": settings}, headers=headers).status_code
        == 409
    )
    assert client.get(f"/api/v1/audio/work/{uuid4()}/1").status_code == 404
    from asa.registry.repository import migrate

    other, asset = uuid4(), uuid4()
    migrate(db[0], other)
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "INSERT INTO audio_assets(workspace_id,id,name,data,duration,sha256) "
            "VALUES (%s,%s,'foreign',%s,1,'test')",
            (other, asset, b"private"),
        )
    assert client.get(f"/api/v1/audio/assets/{asset}/media").status_code == 404
    settings["music"] = {"asset_id": str(asset)}
    assert (
        client.put(path, json={"revision": 1, "settings": settings}, headers=headers).status_code
        == 404
    )
    assert client.get(path).json()["revision"] == 1
    assert (
        client.post(
            path + "/speech",
            json={"id": str(uuid4()), "revision": 1, "cue_id": "one"},
            headers=headers,
        ).status_code
        == 409
    )


def test_speech_worker_snapshot_timing_and_uncertain_call(db, monkeypatch):
    import psycopg
    from fastapi.testclient import TestClient
    from test_registry_db import KEY

    from asa import audio_worker
    from asa.api import create_app
    from asa.audio_media import pcm_wav
    from asa.audio_worker import AudioWorker
    from asa.config import Settings

    config = Settings(
        _env_file=None,
        database_url=db[0],
        workspace_id=db[1],
        owner_access_key=KEY,
        allowed_origins=["http://testserver"],
        audio_ai_enabled=True,
        audio_api_key="test-only",
    )
    with TestClient(create_app(config)) as client:
        headers, work, _ = script_work(client)
        with psycopg.connect(db[0]) as conn:
            conn.execute(
                "INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)",
                (db[1], work["id"]),
            )
            conn.execute(
                "INSERT INTO script_versions(workspace_id,request_id,version,operation_id,"
                "title,narration,source,answer) VALUES (%s,%s,1,%s,'test','test','ai',%s)",
                (db[1], work["id"], uuid4(), Jsonb({"result": "test"})),
            )
        path = f"/api/v1/audio/work/{work['id']}/1"
        data = {
            "enabled": True,
            "speakers": [{"id": "child", "name": "아이"}],
            "cues": [{"id": "one", "speaker_id": "child", "text": "안녕", "start": 0, "end": 0.5}],
        }
        assert (
            client.put(path, json={"revision": 0, "settings": data}, headers=headers).status_code
            == 200
        )
        # A production voice must first be selected from a reviewed sample.
        from asa.audio_contracts import AudioSettings
        from asa.registry.audio_service import sample_spec, speech_key
        assert client.post(path + '/speech', json={
            'id': str(uuid4()), 'revision': 1, 'cue_id': 'one'}, headers=headers).status_code == 409
        sample_id = uuid4()
        data = client.get(path).json()['settings']
        parsed = AudioSettings.model_validate(data)
        spec = sample_spec(config, parsed, 'child')
        with psycopg.connect(db[0]) as conn:
            conn.execute("INSERT INTO audio_jobs(workspace_id,id,request_id,answer_version,kind,"
                         "cue_id,fingerprint,input,status,media,duration) "
                         "VALUES (%s,%s,%s,1,'speech','child',%s,%s,'approved',%s,1)",
                         (db[1], sample_id, work['id'], speech_key(spec), Jsonb(spec), b'fixture'))
            data['speakers'][0]['sample_job_id'] = str(sample_id)
            conn.execute('UPDATE audio_settings SET settings=%s WHERE workspace_id=%s '
                         'AND request_id=%s', (Jsonb(data), db[1], work['id']))
        operation = {"id": str(uuid4()), "revision": 1, "cue_id": "one"}
        queued = client.post(path + "/speech", json=operation, headers=headers)
        assert queued.status_code == 200, queued.text
        job = queued.json()["id"]
        assert client.post(path + "/speech", json=operation, headers=headers).json()["id"] == job
        calls = []

        def synthesize(*args):
            calls.append(1)
            return pcm_wav(b"\0\0" * 24000), "안녕"

        monkeypatch.setattr(audio_worker, "synthesize", synthesize)
        worker = AudioWorker(config)
        assert worker.tick()
        assert not worker.tick()
        assert len(calls) == 1

        approve = f"/api/v1/audio/jobs/{job}/approve"
        assert client.post(approve, json={}, headers=headers).status_code == 409
        data["cues"][0]["end"] = 2
        assert (
            client.put(path, json={"revision": 1, "settings": data}, headers=headers).status_code
            == 200
        )
        assert client.post(approve, json={}, headers=headers).status_code == 200
        data["cues"][0]["text"] = "다른 말"
        assert (
            client.put(path, json={"revision": 2, "settings": data}, headers=headers).status_code
            == 200
        )
        assert not client.get(path).json()["jobs"][0]["current"]
        assert client.post(approve, json={}, headers=headers).status_code == 409
        second = client.post(
            path + "/speech", json={**operation, "id": str(uuid4()), "revision": 3}, headers=headers
        )
        with psycopg.connect(db[0]) as conn:
            conn.execute(
                "UPDATE audio_jobs SET status='running' WHERE workspace_id=%s AND id=%s",
                (db[1], second.json()["id"]),
            )
        assert not AudioWorker(config).tick()
        assert client.get(path).json()["jobs"][0]["status"] == "unknown"
        assert len(calls) == 1


def test_composition_requires_approval_retries_and_detects_replaced_video(client, db, monkeypatch):
    import psycopg

    from asa import audio_worker
    from asa.audio_worker import AudioWorker
    from asa.config import Settings

    headers, work, _ = script_work(client)
    answer = {
        "model_key": "test",
        "model_revision": "1",
        "aspect_ratio": "16:9",
        "clips": [
            {
                "clip_id": "one",
                "scene_id": "scene",
                "shot_id": "shot",
                "image_id": str(uuid4()),
                "source_start_seconds": 0,
                "source_end_seconds": 1,
                "duration_seconds": 1,
                "prompt": "A quiet room",
                "source_excerpt": "",
                "continuity_in": "",
                "continuity_out": "",
                "split_reason": "",
            }
        ],
    }
    video_id = uuid4()
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)", (db[1], work["id"])
        )
        conn.execute(
            "INSERT INTO script_versions(workspace_id,request_id,version,operation_id,"
            "title,narration,source,answer) VALUES (%s,%s,1,%s,'test','test','ai',%s)",
            (db[1], work["id"], uuid4(), Jsonb(answer)),
        )
        conn.execute(
            "INSERT INTO video_clip_jobs(workspace_id,id,request_id,answer_version,clip_id,"
            "model_snapshot,generation_input,status,video) "
            "VALUES (%s,%s,%s,1,'one','{}','{}','review',%s)",
            (db[1], video_id, work["id"], b"fixture"),
        )
    path = f"/api/v1/audio/work/{work['id']}/1"
    assert (
        client.put(
            path, json={"revision": 0, "settings": {"enabled": True}}, headers=headers
        ).status_code
        == 200
    )
    operation = {"id": str(uuid4()), "revision": 1}
    assert client.post(path + "/compose", json=operation, headers=headers).status_code == 409
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "UPDATE video_clip_jobs SET status='approved' WHERE workspace_id=%s AND id=%s",
            (db[1], video_id),
        )
    first = client.post(path + "/compose", json=operation, headers=headers)
    assert first.status_code == 200, first.text
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "UPDATE audio_jobs SET status='failed' WHERE workspace_id=%s AND id=%s",
            (db[1], first.json()["id"]),
        )
    operation["id"] = str(uuid4())
    second = client.post(path + "/compose", json=operation, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["id"] != first.json()["id"]
    monkeypatch.setattr(audio_worker, "compose", lambda *args: b"fixture-composition")
    assert AudioWorker(Settings(_env_file=None, database_url=db[0], workspace_id=db[1])).tick()
    approve = f"/api/v1/audio/jobs/{second.json()['id']}/approve"
    assert client.post(approve, json={}, headers=headers).status_code == 200
    assert client.get(approve.removesuffix("/approve") + "/media").content == b"fixture-composition"
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "UPDATE video_clip_jobs SET video=%s WHERE workspace_id=%s AND id=%s",
            (b"replacement", db[1], video_id),
        )
    assert not client.get(path).json()["jobs"][0]["current"]
    assert client.post(approve, json={}, headers=headers).status_code == 409
