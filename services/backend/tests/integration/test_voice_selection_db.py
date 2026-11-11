from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from test_registry_db import KEY, script_work
from test_registry_db import db as db_fixture

from asa import audio_worker
from asa.api import create_app
from asa.audio_media import pcm_wav
from asa.config import Settings

db = db_fixture


def test_voice_sample_selection_and_timing_exclusion(db, monkeypatch):
    config = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                      owner_access_key=KEY, allowed_origins=['http://testserver'],
                      audio_ai_enabled=True, audio_api_key='test-only')
    calls = []

    def speak(key, spec):
        calls.append(spec)
        return pcm_wav(b'\0\0' * 24000), spec['cue']['text']

    monkeypatch.setattr(audio_worker, 'synthesize', speak)
    with TestClient(create_app(config)) as client:
        headers, work, _ = script_work(client)
        with psycopg.connect(db[0]) as conn:
            conn.execute('INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)',
                         (db[1], work['id']))
            conn.execute("INSERT INTO script_versions(workspace_id,request_id,version,"
                         "operation_id,title,narration,source,answer) "
                         "VALUES (%s,%s,1,%s,'test','test','ai',%s)",
                         (db[1], work['id'], uuid4(), Jsonb({'characters': [
                             {'id': 'child', 'name': '아이'}]})))
        path = f"/api/v1/audio/work/{work['id']}/1"
        data = client.get(path).json()['settings']
        assert any(s['role'] == 'narrator' for s in data['speakers'])
        data.update(enabled=True, cues=[{'id': 'line', 'speaker_id': 'child',
                                        'text': '안녕', 'start': 0, 'end': 2}])
        assert client.put(path, json={'revision': 0, 'settings': data},
                          headers=headers).status_code == 200
        operation = {'id': str(uuid4()), 'revision': 1, 'cue_id': 'child'}
        assert client.post(path+'/sample', json=operation).status_code == 403
        sample = client.post(path+'/sample', json=operation, headers=headers)
        assert sample.status_code == 200, sample.text
        assert client.post(path+'/sample', json=operation, headers=headers).json() == sample.json()
        assert client.post(path+'/select-voice', json=operation, headers=headers).status_code == 409
        worker = audio_worker.AudioWorker(config)
        assert worker.tick()
        assert calls[0]['purpose'] == 'sample'
        sample_view = client.get(path).json()['jobs'][0]
        assert sample_view['sample_voice']['voice'] == 'marin'
        assert sample_view['sample_text'] == calls[0]['cue']['text']
        catalog = client.get('/api/v1/audio/catalog').json()
        assert catalog['sample_text'] == sample_view['sample_text']
        assert 'input' not in sample_view
        assert client.post(f"/api/v1/audio/jobs/{operation['id']}/approve",
                           json={}, headers=headers).status_code == 409
        selected = client.post(path+'/select-voice', json=operation, headers=headers)
        assert selected.status_code == 200, selected.text
        assert selected.json()['selected_speakers'] == ['child']
        data = selected.json()['settings']
        production = {'id': str(uuid4()), 'revision': 2, 'cue_id': 'line'}
        assert client.post(path+'/speech', json=production, headers=headers).status_code == 200
        assert worker.tick()
        assert calls[-1]['purpose'] == 'production'
        data['speakers'][0]['voice']['instructions'] = '새 말투'
        assert client.put(path, json={'revision': 2, 'settings': data},
                          headers=headers).status_code == 200
        assert client.get(path).json()['selected_speakers'] == []
        assert client.post(path+'/speech', json={**production, 'id': str(uuid4()), 'revision': 3},
                           headers=headers).status_code == 409
        data['purpose'] = 'timing'
        assert client.put(path, json={'revision': 3, 'settings': data},
                          headers=headers).status_code == 200
        timed = {**production, 'id': str(uuid4()), 'revision': 4}
        assert client.post(path+'/speech', json=timed, headers=headers).status_code == 200
        assert worker.tick()
        assert client.post(f"/api/v1/audio/jobs/{timed['id']}/approve",
                           json={}, headers=headers).status_code == 409
        review = client.get(path+'/review').json()['jobs']
        assert not any(j['can_approve'] for j in review if j['purpose'] == 'timing')
        assert all(j['purpose'] != 'sample' for j in review)

        preview = client.get(path+'/timing-preview')
        assert preview.status_code == 200, preview.text[:100]
        from asa.audio_media import wav_duration
        assert wav_duration(preview.content) == 2
        summary = client.get(path+'/review').json()['timing']
        assert summary['speech_seconds'] == 1 and summary['gap_seconds'] == 1
        assert client.get(f'/api/v1/audio/work/{uuid4()}/1/timing-preview').status_code == 404

        data['purpose'] = 'production'
        data['speakers'][0]['voice']['voice'] = 'cedar'
        changed = client.put(path, json={'revision': 4, 'settings': data}, headers=headers)
        assert changed.status_code == 200
        second = {'id': str(uuid4()), 'revision': 5, 'cue_id': 'child'}
        assert client.post(path+'/sample', json=second, headers=headers).status_code == 200
        assert worker.tick()
        samples = [j for j in client.get(path).json()['jobs'] if j['purpose'] == 'sample']
        assert len(samples) == 2
        assert {j['sample_text'] for j in samples} == {sample_view['sample_text']}
        assert {j['sample_voice']['voice'] for j in samples} == {'marin', 'cedar'}
        assert client.post(path+'/select-voice', json={**operation, 'revision': 5},
                           headers=headers).status_code == 409
        data['speakers'][0]['voice'] = sample_view['sample_voice']
        restored = client.put(path, json={'revision': 5, 'settings': data}, headers=headers)
        assert restored.status_code == 200
        assert client.post(path+'/select-voice', json={**operation, 'revision': 6},
                           headers=headers).status_code == 200
        assert len(calls) == 4  # Restoring/selecting a sample never generates paid audio.


def test_basic_previews_are_read_only_scoped_media(db, monkeypatch, tmp_path):
    from asa.voice_previews import prepare_previews

    config = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                      owner_access_key=KEY, allowed_origins=['http://testserver'],
                      audio_preview_dir=str(tmp_path),
                      audio_ai_enabled=True, audio_api_key='test-only')
    calls = []

    def speak(key, spec):
        calls.append(spec)
        return pcm_wav(b'\0\0' * 24000), spec['cue']['text']

    monkeypatch.setattr('asa.voice_previews.synthesize', speak)
    prepare_previews(config, allow_paid_call=True)
    with TestClient(create_app(config)) as client:
        url = '/api/v1/audio/previews/openai-realtime/marin'
        assert client.get(url).status_code in (401, 403)
        script_work(client)
        assert client.get(url).status_code == 200
        assert client.get(url).content.startswith(b'RIFF')
        assert client.get(url.replace('marin', 'invalid')).status_code == 404
        assert client.get(url.replace('openai-realtime', 'invalid')).status_code == 404
        catalog = client.get('/api/v1/audio/catalog').json()
        assert all(v['ready'] for v in catalog['previews']['openai-realtime'].values())
        assert len(calls) == 10
    other = config.model_copy(update={'workspace_id': uuid4()})
    from asa.voice_previews import preview_catalog
    assert not preview_catalog(other)['openai-realtime']['marin']['ready']
