import json
import math
import re
from typing import Any

from asa.registry.schemas import AgentDraft, ValidationIssue

MAX_NUMBER = 9007199254740991


def safe_number(value: Any) -> bool:
    return (
        type(value) in (int, float)
        and abs(value) <= MAX_NUMBER
        and (type(value) is int or math.isfinite(value))
    )


def normalize_schema(node: dict[str, Any]) -> dict[str, Any]:
    result = dict(node)
    kind = result["type"]
    if kind == "object":
        result["additionalProperties"] = False
        result["properties"] = {
            k: normalize_schema(v) for k, v in result.get("properties", {}).items()
        }
    elif kind == "array":
        result.setdefault("maxItems", 100)
        result["items"] = normalize_schema(result["items"])
    elif kind == "string":
        result.setdefault("maxLength", 65536)
    elif kind in ("number", "integer"):
        result.setdefault("minimum", -MAX_NUMBER)
        result.setdefault("maximum", MAX_NUMBER)
    return result


def validate_definition(
    draft: AgentDraft,
    catalog: dict[str, dict[str, Any]],
    agent_id: str | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    def issue(code: str, path: str, message: str) -> None:
        issues.append(ValidationIssue(code=code, field_path=path, message=message))

    if len(json.dumps(draft.model_dump(), ensure_ascii=False).encode()) > 65536:
        issue("payload_size", "definition", "정의는 64 KiB 이하여야 합니다.")
    if draft.model_profile != "default":
        issue("model_profile", "model_profile", "등록된 서버 모델 프로필을 선택하세요.")

    def validate_schema(node: Any, path: str, depth: int, counter: list[int]) -> None:
        if depth > 4:
            issue("schema_depth", path, "중첩 깊이는 4 이하여야 합니다.")
            return
        if not isinstance(node, dict):
            issue("schema_type", path, "스키마 객체가 필요합니다.")
            return
        kind = node.get("type")
        keywords = {
            "object": {"properties", "required", "additionalProperties"},
            "array": {"items", "minItems", "maxItems"},
            "string": {"minLength", "maxLength", "enum"},
            "number": {"minimum", "maximum", "enum"},
            "integer": {"minimum", "maximum", "enum"},
            "boolean": {"enum"},
        }
        if not isinstance(kind, str) or kind not in keywords:
            issue("schema_type", path, "지원되는 필드 유형을 선택하세요.")
            return
        for key in node.keys() - (keywords[kind] | {"type", "description"}):
            issue("schema_keyword", path + "." + key, "지원하지 않는 스키마 속성입니다.")
        if "description" in node and (
            not isinstance(node["description"], str) or len(node["description"]) > 400
        ):
            issue("schema_description", path, "설명은 400자 이하의 문자열이어야 합니다.")
        for lower, upper, ceiling in [
            ("minLength", "maxLength", 65536),
            ("minItems", "maxItems", 100),
        ]:
            for key in (lower, upper):
                if key in node and (type(node[key]) is not int or not 0 <= node[key] <= ceiling):
                    issue("schema_bound", path + "." + key, "허용 범위를 벗어난 길이입니다.")
            if type(node.get(lower)) is int and type(node.get(upper)) is int:
                if node[lower] > node[upper]:
                    issue("schema_bound", path, "최솟값은 최댓값 이하여야 합니다.")
        for key in ("minimum", "maximum"):
            if key in node and not safe_number(node[key]):
                issue("schema_bound", path, "유한한 숫자가 필요합니다.")
        if all(type(node.get(k)) in (int, float) for k in ("minimum", "maximum")):
            if node["minimum"] > node["maximum"]:
                issue("schema_bound", path, "최솟값은 최댓값 이하여야 합니다.")
        if "enum" in node:
            values = node["enum"]
            types = {
                "string": (str,),
                "number": (int, float),
                "integer": (int,),
                "boolean": (bool,),
            }
            if (
                not isinstance(values, list)
                or not 1 <= len(values) <= 100
                or any(type(v) not in types.get(kind, ()) for v in values)
                or (kind in ("number", "integer") and any(not safe_number(v) for v in values))
            ):
                issue("schema_enum", path, "필드 유형과 일치하는 선택값이 필요합니다.")
        if kind == "object":
            props = node.get("properties", {})
            required = node.get("required", [])
            if not isinstance(props, dict):
                issue("schema_properties", path, "필드 목록이 올바르지 않습니다.")
                return
            if (
                not isinstance(required, list)
                or any(not isinstance(k, str) for k in required)
                or any(k not in props for k in required)
                or len(set(required)) != len(required)
            ):
                issue("schema_required", path, "필수 필드는 실제 필드 목록에 있어야 합니다.")
            if node.get("additionalProperties", False) is not False:
                issue("schema_keyword", path, "추가 필드는 허용하지 않습니다.")
            counter[0] += len(props)
            if counter[0] > 50:
                issue("schema_fields", path, "전체 필드는 50개 이하여야 합니다.")
                return
            for name, child in props.items():
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
                    issue(
                        "schema_name", path, "필드 이름은 영문자로 시작하는 영문·숫자·밑줄입니다."
                    )
                validate_schema(child, f"{path}.properties.{name}", depth + 1, counter)
        if kind == "array":
            validate_schema(node.get("items"), path + ".items", depth + 1, counter)

    for label, schema in [
        ("input_schema", draft.input_schema),
        ("output_schema", draft.output_schema),
    ]:
        allowed_roots = {"object", "string"} if label == "output_schema" else {"object"}
        if schema.get("type") not in allowed_roots:
            issue(
                "schema_root",
                label,
                "입력은 항목 묶음, 결과는 자유 텍스트 또는 항목 묶음이어야 합니다.",
            )
        validate_schema(schema, label, 1, [0])
    if len(set(draft.tools)) != len(draft.tools):
        issue("duplicate_tool", "tools", "같은 도구를 중복 선택할 수 없습니다.")

    def visit(tool_id: str, ancestors: set[str], path: str) -> None:
        tool = catalog.get(tool_id)
        if not tool or not tool.get("available"):
            issue("tool_unavailable", path, "등록 가능하고 권한이 있는 도구만 선택하세요.")
            return
        target = tool.get("agent_id")
        if target and (target == agent_id or target in ancestors):
            issue("agent_cycle", path, "자기 자신 또는 순환하는 에이전트를 호출할 수 없습니다.")
            return
        if len(ancestors) >= 3:
            issue("agent_depth", path, "에이전트 호출 깊이 상한을 초과합니다.")
            return
        for child in tool.get("dependencies", []):
            visit(child, ancestors | ({target} if target else set()), path)

    for index, tool in enumerate(draft.tools):
        visit(tool, set(), f"tools.{index}")
    return issues
