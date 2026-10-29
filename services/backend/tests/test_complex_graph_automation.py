"""Complex control-flow contracts, using only samples and the free local tool."""

import json

import pytest

from asa.registry.automations import Automation, check_flow, preview_flow
from asa.registry.graph_automation import Evaluator
from asa.tools.catalog import builtin_tools


def complex_flow():
    nodes = [
        {"id": "start", "label": "Start", "kind": "start"},
        {"id": "items", "label": "List sample", "kind": "ai", "instructions": "List",
         "output_type": "list", "bindings": {"$": {"source": "input"}}},
        {"id": "loop", "label": "Repeat", "kind": "repeat", "items": {"source": "items"}},
    ]
    for key in ("inspect", "merge"):
        nodes.append({"id": key, "label": key, "kind": "tool", "tool_id": "asa.text.inspect:1",
                      "bindings": {"text": {"source": "loop", "field": "item"},
                                   "limit": {"source": "literal", "value": 3}}})
    nodes.append({"id": "length", "label": "Length", "kind": "condition",
                  "condition": {"left": {"source": "inspect", "field": "exceeded"},
                                "operator": "is_true"}})
    for key in ("long_tag", "short_tag"):
        nodes.append({"id": key, "label": key, "kind": "condition",
                      "condition": {"left": {"source": "loop", "field": "item"},
                                    "operator": "contains", "right": "#"}})
    for key in ("long_yes", "long_no", "short_yes", "short_no"):
        nodes.append({"id": key, "label": key, "kind": "ai", "instructions": "Echo",
                      "bindings": {"$": {"source": "loop", "field": "item"}}})
    nodes.append({"id": "end", "label": "End", "kind": "end",
                  "bindings": {"$": {"source": "loop", "field": "results"}}})
    links = [("start", "items", "next"), ("items", "loop", "next"),
             ("loop", "inspect", "item"), ("loop", "end", "done"),
             ("inspect", "length", "next"), ("length", "long_tag", "yes"),
             ("length", "short_tag", "no"), ("merge", "loop", "next")]
    for size in ("long", "short"):
        for port in ("yes", "no"):
            links.extend([(f"{size}_tag", f"{size}_{port}", port),
                          (f"{size}_{port}", "merge", "next")])
    return Automation.model_validate({"name": "Layered loop", "graph": {
        "nodes": nodes,
        "edges": [{"id": f"edge{i}", "source": s, "target": t, "port": p}
                  for i, (s, t, p) in enumerate(links)],
    }})


ITEMS = ["#long", "long", "#", "x"]
PATHS = ["long_yes", "long_no", "short_yes", "short_no"]
EXPECTED = [
    {"characters": 5, "limit": 3, "exceeded": True},
    {"characters": 4, "limit": 3, "exceeded": True},
    {"characters": 1, "limit": 3, "exceeded": False},
    {"characters": 1, "limit": 3, "exceeded": False},
]


@pytest.mark.parametrize("repetitions", [1, 5])
def test_layered_loop_visits_all_four_paths_and_merges_in_item_order(repetitions):
    draft = complex_flow()
    assert check_flow(draft, builtin_tools()) == []
    samples = {"items": ITEMS * repetitions, **{key: f"sample:{key}" for key in PATHS}}
    rows = preview_flow(draft, builtin_tools(), "Create test items", samples)
    expected_path = ["start", "items", "loop"]
    for selected in PATHS * repetitions:
        expected_path.extend(["inspect", "length", selected.split("_")[0] + "_tag",
                              selected, "merge", "loop"])
    expected_path.append("end")
    assert [row["node_id"] for row in rows] == expected_path
    assert all(row["status"] == "succeeded" for row in rows)
    assert rows[-1]["output"] == EXPECTED * repetitions
    assert len({row["id"] for row in rows}) == len(rows)
    selected_rows = [row for row in rows if row["node_id"] in PATHS]
    assert [row["input"] for row in selected_rows] == ITEMS * repetitions
    assert [row["output"] for row in selected_rows] == [
        f"sample:{key}" for key in PATHS * repetitions]
    assert [row["iteration"] for row in selected_rows] == list(range(4 * repetitions))
    assert all(row["kind"] == "sample" for row in selected_rows)
    assert all(row["kind"] == "local_tool" for row in rows
               if row["node_id"] in ("inspect", "merge"))


