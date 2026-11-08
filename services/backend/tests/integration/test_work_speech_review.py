from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_registry_db import client as client_fixture
from test_registry_db import db as db_fixture
from test_registry_db import script_work

from asa.audio_contracts import AudioSettings
from asa.config import Settings
from asa.registry.audio_service import review_speech, speech_key, speech_spec
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError

client = client_fixture
db = db_fixture


def test_review_follows_answer_ancestry_and_rejects_invalid_speech(client, db):
    path = f'/api/v1/audio/work/{uuid4()}/3/review'
    assert client.get(path).status_code == 401
    headers, work, _ = script_work(client)
    rid = work['id']
    data = AudioSettings.model_validate({
        'enabled': True, 'speakers': [{'id': 'child', 'name': '아이'}],
        'cues': [{'id': 'hello', 'speaker_id': 'child', 'text': '안녕', 'start': 1, 'end': 3}],
    })
    data = AudioSettings.model_validate(data.model_dump(mode='json'))
    spec = speech_spec(Settings(_env_file=None), data, 'hello')
    valid, rejected = uuid4(), uuid4()
    with psycopg.connect(db[0]) as conn:
        conn.execute('INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)',
                     (db[1], rid))
        for version, base in [(1, None), (2, 1), (3, 2), (4, 1)]:
            conn.execute(
                'INSERT INTO script_versions(workspace_id,request_id,version,operation_id,'
                "title,narration,source,answer,base_version) VALUES (%s,%s,%s,%s,'','','ai',%s,%s)",
                (db[1], rid, version, uuid4(), Jsonb('text'), base))
        conn.execute('INSERT INTO audio_settings VALUES (%s,%s,2,1,%s)',
                     (db[1], rid, Jsonb(data.model_dump(mode='json'))))
        for jid, error, key in [(valid, None, speech_key(spec)),
                                (rejected, 'audio_transcript_mismatch', 'old')]:
            conn.execute(
                'INSERT INTO audio_jobs(workspace_id,id,request_id,answer_version,kind,'
                'cue_id,fingerprint,input,status,media,duration,transcript,error_code) '
                "VALUES (%s,%s,%s,2,'speech','hello',%s,%s,'review',%s,1.5,'안녕',%s)",
                (db[1], jid, rid, key, Jsonb(spec), b'fake-wave', error))
    path = f'/api/v1/audio/work/{rid}/3/review'
    response = client.get(path)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['source_version'] == 2 and result['answer_version'] == 3
    by_id = {job['id']: job for job in result['jobs']}
    assert by_id[str(valid)]['can_approve']
    assert by_id[str(valid)]['speaker_name'] == '아이'
    assert by_id[str(valid)]['text'] == '안녕'
    assert by_id[str(valid)]['start'] == 1
    assert by_id[str(rejected)]['excluded_reason'] == 'audio_transcript_mismatch'
    assert not by_id[str(rejected)]['can_approve']
    assert client.post(f'/api/v1/audio/jobs/{valid}/approve').status_code == 403
    assert client.post(f'/api/v1/audio/jobs/{rejected}/approve',
                       json={}, headers=headers).status_code == 409
    assert client.post(f'/api/v1/audio/jobs/{valid}/approve',
                       json={}, headers=headers).status_code == 200
    assert not next(j for j in client.get(path).json()['jobs']
                    if j['id'] == str(valid))['can_approve']
    assert client.get(f'/api/v1/audio/work/{rid}/4/review').json()['source_version'] is None
    assert client.get(f'/api/v1/audio/work/{rid}/1/review').json()['jobs'] == []
    assert client.get(f'/api/v1/audio/work/{rid}/99/review').status_code == 404
    assert client.get(f'/api/v1/audio/work/{uuid4()}/3/review').status_code == 404
    with RegistryRepository(*db)._connect() as conn:
        with pytest.raises(RegistryError, match='audio_work_missing'):
            review_speech(conn, Settings(_env_file=None, workspace_id=uuid4()),
                          work['id'], 3)
    with psycopg.connect(db[0]) as conn:
        conn.execute("UPDATE audio_jobs SET duration=4,status='review' WHERE id=%s", (valid,))
    long_job = next(j for j in client.get(path).json()['jobs'] if j['id'] == str(valid))
    assert not long_job['timing_ok'] and not long_job['can_approve']
    assert client.post(f'/api/v1/audio/jobs/{valid}/approve',
                       json={}, headers=headers).status_code == 409
    changed = data.model_copy(deep=True)
    changed.cues[0].text = '새로운 대사'
    with psycopg.connect(db[0]) as conn:
        conn.execute('UPDATE audio_settings SET settings=%s WHERE workspace_id=%s '
                     'AND request_id=%s AND answer_version=2',
                     (Jsonb(changed.model_dump(mode='json')), db[1], rid))
    assert next(j for j in client.get(path).json()['jobs'] if j['id'] == str(valid))[
        'excluded_reason'] == 'audio_source_changed'
    with psycopg.connect(db[0]) as conn:
        # Own settings are an explicit boundary; never borrow a parent's removed cues.
        conn.execute('INSERT INTO audio_settings VALUES (%s,%s,3,1,%s)',
                     (db[1], rid, Jsonb(AudioSettings().model_dump(mode='json'))))
    assert client.get(path).json()['source_version'] == 3
    assert client.get(path).json()['jobs'] == []
