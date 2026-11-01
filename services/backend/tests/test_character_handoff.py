from copy import deepcopy

import pytest

from asa.registry.automations import accepts
from asa.registry.schemas import RegistryError
from asa.tools.character_handoff import handoff, handoff_tool


def project():
    return {"id": "p", "request_id": "r", "source_version": 1,
            "characters": [{"id": "a", "name": "plan"}, {"id": "b", "name": "excluded"}],
            "excluded": ["b"], "approved": {"a": "image1", "b": "image2"},
            "work_progress": {"items": [{"id": "a", "state": "approved"},
                                        {"id": "b", "state": "excluded"}]},
            "jobs": [{"id": "image1", "character_id": "a", "status": "succeeded",
                      "version": 1, "character": {"id": "a", "name": "final", "facts": "fact",
                      "appearance": "yellow", "proposed": "proposal", "scene_ids": "1",
                      "image_prompt": "front"}, "change": "blue hat"}]}


def test_confirmed_settings_only_and_source_unchanged():
    p = project()
    before = deepcopy(p)
    result = handoff(p)
    assert [c["id"] for c in result["characters"]] == ["a"]
    assert result["characters"][0]["name"] == "final"
    assert result["characters"][0]["image_change"] == "blue hat"
    assert accepts(result, handoff_tool()["output_schema"])
    assert p == before
    assert "script" not in result and "scenes" not in result


@pytest.mark.parametrize("state", ["pending", "review", "running", "failed", "unknown"])
def test_incomplete_required_character_blocks_entire_handoff(state):
    p = project()
    p["work_progress"]["items"][0]["state"] = state
    with pytest.raises(RegistryError, match="character_handoff_not_ready"):
        handoff(p)


def test_missing_approved_asset_and_all_excluded():
    p = project()
    p["approved"]["a"] = "missing"
    with pytest.raises(RegistryError):
        handoff(p)
    p["excluded"] = ["a", "b"]
    assert handoff(p)["characters"] == []


def test_automation_model_receives_actual_image_and_unchanged_text(monkeypatch):
    from types import SimpleNamespace

    from asa import runtime_worker
    from asa.config import Settings
    from asa.registry import review_connection
    calls = []

    class Model:
        def with_structured_output(self, schema):
            return self

        def invoke(self, messages, **kwargs):
            calls.append(messages)
            return {"value": "done"}

    monkeypatch.setattr(runtime_worker, "init_chat_model", lambda *a, **kw: Model())
    attachment = {"type": "image_url", "image_url": {"url": "data:image/png;base64,ZmFrZQ=="}}
    monkeypatch.setattr(runtime_worker, "image_content", lambda *a: [attachment])
    monkeypatch.setattr(review_connection, "validate_review_model", lambda *a: None)
    repo = SimpleNamespace(settings=Settings(_env_file=None, ai_api_key="test-only"))
    tool = {"provider": "openai", "model": "test", "input_schema": {"type": "object"},
            "output_schema": {"type": "string"},
            "definition": {"instructions": "keep instructions", "limits": {"seconds": 60}}}
    original = {"script": "원문 대본", "scenes": "원문 장면", "cast": handoff(project())}
    before = deepcopy(original)
    assert runtime_worker.generate(repo, tool, original) == "done"
    assert original == before
    assert calls[0][1].content[-1] == attachment
    import json
    assert json.loads(calls[0][1].content[0]["text"])["input"] == original
