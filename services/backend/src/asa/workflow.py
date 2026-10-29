from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from asa.models import Approval, DraftRequest, Script


class DraftState(TypedDict, total=False):
    prompt: str
    script: dict[str, str]
    status: str


def build_graph(
    generate: Callable[[str], Script], checkpointer: BaseCheckpointSaver[Any]
) -> CompiledStateGraph[DraftState, None, Any, Any]:
    def draft(state: DraftState) -> DraftState:
        request = DraftRequest(prompt=state["prompt"])
        script = generate(request.prompt)
        return {"script": script.model_dump(), "status": "waiting_approval"}

    def review(state: DraftState) -> DraftState:
        answer = interrupt({"kind": "script_approval", "script": state["script"]})
        decision = Approval.model_validate(answer)
        return {"status": "approved" if decision.approved else "rejected"}

    graph = StateGraph(DraftState)
    graph.add_node("draft", draft)
    graph.add_node("review", review)
    graph.add_edge(START, "draft")
    graph.add_edge("draft", "review")
    graph.add_edge("review", END)
    return graph.compile(checkpointer=checkpointer)
