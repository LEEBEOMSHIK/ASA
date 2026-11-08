"""Explicit, additive upgrade for video planner definitions; never queued snapshots."""
from copy import deepcopy
from typing import Any

MARKER = "[클립 연결 규칙 v1]"
TRIM_RULE = (
    "연속 연결에서는 앞 클립의 생성 길이와 사용 길이가 같아야 한다. "
    "앞 클립 끝을 잘라야 한다면 실제 마지막 프레임은 편집 종료점과 다르므로 "
    "continue를 지정하지 않는다. 연속 구간의 길이 배분을 다시 계획하거나 컷 전환으로 분리한다."
)
COMMON = (
    '[클립 연결 규칙 v1] 각 클립에 connection_type과 '
    'previous_clip_id를 출력한다. 첫 클립·장소/시간/구도가 바뀌는 '
    '독립 컷은 cut, previous_clip_id는 빈 문자열이다. 같은 '
    '동작을 이어가는 클립만 continue로 지정하고 바로 앞 clip_id를 '
    'previous_clip_id에 쓴다. 모든 클립을 무조건 연속으로 연결하지 '
    '않는다. cut은 해당 확정 씬 이미지에서 시작한다. continue는 '
    '사용자가 확정한 앞 영상의 실제 마지막 프레임에서 시작하며, 앞 영상 확정 '
    '전 다음 영상 생성은 차단된다. 계획 시 continuity_out은 목표 '
    '상태이지 실제 관찰 결과가 아니다. 앞 영상에 없던 동작이 완료됐다고 '
    '단정하지 않는다. 동작 진행 방향, 시선, 카메라 축, 인물·소품 위치, '
    '접촉 상태를 continuity_in/out에 적는다. 같은 동작을 '
    '중복하거나 순간 이동하지 않는다. 얼굴·의상·빛·공간을 유지하되 대본상 '
    '변화는 전후 상태를 명시한다. 확정 영상이 바뀌면 후속 연결을 재검토해야 '
    '한다. 현재 지원은 클립 생성과 확정 마지막 프레임 전달이다. 전체 영상 '
    '자동 조립, 오디오 믹싱, 자막 합성, 공급자 영상 연장 API는 '
    '미구현이다. 컷 전환·디졸브·오디오 연결·여분 길이 제거는 '
    'edit_notes에 후반 작업으로 표시한다. 계획만으로 최종 영상이 '
    '완성됐다고 말하지 않는다. '
)
STYLES = {
    'animation_2d': (
        '2D 연속 컷은 선 두께·색면·실루엣·캐릭터 비율과 포즈를 유지한다. 마지막 '
        '포즈에서 다음 동작으로 이어지도록 '
        'anticipation/action/settle 단계와 시선·화면 이동 '
        '방향을 명시한다. 컷 전환은 구도 변경임을 구분하고 중간 프레임 보간이 '
        '구현되었다고 가정하지 않는다. '
    ),
    'animation_3d': (
        '3D 연속 컷은 모델 비율·재질·조명·카메라 축을 유지한다. 발바닥 접지, '
        '체중 이동, 손과 소품 접촉, 관성 및 동작 안착을 마지막 상태와 다음 시작 '
        '상태에 명시한다. 컷 전환은 독립 구도로 계획하고 자동 리깅·모션 블렌딩을 '
        '가정하지 않는다. '
    ),
    'live_action': (
        '실사 연속 컷은 인물 정체성·의상·렌즈감·노출·색온도·광원 방향을 유지한다. '
        '180도 축과 시선 연결, 손 위치·소품·체중 이동을 이어간다. 컷 '
        '전환에서는 매치 온 액션 등 편집 의도를 적되 광학 흐름 보간·립싱크·오디오 '
        '브리지가 자동 처리된다고 가정하지 않는다. '
    ),
}


def upgrade_definition(definition: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(definition)
    props = result.get("output_schema", {}).get("properties", {})
    items = props.get("clips", {}).get("items", {})
    if items.get("type") != "object":
        raise ValueError("video_clip_output_schema_missing")
    if MARKER not in result["instructions"]:
        result["instructions"] += "\n\n" + COMMON
    if TRIM_RULE not in result["instructions"]:
        result["instructions"] += "\n\n" + TRIM_RULE
    styles = result.get("video_prompt_modules", {}).get("style_instructions", {})
    for name, text in STYLES.items():
        if styles.get(name) and MARKER not in styles[name]:
            styles[name] += "\n\n" + MARKER + "\n" + text
    items["properties"].update({
        "connection_type": {"type": "string", "enum": ["cut", "continue"],
                            "description": "컷 전환 또는 앞 확정 영상에서 연속 동작"},
        "previous_clip_id": {"type": "string", "maxLength": 100,
                             "description": "continue는 바로 앞 clip_id, cut은 빈 문자열"},
    })
    items["required"] = list(dict.fromkeys([
        *items.get("required", []), "connection_type", "previous_clip_id",
    ]))
    return result
