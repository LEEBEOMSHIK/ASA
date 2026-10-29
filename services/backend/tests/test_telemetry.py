from decimal import Decimal

import pytest

from asa.config import ModelPrice, Settings
from asa.telemetry import estimate, normalize_usage, redact


def test_price_excludes_cache_from_regular_input_and_keeps_snapshot():
    usage = normalize_usage({'input_tokens': 1000, 'output_tokens': 200,
                             'input_token_details': {'cache_read': 300, 'cache_creation': 100}})
    price = ModelPrice(label='test-rate', input='2', output='8',
                       cache_read='0.5', cache_creation='3')
    assert estimate(usage, price) == (Decimal('0.00325'), 'estimated')
    assert estimate(usage, price, True) == (Decimal('0.00325'), 'tokens_only')
    assert estimate(usage, None) == (None, 'rate_missing')
    assert estimate(None, price) == (None, 'usage_unknown')
    assert estimate(usage, ModelPrice(label='no cache', input=2, output=8)) == (
        None, 'cache_rate_missing')


@pytest.mark.parametrize('usage', [None, {}, {'input_tokens': -1, 'output_tokens': 0},
    {'input_tokens': True, 'output_tokens': 0},
    {'input_tokens': 1, 'output_tokens': 0, 'input_token_details': {'cache_read': 2}}])
def test_missing_or_invalid_usage_is_not_zero(usage):
    assert normalize_usage(usage) is None


def test_real_zero_usage_is_distinct():
    usage = normalize_usage({'input_tokens': 0, 'output_tokens': 0})
    assert estimate(usage, ModelPrice(label='test', input=2, output=8)) == (0, 'estimated')


def test_anthropic_cache_ttl_is_not_counted_as_regular_input():
    usage = normalize_usage({'input_tokens': 1000, 'output_tokens': 20,
                             'input_token_details': {'cache_read': 200, 'cache_creation': 0,
                                                     'ephemeral_5m_input_tokens': 100,
                                                     'ephemeral_1h_input_tokens': 200}})
    price = ModelPrice(label='ttl', input=2, output=8, cache_read=1,
                       cache_creation_5m=3, cache_creation_1h=4)
    assert estimate(usage, price) == (Decimal('0.00246'), 'estimated')
    assert estimate(usage, ModelPrice(label='generic', input=2, output=8, cache_read=1,
                                      cache_creation=3)) == (None, 'cache_rate_missing')


def test_redaction_and_bounded_payloads():
    settings = Settings(_env_file=None, ai_api_key='private-value')
    value = redact({'api_key': 'anything', 'message': 'key private-value Bearer abc123'}, settings)
    assert value == {'api_key': '[REDACTED]', 'message': 'key [REDACTED] Bearer [REDACTED]'}
    assert redact('a' * 65000, settings)['truncated']
    serialized = '{"password":"hunter2", "nested":{"api_key":"other-key"}}'
    redacted = redact(serialized, settings)
    assert 'hunter2' not in redacted and 'other-key' not in redacted


@pytest.mark.parametrize('price', [-1, 'NaN', 'Infinity'])
def test_invalid_rate_rejected(price):
    with pytest.raises(ValueError):
        ModelPrice(label='test', input=price, output=1)
