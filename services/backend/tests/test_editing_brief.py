import copy
import json

from asa.editing_brief import model_contract, written_brief


def test_empty_sections_and_multiline_user_content():
    assert written_brief("편집 방향: \n목표 길이: \n자막 요청: ") == ""
    assert written_brief(
        "편집 방향: 차분하게\n목표 길이: \n자막 요청:\n안녕하세요\n두 번째 줄"
    ) == (
        "편집 방향: 차분하게\n자막 요청:\n안녕하세요\n두 번째 줄"
    )
    assert written_brief("순서·사용 구간: S02 → S01\n목표 길이： 15초\n자막 요청: 없음") == (
        "순서·사용 구간: S02 → S01\n목표 길이： 15초\n자막 요청: 없음"
    )
    assert written_brief("자유롭게 쓴 요청\n목표 길이: ") == "자유롭게 쓴 요청"


def test_model_only_cleanup_preserves_original_and_other_fields():
    original = {"input_schema": {"properties": {
        "brief": {"x-editing-brief": True, "default": "목표 길이: "},
        "other": {"default": "목표 길이: "},
    }}, "original_request": {"brief": "목표 길이: ", "other": "목표 길이: "}}
    before = copy.deepcopy(original)
    result = model_contract(original)
    assert result["original_request"] == {"other": "목표 길이: "}
    assert "default" not in result["input_schema"]["properties"]["brief"]
    assert original == before


def test_provider_messages_exclude_blank_template(monkeypatch):
    from asa.config import Settings
    from asa.providers import make_agent_generator

    calls = []

    class Model:
        def with_structured_output(self, schema):
            return self

        def invoke(self, messages, **kwargs):
            calls.append(messages)
            return {"value": "계획"}

    monkeypatch.setattr("asa.providers.init_chat_model", lambda *a, **k: Model())
    generate = make_agent_generator(Settings(_env_file=None, ai_model="test", ai_api_key="fake"))
    contract = {"agent_instructions": "편집 계획", "output_schema": {"type": "string"},
                "input_schema": {"properties": {"brief": {
                    "x-editing-brief": True, "default": "목표 길이: "}}},
                "original_request": {"editing_mode": "씬 이미지로 영상 만들기",
                                     "brief": "편집 방향: 차분하게\n목표 길이: \n자막 요청: "}}
    generate(json.dumps(contract))
    sent = json.loads(calls[0][1][1])
    assert sent["original_request"]["editing_mode"] == "씬 이미지로 영상 만들기"
    assert sent["original_request"]["brief"] == "편집 방향: 차분하게"
    assert "default" not in sent["input_schema"]["properties"]["brief"]
