import hashlib
import json
from pathlib import Path
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from test_registry_db import KEY, definition, login
from test_registry_db import db as db_fixture

from asa import audio_worker
from asa.api import create_app
from asa.audio_contracts import AudioSettings
from asa.audio_media import pcm_wav
from asa.audio_provider import speech_events
from asa.config import Settings
from asa.registry.audio_service import SAMPLE_TEXT

db = db_fixture


def test_prepare_scene_speech_review_retry_and_editing_library(db, monkeypatch):
    config = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                      owner_access_key=KEY, allowed_origins=["http://testserver"],
                      audio_ai_enabled=True, audio_api_key="mock-key")
    calls = []
    media = pcm_wav(b"\x00\x01" * 12000)
    direction = "짧게 숨을 들이킨 뒤 조용히 말한다."

    def synthesize(key, spec):
        assert key == "mock-key"
        text = spec["cue"]["text"]
        if text != SAMPLE_TEXT:
            events = speech_events(spec)
            assert events[0]["session"]["instructions"].endswith(direction)
            assert events[1]["item"]["content"][0]["text"] == "바람이 분다."
            assert "눈을 뜨는 모습" not in events[0]["session"]["instructions"]
        calls.append(text)
        return media, "다른 문장" if len(calls) == 1 else text

    monkeypatch.setattr(audio_worker, "synthesize", synthesize)
    timing = AudioSettings.model_validate({
        "purpose": "timing",
        "speakers": [{"id": "narrator", "name": "내레이터", "role": "narrator"}],
        "cues": [
            {"id": "n1", "speaker_id": "narrator", "text": "바람이 분다.", "start": 2, "end": 5},
        ],
    })
    with TestClient(create_app(config)) as client:
        headers = login(client)
        scene_agent = client.post("/api/v1/agents/save", headers=headers, json={
            **definition(), "after_tasks": {"scene_timing": True},
        })
        assert scene_agent.status_code == 201, scene_agent.text
        scene_id = str(uuid4())
        scene = client.post("/api/v1/work-requests", headers=headers, json={
            "id": scene_id, "agent_id": scene_agent.json()["id"], "version": 1,
            "input": {"topic": "바람 부는 날"},
        })
        scene.raise_for_status()
        with psycopg.connect(db[0]) as conn:
            conn.execute(
                "INSERT INTO script_stages(workspace_id,request_id,head_version) VALUES (%s,%s,1)",
                (db[1], scene_id),
            )
            conn.execute(
                "INSERT INTO script_versions(workspace_id,request_id,version,operation_id,"
                "title,narration,source,answer) VALUES (%s,%s,1,%s,'','','ai',%s)",
                (db[1], scene_id, uuid4(), Jsonb({
                    "clips": [{"clip_id": "s02", "source_start_seconds": 5},
                              {"clip_id": "s01", "source_start_seconds": 3}],
                })),
            )
            conn.execute("INSERT INTO audio_settings VALUES (%s,%s,1,1,%s)",
                         (db[1], scene_id, Jsonb(timing.model_dump(mode="json"))))
        sources = client.get("/api/v1/audio/production-sources", params={"q": "바람"}).json()
        assert [(row["request_id"], row["version"], row["cue_count"]) for row in sources] == [
            (scene_id, 1, 1),
        ]
        assert sources[0]["title"] == "바람 부는 날"
        template = Path(__file__).parents[4] / "docs/agent-templates/speech-producer.json"
        agent = client.post("/api/v1/agents/save", headers=headers,
                            json=json.loads(template.read_text(encoding="utf-8")))
        assert agent.status_code == 201, agent.text
        work_id = str(uuid4())
        payload = {"id": work_id, "agent_id": agent.json()["id"], "version": 1,
                   "input": {"scene_source": f"{scene_id}:1"}}
        bad = {**payload, "input": {"scene_source": f"{uuid4()}:1"}}
        assert client.post("/api/v1/work-requests", json=bad, headers=headers).status_code == 422
        first = client.post("/api/v1/work-requests", json=payload, headers=headers)
        assert first.status_code == 201, first.text
        assert first.json()["result"]["cue_count"] == 1
        duplicate = client.post("/api/v1/work-requests", json=payload, headers=headers)
        assert duplicate.json() == first.json()
        assert client.get(f"/api/v1/work-requests/{work_id}/script").json()["attempts"] == []
        path = f"/api/v1/audio/work/{work_id}/1"
        state = client.get(path).json()
        assert state["settings"]["purpose"] == "production"
        assert state["settings"]["cues"] == [cue.model_dump() for cue in timing.cues]
        assert state["jobs"] == [] and calls == []
        review_id, clip_job_id = str(uuid4()), str(uuid4())
        candidate = {
            "text": "바람이 분다.", "start_seconds": 0.8, "end_seconds": 2.3,
            "observed": "눈을 뜨는 모습", "delivery": direction, "basis": "event",
        }
        with psycopg.connect(db[0]) as conn:
            conn.execute("INSERT INTO video_clip_jobs(workspace_id,id,request_id,answer_version,"
                         "clip_id,model_snapshot,generation_input,status,video) "
                         "VALUES (%s,%s,%s,1,'s01',%s,%s,'review',%s)",
                         (db[1], clip_job_id, scene_id, Jsonb({}), Jsonb({}), b"synthetic-video"))
            conn.execute("INSERT INTO video_asset_reviews(workspace_id,id,job_id,agent_ref,"
                         "definition,generation_input,video_sha256,status,result,finished_at) "
                         "VALUES (%s,%s,%s,'fixture',%s,%s,%s,'succeeded',%s,now())",
                         (db[1], review_id, clip_job_id, Jsonb({}), Jsonb({}),
                          hashlib.sha256(b"synthetic-video").hexdigest(),
                          Jsonb({"speech_suggestions": [
                              candidate, {**candidate, "start_seconds": 3},
                              {**candidate, "text": "다른 문장"},
                              {**candidate, "basis": "mouth"},
                          ]})))
        selected_sources = client.get(path + "/video-timing-sources", params={"cue_id": "n1"})
        assert selected_sources.status_code == 200, selected_sources.text
        assert selected_sources.json()[0]["timeline_start"] == 3
        assert [{key: item[key] for key in ("review_id", "suggestion", "job_id", "delivery")}
                for item in selected_sources.json()] == [
                    {"review_id": review_id, "suggestion": 0,
                     "job_id": clip_job_id, "delivery": direction},
                ]
        assert client.get(
            f"/api/v1/audio/work/{scene_id}/1/video-timing-sources", params={"cue_id": "n1"}
        ).status_code == 422
        state["settings"]["cues"][0]["text"] = "다른 문장"
        assert client.put(path, headers=headers, json={
            "revision": state["revision"], "settings": state["settings"],
        }).status_code == 422
        cue = state["settings"]["cues"][0]
        cue.update(text="바람이 분다.", start=3.8, end=5.3, emotion=direction)
        cue["video_timing"] = {"review_id": review_id, "suggestion": 2, "clip_offset": 3}
        assert client.put(path, headers=headers, json={
            "revision": state["revision"], "settings": state["settings"],
        }).status_code == 422
        cue["video_timing"]["suggestion"] = 0
        save = client.put(path, headers=headers, json={
            "revision": state["revision"], "settings": state["settings"],
        })
        assert save.status_code == 200, save.text
        assert save.json()["settings"]["cues"][0] == cue
        state = save.json()
        sample = {"id": str(uuid4()), "revision": state["revision"], "cue_id": "narrator"}
        client.post(path + "/sample", json=sample, headers=headers).raise_for_status()
        worker = audio_worker.AudioWorker(config)
        assert worker.tick() and calls == [SAMPLE_TEXT]
        rejected = client.post(path + "/select-voice", json=sample, headers=headers)
        assert rejected.status_code == 409
        sample = {**sample, "id": str(uuid4()), "retry_job_id": sample["id"]}
        client.post(path + "/sample", json=sample, headers=headers).raise_for_status()
        assert worker.tick() and calls == [SAMPLE_TEXT, SAMPLE_TEXT]
        selected = client.post(path + "/select-voice", json=sample, headers=headers)
        assert selected.status_code == 200, selected.text
        speech = {"id": str(uuid4()), "revision": selected.json()["revision"], "cue_id": "n1"}
        client.post(path + "/speech", json=speech, headers=headers).raise_for_status()
        assert worker.tick() and calls[-1] == "바람이 분다." and len(calls) == 3
        approve_path = f"/api/v1/audio/jobs/{speech['id']}/approve"
        client.post(approve_path, headers=headers).raise_for_status()
        sources = client.get("/api/v1/editing/sources?kind=audio").json()["items"]
        assert [(row["id"], row["title"]) for row in sources] == [
            ("audio:" + speech["id"], "내레이터 · 바람이 분다."),
        ]
        preview = client.get(f"/api/v1/admin/work-history/{work_id}/preview").json()
        assert any("음성 기록" in blocker for blocker in preview["blockers"])
        retry = {**speech, "id": str(uuid4()), "retry_job_id": speech["id"]}
        queued = client.post(path + "/speech", json=retry, headers=headers)
        assert queued.status_code == 200 and queued.json()["id"] == retry["id"]
        assert client.post(path + "/speech", json=retry, headers=headers).json() == queued.json()
        assert client.post(path + "/speech", json={**retry, "id": str(uuid4())},
                           headers=headers).status_code == 409
        assert worker.tick() and calls[-2:] == ["바람이 분다.", "바람이 분다."]
        assert next(job for job in client.get(path).json()["jobs"]
                    if job["id"] == speech["id"])["status"] == "approved"

        # The applied source remains discoverable after newer reviews fill the list.
        with psycopg.connect(db[0]) as conn:
            conn.execute(
                "INSERT INTO video_asset_reviews(workspace_id,id,job_id,agent_ref,definition,"
                "generation_input,video_sha256,status,result,finished_at) "
                "SELECT workspace_id,gen_random_uuid(),job_id,agent_ref,definition,"
                "generation_input,video_sha256,status,%s,now() FROM video_asset_reviews CROSS JOIN "
                "generate_series(1,24) WHERE id=%s",
                (Jsonb({"speech_suggestions": [candidate]}), review_id),
            )
        sources = client.get(path + "/video-timing-sources", params={"cue_id": "n1"}).json()
        assert len(sources) == 24 and sources[0]["review_id"] == review_id

        # Losing access to an earlier source does not invalidate speech or block settings edits.
        with psycopg.connect(db[0]) as conn:
            conn.execute("DELETE FROM video_asset_reviews WHERE id=%s", (review_id,))
        state = client.get(path).json()
        cue = state["settings"]["cues"][0]
        cue["start"] += 0.1
        client.put(path, headers=headers, json={
            "revision": state["revision"], "settings": state["settings"],
        }).raise_for_status()
        state = client.get(path).json()
        cue = state["settings"]["cues"][0]
        cue["video_timing"]["clip_offset"] += 1
        assert client.put(path, headers=headers, json={
            "revision": state["revision"], "settings": state["settings"],
        }).status_code == 422
        cue.pop("video_timing")
        saved = client.put(path, headers=headers, json={
            "revision": state["revision"], "settings": state["settings"],
        })
        saved.raise_for_status()
        assert "video_timing" not in saved.json()["settings"]["cues"][0]
        assert next(job for job in saved.json()["jobs"]
                    if job["id"] == speech["id"])["status"] == "approved"
        assert client.get(f"/api/v1/audio/work/{scene_id}/1").json()["settings"] == (
            timing.model_dump(mode="json")
        )
