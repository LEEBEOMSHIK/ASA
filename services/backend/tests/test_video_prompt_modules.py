import copy
import json
from dataclasses import replace

import pytest
from pydantic import ValidationError

from asa.video_prompt_modules import (
    Module,
    VideoPromptModules,
    build_prompt_bundle,
    bundled_instructions,
    freeze_module_catalog,
    prepare_video_prompt_tool,
)


def test_queued_catalog_survives_module_file_changes(tmp_path, modules):
    config = {"instructions": "Original", "video_prompt_modules": {
        "enabled": True, "metadata_style_field": "style",
    }}
    tool = {"definition": config, "video_prompt_catalog": freeze_module_catalog(
        config, registry=modules, root=tmp_path,
    )}
    original = copy.deepcopy(tool)
    (tmp_path / "animation_3d.md").write_text("Changed later", encoding="utf-8")
    value = {"style": {"media_type": "animation_3d"}, "image_id": "approved-v2",
             "script": "Original script", "reference_roles": ["reference_only"]}
    before = copy.deepcopy(value)
    result = prepare_video_prompt_tool(tool, value)
    assert "trusted:animation_3d" in bundled_instructions(result)
    assert "Changed later" not in bundled_instructions(result)
    assert result["video_prompt_bundle"]["media_type"] == "animation_3d"
    assert tool == original
    assert value == before


def test_legacy_queued_tool_does_not_load_modules():
    tool = {"definition": {"instructions": "Original", "video_prompt_modules": {
        "enabled": True, "mode": "manual", "profile_id": "live_action",
    }}}
    assert prepare_video_prompt_tool(tool, {}) is tool
    assert bundled_instructions(tool) == "Original"


@pytest.fixture
def modules(tmp_path):
    registry = tuple(
        Module(key, "1", key, None if key == "common" else key, f"{key}.md", True)
        for key in ("common", "animation_2d", "animation_3d", "live_action")
    )
    for module in registry:
        (tmp_path / module.instruction_source).write_text(
            f"trusted:{module.profile_id}", encoding="utf-8"
        )
    return registry


def definition(**settings):
    return {
        "instructions": "기존 사용자 지침을 그대로 보존합니다.",
        "video_prompt_modules": {"enabled": True, "user_style_field": "style", **settings},
    }


@pytest.mark.parametrize("media", ["animation_2d", "animation_3d", "live_action"])
def test_only_selected_specialist_is_composed(tmp_path, modules, media):
    result = build_prompt_bundle(
        definition(), {"style": media}, registry=modules, root=tmp_path
    )
    assert result["style_profile_ids"] == ["common", media]
    assert result["instructions"] == (
        f"trusted:common\n\ntrusted:{media}\n\n" + definition()["instructions"]
    )
    assert len(result["modules"][1]["sha256"]) == 64


def test_disabled_preserves_legacy_instructions():
    result = build_prompt_bundle({"instructions": "original"}, {"style": "live_action"})
    assert result["instructions"] == "original"
    assert result["style_profile_ids"] == []
    assert result["fallback"]
    assert not result["warnings"]
    assert bundled_instructions({"agent_instructions": "old queued instruction"}) == (
        "old queued instruction"
    )


@pytest.mark.parametrize("inputs", ["normal text input", ["animation_2d"]])
def test_non_object_input_with_enabled_mapping_falls_back(inputs):
    original = copy.deepcopy(inputs)
    result = build_prompt_bundle(definition(), inputs)
    assert result["instructions"] == definition()["instructions"]
    assert result["media_type"] is None
    assert result["fallback"]
    assert "media_type_unresolved" in result["warnings"]
    assert inputs == original


def test_agent_provider_uses_frozen_enabled_bundle(tmp_path, modules, monkeypatch):
    from asa.config import Settings
    from asa.providers import make_agent_generator

    captured = {}

    class Model:
        def with_structured_output(self, schema):
            return self

        def invoke(self, messages, **kwargs):
            captured["messages"] = messages
            return {"value": "answer"}

    monkeypatch.setattr("asa.providers.init_chat_model", lambda *a, **k: Model())
    inputs = {"style": "animation_2d"}
    bundle = build_prompt_bundle(definition(), inputs, registry=modules, root=tmp_path)
    (tmp_path / "animation_2d.md").write_text("Changed later", encoding="utf-8")
    contract = {
        "agent_instructions": "legacy fallback must not replace bundle",
        "video_prompt_bundle": bundle,
        "original_request": inputs,
        "output_schema": {"type": "string"},
    }
    generator = make_agent_generator(
        Settings(_env_file=None, ai_provider="openai", ai_model="test", ai_api_key="fake")
    )
    assert generator(json.dumps(contract)).value == "answer"
    assert captured["messages"][0] == ("system", bundle["instructions"])
    assert "trusted:animation_2d" in captured["messages"][0][1]
    assert json.loads(captured["messages"][1][1])["original_request"] == inputs


