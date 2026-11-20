from uuid import uuid4

import pytest

from asa.registry.schemas import RegistryError
from asa.video_contracts import VideoReferenceInputs
from asa.video_references import resolve_upload_media, video_source


def test_empty_video_refs_preserve_old_snapshot():
    assert VideoReferenceInputs().model_dump(mode='json') == {
        'character_image_ids': [], 'audio': []}


def test_video_source_is_scoped_and_bounded():
    workspace, request, job = uuid4(), uuid4(), uuid4()

    class Missing:
        def execute(self, sql, params):
            assert 'workspace_id=%s' in sql and 'request_id=%s' in sql
            assert params == (workspace, request, str(job))
            return self

        def fetchone(self):
            return None

    with pytest.raises(RegistryError, match='video_reference_video_missing'):
        video_source(Missing(), workspace, request, {'job_id': str(job)})


def test_higgsfield_validates_all_assets_before_upload(monkeypatch):
    import hashlib

    from asa.config import Settings
    image, video = str(uuid4()), str(uuid4())
    monkeypatch.setattr('asa.video_references.image_bytes', lambda *args: b'image')
    monkeypatch.setattr('asa.video_references.video_source',
                        lambda *args: {'video': b'changed', 'answer_version': 1})
    spec = {'start_image_id': image,
            'reference_inputs': {'video': [{'job_id': video}]},
            'reference_images': [{'image_id': image,
                                  'sha256': hashlib.sha256(b'image').hexdigest()}],
            'reference_video': {'job_id': video, 'source_answer_version': 1,
                                'source_sha256': hashlib.sha256(b'original').hexdigest()}}
    with pytest.raises(RegistryError, match='video_reference_video_source_changed'):
        resolve_upload_media(None, Settings(_env_file=None), uuid4(),
                             {'request_id': uuid4(), 'generation_input': spec})


def test_catalog_estimate_without_key_uses_video_rate():
    from asa.config import Settings
    from asa.registry.video_planning import catalog_estimate
    model = next(m for m in Settings(_env_file=None).video_model_profiles.values()
                 if m.provider == 'higgsfield')
    assert catalog_estimate(model, 10)['amount_usd'] == .75
    assert catalog_estimate(model, 10, True)['amount_usd'] == 1.493


@pytest.mark.parametrize('failure', [None, OSError('dns failure')])
def test_worker_uploads_only_after_reservation_and_submits_once(monkeypatch, failure):
    import httpx
    from test_video_worker_diagnostics import Connection

    from asa import video_worker
    from asa.config import Settings
    cfg = Settings(_env_file=None, higgsfield_api_key='test')
    model = next(m for m in cfg.video_model_profiles.values() if m.provider == 'higgsfield')
    conn = Connection('queued')
    conn.row['model_snapshot'] = model.model_dump()
    conn.row['generation_input'].update(prompt='Move slowly', duration_seconds=5,
                                        aspect_ratio='16:9', resolution='720p', audio=True)
    monkeypatch.setattr(video_worker, 'lock_policy', lambda *a: None)
    monkeypatch.setattr(video_worker, 'policy', lambda *a: {})
    monkeypatch.setattr(video_worker, 'allowed', lambda *a: True)
    monkeypatch.setattr(video_worker, 'accepting_work', lambda *a: True)
    monkeypatch.setattr('asa.video_references.resolve_upload_media',
                        lambda *a: (b'png', []))
    uploads = []

    def upload(*args):
        assert any("status='submitting'" in sql for sql, _ in conn.calls)
        uploads.append(args[-1])
        if failure:
            raise failure
        return 'https://assets.example/image.png'

    monkeypatch.setattr('asa.higgsfield_provider.upload_media', upload)
    requests = []

    def respond(request):
        requests.append(request)
        assert request.headers['Idempotency-Key'] == str(conn.row['id'])
        return httpx.Response(200, json={'request_id': 'task-123'})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert video_worker.process(conn, client, uuid4(), cfg)
    assert uploads == ['image/png']
    if failure:
        assert not requests
        assert conn.calls[-1][1][:2] == ('failed', 'reference_upload_failed')
    else:
        assert len(requests) == 1
        assert '/alibaba/wan-3.0/image-to-video' in str(requests[0].url)
        assert conn.calls[-1][1][0] == 'task-123'


def test_higgsfield_audio_freeze_does_not_require_external_origin(monkeypatch):
    from asa.config import Settings
    from asa.video_references import freeze
    monkeypatch.setattr('asa.video_references.image_bytes', lambda *a: b'image')
    monkeypatch.setattr('asa.video_reference_delivery.require_audio_delivery',
                        lambda *a: pytest.fail('Higgsfield uploads its own audio'))
    monkeypatch.setattr('asa.video_references.audio_source',
                        lambda *a: {'video': b'video', 'answer_version': 2})
    monkeypatch.setattr('asa.video_references.extract_audio', lambda *a: b'wave')
    spec = {'start_image_id': str(uuid4()), 'reference_inputs': {'audio': [{
        'job_id': str(uuid4()), 'speaker_id': 'narrator', 'start_seconds': 0, 'end_seconds': 2}]}}
    freeze(None, Settings(_env_file=None), uuid4(), uuid4(), spec, {'scenes': []}, 'higgsfield')
    assert spec['reference_audio']['source_answer_version'] == 2
