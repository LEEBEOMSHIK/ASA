"""Explicit scene follow-up contract; never infer speech from arbitrary answer text."""
from typing import Any, Literal
from uuid import UUID, uuid5

from psycopg.types.json import Jsonb
from pydantic import Field

from asa.audio_contracts import AudioSettings, Cue, Identifier, Strict
from asa.config import Settings


class TimingSpeaker(Strict):
    id: Identifier
    name: str = Field(min_length=1, max_length=100)
    role: Literal['character', 'narrator']


class SceneTimingPlan(Strict):
    duration: float = Field(gt=0, le=3600, allow_inf_nan=False)
    planned_duration: float | None = Field(default=None, gt=0, le=3600, allow_inf_nan=False)
    speakers: list[TimingSpeaker] = Field(max_length=30)
    cues: list[Cue] = Field(max_length=200)


INSTRUCTIONS = '''본문 value와 별도로 timing_plan을 반드시 작성하세요.
duration은 요청한 전체 영상 길이(초)이며 없으면 계획의 총길이입니다.
planned_duration은 필요한 행동·반응·발화로 구성한 실제 계획의 끝 시각입니다.
목표 duration까지 무음·시선 유지·마지막 여운을 늘리지 마세요. 부족하면 부족분을 밝히세요.
본문에 행동·반응별 시작/끝/초수/구체적 동작/배정 근거/발화 동시 여부를 적으세요.
계획끝은 마지막 발화끝 이상이며 이후 필요한 행동이 있을 때만 그 시간을 포함합니다.
speakers에는 실제 대사 화자와 내레이터, cues에는 모든 발화 원문을 정확히 한 번씩 담습니다.
화면·카메라 설명과 효과음을 읽을 대사에 넣지 마세요. 대사가 없는 작품은 빈 cues입니다.
start/end는 전체 영상 기준 초입니다. 본문 시간표와 일치해야 합니다.
같은 화자의 발화는 겹치지 않아야 하며 대사 중간을 임의로 생략하지 마세요.
이 계획으로 시간 측정용 TTS가 자동 접수됩니다. 예상 시간을 실측값이라고 쓰지 마세요.
최종 캐릭터 목소리는 별도로 선택합니다. 측정 발화의 감정은 과장하지 않고 원문 낭독용입니다.'''


def timing_settings(plan: SceneTimingPlan, model_key: str, voice: str) -> AudioSettings:
    return AudioSettings.model_validate({
        'enabled': True, 'purpose': 'timing', 'timing_duration_seconds': plan.duration,
        'timing_auto_align': True,
        'timing_preview_seconds': max(plan.planned_duration or 0,
                                      max((c.end for c in plan.cues), default=0)) or None,
        'speakers': [{**s.model_dump(), 'voice': {'model_key': model_key, 'voice': voice,
                     'speed': 1.0, 'language': '한국어',
                     'instructions': '시간 측정용. 자연스럽게 원문만 읽으세요. 배속하지 마세요.'}}
                    for s in plan.speakers],
        'cues': [c.model_dump() for c in plan.cues]})


def enqueue_timing(conn: Any, settings: Settings, request_id: str, version: int,
                   value: dict[str, Any]) -> None:
    from asa.registry.audio_service import speech_key, speech_spec

    data = timing_settings(SceneTimingPlan.model_validate(value), settings.audio_timing_model_key,
                           settings.audio_timing_voice)
    inserted = conn.execute('INSERT INTO audio_settings VALUES (%s,%s,%s,1,%s) '
                            'ON CONFLICT DO NOTHING RETURNING revision',
                            (settings.workspace_id, request_id, version,
                             Jsonb(data.model_dump(mode='json')))).fetchone()
    if not inserted:
        return
    for cue in data.cues:
        spec = {**speech_spec(settings, data, cue.id), 'purpose': 'timing'}
        operation = uuid5(UUID(str(request_id)), f'scene-timing:{version}:{cue.id}')
        conn.execute('INSERT INTO audio_jobs(workspace_id,id,request_id,answer_version,kind,'
                     'cue_id,fingerprint,input,status) '
                     "VALUES (%s,%s,%s,%s,'speech',%s,%s,%s,'queued') ON CONFLICT DO NOTHING",
                     (settings.workspace_id, operation, request_id, version, cue.id,
                      speech_key(spec), Jsonb(spec)))


def finish_timing(conn: Any, settings: Settings, request_id: str, version: int) -> None:
    from asa.registry.audio_service import speech_key, speech_spec

    row = conn.execute('SELECT settings FROM audio_settings WHERE workspace_id=%s '
                       'AND request_id=%s AND answer_version=%s FOR UPDATE',
                       (settings.workspace_id, request_id, version)).fetchone()
    if not row:
        return
    data = AudioSettings.model_validate(row['settings'])
    if data.purpose != 'timing' or not data.timing_auto_align:
        return
    durations = {}
    for cue in data.cues:
        key = speech_key({**speech_spec(settings, data, cue.id), 'purpose': 'timing'})
        job = conn.execute('SELECT duration,error_code,status FROM audio_jobs WHERE '
                           'workspace_id=%s AND request_id=%s AND answer_version=%s '
                           "AND fingerprint=%s AND kind='speech' ORDER BY created_at DESC LIMIT 1",
                           (settings.workspace_id, request_id, version, key)).fetchone()
        if not job or job['status'] != 'review' or job['error_code'] or not job['duration']:
            return
        durations[cue.id] = job['duration']
    cursor = previous_end = 0.0
    for cue in sorted(data.cues, key=lambda c: c.start):
        gap, previous_end = max(0, cue.start-previous_end), cue.end
        cue.start = cursor + gap
        cue.end = cue.start + durations[cue.id]
        cursor = cue.end
    # Preserve the originally allocated trailing pause even if speech runs longer.
    trailing = max(0, (data.timing_preview_seconds or previous_end)-previous_end)
    if data.cues and cursor + trailing > 3600:
        return
    data.timing_preview_seconds = cursor + trailing or None
    data.timing_auto_align = False
    conn.execute('UPDATE audio_settings SET settings=%s,revision=revision+1 WHERE workspace_id=%s '
                 'AND request_id=%s AND answer_version=%s',
                 (Jsonb(data.model_dump(mode='json')), settings.workspace_id, request_id, version))
