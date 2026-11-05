from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from asa.registry import character_library, scene_images, scene_selection
from asa.registry.schemas import RegistryError


def test_scene_override_preserves_default_and_version_settings(monkeypatch):
    ids = [str(uuid4()), str(uuid4())]
    choices = [
        dict(
            id=image,
            version=i + 1,
            confirmed=True,
            character_id="hero",
            source_deleted=False,
            state="approved",
            project_id="project",
            request_id="request",
            source_version=1,
            character={"id": "hero", "name": "Hero", "appearance": color},
            image_change=f"use {color}",
        )
        for i, (image, color) in enumerate(zip(ids, ["red", "blue"], strict=True))
    ]
    monkeypatch.setattr(character_library, "versions", lambda *args: choices)
    refs = [{"id": "hero", "image_id": ids[1]}]
    original = deepcopy(choices)
    default = scene_images.resolve_references(None, refs, {})["characters"][0]
    override = scene_images.resolve_references(None, refs, {"hero": UUID(ids[0])})["characters"][0]
    assert (default["image_version"], default["appearance"]) == (2, "blue")
    assert (override["image_version"], override["appearance"]) == (1, "red")
    assert override["image_change"] == "use red"
    assert override["selection"] == "scene_override"
    assert choices == original
    assert scene_images.resolve_references(None, refs, {})["characters"][0] == default
    with pytest.raises(RegistryError, match="scene_reference_override_invalid"):
        scene_images.resolve_references(None, refs, {"other": UUID(ids[0])})
    with pytest.raises(RegistryError, match="scene_reference_override_invalid"):
        scene_images.resolve_references(None, refs, {"hero": uuid4()})
    choices[0]["confirmed"] = False
    with pytest.raises(RegistryError, match="scene_reference_override_invalid"):
        scene_images.resolve_references(None, refs, {"hero": UUID(ids[0])})
    choices[0]["confirmed"] = True
    choices[0]["character_id"] = "another-character"
    with pytest.raises(RegistryError, match="scene_reference_override_invalid"):
        scene_images.resolve_references(None, refs, {"hero": UUID(ids[0])})


def test_retained_confirmed_reference_remains_usable_after_source_deletion(monkeypatch):
    image = uuid4()
    choice = dict(
        id=str(image), version=1, confirmed=True, character_id="hero",
        source_deleted=True, state="approved", project_id="project",
        request_id="deleted-request", source_version=1,
        character={"id": "hero", "name": "Hero", "appearance": "red coat"},
    )
    monkeypatch.setattr(character_library, "versions", lambda *args: [choice])
    refs = [{"id": "hero", "image_id": str(image)}]
    result = scene_images.resolve_references(None, refs, {})["characters"][0]
    assert result["image_id"] == str(image)
    assert result["appearance"] == "red coat"
    choice["state"] = "excluded"
    with pytest.raises(RegistryError, match="scene_reference_unavailable"):
        scene_images.resolve_references(None, refs, {})
    choice["state"] = "approved"
    choice["confirmed"] = False
    with pytest.raises(RegistryError, match="scene_reference_override_invalid"):
        scene_images.resolve_references(None, refs, {})


def test_queued_scene_loads_pinned_asset_not_new_default():
    workspace, image = uuid4(), uuid4()

    class Connection:
        def execute(self, query, params):
            assert params == (workspace, image, workspace, image)
            assert "status='succeeded'" in query
            return SimpleNamespace(fetchone=lambda: {"image": b"old-version"})

    repo = SimpleNamespace(workspace_id=workspace, _connect=lambda: nullcontext(Connection()))
    snapshot = {"references": {"characters": [{"image_id": str(image)}]}}
    assert scene_images.reference_bytes(repo, snapshot) == [b"old-version"]


def test_video_scene_uses_only_single_confirmed_version(monkeypatch):
    from asa.registry.characters import CharacterRepository

    workspace, project_id, v1, v2, foreign = [uuid4() for _ in range(5)]
    context = dict(
        shot={"scene_id": "6", "shot_id": "6a"},
        aspect_ratio="9:16",
        references={"characters": [{"id": "hero", "image_version": 1}]},
    )
    rows = [
        dict(id=i, project_id=project_id, character_id="scene_6", scene_context=context)
        for i in [v1, v2, foreign]
    ]
    rows[-1]["character_id"] = "scene_7"
    project = dict(
        id=str(project_id),
        request_id=str(uuid4()),
        source_version=1,
        kind="scene",
        approved={"scene_6": str(v2)},
        work_progress={"items": [{"id": "scene_6", "state": "approved"}]},
        jobs=[
            dict(
                id=str(i),
                version=n + 1,
                change=f"revision {n + 1}",
                character={"name": "Scene six", "appearance": f"look {n + 1}"},
            )
            for n, i in enumerate([v1, v2])
        ],
    )

    class Connection:
        def execute(self, query, params=None):
            if params:
                assert params[0] == workspace
                return SimpleNamespace(fetchall=lambda: [r for r in rows if r["id"] in params[1]])
            return None

    monkeypatch.setattr(CharacterRepository, "_connect", lambda self: nullcontext(Connection()))
    monkeypatch.setattr(CharacterRepository, "project", lambda *args: project)
    repo = SimpleNamespace(dsn="unused", workspace_id=workspace)
    default = scene_selection.selected_scenes(repo, [v2])["scenes"][0]
    assert default["image_version"] == 2
    assert project["approved"]["scene_6"] == str(v2)
    with pytest.raises(RegistryError, match="scene_single_confirmed_version_required"):
        scene_selection.selected_scenes(repo, [v2], {v2: v1})
    with pytest.raises(RegistryError, match="scene_selection_not_ready"):
        scene_selection.selected_scenes(repo, [v1])
    with pytest.raises(RegistryError, match="scene_single_confirmed_version_required"):
        scene_selection.selected_scenes(repo, [v2], {v2: foreign})
