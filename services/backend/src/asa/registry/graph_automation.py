"""Bounded graph definitions and shared, non-executable control evaluator."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from asa.config import Settings
from asa.registry.schemas import ValidationIssue
from asa.registry.service import safe_number


class Binding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(max_length=80)
    field: str = Field(default="", max_length=100)
    value: Any = None


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left: Binding
    operator: Literal["equals", "not_equals", "contains", "greater_than", "less_than", "is_true"]
    right: Any = None


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
    label: str = Field(min_length=1, max_length=80)
    kind: Literal["start", "tool", "ai", "condition", "repeat", "end", "map"]
    x: float = Field(default=0, ge=-100000, le=100000, allow_inf_nan=False)
    y: float = Field(default=0, ge=-100000, le=100000, allow_inf_nan=False)
    tool_id: str | None = Field(default=None, max_length=120)
    bindings: dict[str, Binding] = Field(default_factory=dict, max_length=50)
    instructions: str = Field(default="", max_length=12000)
    model: str | None = Field(default=None, min_length=1, max_length=200,
                             exclude_if=lambda value: value is None)
    provider: Literal["openai", "anthropic"] | None = Field(
        default=None, exclude_if=lambda value: value is None)
    web_search: bool = Field(default=False, strict=True, exclude_if=lambda value: not value)
    output_type: Literal["text", "list"] = "text"
    condition: Condition | None = None
    items: Binding | None = None
    max_items: int = Field(default=20, ge=1, le=20, strict=True)
    output_fields: dict[str, Literal["text", "number", "boolean", "text-list"]] = Field(
        default_factory=dict, max_length=20, exclude_if=lambda value: not value)
    review_after: bool = False


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=80)
    source: str = Field(max_length=64)
    target: str = Field(max_length=64)
    port: Literal["next", "yes", "no", "item", "done"]


class GraphDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: list[GraphNode] = Field(max_length=50)
    edges: list[GraphEdge] = Field(max_length=100)


def ai_tool(node: GraphNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "node_id": node.id,
        "web_search": node.web_search,
        "kind": "agent",
        "available": True,
        "input_schema": {"type": "string", "maxLength": 65536},
        "output_schema": (
            {"type": "array", "items": {"type": "string"}, "maxItems": 20}
            if node.output_type == "list"
            else {"type": "string"}
        ),
        "definition": {"instructions": node.instructions, "tools": [], "limits": {"seconds": 120}},
    }


def mapping_tool(node: GraphNode) -> dict[str, Any]:
    types: dict[str, Any] = {"text": {"type": "string"}, "number": {"type": "number"},
                            "boolean": {"type": "boolean"},
                            "text-list": {"type": "array", "items": {"type": "string"}}}
    schema = {"type": "object", "properties": {k: types[v] for k, v in node.output_fields.items()},
              "required": list(node.output_fields)}
    return {"available": True, "input_schema": schema, "output_schema": schema}


def graph_selection_issues(graph: GraphDefinition, settings: Settings | None = None
                           ) -> list[ValidationIssue]:
    issues = []
    if sum(n.kind == "end" for n in graph.nodes) != 1:
        issues.append(ValidationIssue(code="invalid_graph", field_path="graph",
                                     message="최종 결과 블록은 하나여야 합니다."))
    for node in graph.nodes:
        provider = node.provider or (settings.ai_provider if settings else "openai")
        allowed = settings.models_for(provider) if settings else []
        if node.web_search and (node.kind != "ai" or node.output_type != "text" or not settings
                or not settings.search_supported(provider, node.model or settings.ai_model)):
            issues.append(ValidationIssue(code="invalid_model", field_path=f"{node.id}.web_search",
                                         message="검색 지원 모델과 하나의 글 형식을 선택하세요."))
        if node.provider is not None and (node.kind != "ai" or (
                not node.model and (not settings or provider != settings.ai_provider))):
            issues.append(ValidationIssue(code="invalid_model", field_path=f"{node.id}.provider",
                                         message="Claude를 사용할 모델을 선택하세요."))
        if node.model is not None and (node.kind != "ai" or node.model not in allowed):
            issues.append(ValidationIssue(code="invalid_model", field_path=f"{node.id}.model",
                                         message="서버에 등록된 사용 가능한 AI 모델을 선택하세요."))
    return issues


def validate_graph(graph: GraphDefinition, tools: list[dict[str, Any]],
                   settings: Settings | None = None) -> list[ValidationIssue]:
    # Imports here keep legacy public helpers compatible.
    from asa.registry.automations import accepts, fields

    issues: list[ValidationIssue] = graph_selection_issues(graph, settings)

    def issue(node: str, message: str) -> None:
        issues.append(ValidationIssue(code="invalid_graph", field_path=node, message=message))

    nodes = {n.id: n for n in graph.nodes}
    catalog = {t["id"]: t for t in tools}
    if len(nodes) != len(graph.nodes) or {"input", "literal"} & nodes.keys():
        issue("graph", "블록 ID는 중복되거나 예약된 이름일 수 없습니다.")
    starts = [n.id for n in graph.nodes if n.kind == "start"]
    if len(starts) != 1:
        issue("graph", "시작 블록은 하나여야 합니다.")
    if len({e.id for e in graph.edges}) != len(graph.edges):
        issue("graph", "연결 ID가 중복됩니다.")
    outgoing: dict[str, dict[str, str]] = {n: {} for n in nodes}
    for e in graph.edges:
        if e.source not in nodes or e.target not in nodes or e.target in starts:
            issue(e.id, "연결 대상이 없거나 시작 블록으로 돌아가는 연결입니다.")
        elif e.port in outgoing[e.source]:
            issue(e.id, "같은 출력에는 연결 하나만 허용됩니다.")
        else:
            outgoing[e.source][e.port] = e.target
    ports = {
        "start": {"next"},
        "tool": {"next"},
        "ai": {"next"},
        "condition": {"yes", "no"},
        "repeat": {"item", "done"},
        "end": set(), "map": {"next"},
    }
    for n in graph.nodes:
        if set(outgoing[n.id]) != ports[n.kind]:
            issue(n.id, "블록 종류에 맞는 출력 연결을 모두 지정하세요.")
        if n.kind == "condition" and n.condition is None:
            issue(n.id, "조건을 입력하세요.")
        if n.kind == "repeat" and n.items is None:
            issue(n.id, "반복할 목록을 연결하세요.")
        if n.kind == "ai" and not n.instructions.strip():
            issue(n.id, "AI 지시문을 입력하세요.")
        tool = (ai_tool(n) if n.kind == "ai" else mapping_tool(n) if n.kind == "map"
                else catalog.get(n.tool_id or ""))
        if n.kind in ("ai", "tool", "map"):
            if not tool or not tool.get("available"):
                issue(n.id, "사용 가능한 도구를 선택하세요.")
            else:
                schema = tool["input_schema"]
                required = schema.get("required", []) if schema.get("type") == "object" else ["$"]
                if not set(required) <= n.bindings.keys():
                    issue(n.id, "필수 입력을 연결하세요.")
                for key, binding in n.bindings.items():
                    target = fields(schema).get(key)
                    if target is None or (
                        binding.source == "literal" and not accepts(binding.value, target)
                    ):
                        issue(n.id, "입력 항목의 형식 또는 값이 잘못되었습니다.")
        if n.kind == "map" and (not n.output_fields or any(
                not k.strip() or len(k) > 80 or "." in k or k.startswith("__")
                for k in n.output_fields)):
            issue(n.id, "항목 이름은 1~80자여야 합니다. 점 또는 __ 접두사는 사용할 수 없습니다.")
        bindings = list(n.bindings.values())
        if n.items:
            bindings.append(n.items)
        if n.condition:
            bindings.append(n.condition.left)
        for b in bindings:
            if b.source not in {"literal", "input"} | nodes.keys():
                issue(n.id, "입력 출처 블록이 없습니다.")
            if b.field and any(not p or p.startswith("__") for p in b.field.split(".")):
                issue(n.id, "안전한 점 구분 결과 경로를 사용하세요.")
    output_schemas: dict[str, Any] = {"input": {"type": "string"}}
    for n in graph.nodes:
        if n.kind == "ai":
            output_schemas[n.id] = ai_tool(n)["output_schema"]
        elif n.kind == "map":
            output_schemas[n.id] = mapping_tool(n)["output_schema"]
        elif n.kind == "tool" and n.tool_id in catalog:
            output_schemas[n.id] = catalog[n.tool_id]["output_schema"]
        elif n.kind == "start":
            output_schemas[n.id] = {"type": "string"}
        elif n.kind == "condition":
            output_schemas[n.id] = {"type": "boolean"}
        elif n.kind == "repeat":
            output_schemas[n.id] = {
                "type": "object",
                "properties": {
                    "item": {},
                    "index": {"type": "integer"},
                    "results": {"type": "array", "items": {}},
                },
            }
    for n in graph.nodes:
        tool = (ai_tool(n) if n.kind == "ai" else mapping_tool(n) if n.kind == "map"
                else catalog.get(n.tool_id or ""))
        for key, binding in n.bindings.items():
            if binding.source == "literal":
                continue
            source_schema = output_schemas.get(binding.source, {})
            for part in binding.field.split(".") if binding.field else []:
                if not source_schema:
                    break  # Dynamic repeat item/results are checked at execution time.
                if source_schema.get("type") == "array" and part.isdigit():
                    source_schema = source_schema.get("items", {})
                elif source_schema.get("type") == "object":
                    source_schema = source_schema.get("properties", {}).get(part)
                    if source_schema is None:
                        issue(n.id, "선택한 결과 항목이 없습니다.")
                        break
                else:
                    issue(n.id, "선택한 결과 항목이 없습니다.")
                    source_schema = None
                    break
            if tool and source_schema and n.kind in ("ai", "tool", "map"):
                target = fields(tool["input_schema"]).get(key, {})
                if source_schema.get("type") != target.get("type") and not (
                    source_schema.get("type") == "integer" and target.get("type") == "number"
                ):
                    issue(n.id, "입력과 결과의 자료 형식이 다릅니다.")
    if issues:
        return issues
    # Expand each bounded repeat once. Every body path must return to its owner;
    # a node cannot be shared across body and main scopes or across repeat bodies.
    owners: dict[str, str | None] = {}
    visited: set[tuple[str, str | None]] = set()

    def walk(key: str, owner: str | None, stack: set[str]) -> None:
        if key == owner:
            return
        if key in stack:
            issue(key, "반복 블록으로 돌아가는 연결 외 순환은 허용되지 않습니다.")
            return
        if key in owners and owners[key] != owner:
            issue(key, "반복 내부와 외부 경로를 공유할 수 없습니다.")
            return
        owners[key] = owner
        if (key, owner) in visited:
            return
        visited.add((key, owner))
        n = nodes[key]
        if owner and n.kind in ("repeat", "end"):
            issue(key, "중첩 반복은 지원하지 않으며 반복 본문은 소유 반복으로 돌아와야 합니다.")
            return
        if n.kind == "repeat":
            if outgoing[key]["item"] == key:
                issue(key, "반복 본문에 작업 또는 조건 블록이 필요합니다.")
            walk(outgoing[key]["item"], key, stack | {key})
            walk(outgoing[key]["done"], owner, stack | {key})
        else:
            for target in outgoing[key].values():
                walk(target, owner, stack | {key})

    walk(starts[0], None, set())
    if set(owners) != set(nodes):
        issue("graph", "시작에서 도달하지 못하는 블록이 있습니다.")
    # Dominators on the acyclic skeleton guarantee all referenced outputs exist.
    # Repeat return edges do not make previous-iteration body values available.
    if not issues:
        predecessors: dict[str, set[str]] = {key: set() for key in nodes}
        for e in graph.edges:
            if owners.get(e.source) == e.target:
                continue
            predecessors[e.target].add(e.source)
        dom = {key: ({key} if key == starts[0] else set(nodes)) for key in nodes}
        changed = True
        while changed:
            changed = False
            for key in nodes:
                if key == starts[0]:
                    continue
                prior = predecessors[key]
                value = {key} | (set.intersection(*(dom[p] for p in prior)) if prior else set())
                if value != dom[key]:
                    dom[key] = value
                    changed = True
        for n in graph.nodes:
            bindings = list(n.bindings.values()) + ([n.items] if n.items else [])
            if n.condition:
                bindings.append(n.condition.left)
            for b in bindings:
                if b.source in nodes and (b.source == n.id or b.source not in dom[n.id]):
                    issue(n.id, "모든 경로에서 먼저 실행되는 블록의 결과만 연결하세요.")
                if b.source in nodes and nodes[b.source].kind == "repeat":
                    inside = owners.get(n.id) == b.source
                    allowed = ("item", "index") if inside else ("results",)
                    if b.field.split(".")[0] not in allowed:
                        issue(n.id, "반복 내부는 item/index, 외부는 results를 연결하세요.")
    # Body values are local to an iteration. Only repeat.results crosses its boundary.
    for n in graph.nodes:
        bindings = list(n.bindings.values()) + ([n.items] if n.items else [])
        if n.condition:
            bindings.append(n.condition.left)
        for b in bindings:
            if (
                b.source in owners
                and owners[b.source] is not None
                and owners[b.source] != owners.get(n.id)
            ):
                issue(n.id, "반복 밖에서는 반복 블록의 results를 연결하세요.")
    return issues


def resolve(binding: Binding, outputs: dict[str, Any]) -> Any:
    if binding.source == "literal":
        return binding.value
    if binding.source not in outputs:
        raise ValueError("연결한 블록이 이 경로에서 실행되지 않았습니다.")
    value = outputs[binding.source]
    for part in binding.field.split(".") if binding.field else []:
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise ValueError("연결한 결과 항목이 없거나 형식이 다릅니다.")
    return value


def condition_value(condition: Condition, outputs: dict[str, Any]) -> bool:
    left, right = resolve(condition.left, outputs), condition.right
    op = condition.operator
    if op == "is_true":
        if type(left) is not bool:
            raise ValueError("참/거짓 조건에는 논리 값이 필요합니다.")
        return bool(left)
    if op in ("equals", "not_equals"):
        equal = type(left) is type(right) and left == right
        return bool(equal if op == "equals" else not equal)
    if op == "contains":
        if isinstance(left, str) and isinstance(right, str):
            return right in left
        if isinstance(left, list):
            return right in left
        raise ValueError("포함 조건에는 문자열 또는 목록이 필요합니다.")
    if not safe_number(left) or not safe_number(right):
        raise ValueError("크기 비교에는 숫자가 필요합니다.")
    return bool(left > right if op == "greater_than" else left < right)


class Evaluator:
    """One durable transition at a time; callers own paid calls and transactions."""

    def __init__(self, graph: GraphDefinition, prompt: str, state: dict[str, Any] | None = None):
        self.nodes = {n.id: n for n in graph.nodes}
        self.edges: dict[tuple[str, str], str] = {(e.source, e.port): e.target for e in graph.edges}
        self.state = state or {
            "current": next(n.id for n in graph.nodes if n.kind == "start"),
            "outputs": {"input": prompt},
            "loop": None,
            "count": 0,
            "last": prompt,
        }

    @property
    def node(self) -> GraphNode:
        return self.nodes[str(self.state["current"])]

    def input(self) -> Any:
        n = self.node
        outputs = self.state["outputs"]
        if n.kind == "condition":
            assert n.condition
            return condition_value(n.condition, outputs)
        if n.kind == "repeat":
            assert n.items
            return resolve(n.items, outputs) if self.state["loop"] is None else None
        return {k: resolve(b, outputs) for k, b in n.bindings.items()}

    def advance(self, actual: Any, output: Any = None) -> dict[str, Any]:
        n, s = self.node, self.state
        if s["count"] >= 200:
            raise ValueError("실행 블록 상한 200개를 초과했습니다.")
        port = "next"
        if n.kind == "start":
            output = s["outputs"]["input"]
        elif n.kind == "condition":
            output, port = actual, "yes" if actual else "no"
        elif n.kind == "map":
            from asa.registry.automations import accepts
            if not accepts(actual, mapping_tool(n)["output_schema"]):
                raise ValueError("결과 항목의 자료형 또는 값이 올바르지 않습니다.")
            output = actual
        elif n.kind == "end":
            output = actual.get("$", s["last"])
        elif n.kind == "repeat":
            loop = s["loop"]
            if loop is None:
                if not isinstance(actual, list) or len(actual) > n.max_items:
                    raise ValueError("반복 입력은 최대 20개(설정 상한 이내)의 목록이어야 합니다.")
                loop = {
                    "id": n.id,
                    "items": actual,
                    "index": 0,
                    "results": [],
                    "baseline": dict(s["outputs"]),
                }
                s["loop"] = loop
            else:
                loop["results"].append(s["last"])
                loop["index"] += 1
            s["outputs"] = dict(loop["baseline"])
            if loop["index"] < len(loop["items"]):
                output = {"item": loop["items"][loop["index"]], "index": loop["index"]}
                port = "item"
            else:
                output, port = {"results": loop["results"]}, "done"
                s["loop"] = None
        row = {
            "id": f"{n.id}:{s['count']}",
            "node_id": n.id,
            "label": n.label,
            "status": "succeeded",
            "input": actual,
            "output": output,
        }
        if s["loop"] is not None:
            row["iteration"] = s["loop"]["index"]
        s["outputs"][n.id] = output
        s["last"] = output
        s["count"] += 1
        s["current"] = None if n.kind == "end" else self.edges[(n.id, port)]
        return row


def preview_graph(
    graph: GraphDefinition, tools: list[dict[str, Any]], prompt: str, samples: dict[str, Any]
) -> list[dict[str, Any]]:
    from asa.registry.automations import accepts
    from asa.tools.catalog import inspect_text

    ev = Evaluator(graph, prompt)
    catalog = {t["id"]: t for t in tools}
    rows: list[dict[str, Any]] = []
    while ev.state["current"]:
        n = ev.node
        kind = "control"
        actual: Any = None
        try:
            if ev.state["count"] >= 200:
                raise ValueError("실행 블록 상한 200개를 초과했습니다.")
            actual = ev.input()
            output = None
            if n.kind in ("ai", "tool"):
                tool = ai_tool(n) if n.kind == "ai" else catalog[n.tool_id or ""]
                actual = actual if tool["input_schema"]["type"] == "object" else actual.get("$")
                if not accepts(actual, tool["input_schema"]):
                    raise ValueError("전달 값의 형식/범위 오류")
                if n.kind == "tool" and n.tool_id == "asa.text.inspect:1":
                    output, kind = inspect_text(actual["text"], actual["limit"]), "local_tool"
                else:
                    kind = "needs_sample"
                    if n.id not in samples:
                        raise ValueError("샘플 결과를 입력하세요.")
                    output, kind = samples[n.id], "invalid_sample"
                if not accepts(output, tool["output_schema"]):
                    raise ValueError("샘플 결과 형식 오류")
                if kind == "invalid_sample":
                    kind = "sample"
            rows.append({**ev.advance(actual, output), "kind": kind})
        except (ValueError, KeyError, TypeError) as exc:
            rows.append(
                {
                    "id": f"{n.id}:{ev.state['count']}",
                    "node_id": n.id,
                    "label": n.label,
                    "status": "failed",
                    "input": actual,
                    "kind": kind if kind in ("needs_sample", "invalid_sample") else "invalid_input",
                    "message": str(exc),
                }
            )
            break
    return rows
