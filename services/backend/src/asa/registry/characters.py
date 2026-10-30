"""Workspace-scoped character plans and immutable image versions."""

from contextlib import nullcontext
from typing import Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, Request, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from starlette.responses import StreamingResponse

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.history import HistoryRepository
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError
from asa.registry.sse import snapshot_stream
from asa.registry.work_progress import character_progress


class Character(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,39}$")
    name: str = Field(min_length=1, max_length=100)
    facts: str = Field(max_length=3000)
    appearance: str = Field(min_length=1, max_length=3000)
    proposed: str = Field(max_length=2000)
    scene_ids: str = Field(max_length=1000)
    image_prompt: str = Field(min_length=1, max_length=4000)


class CharacterPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    characters: list[Character] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def unique_ids(self) -> "CharacterPlan":
        if len({c.id for c in self.characters}) != len(self.characters):
            raise ValueError("duplicate_character_id")
        return self


class ImportPlan(BaseModel):
    id: UUID
    request_id: UUID
    source_version: int = Field(default=1, ge=1)
    name: str = Field(min_length=1, max_length=100)


class ImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    character: Character
    model: str = Field(min_length=1, max_length=100)
    change: str = Field(default="", max_length=3000)
    base_id: UUID | None = None


class Approval(BaseModel):
    expected: UUID | None = None
    expected_latest_version: int = Field(ge=1, strict=True)


class ItemScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    excluded: bool = Field(strict=True)
    expected: bool = Field(strict=True)


JOB_COLUMNS = (
    "id::text,project_id::text,character_id,version,model,character,change,"
    "base_id::text,status,error_code,usage,estimated_usd,created_at::text,"
    "started_at::text,finished_at::text"
)


