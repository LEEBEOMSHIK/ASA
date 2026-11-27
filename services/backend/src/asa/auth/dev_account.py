"""Opt-in local development account; never seed production accounts."""
import secrets

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from asa.auth.access import password_hash
from asa.auth.permissions import MEMBER_PERMISSIONS
from asa.config import Settings
from asa.database import connection

TEST_USER = "86e637be-bf6c-4395-a8c9-26c03b0a3611"
TEST_ROLE = "86e637be-bf6c-4395-a8c9-26c03b0a3612"


def ensure_test_member(settings: Settings) -> str:
    if settings.environment != "development" or not settings.dev_login_enabled:
        raise HTTPException(404, "not_found")
    with connection(settings.database_url) as conn:
        conn.execute(
            "INSERT INTO access_roles(workspace_id,id,name,permissions) "
            "VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (settings.workspace_id, TEST_ROLE, "일반 사용자 테스트", Jsonb(MEMBER_PERMISSIONS)),
        )
        created = conn.execute(
            "INSERT INTO access_users(workspace_id,id,username,display_name,role_id,password_hash) "
            "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id",
            (settings.workspace_id, TEST_USER, "demo-member", "일반 사용자 테스트", TEST_ROLE,
             password_hash(secrets.token_urlsafe(48))),
        ).fetchone()
        account = conn.execute(
            "SELECT u.enabled,r.enabled,r.permissions FROM access_users u JOIN access_roles r "
            "ON r.workspace_id=u.workspace_id AND r.id=u.role_id "
            "WHERE u.workspace_id=%s AND u.id=%s AND u.username='demo-member'",
            (settings.workspace_id, TEST_USER),
        ).fetchone()
        # Never reactivate disabled accounts or use quick login for an elevated role.
        if (not account or not account[0] or not account[1]
                or set(account[2]) - set(MEMBER_PERMISSIONS)):
            raise HTTPException(403, "test_account_unavailable")
        if created:
            conn.execute(
                "INSERT INTO access_audit(workspace_id,actor,event,target) VALUES (%s,%s,%s,%s)",
                (settings.workspace_id, "local-development", "test_user_created", TEST_USER),
            )
    return TEST_USER
