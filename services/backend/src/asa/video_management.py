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
from asa.video_connection import current as current_connection
from asa.video_providers import connection_state, provider_connection
from asa.wan_regions import WanRegion, active_settings, regional_settings, selection
from asa.wan_regions import status as region_status


def policy(conn: Any, settings: Settings, workspace: UUID) -> dict[str, Any]:
    row = conn.execute("SELECT enabled,providers,revision,user_details_enabled,model_defaults "
                       "FROM video_generation_controls "
                       "WHERE workspace_id=%s", (workspace,)).fetchone()
    data: dict[str, Any] = dict(row) if row else {
        "enabled": settings.video_ai_enabled, "revision": 0,
        "providers": {"runway": True, "alibaba": True}}
    data["providers"] = {"higgsfield": True, **data["providers"]}
    data.setdefault('user_details_enabled', False)
    data.setdefault('model_defaults', {})
    return data


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
    user_details_enabled: bool | None = None
    model_defaults: dict[str, dict[str, Any]] | None = None


class RegionSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    region: WanRegion
    revision: int = Field(ge=0)


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
            resolved = active_settings(conn, settings, p.workspace_id)
            regions = region_status(conn, settings, p.workspace_id)
            counts = conn.execute("SELECT count(*) FILTER (WHERE status='queued' AND paused) "
                                  "AS paused,count(*) FILTER (WHERE status IN "
                                  "('submitting','running')) AS running FROM video_clip_jobs "
                                  "WHERE workspace_id=%s", (p.workspace_id,)).fetchone()
        return {**data, "counts": counts, "can_manage": can_manage(p), 'wan_regions': regions,
                "connection_checks": {provider: current_connection(resolved, p.workspace_id,
                                                                  provider)
                                      for provider in ("runway", "alibaba", "higgsfield")},
                "worker": WorkerControl(settings).status("video"),
                "connections": {provider: connection_state(resolved, provider)
                                for provider in ("runway", "alibaba", "higgsfield")}}

    @router.post('/wan-regions/{region}/check')
    def check_region(region: WanRegion,
                     p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        authorize(p)
        from asa.video_connection import check
        return check(regional_settings(settings, region), p.workspace_id, 'alibaba')

    @router.put('/wan-region')
    def apply_region(body: RegionSelection,
                     p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        authorize(p)
        from asa.video_connection import check
        with connection(settings.database_url, dictionary=True) as conn:
            lock_policy(conn, p.workspace_id)
            current = selection(conn, settings, p.workspace_id)
            if current['revision'] != body.revision:
                raise RegistryError(409, 'wan_region_changed')
            # Recheck on the server; a browser's cached success is not authorization.
            result = check(regional_settings(settings, body.region), p.workspace_id, 'alibaba')
            if result['status'] != 'authenticated':
                raise RegistryError(409, 'wan_region_not_authenticated')
            conn.execute('INSERT INTO wan_region_controls(workspace_id,active_region,revision) '
                         'VALUES (%s,%s,%s) ON CONFLICT(workspace_id) DO UPDATE SET '
                         'active_region=excluded.active_region,revision=excluded.revision',
                         (p.workspace_id, body.region, body.revision + 1))
        return status(p)

    @router.put("")
    def update(body: VideoPolicy, p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        authorize(p)
        from asa.worker_control import WorkerControl
        if WorkerControl(settings).status("video")["state"] == "external":
            raise RegistryError(409, "worker_restart_required")
        if set(body.providers) not in ({"runway", "alibaba"},
                                       {"runway", "alibaba", "higgsfield"}):
            raise RegistryError(422, "video_providers_invalid")
        with connection(settings.database_url, dictionary=True) as conn:
            lock_policy(conn, p.workspace_id)
            current = policy(conn, settings, p.workspace_id)
            if current["revision"] != body.revision:
                raise RegistryError(409, "video_policy_changed")
            # Older clients keep the new provider's existing choice.
            providers = {**current["providers"], **body.providers}
            user_details = (current['user_details_enabled'] if body.user_details_enabled is None
                            else body.user_details_enabled)
            defaults = (current['model_defaults'] if body.model_defaults is None
                        else body.model_defaults)
            from asa.video_settings import validate_defaults
            validate_defaults(settings, defaults)
            conn.execute("INSERT INTO video_generation_controls(workspace_id,enabled,providers,"
                         "revision,user_details_enabled,model_defaults) VALUES (%s,%s,%s,%s,%s,%s) "
                         "ON CONFLICT(workspace_id) DO UPDATE SET "
                         "enabled=excluded.enabled,providers=excluded.providers,"
                         "user_details_enabled=excluded.user_details_enabled,"
                         "model_defaults=excluded.model_defaults,"
                         "revision=excluded.revision", (p.workspace_id, body.enabled,
                         Jsonb(providers), body.revision + 1, user_details, Jsonb(defaults)))
            for provider, enabled in providers.items():
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
            rows = conn.execute("SELECT id,model_snapshot FROM video_clip_jobs "
                                "WHERE workspace_id=%s AND status='queued' AND paused",
                                (p.workspace_id,)).fetchall()
            for row in rows:
                if not allowed(data, row['model_snapshot']['provider']):
                    continue
                try:
                    provider_connection(settings, row['model_snapshot'])
                except ValueError:
                    continue
                conn.execute("UPDATE video_clip_jobs SET paused=false WHERE workspace_id=%s "
                             "AND id=%s AND status='queued'", (p.workspace_id, row['id']))
        return status(p)

    return router
