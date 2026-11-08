"""Deterministic display metadata; never modifies saved inputs or generated answers."""

import re
from typing import Any
from uuid import UUID

import psycopg

from asa.registry.answer_sources import _text_title, _title


def clean(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    result = re.sub(r"\s+", " ", _title(value)).strip()[:120]
    return "" if result.lower() in {"untitled", "none", "null", "제목없음"} else result


def explicit_title(value: Any) -> str:
    if isinstance(value, str):
        return clean(_text_title(value[:16000]))
    if isinstance(value, dict):
        for key in ("title", "제목", "work_title", "project_title"):
            if title := clean(value.get(key)):
                return title
        for key in ("result", "script", "content", "body"):
            if isinstance(value.get(key), str) and (title := explicit_title(value[key])):
                return title
    return ""


def describe_work(
    answer: Any,
    title: str,
    inputs: Any,
    schema: dict[str, Any],
    agent_name: str,
    custom: str | None = None,
    linked: str | None = None,
    output_schema: dict[str, Any] | None = None,
) -> dict[str, str]:
    values = inputs if isinstance(inputs, dict) else {"prompt": inputs}
    props = schema.get("properties", {})
    context = []
    for key, prop in props.items():
        value = values.get(key)
        label = prop.get("description", "")
        if isinstance(value, str) and (
            label in {"이야기 길이", "영상 길이", "영상 스타일"} or key == "video_style"
        ):
            context.append(
                {
                    "animation_2d": "2D 애니메이션",
                    "animation_3d": "3D 애니메이션",
                    "live_action": "실사",
                }.get(value, clean(value))
            )
    result = {"context": " · ".join(context[:2])}
    answer_title = explicit_title(answer) or clean(title)
    if not answer_title and isinstance(answer, dict):
        for key, prop in (output_schema or {}).get("properties", {}).items():
            if prop.get("description") in {"제목", "작품 제목", "작업 이름", "결과 제목"}:
                answer_title = clean(answer.get(key))
                if answer_title:
                    break
    for candidate, source in (
        (custom.strip() if custom else "", "custom"),
        (answer_title, "answer"),
        (linked.strip() if linked else "", "linked"),
    ):
        if candidate:
            return {**result, "display_title": candidate, "title_source": source}
    for key, value in values.items():
        if props.get(key, {}).get("x-previous-answer") or key in {"script", "scenes"}:
            if candidate := explicit_title(value):
                return {**result, "display_title": candidate, "title_source": "linked"}
    input_keys = ["title", "name", "subject", "custom_subject", "topic", "goal", "prompt"]
    input_keys += [
        key
        for key, prop in props.items()
        if prop.get("description")
        in {"작업 이름", "제목", "주제", "요청 내용", "분석 목적", "이야기 소재 직접 입력"}
    ]
    for key in input_keys:
        value = values.get(key)
        if props.get(key, {}).get("enum") or not isinstance(value, str):
            continue
        if value.lstrip().startswith(("http:", "https:", "data:")):
            continue
        if candidate := explicit_title(value) or clean(value):
            return {**result, "display_title": candidate, "title_source": "input"}
    for value in values.values():
        for entry in value if isinstance(value, list) else []:
            if isinstance(entry, dict) and (candidate := clean(entry.get("filename"))):
                return {**result, "display_title": candidate, "title_source": "input"}
    return {
        **result,
        "display_title": clean(agent_name) or "제목 없는 작업",
        "title_source": "agent",
    }


def attach_titles(
    conn: psycopg.Connection[Any],
    workspace_id: UUID,
    user_id: str | None,
    items: list[dict[str, Any]],
) -> None:
    if not items:
        return
    rows = conn.execute(
        "SELECT r.id::text,r.input,v.definition->'input_schema' AS schema,"
        "v.definition->'output_schema' AS output_schema,"
        "v.definition->>'name' AS agent_name,a.answer,a.title,n.name AS custom_name,"
        "coalesce(n.revision,0) AS name_revision,"
        "pn.name AS parent_name,pa.answer AS parent_answer,pa.title AS parent_title "
        "FROM customer_requests r JOIN registry_versions v USING(workspace_id,agent_id,version) "
        "LEFT JOIN user_work_names n ON n.workspace_id=r.workspace_id AND n.request_id=r.id "
        "AND n.user_id=%s "
        "LEFT JOIN LATERAL (SELECT answer,title FROM script_versions "
        "WHERE workspace_id=r.workspace_id "
        "AND request_id=r.id ORDER BY version DESC LIMIT 1) a ON true "
        "LEFT JOIN user_work_names pn ON pn.workspace_id=r.workspace_id "
        "AND pn.request_id=r.source_id AND pn.user_id=%s "
        "LEFT JOIN LATERAL (SELECT answer,title FROM script_versions "
        "WHERE workspace_id=r.workspace_id "
        "AND request_id=r.source_id ORDER BY version DESC LIMIT 1) pa ON true "
        "WHERE r.workspace_id=%s AND r.id=ANY(%s::uuid[])",
        (user_id, user_id, workspace_id, [item["id"] for item in items]),
    ).fetchall()
    by_id = {row["id"]: row for row in rows}
    for item in items:
        row = by_id[item["id"]]
        linked = (
            row["parent_name"]
            or explicit_title(row["parent_answer"])
            or clean(row["parent_title"])
        )
        item.update(
            describe_work(
                row["answer"],
                row["title"],
                row["input"],
                row["schema"],
                row["agent_name"],
                row["custom_name"],
                linked,
                row["output_schema"],
            )
        )
        item.update(custom_name=row["custom_name"], name_revision=row["name_revision"])
