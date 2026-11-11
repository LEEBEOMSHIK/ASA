"""Saved voice descriptions; no synthesis, voice IDs, or external calls."""

import json
from typing import Any
from uuid import UUID

from pydantic import Field

from asa.audio_contracts import AudioSettings, Speaker, Strict
from asa.registry.schemas import RegistryError


class Direction(Strict):
    id: str = Field(min_length=1, max_length=64)
    instructions: str = Field(default='', max_length=1000)
    language: str = Field(default='한국어', min_length=1, max_length=80)
    speed: float = Field(default=1, ge=0.75, le=1.25, allow_inf_nan=False)
    enabled: bool = True


class DirectionEdit(Strict):
    revision: int = Field(ge=0, strict=True)
    speakers: list[Direction] = Field(max_length=30)


def merge_directions(original: AudioSettings, changes: list[dict[str, Any]]) -> AudioSettings:
    result = original.model_copy(deep=True)
    by_id = {speaker.id: speaker for speaker in result.speakers}
    seen = set()
    for value in changes:
        change = Direction.model_validate(value)
        if change.id not in by_id or change.id in seen:
            raise RegistryError(422, 'video_voice_speaker_invalid')
        seen.add(change.id)
        speaker = by_id[change.id]
        speaker.video_enabled = change.enabled
        speaker.voice.instructions = change.instructions
        speaker.voice.language = change.language
        speaker.voice.speed = change.speed
    return result


def snapshot_speaker(speaker: Speaker) -> dict[str, Any]:
    # Only fresh requests adopt automatic narration. Past snapshots stay immutable.
    automatic = not speaker.video_enabled or not speaker.voice.instructions.strip()
    subject = '나레이션' if speaker.role == 'narrator' else f'캐릭터 {speaker.name}의 대사'
    return {'id': speaker.id, 'name': speaker.name, 'role': speaker.role,
            'video_enabled': True if automatic else speaker.video_enabled,
            'voice': {
                'instructions': ('자동 목소리: 이야기의 내용·장르·정서, 장면의 행동과 분위기, '
                                 f'제공된 캐릭터 설정·씬 이미지에 어울리는 {subject} 목소리와 '
                                 '말투를 정하세요. 원문 발화를 생략하거나 변경하지 말고, '
                                 '다른 화자와 구분되며 작품 전체에 일관된 목소리로 전달하세요.')
                if automatic else speaker.voice.instructions,
                'language': '원문 언어' if automatic else speaker.voice.language,
                'speed': 1 if automatic else speaker.voice.speed}}


def snapshot(conn: Any, workspace: UUID, inputs: Any) -> dict[str, Any]:
    """Resolve only explicit selected image references within this workspace."""
    from asa.registry.audio_service import load

    image_ids: set[UUID] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get('format') == 'asa_scene_selection_v1':
                for scene in value.get('scenes', []):
                    try:
                        refs = json.loads(scene.get('character_settings', '[]'))
                        for ref in refs:
                            image_ids.add(UUID(ref['image_id']))
                    except (ValueError, TypeError, KeyError) as exc:
                        raise RegistryError(422, 'video_voice_source_invalid') from exc
            elif value.get('format') in {'asa_character_handoff_v1', 'asa_character_selection_v1'}:
                for char in value.get('characters', []):
                    image_ids.add(UUID(char['image_id']))
            else:
                for child in value.values():
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(inputs)
    if not image_ids:
        return {'speakers': [], 'sources': []}
    rows = conn.execute(
        'SELECT DISTINCT p.request_id,p.source_version,j.character_id FROM character_image_jobs j '
        'JOIN character_projects p ON p.workspace_id=j.workspace_id AND p.id=j.project_id '
        "WHERE j.workspace_id=%s AND j.id=ANY(%s) AND p.kind='character' "
        "AND j.status='succeeded' ORDER BY p.request_id,p.source_version,j.character_id",
        (workspace, list(image_ids))).fetchall()
    speakers: dict[str, dict[str, Any]] = {}
    sources = []
    loaded = {}
    for row in rows:
        key = (row['request_id'], row['source_version'])
        if key not in loaded:
            loaded[key] = load(conn, workspace, *key)
        source = loaded[key]
        source_key = {'request_id': str(row['request_id']), 'version': row['source_version'],
                      'revision': source['revision']}
        if source_key not in sources:
            sources.append(source_key)
        for speaker in source['settings'].speakers:
            if speaker.id != row['character_id'] and speaker.role != 'narrator':
                continue
            value = snapshot_speaker(speaker)
            if speaker.id in speakers and speakers[speaker.id] != value:
                raise RegistryError(422, 'video_voice_source_conflict')
            speakers[speaker.id] = value
    return {'speakers': list(speakers.values()), 'sources': sources}


