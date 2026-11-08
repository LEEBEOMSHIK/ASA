import pytest
from pydantic import ValidationError

from asa.registry.navigation_colors import NavigationColorEdit


@pytest.mark.parametrize("color", ["#000000", "#ffffff", "#3B82F6", "#Aa00Ff", "blue", None])
def test_navigation_color_supports_hex_and_existing_palette(color):
    assert NavigationColorEdit(color=color, revision=0).color == (color.lower() if color else None)


@pytest.mark.parametrize("color", ["#fff", "#12345678", "123456", "#12zz34", "red;", "", 12])
def test_navigation_color_rejects_invalid_or_css_payloads(color):
    with pytest.raises(ValidationError):
        NavigationColorEdit(color=color, revision=0)
