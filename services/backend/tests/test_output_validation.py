import json
from copy import deepcopy

import pytest

from asa.config import Settings
from asa.output_validation import output_issues, strict_output_schema
from asa.providers import make_agent_generator

SCHEMA = {'type': 'object', 'properties': {'clips': {'type': 'array', 'items': {
    'type': 'object', 'properties': {
        'source_start_seconds': {'type': 'integer', 'minimum': 0, 'maximum': 100},
        'source_end_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 100},
        'continuity_in': {'type': 'string', 'maxLength': 100}},
    'required': ['source_start_seconds', 'source_end_seconds', 'continuity_in']}}},
    'required': ['clips']}


def test_diagnostics_preserve_data_and_do_not_leak_output():
    value = {'clips': [{'continuity_in': 'private text' * 20}]}
    original = deepcopy((value, SCHEMA))
    issues = output_issues(value, SCHEMA)
    assert len(issues) == 3
    assert 'source_start_seconds' in issues[0]
    assert 'source_end_seconds' in issues[1]
    assert '100자 제한' in issues[2]
    assert 'private' not in str(issues)
    assert (value, SCHEMA) == original
    assert output_issues(None, SCHEMA) == []


@pytest.mark.parametrize('streaming', [True, False])
@pytest.mark.parametrize('invalid', [True, False])
def test_video_generation_strict_contract_and_final_validation(monkeypatch, streaming, invalid):
    captured = {}
    value = {'clips': [{'source_start_seconds': 0, 'source_end_seconds': 5,
                        'continuity_in': '짧은 시작 모습'}]}
    if invalid:
        value['clips'][0].pop('source_end_seconds')

    class Model:
        def with_structured_output(self, schema, **kwargs):
            captured.update(schema=schema, options=kwargs)
            return self

        def invoke(self, messages, **kwargs):
            captured['messages'] = messages
            return {'value': value}

        def stream(self, messages, **kwargs):
            yield self.invoke(messages)

    monkeypatch.setattr('asa.providers.init_chat_model', lambda *a, **kw: Model())
    monkeypatch.setattr('asa.registry.video_planning.planner_constraints', lambda *a: '영상 계약')
    schema = deepcopy(SCHEMA)
    generator = make_agent_generator(
        Settings(_env_file=None, ai_model='test', ai_api_key='fake'),
        (lambda _: None) if streaming else None)
    prompt = json.dumps({'agent_instructions': '클립 작성', 'output_schema': schema})
    if invalid:
        with pytest.raises(ValueError, match='invalid_agent_output'):
            generator(prompt)
    else:
        assert generator(prompt).value == value
    assert captured['options'] == {'method': 'json_schema', 'strict': True}
    clip = captured['schema']['properties']['value']['properties']['clips']['items']
    assert clip['additionalProperties'] is False
    assert clip['required'] == list(clip['properties'])
    assert clip['properties']['continuity_in']['maxLength'] == 100
    assert 'source_end_seconds' in str(captured['messages'])
    assert 'maxLength' in str(captured['messages'])
    assert schema == SCHEMA


def test_strict_schema_does_not_mutate_stored_contract():
    schema = {'type': 'object', 'properties': {'optional': {'type': 'string'}}}
    strict = strict_output_schema(schema)
    assert strict['required'] == ['optional']
    assert 'required' not in schema
