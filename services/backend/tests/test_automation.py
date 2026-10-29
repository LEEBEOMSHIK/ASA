from asa.registry.automations import Automation, accepts, check_flow, preview_flow
from asa.tools.catalog import builtin_tools


def flow(source="input"):
    return Automation(name="길이 검사", steps=[{
        "id": "check", "tool_id": "asa.text.inspect:1", "label": "대본 검사",
        "bindings": {"text": {"source": source},
                     "limit": {"source": "literal", "value": 3}},
    }])


def test_preview_real_local_tool_and_no_ai():
    result = preview_flow(flow(), builtin_tools(), "안녕하세요", {})
    assert result[0]["output"] == {"characters": 5, "limit": 3, "exceeded": True}
    assert result[0]["kind"] == "local_tool"


def test_missing_future_and_wrong_typed_bindings():
    assert check_flow(flow("later"), builtin_tools())
    draft = flow()
    draft.steps[0].bindings["limit"].value = "wrong"
    assert check_flow(draft, builtin_tools())
    draft.steps[0].bindings.pop("text")
    assert any("text" in i.field_path for i in check_flow(draft, builtin_tools()))


def test_integer_tool_input_rejects_float_before_dispatch():
    draft = flow()
    draft.steps[0].bindings["limit"].value = 3.0
    assert check_flow(draft, builtin_tools())


def test_declared_value_constraints_are_checked():
    assert not accepts("", {"type": "string", "minLength": 1})
    assert not accepts("bad", {"type": "string", "enum": ["good"]})
    assert not accepts([], {"type": "array", "minItems": 1, "items": {"type": "string"}})


def test_sample_agent_output_is_explicit_and_validated():
    catalog = builtin_tools() + [{"id": "agent:test:1", "available": True, "kind": "agent",
        "input_schema": {"type": "string"}, "output_schema": {"type": "string"}}]
    draft = flow("writer")
    draft.steps.insert(0, type(draft.steps[0])(
        id="writer", tool_id="agent:test:1", label="작가",
        bindings={"$": {"source": "input"}}))
    assert not check_flow(draft, catalog)
    waiting = preview_flow(draft, catalog, "고양이", {})
    assert waiting[0]["kind"] == "needs_sample"
    result = preview_flow(draft, catalog, "고양이", {"writer": "샘플 대본"})
    assert result[0]["kind"] == "sample"
    assert result[1]["input"]["text"] == "샘플 대본"
