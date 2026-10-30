import hashlib
import json
from contextlib import AbstractContextManager
from importlib.resources import files
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from asa.database import connection
from asa.registry.schemas import AgentDraft, RegistryError
from asa.registry.service import normalize_schema, validate_definition
from asa.tools.catalog import builtin_tools


def migrate(dsn: str, workspace_id: UUID) -> None:
    migration = files("asa.registry").joinpath("migration.sql").read_text(encoding="utf-8")
    with psycopg.connect(dsn) as conn:
        conn.execute(migration)
        conn.execute(
            "INSERT INTO registry_workspaces(id) VALUES (%s) ON CONFLICT DO NOTHING",
            (workspace_id,),
        )


class RegistryRepository:
    def __init__(self, dsn: str, workspace_id: UUID):
        self.dsn = dsn
        self.workspace_id = workspace_id

    def _connect(self) -> AbstractContextManager[psycopg.Connection[dict[str, Any]]]:
        return connection(self.dsn, dictionary=True)

    def _agent(
        self, conn: psycopg.Connection[dict[str, Any]], agent_id: str, lock: bool = False
    ) -> dict[str, Any]:
        query = (
            "SELECT id::text,revision,draft FROM registry_agents WHERE workspace_id=%s AND id=%s"
        )
        if lock:
            query += " FOR UPDATE"
        row = conn.execute(query, (self.workspace_id, agent_id)).fetchone()
        if row is None:
            raise RegistryError(404, "agent_not_found")
        return row

    def list_agents(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT id::text,revision,draft FROM registry_agents "
                "WHERE workspace_id=%s ORDER BY updated_at DESC,id LIMIT 200",
                (self.workspace_id,),
            ).fetchall()

    def create(self, draft: AgentDraft) -> dict[str, Any]:
        agent_id = str(uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO registry_agents(workspace_id,id,draft) VALUES (%s,%s,%s)",
                (self.workspace_id, agent_id, Jsonb(draft.model_dump())),
            )
            return self._agent(conn, agent_id)

    def get(self, agent_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = self._agent(conn, agent_id)
            row["versions"] = conn.execute(
                "SELECT version,source_revision,definition,digest,created_at::text "
                "FROM registry_versions WHERE workspace_id=%s AND agent_id=%s "
                "ORDER BY version DESC",
                (self.workspace_id, agent_id),
            ).fetchall()
            return row

    def update(self, agent_id: str, revision: int, draft: AgentDraft) -> dict[str, Any]:
        with self._connect() as conn:
            row = self._agent(conn, agent_id, lock=True)
            if row["revision"] != revision:
                raise RegistryError(409, "revision_conflict")
            conn.execute(
                "UPDATE registry_agents SET draft=%s,revision=revision+1,updated_at=now() "
                "WHERE workspace_id=%s AND id=%s",
                (Jsonb(draft.model_dump()), self.workspace_id, agent_id),
            )
            return self._agent(conn, agent_id)

    def _tools(self, conn: psycopg.Connection[dict[str, Any]]) -> list[dict[str, Any]]:
        tools = builtin_tools()
        rows = conn.execute(
            "SELECT v.agent_id::text,v.version,v.definition,t.alias FROM registry_versions v "
            "JOIN registry_agent_tools t USING(workspace_id,agent_id,version) "
            "WHERE v.workspace_id=%s ORDER BY v.created_at DESC",
            (self.workspace_id,),
        ).fetchall()
        for row in rows:
            definition = row["definition"]
            tools.append(
                {
                    "id": f"agent:{row['agent_id']}:{row['version']}",
                    "agent_id": row["agent_id"],
                    "version": row["version"],
                    "alias": row["alias"],
                    "kind": "agent",
                    "name": definition["name"],
                    "description": definition["description"],
                    "available": True,
                    "execution_available": False,
                    "unavailable_reason": "등록 가능 · 실행 연결은 다음 단계에서 제공",
                    "input_schema": definition["input_schema"],
                    "output_schema": definition["output_schema"],
                    "dependencies": definition["tools"],
                }
            )
        return tools

    def tools(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return self._tools(conn)

    def validate(self, agent_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            agent = self._agent(conn, agent_id)
            catalog = {tool["id"]: tool for tool in self._tools(conn)}
            return [
                i.model_dump()
                for i in validate_definition(
                    AgentDraft.model_validate(agent["draft"]), catalog, agent_id
                )
            ]

    def publish(self, agent_id: str, revision: int) -> dict[str, Any]:
        with self._connect() as conn:
            agent = self._agent(conn, agent_id, lock=True)
            if agent["revision"] != revision:
                raise RegistryError(409, "revision_conflict")
            existing = conn.execute(
                "SELECT version,source_revision,definition,digest FROM registry_versions "
                "WHERE workspace_id=%s AND agent_id=%s AND source_revision=%s",
                (self.workspace_id, agent_id, revision),
            ).fetchone()
            if existing:
                return existing
            definition = AgentDraft.model_validate(agent["draft"])
            issues = validate_definition(
                definition, {t["id"]: t for t in self._tools(conn)}, agent_id
            )
            if issues:
                raise RegistryError(422, "invalid_definition", issues)
            result = conn.execute(
                "SELECT COALESCE(MAX(version),0)+1 AS version FROM registry_versions "
                "WHERE workspace_id=%s AND agent_id=%s",
                (self.workspace_id, agent_id),
            ).fetchone()
            assert result is not None
            version = result["version"]
            payload = definition.model_dump()
            payload["input_schema"] = normalize_schema(payload["input_schema"])
            payload["output_schema"] = normalize_schema(payload["output_schema"])
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            conn.execute(
                "INSERT INTO registry_versions "
                "(workspace_id,agent_id,version,source_revision,definition,digest) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (self.workspace_id, agent_id, version, revision, Jsonb(payload), digest),
            )
            alias = f"agent_{UUID(agent_id).hex}_v{version}"
            conn.execute(
                "INSERT INTO registry_agent_tools VALUES (%s,%s,%s,%s)",
                (self.workspace_id, agent_id, version, alias),
            )
            return {
                "version": version,
                "source_revision": revision,
                "definition": payload,
                "digest": digest,
            }
