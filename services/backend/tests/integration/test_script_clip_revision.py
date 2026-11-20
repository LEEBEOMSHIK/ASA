import json
from uuid import uuid4

from psycopg.types.json import Jsonb
from test_registry_db import client, db, definition, login  # noqa: F401

from asa.audio_contracts import AudioSettings
from asa.config import Settings
from asa.models import AgentAnswer
from asa.providers import make_agent_generator
from asa.registry.script_stage import SaveScript, ScriptRepository, execute_attempt
from asa.video_review import save, sources


def test_clip_revision_keeps_the_other_clip_and_original_input(client, db, monkeypatch):  # noqa: F811
    headers = login(client)
    clip = {
        "clip_id": "first", "scene_id": "scene", "shot_id": "shot",
        "image_id": str(uuid4()), "source_start_seconds": 0, "source_end_seconds": 5,
        "duration_seconds": 5, "prompt": "기존 동작", "source_excerpt": "원문",
        "continuity_in": "", "continuity_out": "", "split_reason": "",
    }
    other = {**clip, "clip_id": "second", "source_start_seconds": 5,
             "source_end_seconds": 10, "prompt": "이웃 클립"}
    answer = {"model_key": "wan3", "model_revision": "1", "aspect_ratio": "9:16",
              "clips": [clip, other]}
    properties = {
        key: {"type": "string", "maxLength": 500} if isinstance(value, str)
        else {"type": "integer", "minimum": 0, "maximum": 100}
        for key, value in clip.items()
    }
    original = definition()
    original["input_schema"]["properties"]["video_model"] = {
        "type": "string", "x-video-model": True, "maxLength": 100,
    }
    original["video_prompt_modules"] = {
        "style_instructions": {"animation_2d": "2D 전용 지침"},
    }
    original["output_schema"] = {"type": "object", "required": list(answer),
        "properties": {"model_key": {"type": "string", "maxLength": 100},
                       "model_revision": {"type": "string", "maxLength": 100},
                       "aspect_ratio": {"type": "string", "maxLength": 20},
                       "clips": {"type": "array", "maxItems": 100,
                                 "items": {"type": "object", "properties": properties,
                                           "required": list(properties)}}}}
    created = client.post("/api/v1/agents/save", json=original, headers=headers)
    assert created.status_code == 201, created.text
    agent = created.json()
    rid = str(uuid4())
    original_input = {"topic": "대본 자료", "video_model": "wan3", "video_style": "animation_2d"}
    response = client.post("/api/v1/work-requests", headers=headers, json={
        "id": rid, "agent_id": agent["id"], "version": 1, "input": original_input})
    assert response.status_code == 201, response.text
    repo = ScriptRepository(*db)
    previous = repo.save(rid, SaveScript(id=uuid4(), expected_revision=0, answer=answer))
    audio = AudioSettings(delivery_mode="video")
    with repo._connect() as conn:
        conn.execute("INSERT INTO audio_settings VALUES (%s,%s,1,1,%s)",
                     (db[1], rid, Jsonb(audio.model_dump(mode="json"))))
        old_sources = {**sources(answer, audio), "second:voice": "저장 수정 전 목소리"}
        save(conn, db[1], rid, 1, {"sections": [
            {"key": key, "parts": [{"text": text, "kind": "action"}] if text else []}
            for key, text in old_sources.items()
        ]}, old_sources)
    saved = client.put(f"/api/v1/agents/{agent['id']}/save", headers={
        **headers, "If-Match": f'"{agent["revision"]}"'},
        json={**original, "instructions": "최신 지침으로 수정"})
    assert saved.status_code == 200, saved.text
    url = f"/api/v1/work-requests/{rid}/script/revise-clip"
    command = {"id": str(uuid4()), "expected_revision": previous["revision"],
               "base_version": 1, "clip_id": "first", "instruction": "동작 변경"}
    queued = client.post(url, headers=headers, json=command)
    assert queued.status_code == 201, queued.text
    assert queued.json()["attempts"][0]["revision_clip_id"] == "first"
    assert client.post(url, headers=headers, json=command).status_code == 201
    other_clip = client.post(url, headers=headers, json={**command, "clip_id": "second"})
    assert other_clip.status_code == 409

    class Model:
        def with_structured_output(self, schema, **_kwargs):
            assert set(schema["properties"]["value"]["required"]) == set(properties)
            return self

        def invoke(self, messages, **_kwargs):
            assert messages[0] == ("system", "최신 지침으로 수정\n\n2D 전용 지침")
            assert "첫 시작은 0" not in str(messages)
            assert "audio_plan은 enabled=false로 두고" not in str(messages)
            sent = json.loads(messages[-1][1])
            assert sent["revision_clip_id"] == "first"
            assert sent["effective_clip_revision_audio"]["delivery_mode"] == "video"
            return {"value": {**clip, "prompt": "수정 동작"}}

    def classify(_model, texts):
        assert texts == {"first:prompt": "수정 동작", "first:edit_notes": "", "first:voice": ""}
        return {"sections": [
            {"key": key, "parts": [{"text": text, "kind": "action"}] if text else []}
            for key, text in texts.items()
        ]}

    monkeypatch.setattr("asa.providers.init_chat_model", lambda *_args, **_kwargs: Model())
    monkeypatch.setattr("asa.video_review.classify", classify)
    run = make_agent_generator(Settings(_env_file=None, ai_model="test", ai_api_key="fake"))

    def model(prompt):
        snapshot = json.loads(prompt)
        assert snapshot["agent_instructions"] == "최신 지침으로 수정"
        assert snapshot["original_request"] == original_input
        assert snapshot["previous_answer"] == answer
        return run(prompt)

    with repo._connect() as conn:
        conn.execute("UPDATE audio_settings SET revision=2,settings=%s WHERE request_id=%s",
                     (Jsonb(AudioSettings().model_dump(mode="json")), rid))
    assert execute_attempt(repo, rid, command["id"], model)
    result = repo.get(rid)
    assert result["head_version"] == 2, result["attempts"]
    assert [item["answer"] for item in result["versions"]] == [
        {**answer, "clips": [{**clip, "prompt": "수정 동작"}, other]}, answer,
    ]
    with repo._connect() as conn:
        revised_audio = conn.execute("SELECT revision,settings FROM audio_settings "
                                     "WHERE request_id=%s AND answer_version=2", (rid,)).fetchone()
        assert revised_audio == {"revision": 1, "settings": audio.model_dump(mode="json")}
        review = conn.execute("SELECT annotations,validation FROM video_review_annotations "
                              "WHERE request_id=%s AND answer_version=2", (rid,)).fetchone()
        assert {span["key"] for span in review["annotations"]} == {"first:prompt", "second:prompt"}
        assert not review["validation"]["complete"]
        assert review["validation"]["covered_sections"] == 5
    stale = {**command, "id": str(uuid4()), "expected_revision": result["revision"]}
    assert client.post(url, headers=headers, json=stale).status_code == 409
    bad = {**stale, "base_version": 2}
    assert client.post(url, headers=headers, json=bad).status_code == 201
    assert execute_attempt(repo, rid, bad["id"], lambda _: AgentAnswer(value={
        **clip, "source_end_seconds": 4,
    }))
    failure = repo.get(rid)
    assert failure["head_version"] == 2
    assert failure["attempts"][0]["error_code"] == "ai_output_invalid"
