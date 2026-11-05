"""Workspace administrator deletion preview, atomic removal and metadata-only audit."""

import hashlib
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from psycopg import errors
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.database import connection
from asa.registry.schemas import RegistryError


class DeleteWork(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delete_assets: bool = False
    token: str = Field(pattern=r"^[0-9a-f]{64}$")


def impact(conn: Any, workspace: UUID, request: UUID, assets: bool) -> dict[str, Any]:
    args = (workspace, request)
    row = conn.execute(
        "SELECT r.status, r.updated_at, v.definition->>'name' AS name "
        "FROM customer_requests r JOIN registry_versions v USING(workspace_id,agent_id,version) "
        "WHERE r.workspace_id=%s AND r.id=%s",
        args,
    ).fetchone()
    if not row:
        raise RegistryError(404, "work_not_found")
    jobs = conn.execute(
        "SELECT j.id::text,j.status,j.character->>'name' AS label,j.version,"
        "(j.image IS NOT NULL) AS generated FROM character_image_jobs j "
        "JOIN character_projects p ON p.workspace_id=j.workspace_id AND p.id=j.project_id "
        "WHERE p.workspace_id=%s AND p.request_id=%s ORDER BY j.id",
        args,
    ).fetchall()
    clips = conn.execute(
        "SELECT id::text,status,clip_id AS label,answer_version AS version,"
        "(video IS NOT NULL) AS generated FROM video_clip_jobs "
        "WHERE workspace_id=%s AND request_id=%s ORDER BY id",
        args,
    ).fetchall()
    versions = conn.execute(
        "SELECT version FROM script_versions WHERE workspace_id=%s AND "
        "request_id=%s ORDER BY version",
        args,
    ).fetchall()
    reasons = []
    active = {"queued", "running", "submitting"}
    if (
        row["status"] in active
        or any(j["status"] in active for j in jobs + clips)
        or conn.execute(
            "SELECT 1 FROM script_attempts WHERE workspace_id=%s AND request_id=%s "
            "AND status IN ('queued','running') UNION ALL SELECT 1 FROM asset_reviews a "
            "JOIN character_projects p ON p.workspace_id=a.workspace_id AND p.id=a.project_id "
            "WHERE p.workspace_id=%s AND p.request_id=%s AND a.status IN ('queued','running') "
            "LIMIT 1",
            args + args,
        ).fetchone()
    ):
        reasons.append("실행 중인 작업이 있습니다. 실행이 끝나거나 취소된 뒤 삭제하세요.")
    if conn.execute(
        "SELECT 1 FROM customer_requests WHERE workspace_id=%s AND source_id=%s LIMIT 1", args
    ).fetchone():
        reasons.append("이 요청으로 다시 시작한 작업이 원본을 참조하고 있습니다.")
    references = []
    if jobs or clips:
        ids = [j["id"] for j in jobs + clips]
        # These JSON snapshots may contain a selected image, a handoff project, or a clip URL.
        ids.extend(
            r["id"]
            for r in conn.execute(
                "SELECT id::text FROM character_projects WHERE workspace_id=%s AND request_id=%s",
                args,
            ).fetchall()
        )
        linked = conn.execute(
            """
            WITH refs AS (
             SELECT input::text AS payload FROM customer_requests WHERE workspace_id=%s AND id<>%s
             UNION ALL SELECT answer::text FROM script_versions WHERE workspace_id=%s
             AND request_id<>%s
             UNION ALL SELECT context::text FROM character_projects WHERE workspace_id=%s
             AND request_id<>%s
             UNION ALL SELECT j.scene_context::text FROM character_image_jobs j
             JOIN character_projects p ON p.workspace_id=j.workspace_id AND p.id=j.project_id
             WHERE p.workspace_id=%s AND p.request_id<>%s
             UNION ALL SELECT generation_input::text FROM video_clip_jobs WHERE workspace_id=%s
             AND request_id<>%s
             UNION ALL SELECT draft::text FROM automation_drafts WHERE workspace_id=%s
             UNION ALL SELECT definition::text||manifest::text||steps::text||prompt||
              COALESCE(graph_state::text,'')
             FROM automation_runs WHERE workspace_id=%s
             UNION ALL SELECT definition::text||manifest::text||prompt FROM automation_schedules
             WHERE workspace_id=%s
             UNION ALL SELECT definition::text FROM registry_versions WHERE workspace_id=%s
             UNION ALL SELECT draft::text FROM registry_agents WHERE workspace_id=%s
            )
            SELECT id FROM unnest(%s::text[]) AS ids(id) WHERE EXISTS
             (SELECT 1 FROM refs WHERE position(ids.id in payload)>0) ORDER BY id
        """,
            args * 5 + (workspace,) * 5 + (ids,),
        ).fetchall()
        labels = {j["id"]: f"{j['label']} · v{j['version']}" for j in jobs + clips}
        references = [labels.get(r["id"], "결과물 묶음") for r in linked]
        if assets and linked:
            reasons.append("다른 작업이나 자동화가 결과물을 참조합니다. 결과물을 보존하세요.")
    counts = {
        "requests": 1,
        "answers": len(versions),
        "images": sum(j["generated"] for j in jobs),
        "videos": sum(j["generated"] for j in clips),
        "delete_assets": assets,
    }
    stamp = json.dumps(
        [str(request), str(row["updated_at"]), versions, jobs, clips, counts, reasons],
        sort_keys=True,
    )
    return {
        "name": row["name"],
        "summary": counts,
        "blockers": reasons,
        "references": references,
        "token": hashlib.sha256(stamp.encode()).hexdigest(),
    }


def management_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin/work-history")

    def admin(p: Principal = Depends(sessions.principal)) -> Principal:
        if not {"owner", "admin"}.intersection(p.roles):
            raise RegistryError(403, "admin_required")
        return p

    @router.get("")
    def listing(
        q: str = Query("", max_length=200),
        deleted: bool = False,
        offset: int = Query(0, ge=0, le=100000),
        p: Principal = Depends(admin),
    ) -> dict[str, Any]:
        with connection(settings.database_url, dictionary=True) as conn:
            if deleted:
                query = (
                    "SELECT d.request_id,d.name,d.actor,d.deleted_at,d.summary,"
                    " ARRAY(SELECT jsonb_build_object('id',v.id,'label',v.clip_id) "
                    "FROM retained_work_videos v WHERE v.workspace_id=d.workspace_id "
                    "AND v.request_id=d.request_id) AS videos FROM work_deletions d "
                    "WHERE workspace_id=%s AND position(lower(%s) in lower(name))>0 "
                    "ORDER BY deleted_at DESC,request_id"
                )
            else:
                query = (
                    "SELECT r.id AS request_id,r.created_at,r.status,v.definition->>'name' "
                    "AS name FROM customer_requests r JOIN registry_versions v "
                    "USING(workspace_id,agent_id,version) WHERE r.workspace_id=%s AND "
                    "position(lower(%s) in lower(v.definition->>'name'))>0 "
                    "ORDER BY r.created_at DESC,r.id"
                )
            rows = conn.execute(
                query + " LIMIT 21 OFFSET %s", (p.workspace_id, q, offset)
            ).fetchall()
            return {"items": rows[:20], "has_more": len(rows) > 20}

    @router.get("/{request}/preview")
    def preview(
        request: UUID, delete_assets: bool = False, p: Principal = Depends(admin)
    ) -> dict[str, Any]:
        with connection(settings.database_url, dictionary=True) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            return impact(conn, p.workspace_id, request, delete_assets)

    @router.post("/{request}/delete")
    def delete(request: UUID, body: DeleteWork, p: Principal = Depends(admin)) -> dict[str, Any]:
        args = (p.workspace_id, request)
        try:
            with connection(settings.database_url, dictionary=True) as conn:
                conn.execute("SET LOCAL lock_timeout='2s'")
                conn.execute("SELECT id FROM registry_workspaces WHERE id=%s FOR UPDATE", args[:1])
                previous = conn.execute(
                    "SELECT actor,confirmation_token,summary FROM work_deletions "
                    "WHERE workspace_id=%s AND request_id=%s",
                    args,
                ).fetchone()
                if previous:
                    if (
                        previous["actor"] == p.user_id
                        and previous["confirmation_token"] == body.token
                        and previous["summary"]["delete_assets"] == body.delete_assets
                    ):
                        return dict(previous["summary"])
                    raise RegistryError(409, "deletion_changed")
                # Prevent new references, queued jobs, and worker completions during final check.
                conn.execute(
                    "LOCK TABLE customer_requests,script_stages,script_versions,"
                    "script_attempts,character_projects,character_image_jobs,asset_reviews,"
                    "video_clip_jobs,automation_drafts,automation_runs,automation_schedules,"
                    "registry_versions,registry_agents IN SHARE ROW EXCLUSIVE MODE"
                )
                plan = impact(conn, *args, body.delete_assets)
                if plan["blockers"] or plan["token"] != body.token:
                    raise RegistryError(409, "deletion_changed")
                summary: dict[str, Any] = plan["summary"]
                conn.execute(
                    "INSERT INTO work_deletions(workspace_id,request_id,name,actor,"
                    "summary,confirmation_token)"
                    " VALUES (%s,%s,%s,%s,%s,%s)",
                    (*args, plan["name"], p.user_id, Jsonb(summary), body.token),
                )
                projects = (
                    "SELECT id FROM character_projects WHERE workspace_id=%s AND request_id=%s"
                )
                if body.delete_assets:
                    for table in ("asset_reviews", "character_image_jobs"):
                        conn.execute(
                            f"DELETE FROM {table} WHERE workspace_id=%s AND project_id "
                            f"IN ({projects})",
                            (p.workspace_id, *args),
                        )
                    conn.execute(
                        "DELETE FROM character_projects WHERE workspace_id=%s AND request_id=%s",
                        args,
                    )
                    conn.execute(
                        "DELETE FROM work_item_preferences WHERE workspace_id=%s AND request_id=%s",
                        args,
                    )
                else:
                    conn.execute(
                        "INSERT INTO retained_work_videos SELECT workspace_id,id,"
                        "request_id,clip_id,answer_version,video FROM video_clip_jobs "
                        "WHERE workspace_id=%s AND request_id=%s AND video IS NOT NULL",
                        args,
                    )
                    conn.execute(
                        "UPDATE character_image_jobs SET scene_context=scene_context "
                        "- 'source_input' WHERE workspace_id=%s AND project_id IN "
                        f"({projects}) AND jsonb_typeof(scene_context)='object'",
                        (p.workspace_id, *args),
                    )
                    conn.execute(
                        "UPDATE character_projects SET context='{}' WHERE workspace_id=%s "
                        "AND request_id=%s",
                        args,
                    )
                for table in (
                    "video_clip_jobs",
                    "script_attempts",
                    "script_versions",
                    "script_stages",
                ):
                    conn.execute(
                        f"DELETE FROM {table} WHERE workspace_id=%s AND request_id=%s", args
                    )
                conn.execute(
                    "UPDATE ai_usage_events SET original_request=NULL,messages=NULL,"
                    "response=NULL WHERE workspace_id=%s AND request_id=%s",
                    (p.workspace_id, str(request)),
                )
                conn.execute("DELETE FROM customer_requests WHERE workspace_id=%s AND id=%s", args)
                return summary
        except (
            errors.LockNotAvailable,
            errors.DeadlockDetected,
            errors.ForeignKeyViolation,
        ) as exc:
            raise RegistryError(409, "deletion_changed") from exc

    return router
