from uuid import uuid4

import pytest
from pydantic import ValidationError
from test_video_providers import settings, spec

from asa.video_contracts import VideoReferenceInputs
from asa.video_providers import generation_request


def test_reference_configuration_must_match_saved_request():
    from asa.registry.schemas import RegistryError
    from asa.video_references import validate_requested
    configured = {'clip_ids': ['G01'], 'character_image_ids': [], 'audio': []}
    validate_requested('G01', {'character_image_ids': [], 'audio': []}, configured)
    with pytest.raises(RegistryError):
        validate_requested('G02', {'character_image_ids': [], 'audio': []}, configured)
    with pytest.raises(RegistryError):
        validate_requested('G01', None, configured)


def test_narrator_bounds_exclude_other_voice_and_sound_effect():
    from asa.registry.schemas import RegistryError
    from asa.video_references import validate_audio_segment
    answer = {'audio_plan': {'speakers': [{'id': 'narrator', 'role': 'narrator'}],
              'cues': [{'speaker_id': 'narrator', 'start': 0, 'end': 3.4},
                       {'speaker_id': 'ghost', 'start': 4, 'end': 5}]}}
    clip = {'source_start_seconds': 0, 'source_end_seconds': 7,
            'quality': {'events': [{'kind': 'sound_effect', 'start': 4, 'end': 5}]}}
    ref = {'speaker_id': 'narrator', 'start_seconds': 0, 'end_seconds': 3.4}
    validate_audio_segment(ref, answer, clip)
    with pytest.raises(RegistryError):
        validate_audio_segment({**ref, 'end_seconds': 5}, answer, clip)
    clip['quality']['events'][0].update(start=2, end=3)
    with pytest.raises(RegistryError):
        validate_audio_segment(ref, answer, clip)


def test_reference_character_allowlist_uses_all_original_scenes():
    import json

    from asa.video_references import allowed_character_images
    image = str(uuid4())
    selection = {'scenes': [{'character_settings': json.dumps([{'image_id': image}])},
                            {'character_settings': '[]'}]}
    assert allowed_character_images(selection) == {image}


def test_reference_contract_rejects_duplicates_and_audio_outside_bounds():
    image = str(uuid4())
    with pytest.raises(ValidationError):
        VideoReferenceInputs(character_image_ids=[image, image])
    with pytest.raises(ValidationError):
        VideoReferenceInputs(audio=[dict(job_id=uuid4(), speaker_id='narrator',
                                        start_seconds=0, end_seconds=16)])


def test_reference_media_is_ordered_without_first_frame():
    cfg = settings()
    model = cfg.video_model_profiles['wan3'].model_dump()
    refs = [{'type': 'reference_image', 'url': 'data:image/png;base64,eA=='},
            {'type': 'reference_audio', 'url': 'https://assets.example/audio.wav'}]
    _, _, body = generation_request(cfg, model,
        spec(reference_inputs={'character_image_ids': [str(uuid4())], 'audio': [{}]}),
        b'png', refs)
    assert [m['type'] for m in body['input']['media']] == [
        'reference_image', 'reference_image', 'reference_audio']


def test_reference_mode_rejects_mixed_first_frame_and_unsupported_provider():
    cfg = settings()
    with pytest.raises(ValueError):
        generation_request(cfg, cfg.video_model_profiles['wan3'].model_dump(),
            spec(reference_inputs={}), b'png', [{'type': 'first_frame', 'url': 'x'}])
    with pytest.raises(ValueError):
        generation_request(cfg, cfg.video_model_profiles['runway-gen45'].model_dump(),
            spec(duration_seconds=5, reference_inputs={}), b'png', [])


def test_provider_never_silently_omits_required_audio_reference():
    cfg = settings()
    with pytest.raises(ValueError, match='reference_media_missing'):
        generation_request(cfg, cfg.video_model_profiles['wan3'].model_dump(),
            spec(reference_inputs={'character_image_ids': [], 'audio': [{}]}), b'png')


