from copy import deepcopy
from uuid import uuid4

import pytest

from asa.audio_contracts import AudioSettings
from asa.audio_instructions import upgrade_definition
from asa.config import Settings
from asa.registry import video_planning
from asa.registry.history import valid_input
from asa.registry.schemas import RegistryError
from asa.video_contracts import VideoPreparation
from asa.video_providers import generation_request
from asa.voice_directions import apply_snapshot


def test_new_voice_contract_accepts_resolved_voice_and_preserves_legacy_definition():
    original = {'instructions': '', 'output_schema': {'type': 'object', 'properties': {}}}
    before = deepcopy(original)
    schema = upgrade_definition(original, video_voice=True)['output_schema']
    audio = {'enabled': False, 'speakers': [{'id': 'narrator', 'name': '나레이션',
             'role': 'narrator', 'voice': {'instructions': '따뜻한 중저음과 또렷한 발음',
                                         'language': '한국어', 'speed': 1}}], 'cues': []}
    assert valid_input({'audio_plan': audio}, schema)
    result = apply_snapshot(audio, {'resolution_version': 2, 'speakers': [],
                                   'automatic_speaker_ids': []})
    assert (result['speakers'][0]['voice']['instructions']
            == audio['speakers'][0]['voice']['instructions'])
    assert original == before
    legacy = upgrade_definition(original)['output_schema']
    assert not valid_input({'audio_plan': audio}, legacy)


def test_image_block_and_timed_events_are_executable_contract():
    from asa.registry.schemas import RegistryError
    from asa.video_plan_quality import ClipQuality, event_prompt, require_ready
    quality = ClipQuality.model_validate({'image_status': 'conflict',
        'image_reason': '참조는 이미 점프 중인데 지시는 점프 전이다.',
        'events': [{'start': 0, 'end': 2, 'minimum_seconds': 2,
                    'description': '원문대로 웃는다', 'kind': 'action'}]})
    with pytest.raises(RegistryError, match='video_start_image_review_required'):
        require_ready(quality)
    quality.image_status = 'compatible'
    require_ready(quality)
    assert '0.00–2.00' in event_prompt(quality)
    assert '원문대로 웃는다' in event_prompt(quality)


@pytest.mark.parametrize('start,end,minimum', [(0, 1, 2), (2, 1, 0)])
def test_event_duration_cannot_shrink_source_minimum(start, end, minimum):
    from pydantic import ValidationError

    from asa.video_plan_quality import TimedEvent
    with pytest.raises(ValidationError):
        TimedEvent(start=start, end=end, minimum_seconds=minimum,
                   description='웃음', kind='action')



def plan_value():
    return {'model_key': 'wan3', 'model_revision': '1', 'aspect_ratio': '9:16',
        'clips': [{'clip_id': 'G01', 'scene_id': 'S01', 'shot_id': 'shot1',
                   'image_id': str(uuid4()), 'source_start_seconds': 0,
                   'source_end_seconds': 5, 'duration_seconds': 5,
                   'prompt': '두 사람이 이야기한다.', 'source_excerpt': '',
                   'continuity_in': '함께 서 있다', 'continuity_out': '웃는다', 'split_reason': '',
                   'quality': {'image_status': 'compatible', 'image_reason': '서 있는 첫 프레임',
                               'events': [{'start': 2, 'end': 4, 'minimum_seconds': 2,
                                           'kind': 'sound_effect', 'description': '웃음 2초'}]}}],
        'duration_review': {'target_seconds': 6, 'planned_seconds': 5,
                            'difference_reason': '목표보다 1초 짧음. 실측 전.'}}


@pytest.mark.parametrize('status', ['conflict', 'unverified'])
def test_prepare_blocks_unready_images(status, monkeypatch):
    value = plan_value()
    value['clips'][0]['quality']['image_status'] = status
    monkeypatch.setattr(video_planning, 'selected_scenes', lambda *a: {'scenes': []})
    with pytest.raises(RegistryError, match='video_start_image_review_required'):
        video_planning.prepare(None, Settings(_env_file=None),
                               VideoPreparation.model_validate(value))


def test_actions_and_voice_reach_wan_request(monkeypatch):
    value = plan_value()
    clip = value['clips'][0]
    monkeypatch.setattr(video_planning, 'selected_scenes', lambda *a: {'scenes': [{
        'image_id': clip['image_id'], 'scene_id': 'S01', 'shot_id': 'shot1'}]})
    settings = Settings(_env_file=None, wan_api_key='test', wan_workspace_id='test')
    voice = AudioSettings.model_validate({'speakers': [{'id': 'child', 'name': '아이',
        'voice': {'instructions': '밝은 고음과 또렷한 발음'}}], 'cues': [
        {'id': 'c1', 'speaker_id': 'child', 'text': '안녕', 'start': 0, 'end': 1,
         'emotion': '반갑게'}]})
    prepared = video_planning.prepare(None, settings, VideoPreparation.model_validate(value),
                                     voice_settings=voice)
    spec = prepared['clips'][0]['generation_input']
    _, _, request = generation_request(settings, prepared['model_snapshot'], spec, b'image')
    prompt = request['input']['prompt']
    assert '웃음 2초' in prompt and '2.00–4.00' in prompt
    assert '밝은 고음과 또렷한 발음' in prompt and '반갑게' in prompt
    assert request['parameters']['audio'] is True


