"""Restrict a model revision to the requested clip in a saved answer."""

from typing import Any

from pydantic import ValidationError

from asa.audio_contracts import AudioSettings
from asa.registry.history import valid_input
from asa.registry.schemas import RegistryError
from asa.video_contracts import VideoPreparation
from asa.voice_directions import clip_audio_prompt, validate_timeline

FIXED_FIELDS = (
    'clip_id', 'scene_id', 'shot_id', 'image_id', 'source_excerpt',
    'source_start_seconds', 'source_end_seconds', 'duration_seconds',
)


def validate_plan(answer: Any, audio: AudioSettings) -> VideoPreparation:
    plan = VideoPreparation.model_validate(answer)
    if audio.delivery_mode == 'video':
        validate_timeline(audio, plan.clips[-1].source_end_seconds)
        for clip in plan.clips:
            clip_audio_prompt(audio, clip.source_start_seconds, clip.source_end_seconds)
    return plan


def revision_contract(
    answer: Any, output_schema: dict[str, Any], base_contract: dict[str, Any],
    clip_id: str, audio: AudioSettings,
) -> dict[str, Any]:
    clip_schema = output_schema.get('properties', {}).get('clips', {}).get('items', {})
    try:
        plan = validate_plan(answer, audio)
    except (RegistryError, ValidationError) as exc:
        raise RegistryError(422, 'video_clip_revision_unavailable') from exc
    if (clip_schema.get('type') != 'object' or not valid_input(answer, output_schema)
            or not any(clip.clip_id == clip_id for clip in plan.clips)):
        raise RegistryError(422, 'video_clip_revision_unavailable')
    return {
        **{key: base_contract[key] for key in ('video_voice_directions', 'video_quality_version')
           if key in base_contract},
        'revision_clip_id': clip_id,
        'clip_output_schema': clip_schema,
        'effective_clip_revision_audio': audio.model_dump(mode='json'),
    }


def merge_clip_revision(contract: dict[str, Any], replacement: Any) -> dict[str, Any]:
    clip_id = contract['revision_clip_id']
    if not valid_input(replacement, contract['clip_output_schema']):
        raise ValueError('invalid_agent_output')
    answer = contract['previous_answer']
    previous = next(clip for clip in answer['clips'] if clip['clip_id'] == clip_id)
    if any(replacement.get(key) != previous.get(key) for key in FIXED_FIELDS):
        raise ValueError('invalid_agent_output')
    merged = {**answer, 'clips': [
        replacement if clip['clip_id'] == clip_id else clip for clip in answer['clips']
    ]}
    if not valid_input(merged, contract['output_schema']):
        raise ValueError('invalid_agent_output')
    try:
        audio = AudioSettings.model_validate(contract['effective_clip_revision_audio'])
        validate_plan(merged, audio)
    except (RegistryError, ValidationError) as exc:
        raise ValueError('invalid_agent_output') from exc
    return merged


INSTRUCTIONS = '''[클립 단독 수정]
revision_clip_id로 지정한 클립 객체 한 개만 value에 반환하세요. 전체 계획, clips 배열,
audio_plan, duration_review는 반환하지 않습니다. 다른 지침의 전체 계획 출력 조건보다
이 클립 단독 출력 조건을 우선하세요. 이전 답변, 공통 음성 설정과 앞뒤 클립은
연결을 확인하는 참고 자료입니다. 지정 클립의 clip_id, scene_id, shot_id, image_id,
source_excerpt, source_start_seconds, source_end_seconds, duration_seconds는 그대로
유지하세요. 기존 음성 대사와 타이밍을 유지하고 사용자 수정 요청의 지정 클립 연출만 반영하세요.
정해진 시간 안의 동작, 앞뒤 연결과 해당 이미지 기준을 확인하세요. JSON 스키마의 필수
항목과 길이 제한을 지키세요. quality가 필요한 경우 실제 시작 이미지와 첫 동작을 비교해
확인할 수 없으면 unverified, 충돌하면 conflict, 확인된 호환만 compatible로 기록하세요.
행동·반응·효과음의 시작과 종료는 클립 상대 시간이며 원문의 최소 지속 시간을 지키세요.
기존 발화와 동시인 동작은 시간을 겹치게 배치하세요.'''
