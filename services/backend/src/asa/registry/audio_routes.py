import base64
import hashlib
import subprocess
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Response
from psycopg.types.json import Jsonb
from pydantic import Field, ValidationError

from asa.audio_contracts import AudioSettings, Strict, fingerprint
from asa.audio_media import normalize_audio
from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry import audio_service as service
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError


class Edit(Strict):
    revision: int = Field(ge=0, strict=True)
    settings: AudioSettings


class Generate(Strict):
    id: UUID
    revision: int = Field(ge=0, strict=True)
    cue_id: str = Field(default="", max_length=64)
    remove_original: bool = False


class Upload(Strict):
    name: str = Field(min_length=1, max_length=150)
    data: str = Field(min_length=1, max_length=22_369_624)


def audio_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/audio")
    path = "/work/{request_id}/{version}"

    def repo(p: Principal) -> RegistryRepository:
        return RegistryRepository(settings.database_url, p.workspace_id)

    @router.get("/catalog")
    def catalog(p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        return {
            "models": {
                key: value.model_dump()
                for key, value in settings.audio_model_profiles.items()
                if value.enabled
            },
            "generation_enabled": bool(
                settings.audio_ai_enabled and settings.audio_api_key.get_secret_value()
            ),
            "ai_voice_notice": "AI로 생성하는 목소리입니다.",
        }

    @router.get("/sources")
    def sources(p: Principal = Depends(sessions.principal)) -> list[dict[str, Any]]:
        with repo(p)._connect() as conn:
            return list(
                conn.execute(
                    "SELECT s.request_id,s.version,s.answer->'characters' "
                    "AS characters,r.created_at,v.definition->>'name' AS agent_name "
                    "FROM script_versions s JOIN customer_requests r "
                    "ON r.workspace_id=s.workspace_id "
                    "AND r.id=s.request_id JOIN registry_versions v "
                    "ON v.workspace_id=r.workspace_id "
                    "AND v.agent_id=r.agent_id AND v.version=r.version WHERE s.workspace_id=%s "
                    "AND jsonb_typeof(s.answer->'characters')='array' "
                    "ORDER BY r.created_at DESC,s.version DESC LIMIT 100",
                    (p.workspace_id,),
                ).fetchall()
            )

    @router.get(path)
    def get(
        request_id: UUID, version: int, p: Principal = Depends(sessions.principal)
    ) -> dict[str, Any]:
        with repo(p)._connect() as conn:
            current = service.load(conn, p.workspace_id, request_id, version)
            jobs = conn.execute(
                "SELECT id,kind,cue_id,fingerprint,status,duration,transcript,"
                "error_code,created_at,input "
                "FROM audio_jobs WHERE workspace_id=%s AND request_id=%s AND answer_version=%s "
                "ORDER BY created_at DESC",
                (p.workspace_id, request_id, version),
            ).fetchall()
            for job in jobs:
                try:
                    if job["kind"] == "speech":
                        key = service.speech_key(
                            service.speech_spec(settings, current["settings"], job["cue_id"])
                        )
                    else:
                        key = fingerprint(
                            service.composition_spec(
                                conn,
                                settings,
                                p.workspace_id,
                                request_id,
                                version,
                                current,
                                job["input"]["remove_original"],
                            )
                        )
                    job["current"] = key == job["fingerprint"]
                except (RegistryError, ValueError):
                    job["current"] = False
            for job in jobs:
                job.pop("input", None)
            return {
                "settings": current["settings"].model_dump(mode="json"),
                "revision": current["revision"],
                "jobs": jobs,
            }

    @router.put(path)
    def save(
        request_id: UUID, version: int, body: Edit, p: Principal = Depends(sessions.principal)
    ) -> dict[str, Any]:
        with repo(p)._connect() as conn:
            current = service.load(conn, p.workspace_id, request_id, version, lock=True)
            if current["revision"] != body.revision:
                raise RegistryError(409, "audio_settings_changed")
            service.validate_assets(conn, p.workspace_id, body.settings)
            for speaker in body.settings.speakers:
                model = settings.audio_model_profiles.get(speaker.voice.model_key)
                if not model or not model.enabled or speaker.voice.voice not in model.voices:
                    raise RegistryError(422, "audio_voice_unavailable")
            for cue in body.settings.cues:
                service.speech_spec(settings, body.settings, cue.id)
            conn.execute(
                "INSERT INTO audio_settings VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT(workspace_id,request_id,answer_version) DO UPDATE SET "
                "revision=excluded.revision,settings=excluded.settings",
                (
                    p.workspace_id,
                    request_id,
                    version,
                    body.revision + 1,
                    Jsonb(body.settings.model_dump(mode="json")),
                ),
            )
        return get(request_id, version, p)

    @router.get("/assets")
    def assets(p: Principal = Depends(sessions.principal)) -> list[dict[str, Any]]:
        with repo(p)._connect() as conn:
            return list(
                conn.execute(
                    "SELECT id,name,duration FROM audio_assets "
                    "WHERE workspace_id=%s ORDER BY created_at DESC LIMIT 100",
                    (p.workspace_id,),
                ).fetchall()
            )

    @router.post("/assets")
    def upload(body: Upload, p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        try:
            data, duration = normalize_audio(
                base64.b64decode(body.data, validate=True), settings.ffmpeg_path
            )
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            raise RegistryError(422, "audio_upload_invalid") from exc
        asset_id = uuid4()
        with repo(p)._connect() as conn:
            conn.execute(
                "INSERT INTO audio_assets(workspace_id,id,name,data,duration,sha256) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    p.workspace_id,
                    asset_id,
                    body.name,
                    data,
                    duration,
                    hashlib.sha256(data).hexdigest(),
                ),
            )
        return {"id": str(asset_id), "name": body.name, "duration": duration}

    @router.get("/assets/{asset_id}/media")
    def asset_media(asset_id: UUID, p: Principal = Depends(sessions.principal)) -> Response:
        with repo(p)._connect() as conn:
            row = conn.execute(
                "SELECT data FROM audio_assets WHERE workspace_id=%s AND id=%s",
                (p.workspace_id, asset_id),
            ).fetchone()
        if not row:
            raise RegistryError(404, "audio_asset_missing")
        return Response(
            bytes(row["data"]), media_type="audio/wav", headers={"Cache-Control": "no-store"}
        )

    def enqueue(
        kind: str, request_id: UUID, version: int, body: Generate, p: Principal
    ) -> dict[str, Any]:
        with repo(p)._connect() as conn:
            current = service.load(conn, p.workspace_id, request_id, version, lock=True)
            if current["revision"] != body.revision:
                raise RegistryError(409, "audio_settings_changed")
            if not current["settings"].enabled:
                raise RegistryError(409, "audio_disabled")
            if kind == "speech":
                if not settings.audio_ai_enabled or not settings.audio_api_key.get_secret_value():
                    raise RegistryError(409, "audio_generation_disabled")
                spec = service.speech_spec(settings, current["settings"], body.cue_id)
                key = service.speech_key(spec)
            else:
                try:
                    spec = service.composition_spec(
                        conn,
                        settings,
                        p.workspace_id,
                        request_id,
                        version,
                        current,
                        body.remove_original,
                    )
                except (ValueError, ValidationError) as exc:
                    raise RegistryError(422, "audio_timeline_invalid") from exc
                key = fingerprint(spec)
            prior = conn.execute(
                "SELECT id,status,fingerprint,request_id,answer_version,kind "
                "FROM audio_jobs WHERE workspace_id=%s AND id=%s",
                (p.workspace_id, body.id),
            ).fetchone()
            if prior and (
                prior["fingerprint"] != key
                or prior["request_id"] != request_id
                or prior["answer_version"] != version
                or prior["kind"] != kind
            ):
                raise RegistryError(409, "audio_operation_conflict")
            if prior:
                return {"id": prior["id"], "status": prior["status"]}
            conn.execute(
                "INSERT INTO audio_jobs(workspace_id,id,request_id,answer_version,kind,"
                "cue_id,fingerprint,input,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'queued') "
                "ON CONFLICT DO NOTHING",
                (p.workspace_id, body.id, request_id, version, kind, body.cue_id, key, Jsonb(spec)),
            )
            row = conn.execute(
                "SELECT id,status FROM audio_jobs WHERE workspace_id=%s "
                "AND request_id=%s AND answer_version=%s AND kind=%s AND fingerprint=%s "
                "ORDER BY created_at DESC LIMIT 1",
                (p.workspace_id, request_id, version, kind, key),
            ).fetchone()
            if not row:
                raise RegistryError(409, "audio_operation_conflict")
            return dict(row)

    @router.post(path + "/speech")
    def speech(
        request_id: UUID, version: int, body: Generate, p: Principal = Depends(sessions.principal)
    ) -> dict[str, Any]:
        return enqueue("speech", request_id, version, body, p)

    @router.post(path + "/compose")
    def compose(
        request_id: UUID, version: int, body: Generate, p: Principal = Depends(sessions.principal)
    ) -> dict[str, Any]:
        return enqueue("compose", request_id, version, body, p)

    @router.post("/jobs/{job_id}/approve")
    def approve(job_id: UUID, p: Principal = Depends(sessions.principal)) -> dict[str, str]:
        with repo(p)._connect() as conn:
            job = conn.execute(
                "SELECT * FROM audio_jobs WHERE workspace_id=%s AND id=%s", (p.workspace_id, job_id)
            ).fetchone()
            if not job:
                raise RegistryError(404, "audio_job_missing")
            current = service.load(
                conn, p.workspace_id, job["request_id"], job["answer_version"], lock=True
            )
            if job["status"] not in {"review", "approved"} or not job["media"]:
                raise RegistryError(409, "audio_not_ready")
            try:
                if job["kind"] == "speech":
                    service.approve_speech(settings, current["settings"], job)
                else:
                    spec = service.composition_spec(
                        conn,
                        settings,
                        p.workspace_id,
                        job["request_id"],
                        job["answer_version"],
                        current,
                        job["input"]["remove_original"],
                    )
                    if fingerprint(spec) != job["fingerprint"]:
                        raise RegistryError(409, "audio_source_changed")
            except ValueError as exc:
                raise RegistryError(409, str(exc)) from exc
            conn.execute(
                "UPDATE audio_jobs SET status='approved',updated_at=now() "
                "WHERE workspace_id=%s AND id=%s",
                (p.workspace_id, job_id),
            )
        return {"status": "approved"}

    @router.get("/jobs/{job_id}/media")
    def media(job_id: UUID, p: Principal = Depends(sessions.principal)) -> Response:
        with repo(p)._connect() as conn:
            row = conn.execute(
                "SELECT kind,media FROM audio_jobs WHERE workspace_id=%s AND id=%s "
                "AND status IN ('review','approved')",
                (p.workspace_id, job_id),
            ).fetchone()
        if not row or not row["media"]:
            raise RegistryError(404, "audio_job_missing")
        return Response(
            bytes(row["media"]),
            media_type=("video/mp4" if row["kind"] == "compose" else "audio/wav"),
            headers={"Cache-Control": "no-store"},
        )

    return router
