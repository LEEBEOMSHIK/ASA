"""Read-only workspace-scoped answer snapshots for reuse in text inputs."""
from typing import Any
from uuid import UUID

from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError


def work_summary(answer: Any, title: str | None, request: Any) -> dict[str, str]:
    """Use saved content to identify a work item; never generate a new title with AI."""
    values = request.values() if isinstance(request, dict) else [request]
    summary = ' · '.join(v.strip() for v in values if isinstance(v, str) and v.strip())
    heading = answer.get('title') if isinstance(answer, dict) else None
    if not isinstance(heading, str) or not heading.strip():
        heading = title or ''
    if not heading and isinstance(answer, str):
        heading = next((line.lstrip('# ').strip() for line in answer.splitlines()
                        if line.startswith('# ')), '')
    heading = heading.strip() or summary or '제목 없는 작업'
    return {'title': heading[:120], 'request_preview': summary[:240]}


def answer_sources(repo: RegistryRepository, q: str = '', offset: int = 0,
                   agent_id: UUID | None = None) -> dict[str, Any]:
    with repo._connect() as conn:
        rows = conn.execute("""
            SELECT r.id::text,r.is_test,r.created_at::text,v.definition->>'name' name,
                   a.version,a.created_at::text answered_at,r.input,a.answer,a.title
            FROM customer_requests r JOIN registry_versions v USING(workspace_id,agent_id,version)
            JOIN LATERAL (SELECT version,created_at,answer,title FROM script_versions s
                WHERE s.workspace_id=r.workspace_id AND s.request_id=r.id
                ORDER BY version DESC LIMIT 1) a ON true
            WHERE r.workspace_id=%s AND (%s::uuid IS NULL OR r.agent_id=%s) AND (%s='' OR
                position(lower(%s) in lower(v.definition->>'name'))>0 OR
                position(lower(%s) in lower(r.input::text))>0 OR
                position(lower(%s) in lower(coalesce(a.title,'') || coalesce(a.answer::text,'')))>0)
            ORDER BY a.created_at DESC,r.id DESC LIMIT 21 OFFSET %s
        """, (repo.workspace_id, agent_id, agent_id, q, q, q, q, offset)).fetchall()
    for row in rows:
        row.update(work_summary(row.pop('answer'), row.pop('title'), row.pop('input')))
    return {'items': rows[:20], 'has_more': len(rows) > 20}


def answer_versions(repo: RegistryRepository, request_id: UUID) -> dict[str, Any]:
    with repo._connect() as conn:
        row = conn.execute("SELECT v.definition->>'name' name,v.definition->'output_schema' schema "
                           "FROM customer_requests r JOIN registry_versions v "
                           "USING(workspace_id,agent_id,version) "
                           "WHERE r.workspace_id=%s AND r.id=%s",
                           (repo.workspace_id, request_id)).fetchone()
        if row is None:
            raise RegistryError(404, 'work_not_found')
        versions = conn.execute("SELECT version,answer,title,narration,source,created_at::text "
                                "FROM script_versions WHERE workspace_id=%s AND request_id=%s "
                                "ORDER BY version DESC", (repo.workspace_id, request_id)).fetchall()
    # Legacy answers have title/narration columns but no general answer payload.
    for version in versions:
        if version['answer'] is None:
            version['answer'] = {'title': version['title'], 'narration': version['narration']}
        del version['title'], version['narration']
    return {**row, 'versions': versions}
