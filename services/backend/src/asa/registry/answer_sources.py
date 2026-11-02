"""Read-only workspace-scoped answer snapshots for reuse in text inputs."""
import re
from typing import Any
from uuid import UUID

from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError

# Resolve provenance from the immutable execution manifest, never from current drafts.
# Ordinality identifies repeated executions of the same graph node independently.
AUTOMATION_ANSWERS = """
    SELECT r.id::text, false AS is_test, r.created_at, m.tool->>'name' AS name,
           1 AS version, r.created_at AS answered_at,
           s.step->'input' AS input, s.step->'output' AS answer, NULL::text AS title,
           'automation'::text AS source_kind, (s.ordinality-1)::int AS step_index,
           r.definition->>'name' AS automation_name,
           coalesce(s.step->>'label',m.tool->>'name') AS step_label,
           m.tool->>'agent_id' AS agent_id, m.tool->'output_schema' AS schema
    FROM automation_runs r
    CROSS JOIN LATERAL jsonb_array_elements(r.steps) WITH ORDINALITY s(step,ordinality)
    JOIN LATERAL (
        SELECT tool FROM jsonb_array_elements(r.manifest) WITH ORDINALITY t(tool,n)
        WHERE (s.step->>'node_id' IS NOT NULL AND tool->>'node_id'=s.step->>'node_id')
           OR (s.step->>'node_id' IS NULL AND
               r.definition->'steps'->(t.n::int-1)->>'id'=s.step->>'id')
        LIMIT 1
    ) m ON true
    WHERE r.workspace_id=%s AND m.tool->>'agent_id' IS NOT NULL
      AND s.step->>'status'='succeeded'
      AND s.step->'output' IS NOT NULL AND s.step->'output'<>'null'::jsonb
"""


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
        if not heading:
            match = re.search(r'^\s*\*\*제목:\s*(.+?)\*\*', answer, re.MULTILINE)
            heading = match.group(1) if match else ''
    heading = heading.strip() or summary or '제목 없는 작업'
    return {'title': heading[:120], 'request_preview': summary[:240]}


def answer_sources(repo: RegistryRepository, q: str = '', offset: int = 0,
                   agent_id: UUID | None = None) -> dict[str, Any]:
    with repo._connect() as conn:
        rows = conn.execute("""
            WITH sources AS (
            SELECT r.id::text,r.is_test,r.created_at,v.definition->>'name' name,
                   a.version,a.created_at answered_at,r.input,a.answer,a.title,
                   'agent'::text source_kind,NULL::int step_index,
                   NULL::text automation_name,NULL::text step_label,r.agent_id::text,
                   v.definition->'output_schema' schema
            FROM customer_requests r JOIN registry_versions v USING(workspace_id,agent_id,version)
            JOIN LATERAL (SELECT version,created_at,answer,title FROM script_versions s
                WHERE s.workspace_id=r.workspace_id AND s.request_id=r.id
                ORDER BY version DESC LIMIT 1) a ON true
            WHERE r.workspace_id=%s
            UNION ALL
        """ + AUTOMATION_ANSWERS + """
            ) SELECT * FROM sources
            WHERE (%s::text IS NULL OR agent_id=%s::text) AND (%s='' OR
                position(lower(%s) in lower(coalesce(name,'') || coalesce(input::text,'') ||
                  coalesce(title,'') || coalesce(answer::text,'') ||
                  coalesce(automation_name,'')))>0)
            ORDER BY answered_at DESC,id DESC,step_index ASC NULLS FIRST LIMIT 21 OFFSET %s
        """, (repo.workspace_id, repo.workspace_id, agent_id, agent_id, q, q, offset)).fetchall()
    for row in rows:
        row.update(work_summary(row.pop('answer'), row.pop('title'), row.pop('input')))
        row.pop('schema')
    return {'items': rows[:20], 'has_more': len(rows) > 20}


def automation_answer(repo: RegistryRepository, run_id: UUID, step_index: int) -> dict[str, Any]:
    with repo._connect() as conn:
        row = conn.execute('SELECT * FROM (' + AUTOMATION_ANSWERS +
                           ') a WHERE id=%s AND step_index=%s',
                           (repo.workspace_id, str(run_id), step_index)).fetchone()
    if row is None:
        raise RegistryError(404, 'work_not_found')
    return {'name': row['name'], 'schema': row['schema'] or {}, 'versions': [{
        'version': 1, 'answer': row['answer'], 'source': 'ai',
        'created_at': row['created_at']}]}


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
