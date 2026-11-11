import json
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_registry_db import client as client_fixture
from test_registry_db import db as db_fixture
from test_registry_db import script_work

from asa.config import Settings
from asa.registry import audio_service, video_planning
from asa.registry.schemas import RegistryError
from asa.video_contracts import VideoPreparation
from asa.video_providers import generation_request
from asa.voice_directions import snapshot

client = client_fixture
db = db_fixture


def test_directions_storage_snapshot_and_real_provider_payload(client, db, monkeypatch):
    headers, work, _ = script_work(client)
    rid, project, image, operation = UUID(work["id"]), uuid4(), uuid4(), uuid4()
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        conn.execute(
            "INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)", (db[1], rid)
        )
        conn.execute(
            "INSERT INTO script_versions(workspace_id,request_id,version,operation_id,"
            "title,narration,source,answer) VALUES(%s,%s,1,%s,'','','ai',%s)",
            (db[1], rid, operation, Jsonb({"characters": [{"id": "child", "name": "아이"}]})),
        )
        conn.execute(
            "INSERT INTO character_projects(workspace_id,id,request_id,name,characters) "
            "VALUES(%s,%s,%s,'p','[]')",
            (db[1], project, rid),
        )
        conn.execute(
            "INSERT INTO character_image_jobs(workspace_id,id,project_id,character_id,"
            "version,model,character,change,status,image) "
            "VALUES(%s,%s,%s,'child',1,'test','{}','','succeeded',%s)",
            (db[1], image, project, b"image"),
        )
    path = f"/api/v1/audio/work/{rid}/1"
    initial = client.get(path).json()["settings"]
    initial["speakers"][0]["voice"]["voice"] = "cedar"
    assert (
        client.put(path, json={"revision": 0, "settings": initial}, headers=headers).status_code
        == 200
    )
    edit = {
        "revision": 1,
        "speakers": [
            {
                "id": "child",
                "instructions": "높고 맑은 아이 목소리",
                "language": "한국어",
                "speed": 1,
            },
            {"id": "narrator", "instructions": "차분한 중저음", "language": "한국어", "speed": 1},
        ],
    }
    assert client.put(path + "/voice-directions", json=edit).status_code == 403
    saved = client.put(path + "/voice-directions", json=edit, headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["settings"]["speakers"][0]["voice"]["voice"] == "cedar"
    assert client.put(path + "/voice-directions", json=edit, headers=headers).status_code == 409
    assert (
        client.put(
            f"/api/v1/audio/work/{uuid4()}/1/voice-directions", json=edit, headers=headers
        ).status_code
        == 404
    )
    selection = {
        "format": "asa_scene_selection_v1",
        "scenes": [{"character_settings": json.dumps([{"image_id": str(image)}])}],
    }
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        frozen = snapshot(conn, db[1], {"scene_images": selection})
        assert frozen["speakers"][0]["voice"]["instructions"] == "높고 맑은 아이 목소리"
        assert snapshot(conn, uuid4(), {"scene_images": selection})["speakers"] == []
    clip = dict(
        clip_id="one",
        scene_id="s1",
        shot_id="shot1",
        image_id=str(image),
        source_start_seconds=0,
        source_end_seconds=5,
        duration_seconds=5,
        prompt="아이를 따라 카메라가 이동한다.",
        source_excerpt="",
        continuity_in="",
        continuity_out="",
        split_reason="",
    )
    answer = dict(
        model_key="wan3",
        model_revision="1",
        aspect_ratio="9:16",
        clips=[clip],
        audio_plan={
            "enabled": True,
            "speakers": [{"id": "child", "name": "아이"}],
            "cues": [
                {
                    "id": "line",
                    "speaker_id": "child",
                    "text": "안녕!",
                    "start": 1,
                    "end": 3,
                    "emotion": "기쁘게",
                }
            ],
        },
    )
    # A queued attempt holds the immutable descriptions, even after source edits.
    attempt = uuid4()
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        conn.execute(
            "INSERT INTO script_attempts(workspace_id,request_id,id,instruction,status,"
            "prompt,model_profile,provider,model) VALUES(%s,%s,%s,'','succeeded',%s,"
            "'default','openai','test')",
            (db[1], rid, attempt, json.dumps({"video_voice_directions": frozen})),
        )
        conn.execute(
            "INSERT INTO script_versions(workspace_id,request_id,version,operation_id,"
            "title,narration,source,answer) VALUES(%s,%s,2,%s,'','','ai',%s)",
            (db[1], rid, attempt, Jsonb(answer)),
        )
        conn.execute(
            "INSERT INTO script_versions(workspace_id,request_id,version,operation_id,"
            "title,narration,source,base_version,answer) VALUES(%s,%s,3,%s,'','','manual',2,%s)",
            (db[1], rid, uuid4(), Jsonb(answer)),
        )
    assert (
        client.put(
            path + "/voice-directions",
            json={
                **edit,
                "revision": 2,
                "speakers": [{"id": "child", "instructions": "수정된 목소리"}],
            },
            headers=headers,
        ).status_code
        == 200
    )
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        state = audio_service.load(conn, db[1], rid, 3)["settings"]
    assert state.delivery_mode == "video" and not state.enabled
    assert state.speakers[0].voice.instructions == "높고 맑은 아이 목소리"
    monkeypatch.setattr(
        video_planning,
        "selected_scenes",
        lambda *args: {"scenes": [{"image_id": str(image), "scene_id": "s1", "shot_id": "shot1"}]},
    )
    settings = Settings(_env_file=None, wan_api_key="test", wan_workspace_id="ws-test")
    prepared = video_planning.prepare(
        None, settings, VideoPreparation.model_validate(answer), voice_settings=state,
        visual_style={'media_type': 'animation_2d', 'prompt': 'watercolor'},
    )
    spec = prepared["clips"][0]["generation_input"]
    assert spec["audio"] and "높고 맑은 아이 목소리" in spec["prompt"]
    assert 'WORK VISUAL CATEGORY: animation_2d' in spec['prompt']
    assert 'watercolor' in spec['prompt']
    assert "1.00–3.00" in spec["prompt"] and "안녕!" in spec["prompt"]
    _, _, body = generation_request(settings, prepared["model_snapshot"], spec, b"png")
    assert body["parameters"]["audio"] is True
    assert body["input"]["prompt"] == spec["prompt"]
    settings.video_model_profiles["wan3"].supports_audio = False
    with pytest.raises(RegistryError, match="video_audio_unsupported"):
        video_planning.prepare(
            None, settings, VideoPreparation.model_validate(answer), voice_settings=state
        )