def test_priority_conflicts_and_input_integrity(tmp_path, modules):
    settings = definition(
        confirmed_style_field="confirmed", reference_style_field="reference",
        metadata_style_field="metadata",
    )
    inputs = {
        "style": {"media_type": "animation_2d", "instructions": "UNTRUSTED"},
        "confirmed": {"media_type": "animation_3d"},
        "reference": {"media_type": "live_action", "excluded": ["realistic face"]},
        "metadata": "live_action",
        "scene": {"scene_id": "s1", "shot_id": "shot1", "clip_id": "c1",
                  "image_id": "i1", "image_version": 2, "reference_roles": ["reference_only"]},
    }
    original = copy.deepcopy((settings, inputs))
    result = build_prompt_bundle(settings, inputs, registry=modules, root=tmp_path)
    assert result["selection_source"] == "user"
    assert len(result["conflicts"]) == 3
    assert "style_conflict_review_required" in result["warnings"]
    assert "UNTRUSTED" not in result["instructions"]
    assert (settings, inputs) == original
    del inputs["style"]
    assert build_prompt_bundle(settings, inputs)["selection_source"] == "confirmed"
    del inputs["confirmed"]
    assert build_prompt_bundle(settings, inputs)["selection_source"] == "reference"
    del inputs["reference"]
    assert build_prompt_bundle(settings, inputs)["selection_source"] == "metadata"


def test_manual_selection_wins_and_missing_profile_does_not_guess(tmp_path, modules):
    result = build_prompt_bundle(
        definition(mode="manual", profile_id="animation_3d"),
        {"style": "live_action"}, registry=modules, root=tmp_path,
    )
    assert result["media_type"] == "animation_3d"
    assert result["selection_source"] == "manual"
    missing = build_prompt_bundle(
        definition(mode="manual"), {"style": "live_action"}, registry=modules, root=tmp_path,
    )
    assert missing["style_profile_ids"] == ["common"]
    assert "manual_profile_missing" in missing["warnings"]


@pytest.mark.parametrize(
    "style", ["film", "cinematic", "watercolor", None, {"visual_style": "anime"}]
)
def test_unknown_style_uses_common_only(tmp_path, modules, style):
    result = build_prompt_bundle(
        definition(), {"style": style}, registry=modules, root=tmp_path
    )
    assert result["media_type"] is None
    assert result["style_profile_ids"] == ["common"]
    assert "media_type_unresolved" in result["warnings"]


def test_unavailable_specialist_keeps_common(tmp_path, modules):
    result = build_prompt_bundle(
        definition(), {"style": "animation_2d"}, registry=modules[:1], root=tmp_path
    )
    assert result["style_profile_ids"] == ["common"]
    assert "module_unavailable:animation_2d" in result["warnings"]


@pytest.mark.parametrize("source", ["../outside.md", "common.txt", "missing.md"])
def test_invalid_common_source_falls_back(tmp_path, modules, source):
    registry = (replace(modules[0], instruction_source=source), *modules[1:])
    result = build_prompt_bundle(
        definition(), {"style": "animation_2d"}, registry=registry, root=tmp_path
    )
    assert result["style_profile_ids"] == []
    assert result["instructions"] == definition()["instructions"]
    assert "module_body_unavailable:common" in result["warnings"]


@pytest.mark.parametrize("body", ["", "x" * 131073], ids=["empty", "oversized"])
def test_invalid_body_falls_back(tmp_path, modules, body):
    (tmp_path / "common.md").write_text(body, encoding="utf-8")
    assert build_prompt_bundle(
        definition(), {"style": "animation_2d"}, registry=modules, root=tmp_path
    )["fallback"]


def test_disabled_common_cannot_run_specialist(tmp_path, modules):
    registry = (replace(modules[0], enabled=False), *modules[1:])
    assert build_prompt_bundle(
        definition(), {"style": "animation_2d"}, registry=registry, root=tmp_path
    )["fallback"]


def test_snapshot_is_stable_and_retry_does_not_reload(tmp_path, modules):
    args = (definition(), {"style": "animation_2d"})
    first = build_prompt_bundle(*args, registry=modules, root=tmp_path)
    assert first == build_prompt_bundle(*args, registry=modules, root=tmp_path)
    contract = {"agent_instructions": "legacy", "video_prompt_bundle": copy.deepcopy(first)}
    (tmp_path / "animation_2d.md").write_text("updated body", encoding="utf-8")
    second = build_prompt_bundle(*args, registry=modules, root=tmp_path)
    assert first["prompt_bundle_version"] != second["prompt_bundle_version"]
    bumped = (replace(modules[0], version="2"), *modules[1:])
    third = build_prompt_bundle(*args, registry=bumped, root=tmp_path)
    assert second["prompt_bundle_version"] != third["prompt_bundle_version"]
    assert bundled_instructions(contract) == first["instructions"]


def test_strict_configuration_rejects_unknown_and_invalid_fields():
    for value in ({"enabled": "true"}, {"profile_id": "film"}, {"path": "/tmp/x"}):
        with pytest.raises(ValidationError):
            VideoPromptModules.model_validate(value)
