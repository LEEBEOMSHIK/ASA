from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.graph_automation import (
    Binding,
    GraphDefinition,
    graph_selection_issues,
    preview_graph,
    validate_graph,
)
from asa.registry.model_catalog import effective_settings
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError, ValidationIssue
from asa.registry.service import safe_number
from asa.tools.catalog import inspect_text


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    label: str = Field(min_length=1, max_length=80)
    tool_id: str = Field(max_length=120)
    review_after: bool = False
    bindings: dict[str, Binding] = Field(default_factory=dict, max_length=50)


class Automation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=400)
    steps: list[Step] = Field(default_factory=list, max_length=50)
    graph: GraphDefinition | None = None


def fields(schema: dict[str, Any]) -> dict[str, Any]:
    return schema.get("properties", {}) if schema.get("type") == "object" else {"$": schema}


def accepts(value: Any, schema: dict[str, Any]) -> bool:
    if "enum" in schema and value not in schema["enum"]:
        return False
    kind = schema.get("type")
    if kind == "object":
        props = schema.get("properties", {})
        return (isinstance(value, dict) and set(schema.get("required", [])) <= value.keys()
                and value.keys() <= props.keys()
                and all(accepts(v, props[k]) for k, v in value.items()))
    if kind == "array":
        return (isinstance(value, list)
                and schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 100)
                and all(accepts(v, schema.get("items", {})) for v in value))
    if kind == "string":
        return (isinstance(value, str)
                and schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 65536))
    if kind == "boolean":
        return type(value) is bool
    return (kind in ("integer", "number") and safe_number(value)
            and (kind != "integer" or type(value) is int)
            and schema.get("minimum", float("-inf")) <= value
            <= schema.get("maximum", float("inf")))


def check_flow(draft: Automation, tools: list[dict[str, Any]],
               settings: Settings | None = None) -> list[ValidationIssue]:
    if draft.graph is not None:
        if draft.steps:
            return [ValidationIssue(code="invalid_graph", field_path="steps",
                                    message="Cannot combine graph and steps.")]
        return validate_graph(draft.graph, tools, settings)
    catalog = {t["id"]: t for t in tools}
    outputs: dict[str, Any] = {"input": {"type": "string"}}
    issues: list[ValidationIssue] = []

    def issue(path: str, message: str) -> None:
        issues.append(ValidationIssue(code="invalid_mapping", field_path=path, message=message))

    if not draft.steps:
        issue("steps", "작업 블록을 하나 이상 추가하세요.")
    for step in draft.steps:
        path = step.id
        if step.id in outputs or step.id == "literal":
            issue(path, "블록 ID가 중복되거나 예약된 이름입니다.")
        tool = catalog.get(step.tool_id)
        if not tool or not tool.get("available"):
            issue(path, "사용할 수 있는 등록 에이전트 또는 도구를 선택하세요.")
            continue
        schema = tool["input_schema"]
        target_fields = fields(schema)
        required = schema.get("required", []) if schema.get("type") == "object" else ["$"]
        for key in required:
            if key not in step.bindings:
                issue(f"{path}.{key}", "필수 입력의 출처를 선택하세요.")
        for key, binding in step.bindings.items():
            target = target_fields.get(key)
            if target is None:
                issue(f"{path}.{key}", "이 블록에 없는 입력 항목입니다.")
                continue
            if binding.source == "literal":
                if not accepts(binding.value, target):
                    issue(f"{path}.{key}", "직접 입력한 값의 형식이나 범위를 확인하세요.")
                continue
            source = outputs.get(binding.source)
            if source is None:
                issue(f"{path}.{key}", "앞에 있는 블록의 결과만 연결할 수 있습니다.")
                continue
            if binding.field:
                source = source.get("properties", {}).get(binding.field)
            if source is None:
                issue(f"{path}.{key}", "선택한 결과 항목이 없습니다.")
            elif source.get("type") != target.get("type") and not (
                source.get("type") == "integer" and target.get("type") == "number"
            ):
                issue(f"{path}.{key}", "입력과 결과의 자료 형식이 다릅니다.")
        outputs[step.id] = tool["output_schema"]
    return issues