def test_restart_between_every_transition_preserves_results_and_clears_iteration_outputs():
    draft = complex_flow()
    samples = {"items": ITEMS, **{key: key for key in PATHS}}
    preview = preview_flow(draft, builtin_tools(), "request", samples)
    ev = Evaluator(draft.graph, "request")
    for expected in preview:
        # Simulate JSON checkpoint persistence and a new evaluator per transition.
        ev = Evaluator(draft.graph, "ignored on resume", json.loads(json.dumps(ev.state)))
        actual = ev.input()
        if ev.node.kind == "ai":
            actual = actual["$"]
        row = ev.advance(actual, expected["output"])
        assert row == {key: value for key, value in expected.items() if key != "kind"}
        if row["node_id"] == "loop":
            assert set(ev.state["outputs"]) == {"input", "start", "items", "loop"}
    assert ev.state["current"] is None
    assert ev.state["last"] == EXPECTED


@pytest.mark.parametrize("mutation,issue_path", [
    ("cycle", "inspect"), ("nested", "inspect"), ("optional_reference", "merge"),
])
def test_complex_graph_rejects_invalid_control_or_cross_branch_reference(mutation, issue_path):
    draft = complex_flow()
    if mutation == "cycle":
        next(edge for edge in draft.graph.edges if edge.source == "merge").target = "inspect"
    elif mutation == "nested":
        # Keep required ports valid so this exercises the nested-loop scope rule.
        node = next(node for node in draft.graph.nodes if node.id == "inspect")
        node.kind = "repeat"
        node.items = draft.graph.nodes[2].items.model_copy()
        node.bindings = {}
        node.tool_id = None
        edge = next(edge for edge in draft.graph.edges if edge.source == "inspect")
        edge.port = "item"
        draft.graph.edges.append(edge.model_copy(update={
            "id": "nested_done", "target": "loop", "port": "done"}))
    else:
        merge = next(node for node in draft.graph.nodes if node.id == "merge")
        merge.bindings["text"].source = "long_yes"
        merge.bindings["text"].field = ""
    issues = check_flow(draft, builtin_tools())
    assert any(issue.field_path == issue_path for issue in issues)


@pytest.mark.parametrize("prompt,expected", [("yes", True), ("no", False)])
def test_maximum_node_graph_traverses_48_merging_conditions(prompt, expected):
    nodes = [{"id": "start", "label": "Start", "kind": "start"}]
    links = [("start", "condition0", "next")]
    for index in range(48):
        key = f"condition{index}"
        nodes.append({"id": key, "label": key, "kind": "condition",
                      "condition": {"left": {"source": "input"},
                                    "operator": "equals", "right": "yes"}})
        target = f"condition{index + 1}" if index < 47 else "end"
        links.extend([(key, target, "yes"), (key, target, "no")])
    nodes.append({"id": "end", "label": "End", "kind": "end"})
    draft = Automation.model_validate({"name": "Maximum nodes", "graph": {
        "nodes": nodes,
        "edges": [{"id": f"edge{i}", "source": s, "target": t, "port": p}
                  for i, (s, t, p) in enumerate(links)],
    }})
    assert check_flow(draft, []) == []
    rows = preview_flow(draft, [], prompt, {})
    assert [row["node_id"] for row in rows] == [node["id"] for node in nodes]
    assert all(row["output"] is expected for row in rows[1:])
    assert all(row["status"] == "succeeded" for row in rows)
