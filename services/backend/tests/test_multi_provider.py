import pytest

from asa.config import Settings
from asa.registry.automations import Automation, check_flow
from asa.registry.runtime import RunRepository


def settings(**kwargs):
    return Settings(_env_file=None, ai_model='openai-test', ai_api_key='openai-secret',
                    anthropic_models=['claude-test'], automation_ai_enabled=True, **kwargs)


def test_keys_and_models_are_isolated():
    config = settings(anthropic_api_key='claude-secret')
    assert config.models_for('anthropic') == ['claude-test']
    assert config.models_for('openai') == ['openai-test']
    assert config.key_for('anthropic').get_secret_value() == 'claude-secret'
    assert config.key_for('openai').get_secret_value() == 'openai-secret'
    assert 'secret' not in config.model_dump_json()


def test_missing_claude_key_cannot_fallback_to_openai():
    repo = RunRepository(settings())
    assert not repo.ai_ready('claude-test', 'anthropic')
    assert not repo.ai_ready('openai-test', 'anthropic')
    assert repo.ai_ready('openai-test', 'openai')


def test_selected_claude_snapshot_and_removal():
    config = settings(anthropic_api_key='claude-secret')
    manifest = {'provider': 'anthropic', 'model': 'claude-test', 'model_selected': True}
    assert RunRepository(config).model_available(manifest)
    assert not RunRepository(config.model_copy(update={'anthropic_models': []})).model_available(
        manifest)
    assert not RunRepository(config).model_available({**manifest, 'provider': 'openai'})


@pytest.mark.parametrize('provider,model,valid', [
    ('anthropic', 'claude-test', True), ('anthropic', 'openai-test', False),
    ('anthropic', None, False), ('openai', 'claude-test', False), (None, None, True)])
def test_graph_provider_model_pair(provider, model, valid):
    draft = Automation.model_validate({'name': 'Providers', 'graph': {'nodes': [
        {'id': 'start', 'label': 'Start', 'kind': 'start'},
        {'id': 'ai', 'label': 'AI', 'kind': 'ai', 'provider': provider, 'model': model,
         'instructions': 'Echo', 'bindings': {'$': {'source': 'input'}}},
        {'id': 'end', 'label': 'End', 'kind': 'end'}], 'edges': [
        {'id': 'a', 'source': 'start', 'target': 'ai', 'port': 'next'},
        {'id': 'b', 'source': 'ai', 'target': 'end', 'port': 'next'}]}})
    assert (not check_flow(draft, [], settings())) == valid

@pytest.mark.parametrize('provider,model,key', [
    ('openai', 'openai-test', 'openai-secret'),
    ('anthropic', 'claude-test', 'claude-secret')])
def test_worker_uses_selected_provider_key(monkeypatch, provider, model, key):
    from asa.runtime_worker import generate

    calls = []

    class Model:
        def with_structured_output(self, schema):
            return self

        def invoke(self, messages):
            return {'value': 'sample'}

    def init(model_id, **kwargs):
        calls.append((model_id, kwargs['model_provider'], kwargs['api_key']))
        return Model()

    monkeypatch.setattr('asa.runtime_worker.init_chat_model', init)
    repo = RunRepository(settings(anthropic_api_key='claude-secret'))
    assert generate(repo, {'model': model, 'provider': provider,
                          'definition': {'instructions': 'Echo', 'limits': {'seconds': 60}},
                          'input_schema': {'type': 'string'},
                          'output_schema': {'type': 'string'}}, 'input') == 'sample'
    assert calls == [(model, provider, key)]
