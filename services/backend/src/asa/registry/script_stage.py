import json
from collections.abc import Callable
from typing import Any, TypedDict
from uuid import UUID

import psycopg
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from asa.models import AgentAnswer, Script
from asa.registry.history import valid_input
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError


class SaveScript(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = ""
    narration: str = ""
    answer: Any = None
    id: UUID
    expected_revision: int = Field(ge=0, strict=True)
    base_version: int | None = Field(default=None, ge=0, strict=True)


class GenerateScript(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: UUID
    expected_revision: int = Field(ge=0, strict=True)
    base_version: int = Field(ge=0, strict=True)
    instruction: str = Field(min_length=1, max_length=2000)
    acknowledge_unknown: bool = False


class ApproveScript(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    version: int = Field(ge=1, strict=True)


class ScriptRepository(RegistryRepository):
    def _request(
        self, conn: psycopg.Connection[dict[str, Any]], request_id: str, lock: bool = False
    ) -> dict[str, Any]:
        row = conn.execute(
            "SELECT r.input,v.definition FROM customer_requests r JOIN registry_versions v "
            "USING(workspace_id,agent_id,version) WHERE r.workspace_id=%s AND r.id=%s"
            + (" FOR UPDATE OF r" if lock else ""),
            (self.workspace_id, request_id),
        ).fetchone()
        if row is None:
            raise RegistryError(404, "work_not_found")
        return row

    def _stage(
        self, conn: psycopg.Connection[dict[str, Any]], request_id: str, expected: int | None = None
    ) -> dict[str, Any]:
        conn.execute(
            "INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s) "
            "ON CONFLICT DO NOTHING",
            (self.workspace_id, request_id),
        )
        row = conn.execute(
            "SELECT * FROM script_stages WHERE workspace_id=%s AND request_id=%s",
            (self.workspace_id, request_id),
        ).fetchone()
        assert row is not None
        if expected is not None and row["revision"] != expected:
            raise RegistryError(409, "script_revision_conflict")
        return row

    def _idle(self, conn: psycopg.Connection[dict[str, Any]], request_id: str) -> None:
        row = conn.execute(
            "SELECT id FROM script_attempts WHERE workspace_id=%s AND request_id=%s "
            "AND status IN ('queued','running')",
            (self.workspace_id, request_id),
        )
        if row.fetchone():
            raise RegistryError(409, "script_busy")

    def get(self, request_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            request = self._request(conn, request_id)
            stage = conn.execute(
                "SELECT revision,head_version,approved_version FROM script_stages "
                "WHERE workspace_id=%s AND request_id=%s",
                (self.workspace_id, request_id),
            ).fetchone() or {"revision": 0, "head_version": 0, "approved_version": None}
            stage["versions"] = conn.execute(
                "SELECT version,title,narration,answer,source,base_version,instruction,"
                "created_at::text "
                "FROM script_versions WHERE workspace_id=%s AND request_id=%s "
                "ORDER BY version DESC",
                (self.workspace_id, request_id),
            ).fetchall()
            stage["attempts"] = conn.execute(
                "SELECT id::text,base_version,instruction,status,result_version,provider,model,"
                "created_at::text,started_at::text,finished_at::text,error_code,live_output "
                "FROM script_attempts "
                "WHERE workspace_id=%s AND request_id=%s ORDER BY created_at DESC LIMIT 20",
                (self.workspace_id, request_id),
            ).fetchall()
            stage["output_schema"] = request["definition"]["output_schema"]
            stage["requires_approval"] = request["definition"].get("requires_approval", False)
            stage["tools_supported"] = not request["definition"]["tools"]
            return stage

    def save(self, request_id: str, body: SaveScript) -> dict[str, Any]:
        with self._connect() as conn:
            request = self._request(conn, request_id, True)
            if body.answer is not None:
                if not valid_input(body.answer, request["definition"]["output_schema"]):
                    raise RegistryError(422, "invalid_work_input")
            else:
                try:
                    Script(title=body.title, narration=body.narration)
                except ValueError:
                    raise RegistryError(422, "invalid_work_input") from None
            existing = conn.execute(
                "SELECT title,narration,answer,source FROM script_versions "
                "WHERE workspace_id=%s AND request_id=%s AND operation_id=%s",
                (self.workspace_id, request_id, body.id),
            ).fetchone()
            if existing:
                if (
                    existing["answer"] != body.answer
                    or existing["source"] != "manual"
                    or existing["title"] != body.title
                    or existing["narration"] != body.narration
                ):
                    raise RegistryError(409, "work_conflict")
            else:
                stage = self._stage(conn, request_id, body.expected_revision)
                self._idle(conn, request_id)
                base = body.base_version if body.base_version is not None else stage["head_version"]
                if (
                    base
                    and not conn.execute(
                        "SELECT 1 FROM script_versions WHERE workspace_id=%s "
                        "AND request_id=%s AND version=%s",
                        (self.workspace_id, request_id, base),
                    ).fetchone()
                ):
                    raise RegistryError(404, "script_version_not_found")
                self._add_version(
                    conn,
                    request_id,
                    stage,
                    body.id,
                    body.title,
                    body.narration,
                    "manual",
                    base,
                    "",
                    body.answer,
                )
        return self.get(request_id)

    def _add_version(
        self,
        conn: psycopg.Connection[dict[str, Any]],
        request_id: str,
        stage: dict[str, Any],
        operation_id: UUID,
        title: str,
        narration: str,
        source: str,
        base: int,
        instruction: str,
        answer: Any = None,
    ) -> int:
        version = int(stage["head_version"]) + 1
        conn.execute(
            "INSERT INTO script_versions(workspace_id,request_id,version,operation_id,"
            "title,narration,source,base_version,instruction,answer) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                self.workspace_id,
                request_id,
                version,
                operation_id,
                title,
                narration,
                source,
                base or None,
                instruction,
                Jsonb(answer) if answer is not None else None,
            ),
        )
        conn.execute(
            "UPDATE script_stages SET head_version=%s,approved_version=NULL,"
            "revision=revision+1 WHERE workspace_id=%s AND request_id=%s",
            (version, self.workspace_id, request_id),
        )
        conn.execute(
            "UPDATE customer_requests SET result=%s,status='succeeded',error=NULL,"
            "updated_at=now() WHERE workspace_id=%s AND id=%s",
            (
                Jsonb(answer if answer is not None else {"title": title, "narration": narration}),
                self.workspace_id,
                request_id,
            ),
        )
        return version

    def approve(self, request_id: str, body: ApproveScript) -> dict[str, Any]:
        with self._connect() as conn:
            self._request(conn, request_id, True)
            stage = self._stage(conn, request_id, body.expected_revision)
            self._idle(conn, request_id)
            if stage["head_version"] != body.version:
                raise RegistryError(409, "script_revision_conflict")
            conn.execute(
                "UPDATE script_stages SET approved_version=%s,revision=revision+1 "
                "WHERE workspace_id=%s AND request_id=%s",
                (body.version, self.workspace_id, request_id),
            )
        return self.get(request_id)

    def queue(
        self,
        request_id: str,
        body: GenerateScript,
        *,
        provider: str | None = None,
        model: str | None = None,
        automatic: bool = False,
        queue_limit: int = 100,
    ) -> dict[str, Any]:
        with self._connect() as conn:
            if automatic:
                conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (f"script-enqueue:{self.workspace_id}",),
                )
            request = self._request(conn, request_id, True)
            existing = conn.execute(
                "SELECT * FROM script_attempts WHERE workspace_id=%s AND request_id=%s AND id=%s",
                (self.workspace_id, request_id, body.id),
            ).fetchone()
            if existing:
                if (
                    existing["base_version"] != body.base_version
                    or existing["instruction"] != body.instruction
                ):
                    raise RegistryError(409, "work_conflict")
            else:
                if automatic:
                    pending = conn.execute(
                        "SELECT count(*) n FROM script_attempts WHERE workspace_id=%s "
                        "AND automatic AND status IN ('queued','running')",
                        (self.workspace_id,),
                    ).fetchone()
                    if pending and pending["n"] >= queue_limit:
                        raise RegistryError(429, "script_queue_full")
                self._stage(conn, request_id, body.expected_revision)
                self._idle(conn, request_id)
                if request["definition"]["tools"]:
                    raise RegistryError(422, "script_tools_unsupported")
                if (
                    not body.acknowledge_unknown
                    and conn.execute(
                        "SELECT id FROM script_attempts WHERE workspace_id=%s AND request_id=%s "
                        "AND status='unknown' LIMIT 1",
                        (self.workspace_id, request_id),
                    ).fetchone()
                ):
                    raise RegistryError(409, "script_unknown_ack_required")
                base = None
                if body.base_version:
                    base = conn.execute(
                        "SELECT title,narration,answer FROM script_versions "
                        "WHERE workspace_id=%s AND request_id=%s AND version=%s",
                        (self.workspace_id, request_id, body.base_version),
                    ).fetchone()
                    if base is None:
                        raise RegistryError(404, "script_version_not_found")
                previous_answer = (
                    base["answer"]
                    if base and base["answer"] is not None
                    else {k: base[k] for k in ["title", "narration"]}
                    if base
                    else None
                )
                prompt = json.dumps(
                    {
                        "agent_instructions": request["definition"]["instructions"],
                        "original_request": request["input"],
                        "input_schema": request["definition"]["input_schema"],
                        "previous_answer": previous_answer,
                        "output_schema": request["definition"]["output_schema"],
                        "revision_request": body.instruction,
                    },
                    ensure_ascii=False,
                )
                conn.execute(
                    "INSERT INTO script_attempts(workspace_id,request_id,id,base_version,"
                    "instruction,status,prompt,model_profile,provider,model,automatic) "
                    "VALUES (%s,%s,%s,%s,%s,'queued',%s,%s,%s,%s,%s)",
                    (
                        self.workspace_id,
                        request_id,
                        body.id,
                        body.base_version,
                        body.instruction,
                        prompt,
                        request["definition"]["model_profile"],
                        provider,
                        model,
                        automatic,
                    ),
                )
                conn.execute(
                    "UPDATE script_stages SET revision=revision+1 "
                    "WHERE workspace_id=%s AND request_id=%s",
                    (self.workspace_id, request_id),
                )
                conn.execute(
                    "UPDATE customer_requests SET status='queued',error=NULL,"
                    "updated_at=now() WHERE workspace_id=%s AND id=%s",
                    (self.workspace_id, request_id),
                )
        return self.get(request_id)

    def cancel(self, request_id: str, attempt_id: UUID) -> dict[str, Any]:
        with self._connect() as conn:
            self._request(conn, request_id, True)
            row = conn.execute(
                "SELECT status FROM script_attempts WHERE workspace_id=%s "
                "AND request_id=%s AND id=%s",
                (self.workspace_id, request_id, attempt_id),
            ).fetchone()
            if row is None:
                raise RegistryError(404, "work_not_found")
            if row["status"] not in ("queued", "cancelled"):
                raise RegistryError(409, "script_busy")
            if row["status"] == "queued":
                conn.execute(
                    "UPDATE customer_requests SET status='cancelled',updated_at=now() "
                    "WHERE workspace_id=%s AND id=%s",
                    (self.workspace_id, request_id),
                )
                conn.execute(
                    "UPDATE script_attempts SET status='cancelled',finished_at=now() "
                    "WHERE workspace_id=%s AND request_id=%s AND id=%s",
                    (self.workspace_id, request_id, attempt_id),
                )
                conn.execute(
                    "UPDATE script_stages SET revision=revision+1 "
                    "WHERE workspace_id=%s AND request_id=%s",
                    (self.workspace_id, request_id),
                )
        return self.get(request_id)

    def claim(
        self, request_id: str, attempt_id: str, provider: str, model: str
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            self._request(conn, request_id, True)
            attempt = conn.execute(
                "UPDATE script_attempts SET status='running',started_at=now(),provider=%s,model=%s "
                "WHERE workspace_id=%s AND request_id=%s AND id=%s AND status='queued' RETURNING *",
                (provider, model, self.workspace_id, request_id, attempt_id),
            ).fetchone()
            if attempt:
                conn.execute(
                    "UPDATE customer_requests SET status='running',updated_at=now() "
                    "WHERE workspace_id=%s AND id=%s",
                    (self.workspace_id, request_id),
                )
            return attempt

    def finish(
        self, request_id: str, attempt: dict[str, Any], result: Script | AgentAnswer | None
    ) -> None:
        with self._connect() as conn:
            self._request(conn, request_id, True)
            active = conn.execute(
                "SELECT status FROM script_attempts WHERE workspace_id=%s "
                "AND request_id=%s AND id=%s",
                (self.workspace_id, request_id, attempt["id"]),
            ).fetchone()
            if active is None or active["status"] != "running":
                raise RegistryError(409, "script_busy")
            stage = self._stage(conn, request_id)
            conn.execute(
                "UPDATE customer_requests SET status=%s,result=COALESCE(%s,result),"
                "error=%s,updated_at=now() WHERE workspace_id=%s AND id=%s",
                (
                    "succeeded" if result else "failed",
                    Jsonb(result.value if isinstance(result, AgentAnswer) else result.model_dump())
                    if result
                    else None,
                    None if result else ("AI 응답 시간 초과 · 결과와 사용량 확인이 필요합니다. "
                                         "자동 재시도하지 않습니다."
                                         if attempt.get("error_code") == "ai_timeout" else
                                         "AI 결과 확인 필요 · 자동 재시도하지 않습니다."),
                    self.workspace_id,
                    request_id,
                ),
            )
            version = None
            if result:
                if isinstance(result, AgentAnswer):
                    version = self._add_version(
                        conn,
                        request_id,
                        stage,
                        attempt["id"],
                        "",
                        "",
                        "ai",
                        attempt["base_version"],
                        attempt["instruction"],
                        result.value,
                    )
                else:
                    version = self._add_version(
                        conn,
                        request_id,
                        stage,
                        attempt["id"],
                        result.title,
                        result.narration,
                        "ai",
                        attempt["base_version"],
                        attempt["instruction"],
                    )
            else:
                conn.execute(
                    "UPDATE script_stages SET revision=revision+1 "
                    "WHERE workspace_id=%s AND request_id=%s",
                    (self.workspace_id, request_id),
                )
            conn.execute(
                "UPDATE script_attempts SET status=%s,result_version=%s,error_code=%s,"
                "finished_at=now() "
                "WHERE workspace_id=%s AND request_id=%s AND id=%s",
                (
                    "succeeded" if result else "unknown",
                    version,
                    attempt.get("error_code"),
                    self.workspace_id,
                    request_id,
                    attempt["id"],
                ),
            )


class ScriptState(TypedDict, total=False):
    prompt: str
    script: Script | AgentAnswer


def execute_attempt(
    repo: ScriptRepository,
    request_id: str,
    attempt_id: str,
    generate: Callable[[str], Script | AgentAnswer],
    provider: str = "test",
    model: str = "test",
) -> bool:
    attempt = repo.claim(request_id, attempt_id, provider, model)
    if attempt is None:
        return False

    def draft(state: ScriptState) -> ScriptState:
        result = generate(state["prompt"])
        if isinstance(result, AgentAnswer):
            schema = json.loads(state["prompt"])["output_schema"]
            if not valid_input(result.value, schema):
                raise ValueError("invalid_agent_output")
        elif not isinstance(result, Script):
            raise ValueError("invalid_agent_output")
        return {"script": result}

    graph = StateGraph(ScriptState)
    graph.add_node("script", draft)
    graph.add_edge(START, "script")
    graph.add_edge("script", END)
    with tracing_context(enabled=False):
        try:
            result = graph.compile().invoke({"prompt": attempt["prompt"]})
            script = result["script"]
        except Exception as exc:
            if is_timeout(exc):
                attempt = {**attempt, "error_code": "ai_timeout"}
            repo.finish(request_id, attempt, None)
            return True
    repo.finish(request_id, attempt, script)
    return True


def is_timeout(error: BaseException) -> bool:
    """Identify actual timeouts, not slow responses or arbitrary error messages."""
    import httpx

    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (TimeoutError, httpx.TimeoutException)):
            return True
        if type(current).__name__ == "APITimeoutError":
            return True
        current = current.__cause__ or current.__context__
    return False
