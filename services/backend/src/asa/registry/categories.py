"""Workspace category metadata, separate from agent execution definitions."""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, model_validator

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError


class Category(BaseModel):
    id: UUID
    name: str = Field(min_length=1, max_length=60)


class Catalog(BaseModel):
    revision: int = Field(ge=0)
    categories: list[Category] = Field(default_factory=list, max_length=100)
    assignments: dict[UUID, UUID] = Field(default_factory=dict, max_length=10000)

    @model_validator(mode="after")
    def valid(self) -> "Catalog":
        ids = [c.id for c in self.categories]
        names = [c.name.strip().casefold() for c in self.categories]
        if len(set(ids)) != len(ids) or len(set(names)) != len(names) or not all(names):
            raise ValueError("duplicate_or_empty_category")
        if not set(self.assignments.values()).issubset(ids):
            raise ValueError("unknown_category")
        for category in self.categories:
            category.name = category.name.strip()
        return self


def read(repo: RegistryRepository) -> dict[str, Any]:
    with repo._connect() as conn:
        row = conn.execute("SELECT revision,content FROM agent_categories WHERE workspace_id=%s",
                           (repo.workspace_id,)).fetchone()
        if row:
            return {"revision": row["revision"], **row["content"]}
        return Catalog(revision=0).model_dump(mode="json")


def save(repo: RegistryRepository, body: Catalog) -> dict[str, Any]:
    with repo._connect() as conn:
        conn.execute("INSERT INTO agent_categories(workspace_id) VALUES (%s) "
                     "ON CONFLICT DO NOTHING",
                     (repo.workspace_id,))
        row = conn.execute("SELECT revision FROM agent_categories WHERE workspace_id=%s FOR UPDATE",
                           (repo.workspace_id,)).fetchone()
        if row is None or row["revision"] != body.revision:
            raise RegistryError(409, "category_conflict")
        agents = conn.execute("SELECT id FROM registry_agents WHERE workspace_id=%s",
                              (repo.workspace_id,)).fetchall()
        if not set(body.assignments).issubset({a["id"] for a in agents}):
            raise RegistryError(422, "category_agent_missing")
        content = body.model_dump(mode="json", exclude={"revision"})
        conn.execute("UPDATE agent_categories SET revision=revision+1,content=%s "
                     "WHERE workspace_id=%s",
                     (Jsonb(content), repo.workspace_id))
        return {"revision": body.revision + 1, **content}


def category_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/agent-categories")

    @router.get("")
    def get(principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        return {**read(RegistryRepository(settings.database_url, principal.workspace_id)),
                "can_manage": bool({"owner", "admin"}.intersection(principal.roles))}

    @router.put("")
    def put(body: Catalog, principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        if not {"owner", "admin"}.intersection(principal.roles):
            raise HTTPException(403, "admin_required")
        return {**save(RegistryRepository(settings.database_url, principal.workspace_id), body),
                "can_manage": True}

    @router.get("/favorites")
    def favorites(principal: Principal = Depends(sessions.principal)) -> list[str]:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            rows = conn.execute("SELECT agent_id FROM agent_favorites WHERE workspace_id=%s "
                                "AND user_id=%s", (repo.workspace_id, principal.user_id)).fetchall()
        return [str(row["agent_id"]) for row in rows]

    @router.put("/favorites/{agent_id}")
    def add_favorite(agent_id: UUID, principal: Principal = Depends(sessions.principal)) -> None:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            if not conn.execute("SELECT 1 FROM registry_agents WHERE workspace_id=%s AND id=%s "
                                "FOR KEY SHARE", (repo.workspace_id, agent_id)).fetchone():
                raise HTTPException(404, "agent_not_found")
            conn.execute("INSERT INTO agent_favorites(workspace_id,user_id,agent_id) "
                         "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                         (repo.workspace_id, principal.user_id, agent_id))

    @router.delete("/favorites/{agent_id}")
    def remove_favorite(agent_id: UUID, principal: Principal = Depends(sessions.principal)) -> None:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            conn.execute("DELETE FROM agent_favorites WHERE workspace_id=%s AND user_id=%s "
                         "AND agent_id=%s", (repo.workspace_id, principal.user_id, agent_id))

    return router
