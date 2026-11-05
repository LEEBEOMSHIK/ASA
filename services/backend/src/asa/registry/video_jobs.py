"""Queue clips from a saved agent answer; the browser submits only selected clip IDs."""

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, ValidationError

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError
from asa.registry.video_planning import prepare
from asa.video_contracts import VideoPreparation


class ClipSelection(BaseModel):
    clip_ids: list[str] = Field(min_length=1, max_length=100)


def video_job_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/video-clips")
    path = "/{request_id}/{version}"

    @router.get(path)
    def jobs(
        request_id: UUID, version: int, principal: Principal = Depends(sessions.principal)
    ) -> dict[str, Any]:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            rows = conn.execute(
                "SELECT id,clip_id,status,error_code,created_at,updated_at, "
                "(model_snapshot->>'usd_per_second')::numeric * "
                "(generation_input->>'duration_seconds')::integer AS estimate FROM video_clip_jobs "
                "WHERE workspace_id=%s AND request_id=%s AND answer_version=%s ORDER BY created_at",
                (repo.workspace_id, request_id, version),
            ).fetchall()
            online = (
                conn.execute(
                    "SELECT 1 FROM pg_stat_activity WHERE datname=current_database() "
                    "AND application_name=%s LIMIT 1",
                    (f"asa-video-{repo.workspace_id}",),
                ).fetchone()
                is not None
            )
        return {
            "jobs": rows,
            "worker_online": online,
            "rates": {
                key: model.usd_per_second
                for key, model in settings.video_model_profiles.items()
                if model.enabled
            },
            "enabled": settings.video_ai_enabled
            and bool(settings.runway_api_key.get_secret_value()),
        }

    @router.post(path)
    def enqueue(
        request_id: UUID,
        version: int,
        body: ClipSelection,
        principal: Principal = Depends(sessions.principal),
    ) -> dict[str, int]:
        if not settings.video_ai_enabled or not settings.runway_api_key.get_secret_value():
            raise RegistryError(409, "video_generation_disabled")
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            row = conn.execute(
                "SELECT v.answer,r.input FROM script_versions v JOIN customer_requests r "
                "ON r.workspace_id=v.workspace_id AND r.id=v.request_id "
                "WHERE v.workspace_id=%s AND v.request_id=%s AND v.version=%s",
                (repo.workspace_id, request_id, version),
            ).fetchone()
            if not row:
                raise RegistryError(404, "video_answer_missing")
            try:
                plan = VideoPreparation.model_validate(row["answer"])
            except ValidationError as exc:
                raise RegistryError(422, "video_plan_invalid") from exc
            inputs = row["input"]
            if plan.model_key != inputs.get("video_model"):
                raise RegistryError(422, "video_model_mismatch")
            selection = inputs.get("scene_images")
            if (
                not isinstance(selection, dict)
                or selection.get("format") != "asa_scene_selection_v1"
            ):
                raise RegistryError(422, "video_scene_reference_mismatch")
            source_images = {s["image_id"] for s in selection["scenes"]}
            if any(str(c.image_id) not in source_images for c in plan.clips):
                raise RegistryError(422, "video_scene_reference_mismatch")
            prepared = prepare(repo, settings, plan, selection)
            model = prepared["model_snapshot"]
            if (
                model["provider"] != "runway"
                or model["model"] != "gen4.5"
                or plan.audio
                or model["resolution"] != "720p"
                or plan.aspect_ratio not in {"9:16", "16:9"}
            ):
                raise RegistryError(422, "video_model_unavailable")
            selected = set(body.clip_ids)
            if selected - {c.clip_id for c in plan.clips}:
                raise RegistryError(422, "video_plan_invalid")
            count = 0
            for clip in prepared["clips"]:
                if clip["clip_id"] not in selected:
                    continue
                count += conn.execute(
                    "INSERT INTO video_clip_jobs(workspace_id,id,request_id,answer_version,"
                    "clip_id,model_snapshot,generation_input,status) VALUES "
                    "(%s,%s,%s,%s,%s,%s,%s,'queued') ON CONFLICT DO NOTHING",
                    (
                        repo.workspace_id,
                        uuid4(),
                        request_id,
                        version,
                        clip["clip_id"],
                        Jsonb(model),
                        Jsonb(clip["generation_input"]),
                    ),
                ).rowcount
            conn.execute("SELECT pg_notify('asa_video_jobs',%s)", (str(repo.workspace_id),))
        return {"queued": count}

    @router.post(path + "/approve")
    def approve(
        request_id: UUID,
        version: int,
        body: ClipSelection,
        principal: Principal = Depends(sessions.principal),
    ) -> dict[str, int]:
        selected = set(body.clip_ids)
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            result = conn.execute(
                "UPDATE video_clip_jobs SET status='approved',updated_at=now() "
                "WHERE workspace_id=%s AND request_id=%s AND answer_version=%s "
                "AND clip_id=ANY(%s) AND status IN ('review','approved') AND video IS NOT NULL",
                (repo.workspace_id, request_id, version, list(selected)),
            )
            if result.rowcount != len(selected):
                raise RegistryError(409, "video_review_changed")
        return {"approved": len(selected)}

    @router.get("/asset/{job_id}/video")
    def asset(job_id: UUID, principal: Principal = Depends(sessions.principal)) -> Response:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            row = conn.execute(
                "SELECT video FROM video_clip_jobs WHERE workspace_id=%s "
                "AND id=%s AND status IN ('review','approved')",
                (repo.workspace_id, job_id),
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT video FROM retained_work_videos WHERE workspace_id=%s AND id=%s",
                    (repo.workspace_id, job_id),
                ).fetchone()
        if not row or not row["video"]:
            raise RegistryError(404, "video_asset_missing")
        return Response(content=bytes(row["video"]), media_type="video/mp4")

    return router
