"""Workspace accounts and editable roles. Credentials never appear in list/audit responses."""

import hashlib
import hmac
import secrets
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from asa.auth.permissions import ALL_PERMISSIONS, CATALOG
from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.database import connection


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return salt + ":" + digest.hex()


def password_matches(password: str, stored: str) -> bool:
    try:
        return hmac.compare_digest(password_hash(password, stored.split(":")[0]), stored)
    except (ValueError, TypeError):
        return False


class RoleEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    enabled: bool = True
    permissions: list[str] = Field(max_length=100)
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_permissions(self) -> "RoleEdit":
        self.name = self.name.strip()
        if not self.name or set(self.permissions) - ALL_PERMISSIONS:
            raise ValueError("invalid_permissions")
        for p in self.permissions:
            if p.split(".")[0] + ".view" not in self.permissions:
                raise ValueError("menu_view_required")
        self.permissions = sorted(set(self.permissions))
        return self


class UserEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}$")
    display_name: str = Field(min_length=1, max_length=80)
    role_id: UUID
    enabled: bool = True
    password: SecretStr | None = None
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_password(self) -> "UserEdit":
        self.username = self.username.lower()
        self.display_name = self.display_name.strip()
        if not self.display_name:
            raise ValueError("display_name_required")
        if self.password is not None and not 12 <= len(self.password.get_secret_value()) <= 128:
            raise ValueError("password_length_12_128")
        return self


def audit(conn: Any, p: Principal, event: str, target: str) -> None:
    conn.execute(
        "INSERT INTO access_audit(workspace_id,actor,event,target) VALUES (%s,%s,%s,%s)",
        (p.workspace_id, p.user_id, event, target),
    )


