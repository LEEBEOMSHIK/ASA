from asa.registry.art_styles import apply_style
from asa.tools.character_images import image_prompt


def test_default_live_action_is_explicit_even_without_custom_prompt():
    result = apply_style("legacy 2D", {"media_type": "live_action", "prompt": ""})
    assert "photographic" in result
    assert "stylized proportions" in result
    assert "not a cartoon" in result


def test_reference_style_preservation_defers_to_common_style():
    result = image_prompt({"name": "child", "appearance": "red coat"}, "restyle")
    assert "preserve its face, proportions, style and clothes" not in result
    assert "WORK ART STYLE POLICY" in result
