import httpx
import pytest
from pydantic import SecretStr

from asa.config import Settings
from asa.registry.automations import Automation, check_flow, preview_flow
from asa.tools.search import search_tool, web_search


def test_search_adapter(monkeypatch):
    client = httpx.Client

    def respond(request):
        assert request.url.host == "api.search.brave.com"
        assert request.headers["X-Subscription-Token"] == "test-key"
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {"title": "Title", "url": "https://example.com", "description": "Summary"}
                    ]
                }
            },
        )

    monkeypatch.setattr(
        httpx, "Client", lambda **kw: client(transport=httpx.MockTransport(respond), **kw)
    )
    settings = Settings(search_enabled=True, search_api_key=SecretStr("test-key"))
    assert web_search(settings, {"query": "cats", "count": 1})["results"][0]["snippet"] == "Summary"


@pytest.mark.parametrize("payload", [{"web": {"results": []}}, {}])
def test_empty_search(monkeypatch, payload):
    client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)), **kw
        ),
    )
    assert web_search(
        Settings(search_enabled=True, search_api_key=SecretStr("test")),
        {"query": "cats", "count": 1},
    ) == {"results": []}


def test_search_disabled():
    with pytest.raises(ValueError, match="configuration"):
        web_search(Settings(search_enabled=False), {"query": "cats", "count": 1})


@pytest.mark.parametrize(
    "status,payload",
    [
        (401, {"secret": "hidden"}),
        (
            200,
            {"web": {"results": [{"title": "bad", "url": "file:///secret", "description": "bad"}]}},
        ),
    ],
)
def test_search_failure_redacted(monkeypatch, status, payload):
    client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: client(
            transport=httpx.MockTransport(lambda request: httpx.Response(status, json=payload)),
            **kw,
        ),
    )
    with pytest.raises(ValueError, match="^search_request_failed$"):
        web_search(
            Settings(search_enabled=True, search_api_key=SecretStr("hidden")),
            {"query": "cats", "count": 1},
        )


def mapped_flow():
    nodes = [
        {"id": "start", "label": "Start", "kind": "start"},
        {
            "id": "search",
            "label": "Search",
            "kind": "tool",
            "tool_id": "asa.web.search:1",
            "bindings": {"query": {"source": "input"}, "count": {"source": "literal", "value": 1}},
        },
        {
            "id": "select",
            "label": "Select",
            "kind": "map",
            "output_fields": {"article": "text"},
            "bindings": {"article": {"source": "search", "field": "results.0.title"}},
        },
        {
            "id": "end",
            "label": "End",
            "kind": "end",
            "bindings": {"$": {"source": "select", "field": "article"}},
        },
    ]
    return Automation.model_validate(
        {
            "name": "Search mapping",
            "graph": {
                "nodes": nodes,
                "edges": [
                    {"id": str(i), "source": s, "target": t, "port": "next"}
                    for i, (s, t) in enumerate(
                        [("start", "search"), ("search", "select"), ("select", "end")]
                    )
                ],
            },
        }
    )


def test_search_mapping_preview():
    draft = mapped_flow()
    tool = search_tool()
    assert check_flow(draft, [tool]) == []
    rows = preview_flow(draft, [tool], "cats", {"search": tool["example_output"]})
    assert rows[-1]["output"] == tool["example_output"]["results"][0]["title"]


def test_empty_result_mapping_stops():
    rows = preview_flow(mapped_flow(), [search_tool()], "cats", {"search": {"results": []}})
    assert rows[-1]["kind"] == "invalid_input"


def test_mapping_wrong_type_rejected():
    draft = mapped_flow()
    draft.graph.nodes[2].output_fields = {"article": "number"}
    assert check_flow(draft, [search_tool()])


def test_mapping_checkpoint_resume():
    import json

    from asa.registry.graph_automation import Evaluator

    draft = mapped_flow()
    engine = Evaluator(draft.graph, 'cats')
    engine.advance(engine.input())
    engine.advance(engine.input(), search_tool()['example_output'])
    restored = Evaluator(draft.graph, 'ignored', json.loads(json.dumps(engine.state)))
    assert restored.node.kind == 'map'
    restored.advance(restored.input())
    assert restored.advance(restored.input())['output'] == '고양이가 상자를 좋아하는 이유'


@pytest.mark.parametrize('name', ['', 'bad.path', '__private', 'x' * 81])
def test_mapping_invalid_name(name):
    draft = mapped_flow()
    draft.graph.nodes[2].output_fields = {name: 'text'}
    assert check_flow(draft, [search_tool()])
