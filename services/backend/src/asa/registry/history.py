from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import StreamingResponse

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.input_requirements import requirements_met
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError
from asa.registry.service import safe_number
from asa.registry.sse import snapshot_stream
from asa.registry.work_progress import attach_progress
from asa.registry.work_titles import attach_titles


class WorkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    agent_id: UUID
    version: int = Field(ge=1, strict=True)
    input: Any
    source_id: UUID | None = None
    is_test: bool = Field(default=False, strict=True)


class WorkNameEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    revision: int = Field(ge=0, strict=True)


def valid_input(value: Any, schema: dict[str, Any]) -> bool:
    if "enum" in schema and value not in schema["enum"]:
        return False
    kind = schema["type"]
    if kind == "object":
        properties = schema.get("properties", {})
        return (
            isinstance(value, dict)
            and requirements_met(schema, value)
            and value.keys() <= properties.keys()
            and all(valid_input(v, properties[k]) for k, v in value.items())
        )
    if kind == "array":
        return (isinstance(value, list)
                and schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 100)
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
                "icon": definition.get("icon", "bot"),
                "input_schema": definition["input_schema"], "available": True,
                "execution_available": False, "unavailable_reason": "실행 연결 준비 중",
            }
            attach_progress(conn, self.workspace_id, [row])
            attach_titles(conn, self.workspace_id, self.requested_by, [row])
            return row

    def history(self, offset: int, hidden: bool = False) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT r.is_test,r.id::text,r.status,r.error,r.updated_at::text,"
                "r.created_at::text,r.version,"
                "(SELECT a.error_code FROM script_attempts a WHERE a.workspace_id=r.workspace_id "
                "AND a.request_id=r.id ORDER BY a.created_at DESC,a.id DESC LIMIT 1) error_code,"
                "v.definition->>'name' AS name FROM customer_requests r "
                "JOIN registry_versions v USING(workspace_id,agent_id,version) "
                "WHERE r.workspace_id=%s AND EXISTS (SELECT 1 FROM hidden_work_requests h "
                "WHERE h.workspace_id=r.workspace_id AND h.request_id=r.id AND h.user_id=%s)=%s "
                "ORDER BY r.created_at DESC,r.id DESC LIMIT 21 OFFSET %s",
                (self.workspace_id, self.requested_by, hidden, offset),
            ).fetchall()
            attach_progress(conn, self.workspace_id, rows[:20])
            attach_titles(conn, self.workspace_id, self.requested_by, rows[:20])
            return {"items": rows[:20], "has_more": len(rows) > 20}

    def save(self, body: WorkRequest) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute("SELECT id FROM registry_workspaces WHERE id=%s FOR UPDATE",
                         (self.workspace_id,))
            if conn.execute("SELECT 1 FROM work_deletions WHERE workspace_id=%s AND request_id=%s",
                            (self.workspace_id, body.id)).fetchone():
                raise RegistryError(410, "work_deleted")
            existing = conn.execute(
                "SELECT agent_id,version,input,source_id,is_test FROM customer_requests "
                "WHERE workspace_id=%s AND id=%s", (self.workspace_id, body.id),
            ).fetchone()
            if existing:
                if (existing["agent_id"] != body.agent_id or existing["input"] != body.input
                        or existing["source_id"] != body.source_id
                        or existing["is_test"] != body.is_test):
                    raise RegistryError(409, "work_conflict")
                body = body.model_copy(update={"version": existing["version"]})
            elif not body.source_id:
                latest = conn.execute(
                    "SELECT version FROM registry_versions WHERE workspace_id=%s AND agent_id=%s "
                    "ORDER BY version DESC LIMIT 1", (self.workspace_id, body.agent_id),
                ).fetchone()
                if latest:
                    body = body.model_copy(update={"version": latest["version"]})
            version = conn.execute(
                "SELECT v.definition FROM registry_versions v JOIN registry_agent_tools t "
                "USING(workspace_id,agent_id,version) "
                "WHERE v.workspace_id=%s AND v.agent_id=%s AND v.version=%s",
                (self.workspace_id, body.agent_id, body.version),
            ).fetchone()
            if version is None:
                raise RegistryError(404, "tool_not_found")
            from asa.registry import art_styles

            definition = version["definition"]
            video = any(field.get('x-video-model') for field in
                        definition['input_schema'].get('properties', {}).values())
            style = art_styles.resolve(conn, self.workspace_id, body.input) if video else None
            effective_input = art_styles.video_inputs(definition, body.input, style)
            if not valid_input(effective_input, definition["input_schema"]):
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
    def history(offset: int = Query(0, ge=0, le=100000), hidden: bool = False,
                repository: HistoryRepository = Depends(repo)) -> dict[str, Any]:
        return repository.history(offset, hidden)

    @router.put("/{request_id}/visibility")
    def visibility(request_id: UUID, hidden: bool, repository: HistoryRepository = Depends(repo)
                   ) -> dict[str, bool]:
        with repository._connect() as conn:
            args = (repository.workspace_id, request_id, repository.requested_by)
            if not conn.execute("SELECT id FROM customer_requests WHERE workspace_id=%s AND id=%s "
                                "FOR KEY SHARE", args[:2]).fetchone():
                raise RegistryError(404, "work_not_found")
            if hidden:
                conn.execute("INSERT INTO hidden_work_requests(workspace_id,request_id,user_id) "
                             "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING", args)
            else:
                conn.execute("DELETE FROM hidden_work_requests WHERE workspace_id=%s AND "
                             "request_id=%s AND user_id=%s", args)
        return {"hidden": hidden}

    @router.get("/events")
    def events(request: Request, hidden: bool = False, pages: int = Query(1, ge=1, le=100),
               repository: HistoryRepository = Depends(repo)) -> StreamingResponse:
        def load() -> dict[str, Any]:
            sessions.principal(request)
            chunks = [repository.history(page * 20, hidden) for page in range(pages)]
            return {"items": [item for chunk in chunks for item in chunk["items"]],
                    "has_more": chunks[-1]["has_more"]}
        return snapshot_stream(request, load, repository.dsn, repository.workspace_id)

    @router.put("/{request_id}/name")
    def rename(request_id: UUID, body: WorkNameEdit,
               repository: HistoryRepository = Depends(repo)) -> dict[str, Any]:
        with repository._connect() as conn:
            if not conn.execute("SELECT id FROM customer_requests WHERE workspace_id=%s AND id=%s "
                                "FOR KEY SHARE", (repository.workspace_id, request_id)).fetchone():
                raise RegistryError(404, "work_not_found")
            args = (repository.workspace_id, request_id, repository.requested_by, body.name)
            if body.revision == 0:
                row = conn.execute(
                    "INSERT INTO user_work_names(workspace_id,request_id,user_id,name,revision) "
                    "VALUES (%s,%s,%s,%s,1) ON CONFLICT DO NOTHING RETURNING revision", args,
                ).fetchone()
            else:
                row = conn.execute(
                    "UPDATE user_work_names SET name=%s,revision=revision+1 WHERE workspace_id=%s "
                    "AND request_id=%s AND user_id=%s AND revision=%s RETURNING revision",
                    (body.name, *args[:3], body.revision),
                ).fetchone()
            if row is None:
                raise RegistryError(409, "work_name_conflict")
        return repository.detail(request_id)

    @router.get("/answer-sources")
    def sources(agent_id: UUID | None = None, q: str = Query('', max_length=200),
                offset: int = Query(0, ge=0, le=100000),
                repository: HistoryRepository = Depends(repo)) -> dict[str, Any]:
        from asa.registry.answer_sources import answer_sources
        return answer_sources(repository, q, offset, agent_id)

    @router.get("/answer-sources/{request_id}")
    def source_versions(request_id: UUID,
                        source_kind: str = Query('agent', pattern='^(agent|automation)$'),
                        step_index: int = Query(0, ge=0),
                        repository: HistoryRepository = Depends(repo)) -> dict[str, Any]:
        from asa.registry.answer_sources import answer_versions, automation_answer
        if source_kind == 'automation':
            return automation_answer(repository, request_id, step_index)
        return answer_versions(repository, request_id)

    @router.get("/{request_id}")
    def detail(request_id: UUID,
               repository: HistoryRepository = Depends(repo)) -> dict[str, Any]:
        return repository.detail(request_id)

    @router.post("", status_code=201)
    def save(body: WorkRequest,
             repository: HistoryRepository = Depends(repo)) -> dict[str, Any]:
        return repository.save(body)

    return router