def test_frozen_image_content_is_rechecked_before_provider_submission(monkeypatch):
    import hashlib

    from asa.registry.schemas import RegistryError
    from asa.video_references import resolve_media
    image = str(uuid4())
    job = {'generation_input': {'reference_inputs': {'character_image_ids': [], 'audio': []},
           'start_image_id': image, 'reference_images': [
               {'image_id': image, 'sha256': hashlib.sha256(b'original').hexdigest()}]}}
    monkeypatch.setattr('asa.video_references.image_bytes', lambda *args: b'changed')
    with pytest.raises(RegistryError) as error:
        resolve_media(None, settings(), uuid4(), job)
    assert error.value.code == 'video_reference_image_changed'


def test_audio_hash_change_blocks_extraction(monkeypatch):
    from asa.registry.schemas import RegistryError
    from asa.video_references import resolve_audio
    monkeypatch.setattr('asa.video_references.audio_source',
                        lambda *args: {'video': b'changed', 'answer_version': 12})
    monkeypatch.setattr('asa.video_references.extract_audio',
                        lambda *args: pytest.fail('changed source must not be extracted'))
    with pytest.raises(RegistryError) as error:
        resolve_audio(None, uuid4(), uuid4(), {'source_sha256': '0' * 64,
                      'source_answer_version': 12}, 'ffmpeg')
    assert error.value.code == 'video_reference_audio_source_changed'


def test_audio_source_query_requires_same_workspace_and_request():
    from asa.registry.schemas import RegistryError
    from asa.video_references import audio_source
    workspace, request, job = uuid4(), uuid4(), uuid4()

    class Missing:
        def execute(self, sql, parameters):
            assert 'j.workspace_id=%s AND j.request_id=%s AND j.id=%s' in sql
            assert parameters == (workspace, request, str(job))
            return self

        def fetchone(self):
            return None

    with pytest.raises(RegistryError) as error:
        audio_source(Missing(), workspace, request, {'job_id': str(job)})
    assert error.value.code == 'video_reference_audio_missing'


def test_reference_plan_changes_only_its_own_fingerprint():
    from test_video_plan_approvals import plan

    from asa.audio_contracts import AudioSettings
    from asa.registry.video_plan_approvals import fingerprints
    from asa.registry.video_planning import generation_input

    value = plan()
    before = fingerprints(value, AudioSettings(), {})
    legacy = generation_input(value, value.clips[0], '720p')
    assert 'reference_inputs' not in legacy
    value.clips[0].reference_inputs = [VideoReferenceInputs()]
    after = fingerprints(value, AudioSettings(), {})
    assert before['clip1'] != after['clip1']
    assert before['clip2'] == after['clip2']
    assert before['clip3'] == after['clip3']


def test_audio_reference_enables_provider_audio_even_without_text_voice():
    from test_video_plan_approvals import plan

    from asa.registry.video_planning import generation_input

    value = plan()
    value.clips[0].reference_inputs = [VideoReferenceInputs(audio=[{
        'job_id': uuid4(), 'speaker_id': 'narrator', 'start_seconds': 0, 'end_seconds': 3.4}])]
    assert generation_input(value, value.clips[0], '720p')['audio'] is True


def test_extract_audio_outputs_only_requested_interval(tmp_path):
    import importlib
    import wave
    from io import BytesIO

    from asa.video_analysis import run
    from asa.video_references import extract_audio

    ffmpeg = importlib.import_module('imageio_ffmpeg').get_ffmpeg_exe()
    source = tmp_path / 'source.mp4'
    result = run([ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error',
                  '-f', 'lavfi', '-i', 'sine=frequency=440:duration=6',
                  '-c:a', 'aac', '-y', str(source)], 30)
    assert result.returncode == 0
    audio = extract_audio(source.read_bytes(), 0, 3.4, ffmpeg)
    with wave.open(BytesIO(audio)) as wav:
        assert wav.getnchannels() == 1
        assert wav.getnframes() / wav.getframerate() == pytest.approx(3.4, abs=.001)
