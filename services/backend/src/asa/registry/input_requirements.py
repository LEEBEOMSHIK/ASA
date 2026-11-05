"""Conditional requirements shared by request and automation validation."""
from typing import Any


def same_value(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return bool(left == right)


def conditional_fields(schema: dict[str, Any], values: dict[str, Any]) -> set[str]:
    return {
        key for key, node in schema.get("properties", {}).items()
        if isinstance(rule := node.get("x-required-when"), dict)
        and rule.get("field") in values
        and same_value(values[rule["field"]], rule.get("equals"))
    }


def required_fields(schema: dict[str, Any], values: dict[str, Any]) -> set[str]:
    return set(schema.get("required", [])) | conditional_fields(schema, values)


def requirements_met(schema: dict[str, Any], values: dict[str, Any]) -> bool:
    if not required_fields(schema, values) <= values.keys():
        return False
    return all(has_input_value(values[key]) for key in conditional_fields(schema, values))


def has_input_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def valid_condition(field: str, rule: Any, schema: dict[str, Any]) -> bool:
    if not isinstance(rule, dict) or rule.keys() != {"field", "equals"}:
        return False
    source = rule["field"]
    required = schema.get("required", [])
    if (not isinstance(source, str) or source == field
            or not isinstance(required, list) or field in required):
        return False
    node = schema.get("properties", {}).get(source)
    if not isinstance(node, dict):
        return False
    choices = node.get("enum", [True, False] if node.get("type") == "boolean" else [])
    return (
        node.get("type") in {"string", "number", "integer", "boolean"}
        and isinstance(choices, list) and len(choices) > 0
        and type(rule["equals"]) in (str, int, float, bool)
        and rule["equals"] != ""
        and any(same_value(rule["equals"], choice) for choice in choices)
    )
