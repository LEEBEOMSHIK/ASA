from asa.registry.art_styles import apply_style
from asa.tools.character_images import image_prompt


def test_automatic_style_follows_references_before_story_without_forcing_photography():
    result = apply_style("legacy cinematic scene", {"mode": "auto"})
    assert "approved character reference images" in result
    assert "Only when no visual reference" in result
    assert "AUTOMATIC VISUAL STYLE" in result
    assert "Render a photographic" not in result


def test_automatic_video_ignores_old_specialist_choice():
    from asa.video_prompt_modules import build_prompt_bundle

    definition = {"instructions": "COMMON", "video_prompt_modules": {
        "enabled": True, "editor_managed": True, "selection_required": True,
        "style_instructions": {"live_action": "FORCE_PHOTO"}}}
    bundle = build_prompt_bundle(definition, {"video_style": "live_action"}, work_style_auto=True)
    assert bundle["media_type"] is None
    assert bundle["selection_source"] == "work_auto"
    assert "FORCE_PHOTO" not in bundle["instructions"]
    assert "AUTOMATIC VISUAL STYLE" in bundle["instructions"]


def test_auto_video_policy_accepts_saved_video_contract_without_relaxing_other_enums():
    from asa.registry.art_styles import generation_style, video_inputs
    from asa.registry.history import valid_input

    schema = {"type": "object", "properties": {
        "model": {"type": "string", "x-video-model": True},
        "video_style": {"type": "string", "enum": [
            "animation_2d", "animation_3d", "live_action"]}},
        "required": ["video_style"]}
    style = generation_style({"prompt": "", "media_type": None})
    inputs = video_inputs({"input_schema": schema}, {}, style)
    assert inputs == {"video_style": "auto"}
    assert valid_input(inputs, schema)
    assert not valid_input("auto", schema["properties"]["video_style"])
    assert not valid_input({"video_style": "invalid"}, schema)
    explicit = {"prompt": "watercolor", "media_type": None}
    assert generation_style(explicit) == explicit


def test_legacy_plan_stays_usable_but_explicit_style_change_requires_new_plan():
    import pytest

    from asa.registry.art_styles import check_plan_style
    from asa.registry.schemas import RegistryError

    auto = {"mode": "auto", "prompt": "", "media_type": None}
    check_plan_style(None, auto)
    with pytest.raises(RegistryError, match="work_visual_plan_changed"):
        check_plan_style({"media_type": "live_action", "prompt": ""}, auto)


def test_default_live_action_is_explicit_even_without_custom_prompt():
    result = apply_style("legacy 2D", {"media_type": "live_action", "prompt": ""})
    assert "photographic" in result
    assert "stylized proportions" in result
    assert "not a cartoon" in result


def test_reference_style_preservation_defers_to_common_style():
    result = image_prompt({"name": "child", "appearance": "red coat"}, "restyle")
    assert "preserve its face, proportions, style and clothes" not in result
    assert "WORK ART STYLE POLICY" in result


def test_video_detail_validation_and_snapshot():
    import pytest

    from asa.registry.art_styles import apply_style, video_style
    from asa.registry.history import valid_input
    from asa.registry.schemas import RegistryError

    schema = {"type": "object", "properties": {
        "video_model": {"type": "string", "x-video-model": True},
        "video_style": {"type": "string"}}}
    values = {"video_style": "animation_2d", "video_art_style": "soft watercolor"}
    assert valid_input(values, schema)
    assert not valid_input({**values, "video_art_style": "x" * 2001}, schema)
    assert not valid_input({**values, "video_art_style": []}, schema)
    assert not valid_input(values, {
        "type": "object", "properties": {"video_style": {"type": "string"}}})
    frozen = video_style(values, {"prompt": "photo", "media_type": "live_action"})
    assert frozen["prompt"] == "soft watercolor"
    assert "soft watercolor" in apply_style("original scene", frozen)
    assert video_style({**values, "video_style": "auto"}, None)["prompt"] == ""
    with pytest.raises(RegistryError):
        video_style({**values, "video_art_style": []}, None)
