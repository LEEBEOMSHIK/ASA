"""Display contract for image reviews, separate from the user's answer contract."""
from typing import Any


def obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string"}
REPORT_SCHEMA = obj({
    "summary": TEXT,
    "requirements": {"type": "array", "items": obj({
        "label": TEXT,
        "status": {"type": "string", "enum": ["met", "unmet", "unknown"]},
        "evidence": TEXT,
    })},
    "issues": {"type": "array", "items": obj({
        "title": TEXT, "location": TEXT, "evidence": TEXT, "correction": TEXT,
        "severity": {"type": "string", "enum": ["major", "minor", "unknown"]},
        "scope": {"type": "string", "enum": ["local", "global", "unknown"]},
    })},
    "edit_instruction": TEXT,
    "human_checks": {"type": "array", "items": TEXT},
})
REPORT_INSTRUCTIONS = (
    "사용자가 정한 답변은 value에 그대로 작성하고, "
    "같은 검수의 화면 표시용 요약은 report에 작성하세요. "
    "report는 한국어로 작성하세요. requirements에는 입력 설정에서 실제 확인한 요구사항과 "
    "이미지 근거를 기록하세요. 확인 불가능하면 unknown이며 충족으로 간주하지 마세요. "
    "issues는 관찰된 문제만 포함하고 title/location/evidence/correction을 구분하세요. "
    "심각도나 범위를 판단할 수 없으면 unknown을 사용하세요. "
    "edit_instruction에는 문제를 고치되 유지할 특징을 포함한 복사 가능한 수정 지시를 작성하세요. "
    "문제가 없으면 issues는 빈 목록, edit_instruction은 빈 문자열입니다. "
    "human_checks에는 최종 판단이 필요한 부분을 기록하세요. "
    "임의 점수나 사용자 확정을 만들지 마세요."
)
