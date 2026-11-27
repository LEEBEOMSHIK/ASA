from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from test_registry_db import KEY, script_work
from test_registry_db import db as db_fixture

from asa import audio_worker
from asa.api import create_app
from asa.audio_contracts import AudioModel
from asa.audio_media import pcm_wav
from asa.config import Settings
from asa.registry.audio_service import SAMPLE_TEXT

db = db_fixture


def test_typecast_worker_reserves_two_calls_and_blocks_unverified_voice(db, monkeypatch):
    config = Settings(
        _env_file=None, database_url=db[0], workspace_id=db[1], owner_access_key=KEY,
        allowed_origins=["http://testserver"], audio_ai_enabled=True, audio_daily_calls=3,
        audio_api_key="test-openai", audio_typecast_api_key="test-typecast",
        audio_transcription_model="gpt-transcribe",
        audio_model_profiles={
            "openai-realtime": AudioModel(),
            "typecast": AudioModel(provider="typecast", model="ssfm-v30", voices=["tc_test"]),
        },
    )
    media = pcm_wav(b"\x00\x01" * 24000)
    calls = []

    def typecast(key, transcription_key, transcription_model, spec, ffmpeg):
        assert (key, transcription_key, transcription_model) == (
            "test-typecast", "test-openai", "gpt-transcribe",
        )
        assert spec["model"]["provider"] == "typecast"
        calls.append("typecast")
        return media, None

    def realtime(key, spec):
        assert key == "test-openai"
        assert "provider" not in spec["model"]
        calls.append("openai")
        return media, SAMPLE_TEXT

    monkeypatch.setattr(audio_worker, "synthesize_typecast", typecast)
    monkeypatch.setattr(audio_worker, "synthesize", realtime)
    with TestClient(create_app(config)) as client:
        headers, work, _ = script_work(client)
        voice = {"model_key": "typecast", "voice": "tc_test"}
        speakers = [
            {"id": "child", "name": "아이", "voice": voice},
            {"id": "parent", "name": "부모", "voice": voice},
            {"id": "third", "name": "세 번째 화자"},
        ]
        with psycopg.connect(db[0]) as conn:
            conn.execute("INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)",
                         (db[1], work["id"]))
            conn.execute(
                "INSERT INTO script_versions(workspace_id,request_id,version,operation_id,"
                "title,narration,source,answer) VALUES (%s,%s,1,%s,'test','test','ai',%s)",
                (db[1], work["id"], uuid4(), Jsonb({"characters": speakers})),
            )
        path = f"/api/v1/audio/work/{work['id']}/1"
        saved = client.put(path, json={"revision": 0, "settings": {"speakers": speakers}},
                           headers=headers)
        assert saved.status_code == 200, saved.text
        jobs = {}
        for cue_id in ("child", "parent", "third"):
            operation = {"id": str(uuid4()), "revision": 1, "cue_id": cue_id}
            queued = client.post(path + "/sample", json=operation, headers=headers)
            assert queued.status_code == 200, queued.text
            jobs[cue_id] = operation

        worker = audio_worker.AudioWorker(config)
        assert worker.tick()
        assert worker.tick()
        assert not worker.tick()
        assert calls == ["typecast", "openai"]

        work_jobs = {job["id"]: job for job in client.get(path).json()["jobs"]}
        first = work_jobs[jobs["child"]["id"]]
        assert first["status"] == "review"
        assert first["error_code"] == "audio_transcript_unverified"
        assert work_jobs[jobs["parent"]["id"]]["status"] == "queued"
        response = client.get(f"/api/v1/audio/jobs/{first['id']}/media")
        assert response.content == media
        unverified = client.post(path + "/select-voice", json=jobs["child"], headers=headers)
        assert unverified.status_code == 409
        verified = client.post(path + "/select-voice", json=jobs["third"], headers=headers)
        assert verified.status_code == 200
