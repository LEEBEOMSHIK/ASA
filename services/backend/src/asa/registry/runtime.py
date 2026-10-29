from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.automations import Automation, check_flow
from asa.registry.graph_automation import GraphNode, ai_tool
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError
from asa.tools.search import SEARCH_ID, search_ready

SEOUL = timezone(timedelta(hours=9))


def next_daily(value: str, now: datetime) -> datetime:
    hour, minute = map(int, value.split(":"))
    local = now.astimezone(SEOUL)
    target = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return target.astimezone(UTC)


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    revision: int = Field(ge=1, strict=True)
    prompt: str = Field(min_length=1, max_length=6000)


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    next_step: int = Field(ge=1, le=200, strict=True)


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1, strict=True)
    schedule_revision: int = Field(ge=0, strict=True)
    enabled: bool
    kind: Literal["once", "daily"]
    time: str = Field(default="09:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    at: datetime | None = None
    prompt: str = Field(min_length=1, max_length=6000)


class RunRepository(RegistryRepository):
    def __init__(self, settings: Settings, requested_by: str | None = None):
        super().__init__(settings.database_url, settings.workspace_id)
        self.settings = settings
        self.requested_by = requested_by

    def ai_ready(self, model: str | None = None, provider: str = "openai") -> bool:
        return bool(self.settings.automation_ai_enabled
                    and (model or self.settings.ai_model) in self.settings.models_for(provider)
                    and self.settings.key_for(provider).get_secret_value().strip())

    def model_available(self, tool: dict[str, Any]) -> bool:
        return bool(tool["provider"] in ("openai", "anthropic")
                    and self.ai_ready(tool["model"], tool["provider"])
                    and (not tool.get("web_search") or self.settings.search_supported(
                        tool["provider"], tool["model"]))
                    and (tool.get("model_selected", False)
                         or tool["model"] == self.settings.ai_model))

    def snapshot(self, automation_id: UUID, revision: int) -> tuple[dict[str, Any], list[Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT draft,revision FROM automation_drafts WHERE workspace_id=%s "
                               "AND id=%s", (self.workspace_id, automation_id)).fetchone()
            if not row:
                raise RegistryError(404, "automation_not_found")
            if row["revision"] != revision:
                raise RegistryError(409, "revision_conflict")
            draft = Automation.model_validate(row["draft"])
            tools = self._tools(conn)
            issues = check_flow(draft, tools, self.settings)
            if issues:
                raise RegistryError(422, "invalid_definition", issues)
            catalog = {t["id"]: t for t in tools}
            manifest = []
            ai_count = 0
            executable = ([n for n in draft.graph.nodes if n.kind in ('ai', 'tool')]
                          if draft.graph else draft.steps)
            for step in executable:
                inline = getattr(step, "kind", None) == "ai"
                tool = (ai_tool(step) if isinstance(step, GraphNode) and inline
                        else dict(catalog[step.tool_id]))
                if draft.graph:
                    tool["node_id"] = step.id
                if tool["kind"] == "agent" and not inline:
                    agent = conn.execute(
                        "SELECT definition FROM registry_versions WHERE workspace_id=%s "
                        "AND agent_id=%s AND version=%s",
                        (self.workspace_id, tool["agent_id"], tool["version"]),
                    ).fetchone()
                    assert agent
                    tool["definition"] = agent["definition"]
                if tool["kind"] == "agent":
                    if tool["definition"]["tools"]:
                        raise RegistryError(422, "runtime_nested_tools_unsupported")
                    selected = step.model if isinstance(step, GraphNode) and inline else None
                    model = selected or self.settings.ai_model
                    provider = (step.provider or self.settings.ai_provider
                                if isinstance(step, GraphNode) and inline
                                else self.settings.ai_provider)
                    if not self.ai_ready(model, provider):
                        raise RegistryError(422, "runtime_ai_unconfigured")
                    tool["provider"] = provider
                    tool["model"] = model
                    tool["model_selected"] = selected is not None
                    ai_count += 1
                elif step.tool_id == SEARCH_ID:
                    if not search_ready(self.settings):
                        raise RegistryError(422, "runtime_search_unconfigured")
                    tool["search_provider"] = self.settings.search_provider
                elif step.tool_id != "asa.text.inspect:1":
                    raise RegistryError(422, "runtime_tool_unavailable")
                manifest.append(tool)
            if ai_count > 20:
                raise RegistryError(422, "runtime_call_limit")
            return draft.model_dump(), manifest

    def enqueue(self, automation_id: UUID, body: RunInput) -> dict[str, Any]:
        # Serialize enqueue per workspace, including duplicate IDs and queue limits.
        with self._connect() as conn:
            conn.execute("SELECT id FROM registry_workspaces WHERE id=%s FOR UPDATE",
                         (self.workspace_id,))
            old = conn.execute("SELECT * FROM automation_runs WHERE workspace_id=%s AND id=%s",
                               (self.workspace_id, body.id)).fetchone()
            if old:
                if (old["automation_id"] != automation_id or old["revision"] != body.revision
                        or old["prompt"] != body.prompt):
                    raise RegistryError(409, "runtime_id_conflict")
                return {"id": str(body.id), "status": old["status"]}
            definition, manifest = self.snapshot(automation_id, body.revision)
            count = conn.execute("SELECT count(*) AS n FROM automation_runs WHERE workspace_id=%s "
                                 "AND status IN ('queued','running','waiting_review')",
                                 (self.workspace_id,)).fetchone()
            if count and count["n"] >= 100:
                raise RegistryError(409, "runtime_queue_full")
            conn.execute("INSERT INTO automation_runs(workspace_id,id,automation_id,revision,"
                         "definition,manifest,prompt,requested_by) "
                         "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                         (self.workspace_id, body.id, automation_id, body.revision,
                          Jsonb(definition), Jsonb(manifest), body.prompt, self.requested_by))
        return {"id": str(body.id), "status": "queued"}

    def runs(self, automation_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return conn.execute("SELECT id::text,status,revision,created_at::text,error "
                                "FROM automation_runs WHERE workspace_id=%s AND automation_id=%s "
                                "ORDER BY created_at DESC LIMIT 50",
                                (self.workspace_id, automation_id)).fetchall()

    def detail(self, run_id: UUID) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT id::text,automation_id::text,revision,definition,prompt,"
                               "status,steps,next_step,error,created_at::text,updated_at::text "
                               "FROM automation_runs WHERE workspace_id=%s AND id=%s",
                               (self.workspace_id, run_id)).fetchone()
            if not row:
                raise RegistryError(404, "runtime_not_found")
            return row

    def transition(self, run_id: UUID, approve: bool,
                   expected_step: int | None = None) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT status,next_step FROM automation_runs WHERE workspace_id=%s "
                               "AND id=%s FOR UPDATE", (self.workspace_id, run_id)).fetchone()
            if not row:
                raise RegistryError(404, "runtime_not_found")
            allowed = ("waiting_review",) if approve else ("queued", "waiting_review")
            if row["status"] not in allowed:
                raise RegistryError(409, "runtime_state_conflict")
            if approve and row["next_step"] != expected_step:
                raise RegistryError(409, "runtime_state_conflict")
            conn.execute("UPDATE automation_runs SET status=%s,updated_at=now() "
                         "WHERE workspace_id=%s AND id=%s",
                         ("queued" if approve else "cancelled", self.workspace_id, run_id))
        return self.detail(run_id)

    def schedule(self, automation_id: UUID) -> dict[str, Any] | None:
        with self._connect() as conn:
            return conn.execute("SELECT revision,enabled,kind,time,next_at::text,prompt,"
                                "definition_revision,note FROM automation_schedules "
                                "WHERE workspace_id=%s AND automation_id=%s",
                                (self.workspace_id, automation_id)).fetchone()

    def save_schedule(self, automation_id: UUID, body: ScheduleInput) -> dict[str, Any]:
        definition, manifest = self.snapshot(automation_id, body.revision)
        now = datetime.now(UTC)
        target = next_daily(body.time, now) if body.kind == "daily" else body.at
        if body.enabled and (target is None or target.tzinfo is None or target <= now):
            raise RegistryError(422, "runtime_schedule_time")
        with self._connect() as conn:
            conn.execute("SELECT id FROM registry_workspaces WHERE id=%s FOR UPDATE",
                         (self.workspace_id,))
            old = conn.execute("SELECT revision FROM automation_schedules WHERE workspace_id=%s "
                               "AND automation_id=%s FOR UPDATE",
                               (self.workspace_id, automation_id)).fetchone()
            if (old["revision"] if old else 0) != body.schedule_revision:
                raise RegistryError(409, "revision_conflict")
            conn.execute("INSERT INTO automation_schedules(workspace_id,automation_id,enabled,"
                         "kind,time,next_at,prompt,definition,manifest,definition_revision,"
                         "requested_by) "
                         "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT "
                         "(workspace_id,automation_id) DO UPDATE SET revision=automation_schedules."
                         "revision+1,enabled=EXCLUDED.enabled,kind=EXCLUDED.kind,time=EXCLUDED.time,"
                         "next_at=EXCLUDED.next_at,prompt=EXCLUDED.prompt,definition=EXCLUDED.definition,"
                         "manifest=EXCLUDED.manifest,definition_revision=EXCLUDED.definition_revision,"
                         "note='',requested_by=EXCLUDED.requested_by",
                         (self.workspace_id, automation_id, body.enabled, body.kind,
                                     body.time, target, body.prompt, Jsonb(definition),
                                     Jsonb(manifest), body.revision, self.requested_by))
        return self.schedule(automation_id) or {}

    def disable_schedule(self, automation_id: UUID) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE automation_schedules SET enabled=false,revision=revision+1 "
                         "WHERE workspace_id=%s AND automation_id=%s",
                         (self.workspace_id, automation_id))

    def dispatch_due(self, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        dispatched = 0
        with self._connect() as conn:
            conn.execute("SELECT id FROM registry_workspaces WHERE id=%s FOR UPDATE",
                         (self.workspace_id,))
            rows = conn.execute("SELECT * FROM automation_schedules WHERE workspace_id=%s "
                                "AND enabled=true AND next_at<=%s FOR UPDATE SKIP LOCKED",
                                (self.workspace_id, now)).fetchall()
            for row in rows:
                count = conn.execute("SELECT count(*) AS n FROM automation_runs "
                                     "WHERE workspace_id=%s AND status IN "
                                     "('queued','running','waiting_review')",
                                     (self.workspace_id,)).fetchone()
                if count and count["n"] >= 100:
                    continue  # Keep the due occurrence pending until capacity is available.
                active = conn.execute("SELECT id FROM automation_runs WHERE workspace_id=%s "
                                      "AND automation_id=%s AND status IN "
                                      "('queued','running','waiting_review') LIMIT 1",
                                      (self.workspace_id, row["automation_id"])).fetchone()
                note = "이전 작업이 진행 중이어서 이번 예약을 건너뛰었습니다." if active else ""
                ai_blocked = any(t["kind"] == "agent" and not self.model_available(t)
                                 for t in row["manifest"])
                if ai_blocked:
                    note = "AI 설정을 확인한 뒤 예약을 다시 켜 주세요."
                if not active and not ai_blocked:
                    conn.execute("INSERT INTO automation_runs(workspace_id,id,automation_id,"
                                 "revision,definition,manifest,prompt,schedule_id,occurrence,"
                                 "requested_by) "
                                 "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                                 (self.workspace_id, uuid4(), row["automation_id"],
                                  row["definition_revision"], Jsonb(row["definition"]),
                                  Jsonb(row["manifest"]), row["prompt"], row["automation_id"],
                                  row["next_at"], row.get("requested_by")))
                    dispatched += 1
                conn.execute("UPDATE automation_schedules SET revision=revision+1,"
                             "enabled=%s,next_at=%s,note=%s "
                             "WHERE workspace_id=%s AND automation_id=%s",
                             (row["kind"] == "daily" and not ai_blocked,
                              next_daily(row["time"], now) if row["kind"] == "daily" else None,
                              note, self.workspace_id, row["automation_id"]))
        return dispatched

    def status(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT seen_at::text,seen_at>now()-interval '6 minutes' AS online "
                               "FROM automation_worker_status WHERE workspace_id=%s",
                               (self.workspace_id,)).fetchone()
        return {"worker_online": bool(row and row["online"]), "last_seen": row["seen_at"] if row
                else None, "ai_ready": self.ai_ready(), "daily_call_limit":
                self.settings.automation_daily_ai_calls}


