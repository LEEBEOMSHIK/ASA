"""AI-authored human review metadata. Never part of a video generation payload."""
import json
from typing import Any, Literal

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from asa.audio_contracts import AudioSettings
from asa.voice_directions import clip_audio_prompt


class ReviewSpan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    clip_id: str = Field(min_length=1, max_length=100)
    section: Literal['prompt', 'voice', 'edit_notes']
    quote: str = Field(min_length=1, max_length=4000)
    kind: Literal['camera', 'expression', 'gaze', 'action', 'voice', 'music']


class ReviewAnnotations(BaseModel):
    spans: list[ReviewSpan] = Field(default_factory=list, max_length=2000)


class ReviewPart(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=32000)
    kind: Literal['camera', 'expression', 'gaze', 'action', 'voice', 'music', 'none']


class ReviewSection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: str = Field(min_length=1, max_length=120)
    parts: list[ReviewPart] = Field(max_length=1000)


class ReviewPartition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sections: list[ReviewSection] = Field(max_length=300)


INSTRUCTIONS = '''review_annotations는 사람이 계획을 검토하기 위한 별도 분류입니다.
원문을 고치거나 분류 라벨을 본문에 넣지 마세요. 키워드가 아니라 문맥과 의미로
클립별 prompt, edit_notes, 음성 지시의 구절을 분류하세요. camera=구도·카메라,
expression=표정, gaze=시선, action=동작, voice=목소리·말투, music=배경음악.
quote에는 원문에서 연속된 구절을 정확히 복사하세요(공백·문장부호 포함).
하나의 구절에는 가장 적절한 분류 하나만 붙이고 서로 겹치지 않게 하세요.
대사 자체는 분류하지 말고 발화 방식만 분류하세요. 반복되어 위치를 특정할 수 없는
짧은 단어 대신 문맥이 있는 고유한 구절을 선택하세요. 분류할 내용이 없으면 빈 배열입니다.
section voice는 audio_plan의 목소리 특징/감정 연출 문구에 해당합니다.'''

