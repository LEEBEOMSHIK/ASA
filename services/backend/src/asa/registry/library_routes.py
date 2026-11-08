from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry import library
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError


class WorkEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    revision: int = Field(default=0, ge=0, strict=True)


class Assignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=100)
    work_id: UUID | None
    revision: int = Field(ge=0, strict=True)


def library_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/library")

    def repo(p: Principal) -> RegistryRepository:
        return RegistryRepository(settings.database_url, p.workspace_id)

    @router.get("")
    def listing(
        p: Principal = Depends(sessions.principal),
        kind: Literal[
            "",
            "script",
            "scene",
            "character",
            "image",
            "audio",
            "video",
            "prompt",
            "document",
            "character_image",
            "scene_image",
            "reference_image",
            "speech",
            "music",
        ] = "",
        q: str = Query(default="", max_length=200),
        work: str = Query(default="", max_length=100),
        state: str = Query(default="", max_length=20),
        offset: int = Query(default=0, ge=0, le=1000000),
        limit: int = Query(default=24, ge=1, le=48),
    ) -> dict[str, Any]:
        data = library.index(repo(p), p.user_id)
        data["items"] = library.visible_items(data["items"])
        rows = [
            i
            for i in data["items"]
            if (
                not kind
                or i["category"] == kind
                or (kind in {"image", "audio"} and i["kind"] == kind)
            )
            and (not state or i["status"] == state)
            and (not work or (not i["work_id"] if work == "unassigned" else i["work_id"] == work))
            and (
                not q
                or q.casefold()
                in " ".join(
                    str(i.get(k) or "")
                    for k in ("title", "source_name", "work_name", "agent_name", "id")
                ).casefold()
            )
        ]
        rows.sort(key=lambda i: (i["created_at"], i["version"], i["id"]), reverse=True)
        counts = {
            k: sum(
                i["category"] == k or (k in {"image", "audio"} and i["kind"] == k)
                for i in data["items"]
                if not work or (not i["work_id"] if work == "unassigned" else i["work_id"] == work)
            )
            for k in (
                "script",
                "scene",
                "character",
                "character_image",
                "scene_image",
                "reference_image",
                "speech",
                "music",
                "image",
                "audio",
                "video",
                "prompt",
                "document",
            )
        }
        return {
            "items": rows[offset : offset + limit],
            "total": len(rows),
            "has_more": len(rows) > offset + limit,
            "works": data["works"],
            "counts": counts,
            "unassigned": sum(not i["work_id"] for i in data["items"]),
        }

    @router.get("/items/{item_id}")
    def item(item_id: str, p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        return library.detail(repo(p), p.user_id, item_id)

    @router.get("/references/{source_id}/media")
    def reference_media(source_id: UUID, p: Principal = Depends(sessions.principal)) -> Response:
        with repo(p)._connect() as conn:
            row = conn.execute(
                "SELECT video FROM video_references WHERE workspace_id=%s AND id=%s",
                (p.workspace_id, source_id),
            ).fetchone()
        if not row or not row["video"]:
            raise RegistryError(404, "library_item_missing")
        raw = bytes(row["video"])
        return Response(
            raw,
            media_type="video/webm" if raw[:4] == b"\x1aE\xdf\xa3" else "video/mp4",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @router.post("/works")
    def create(body: WorkEdit, p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        with repo(p)._connect() as conn:
            row = conn.execute(
                "INSERT INTO library_works(workspace_id,id,name) VALUES (%s,%s,%s) "
                "RETURNING id::text,name,revision",
                (p.workspace_id, uuid4(), body.name),
            ).fetchone()
        assert row is not None
        return dict(row)

    @router.put("/works/{work_id}")
    def rename(
        work_id: UUID, body: WorkEdit, p: Principal = Depends(sessions.principal)
    ) -> dict[str, Any]:
        with repo(p)._connect() as conn:
            row = conn.execute(
                "UPDATE library_works SET name=%s,revision=revision+1 "
                "WHERE workspace_id=%s AND id=%s AND revision=%s "
                "RETURNING id::text,name,revision",
                (body.name, p.workspace_id, work_id, body.revision),
            ).fetchone()
        if not row:
            raise RegistryError(409, "library_changed")
        return dict(row)

    @router.put("/assignment")
    def assign(body: Assignment, p: Principal = Depends(sessions.principal)) -> dict[str, int]:
        data = library.index(repo(p), p.user_id)
        if not any(i["subject"] == body.subject for i in data["items"]):
            raise RegistryError(404, "library_item_missing")
        target = next((w for w in data["works"] if w["id"] == str(body.work_id)), None)
        if body.work_id and target is None:
            raise RegistryError(404, "library_work_missing")
        with repo(p)._connect() as conn:
            conn.execute(
                "SELECT id FROM registry_workspaces WHERE id=%s FOR UPDATE", (p.workspace_id,)
            )
            if target:
                conn.execute(
                    "INSERT INTO library_works(workspace_id,id,name) VALUES (%s,%s,%s) "
                    "ON CONFLICT(workspace_id,id) DO NOTHING",
                    (p.workspace_id, body.work_id, target["name"]),
                )
            old = conn.execute(
                "SELECT revision FROM library_assignments WHERE workspace_id=%s AND subject=%s",
                (p.workspace_id, body.subject),
            ).fetchone()
            if (old["revision"] if old else 0) != body.revision:
                raise RegistryError(409, "library_changed")
            conn.execute(
                "INSERT INTO library_assignments(workspace_id,subject,work_id,revision) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT(workspace_id,subject) DO UPDATE "
                "SET work_id=excluded.work_id,revision=excluded.revision",
                (p.workspace_id, body.subject, body.work_id, body.revision + 1),
            )
        return {"revision": body.revision + 1}

    return router