def runtime_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def repo(principal: Principal = Depends(sessions.principal)) -> RunRepository:
        return RunRepository(settings.model_copy(update={"workspace_id": principal.workspace_id}),
                             principal.user_id)

    @router.get("/automation-runtime")
    def status(repository: RunRepository = Depends(repo)) -> dict[str, Any]:
        return repository.status()

    @router.post("/automations/{automation_id}/runs", status_code=201)
    def enqueue(automation_id: UUID, body: RunInput,
                repository: RunRepository = Depends(repo)) -> dict[str, Any]:
        return repository.enqueue(automation_id, body)

    @router.get("/automations/{automation_id}/runs")
    def runs(automation_id: UUID,
             repository: RunRepository = Depends(repo)) -> list[dict[str, Any]]:
        return repository.runs(automation_id)

    @router.get("/automation-runs/{run_id}")
    def detail(run_id: UUID, repository: RunRepository = Depends(repo)) -> dict[str, Any]:
        return repository.detail(run_id)

    @router.post("/automation-runs/{run_id}/approve")
    def approve(run_id: UUID, body: ApprovalInput,
                repository: RunRepository = Depends(repo)) -> dict[str, Any]:
        return repository.transition(run_id, True, body.next_step)

    @router.post("/automation-runs/{run_id}/cancel")
    def cancel(run_id: UUID, repository: RunRepository = Depends(repo)) -> dict[str, Any]:
        return repository.transition(run_id, False)

    @router.get("/automations/{automation_id}/schedule")
    def schedule(automation_id: UUID,
                 repository: RunRepository = Depends(repo)) -> dict[str, Any] | None:
        return repository.schedule(automation_id)

    @router.put("/automations/{automation_id}/schedule")
    def save_schedule(automation_id: UUID, body: ScheduleInput,
                      repository: RunRepository = Depends(repo)) -> dict[str, Any]:
        return repository.save_schedule(automation_id, body)

    @router.delete("/automations/{automation_id}/schedule")
    def disable_schedule(automation_id: UUID,
                         repository: RunRepository = Depends(repo)) -> dict[str, str]:
        repository.disable_schedule(automation_id)
        return {"status": "disabled"}

    return router
