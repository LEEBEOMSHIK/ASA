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
        ("asa.media.image", "이미지 생성"),
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
    items.append(search_tool())
    return items
