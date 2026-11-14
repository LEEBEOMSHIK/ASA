import json
from uuid import UUID, uuid4

import pytest
from test_registry_db import db as db
from test_registry_db import definition

from asa import audio_worker
from asa.audio_media import pcm_wav
from asa.config import Settings
from asa.models import AgentAnswer
from asa.registry.audio_service import review_speech
from asa.registry.history import HistoryRepository, WorkRequest
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import AgentDraft
from asa.registry.script_queue import ScriptQueue
from asa.registry.script_stage import GenerateScript, execute_attempt


@pytest.mark.parametrize('planned,expected', [(None, 9), (8, 10), (10, 12)])
def test_new_and_retry_queue_separate_timing_tracks_and_keep_gaps(
        db, monkeypatch, planned, expected):
    config = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                      script_ai_enabled=True, ai_api_key='test-only', ai_model='first',
                      ai_models=['first'], audio_ai_enabled=True)
    draft = {**definition(), 'after_tasks': {'scene_timing': True}}
    agent = RegistryRepository(*db).save_settings(AgentDraft.model_validate(draft))
    rid = uuid4()
    HistoryRepository(*db).save(WorkRequest(
        id=rid, agent_id=agent['id'], version=1, input={'topic': 'sample'}))
    detail = HistoryRepository(*db).detail(rid)
    assert detail['agent']['after_tasks']['scene_timing'] is True
    assert detail['agent']['output_schema']['properties']['script']['type'] == 'string'
    queue = ScriptQueue(config)
    plan = {'duration': 10, 'planned_duration': planned,
            'speakers': [{'id': 'n', 'name': '나레이션', 'role': 'narrator'}],
            'cues': [{'id': 'a', 'speaker_id': 'n', 'text': '첫 대사', 'start': 1, 'end': 3},
                     {'id': 'b', 'speaker_id': 'n', 'text': '다음 대사', 'start': 5, 'end': 7}]}
    def generate(prompt):
        assert json.loads(prompt)['scene_timing'] is True
        return AgentAnswer(value={'script': 'unchanged'}, timing_plan=plan)
    queue.submit(str(rid))
    assert execute_attempt(queue, str(rid), str(rid), generate)
    assert queue.get(str(rid))['versions'][0]['after_tasks']['scene_timing'] is True
    calls = []
    def speak(key, spec):
        assert key == 'test-only'  # Reuses the existing OpenAI key.
        calls.append(spec)
        return pcm_wav(b'\0\0' * 24000 * 3), spec['cue']['text']
    monkeypatch.setattr(audio_worker, 'synthesize', speak)
    worker = audio_worker.AudioWorker(config)
    with queue._connect() as conn:
        assert review_speech(conn, config, rid, 1)['timing']['queued'] == 2
    assert worker.tick() and worker.tick()
    assert not worker.tick()
    with queue._connect() as conn:
        timing = review_speech(conn, config, rid, 1)['timing']
    assert timing['preview_ready']
    assert timing['duration'] == expected and timing['overrun'] == max(0, expected-10)
    assert timing['shortfall'] == max(0, 10-expected)
    assert timing['speech_seconds'] == 6 and timing['gap_seconds'] == expected-6
    assert [c['start'] for c in timing['clips']] == [1, 6]
    retry = GenerateScript(id=uuid4(), expected_revision=queue.get(str(rid))['revision'],
                           base_version=1, instruction='다시')
    queue.submit(str(rid), retry)
    assert execute_attempt(queue, str(rid), str(retry.id), generate)
    # Re-submission of the same operation cannot enqueue a second set of speech jobs.
    queue.submit(str(rid), retry)
    with queue._connect() as conn:
        jobs = conn.execute('SELECT answer_version,count(*) n FROM audio_jobs '
                            'WHERE workspace_id=%s AND request_id=%s GROUP BY answer_version',
                            (db[1], rid)).fetchall()
        assert {j['answer_version']: j['n'] for j in jobs} == {1: 2, 2: 2}
        assert review_speech(conn, config, rid, 2)['timing']['queued'] == 2
    assert worker.tick() and worker.tick() and not worker.tick()
    assert len(calls) == 4
    assert all(c['purpose'] == 'timing' for c in calls)
    assert all(v['answer'] == {'script': 'unchanged'} for v in queue.get(str(rid))['versions'])
    assert UUID(str(rid)) == rid