def preview_flow(draft: Automation, tools: list[dict[str, Any]], prompt: str,
                 samples: dict[str, Any], settings: Settings | None = None) -> list[dict[str, Any]]:
    issues = check_flow(draft, tools, settings)
    if issues:
        raise RegistryError(422, "invalid_definition", issues)
    if draft.graph is not None:
        return preview_graph(draft.graph, tools, prompt, samples)
    catalog = {t["id"]: t for t in tools}
    outputs: dict[str, Any] = {"input": prompt}
    results: list[dict[str, Any]] = []
    for step in draft.steps:
        tool = catalog[step.tool_id]
        values = {}
        try:
            for key, binding in step.bindings.items():
                value = binding.value if binding.source == "literal" else outputs[binding.source]
                if binding.source != "literal" and binding.field:
                    value = value[binding.field]
                values[key] = value
        except (KeyError, TypeError):
            results.append({"id": step.id, "kind": "invalid_input", "input": values,
                            "message": "앞 단계 결과에 연결한 항목이 없습니다."})
            break
        actual: Any = values if tool["input_schema"].get("type") == "object" else values.get("$")
        row: dict[str, Any] = {"id": step.id, "input": actual}
        if not accepts(actual, tool["input_schema"]):
            results.append({**row, "kind": "invalid_input", "message": "전달 값의 형식/범위 오류"})
            break
        if step.tool_id == "asa.text.inspect:1":
            output = inspect_text(actual["text"], actual["limit"])
            row["kind"] = "local_tool"
        elif step.id not in samples:
            results.append({**row, "kind": "needs_sample", "message": "샘플 결과를 입력하세요."})
            break
        else:
            output = samples[step.id]
            row["kind"] = "sample"
        if not accepts(output, tool["output_schema"]):
            results.append({**row, "kind": "invalid_sample", "message": "샘플 결과 형식 오류"})
            break
        row["output"] = output
        results.append(row)
        outputs[step.id] = output
    return results


class SaveAutomation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    revision: int = Field(ge=0, strict=True)
    draft: Automation


class Preview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft: Automation
    prompt: str = Field(max_length=6000)
    samples: dict[str, Any] = Field(default_factory=dict, max_length=50)


class AutomationRepository(RegistryRepository):
    def listing(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT id::text,revision,draft,updated_at::text FROM automation_drafts "
                "WHERE workspace_id=%s ORDER BY updated_at DESC,id LIMIT 200",
                (self.workspace_id,),
            ).fetchall()

    def save(self, body: SaveAutomation) -> dict[str, Any]:
        with self._connect() as conn:
            if body.revision == 0:
                conn.execute(
                    "INSERT INTO automation_drafts(workspace_id,id,draft) VALUES (%s,%s,%s) "
                    "ON CONFLICT DO NOTHING",
                    (self.workspace_id, body.id, Jsonb(body.draft.model_dump())),
                )
            row = conn.execute(
                "SELECT id::text,revision,draft FROM automation_drafts "
                "WHERE workspace_id=%s AND id=%s FOR UPDATE", (self.workspace_id, body.id),
            ).fetchone()
            if row is None:
                raise RegistryError(404, "automation_not_found")
            payload = body.draft.model_dump()
            if body.revision == 0 and row["revision"] == 1 and row["draft"] == payload:
                return row
            if row["revision"] != body.revision:
                raise RegistryError(409, "revision_conflict")
            return conn.execute(
                "UPDATE automation_drafts SET draft=%s,revision=revision+1,updated_at=now() "
                "WHERE workspace_id=%s AND id=%s RETURNING id::text,revision,draft",
                (Jsonb(payload), self.workspace_id, body.id),
            ).fetchone() or {}


def automation_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/automations")

    def repo(principal: Principal = Depends(sessions.principal)) -> AutomationRepository:
        return AutomationRepository(settings.database_url, principal.workspace_id)

    @router.get("")
    def listing(repository: AutomationRepository = Depends(repo)) -> list[dict[str, Any]]:
        return repository.listing()

    @router.post("")
    def save(body: SaveAutomation,
             repository: AutomationRepository = Depends(repo)) -> dict[str, Any]:
        if body.draft.graph is not None:
            issues = graph_selection_issues(body.draft.graph, effective_settings(
                settings.model_copy(update={"workspace_id": repository.workspace_id})))
            if issues:
                raise RegistryError(422, "invalid_definition", issues)
        return repository.save(body)

    @router.post("/validate")
    def validate(body: Automation,
                 repository: AutomationRepository = Depends(repo)) -> dict[str, Any]:
        return {"issues": check_flow(body, repository.tools(), effective_settings(
            settings.model_copy(update={"workspace_id": repository.workspace_id}))),
                "execution_available": False}

    @router.post("/preview")
    def preview(body: Preview,
                repository: AutomationRepository = Depends(repo)) -> dict[str, Any]:
        return {"results": preview_flow(body.draft, repository.tools(), body.prompt,
                                        body.samples, effective_settings(settings.model_copy(
                                            update={"workspace_id": repository.workspace_id}))),
                "mode": "connection_test", "paid_calls": 0}

    return router
