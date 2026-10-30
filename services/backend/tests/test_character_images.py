from decimal import Decimal

import pytest

from asa.tools.character_images import image_cost, image_prompt


def test_image_cost_distinguishes_text_and_image_input():
    usage = {'input_tokens': 120, 'output_tokens': 400,
             'input_tokens_details': {'text_tokens': 100, 'image_tokens': 20}}
    assert image_cost(usage) == Decimal('0.01266')
    assert image_cost(None) is None
    assert image_cost({'input_tokens': 120, 'output_tokens': 400}) is None
    assert image_cost({**usage, 'input_tokens': 121}) is None


def test_edit_prompt_keeps_character_and_scopes_requested_change():
    prompt = image_prompt({'name': '하나', 'appearance': '노란 우비',
                           'image_prompt': '정면 전신'}, '모자만 파란색으로')
    assert '노란 우비' in prompt
    assert '모자만 파란색으로' in prompt
    assert 'reference' in prompt


def test_invalid_usage_is_not_free():
    with pytest.raises(ValueError):
        image_prompt({}, '')
    assert image_cost({'input_tokens': -1, 'output_tokens': 2}) is None
