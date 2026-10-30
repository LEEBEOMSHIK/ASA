"""Local automation worker. Uncertain external calls are never retried automatically."""
import argparse
import json
import time
from typing import Any, TypedDict

from langchain.chat_models import init_chat_model
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from psycopg.types.json import Jsonb

from asa.config import Settings
from asa.database import changes, release_lock
from asa.graph_runtime import execute_graph_run
from asa.registry.automations import accepts
from asa.registry.model_catalog import effective_settings
from asa.registry.runtime import RunRepository
from asa.telemetry import call_config, observed_generate
from asa.tools.catalog import inspect_text
from asa.tools.model_search import search_answer
from asa.tools.search import SEARCH_ID, search_ready, web_search


class State(TypedDict):
    cursor: int
    stop: bool


def generate(repo: RunRepository, tool: dict[str, Any], value: Any) -> Any:
    settings = repo.settings
    search = bool(tool.get("web_search"))
    if search and (not repo.model_available(tool) or tool["output_schema"].get("type") != "string"):
        raise ValueError("web_search_unavailable")
    options: dict[str, Any] = ({"use_responses_api": True, "output_version": "responses/v1",
                                "store": False} if search and tool["provider"] == "openai" else {})
    model = init_chat_model(tool["model"], model_provider=tool["provider"],
                            api_key=settings.key_for(tool["provider"]).get_secret_value(),
                            timeout=min(settings.ai_timeout_seconds,
                                        tool["definition"]["limits"]["seconds"]),
                            max_retries=0,
                            max_tokens=settings.automation_output_tokens, **options)
    if search:
        with tracing_context(enabled=False):
            return search_answer(model, tool, value)
    schema = {"title": "AutomationAnswer", "type": "object",
              "properties": {"value": tool["output_schema"]}, "required": ["value"]}
    with tracing_context(enabled=False):
        result = model.with_structured_output(schema).invoke([
            ("system", tool["definition"]["instructions"]),
            ("human", json.dumps({"input": value, "input_schema": tool["input_schema"]},
                                 ensure_ascii=False)),
        ], **call_config())
    if not isinstance(result, dict):
        raise ValueError("invalid_output")
    return result["value"]


def tick(repo: RunRepository) -> bool:
    repo.worker_lock_busy = False
    with repo._connect() as lock:
        acquired = lock.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS ok",
                                (f"asa-runtime:{repo.workspace_id}",)).fetchone()
        lock.commit()
        if not acquired or not acquired["ok"]:
            repo.worker_lock_busy = True
            return False
        try:
            with tracing_context(enabled=False):
                return process(repo)
        finally:
            release_lock(lock, f"asa-runtime:{repo.workspace_id}")


