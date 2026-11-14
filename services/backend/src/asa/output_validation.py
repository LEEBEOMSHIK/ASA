"""Safe, bounded diagnostics: never include model text or provider exceptions."""
from copy import deepcopy
from typing import Any


def output_issues(value: Any, schema: dict[str, Any]) -> list[str]:
    issues: list[str] = []

    def visit(node: Any, spec: dict[str, Any], path: str) -> None:
        if len(issues) >= 40:
            return
        kind = spec.get('type')
        if kind == 'object' and isinstance(node, dict):
            properties = spec.get('properties', {})
            for key in spec.get('required', []):
                if key not in node:
                    issues.append(f'{path}.{key}: 필수 항목이 누락됐습니다.')
            for key, child in properties.items():
                if key in node:
                    visit(node[key], child, f'{path}.{key}')
        elif kind == 'array' and isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, spec.get('items', {}), f'{path}[{index + 1}]')
        elif kind == 'string' and isinstance(node, str):
            maximum = spec.get('maxLength')
            if maximum is not None and len(node) > maximum:
                issues.append(f'{path}: {maximum}자 제한을 초과했습니다(현재 {len(node)}자).')

    visit(value, schema, '답변')
    return issues[:40]


def strict_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Require all declared output properties on the wire; preserve saved contracts."""
    result = deepcopy(schema)

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if node.get('type') == 'object':
                node['additionalProperties'] = False
                node['required'] = list(node.get('properties', {}))
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(result)
    return result
