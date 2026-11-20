"""Add an editable audio timeline to future video planner answers."""

from copy import deepcopy
from typing import Any

MARKER = "[별도 음성 제작 v1]"
COMMON = """[별도 음성 제작 v1]
기존 계획의 수정에서는 previous_answer.audio_plan 및 전달된 실제 음성 설정을 유지한다.
사용자가 음성 방식 변경을 명시하지 않았다면 enabled/delivery_mode, 화자 ID·이름·역할,
화자별 voice(음색·언어·속도), cues의 대사 원문·시작/종료·감정, 음악 설정을 바꾸지 않는다.
자동으로 결정된 기존 목소리도 다시 정하지 않는다. 영상 동작·구도 보완은 음성 방식 변경이 아니다.
기존 audio=true와 영상 내 발화 지시를 audio=false/별도 TTS로 이관하지 않는다.
반대로 별도 음성 제작인 기존 계획을 영상 내 음성으로 전환하지 않는다.
새 계획에서만 이번 실행의 video_voice_directions와 사용자 선택으로 방식을 결정한다.
영상 내 음성이면 영상 모델 음성 연출 계약을 따르고, 별도 음성 방식에만 아래 규칙을 적용한다.
별도 음성 방식: audio_plan.enabled=true, speakers, cues를 출력한다. speakers는 원본
캐릭터의 안정적인 id/name/role(character/narrator)을 유지하고 내레이터는 별도 ID로 둔다.
cues에는 id, speaker_id, text(원문), start/end(전체 영상 시작부터의 초), emotion을 적는다.
대사와 내레이션을 누락·요약하지 않고 충분한 발화 시간을 배분한다. 같은 화자의 발화를
겹치지 않으며 발화가 없으면 빈 배열이다. 별도 음성 방식일 때만 영상은 audio=false로
요청하고 prompt에서 음성 생성 지시를 제외한다. 목소리 모델·음색은 사용자 설정을 따른다.
음악은 edit_notes에 분위기·시작·끝 의도를 제안하되 실제 음원 ID를 만들지 않는다.
사용자가 선택한 음원·음량·반복·페이드·대사 중 음량 감소 설정을 유지한다.
별도 음성은 생성 후 길이를 검토·확정하며 할당 시간을 넘으면 대사/시간표를 검토해야 한다.
자동으로 자르거나 압축하지 않는다. 별도 합성에서는 영상·음성 확정 후 오디오 워커가
컷 연결·음성·음악 합성을 수행하고 원래 영상 소리를 제거한다. 영상 내 음성 방식에는
이 소리 제거 규칙을 적용하지 않는다. 자막·디졸브·립싱크 자동 보정은 지원하지 않는다.
합성 결과는 사용자가 검토·확정하며 동일 음색 설정도 완전히 같은 연기를 보장하지 않는다.
"""
STYLES = {
    "animation_2d": "2D 캐릭터의 말투·감정 대비를 유지하고 대사 사이 반응 포즈 시간을 둔다.",
    "animation_3d": "3D 캐릭터의 호흡·몸짓과 발화 시간을 맞추고 동작 안착 시간을 확보한다.",
    "live_action": "실사는 자연스러운 호흡·휴지를 배분하고 화면 발화와 내레이션을 구분한다.",
}


def upgrade_definition(definition: dict[str, Any], *, video_voice: bool = False) -> dict[str, Any]:
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
    if video_voice:
        speaker = result['output_schema']['properties']['audio_plan']['properties'][
            'speakers']['items']
        speaker['properties']['voice'] = obj({
            'instructions': {**string(1000), 'minLength': 1},
            'language': {**string(80), 'minLength': 1},
            'speed': {'type': 'number', 'minimum': 0.75, 'maximum': 1.25},
        })
        speaker['required'].append('voice')
    return result
