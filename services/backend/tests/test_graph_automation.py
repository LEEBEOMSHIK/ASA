import pytest

from asa.registry.automations import Automation, check_flow, preview_flow


def flow(items=None):
    nodes = [
        {"id": "start", "label": "Start", "kind": "start"},
        {
            "id": "loop",
            "label": "Loop",
            "kind": "repeat",
            "items": {"source": "literal", "value": items or []},
        },
        {
            "id": "ai",
            "label": "AI",
            "kind": "ai",
            "instructions": "Echo",
            "output_type": "text",
            "bindings": {"$": {"source": "loop", "field": "item"}},
        },
        {
            "id": "end",
            "label": "End",
            "kind": "end",
            "bindings": {"$": {"source": "loop", "field": "results"}},
        },
    ]
    edges = [
        {"id": str(i), "source": s, "target": t, "port": p}
        for i, (s, t, p) in enumerate(
            [
                ("start", "loop", "next"),
                ("loop", "ai", "item"),
                ("ai", "loop", "next"),
                ("loop", "end", "done"),
            ]
        )
    ]
    return Automation.model_validate({"name": "Loop", "graph": {"nodes": nodes, "edges": edges}})


@pytest.mark.parametrize("items", [[], ["a", "b"]])
def test_repeat_preview(items):
    draft = flow(items)
    assert check_flow(draft, []) == []
    rows = preview_flow(draft, [], "hello", {"ai": "answer"})
    assert rows[-1]["output"] == ["answer"] * len(items)
    assert len([r for r in rows if r["node_id"] == "ai"]) == len(items)
    assert len({r["id"] for r in rows}) == len(rows)


def test_oversize_repeat_does_not_call_body():
    rows = preview_flow(flow(list(range(21))), [], "hello", {})
    assert rows[-1]["kind"] == "invalid_input"
    assert not any(r["node_id"] == "ai" for r in rows)


def test_invalid_cycle():
    draft = flow(["a"])
    draft.graph.edges[-1].target = "start"
    assert check_flow(draft, [])


def branch_flow():
    return Automation.model_validate(
        {
            "name": "Branch",
            "graph": {
                "nodes": [
                    {"id": "start", "label": "Start", "kind": "start"},
                    {
                        "id": "choice",
                        "label": "Choice",
                        "kind": "condition",
                        "condition": {
                            "left": {"source": "input"},
                            "operator": "equals",
                            "right": "yes",
                        },
                    },
                    {
                        "id": "left",
                        "label": "Left",
                        "kind": "ai",
                        "instructions": "Echo",
                        "bindings": {"$": {"source": "input"}},
                    },
                    {
                        "id": "right",
                        "label": "Right",
                        "kind": "ai",
                        "instructions": "Echo",
                        "bindings": {"$": {"source": "input"}},
                    },
                    {"id": "end", "label": "End", "kind": "end"},
                ],
                "edges": [
                    {"id": str(i), "source": s, "target": t, "port": p}
                    for i, (s, t, p) in enumerate(
                        [
                            ("start", "choice", "next"),
                            ("choice", "left", "yes"),
                            ("choice", "right", "no"),
                            ("left", "end", "next"),
                            ("right", "end", "next"),
                        ]
                    )
                ],
            },
        }
    )


@pytest.mark.parametrize(
    "prompt,chosen,skipped", [("yes", "left", "right"), ("no", "right", "left")]
)
def test_only_selected_branch_executes(prompt, chosen, skipped):
    rows = preview_flow(branch_flow(), [], prompt, {chosen: "selected"})
    assert rows[-1]["output"] == "selected"
    assert chosen in [r["node_id"] for r in rows]
    assert skipped not in [r["node_id"] for r in rows]


def test_branch_merge_cannot_reference_optional_branch():
    draft = branch_flow()
    from asa.registry.automations import Binding

    draft.graph.nodes[-1].bindings = {"$": Binding(source="left")}
    assert check_flow(draft, [])


def test_loop_body_result_cannot_escape_scope():
    draft = flow(["a"])
    draft.graph.nodes[-1].bindings["$"].source = "ai"
    assert check_flow(draft, [])


