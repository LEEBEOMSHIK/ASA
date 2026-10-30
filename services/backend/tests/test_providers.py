import pytest

from asa.config import Settings
from asa.providers import make_script_generator


def test_provider_requires_explicit_model_and_key():
    settings = Settings(_env_file=None, ai_model="", ai_api_key="")
    with pytest.raises(ValueError, match="ASA_AI_MODEL"):
        make_script_generator(settings)


def test_script_generator_caps_output_tokens(monkeypatch):
    captured = {}
    class Model:
        def with_structured_output(self, schema):
            return self
    def init(model, **kwargs):
        captured.update(kwargs)
        return Model()
    monkeypatch.setattr('asa.providers.init_chat_model', init)
    make_script_generator(Settings(_env_file=None, ai_model='test', ai_api_key='fake'))
    assert captured['max_tokens'] == 2048

@pytest.mark.parametrize('schema,value', [({'type': 'string', 'maxLength': 500}, 'A useful answer'), ({'type': 'object', 'properties': {'summary': {'type': 'string'}, 'tags': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['summary', 'tags']}, {'summary': 'Summary', 'tags': ['one']})])
def test_agent_contract_uses_registered_instructions(monkeypatch, schema, value):
    import json
    from asa.providers import make_agent_generator
    captured = {}
    class Model:
        def with_structured_output(self, spec):
            captured['schema'] = spec
            return self
        def invoke(self, messages, **kwargs):
            captured['messages'] = messages
            return {'value': value}
    monkeypatch.setattr('asa.providers.init_chat_model', lambda *a, **k: Model())
    prompt = json.dumps({'agent_instructions': 'You are a helpful analyst.', 'output_schema': schema,
                         'input_schema': {'type': 'string', 'description': '질문'},
                         'original_request': 'Explain', 'previous_answer': 'Old', 'revision_request': 'Improve'})
    assert make_agent_generator(Settings(_env_file=None, ai_model='test', ai_api_key='fake'))(prompt).value == value
    assert captured['messages'][0] == ('system', 'You are a helpful analyst.')
    assert captured['schema']['properties']['value'] == schema
    assert 'previous_answer' in captured['messages'][1][1]
    assert json.loads(captured['messages'][1][1])['input_schema']['description'] == '질문'
    assert 'short-video' not in str(captured['messages'])


def test_automation_model_receives_input_labels(monkeypatch):
    import json
    from types import SimpleNamespace
    from asa.runtime_worker import generate
    captured = {}
    class Model:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages, **kwargs):
            captured['messages'] = messages
            return {'value': 'answer'}
    monkeypatch.setattr('asa.runtime_worker.init_chat_model', lambda *a, **k: Model())
    schema = {'type': 'object', 'properties': {
        'field_1': {'type': 'integer', 'description': '무서운 정도', 'minimum': 1, 'maximum': 5}}}
    tool = {'model': 'test', 'provider': 'openai', 'input_schema': schema,
            'output_schema': {'type': 'string'},
            'definition': {'instructions': 'Use the input.', 'limits': {'seconds': 60}}}
    repo = SimpleNamespace(settings=Settings(_env_file=None, ai_api_key='fake'))
    assert generate(repo, tool, {'field_1': 3}) == 'answer'
    sent = json.loads(captured['messages'][1][1])
    assert sent == {'input': {'field_1': 3}, 'input_schema': schema}


@pytest.mark.parametrize("invalid", [False, True])
def test_agent_stream_public_brief_and_partial_answer(monkeypatch, invalid):
    import json
    from asa.providers import make_agent_generator
    received = []
    called = []

    class Model:
        def with_structured_output(self, spec):
            assert list(spec['properties']) == ['understanding', 'direction', 'value']
            return self

        def stream(self, messages, **kwargs):
            called.append(messages)
            yield {'understanding': '요청 요약'}
            yield {'understanding': '요청 요약', 'direction': '작성 방향', 'value': '시작'}
            assert received[-1]['value'] == '시작'
            yield {'understanding': '요청 요약', 'direction': '작성 방향',
                   'value': 123 if invalid else '시작과 끝'}

    monkeypatch.setattr('asa.providers.init_chat_model', lambda *a, **k: Model())
    generate = make_agent_generator(
        Settings(_env_file=None, ai_model='test', ai_api_key='fake'), received.append)
    prompt = json.dumps({'agent_instructions': '사용자 역할',
                         'output_schema': {'type': 'string'}, 'original_request': '요청'})
    if invalid:
        with pytest.raises(ValueError, match='invalid_agent_output'):
            generate(prompt)
    else:
        assert generate(prompt).value == '시작과 끝'
    assert len(called) == 1
    assert len(received) == 3
