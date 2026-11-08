"""Account-scoped navigation accents, shared by authenticated devices."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.database import connection
from asa.registry.schemas import RegistryError

Menu = Literal[
    "home",
    "automations",
    "agents",
    "characters",
    "tools",
    "video-comparison",
    "admin-agents",
    "work-history",
    "models",
    "monitoring",
    "branding",
]
Color = (
    Literal["red", "orange", "green", "blue", "purple", "pink"]
    | Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
)


class NavigationColorEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    color: Color | None
    revision: int = Field(ge=0)

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: str | None) -> str | None:
        return value.lower() if value else value


def navigation_colors_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/profile/navigation-colors")

    @router.get("")
    def get(response: Response, p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        with connection(settings.database_url, dictionary=True) as conn:
            rows = conn.execute(
                "SELECT menu,color,revision FROM user_navigation_colors "
                "WHERE workspace_id=%s AND user_id=%s",
                (p.workspace_id, p.user_id),
            ).fetchall()
        return {
            "items": {r["menu"]: {"color": r["color"], "revision": r["revision"]} for r in rows}
        }

    @router.put("/{menu}")
    def put(
        menu: Menu,
        body: NavigationColorEdit,
        response: Response,
        p: Principal = Depends(sessions.principal),
    ) -> dict[str, Any]:
        response.headers["Cache-Control"] = "no-store"
        with connection(settings.database_url, dictionary=True) as conn:
            if body.revision == 0:
                row = conn.execute(
                    "INSERT INTO user_navigation_colors(workspace_id,user_id,menu,color,revision) "
                    "VALUES (%s,%s,%s,%s,1) ON CONFLICT DO NOTHING RETURNING color,revision",
                    (p.workspace_id, p.user_id, menu, body.color),
                ).fetchone()
            else:
                row = conn.execute(
                    "UPDATE user_navigation_colors SET color=%s,revision=revision+1 "
                    "WHERE workspace_id=%s AND user_id=%s AND menu=%s AND revision=%s "
                    "RETURNING color,revision",
                    (body.color, p.workspace_id, p.user_id, menu, body.revision),
                ).fetchone()
            if row is None:
                raise RegistryError(409, "navigation_color_conflict")
        return dict(row)

    return router
