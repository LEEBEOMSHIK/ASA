"""Personal automation categories, independent of execution and schedules."""
from typing import Any

from fastapi import APIRouter, Depends
from psycopg.types.json import Jsonb

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.categories import Catalog
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError


class AutomationCatalog(Catalog):
    enabled: bool = False


def read(repo: RegistryRepository, user_id: str) -> dict[str, Any]:
    with repo._connect() as conn:
        row = conn.execute("SELECT revision,content FROM automation_categories "
                           "WHERE workspace_id=%s AND user_id=%s",
                           (repo.workspace_id, user_id)).fetchone()
        if row:
            return {"enabled": False, "revision": row["revision"], **row["content"]}
        return AutomationCatalog(revision=0).model_dump(mode="json")


def save(repo: RegistryRepository, user_id: str, body: AutomationCatalog) -> dict[str, Any]:
    with repo._connect() as conn:
        conn.execute("INSERT INTO automation_categories(workspace_id,user_id) VALUES (%s,%s) "
                     "ON CONFLICT DO NOTHING",
                     (repo.workspace_id, user_id))
        row = conn.execute("SELECT revision FROM automation_categories "
                           "WHERE workspace_id=%s AND user_id=%s FOR UPDATE",
                           (repo.workspace_id, user_id)).fetchone()
        if row is None or row["revision"] != body.revision:
            raise RegistryError(409, "category_conflict")
        automations = conn.execute("SELECT id FROM automation_drafts WHERE workspace_id=%s",
                              (repo.workspace_id,)).fetchall()
        if not set(body.assignments).issubset({a["id"] for a in automations}):
            raise RegistryError(422, "category_automation_missing")
        content = body.model_dump(mode="json", exclude={"revision"})
        conn.execute("UPDATE automation_categories SET revision=revision+1,content=%s "
                     "WHERE workspace_id=%s AND user_id=%s",
                     (Jsonb(content), repo.workspace_id, user_id))
        return {"revision": body.revision + 1, **content}


def automation_category_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/automation-categories")

    @router.get("")
    def get(principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        return {**read(repo, principal.user_id), "can_manage": True}

    @router.put("")
    def put(
        body: AutomationCatalog, principal: Principal = Depends(sessions.principal),
    ) -> dict[str, Any]:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        return {**save(repo, principal.user_id, body), "can_manage": True}

    return router
