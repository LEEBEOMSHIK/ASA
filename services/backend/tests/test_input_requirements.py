from copy import deepcopy

import pytest

from asa.registry.automations import accepts
from asa.registry.history import valid_input
from asa.registry.schemas import AgentDraft
from asa.registry.service import normalize_schema, validate_definition


def schema():
    return {
        "type": "object", "required": ["mode"],
        "properties": {
            "mode": {"type": "string", "enum": ["draft", "image"], "default": "draft"},
            "reference": {"type": "string",
                          "x-required-when": {"field": "mode", "equals": "image"}},
        },
    }


def definition(inputs):
    return AgentDraft(name="조건 테스트", instructions="입력에 답하세요.",
                      input_schema=inputs, output_schema={"type": "string"})


def test_condition_schema_can_be_saved_and_normalized():
    value = schema()
    assert validate_definition(definition(value), {}) == []
    normalized = normalize_schema(value)
    assert normalized["properties"]["reference"]["x-required-when"] == {
        "field": "mode", "equals": "image"}


@pytest.mark.parametrize("check", [valid_input, accepts])
@pytest.mark.parametrize(("value", "expected"), [
    ({"mode": "draft"}, True),
    ({"mode": "draft", "reference": ""}, True),
    ({"mode": "image"}, False),
    ({"mode": "image", "reference": "  "}, False),
    ({"mode": "image", "reference": "original"}, True),
    ({}, False),
])
def test_runtime_and_request_use_the_same_condition(check, value, expected):
    assert check(value, normalize_schema(schema())) is expected


@pytest.mark.parametrize("condition", [
    None, {}, {"field": "missing", "equals": "image"},
    {"field": "reference", "equals": "image"},
    {"field": "mode", "equals": "removed"},
    {"field": "mode", "equals": ["image"]},
    {"field": "mode", "equals": "image", "operator": "eval"},
])
def test_invalid_conditions_are_rejected(condition):
    value = schema()
    value["properties"]["reference"]["x-required-when"] = condition
    assert any(i.code == "input_required_when"
               for i in validate_definition(definition(value), {}))


def test_conflicting_required_and_nested_rules_are_rejected():
    value = schema()
    value["required"].append("reference")
    assert validate_definition(definition(value), {})
    nested = {"type": "object", "properties": {"nested": schema()}}
    assert validate_definition(definition(nested), {})
    draft = definition({"type": "object", "properties": {}})
    draft.output_schema = schema()
    assert validate_definition(draft, {})
    malformed = schema()
    malformed["required"] = None
    assert validate_definition(definition(malformed), {})


def test_boolean_false_and_empty_collections():
    value = schema()
    value["properties"]["mode"] = {"type": "boolean"}
    reference = value["properties"]["reference"]
    reference.update(type="array", items={"type": "string"})
    reference["x-required-when"]["equals"] = False
    assert not validate_definition(definition(value), {})
    for check in (valid_input, accepts):
        assert check({"mode": True}, value)
        assert not check({"mode": False}, value)
        assert not check({"mode": False, "reference": []}, value)
        assert check({"mode": False, "reference": ["image"]}, value)
    # bool is an int subclass in Python; never treat 0 as False in the condition.
    invalid = deepcopy(value)
    invalid["properties"]["reference"]["x-required-when"]["equals"] = 0
    assert validate_definition(definition(invalid), {})


def test_automation_checks_literal_conditions_and_evaluates_upstream_values():
    from asa.registry.automations import Automation, check_flow, preview_flow
    from asa.registry.graph_automation import Binding

    tools = [{"id": "agent:test:1", "available": True, "input_schema": schema(),
              "output_schema": {"type": "string"}}]
    draft = Automation.model_validate({
        "name": "조건 자동화", "steps": [{"id": "step1", "label": "작업", "tool_id": "agent:test:1",
            "bindings": {"mode": {"source": "literal", "value": "image"}}}],
    })
    assert check_flow(draft, tools)
    draft.steps[0].bindings["reference"] = Binding(source="literal", value="  ")
    assert check_flow(draft, tools)
    del draft.steps[0].bindings["reference"]
    draft.steps[0].bindings["mode"].value = "draft"
    assert not check_flow(draft, tools)
    draft.steps[0].bindings["mode"].source = "input"
    assert not check_flow(draft, tools)
    assert preview_flow(draft, tools, "image", {"step1": "ok"})[0]["kind"] == "invalid_input"
    assert preview_flow(draft, tools, "draft", {"step1": "ok"})[0]["output"] == "ok"

    graph = Automation.model_validate({
        "name": "조건 그래프", "graph": {
            "nodes": [{"id": "start", "kind": "start", "label": "시작"},
                      {"id": "step1", "kind": "tool", "label": "작업",
                       "tool_id": "agent:test:1", "bindings": {"mode": {"source": "input"}}},
                      {"id": "end", "kind": "end", "label": "결과"}],
            "edges": [{"id": "e1", "source": "start", "target": "step1", "port": "next"},
                      {"id": "e2", "source": "step1", "target": "end", "port": "next"}],
        },
    })
    assert not check_flow(graph, tools)
    rows = preview_flow(graph, tools, "image", {"step1": "ok"})
    assert rows[-1]["kind"] == "invalid_input"
    assert preview_flow(graph, tools, "draft", {"step1": "ok"})[-1]["output"] == "ok"
    graph.graph.nodes[1].bindings = {
        "mode": Binding(source="literal", value="image"),
        "reference": Binding(source="literal", value="  "),
    }
    assert check_flow(graph, tools)