def test_regular_cycle_rejected():
    draft = branch_flow()
    draft.graph.edges[-1].target = "choice"
    assert check_flow(draft, [])


def test_condition_type_error_stops_before_sample():
    draft = branch_flow()
    draft.graph.nodes[1].condition.operator = "greater_than"
    rows = preview_flow(draft, [], "text", {})
    assert rows[-1]["kind"] == "invalid_input"
    assert len(rows) == 2


def test_known_boolean_cannot_feed_text_input():
    draft = branch_flow()
    draft.graph.nodes[1].condition.left.source = "input"
    draft.graph.nodes[2].bindings["$"].source = "choice"
    assert check_flow(draft, [])


def test_nested_repeat_rejected():
    draft = flow(["a"])
    draft.graph.nodes[2].kind = "repeat"
    draft.graph.nodes[2].items = draft.graph.nodes[1].items
    assert check_flow(draft, [])


def test_empty_repeat_body_rejected():
    draft = flow(["a"])
    draft.graph.edges[1].target = "loop"
    assert check_flow(draft, [])


def test_graph_requires_exactly_one_end():
    draft = branch_flow()
    draft.graph.nodes.append(draft.graph.nodes[-1].model_copy(update={'id': 'second_end'}))
    draft.graph.edges[-1].target = 'second_end'
    assert any('하나' in issue.message for issue in check_flow(draft, []))


def test_selected_model_validation_and_preview():
    from asa.config import Settings
    from asa.registry.schemas import RegistryError

    settings = Settings(_env_file=None, ai_model='default', ai_models=['selected'])
    draft = branch_flow()
    draft.graph.nodes[2].model = 'selected'
    assert check_flow(draft, [], settings) == []
    draft.graph.nodes[2].model = 'unknown'
    assert any(issue.field_path == 'left.model' for issue in check_flow(draft, [], settings))
    with pytest.raises(RegistryError):
        preview_flow(draft, [], 'yes', {'left': 'answer'}, settings)


def test_generate_uses_snapshot_model(monkeypatch):
    from asa.config import Settings
    from asa.registry.runtime import RunRepository
    from asa.runtime_worker import generate

    called = []

    class MockModel:
        def with_structured_output(self, schema):
            return self

        def invoke(self, messages):
            return {'value': 'answer'}

    def init(model, **kwargs):
        called.append(model)
        return MockModel()

    monkeypatch.setattr('asa.runtime_worker.init_chat_model', init)
    repo = RunRepository(Settings(_env_file=None, ai_model='default'))
    assert generate(repo, {'model': 'selected', 'provider': 'openai',
        'definition': {'instructions': 'Echo', 'limits': {'seconds': 120}},
        'output_schema': {'type': 'string'}}, 'hello') == 'answer'
    assert called == ['selected']


def test_default_and_explicit_model_configuration_changes():
    from asa.config import Settings
    from asa.registry.runtime import RunRepository

    settings = Settings(_env_file=None, ai_model='original', ai_models=['selected', 'original'],
                        ai_api_key='fake', automation_ai_enabled=True)
    repo = RunRepository(settings)
    legacy = {'provider': 'openai', 'model': 'original'}
    selected = {'provider': 'openai', 'model': 'selected', 'model_selected': True}
    assert repo.model_available(legacy)
    assert repo.model_available(selected)
    changed = RunRepository(settings.model_copy(update={'ai_model': 'changed'}))
    assert not changed.model_available(legacy)
    assert changed.model_available(selected)
    removed = RunRepository(settings.model_copy(update={'ai_models': []}))
    assert not removed.model_available(selected)
    assert 'model' not in branch_flow().graph.nodes[2].model_dump()


def test_non_ai_node_cannot_choose_model():
    from asa.config import Settings

    draft = branch_flow()
    draft.graph.nodes[0].model = 'approved'
    assert any(issue.field_path == 'start.model' for issue in check_flow(
        draft, [], Settings(_env_file=None, ai_model='approved')))
