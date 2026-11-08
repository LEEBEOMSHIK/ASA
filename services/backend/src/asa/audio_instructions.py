"""Add an editable audio timeline to future video planner answers."""

from copy import deepcopy
from typing import Any

MARKER = "[별도 음성 제작 v1]"
COMMON = """[별도 음성 제작 v1]
audio_plan에 enabled=true, speakers, cues를 출력한다. speakers는 원본 캐릭터의
안정적인 id와 name, role(character/narrator)을 유지한다. 내레이터는 별도 ID로 둔다.
cues에는 id, speaker_id, text(말할 원문), start/end(전체 영상 시작부터의 초), emotion을
적는다. 원본 대사와 내레이션을 누락·요약하지 말고 영상 시간 안에 충분한 발화 시간을
배분한다. 같은 화자의 발화를 겹치지 않는다. 발화가 없으면 빈 배열이다.
영상 모델에는 audio=false로 요청하고 prompt에는 음성 생성 지시를 넣지 않는다.
목소리 모델·음색은 사용자가 캐릭터 목소리를 가져오거나 화면에서 선택한다.
음악은 edit_notes에 분위기와 시작·끝 의도를 제안하되 실제 음원 ID를 만들지 않는다.
사용자가 업로드한 음원을 선택하고 음량·반복·페이드·대사 중 음량 감소를 설정한다.
실제 음성을 생성한 뒤 길이를 검토·확정한다. 할당 시간을 넘으면 대사나 시간표를
수정해야 하며 자르거나 자동으로 압축하지 않는다. 모든 영상·음성이 확정된 후
별도 오디오 워커가 컷 연결과 음성·음악 합성을 수행한다. 생성된 영상의 원래 소리는
제거된다. 자막·디졸브·립싱크 자동 보정은 지원하지 않는다. 합성 결과도 사용자가
미리보기로 검토·확정해야 한다. 같은 음색 설정이 완전히 동일한 연기를 보장하지 않는다.
"""
STYLES = {
    "animation_2d": "2D 캐릭터의 말투·감정 대비를 유지하고 대사 사이 반응 포즈 시간을 둔다.",
    "animation_3d": "3D 캐릭터의 호흡·몸짓과 발화 시간을 맞추고 동작 안착 시간을 확보한다.",
    "live_action": "실사는 자연스러운 호흡·휴지를 배분하고 화면 발화와 내레이션을 구분한다.",
}


def upgrade_definition(definition: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(definition)
    result["instructions"] = result["instructions"].replace(
        "prompt_en에는 음성 생성 지시를 넣지 않는다.", "prompt에는 음성 생성 지시를 넣지 않는다.")
    from asa.video_continuity_instructions import COMMON as legacy

    revised = legacy.replace(
        "전체 영상 자동 조립, 오디오 믹싱, 자막 합성, 공급자 영상 연장 API는 미구현이다.",
        "컷 연결·오디오 합성은 별도 확정 과정에서 수행한다. 자막·공급자 영상 연장은 미구현이다.",
    )
    result["instructions"] = result["instructions"].replace(legacy, revised)
    if MARKER not in result["instructions"]:
        result["instructions"] += "\n\n" + COMMON
    for key, value in result.get("video_prompt_modules", {}).get("style_instructions", {}).items():
        if key in STYLES and MARKER not in value:
            result["video_prompt_modules"]["style_instructions"][key] += (
                "\n\n" + MARKER + " " + STYLES[key]
            )

    def obj(properties: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    def string(limit: int) -> dict[str, Any]:
        return {"type": "string", "maxLength": limit}

    result["output_schema"]["properties"]["audio_plan"] = obj(
        {
            "enabled": {"type": "boolean"},
            "speakers": {
                "type": "array",
                "maxItems": 30,
                "items": obj(
                    {
                        "id": string(64),
                        "name": string(100),
                        "role": {"type": "string", "enum": ["character", "narrator"]},
                    }
                ),
            },
            "cues": {
                "type": "array",
                "maxItems": 100,
                "items": obj(
                    {
                        "id": string(64),
                        "speaker_id": string(64),
                        "text": string(1500),
                        "start": {"type": "number", "minimum": 0, "maximum": 3600},
                        "end": {"type": "number", "minimum": 0, "maximum": 3600},
                        "emotion": string(300),
                    }
                ),
            },
        }
    )
    required = result["output_schema"].setdefault("required", [])
    if "audio_plan" not in required:
        required.append("audio_plan")
    return result