def access_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin/access")

    @router.get("")
    def listing(p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        with connection(settings.database_url, dictionary=True) as conn:
            roles = conn.execute(
                "SELECT id,name,enabled,permissions,revision FROM access_roles "
                "WHERE workspace_id=%s ORDER BY name",
                (p.workspace_id,),
            ).fetchall()
            users = conn.execute(
                "SELECT id,username,display_name,role_id,enabled,revision "
                "FROM access_users WHERE workspace_id=%s ORDER BY username",
                (p.workspace_id,),
            ).fetchall()
            events = conn.execute(
                "SELECT actor,event,target,created_at FROM access_audit "
                "WHERE workspace_id=%s ORDER BY id DESC LIMIT 100",
                (p.workspace_id,),
            ).fetchall()
        return {
            "roles": roles,
            "users": users,
            "catalog": CATALOG,
            "audit": events,
            "can_edit": p.can("access.edit"),
            "user_id": p.user_id,
        }

    @router.get("/audit")
    def audit_listing(
        q: str = Query(default="", max_length=120),
        event: Literal["all", "role_saved", "role_disabled", "user_saved",
                       "user_disabled", "test_user_created"] = "all",
        days: Literal["0", "7", "30", "90"] = "0",
        page: int = Query(default=1, ge=1, le=1000000),
        p: Principal = Depends(sessions.principal),
    ) -> dict[str, Any]:
        base = """
          WITH entries AS (
            SELECT a.id,a.event,a.created_at,
              CASE WHEN a.actor='local-owner' THEN '관리자'
                   WHEN a.actor='local-development' THEN '개발 환경'
                   ELSE COALESCE(actor.display_name,a.actor) END AS actor_name,
              COALESCE(r.name,u.display_name,a.target) AS target_name,
              CASE WHEN a.event LIKE 'role_%%' THEN '역할' ELSE '사용자' END AS target_type
            FROM access_audit a
            LEFT JOIN access_users actor ON actor.workspace_id=a.workspace_id
              AND actor.id::text=a.actor
            LEFT JOIN access_roles r ON r.workspace_id=a.workspace_id AND r.id::text=a.target
              AND a.event LIKE 'role_%%'
            LEFT JOIN access_users u ON u.workspace_id=a.workspace_id AND u.id::text=a.target
              AND a.event NOT LIKE 'role_%%'
            WHERE a.workspace_id=%s
          ), filtered AS (
            SELECT * FROM entries WHERE (%s='all' OR event=%s)
              AND (%s=0 OR created_at>=now() - make_interval(days => %s))
              AND (%s='' OR strpos(lower(actor_name || ' ' || target_name),lower(%s))>0)
          )
        """
        args = (p.workspace_id, event, event, int(days), int(days), q.strip(), q.strip())
        with connection(settings.database_url, dictionary=True) as conn:
            counts = conn.execute(
                base + "SELECT (SELECT count(*) FROM entries) AS total, "
                "(SELECT count(*) FROM filtered) AS filtered_total", args,
            ).fetchone()
            assert counts is not None
            pages = max(1, (counts["filtered_total"] + 9) // 10)
            current = min(page, pages)
            items = conn.execute(
                base + "SELECT * FROM filtered ORDER BY id DESC LIMIT 10 OFFSET %s",
                (*args, (current - 1) * 10),
            ).fetchall()
        return {**counts, "items": items, "page": current, "pages": pages}

    @router.put("/roles/{role_id}")
    def save_role(
        role_id: UUID, body: RoleEdit, p: Principal = Depends(sessions.principal)
    ) -> dict[str, Any]:
        with connection(settings.database_url, dictionary=True) as conn:
            conn.execute(
                "SELECT id FROM registry_workspaces WHERE id=%s FOR UPDATE", (p.workspace_id,)
            )
            # A delegated manager cannot manufacture permissions they do not possess.
            if any(not p.can(permission) for permission in body.permissions):
                raise HTTPException(403, "permission_escalation")
            previous = conn.execute(
                "SELECT permissions FROM access_roles WHERE workspace_id=%s AND id=%s",
                (p.workspace_id, role_id),
            ).fetchone()
            if previous and any(not p.can(v) for v in previous["permissions"]):
                raise HTTPException(403, "permission_escalation")
            if (
                p.user_id != "local-owner"
                and conn.execute(
                    "SELECT 1 FROM access_users WHERE workspace_id=%s AND id=%s AND role_id=%s",
                    (p.workspace_id, p.user_id, role_id),
                ).fetchone()
            ):
                raise HTTPException(403, "own_role_protected")
            if body.revision == 0:
                row = conn.execute(
                    "INSERT INTO access_roles(workspace_id,id,name,enabled,permissions) "
                    "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING revision",
                    (p.workspace_id, role_id, body.name, body.enabled, Jsonb(body.permissions)),
                ).fetchone()
            else:
                row = conn.execute(
                    "UPDATE access_roles SET name=%s,enabled=%s,permissions=%s,"
                    "revision=revision+1 WHERE workspace_id=%s AND id=%s "
                    "AND revision=%s RETURNING revision",
                    (
                        body.name,
                        body.enabled,
                        Jsonb(body.permissions),
                        p.workspace_id,
                        role_id,
                        body.revision,
                    ),
                ).fetchone()
            if not row:
                raise HTTPException(409, "access_conflict")
            audit(conn, p, "role_saved" if body.enabled else "role_disabled", str(role_id))
        return row

    @router.put("/users/{user_id}")
    def save_user(
        user_id: UUID, body: UserEdit, p: Principal = Depends(sessions.principal)
    ) -> dict[str, Any]:
        with connection(settings.database_url, dictionary=True) as conn:
            conn.execute(
                "SELECT id FROM registry_workspaces WHERE id=%s FOR UPDATE", (p.workspace_id,)
            )
            if str(user_id) == p.user_id:
                raise HTTPException(403, "own_account_protected")
            role = conn.execute(
                "SELECT permissions, enabled FROM access_roles WHERE workspace_id=%s AND id=%s",
                (p.workspace_id, body.role_id),
            ).fetchone()
            if (
                not role
                or (body.enabled and not role["enabled"])
                or any(not p.can(v) for v in role["permissions"])
            ):
                raise HTTPException(403, "permission_escalation")
            # Also protect privileged existing accounts from less privileged managers.
            old = conn.execute(
                "SELECT r.permissions FROM access_users u JOIN access_roles r "
                "ON r.workspace_id=u.workspace_id AND r.id=u.role_id "
                "WHERE u.workspace_id=%s AND u.id=%s",
                (p.workspace_id, user_id),
            ).fetchone()
            if old and any(not p.can(v) for v in old["permissions"]):
                raise HTTPException(403, "permission_escalation")
            if conn.execute(
                "SELECT 1 FROM access_users WHERE workspace_id=%s AND username=%s AND id<>%s",
                (p.workspace_id, body.username, user_id),
            ).fetchone():
                raise HTTPException(409, "username_taken")
            password = password_hash(body.password.get_secret_value()) if body.password else None
            if body.revision == 0:
                if not password:
                    raise HTTPException(422, "password_required")
                row = conn.execute(
                    "INSERT INTO access_users(workspace_id,id,username,display_name,"
                    "role_id,enabled,password_hash) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT DO NOTHING RETURNING revision",
                    (
                        p.workspace_id,
                        user_id,
                        body.username,
                        body.display_name,
                        body.role_id,
                        body.enabled,
                        password,
                    ),
                ).fetchone()
            else:
                row = conn.execute(
                    "UPDATE access_users SET username=%s,display_name=%s,role_id=%s,"
                    "enabled=%s,password_hash=COALESCE(%s,password_hash),revision=revision+1 "
                    "WHERE workspace_id=%s AND id=%s AND revision=%s RETURNING revision",
                    (
                        body.username,
                        body.display_name,
                        body.role_id,
                        body.enabled,
                        password,
                        p.workspace_id,
                        user_id,
                        body.revision,
                    ),
                ).fetchone()
            if not row:
                raise HTTPException(409, "access_conflict")
            if password or not body.enabled:
                conn.execute(
                    "DELETE FROM registry_sessions WHERE workspace_id=%s AND user_id=%s",
                    (p.workspace_id, str(user_id)),
                )
            audit(conn, p, "user_saved" if body.enabled else "user_disabled", str(user_id))
        return row

    return router
