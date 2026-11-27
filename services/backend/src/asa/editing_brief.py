"""Remove empty editing-form sections from model input, never from saved originals."""
import copy
import re
from typing import Any

HEADER = re.compile(
    r"^\s*(편집 방향|순서·사용 구간|목표 길이|장면 연결·전환|"
    r"목소리·배경음악|자막 요청)\s*[:：](.*)$"
)


def written_brief(text: str) -> str:
    output: list[str] = []
    section: list[str] = []
    has_content = False
    for line in text.splitlines():
        match = HEADER.match(line)
        if match:
            if has_content:
                output.extend(section)
            section = [line]
            has_content = bool(match[2].strip())
        elif section:
            section.append(line)
            has_content = has_content or bool(line.strip())
        else:
            output.append(line)
    if has_content:
        output.extend(section)
    return "\n".join(output).strip()


def model_contract(contract: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(contract)
    for key, field in result.get("input_schema", {}).get("properties", {}).items():
        if not isinstance(field, dict) or not field.get("x-editing-brief"):
            continue
        field.pop("default", None)
        value = result.get("original_request", {}).get(key)
        if isinstance(value, str):
            cleaned = written_brief(value)
            if cleaned:
                result["original_request"][key] = cleaned
            else:
                result["original_request"].pop(key, None)
    return result