class CharacterRepository(RegistryRepository):
    def project(self, project_id: UUID,
                connection: psycopg.Connection[dict[str, Any]] | None = None) -> dict[str, Any]:
        with nullcontext(connection) if connection is not None else self._connect() as conn:
            row = conn.execute(
                "SELECT id::text,request_id::text,source_version,name,characters,approved "
                "FROM character_projects WHERE workspace_id=%s AND id=%s",
                (self.workspace_id, project_id),
            ).fetchone()
            if not row:
                raise RegistryError(404, "character_project_not_found")
            row["jobs"] = conn.execute(
                f"SELECT {JOB_COLUMNS} FROM character_image_jobs "
                "WHERE workspace_id=%s AND project_id=%s ORDER BY created_at DESC",
                (self.workspace_id, project_id),
            ).fetchall()
            row["worker_online"] = bool(
                conn.execute(
                    "SELECT 1 FROM image_worker_status WHERE workspace_id=%s "
                    "AND seen_at>now()-interval '90 seconds'",
                    (self.workspace_id,),
                ).fetchone()
            )
            row["excluded"] = [
                item["item_id"]
                for item in conn.execute(
                    "SELECT item_id FROM work_item_preferences WHERE workspace_id=%s "
                    "AND request_id=%s AND source_version=%s "
                    "AND kind='character_images' AND excluded",
                    (self.workspace_id, row["request_id"], row["source_version"]),
                ).fetchall()
            ]
            reviewed = {
                item["item_id"]: item["reviewed_version"]
                for item in conn.execute(
                    "SELECT item_id,reviewed_version FROM work_item_preferences WHERE "
                    "workspace_id=%s "
                    "AND request_id=%s AND source_version=%s AND kind='character_images'",
                    (self.workspace_id, row["request_id"], row["source_version"]),
                ).fetchall()
            }
            row["work_progress"] = character_progress(
                row["source_version"],
                row["characters"],
                row["jobs"],
                row["approved"],
                set(row["excluded"]),
                reviewed,
            )
            return row

    def set_scope(self, project_id: UUID, character_id: str, body: ItemScope) -> dict[str, Any]:
        with self._connect() as conn:
            project = conn.execute(
                "SELECT * FROM character_projects WHERE workspace_id=%s AND id=%s FOR UPDATE",
                (self.workspace_id, project_id),
            ).fetchone()
            if not project or character_id not in {c["id"] for c in project["characters"]}:
                raise RegistryError(404, "character_project_not_found")
            key = (
                self.workspace_id,
                project["request_id"],
                project["source_version"],
                character_id,
            )
            current = conn.execute(
                "SELECT excluded FROM work_item_preferences WHERE workspace_id=%s AND "
                "request_id=%s "
                "AND source_version=%s AND kind='character_images' AND item_id=%s",
                key,
            ).fetchone()
            if bool(current and current["excluded"]) != body.expected:
                raise RegistryError(409, "work_scope_changed")
            if conn.execute(
                "SELECT 1 FROM character_image_jobs WHERE workspace_id=%s AND project_id=%s "
                "AND character_id=%s AND status IN ('queued','running')",
                (self.workspace_id, project_id, character_id),
            ).fetchone():
                raise RegistryError(409, "image_already_running")
            conn.execute(
                "INSERT INTO "
                "work_item_preferences(workspace_id,request_id,source_version,"
                "kind,item_id,excluded) "
                "VALUES (%s,%s,%s,'character_images',%s,%s) "
                "ON CONFLICT(workspace_id,request_id,source_version,kind,item_id) "
                "DO UPDATE SET excluded=EXCLUDED.excluded,updated_at=now()",
                (*key, body.excluded),
            )
        return self.project(project_id)

    def import_plan(self, body: ImportPlan) -> dict[str, Any]:
        HistoryRepository(self.dsn, self.workspace_id).detail(body.request_id)
        with self._connect() as conn:
            version = conn.execute(
                "SELECT answer FROM script_versions WHERE workspace_id=%s "
                "AND request_id=%s AND version=%s",
                (self.workspace_id, body.request_id, body.source_version),
            ).fetchone()
        if not version:
            raise RegistryError(409, "character_plan_not_ready")
        try:
            plan = CharacterPlan.model_validate(version["answer"])
        except ValidationError as exc:
            raise RegistryError(422, "character_plan_invalid") from exc
        with self._connect() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"character-import:{self.workspace_id}",),
            )
            existing = conn.execute(
                "SELECT id,request_id,source_version FROM character_projects WHERE workspace_id=%s "
                "AND ((request_id=%s AND source_version=%s) OR id=%s)",
                (self.workspace_id, body.request_id, body.source_version, body.id),
            ).fetchone()
            if existing:
                if (
                    existing["request_id"] != body.request_id
                    or existing["source_version"] != body.source_version
                ):
                    raise RegistryError(409, "image_id_conflict")
                return self.project(existing["id"], conn)
            conn.execute(
                "INSERT INTO character_projects"
                "(workspace_id,id,request_id,source_version,name,characters) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    self.workspace_id,
                    body.id,
                    body.request_id,
                    body.source_version,
                    body.name,
                    Jsonb(plan.model_dump()["characters"]),
                ),
            )
        return self.project(body.id)

    def enqueue(self, project_id: UUID, body: ImageRequest, settings: Settings) -> dict[str, Any]:
        if not settings.image_ai_enabled or not settings.ai_api_key.get_secret_value():
            raise RegistryError(409, "image_not_configured")
        if body.model not in settings.image_models:
            raise RegistryError(422, "image_model_not_allowed")
        with self._connect() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"image-queue:{self.workspace_id}",),
            )
            project = conn.execute(
                "SELECT * FROM character_projects WHERE workspace_id=%s AND id=%s FOR UPDATE",
                (self.workspace_id, project_id),
            ).fetchone()
            if not project or body.character.id not in {c["id"] for c in project["characters"]}:
                raise RegistryError(404, "character_project_not_found")
            existing = conn.execute(
                f"SELECT {JOB_COLUMNS} FROM character_image_jobs WHERE workspace_id=%s AND id=%s",
                (self.workspace_id, body.id),
            ).fetchone()
            if existing:
                if (
                    existing["project_id"] != str(project_id)
                    or existing["character"] != body.character.model_dump()
                    or existing["change"] != body.change
                    or existing["model"] != body.model
                    or existing["base_id"] != (str(body.base_id) if body.base_id else None)
                ):
                    raise RegistryError(409, "image_id_conflict")
                return existing
            if conn.execute(
                "SELECT 1 FROM work_item_preferences WHERE workspace_id=%s AND request_id=%s "
                "AND source_version=%s AND kind='character_images' AND item_id=%s AND excluded",
                (
                    self.workspace_id,
                    project["request_id"],
                    project["source_version"],
                    body.character.id,
                ),
            ).fetchone():
                raise RegistryError(409, "work_item_excluded")
            active = conn.execute(
                "SELECT 1 FROM character_image_jobs WHERE workspace_id=%s "
                "AND project_id=%s AND character_id=%s "
                "AND status IN ('queued','running')",
                (self.workspace_id, project_id, body.character.id),
            ).fetchone()
            if active:
                raise RegistryError(409, "image_already_running")
            count = conn.execute(
                "SELECT count(*) AS n FROM character_image_jobs "
                "WHERE workspace_id=%s AND created_at>now()-interval '24 hours'",
                (self.workspace_id,),
            ).fetchone()
            if count and count["n"] >= settings.image_daily_calls:
                raise RegistryError(429, "image_daily_limit")
            if body.base_id:
                base = conn.execute(
                    "SELECT 1 FROM character_image_jobs WHERE workspace_id=%s "
                    "AND id=%s AND project_id=%s AND character_id=%s "
                    "AND status='succeeded' AND image IS NOT NULL",
                    (self.workspace_id, body.base_id, project_id, body.character.id),
                ).fetchone()
                if not base:
                    raise RegistryError(422, "image_reference_invalid")
            elif body.change.strip():
                raise RegistryError(422, "image_reference_required")
            version = conn.execute(
                "SELECT COALESCE(max(version),0)+1 AS n "
                "FROM character_image_jobs WHERE workspace_id=%s "
                "AND project_id=%s AND character_id=%s",
                (self.workspace_id, project_id, body.character.id),
            ).fetchone()
            assert version
            row = conn.execute(
                "INSERT INTO character_image_jobs(workspace_id,id,project_id,character_id,"
                "version,model,character,change,base_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                f"RETURNING {JOB_COLUMNS}",
                (
                    self.workspace_id,
                    body.id,
                    project_id,
                    body.character.id,
                    version["n"],
                    body.model,
                    Jsonb(body.character.model_dump()),
                    body.change,
                    body.base_id,
                ),
            ).fetchone()
            assert row
            return row

    def approve(self, job_id: UUID, expected: UUID | None, expected_latest_version: int) -> None:
        with self._connect() as conn:
            job = conn.execute(
                "SELECT * FROM character_image_jobs WHERE workspace_id=%s "
                "AND id=%s AND status='succeeded'",
                (self.workspace_id, job_id),
            ).fetchone()
            if not job:
                raise RegistryError(404, "image_not_found")
            project = conn.execute(
                "SELECT approved,request_id,source_version FROM character_projects WHERE "
                "workspace_id=%s "
                "AND id=%s FOR UPDATE",
                (self.workspace_id, job["project_id"]),
            ).fetchone()
            assert project
            latest = conn.execute(
                "SELECT max(version) AS version FROM character_image_jobs "
                "WHERE workspace_id=%s AND project_id=%s AND character_id=%s",
                (self.workspace_id, job["project_id"], job["character_id"]),
            ).fetchone()
            if not latest or latest["version"] != expected_latest_version:
                raise RegistryError(409, "image_review_changed")
            if conn.execute(
                "SELECT 1 FROM work_item_preferences WHERE workspace_id=%s AND request_id=%s "
                "AND source_version=%s AND kind='character_images' AND item_id=%s AND excluded",
                (
                    self.workspace_id,
                    project["request_id"],
                    project["source_version"],
                    job["character_id"],
                ),
            ).fetchone():
                raise RegistryError(409, "work_item_excluded")
            if conn.execute(
                "SELECT 1 FROM character_image_jobs WHERE workspace_id=%s AND project_id=%s "
                "AND character_id=%s AND status IN ('queued','running')",
                (self.workspace_id, job["project_id"], job["character_id"]),
            ).fetchone():
                raise RegistryError(409, "image_already_running")
            approved = project["approved"]
            current = approved.get(job["character_id"])
            if current != (str(expected) if expected else None):
                raise RegistryError(409, "image_approval_changed")
            approved[job["character_id"]] = str(job_id)
            conn.execute(
                "INSERT INTO "
                "work_item_preferences(workspace_id,request_id,source_version,"
                "kind,item_id,reviewed_version) "
                "SELECT %s,%s,%s,'character_images',%s,COALESCE(max(version),0) "
                "FROM character_image_jobs WHERE workspace_id=%s AND project_id=%s AND "
                "character_id=%s "
                "ON CONFLICT(workspace_id,request_id,source_version,kind,item_id) "
                "DO UPDATE SET reviewed_version=EXCLUDED.reviewed_version,updated_at=now()",
                (
                    self.workspace_id,
                    project["request_id"],
                    project["source_version"],
                    job["character_id"],
                    self.workspace_id,
                    job["project_id"],
                    job["character_id"],
                ),
            )
            conn.execute(
                "UPDATE character_projects SET approved=%s WHERE workspace_id=%s AND id=%s",
                (Jsonb(approved), self.workspace_id, job["project_id"]),
            )


