"""Queue clips from a saved agent answer; the browser submits only selected clip IDs."""

import subprocess
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
from asa.video_continuity import approved_source, last_frame, reference_valid, source_video
from asa.video_contracts import VideoPreparation
from asa.video_providers import connection_state, endpoint, supported_model, validate_input


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
            from asa.registry.audio_service import load as load_audio
            from asa.voice_directions import clip_audio_prompt, validate_timeline

            current_audio = load_audio(conn, repo.workspace_id, request_id, version)
            voice_settings = current_audio['settings']
            delivery: dict[str, Any] = {'mode': voice_settings.delivery_mode, 'clips': [],
                                        'speakers': [], 'error': None}
            if voice_settings.delivery_mode == 'video':
                model_key = current_audio['answer'].get('model_key')
                selected_model = settings.video_model_profiles.get(model_key)
                delivery['supports_audio'] = bool(selected_model and selected_model.supports_audio)
                delivery['speakers'] = [
                    {'id': s.id, 'name': s.name, 'role': s.role, 'enabled': s.video_enabled,
                     'instructions': s.voice.instructions, 'language': s.voice.language,
                     'speed': s.voice.speed} for s in voice_settings.speakers]
                try:
                    validate_timeline(voice_settings,
                                      current_audio['answer']['clips'][-1]['source_end_seconds'])
                except RegistryError as exc:
                    delivery['error'] = exc.code
                for clip in current_audio['answer'].get('clips', []):
                    try:
                        prompt = clip_audio_prompt(voice_settings, clip['source_start_seconds'],
                                                   clip['source_end_seconds'])
                        if prompt and not delivery['supports_audio']:
                            delivery['error'] = 'video_audio_unsupported'
                        delivery['clips'].append({'clip_id': clip['clip_id'], 'prompt': prompt})
                    except RegistryError as exc:
                        delivery['error'] = exc.code
            rows = conn.execute(
                "SELECT id,clip_id,status,error_code,created_at,updated_at, "
                "request_id,answer_version,generation_input, "
                "encode(sha256(video),'hex') AS video_sha256, "
                "(model_snapshot->>'usd_per_second')::numeric * "
                "(generation_input->>'duration_seconds')::integer AS estimate FROM video_clip_jobs "
                "WHERE workspace_id=%s AND request_id=%s AND answer_version=%s ORDER BY created_at",
                (repo.workspace_id, request_id, version),
            ).fetchall()
            by_clip = {row["clip_id"]: row for row in rows}
            for row in rows:
                row["reference_valid"] = reference_valid(row, by_clip)
            for row in rows:
                row['voice_direction_prompt'] = row['generation_input'].get(
                    'voice_direction_prompt')
                row.pop("generation_input")
                row.pop("video_sha256")
            online = (
                conn.execute(
                    "SELECT 1 FROM pg_stat_activity WHERE datname=current_database() "
                    "AND application_name=%s LIMIT 1",
                    (f"asa-video-{repo.workspace_id}",),
                ).fetchone()
                is not None
            )
        return {
            'voice_delivery': delivery,
            "jobs": rows,
            "worker_online": online,
            "rates": {
                key: model.usd_per_second
                for key, model in settings.video_model_profiles.items()
                if model.enabled
            },
            "enabled": settings.video_ai_enabled
            and any(connection_state(settings, m.provider) == "configured"
                    for m in settings.video_model_profiles.values() if m.enabled),
            "available_models": [key for key, m in settings.video_model_profiles.items()
                                 if m.enabled and supported_model(m.model_dump())
                                 and settings.video_ai_enabled
                                 and connection_state(settings, m.provider) == "configured"],
        }

    @router.post(path)
    def enqueue(
        request_id: UUID,
        version: int,
        body: ClipSelection,
        principal: Principal = Depends(sessions.principal),
    ) -> dict[str, int]:
        if not settings.video_ai_enabled:
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
            from asa.registry.audio_service import load as load_audio
            audio_settings = load_audio(conn, repo.workspace_id, request_id, version,
                                        lock=True)["settings"]
            if audio_settings.enabled and audio_settings.delivery_mode != 'video':
                plan.audio = False
            from asa.voice_directions import answer_contract

            contract = answer_contract(conn, repo.workspace_id, request_id, version)
            inputs = contract.get('original_request', row['input']) if contract else row['input']
            from asa.registry import art_styles

            visual_style = contract.get('work_visual_style') if contract else None
            current_style = art_styles.resolve(conn, repo.workspace_id, inputs, request_id)
            art_styles.check_plan_style(visual_style, current_style)
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
            prepared = prepare(repo, settings, plan, selection,
                               audio_settings if audio_settings.delivery_mode == 'video' else None,
                               visual_style)
            model = prepared["model_snapshot"]
            if not supported_model(model):
                raise RegistryError(422, "video_model_unavailable")
            if connection_state(settings, model["provider"]) != "configured":
                raise RegistryError(409, "video_generation_disabled")
            model["provider_endpoint"] = endpoint(settings, model["provider"])
            for clip in prepared["clips"]:
                try:
                    validate_input(model, clip["generation_input"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise RegistryError(422, "video_model_unavailable") from exc
            selected = set(body.clip_ids)
            if selected - {c.clip_id for c in plan.clips}:
                raise RegistryError(422, "video_plan_invalid")
            count = 0
            for clip in prepared["clips"]:
                if clip["clip_id"] not in selected:
                    continue
                spec = clip["generation_input"]
                if spec.get("connection_type") == "continue":
                    try:
                        spec.update(approved_source(conn, repo.workspace_id, request_id,
                                                    version, spec["previous_clip_id"]))
                    except ValueError as exc:
                        raise RegistryError(409, str(exc)) from exc
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
            candidates = conn.execute(
                "SELECT * FROM video_clip_jobs WHERE workspace_id=%s AND request_id=%s "
                "AND answer_version=%s AND clip_id=ANY(%s)",
                (repo.workspace_id, request_id, version, list(selected)),
            ).fetchall()
            for candidate in candidates:
                if candidate["generation_input"].get("connection_type") == "continue":
                    try:
                        source_video(conn, repo.workspace_id, candidate)
                    except ValueError as exc:
                        raise RegistryError(409, str(exc)) from exc
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

    @router.get("/asset/{job_id}/last-frame")
    def frame(job_id: UUID, principal: Principal = Depends(sessions.principal)) -> Response:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            row = conn.execute(
                "SELECT video FROM video_clip_jobs WHERE workspace_id=%s AND id=%s "
                "AND status='approved'", (repo.workspace_id, job_id),
            ).fetchone()
        if not row or not row["video"]:
            raise RegistryError(404, "video_asset_missing")
        try:
            png = last_frame(bytes(row["video"]), settings.ffmpeg_path)
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            raise RegistryError(409, "video_frame_extraction_failed") from exc
        return Response(content=png, media_type="image/png")

    return router
