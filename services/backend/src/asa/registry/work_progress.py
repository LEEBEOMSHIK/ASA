"""Read-model for human follow-up work, separate from AI execution status.

Adapters map domain records to this contract; no second mutable job status store.
"""

from collections import Counter
from typing import Any
from uuid import UUID

import psycopg

STATES = ("pending", "queued", "running", "review", "approved", "excluded", "failed", "unknown")


def summarize(kind: str, label: str, version: int, items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = dict.fromkeys(STATES, 0)
    counts.update(Counter(item["state"] for item in items))
    required = len(items) - counts["excluded"]
    if not required:
        status = "not_required"
    elif counts["running"] or counts["queued"]:
        status = "running"
    elif counts["unknown"] or counts["failed"]:
        status = "attention"
    elif counts["review"]:
        status = "review"
    elif counts["pending"]:
        status = "pending"
    else:
        status = "complete"
    return {
        "kind": kind,
        "label": label,
        "source_version": version,
        "items": items,
        "counts": counts,
        "required": required,
        "status": status,
        "resume_anchor": f"followup-{kind}",
    }


def character_progress(
    version: int,
    characters: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    approved: dict[str, str],
    excluded: set[str],
    reviewed: dict[str, int] | None = None,
) -> dict[str, Any]:
    latest = {j["character_id"]: j for j in sorted(jobs, key=lambda j: j["version"])}
    items = []
    for character in characters:
        cid = character["id"]
        job = latest.get(cid)
        if cid in excluded:
            state = "excluded"
        elif not job:
            state = "pending"
        elif (
            job["status"] in ("succeeded", "failed")
            and (reviewed or {}).get(cid, 0) >= job["version"]
            and any(str(j["id"]) == approved.get(cid) and j["status"] == "succeeded" for j in jobs)
        ):
            state = "approved"
        elif job["status"] == "succeeded":
            state = "approved" if approved.get(cid) == str(job["id"]) else "review"
        else:
            state = job["status"] if job["status"] in STATES else "unknown"
        items.append({"id": cid, "name": character["name"], "state": state})
    return summarize("character_images", "캐릭터 이미지", version, items)


def combine_progress(groups: list[dict[str, Any]]) -> dict[str, Any]:
    if len(groups) == 1:
        return groups[0]
    result = summarize("followup", "후속 작업", groups[0]["source_version"], [
        {**item, "id": f"{group['kind']}:{item['id']}"}
        for group in groups for item in group["items"]
    ])
    result["groups"] = groups
    next_group = next(
        (g for g in groups if g["status"] not in ("complete", "not_required")), groups[0]
    )
    result["resume_anchor"] = next_group["resume_anchor"]
    return result


def attach_progress(
    conn: psycopg.Connection[dict[str, Any]], workspace: UUID, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    data = conn.execute(
        "SELECT r.id::text, s.version, s.answer, p.characters, p.approved, "
        "v.definition->>'requires_approval' AS requires_approval, st.approved_version, "
        "COALESCE((SELECT jsonb_agg(jsonb_build_object('id',j.id,'character_id',j.character_id,"
        "'version',j.version,'status',j.status)) FROM character_image_jobs j "
        "WHERE j.workspace_id=r.workspace_id AND j.project_id=p.id),'[]') jobs, "
        "COALESCE((SELECT jsonb_agg(o.item_id) FROM work_item_preferences o "
        "WHERE o.workspace_id=r.workspace_id AND o.request_id=r.id "
        "AND o.source_version=s.version AND o.kind='character_images' AND "
        "o.excluded),'[]') excluded, "
        "COALESCE((SELECT jsonb_object_agg(o.item_id,o.reviewed_version) FROM "
        "work_item_preferences o "
        "WHERE o.workspace_id=r.workspace_id AND o.request_id=r.id AND o.source_version=s.version "
        "AND o.kind='character_images'),'{}') reviewed "
        "FROM customer_requests r JOIN registry_versions v "
        "USING(workspace_id,agent_id,version) "
        "LEFT JOIN script_stages st ON st.workspace_id=r.workspace_id AND st.request_id=r.id "
        "JOIN LATERAL (SELECT version,answer FROM script_versions "
        "WHERE workspace_id=r.workspace_id AND request_id=r.id ORDER BY version DESC "
        "LIMIT 1) s ON true "
        "LEFT JOIN character_projects p ON p.workspace_id=r.workspace_id AND p.request_id=r.id "
        "AND p.source_version=s.version WHERE r.workspace_id=%s AND r.id=ANY(%s)",
        (workspace, [UUID(row["id"]) for row in rows]),
    ).fetchall()
    progress = {}
    for record in data:
        groups = []
        if record["requires_approval"] == "true":
            groups.append(summarize("answer", "답변 검토", record["version"], [{
                "id": "answer", "name": "에이전트 답변",
                "state": (
                    "approved" if record["approved_version"] == record["version"] else "review"
                ),
            }]))
        answer = record["answer"]
        chars = record["characters"] or (
            answer.get("characters") if isinstance(answer, dict) else None
        )
        if (
            isinstance(chars, list)
            and chars
            and all(
                isinstance(c, dict)
                and all(isinstance(c.get(k), str) for k in ("id", "name", "image_prompt"))
                for c in chars
            )
        ):
            groups.append(character_progress(
                record["version"],
                chars,
                record["jobs"],
                record["approved"] or {},
                set(record["excluded"]),
                record["reviewed"],
            ))
        if groups:
            progress[record["id"]] = combine_progress(groups)
    for row in rows:
        row["work_progress"] = progress.get(row["id"])
