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

    # Instructions have their own character limit; Korean text needs multiple UTF-8 bytes.
    settings_payload = draft.model_dump(exclude={"instructions"})
    settings_payload["video_prompt_modules"].pop("common_instructions", None)
    settings_payload["video_prompt_modules"].pop("style_instructions", None)
    settings_json = json.dumps(settings_payload, ensure_ascii=False)
    if len(settings_json.encode()) > 65536:
        issue("payload_size", "definition", "지침을 제외한 설정은 64 KiB 이하여야 합니다.")
    modules = draft.video_prompt_modules
    if modules.enabled and modules.editor_managed:
        path = "video_prompt_modules"
        if not draft.instructions.strip():
            issue("prompt_common_missing", path, "관리자가 공통 지침을 먼저 입력해야 합니다.")
        if modules.mode == "manual":
            if (not modules.profile_id
                    or not modules.style_instructions.get(modules.profile_id, "").strip()):
                issue("prompt_style_missing", path,
                      "적용할 영상 스타일을 선택하고 지침을 입력하세요.")
        else:
            fields = [modules.user_style_field, modules.confirmed_style_field,
                      modules.reference_style_field, modules.metadata_style_field]
            props = draft.input_schema.get("properties", {})
            def style_field(field: str) -> bool:
                node = props.get(field) if isinstance(props, dict) else None
                if not isinstance(node, dict):
                    return False
                if node.get("type") == "string":
                    return True
                children = node.get("properties")
                media = children.get("media_type") if isinstance(children, dict) else None
                return (node.get("type") == "object" and isinstance(media, dict)
                        and media.get("type") == "string")

            if not any(fields) or any(field and not style_field(field) for field in fields):
                issue("prompt_style_field", path, "자동 선택에 사용할 실행 입력 항목을 확인하세요.")
            if not modules.selection_required and (len(modules.style_instructions) != 3
                    or any(not body.strip() for body in modules.style_instructions.values())):
                issue("prompt_style_missing", path,
                      "자동 선택은 세 가지 스타일의 지침이 모두 필요합니다.")
    link = draft.after_tasks.image_review
    if link:
        target = catalog.get(link.agent_ref)
        if (not target or target.get("kind") != "agent"
                or target.get("agent_id") == agent_id):
            issue("review_agent", "after_tasks.image_review",
                  "등록된 이미지 검수 에이전트를 선택하세요.")

    if draft.model_profile != "default":
        issue("model_profile", "model_profile", "등록된 서버 모델 프로필을 선택하세요.")

    def validate_schema(node: Any, path: str, depth: int, counter: list[int]) -> None:
        if depth > 5:
            issue("schema_depth", path, "중첩 깊이는 5 이하여야 합니다.")
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
        form_keys = (
            {"x-widget", "default", "x-previous-answer", "x-answer-agent", "x-video-model"}
            if path.startswith("input_schema") else set()
        )
        if path.startswith("input_schema.properties.") and path.count(".") == 2:
            form_keys.update({"x-required-when", "x-visible-when"})
        if "x-visible-when" in node:
            from asa.registry.input_requirements import valid_condition
            field = path.rsplit(".", 1)[-1]
            rule = node["x-visible-when"]
            if (not path.startswith("input_schema.properties.") or path.count(".") != 2
                    or not valid_condition(field, rule, draft.input_schema)
                    or rule != node.get("x-required-when")
                    or "x-visible-when" in draft.input_schema.get("properties", {}).get(
                        rule.get("field") if isinstance(rule, dict) else "", {})):
                issue("input_visible_when", path + ".x-visible-when",
                      "표시 조건은 조건부 필수와 같아야 하며 항상 표시되는 항목을 참조해야 합니다.")
        if "x-required-when" in node:
            from asa.registry.input_requirements import valid_condition
            field = path.rsplit(".", 1)[-1]
            if (not path.startswith("input_schema.properties.") or path.count(".") != 2
                    or not valid_condition(field, node["x-required-when"], draft.input_schema)):
                issue("input_required_when", path + ".x-required-when",
                      "조건 항목과 선택값을 확인하세요. 항상 필수와 함께 설정할 수 없습니다.")
        for key in node.keys() - (keywords[kind] | {"type", "description"} | form_keys):
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
        if "x-video-model" in node and (
            type(node["x-video-model"]) is not bool or kind != "string"
        ):
            issue("input_video_model", path, "영상 모델 선택은 문자열 입력에만 설정합니다.")
        if "x-previous-answer" in node and (
            type(node["x-previous-answer"]) is not bool or kind != "string" or "enum" in node
        ):
            issue("input_previous_answer", path,
                  "이전 답변 가져오기는 글 입력에서만 켜거나 끌 수 있습니다.")
        if "x-answer-agent" in node:
            source = node["x-answer-agent"]
            known = {str(t.get("agent_id")) for t in catalog.values() if t.get("kind") == "agent"}
            if (not isinstance(source, str) or source not in known
                    or node.get("x-previous-answer") is not True or kind != "string"
                    or "enum" in node):
                issue("input_answer_agent", path, "답변을 가져올 등록된 에이전트를 선택하세요.")
        widget = node.get("x-widget")
        if widget is not None:
            allowed = {"text": "string", "textarea": "string", "radio": "string",
                       "select": "string", "slider": "integer", "number": "number"}
            if not isinstance(widget, str) or widget not in allowed or (kind != allowed.get(widget)
                                        and not (widget == "number" and kind == "integer")):
                issue("input_widget", path, "입력 방식과 자료형이 맞지 않습니다.")
            if widget in ("radio", "select"):
                options = node.get("enum", [])
                if (not isinstance(options, list) or not options
                        or any(not isinstance(v, str) or not v.strip() for v in options)
                        or len({str(v) for v in options}) != len(options)):
                    issue("input_options", path, "중복되거나 빈 선택지는 사용할 수 없습니다.")
            if widget == "slider" and not (
                type(node.get("minimum")) is int and type(node.get("maximum")) is int
                and node["minimum"] < node["maximum"]
            ):
                issue("input_range", path, "슬라이더의 정수 최솟값과 최댓값을 설정하세요.")
        if "default" in node:
            value = node["default"]
            valid = (
                isinstance(value, str) and kind == "string"
                and type(node.get("minLength", 0)) is int
                and type(node.get("maxLength", 65536)) is int
                and node.get("minLength", 0) <= len(value) <= node.get("maxLength", 65536)
            ) or (type(value) is bool and kind == "boolean")
            if kind in ("integer", "number"):
                valid = (safe_number(value) and (kind != "integer" or type(value) is int)
                         and safe_number(node.get("minimum", -MAX_NUMBER))
                         and safe_number(node.get("maximum", MAX_NUMBER))
                         and node.get("minimum", -MAX_NUMBER) <= value
                         <= node.get("maximum", MAX_NUMBER))
            if not valid or ("enum" in node and (
                not isinstance(node["enum"], list) or value not in node["enum"]
            )):
                issue("input_default", path, "기본값이 선택지 또는 입력 범위에 맞지 않습니다.")
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
