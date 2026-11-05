from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.database import connection
from asa.registry.branding import Branding
from asa.registry.schemas import RegistryError


class ProfileEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    display_name: str = Field(min_length=1, max_length=40)
    avatar: str | None = Field(max_length=50000)
    revision: int = Field(ge=0)

    @field_validator("avatar")
    @classmethod
    def png_avatar(cls, value: str | None) -> str | None:
        return Branding.validate_logo(value)


def profile_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/profile")

    @router.get("")
    def get(p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        with connection(settings.database_url, dictionary=True) as conn:
            row = conn.execute(
                "SELECT display_name,avatar,revision FROM user_profiles WHERE "
                "workspace_id=%s AND user_id=%s",
                (p.workspace_id, p.user_id),
            ).fetchone()
        return dict(
            row or {"display_name": p.user_id, "avatar": None, "revision": 0},
            workspace_id=str(p.workspace_id),
            roles=p.roles,
        )

    @router.put("")
    def put(body: ProfileEdit, p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        with connection(settings.database_url, dictionary=True) as conn:
            if body.revision == 0:
                row = conn.execute(
                    "INSERT INTO user_profiles VALUES (%s,%s,%s,%s,1) "
                    "ON CONFLICT DO NOTHING RETURNING revision",
                    (p.workspace_id, p.user_id, body.display_name, body.avatar),
                ).fetchone()
            else:
                row = conn.execute(
                    "UPDATE user_profiles SET display_name=%s,avatar=%s,revision="
                    "revision+1 WHERE workspace_id=%s AND user_id=%s AND revision=%s "
                    "RETURNING revision",
                    (body.display_name, body.avatar, p.workspace_id, p.user_id, body.revision),
                ).fetchone()
            if not row:
                raise RegistryError(409, "profile_conflict")
        return {**body.model_dump(), **row, "workspace_id": str(p.workspace_id), "roles": p.roles}

    return router
