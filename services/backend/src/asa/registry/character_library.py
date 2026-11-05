"""Image-first library and verified user selections. No image bytes in list responses."""
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from asa.registry.schemas import RegistryError

SELECTION_FORMAT = 'asa_character_selection_v1'


class ImageSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    image_ids: list[UUID] = Field(min_length=1, max_length=12)

    @model_validator(mode='after')
    def unique(self) -> 'ImageSelection':
        if len(set(self.image_ids)) != len(self.image_ids):
            raise ValueError('duplicate_image_selection')
        return self


# Use the same approval rules as character_progress, including newer pending/review images.
BASE = """
WITH images AS (
 SELECT j.change AS image_change,j.id::text,j.project_id::text,j.character_id,j.version,
 j.character,j.model,
 j.created_at::text,p.name project_name,p.request_id::text,p.source_version,
 r.agent_id::text,COALESCE(v.definition->>'name',d.name,'이전 에이전트') agent_name,
 d.request_id IS NOT NULL AS source_deleted,
 (p.approved->>j.character_id=j.id::text OR
 (p.kind='character' AND COALESCE(p.approved_versions->j.character_id,'[]'::jsonb)
 ? j.id::text)) AS confirmed,
 p.approved->>j.character_id=j.id::text AS is_default,
 CASE WHEN COALESCE(pref.excluded,false) THEN 'excluded'
 WHEN latest.status IN ('succeeded','failed') AND
 (COALESCE(pref.reviewed_version,0)>=latest.version OR
 p.approved->>j.character_id=latest.id::text) AND
 EXISTS (SELECT 1 FROM character_image_jobs a WHERE a.workspace_id=j.workspace_id
 AND a.project_id=j.project_id AND a.id::text=p.approved->>j.character_id
 AND a.status='succeeded') THEN 'approved'
 WHEN latest.status='succeeded' THEN 'review' ELSE latest.status END AS state
 FROM character_image_jobs j
 JOIN character_projects p ON p.workspace_id=j.workspace_id AND p.id=j.project_id
 LEFT JOIN customer_requests r ON r.workspace_id=p.workspace_id AND r.id=p.request_id
 LEFT JOIN registry_versions v ON v.workspace_id=r.workspace_id AND v.agent_id=r.agent_id
 AND v.version=r.version
 LEFT JOIN work_deletions d ON d.workspace_id=p.workspace_id AND d.request_id=p.request_id
 LEFT JOIN work_item_preferences pref ON pref.workspace_id=p.workspace_id
 AND pref.request_id=p.request_id AND pref.source_version=p.source_version
 AND pref.kind=CASE WHEN p.kind='scene' THEN 'scene_images' ELSE 'character_images' END
 AND pref.item_id=j.character_id
 JOIN LATERAL (SELECT id,version,status FROM character_image_jobs l
 WHERE l.workspace_id=j.workspace_id AND l.project_id=j.project_id
 AND l.character_id=j.character_id AND l.status<>'cancelled'
 ORDER BY version DESC LIMIT 1) latest ON true
 WHERE p.kind=%s AND j.workspace_id=%s AND j.status='succeeded' AND j.image IS NOT NULL
 UNION ALL
 SELECT '' AS image_change,u.id::text,u.id::text,u.character->>'id',1,u.character,'사용자 업로드',
 u.created_at::text,'직접 업로드',NULL::text,1,NULL::text,'직접 업로드',false,true,true,'approved'
 FROM character_reference_uploads u WHERE u.workspace_id=%s AND %s='character'
), representatives AS (
 SELECT DISTINCT ON (project_id,character_id) * FROM images
 ORDER BY project_id,character_id,
 CASE WHEN %s='scene' AND state='review' THEN version END DESC NULLS LAST,
 is_default DESC NULLS LAST,confirmed DESC NULLS LAST,version DESC
)
"""


