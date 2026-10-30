from typing import Any

from asa.tools.search import search_tool


def inspect_text(text: str, limit: int) -> dict[str, int | bool]:
    if not isinstance(text, str) or type(limit) is not int or not 1 <= limit <= 6000:
        raise ValueError("invalid_text_inspection_input")
    return {"characters": len(text), "limit": limit, "exceeded": len(text) > limit}


def builtin_tools() -> list[dict[str, Any]]:
    items = [
        {
            "id": "asa.text.inspect:1",
            "name": "대본 길이 검사",
            "version": 1,
            "kind": "asa",
            "description": "문자 수와 지정한 길이 초과 여부를 확인합니다.",
            "usage": "검사할 대본과 허용할 최대 문자 수를 전달하세요. 공백도 문자 수에 포함됩니다.",
            "example_input": {"text": "고양이 우주", "limit": 4},
            "example_output": inspect_text("고양이 우주", 4),
            "available": True,
            "execution_available": False,
            "unavailable_reason": "등록 가능 · 실행 연결은 다음 단계에서 제공",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "maxLength": 6000, "description": "검사할 대본"},
                    "limit": {
                        "type": "integer", "minimum": 1, "maximum": 6000,
                        "description": "허용할 최대 문자 수",
                    },
                },
                "required": ["text", "limit"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "characters": {"type": "integer", "description": "공백을 포함한 문자 수"},
                    "limit": {"type": "integer", "description": "요청한 최대 문자 수"},
                    "exceeded": {"type": "boolean", "description": "길이를 초과하면 true"},
                },
            },
            "side_effect": "read",
            "cost": "free",
            "dependencies": [],
        }
    ]
    for tool_id, name in [
        ("asa.channel.read_style", "채널 스타일 조회"),
        ("asa.media.voice", "음성 생성"),
        ("asa.video.render", "영상 합성"),
    ]:
        items.append(
            {
                "id": f"{tool_id}:1",
                "name": name,
                "version": 1,
                "kind": "asa",
                "description": "후속 제작 기능",
                "available": False,
                "execution_available": False,
                "unavailable_reason": "아직 구현되지 않았습니다.",
                "input_schema": {},
                "output_schema": {},
                "dependencies": [],
            }
        )
    items.append({
        "id": "asa.media.image:1", "name": "캐릭터 기준 이미지 생성", "version": 1,
        "kind": "asa",
        "description": "캐릭터 설정에서 기준 이미지를 만들고 이전 이미지로 수정합니다.",
        "available": False, "execution_available": False, "launch_path": "/characters",
        "unavailable_reason": "에이전트 답변에서 사용 · 자동화 직접 실행 미지원",
        "usage": "캐릭터 설정 에이전트의 답변을 가져와 인물별 이미지를 생성합니다. "
                 "수정은 선택한 이전 이미지를 함께 전달하며 확정된 기준은 자동 교체하지 않습니다.",
        "input_schema": {"type": "object", "properties": {
            "character": {"type": "object", "description": "검토한 캐릭터 설정"},
            "model": {"type": "string", "description": "사용할 이미지 모델"},
            "base_id": {"type": "string", "description": "수정할 이전 이미지 ID (선택)"},
            "change": {"type": "string", "description": "수정 요청 (선택)"}},
            "required": ["character", "model"]},
        "output_schema": {"type": "object", "properties": {
            "id": {"type": "string", "description": "이미지 작업 ID"},
            "status": {"type": "string", "description": "대기·생성 중·완료·확인 필요"}}},
        "example_input": {"character": {"name": "하나", "appearance": "노란 우비"},
                          "model": "gpt-image-2.5-sunburst"},
        "example_output": {"id": "이미지 작업 ID", "status": "queued"},
        "dependencies": [], "side_effect": "write", "cost": "paid",
    })
    items.append(search_tool())
    return items