@pytest.mark.parametrize('change', ['event_end', 'total'])
def test_invalid_quality_timing_rejected(change):
    from pydantic import ValidationError
    value = plan_value()
    if change == 'event_end':
        value['clips'][0]['quality']['events'][0]['end'] = 6
    else:
        value['duration_review']['planned_seconds'] = 6
    with pytest.raises(ValidationError):
        VideoPreparation.model_validate(value)


def test_full_new_schema_voice_quality_and_post_validation_agree():
    from asa.video_plan_quality import upgrade_schema
    value = plan_value()
    # The stored base schema has only application-supported primitive types.
    properties = {}
    for key, item in value['clips'][0].items():
        if key == 'quality':
            continue
        properties[key] = ({'type': 'integer', 'minimum': 0, 'maximum': 86400}
                           if isinstance(item, int) else {'type': 'string', 'maxLength': 32000})
    base = {'instructions': '', 'output_schema': {'type': 'object', 'properties': {
        'model_key': {'type': 'string'}, 'model_revision': {'type': 'string'},
        'aspect_ratio': {'type': 'string'}, 'clips': {'type': 'array', 'items': {
            'type': 'object', 'properties': properties, 'required': list(properties)}}}}}
    schema = upgrade_schema(upgrade_definition(base, video_voice=True)['output_schema'])
    value['audio_plan'] = {'enabled': False, 'speakers': [{'id': 'narrator',
        'name': '나레이션', 'role': 'narrator', 'voice': {'instructions': '따뜻한 중저음',
        'language': '한국어', 'speed': 1}}], 'cues': []}
    assert valid_input(value, schema)
    resolved = apply_snapshot(value['audio_plan'], {'resolution_version': 2,
                             'speakers': [], 'automatic_speaker_ids': []})
    VideoPreparation.model_validate(value)
    assert resolved['speakers'][0]['voice']['instructions'] == '따뜻한 중저음'
    del value['clips'][0]['quality']
    assert not valid_input(value, schema)


def test_sound_effect_only_clip_enables_audio(monkeypatch):
    value = plan_value()
    c = value['clips'][0]
    monkeypatch.setattr(video_planning, 'selected_scenes', lambda *a: {'scenes': [{
        'image_id': c['image_id'], 'scene_id': c['scene_id'], 'shot_id': c['shot_id']}]})
    settings = Settings(_env_file=None)
    prepared = video_planning.prepare(None, settings, VideoPreparation.model_validate(value))
    assert prepared['clips'][0]['generation_input']['audio'] is True
    settings.video_model_profiles['wan3'].supports_audio = False
    with pytest.raises(RegistryError, match='video_audio_unsupported'):
        video_planning.prepare(None, settings, VideoPreparation.model_validate(value))


def test_selected_ready_clip_is_not_blocked_by_unselected_conflict(monkeypatch):
    value = plan_value()
    second = deepcopy(value['clips'][0])
    second.update(clip_id='G02', source_start_seconds=5, source_end_seconds=10)
    second['quality']['image_status'] = 'conflict'
    value['clips'].append(second)
    value['duration_review']['planned_seconds'] = 10
    c = value['clips'][0]
    monkeypatch.setattr(video_planning, 'selected_scenes', lambda *a: {'scenes': [{
        'image_id': c['image_id'], 'scene_id': c['scene_id'], 'shot_id': c['shot_id']}]})
    model = VideoPreparation.model_validate(value)
    prepared = video_planning.prepare(None, Settings(_env_file=None), model,
                                     selected_clip_ids={'G01'})
    assert [c['clip_id'] for c in prepared['clips']] == ['G01']
    with pytest.raises(RegistryError, match='video_start_image_review_required'):
        video_planning.prepare(None, Settings(_env_file=None), model, selected_clip_ids={'G02'})


def test_actual_template_and_attempt_accept_quality_plan_without_paid_calls():
    import json
    from pathlib import Path

    from asa.models import AgentAnswer
    from asa.registry.script_stage import execute_attempt
    from asa.video_plan_quality import upgrade_schema

    template = json.loads((Path(__file__).resolve().parents[3]
                          / 'docs/agent-templates/video-prompt-planner.json').read_text('utf-8'))
    schema = upgrade_schema(upgrade_definition(template, video_voice=True)['output_schema'])
    value = plan_value()
    value['clips'][0].update(style_application='', edit_notes='', connection_type='cut',
                            previous_clip_id='')
    value['audio_plan'] = {'enabled': False, 'speakers': [{'id': 'narrator',
        'name': '나레이션', 'role': 'narrator', 'voice': {'instructions': '따뜻한 중저음',
        'language': '한국어', 'speed': 1}}], 'cues': []}
    contract = {'output_schema': schema, 'video_quality_version': 1,
                'video_voice_directions': {'resolution_version': 2, 'speakers': [],
                                          'automatic_speaker_ids': []}}
    finished = []

    class Repository:
        def claim(self, *args):
            return {'prompt': json.dumps(contract)}

        def finish(self, request, attempt, answer):
            finished.append((attempt, answer))

    assert execute_attempt(Repository(), 'request', 'attempt', lambda _: AgentAnswer(value=value))
    assert finished[0][1].value == value
    assert 'error_code' not in finished[0][0]
    value['clips'][0]['quality']['events'][0]['end'] = 7
    execute_attempt(Repository(), 'request', 'attempt2', lambda _: AgentAnswer(value=value))
    assert finished[1][1] is None
    assert finished[1][0]['error_code'] == 'ai_output_invalid'
