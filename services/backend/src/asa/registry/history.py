from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import StreamingResponse

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError
from asa.registry.service import safe_number
from asa.registry.sse import snapshot_stream
from asa.registry.work_progress import attach_progress


class WorkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    agent_id: UUID
    version: int = Field(ge=1, strict=True)
    input: Any
    source_id: UUID | None = None
    is_test: bool = Field(default=False, strict=True)


def valid_input(value: Any, schema: dict[str, Any]) -> bool:
    if "enum" in schema and value not in schema["enum"]:
        return False
    kind = schema["type"]
    if kind == "object":
        properties = schema.get("properties", {})
        return (
            isinstance(value, dict)
            and set(schema.get("required", [])) <= value.keys()
            and value.keys() <= properties.keys()
            and all(valid_input(v, properties[k]) for k, v in value.items())
        )
    if kind == "array":
        return (isinstance(value, list) and len(value) <= schema.get("maxItems", 100)
                and all(valid_input(v, schema["items"]) for v in value))
    if kind == "string":
        return (isinstance(value, str)
                and schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 65536))
    if kind == "boolean":
        return type(value) is bool
    return (safe_number(value) and (kind != "integer" or int(value) == value)
            and schema["minimum"] <= value <= schema["maximum"])


class HistoryRepository(RegistryRepository):
    requested_by: str | None = None

    def detail(self, request_id: UUID) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT r.is_test,r.id::text,r.input,r.source_id::text,r.status,r.result,r.error,"
                "r.created_at::text,r.updated_at::text,r.agent_id::text,r.version,v.definition "
                "FROM customer_requests r JOIN registry_versions v "
                "USING(workspace_id,agent_id,version) WHERE r.workspace_id=%s AND r.id=%s",
                (self.workspace_id, request_id),
            ).fetchone()
            if row is None:
                raise RegistryError(404, "work_not_found")
            definition = row.pop("definition")
            row["agent"] = {
                "id": f"agent:{row['agent_id']}:{row['version']}",
                "agent_id": row["agent_id"], "version": row["version"], "kind": "agent",
                "name": definition["name"], "description": definition["description"],
                "input_schema": definition["input_schema"], "available": True,
                "execution_available": False, "unavailable_reason": "실행 연결 준비 중",
            }
            attach_progress(conn, self.workspace_id, [row])
            return row

    def history(self, offset: int) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT r.is_test,r.id::text,r.status,r.error,r.updated_at::text,"
                "r.created_at::text,r.version,"
                "(SELECT a.error_code FROM script_attempts a WHERE a.workspace_id=r.workspace_id "
                "AND a.request_id=r.id ORDER BY a.created_at DESC,a.id DESC LIMIT 1) error_code,"
                "v.definition->>'name' AS name FROM customer_requests r "
                "JOIN registry_versions v USING(workspace_id,agent_id,version) "
                "WHERE r.workspace_id=%s ORDER BY r.created_at DESC,r.id DESC LIMIT 21 OFFSET %s",
                (self.workspace_id, offset),
            ).fetchall()
            attach_progress(conn, self.workspace_id, rows[:20])
            return {"items": rows[:20], "has_more": len(rows) > 20}

    def save(self, body: WorkRequest) -> dict[str, Any]:
        with self._connect() as conn:
            version = conn.execute(
                "SELECT v.definition FROM registry_versions v JOIN registry_agent_tools t "
                "USING(workspace_id,agent_id,version) "
                "WHERE v.workspace_id=%s AND v.agent_id=%s AND v.version=%s",
                (self.workspace_id, body.agent_id, body.version),
            ).fetchone()
            if version is None:
                raise RegistryError(404, "tool_not_found")
            if not valid_input(body.input, version["definition"]["input_schema"]):
                raise RegistryError(422, "invalid_work_input")
            if body.source_id:
                source = conn.execute(
                    "SELECT agent_id,version FROM customer_requests "
                    "WHERE workspace_id=%s AND id=%s", (self.workspace_id, body.source_id),
                ).fetchone()
                if source is None:
                    raise RegistryError(404, "work_not_found")
                if source["agent_id"] != body.agent_id or source["version"] != body.version:
                    raise RegistryError(422, "invalid_work_input")
            conn.execute(
                "INSERT INTO customer_requests(workspace_id,id,agent_id,version,input,"
                "source_id,requested_by,is_test) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(workspace_id,id) DO NOTHING",
                (self.workspace_id, body.id, body.agent_id, body.version,
                 Jsonb(body.input), body.source_id, self.requested_by, body.is_test),
            )
            existing = conn.execute(
                "SELECT agent_id,version,input,source_id,is_test FROM customer_requests "
                "WHERE workspace_id=%s AND id=%s", (self.workspace_id, body.id),
            ).fetchone()
            assert existing is not None
            if (existing["agent_id"] != body.agent_id or existing["version"] != body.version
                    or existing["is_test"] != body.is_test
                    or existing["input"] != body.input or existing["source_id"] != body.source_id):
                raise RegistryError(409, "work_conflict")
        return self.detail(body.id)


def history_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/work-requests")

    def repo(principal: Principal = Depends(sessions.principal)) -> HistoryRepository:
        repository = HistoryRepository(settings.database_url, principal.workspace_id)
        repository.requested_by = principal.user_id
        return repository

    @router.get("")
    def history(offset: int = Query(0, ge=0, le=100000),
                repository: HistoryRepository = Depends(repo)) -> dict[str, Any]:
        return repository.history(offset)

    @router.get("/events")
    def events(request: Request, pages: int = Query(1, ge=1, le=100),
               repository: HistoryRepository = Depends(repo)) -> StreamingResponse:
        def load() -> dict[str, Any]:
            sessions.principal(request)
            return {"items": [item for page in range(pages)
                              for item in repository.history(page * 20)["items"]]}
        return snapshot_stream(request, load, repository.dsn, repository.workspace_id)

    @router.get("/{request_id}")
    def detail(request_id: UUID,
               repository: HistoryRepository = Depends(repo)) -> dict[str, Any]:
        return repository.detail(request_id)

    @router.post("", status_code=201)
    def save(body: WorkRequest,
             repository: HistoryRepository = Depends(repo)) -> dict[str, Any]:
        return repository.save(body)

    return router
