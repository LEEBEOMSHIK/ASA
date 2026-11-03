from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from asa.registry import scene_selection
from asa.registry.schemas import AgentDraft, RegistryError
from asa.registry.service import validate_definition
from asa.tools.character_handoff import image_content


def test_video_template_accepts_scene_input():
    path = Path(__file__).resolve().parents[3] / "docs/agent-templates/video-prompt-planner.json"
    draft = AgentDraft.model_validate_json(path.read_text(encoding="utf-8"))
    assert validate_definition(draft, {}) == []
    assert "scene_images" in draft.input_schema["required"]
    assert "scene_image_plan" not in draft.input_schema["properties"]


def test_fourteen_actual_assets_and_unchanged_source(monkeypatch):
    workspace = uuid4()
    scenes = [{"image_id": str(uuid4()), "id": str(i), "name": f"scene {i}",
               "image_version": 1} for i in range(14)]
    envelope = {"format": scene_selection.FORMAT, "scenes": scenes}
    monkeypatch.setattr(scene_selection, "selected_scenes", lambda *a: envelope)

    class Connection:
        def execute(self, query, params):
            assert params[0] == workspace
            assert "workspace_id=%s" in query
            return SimpleNamespace(fetchone=lambda: {"image": b"png-test"})

    repo = SimpleNamespace(workspace_id=workspace, _connect=lambda: nullcontext(Connection()))
    value = {"script": "original script", "scenes": "original scenes", "images": envelope}
    before = deepcopy(value)
    result = image_content(repo, value)
    assert value == before
    assert len(result) == 28
    assert all(p["image_url"]["url"].startswith("data:image/png;base64,")
               for p in result if p["type"] == "image_url")
    forged = deepcopy(value)
    forged["images"]["scenes"][0]["name"] = "forged"
    with pytest.raises(RegistryError, match="character_handoff_changed"):
        image_content(repo, forged)


def test_selection_rejects_duplicates():
    image = uuid4()
    with pytest.raises(RegistryError, match="scene_selection_invalid"):
        scene_selection.selected_scenes(SimpleNamespace(), [image, image])