PARTITION_INSTRUCTIONS = '''당신은 완성된 영상 계획을 읽는 구절 분류 전담 검토자입니다.
계획 작성·요약·수정은 하지 마세요. 입력은 key=클립ID:section인 정확한 원문 사전입니다.
입력의 모든 key를 sections에 정확히 한 번 반환하세요. 각 본문 전체를 원래 순서대로
parts로 나누고 text와 kind를 붙이세요. parts의 text를 이어 붙이면 공백·줄바꿈·문장부호까지
입력과 완전히 같아야 합니다. 빈 본문만 parts=[]입니다. 대표 구절만 발췌하면 실패입니다.
kind: camera=구도/화면배치/카메라연출/조명, expression=얼굴표정/눈썹/미소,
gaze=시선의 방향/대상/눈맞춤, action=신체동작/자세/이동,
voice=목소리특징/발화속도/언어/감정/말투/발화대상/발화순서,
music=배경음악/음량/음악의 시작과 끝,
none=위 범례 대상이 아닌 내용(대사 원문, 단순 화풍, 기타 안내 등).
voice는 실제 화자의 목소리와 발화 방식만 뜻합니다. 화면 밖 효과음·충격음·환경음의
크기나 부드러움은 voice가 아니며 music도 아닙니다. 효과음 지시는 none입니다.
이 규칙은 발화/시간 조건 규칙보다 우선합니다. 먼저 실제 화자가 말하는 것인지,
효과음이 들리는 것인지 판단하세요. '3.6초부터 미끄럼틀 뒤 화면 밖에서 부드럽게
“히익… 딸꾹!”이 들린다.'는 시간·위치·부드럽게·들린다까지 전부 none입니다.
인용부호가 있다고 발화가 아니며, '들린다'를 '말한다'로 해석하지 마세요.
어떤 인물이 등장/후퇴/튀는 동작은 action, 보이는 대상의 배치/구도는 camera입니다.
기존 이미지와의 충돌 설명, 생성 차단 사유, 재제작 승인 조건은 연출 실행 지시가 아니라
검토 안내이므로 none입니다. 실제 적용할 연출을 서술하는 구절만 분류하세요.
같은 편집 문단 안에서도 차단 안내 뒤의 실제 실행 지시는 별도로 분류하세요.
'대사 끝 딸꾹질은 다음 컷의 튐으로 연결한다.'는 실제 동작 연결이므로 전체 action입니다.
효과음 자체의 음량/음색 설명과 효과음을 기점으로 한 신체동작 연결을 구분하세요.
범례의 경계는 다음처럼 고정합니다. 조명·빛의 방향/강도 및 위협적 조명 금지는 camera.
얼굴·신체 부위가 특정되지 않은 시각 반응 '놀란다'는 expression이며 몸 움직임을 추정하지
마세요. 웃는 연기의 '까르르 웃는다'는 expression으로 함께 묶습니다. 후반 편집에서
웃음소리의 합성/중복 금지만 설명하면 none입니다. 대사 원문은 계속 none이지만
'이루리에게 말한다', 발화 순서와 발화 동안의 동시성 조건은 voice입니다.
시간·연결 조건을 명사구만 강조하면서 버리지 마세요. 시작 시점·지속시간·선후관계·동시성,
유지/연결/금지 술어와 조사도 해당 연출의 범례로 포함해야 합니다. 같은 분류가 계속되는
하나의 완결된 지시는 쪼개지 말고 합치세요. 예: '둘이 2초간 마주 보고'(gaze),
' '(none), '까르르 웃는다.'(expression). '3.9초부터 이루리가 눈썹을 올리고'는 expression.
여러 범례가 공유하는 술어는 복제하지 않고 가장 가까운 앞 연출 구절에 포함합니다.
예: '현재 놀이 자세'(action), '와 '(none), '오른쪽 시선을 유지한다.'(gaze).
'S01의 오른쪽 시선'(gaze), '과 '(none), '미끄럼틀 위치를 연결한다.'(camera).
'두 인물의 좌우 관계와 외형을 유지한다.'는 화면의 연속성 지시이므로 전체 camera.
공유 시간은 바로 뒤 첫 연출에, 공유 유지/연결 술어는 바로 앞 마지막 연출에 귀속하며
다른 연출도 원문상 같은 조건을 공유한다는 의미는 유지합니다. 구절/원문을 복제하지 마세요.
인용 대사는 강조하지 않되 그 양옆의 실제 발화/동시성 조건을 none으로 빠뜨리지 마세요.
예: '이루리가 '(voice), '“안녕!”'(none), '라고 말하는 동안 '(voice),
'둘이 환하게 웃으며'(expression), ' '(none), '손을 흔든다.'(action).
voice 본문의 각 실제 발화 시간 범위(예: '0.70–2.00초')도 voice입니다.
공통 사용 안내/단순 항목 라벨은 none이지만 실제 발화 시간은 시간표라는 이유로 빼지 마세요.
음성 표의 라벨 '목소리 특징:', '; 언어:', '; 속도 의도:', '감정·연출:',
'말할 원문:'은 none으로 분리하고 각 라벨 뒤 실제 값만 voice로 표시하세요.
여러 항목을 하나의 voice 블록으로 합쳐 라벨까지 칠하지 마세요.
키워드가 아니라 문맥으로 분류하세요. 해당 내용이 실제 있는데 none으로 두지 마세요.
prompt, voice, edit_notes를 모두 읽고 모든 클립의 모든 연출 지시를 분류하세요.
동일 의미가 다른 클립에 반복되어도 각각 분류하세요. voice의 공통 안내문과 말할 원문은
none, 실제 목소리 특징·언어·속도·감정 지시는 voice입니다. 인용된 대사 자체는 none입니다.
한 문장을 한 분류로 묶지 마세요. 서로 다른 연기가 연결되면 의미의 최소 연속 구절로 나눕니다.
예: '눈썹을 올리고 고개를 돌린다.' => '눈썹을 올리고'(expression), ' '(none),
'고개를 돌린다.'(action). '서로 마주 보고 웃으며 손을 흔든다.' =>
'서로 마주 보고'(gaze), ' '(none), '웃으며'(expression), ' '(none),
'손을 흔든다.'(action). '눈을 맞춘 채 입가에 미소를 띤다'도 시선과 표정으로 분리합니다.
혼합 구절에 지배적인 분류 하나만 붙이지 마세요. 시선과 카메라 대상은 문맥으로 구분하세요.
부정 지시도 의미를 보존해 분류하세요('카메라는 움직이지 않는다'도 camera).
반환 전 모든 key와 문자를 다 포함했는지, 시선/표정/동작/목소리/음악/구도의 각 지시가
none 속에 빠지지 않았는지, 혼합 구절을 분리했는지 검사하세요. 특히 각 none 구간을
다시 읽고 실제 동작 연결, 시간, 유지/연결 술어, 발화 순서·동시성이 남아 있으면 수정하세요.
분류를 위해 원문은 절대 고치지 마세요.'''


def sources(answer: dict[str, Any], audio: AudioSettings | None = None) -> dict[str, str]:
    result = {}
    if audio is None and answer.get('audio_plan'):
        audio = AudioSettings.model_validate(answer['audio_plan'])
    for clip in answer.get('clips', []):
        for section in ('prompt', 'edit_notes'):
            result[f"{clip['clip_id']}:{section}"] = clip.get(section, '')
        if audio and audio.delivery_mode == 'video':
            result[f"{clip['clip_id']}:voice"] = clip_audio_prompt(
                audio, clip['source_start_seconds'], clip['source_end_seconds'])
    return result


