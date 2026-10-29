"""Persisted graph transitions driven by LangGraph and the shared safe evaluator."""

from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from psycopg.types.json import Jsonb

from asa.registry.automations import accepts
from asa.registry.graph_automation import Evaluator, GraphDefinition
from asa.registry.runtime import RunRepository
from asa.telemetry import observed_generate
from asa.tools.catalog import inspect_text
from asa.tools.search import SEARCH_ID, search_ready, web_search


class GraphState(TypedDict):
    stop: bool


def execute_graph_run(
    repo: RunRepository,
    run: dict[str, Any],
    generate: Callable[[RunRepository, dict[str, Any], Any], Any],
) -> None:
    ev = Evaluator(
        GraphDefinition.model_validate(run["definition"]["graph"]),
        run["prompt"],
        run.get("graph_state"),
    )
    results = run["steps"]
    manifest = {t["node_id"]: t for t in run["manifest"]}

    def persist(status: str, error: str | None = None) -> None:
        with repo._connect() as conn:
            conn.execute(
                "UPDATE automation_runs SET status=%s,steps=%s,next_step=%s,error=%s,"
                "graph_state=%s,updated_at=now() WHERE workspace_id=%s AND id=%s",
                (
                    status,
                    Jsonb(results),
                    ev.state["count"],
                    error,
                    Jsonb(ev.state),
                    repo.workspace_id,
                    run["id"],
                ),
            )
            if error and run["schedule_id"]:
                conn.execute(
                    "UPDATE automation_schedules SET enabled=false,revision=revision+1 "
                    "WHERE workspace_id=%s AND automation_id=%s",
                    (repo.workspace_id, run["schedule_id"]),
                )

    def execute(state: GraphState) -> GraphState:
        if ev.state["current"] is None:
            persist("succeeded")
            return {"stop": True}
        n = ev.node
        row: dict[str, Any] = {
            "id": f"{n.id}:{ev.state['count']}",
            "node_id": n.id,
            "label": n.label,
            "status": "running",
        }
        external = False
        results.append(row)
        try:
            if ev.state["count"] >= 200:
                raise ValueError("invocation_limit")
            actual = ev.input()
            row["input"] = actual
            output = None
            if n.kind in ("ai", "tool"):
                tool = manifest[n.id]
                actual = actual if tool["input_schema"]["type"] == "object" else actual.get("$")
                row["input"] = actual
                if not accepts(actual, tool["input_schema"]):
                    raise ValueError("invalid_input")
                is_search = n.tool_id == SEARCH_ID
                if tool["kind"] == "agent" or is_search:
                    if is_search and (
                        not search_ready(repo.settings)
                        or tool.get("search_provider") != repo.settings.search_provider
                    ):
                        raise ValueError("search_configuration_changed")
                    if not is_search and not repo.model_available(tool):
                        raise ValueError("ai_configuration_changed")
                    with repo._connect() as conn:
                        count = conn.execute(
                            "SELECT count(*) FILTER (WHERE created_at>now()-interval '24 hours') "
                            "AS daily,count(*) FILTER (WHERE run_id=%s) AS total "
                            "FROM automation_ai_calls WHERE workspace_id=%s",
                            (run["id"], repo.workspace_id),
                        ).fetchone()
                        if count and (
                            count["daily"] >= repo.settings.automation_daily_ai_calls
                            or count["total"] >= 20
                        ):
                            raise ValueError("call_limit")
                        conn.execute(
                            "INSERT INTO automation_ai_calls(workspace_id,run_id,step_id) "
                            "VALUES (%s,%s,%s)",
                            (repo.workspace_id, run["id"], row["id"]),
                        )
                    persist("running")
                    external = True
                    if is_search:
                        output = web_search(repo.settings, actual)
                        row.update(provider=repo.settings.search_provider)
                    else:
                        output = observed_generate(repo, run, tool, row["id"], actual, generate)
                        row.update(provider=tool["provider"], model=tool["model"])
                else:
                    if n.tool_id != "asa.text.inspect:1":
                        raise ValueError("unsupported_tool")
                    output = inspect_text(actual["text"], actual["limit"])
                if not accepts(output, tool["output_schema"]):
                    raise ValueError("invalid_output")
            row.update(ev.advance(actual, output))
            review = n.review_after
            persist("waiting_review" if review else "running")
            return {"stop": review}
        except Exception:
            # Provider exceptions can contain private responses: never expose their text.
            row["status"] = "needs_attention" if external else "failed"
            row["message"] = (
                "외부 응답 결과를 확인해야 합니다."
                if external
                else "연결 값, 입력 형식 또는 실행 한도를 확인하세요."
            )
            persist(row["status"], "external_result_uncertain" if external else "graph_step_failed")
            return {"stop": True}

    graph = StateGraph(GraphState)
    graph.add_node("transition", execute)
    graph.add_edge(START, "transition")
    graph.add_conditional_edges("transition", lambda state: END if state["stop"] else "transition")
    graph.compile().invoke({"stop": False}, {"recursion_limit": 405})