def library(repo: Any, q: str = '', state: str = '', project: str = '',
            agent: str = '', offset: int = 0, kind: str = 'character',
            confirmed_versions: bool = False) -> dict[str, Any]:
    source = ('images WHERE confirmed AND state != \'excluded\' AND '
              if confirmed_versions and kind == 'character' else 'representatives WHERE ')
    with repo._connect() as conn:
        rows = conn.execute(BASE + 'SELECT * FROM ' + source + """
 (%s='' OR position(lower(%s) in lower(character->>'name'||' '||project_name||' '||agent_name))>0)
 AND (%s='' OR state=%s) AND (%s='' OR project_id=%s) AND (%s='' OR agent_id=%s)
 ORDER BY created_at DESC,id LIMIT 25 OFFSET %s
 """, (kind, repo.workspace_id, repo.workspace_id, kind, kind, q, q, state, state,
       project, project, agent, agent, offset)).fetchall()
        facets = conn.execute(BASE + "SELECT DISTINCT project_id,project_name,agent_id,agent_name "
                             "FROM representatives ORDER BY project_name,project_id",
                             (kind, repo.workspace_id, repo.workspace_id, kind, kind)).fetchall()
    return {'items': rows[:24], 'has_more': len(rows) > 24, 'facets': facets}


def versions(repo: Any, image_id: UUID, kind: str = 'character') -> list[dict[str, Any]]:
    with repo._connect() as conn:
        rows = conn.execute(BASE + "SELECT * FROM images WHERE (project_id,character_id)="
                            "(SELECT project_id,character_id FROM images WHERE id=%s) "
                            "ORDER BY version DESC",
                            (kind, repo.workspace_id, repo.workspace_id, kind, kind,
                             str(image_id))).fetchall()
    return [dict(row) for row in rows]


def selected_handoff(repo: Any, image_ids: list[UUID]) -> dict[str, Any]:
    from asa.registry.characters import CharacterRepository

    if not 1 <= len(image_ids) <= 12 or len(set(image_ids)) != len(image_ids):
        raise RegistryError(422, 'character_selection_invalid')
    source = CharacterRepository(repo.dsn, repo.workspace_id)
    with source._connect() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        rows = conn.execute('SELECT id,project_id,character_id FROM character_image_jobs '
                            'WHERE workspace_id=%s AND id=ANY(%s) AND image IS NOT NULL '
                            "AND status='succeeded'", (repo.workspace_id, image_ids)).fetchall()
        indexed = {row['id']: row for row in rows}
        uploads = conn.execute('SELECT id,character FROM character_reference_uploads '
                               'WHERE workspace_id=%s AND id=ANY(%s)',
                               (repo.workspace_id, image_ids)).fetchall()
        uploaded = {row['id']: row for row in uploads}
        if len(indexed) + len(uploaded) != len(image_ids):
            raise RegistryError(404, 'character_selection_missing')
        identities = {(row['project_id'], row['character_id']) for row in rows}
        if len(identities) != len(rows):
            raise RegistryError(422, 'character_selection_duplicate_character')
        projects = {row['project_id']: source.project(row['project_id'], conn) for row in rows}
        characters = []
        for image_id in image_ids:
            if image_id in uploaded:
                from asa.registry.character_uploads import uploaded_character
                characters.append(uploaded_character(uploaded[image_id]))
                continue
            row = indexed[image_id]
            p = projects[row['project_id']]
            if p['kind'] != 'character':
                raise RegistryError(422, 'character_selection_invalid')
            cid = row['character_id']
            state = next((i['state'] for i in p['work_progress']['items'] if i['id'] == cid), None)
            if state == 'excluded' or str(image_id) not in p.get('approved_versions', {}).get(
                cid, [p['approved'].get(cid)]
            ):
                raise RegistryError(409, 'character_selection_not_ready')
            job = next(j for j in p['jobs'] if j['id'] == str(image_id))
            characters.append({**job['character'], 'image_id': str(image_id),
                               'image_version': job['version'], 'image_change': job['change'],
                               'project_id': p['id'], 'source_request_id': p['request_id'],
                               'source_version': p['source_version']})
    return {'format': SELECTION_FORMAT, 'characters': characters}
