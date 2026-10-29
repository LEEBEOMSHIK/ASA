import pytest

from asa.registry.schemas import AgentDraft
from asa.registry.service import validate_definition
from asa.tools.catalog import inspect_text


def draft(**changes):
    return AgentDraft.model_validate(
        {
            "name": "대본 작가",
            "description": "채널용 대본",
            "instructions": "짧은 대본을 작성하세요.",
            "model_profile": "default",
            "input_schema": {
                "type": "object",
                "properties": {"topic": {"type": "string"}},
                "required": ["topic"],
            },
            "output_schema": {
                "type": "object",
                "properties": {"script": {"type": "string"}},
                "required": ["script"],
            },
            **changes,
        }
    )


def test_restricted_schema_and_unknown_tool_are_rejected():
    issues = validate_definition(
        draft(
            input_schema={"type": "object", "$ref": "https://invalid/schema"},
            tools=["external.http:1"],
        ),
        {},
    )
    assert {issue.code for issue in issues} >= {"schema_keyword", "tool_unavailable"}


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "properties": {}, "required": ["missing"]},
        {
            "type": "object",
            "properties": {"x": {"type": "array", "items": {"type": "string"}, "maxItems": 101}},
        },
        {"type": "object", "properties": {"x": {"type": "string", "pattern": ".*"}}},
        {"type": "object", "properties": {"x": {"type": "number", "minimum": 4, "maximum": 2}}},
    ],
)
def test_invalid_schema_cannot_be_published(schema):
    assert validate_definition(draft(input_schema=schema), {})


def test_schema_depth_is_bounded():
    nested = {"type": "string"}
    for i in range(5):
        nested = {"type": "object", "properties": {f"field{i}": nested}}
    assert any(
        i.code == "schema_depth" for i in validate_definition(draft(input_schema=nested), {})
    )


def test_valid_definition_and_deterministic_text_tool():
    assert validate_definition(draft(), {}) == []
    assert inspect_text("고양이 우주", 4) == {"characters": 6, "limit": 4, "exceeded": True}


def test_free_text_output_is_allowed_but_input_still_requires_fields():
    assert validate_definition(draft(output_schema={"type": "string"}), {}) == []
    issues = validate_definition(draft(input_schema={"type": "string"}), {})
    assert any(i.code == "schema_root" and i.field_path == "input_schema" for i in issues)


def test_model_profile_must_be_server_defined():
    assert any(
        i.code == "model_profile"
        for i in validate_definition(draft(model_profile="https://user-provided-endpoint"), {})
    )


def test_oversized_numeric_bound_returns_issue_not_server_error():
    schema = {"type": "object", "properties": {"x": {"type": "number", "minimum": 10**1000}}}
    assert any(
        i.code == "schema_bound" for i in validate_definition(draft(input_schema=schema), {})
    )