def validate(raw: Any, texts: dict[str, str]) -> list[dict[str, Any]]:
    """Ignore invalid, ambiguous, overlapping or invented quotes without modifying text."""
    if isinstance(raw, dict) and 'sections' in raw:
        return partition_result(raw, texts)[0]
    accepted: list[dict[str, Any]] = []
    for item in raw.get('spans', []) if isinstance(raw, dict) else []:
        try:
            span = ReviewSpan.model_validate(item)
        except ValueError:
            continue
        key = f'{span.clip_id}:{span.section}'
        text = texts.get(key, '')
        start = text.find(span.quote)
        if start < 0 or text.find(span.quote, start + 1) >= 0:
            continue
        end = start + len(span.quote)
        if any(s['key'] == key and start < s['end'] and end > s['start'] for s in accepted):
            continue
        accepted.append(dict(key=key, quote=span.quote, kind=span.kind,
                             start=start, end=end, source=text))
    return accepted


def partition_result(
    raw: Any, texts: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    issues: list[str] = []
    covered = 0
    try:
        result = ReviewPartition.model_validate(raw)
    except ValueError:
        return [], dict(complete=False, covered_sections=0, total_sections=len(texts),
                        issues=['invalid_partition'])
    keys = [s.key for s in result.sections]
    if set(keys) - texts.keys():
        issues.append('unknown_section')
    for key, text in texts.items():
        if keys.count(key) != 1:
            issues.append(f'{key}:missing_or_duplicate')
            continue
        parts = next(s.parts for s in result.sections if s.key == key)
        if ''.join(p.text for p in parts) != text:
            issues.append(f'{key}:source_mismatch')
            continue
        covered += 1
        start = 0
        for part in parts:
            end = start + len(part.text)
            if part.kind != 'none':
                accepted.append(dict(key=key, quote=part.text, kind=part.kind,
                                     start=start, end=end, source=text))
            start = end
    return accepted, dict(complete=not issues, covered_sections=covered,
                          total_sections=len(texts), issues=issues)


def save(conn: Any, workspace: Any, request: Any, version: int,
         raw: Any, texts: dict[str, str]) -> None:
    annotations = validate(raw, texts)
    status = (partition_result(raw, texts)[1]
              if isinstance(raw, dict) and 'sections' in raw else None)
    _save(conn, workspace, request, version, annotations, status)


def save_clip_revision(conn: Any, workspace: Any, request: Any, version: int, base_version: int,
                       clip_id: str, raw: Any, texts: dict[str, str]) -> None:
    prior = conn.execute(
        'SELECT annotations,validation FROM video_review_annotations '
        'WHERE workspace_id=%s AND request_id=%s AND answer_version=%s',
        (workspace, request, base_version),
    ).fetchone()
    if prior is None and raw is None:
        return
    keys = {f'{clip_id}:{section}' for section in ('prompt', 'edit_notes', 'voice')}
    revised = {key: text for key, text in texts.items() if key in keys}
    inherited_annotations = [
        entry for entry in prior['annotations']
        if entry['key'] not in keys and texts.get(entry['key']) == entry['source']
    ] if prior else []
    annotations = inherited_annotations + validate(raw, revised)
    current = partition_result(raw, revised)[1]
    previous = (prior['validation'] or {}) if prior else {}
    unaffected = texts.keys() - revised.keys()
    verified_voice = {entry['key'] for entry in inherited_annotations}
    # Prompt and edit notes are immutable on the unaffected clips. Voice settings can
    # be edited independently, so their review requires stored evidence of the text.
    inherited = sum(not key.endswith(':voice') or key in verified_voice for key in unaffected
                    ) if previous.get('complete') else 0
    status = dict(
        complete=current['complete'] and inherited == len(unaffected),
        covered_sections=current['covered_sections'] + inherited,
        total_sections=len(texts),
        issues=[*current['issues'], *(
            ['unverified_inherited_sections'] if inherited != len(unaffected) else [])],
    )
    _save(conn, workspace, request, version, annotations, status)


def _save(conn: Any, workspace: Any, request: Any, version: int,
          annotations: list[dict[str, Any]], status: dict[str, Any] | None) -> None:
    conn.execute('INSERT INTO video_review_annotations '
                 '(workspace_id,request_id,answer_version,annotations,validation) '
                 'VALUES (%s,%s,%s,%s,%s) '
                 'ON CONFLICT (workspace_id,request_id,answer_version) DO UPDATE '
                 'SET annotations=EXCLUDED.annotations,validation=EXCLUDED.validation,'
                 'updated_at=now()',
                 (workspace, request, version, Jsonb(annotations), Jsonb(status)))


def classify(model: Any, texts: dict[str, str]) -> dict[str, Any]:
    from asa.telemetry import call_config

    result = model.with_structured_output(ReviewPartition).invoke(
        [('system', PARTITION_INSTRUCTIONS),
         ('human', json.dumps(texts, ensure_ascii=False))], **call_config())
    return ReviewPartition.model_validate(result).model_dump()
