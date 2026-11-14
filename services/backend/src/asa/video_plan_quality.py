"""New-plan quality contract; legacy answers remain readable and immutable."""

from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from asa.registry.schemas import RegistryError


class TimedEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start: float = Field(ge=0, le=120, allow_inf_nan=False)
    end: float = Field(gt=0, le=120, allow_inf_nan=False)
    minimum_seconds: float = Field(ge=0, le=120, allow_inf_nan=False)
    kind: Literal['action', 'sound_effect', 'reaction']
    description: str = Field(min_length=1, max_length=300)

    @model_validator(mode='after')
    def interval(self) -> 'TimedEvent':
        if self.end <= self.start or self.end - self.start + 0.001 < self.minimum_seconds:
            raise ValueError('video_event_duration_invalid')
        return self


class ClipQuality(BaseModel):
    model_config = ConfigDict(extra='forbid')
    image_status: Literal['compatible', 'conflict', 'unverified']
    image_reason: str = Field(min_length=1, max_length=300)
    events: list[TimedEvent] = Field(min_length=1, max_length=20)


class DurationReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    target_seconds: float = Field(ge=0, le=86400, allow_inf_nan=False)
    planned_seconds: float = Field(gt=0, le=86400, allow_inf_nan=False)
    difference_reason: str = Field(min_length=1, max_length=500)


def inline_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    definitions = schema.pop('$defs', {})

    def expand(value: Any) -> Any:
        if isinstance(value, list):
            return [expand(v) for v in value]
        if not isinstance(value, dict):
            return value
        if '$ref' in value:
            return expand(definitions[value['$ref'].rsplit('/', 1)[-1]])
        expanded = {k: expand(v) for k, v in value.items() if k != 'title'}
        # Registry validation requires inclusive bounds; Pydantic also enforces >0.
        if 'exclusiveMinimum' in expanded:
            expanded['minimum'] = expanded['exclusiveMinimum']
        return expanded

    return expand(schema)  # type: ignore[no-any-return]


def upgrade_schema(original: dict[str, Any]) -> dict[str, Any]:
    schema = deepcopy(original)
    clip = schema['properties']['clips']['items']
    clip['properties']['quality'] = inline_schema(ClipQuality)
    clip.setdefault('required', []).append('quality')
    schema['properties']['duration_review'] = inline_schema(DurationReview)
    schema.setdefault('required', []).append('duration_review')
    return schema


def require_ready(quality: ClipQuality | None) -> None:
    if quality is not None and quality.image_status != 'compatible':
        raise RegistryError(422, 'video_start_image_review_required')


def event_prompt(quality: ClipQuality | None) -> str:
    if quality is None:
        return ''
    return ('[시간별 행동·효과음 / 클립 시작 기준]\n'
            '겹치는 시간의 행동과 발화는 동시에 진행하세요. 정해진 시간과 원문을 유지하세요.\n'
            + '\n'.join(f'{e.start:.2f}–{e.end:.2f}초 | {e.kind} | {e.description}'
                        for e in quality.events))


INSTRUCTIONS = '''[영상 계획 품질 계약 v1]
실제 연결된 시작 이미지를 기준으로 클립 첫 동작이 가능한지 확인한다. 이미 등장·점프한
이미지를 등장·점프 이전 상태로 가정하지 않는다. 이미지로 확인하지 못하면 unverified,
충돌하면 conflict, 확인된 호환 상태만 compatible로 quality.image_status에 기록한다.
image_reason에는 실제 시작 상태와 요구 동작의 비교 근거를 적는다. 부적합 이미지로는 생성이
차단된다. '이미지가 준비되면'이라는 조건문이나 edit_notes의 보류 안내로 대체하지 않는다.
부적합 이미지는 그대로 보존하고 교체가 필요한 이유를 적는다. 존재하지 않는 이미지 ID를
만들지 않는다. 앞 컷의 그림자·인물·소품이 다음 컷에서 이유 없이 사라지지 않게 연결한다.
각 클립 quality.events에 행동·반응·효과음의 시작/종료 초를 클립 상대 시간으로 작성한다.
원문에서 지정한 웃음·효과음 등의 최소 시간을 minimum_seconds에 그대로 기록한다.
명시 시간이 없을 때만 0을 사용한다. 원문의 발화·행동·효과음을 임의로 생략/축소/반복하지 않는다.
사용자가 기존 이미지를 유지하는 컷 생략·동작 마무리·발화 위치 조정을 명시적으로 허용했다면,
그 허용 범위의 최종 실행 동작을 실제 첫프레임과 대조한다. 원문 대비 조정과 생략된 선행 동작을
image_reason/edit_notes에 밝히되, 승인된 조정 자체만으로 conflict나 이미지 교체 필수로
판정하지 않는다. 이전 답변의 compatible 표기를 그대로 믿거나 사용자 승인만으로 실제 충돌을
무시하지 않는다. 조정 후에도 불가능한 동작은 conflict, 이미지 미확인은 unverified를 유지한다.
발화는 audio_plan.cues, 행동·효과음은 events에 작성하며 동시에 진행할 동작은 시간을
겹치게 배치한다. 마지막 대사와 손 흔들기 같은 동시 동작을 대사 이후로 밀어내지 않는다.
단일 인물이 순차로 수행할 동작을 억지로 겹치지 않는다. 모든 event는 클립 길이 안에 둔다.
events는 실제 영상 모델에 전달된다. 중요한 연출을 edit_notes에만 적지 않는다.
duration_review에는 원본 목표 길이(target_seconds, 목표가 없으면 0), 계획 총 길이
(planned_seconds), 차이 이유와 재배분 근거(difference_reason)를 적는다. 목표 길이는
입력에서 그대로 가져오며 임의로 계획 길이에 맞추지 않는다. 목표와 다른 길이를 충족했다고
표시하지 않는다. 원문을 줄이거나 무음·반복으로 억지로 채우지 않는다. 어린이 대상 발화는
충분한 발음·쉼 시간을 배정하고 실측하지 않은 길이를 실측했다고 쓰지 않는다.
화자별 공통 목소리는 한 번 정하고 유지한다. 장면 감정·말투는 cues.emotion에 분리한다.
필수 필드와 maxLength, 클립 타임라인 연속성, 발화와 동작 시간, 참조 이미지 ID를 확인한다.
'''
