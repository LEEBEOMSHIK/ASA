"""Workspace video policy. Toggling permission never resumes paused submissions."""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.database import connection
from asa.registry.schemas import RegistryError
from asa.video_providers import connection_state


def policy(conn: Any, settings: Settings, workspace: UUID) -> dict[str, Any]:
    row = conn.execute("SELECT enabled,providers,revision FROM video_generation_controls "
                       "WHERE workspace_id=%s", (workspace,)).fetchone()
    return dict(row) if row else {"enabled": settings.video_ai_enabled, "revision": 0,
                                 "providers": {"runway": True, "alibaba": True}}


def lock_policy(conn: Any, workspace: UUID) -> None:
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                 (f"asa-video-policy:{workspace}",))


def allowed(data: dict[str, Any], provider: str) -> bool:
    return bool(data["enabled"] and data["providers"].get(provider, False))


class VideoPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    revision: int = Field(ge=0)
    providers: dict[str, bool]


def video_management_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/video-management")

    def can_manage(p: Principal) -> bool:
        return bool(settings.environment == "development" and
                    p.workspace_id == settings.workspace_id and
                    {"owner", "admin"}.intersection(p.roles))

    def authorize(p: Principal) -> None:
        if not can_manage(p):
            raise RegistryError(403, "video_management_forbidden")

    @router.get("")
    def status(p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        from asa.worker_control import WorkerControl
        if p.workspace_id != settings.workspace_id:
            raise RegistryError(403, "workspace_forbidden")
        with connection(settings.database_url, dictionary=True) as conn:
            data = policy(conn, settings, p.workspace_id)
            counts = conn.execute("SELECT count(*) FILTER (WHERE status='queued' AND paused) "
                                  "AS paused,count(*) FILTER (WHERE status IN "
                                  "('submitting','running')) AS running FROM video_clip_jobs "
                                  "WHERE workspace_id=%s", (p.workspace_id,)).fetchone()
        return {**data, "counts": counts, "can_manage": can_manage(p),
                "worker": WorkerControl(settings).status("video"),
                "connections": {provider: connection_state(settings, provider)
                                for provider in ("runway", "alibaba")}}

    @router.put("")
    def update(body: VideoPolicy, p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        authorize(p)
        from asa.worker_control import WorkerControl
        if WorkerControl(settings).status("video")["state"] == "external":
            raise RegistryError(409, "worker_restart_required")
        if set(body.providers) != {"runway", "alibaba"}:
            raise RegistryError(422, "video_providers_invalid")
        with connection(settings.database_url, dictionary=True) as conn:
            lock_policy(conn, p.workspace_id)
            current = policy(conn, settings, p.workspace_id)
            if current["revision"] != body.revision:
                raise RegistryError(409, "video_policy_changed")
            conn.execute("INSERT INTO video_generation_controls(workspace_id,enabled,providers,"
                         "revision) VALUES (%s,%s,%s,%s) ON CONFLICT(workspace_id) DO UPDATE SET "
                         "enabled=excluded.enabled,providers=excluded.providers,"
                         "revision=excluded.revision", (p.workspace_id, body.enabled,
                         Jsonb(body.providers), body.revision + 1))
            for provider, enabled in body.providers.items():
                if (not body.enabled or not enabled or
                        body.enabled != current["enabled"] or
                        enabled != current["providers"].get(provider)):
                    conn.execute("UPDATE video_clip_jobs SET paused=true WHERE workspace_id=%s "
                                 "AND status='queued' AND model_snapshot->>'provider'=%s",
                                 (p.workspace_id, provider))
        return status(p)

    @router.post("/resume")
    def resume(p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        authorize(p)
        with connection(settings.database_url, dictionary=True) as conn:
            lock_policy(conn, p.workspace_id)
            data = policy(conn, settings, p.workspace_id)
            if not data["enabled"]:
                raise RegistryError(409, "video_generation_disabled")
            for provider in ("runway", "alibaba"):
                if allowed(data, provider) and connection_state(settings, provider) == "configured":
                    conn.execute("UPDATE video_clip_jobs SET paused=false WHERE workspace_id=%s "
                                 "AND status='queued' AND model_snapshot->>'provider'=%s",
                                 (p.workspace_id, provider))
        return status(p)

    return router