def character_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/characters")

    def repo(p: Principal = Depends(sessions.principal)) -> CharacterRepository:
        return CharacterRepository(settings.database_url, p.workspace_id)

    @router.get("/options")
    def options(r: CharacterRepository = Depends(repo)) -> dict[str, Any]:
        # Only agents with this explicit output contract can feed image cards.
        agents = [
            t
            for t in r.tools()
            if t["kind"] == "agent"
            and "characters" in t.get("output_schema", {}).get("properties", {})
        ]
        return {
            "models": settings.image_models,
            "enabled": settings.image_ai_enabled,
            "agents": agents,
        }

    @router.get("/sources")
    def sources(r: CharacterRepository = Depends(repo)) -> list[dict[str, Any]]:
        with r._connect() as conn:
            return conn.execute(
                "SELECT id::text,definition->>'name' AS name,steps "
                "FROM automation_runs WHERE workspace_id=%s AND status='succeeded' "
                "ORDER BY created_at DESC LIMIT 20",
                (r.workspace_id,),
            ).fetchall()

    @router.get("/projects")
    def projects(r: CharacterRepository = Depends(repo)) -> list[dict[str, Any]]:
        with r._connect() as conn:
            return conn.execute(
                "SELECT id::text,request_id::text,source_version,name,created_at::text "
                "FROM character_projects "
                "WHERE workspace_id=%s ORDER BY created_at DESC LIMIT 100",
                (r.workspace_id,),
            ).fetchall()

    @router.post("/projects")
    def create(body: ImportPlan, r: CharacterRepository = Depends(repo)) -> dict[str, Any]:
        return r.import_plan(body)

    @router.get("/projects/{project_id}")
    def detail(project_id: UUID, r: CharacterRepository = Depends(repo)) -> dict[str, Any]:
        return r.project(project_id)

    @router.get("/projects/{project_id}/events")
    def events(project_id: UUID, request: Request,
               r: CharacterRepository = Depends(repo)) -> StreamingResponse:
        def load() -> dict[str, Any]:
            sessions.principal(request)
            return r.project(project_id)
        return snapshot_stream(request, load, r.dsn, r.workspace_id)

    @router.post("/projects/{project_id}/images")
    def image(
        project_id: UUID, body: ImageRequest, r: CharacterRepository = Depends(repo)
    ) -> dict[str, Any]:
        return r.enqueue(project_id, body, settings)

    @router.post("/projects/{project_id}/characters/{character_id}/scope")
    def scope(
        project_id: UUID, character_id: str, body: ItemScope, r: CharacterRepository = Depends(repo)
    ) -> dict[str, Any]:
        return r.set_scope(project_id, character_id, body)

    @router.post("/images/{job_id}/approve")
    def approve(
        job_id: UUID, body: Approval, r: CharacterRepository = Depends(repo)
    ) -> dict[str, bool]:
        r.approve(job_id, body.expected, body.expected_latest_version)
        return {"ok": True}

    @router.get("/images/{job_id}/asset")
    def asset(job_id: UUID, r: CharacterRepository = Depends(repo)) -> Response:
        with r._connect() as conn:
            row = conn.execute(
                "SELECT image FROM character_image_jobs WHERE workspace_id=%s "
                "AND id=%s AND status='succeeded'",
                (r.workspace_id, job_id),
            ).fetchone()
        if not row or not row["image"]:
            raise RegistryError(404, "image_not_found")
        return Response(
            bytes(row["image"]),
            media_type="image/png",
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
        )

    return router
