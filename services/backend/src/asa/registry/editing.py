"""Workspace-scoped source selection and immutable edit render queue."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, ValidationError

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.database import connection
from asa.editing_contracts import EditPlan
from asa.editing_media import probe
from asa.registry import library
from asa.registry.media_response import media_response
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError
from asa.registry.video_reference import VideoSource, decode_video, save_source
from asa.voice_directions import answer_contract


def sources(settings: Settings, p: Principal) -> list[dict[str, Any]]:
    data = library.index(RegistryRepository(settings.database_url, p.workspace_id), p.user_id)
    rows = [
        i
        for i in library.visible_items(data["items"])
        if i.get("media_url")
        and (
            (i["id"].startswith("video:") and i["status"] == "approved")
            or (i["id"].startswith("image:") and i["status"] == "approved")
            or (i["id"].startswith("audio:") and i["kind"] == "audio" and i["status"] == "approved")
            or i["id"].startswith("music:")
            or i["id"].startswith("reference:")
        )
    ]
    with connection(settings.database_url, dictionary=True) as conn:
        durations = conn.execute(
            "SELECT 'video:'||id id,"
            "generation_input->>'duration_seconds' duration FROM video_clip_jobs "
            "WHERE workspace_id=%s "
            "UNION ALL SELECT 'audio:'||id,duration::text FROM audio_jobs WHERE workspace_id=%s "
            "AND coalesce(input->>'purpose','production')='production' "
            "UNION ALL SELECT 'music:'||id,duration::text FROM audio_assets WHERE workspace_id=%s "
            "UNION ALL SELECT 'reference:'||id,duration_seconds::text FROM video_references "
            "WHERE workspace_id=%s",
            (p.workspace_id, p.workspace_id, p.workspace_id, p.workspace_id),
        ).fetchall()
        approved_speech = conn.execute(
            "SELECT 'audio:'||id AS id,input#>>'{speaker,name}' AS speaker,"
            "input#>>'{cue,text}' AS dialogue FROM audio_jobs WHERE workspace_id=%s "
            "AND kind='speech' AND status='approved' "
            "AND coalesce(input->>'purpose','production')='production'",
            (p.workspace_id,),
        ).fetchall()
    lengths = {r["id"]: float(r["duration"]) if r["duration"] else None for r in durations}
    speech = {row["id"]: row for row in approved_speech}
    rows = [item for item in rows if not item["id"].startswith("audio:") or item["id"] in speech]
    for item in rows:
        item["duration"] = lengths.get(item["id"])
        if item["id"] in speech:
            audio = speech[item["id"]]
            if audio["speaker"] and audio["dialogue"]:
                item["title"] = f"{audio['speaker']} · {audio['dialogue'][:90]}"
    return rows


def source_bytes(conn: Any, workspace: UUID, source_id: str) -> bytes:
    kind, _, ident = source_id.partition(":")
    try:
        key = UUID(ident)
    except ValueError as error:
        raise RegistryError(422, "editing_source_missing") from error
    if kind == "reference":
        row = conn.execute(
            "SELECT video data FROM video_references WHERE workspace_id=%s AND id=%s",
            (workspace, key),
        ).fetchone()
    elif kind == "video":
        row = conn.execute(
            "SELECT video data FROM video_clip_jobs WHERE workspace_id=%s "
            "AND id=%s AND status='approved'",
            (workspace, key),
        ).fetchone()
    elif kind == "image":
        row = conn.execute(
            "SELECT j.image data FROM character_image_jobs j "
            "JOIN character_projects p ON p.workspace_id=j.workspace_id AND p.id=j.project_id "
            "WHERE j.workspace_id=%s AND j.id=%s AND j.status='succeeded' AND "
            "(p.approved->>j.character_id=j.id::text OR "
            "coalesce(p.approved_versions->j.character_id,'[]'::jsonb) ? j.id::text)",
            (workspace, key),
        ).fetchone()
    elif kind == "audio":
        row = conn.execute(
            "SELECT media data FROM audio_jobs WHERE workspace_id=%s "
            "AND id=%s AND status='approved' AND kind='speech' "
            "AND coalesce(input->>'purpose','production')='production'",
            (workspace, key),
        ).fetchone()
    elif kind == "music":
        row = conn.execute(
            "SELECT data FROM audio_assets WHERE workspace_id=%s AND id=%s", (workspace, key)
        ).fetchone()
    else:
        row = None
    if not row or not row["data"]:
        raise RegistryError(409, "editing_source_missing")
    return bytes(row["data"])


def selected_ids(conn: Any, workspace: UUID, request: UUID, version: int) -> set[str]:
    contract = answer_contract(conn, workspace, request, version)
    if contract:
        inputs = contract.get("original_request", {})
    else:
        row = conn.execute(
            "SELECT input FROM customer_requests WHERE workspace_id=%s AND id=%s",
            (workspace, request),
        ).fetchone()
        inputs = row["input"] if row else {}
    try:
        raw = json.loads(inputs.get("editing_sources", "[]"))
        return {i["id"] for i in raw if isinstance(i, dict) and isinstance(i.get("id"), str)}
    except (ValueError, TypeError):
        return set()


class RenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    version: int


def editing_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.post("/editing/uploads", status_code=201)
    def upload(body: VideoSource, p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        if body.url or not body.data:
            raise RegistryError(422, "editing_file_required")
        raw = decode_video(body.data)
        try:
            with TemporaryDirectory(prefix="asa-edit-probe-") as folder:
                path = Path(folder) / "video"
                path.write_bytes(raw)
                duration, _ = probe(path, settings.ffmpeg_path)
            if not 0 < duration <= 600:
                raise ValueError("editing_duration_limit")
        except Exception as exc:
            raise RegistryError(422, "editing_upload_invalid") from exc
        repo = RegistryRepository(settings.database_url, p.workspace_id)
        saved = save_source(repo, body)
        with connection(settings.database_url) as conn:
            conn.execute("UPDATE video_references SET duration_seconds=%s "
                         "WHERE workspace_id=%s AND id=%s",
                         (duration, p.workspace_id, saved["source_id"]))
        return {"id": "reference:" + saved["source_id"], "title": body.filename,
                "kind": "video", "duration": duration,
                "media_url": f"/api/v1/library/references/{saved['source_id']}/media"}

    @router.get("/editing/sources")
    def listing(
        q: str = Query("", max_length=120),
        kind: str = "all",
        origin: Literal["all", "studio", "upload"] = "all",
        page: int = Query(1, ge=1, le=100000),
        p: Principal = Depends(sessions.principal),
    ) -> dict[str, Any]:
        rows = [
            i
            for i in sources(settings, p)
            if (kind == "all" or i["kind"] == kind or (kind == "audio" and i["kind"] == "music"))
            and (origin == "all" or i["id"].startswith("reference:") == (origin == "upload"))
            and q.casefold()
            in " ".join(
                str(i.get(k) or "") for k in ("title", "source_name", "work_name", "agent_name")
            ).casefold()
        ]
        return {"items": rows[(page - 1) * 12 : page * 12], "total": len(rows)}

    @router.get("/work-requests/{request}/editing")
    def jobs(request: UUID, p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        with connection(settings.database_url, dictionary=True) as conn:
            rows = conn.execute(
                "SELECT id,answer_version,status,error_code,created_at,started_at,"
                "finished_at,plan->>'title' title FROM editing_jobs WHERE workspace_id=%s "
                "AND request_id=%s ORDER BY created_at DESC",
                (p.workspace_id, request),
            ).fetchall()
        return {"jobs": rows}

    @router.post("/work-requests/{request}/editing/compose")
    def enqueue(
        request: UUID, body: RenderRequest, p: Principal = Depends(sessions.principal)
    ) -> dict[str, Any]:
        with connection(settings.database_url, dictionary=True) as conn:
            stage = conn.execute(
                "SELECT * FROM script_stages WHERE workspace_id=%s AND request_id=%s FOR UPDATE",
                (p.workspace_id, request),
            ).fetchone()
            if not stage:
                raise RegistryError(404, "work_not_found")
            existing = conn.execute(
                "SELECT id,request_id,answer_version FROM editing_jobs "
                "WHERE workspace_id=%s AND id=%s",
                (p.workspace_id, body.id),
            ).fetchone()
            if existing:
                if existing["request_id"] != request or existing["answer_version"] != body.version:
                    raise RegistryError(409, "editing_operation_conflict")
                return {"id": existing["id"]}
            if stage["approved_version"] != body.version or stage["head_version"] != body.version:
                raise RegistryError(409, "editing_approval_required")
            pending = conn.execute(
                "SELECT 1 FROM script_attempts WHERE workspace_id=%s "
                "AND request_id=%s AND status IN ('queued','running')",
                (p.workspace_id, request),
            ).fetchone()
            if pending:
                raise RegistryError(409, "editing_approval_required")
            existing = conn.execute(
                "SELECT id FROM editing_jobs WHERE workspace_id=%s "
                "AND request_id=%s AND answer_version=%s AND status<>'failed'",
                (p.workspace_id, request, body.version),
            ).fetchone()
            if existing:
                return {"id": existing["id"]}
            row = conn.execute(
                "SELECT answer FROM script_versions WHERE workspace_id=%s "
                "AND request_id=%s AND version=%s",
                (p.workspace_id, request, body.version),
            ).fetchone()
            try:
                plan = EditPlan.model_validate(row["answer"] if row else None)
            except ValidationError as error:
                raise RegistryError(422, "editing_plan_invalid") from error
            identifiers = {s.source_id for s in plan.segments} | {t.source_id for t in plan.tracks}
            allowed = selected_ids(conn, p.workspace_id, request, body.version)
            catalog = {i["id"]: i for i in sources(settings, p)}
            if not identifiers <= allowed or not identifiers <= catalog.keys():
                raise RegistryError(409, "editing_source_missing")
            assets = {key: source_bytes(conn, p.workspace_id, key) for key in identifiers}
            if sum(map(len, assets.values())) > 300 * 1024 * 1024:
                raise RegistryError(422, "editing_source_limit")
            count = conn.execute(
                "SELECT count(*) n FROM editing_jobs WHERE workspace_id=%s "
                "AND status IN ('queued','running')",
                (p.workspace_id,),
            ).fetchone()
            if count and count["n"] >= 10:
                raise RegistryError(409, "editing_queue_full")
            conn.execute(
                "INSERT INTO editing_jobs(workspace_id,id,request_id,answer_version,plan,status) "
                "VALUES (%s,%s,%s,%s,%s,'queued')",
                (
                    p.workspace_id,
                    body.id,
                    request,
                    body.version,
                    Jsonb(plan.model_dump(mode="json")),
                ),
            )
            for key, raw in assets.items():
                meta = {**catalog[key], "sha256": hashlib.sha256(raw).hexdigest()}
                conn.execute(
                    "INSERT INTO editing_job_assets(workspace_id,job_id,source_id,metadata,data) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (p.workspace_id, body.id, key, Jsonb(meta), raw),
                )
        return {"id": body.id}

    @router.get("/editing/jobs/{job}/media")
    def media(job: UUID, request: Request, p: Principal = Depends(sessions.principal)) -> Response:
        with connection(settings.database_url, dictionary=True) as conn:
            response = media_response(
                conn, "SELECT media,'video/mp4' AS media_type "
                "FROM editing_jobs WHERE workspace_id=%s AND id=%s "
                "AND status IN ('review','approved') AND media IS NOT NULL",
                (p.workspace_id, job), request.headers.get("range", ""), "editing_result_missing",
            )
        if response is None:
            raise RegistryError(404, "editing_result_missing")
        return response

    @router.post("/editing/jobs/{job}/approve")
    def approve(job: UUID, p: Principal = Depends(sessions.principal)) -> dict[str, str]:
        with connection(settings.database_url, dictionary=True) as conn:
            row = conn.execute(
                "UPDATE editing_jobs SET status='approved' WHERE workspace_id=%s "
                "AND id=%s AND status IN ('review','approved') AND media IS NOT NULL RETURNING id",
                (p.workspace_id, job),
            ).fetchone()
        if not row:
            raise RegistryError(409, "editing_result_missing")
        return {"status": "approved"}

    return router