def answer_contract(conn: Any, workspace: UUID, request: UUID | str,
                    version: int) -> dict[str, Any] | None:
    """Edited answers inherit the originating attempt's immutable voice settings."""
    row = conn.execute(
        'WITH RECURSIVE lineage AS ('
        'SELECT version,base_version,operation_id FROM script_versions WHERE workspace_id=%s '
        'AND request_id=%s AND version=%s UNION ALL '
        'SELECT v.version,v.base_version,v.operation_id FROM script_versions v JOIN lineage l '
        'ON v.version=l.base_version AND v.version<l.version '
        'WHERE v.workspace_id=%s AND v.request_id=%s) '
        'SELECT a.prompt::jsonb AS contract FROM lineage l '
        'JOIN script_attempts a ON a.id=l.operation_id AND a.workspace_id=%s AND a.request_id=%s '
        'ORDER BY l.version DESC LIMIT 1',
        (workspace, request, version, workspace, request, workspace, request)).fetchone()
    return row['contract'] if row else None


def answer_snapshot(conn: Any, workspace: UUID, request: UUID,
                    version: int) -> dict[str, Any] | None:
    contract = answer_contract(conn, workspace, request, version)
    return contract.get('video_voice_directions') if contract else None


def apply_snapshot(seed: dict[str, Any], directions: dict[str, Any]) -> dict[str, Any]:
    result = AudioSettings.model_validate(seed)
    saved = {s['id']: s for s in directions['speakers']}
    known = set(saved)
    for speaker in result.speakers:
        if known and speaker.id not in known:
            raise RegistryError(422, 'video_voice_speaker_mismatch')
        if speaker.id in saved:
            value = saved.pop(speaker.id)
            speaker.name = value['name']
            speaker.role = value['role']
            speaker.video_enabled = value['video_enabled']
            speaker.voice = speaker.voice.model_copy(update=value['voice'])
    from asa.audio_contracts import Speaker

    result.speakers.extend(Speaker.model_validate(s) for s in saved.values())
    result.delivery_mode = 'video'
    result.enabled = False  # Legacy separate-audio mixing is never enabled implicitly.
    return result.model_dump(mode='json')


def validate_timeline(settings: AudioSettings, end: float) -> None:
    active = {s.id for s in settings.speakers if s.video_enabled}
    if any(c.end > end for c in settings.cues if c.speaker_id in active):
        raise RegistryError(422, 'audio_timeline_invalid')


def clip_audio_prompt(settings: AudioSettings, start: float, end: float) -> str:
    speakers = {s.id: s for s in settings.speakers}
    lines = []
    for cue in sorted(settings.cues, key=lambda c: c.start):
        speaker = speakers[cue.speaker_id]
        if not speaker.video_enabled or cue.end <= start or cue.start >= end:
            continue
        if cue.start < start or cue.end > end:
            raise RegistryError(422, 'video_voice_cue_crosses_clip')
        voice = speaker.voice
        lines.append(
            f'{cue.start-start:.2f}–{cue.end-start:.2f}초 | {speaker.name} ({speaker.id}) | '
            f'{"화면 밖 나레이션" if speaker.role == "narrator" else "캐릭터 대사"}\n'
            f'목소리 특징: {voice.instructions or "별도 특징 미지정"}; '
            f'언어: {voice.language}; 속도 의도: {voice.speed:g}배\n'
            f'감정·연출: {cue.emotion or "장면에 맞게"}\n'
            f'말할 원문: {json.dumps(cue.text, ensure_ascii=False)}')
    if not lines:
        return ''
    return ('[클립 음성 연출]\n아래 시간은 이 클립 시작 기준입니다. 지정 화자가 원문을 '
            '말하고 인물별 목소리 특징을 유지하세요. 다른 화자에게 대사를 넘기거나 '
            '추가 대사·나레이션을 만들지 마세요.\n' + '\n\n'.join(lines))


INSTRUCTIONS = '''[영상 모델 음성 연출]
이번 실행은 별도 TTS 샘플 선택/무음 영상 지시를 대체한다. 전달된 video_voice_directions의
화자 ID와 이름을 유지하고 목소리 특징·언어·속도를 해당 화자에게 적용한다.
audio_plan은 enabled=false로 두고 speakers와 cues를 출력한다. cues에는 원문 대사와
나레이션, 전체 타임라인의 start/end, emotion을 빠짐없이 기록한다. 하나의 발화가 클립
경계를 가로지르지 않도록 동작과 클립을 계획한다. 비디오 prompt에도 해당 클립의 화자와
목소리 특징을 반영한다. video_enabled=false 화자는 발화시키지 않는다.
자동 목소리 나레이션은 원문 대사를 유지하고 이야기·장면 분위기·제공된 이미지로 음색과
말투를 정한다. 목소리 직접 설정이 없다는 이유로 나레이션을 삭제하거나 대사를 추가하지 않는다.
오디오 지원 모델이면 audio=true로 한다. 미지원이면 audio=false로 두고 edit_notes에
음성 생성 미지원이라고 명시한다. 목소리 고정이나 정확한 발화 길이를 보장하지 않는다.
시간 측정용 TTS와 과거 음성은 참고 자료이며 최종 영상 음성으로 자동 합성하지 않는다.
'''