def process(repo: RunRepository) -> bool:
    repo.settings = effective_settings(repo.base_settings)
    with repo._connect() as conn:
        conn.execute("INSERT INTO automation_worker_status(workspace_id) VALUES (%s) "
                     "ON CONFLICT(workspace_id) DO UPDATE SET seen_at=now()", (repo.workspace_id,))
        stale = conn.execute("UPDATE automation_runs SET status='needs_attention',"
                             "error='worker_interrupted',updated_at=now() WHERE workspace_id=%s "
                             "AND status='running' RETURNING schedule_id", (repo.workspace_id,))
        for row in stale.fetchall():
            if row["schedule_id"]:
                conn.execute("UPDATE automation_schedules SET enabled=false,revision=revision+1 "
                             "WHERE workspace_id=%s AND automation_id=%s",
                             (repo.workspace_id, row["schedule_id"]))
    repo.dispatch_due()
    with repo._connect() as conn:
        run = conn.execute("SELECT * FROM automation_runs WHERE workspace_id=%s "
                           "AND status='queued' "
                           "ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED",
                           (repo.workspace_id,)).fetchone()
        if not run:
            return False
        conn.execute("UPDATE automation_runs SET status='running',updated_at=now(),"
                     "started_at=COALESCE(started_at,now()) "
                     "WHERE workspace_id=%s AND id=%s", (repo.workspace_id, run["id"]))
    if run["definition"].get("graph") is not None:
        execute_graph_run(repo, run, generate)
        return True
    results = run["steps"]
    outputs = {"input": run["prompt"], **{r["id"]: r["output"] for r in results if "output" in r}}
    steps = run["definition"]["steps"]

    def persist(status: str, cursor: int, error: str | None = None) -> None:
        with repo._connect() as conn:
            conn.execute("UPDATE automation_runs SET status=%s,steps=%s,next_step=%s,error=%s,"
                         "updated_at=now() WHERE workspace_id=%s AND id=%s",
                         (status, Jsonb(results), cursor, error, repo.workspace_id, run["id"]))
            if error and run["schedule_id"]:
                conn.execute("UPDATE automation_schedules SET enabled=false,revision=revision+1,"
                             "note='실행 결과를 확인하고 예약을 다시 켜 주세요.' "
                             "WHERE workspace_id=%s AND automation_id=%s",
                             (repo.workspace_id, run["schedule_id"]))

    def execute(state: State) -> State:
        cursor = state["cursor"]
        if cursor >= len(steps):
            persist("succeeded", cursor)
            return {"cursor": cursor, "stop": True}
        step, tool = steps[cursor], run["manifest"][cursor]
        external = False
        row: dict[str, Any] = {"id": step["id"], "status": "running"}
        results.append(row)
        try:
            values = {}
            for key, binding in step["bindings"].items():
                value = (binding["value"] if binding["source"] == "literal"
                         else outputs[binding["source"]])
                if binding["source"] != "literal" and binding.get("field"):
                    value = value[binding["field"]]
                values[key] = value
            actual = values if tool["input_schema"]["type"] == "object" else values.get("$")
            row["input"] = actual
            if not accepts(actual, tool["input_schema"]):
                raise ValueError("invalid_input")
            is_search = tool["id"] == SEARCH_ID
            if tool["kind"] == "agent" or is_search:
                if is_search and (not search_ready(repo.settings)
                                  or tool.get("search_provider") != repo.settings.search_provider):
                    raise ValueError("search_configuration_changed")
                if not is_search and not repo.model_available(tool):
                    raise ValueError("ai_configuration_changed")
                with repo._connect() as conn:
                    count = conn.execute("SELECT count(*) AS n FROM automation_ai_calls "
                                         "WHERE workspace_id=%s "
                                         "AND created_at>now()-interval '24 hours'",
                                         (repo.workspace_id,)).fetchone()
                    if count and count["n"] >= repo.settings.automation_daily_ai_calls:
                        raise ValueError("call_limit")
                    conn.execute("INSERT INTO automation_ai_calls(workspace_id,run_id,step_id) "
                                 "VALUES (%s,%s,%s)", (repo.workspace_id, run["id"], step["id"]))
                persist("running", cursor)
                external = True
                if is_search:
                    assert isinstance(actual, dict)
                    output = web_search(repo.settings, actual)
                    row.update(provider=repo.settings.search_provider)
                else:
                    output = observed_generate(repo, run, tool, step["id"], actual, generate)
                    row.update(provider=tool["provider"], model=tool["model"])
            else:
                assert isinstance(actual, dict)
                output = inspect_text(actual["text"], actual["limit"])
            if not accepts(output, tool["output_schema"]):
                raise ValueError("invalid_output")
            row.update(status="succeeded", output=output)
            outputs[step["id"]] = output
            review = step.get("review_after", False)
            persist("waiting_review" if review else "running", cursor + 1)
            return {"cursor": cursor + 1, "stop": review}
        except Exception:
            row["status"] = "needs_attention" if external else "failed"
            persist(row["status"], cursor,
                    "external_result_uncertain" if external else "step_failed")
            return {"cursor": cursor, "stop": True}

    graph = StateGraph(State)
    graph.add_node("step", execute)
    graph.add_edge(START, "step")
    graph.add_conditional_edges("step", lambda s: END if s["stop"] else "step")
    graph.compile().invoke({"cursor": run["next_step"], "stop": False}, {"recursion_limit": 110})
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    repo = RunRepository(Settings())
    hub = changes(repo.dsn)
    scope = str(repo.workspace_id)
    while True:
        version = hub.version(scope, "automation")
        try:
            worked = tick(repo)
            delay = repo.idle_seconds() if not worked and not args.once else 0.0
        except Exception:
            print('Automation worker temporarily unavailable; retrying.', flush=True)
            if args.once:
                raise
            time.sleep(5)
            continue
        if args.once:
            return
        if not worked:
            hub.wait(scope, "automation", version, delay)


if __name__ == "__main__":
    main()
