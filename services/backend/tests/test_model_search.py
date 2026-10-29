from types import SimpleNamespace

import pytest

from asa.config import Settings
from asa.registry.graph_automation import GraphDefinition, graph_selection_issues
from asa.registry.runtime import RunRepository
from asa.tools.model_search import citation_link, normalize_search, search_answer


def message(provider, blocks, **metadata):
    status = {'status': 'completed'} if provider == 'openai' else {'stop_reason': 'end_turn'}
    return SimpleNamespace(content=blocks, response_metadata={**status, **metadata})


@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
def test_search_answer_has_sources_and_bound_calls(provider):
    citation = {'type': 'url_citation' if provider == 'openai' else 'web_search_result_location',
                'title': 'Source', 'url': 'https://example.com/article', 'end_index': 6}
    text = {'type': 'text', 'text': 'Answer',
            'annotations' if provider == 'openai' else 'citations': [citation]}
    call = ({'type': 'web_search_call', 'status': 'completed'} if provider == 'openai'
            else {'type': 'server_tool_use', 'name': 'web_search'})
    class Model:
        def bind_tools(self, tools, **kwargs):
            if provider == 'openai':
                assert tools == [{'type': 'web_search'}]
                assert kwargs == {'max_tool_calls': 1}
            else:
                assert tools[0]['max_uses'] == 1
                assert tools[0]['type'] == 'web_search_20250305'
            return self

        def invoke(self, messages):
            return message(provider, [call, text])

    output = search_answer(Model(), {'provider': provider, 'definition': {'instructions': 'Find'}},
                           'topic')
    assert 'Answer [Source](https://example.com/article)' in output
    assert output.startswith('웹 검색 사용')


@pytest.mark.parametrize('provider,meta', [
    ('openai', {'status': 'incomplete'}), ('anthropic', {'stop_reason': 'pause_turn'}),
    ('anthropic', {'stop_reason': 'max_tokens'})])
def test_incomplete_is_not_success(provider, meta):
    with pytest.raises(ValueError, match='incomplete_search'):
        normalize_search(message(provider, [{'type': 'text', 'text': 'partial'}], **meta), provider)


def test_search_tool_error_is_not_success():
    with pytest.raises(ValueError, match='search_tool_error'):
        normalize_search(message('anthropic', [
            {'type': 'web_search_tool_result', 'content': {
                'type': 'web_search_tool_result_error', 'error_code': 'unavailable'}},
            {'type': 'text', 'text': 'guess'}]), 'anthropic')


def test_no_search_is_labeled():
    result = normalize_search(message('openai', [{'type': 'text', 'text': 'Hello'}]), 'openai')
    assert result.startswith('웹 검색 미사용')


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'file:///secret', 'https://user:pass@host'])
def test_unsafe_citation_rejected(url):
    with pytest.raises(ValueError):
        citation_link({'url': url})


def test_citation_label_cannot_escape_link():
    link = citation_link({'url': 'https://example.com/a(b)', 'title': '[bad]\ntext'})
    assert link == '[(bad) text](https://example.com/a%28b%29)'


def test_search_permissions_rechecked_for_saved_run():
    settings = Settings(_env_file=None, ai_model='test', ai_api_key='fake',
                        automation_ai_enabled=True, openai_web_search_models=['test'])
    tool = {'provider': 'openai', 'model': 'test', 'model_selected': True, 'web_search': True}
    assert RunRepository(settings).model_available(tool)
    assert not RunRepository(settings.model_copy(update={
        'openai_web_search_models': []})).model_available(tool)


def test_graph_search_requires_text_and_allowlist():
    graph = GraphDefinition.model_validate({'nodes': [
        {'id': 'start', 'label': 'Start', 'kind': 'start'},
        {'id': 'ai', 'label': 'AI', 'kind': 'ai', 'web_search': True},
        {'id': 'end', 'label': 'End', 'kind': 'end'}], 'edges': []})
    settings = Settings(_env_file=None, ai_model='test', openai_web_search_models=['test'])
    assert not graph_selection_issues(graph, settings)
    graph.nodes[1].output_type = 'list'
    assert graph_selection_issues(graph, settings)
    graph.nodes[1].output_type = 'text'
    assert graph_selection_issues(
        graph, settings.model_copy(update={'openai_web_search_models': []}))

@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
def test_installed_langchain_sdk_search_contract(monkeypatch, provider):
    import json

    if provider == "anthropic":
        import httpx2 as httpx
    else:
        import httpx
    from langchain.chat_models import init_chat_model

    from asa.runtime_worker import generate

    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body['model'] == 'test-model'
        if provider == 'openai':
            assert request.url.path == '/v1/responses'
            assert body['tools'] == [{'type': 'web_search'}]
            assert body['max_tool_calls'] == 1
            assert body['store'] is False
            return httpx.Response(200, json={
                'id': 'resp_test', 'object': 'response', 'created_at': 1,
                'status': 'completed', 'model': 'test-model', 'output': [
                    {'id': 'ws_test', 'type': 'web_search_call', 'status': 'completed',
                     'action': {'type': 'search', 'query': 'test'}},
                    {'id': 'msg_test', 'type': 'message', 'status': 'completed',
                     'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Found',
                         'annotations': [{'type': 'url_citation', 'title': 'Source',
                                          'url': 'https://example.com',
                                          'start_index': 0, 'end_index': 5}]}]}]})
        assert request.url.path == '/v1/messages'
        assert body['tools'][0]['type'] == 'web_search_20250305'
        assert body['tools'][0]['max_uses'] == 1
        return httpx.Response(200, json={
            'id': 'msg_test', 'type': 'message', 'role': 'assistant', 'model': 'test-model',
            'stop_reason': 'end_turn', 'stop_sequence': None,
            'usage': {'input_tokens': 10, 'output_tokens': 10}, 'content': [
                {'type': 'server_tool_use', 'id': 'srv_1', 'name': 'web_search',
                 'input': {'query': 'test'}},
                {'type': 'text', 'text': 'Found', 'citations': [
                    {'type': 'web_search_result_location', 'url': 'https://example.com',
                     'title': 'Source', 'encrypted_index': 'test', 'cited_text': 'Found'}]}]})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    if provider == 'anthropic':
        monkeypatch.setattr('langchain_anthropic.chat_models._get_default_httpx_client',
                            lambda **kw: client)

    def init(model, **kwargs):
        if provider == 'openai':
            kwargs['http_client'] = client
        return init_chat_model(model, **kwargs)

    monkeypatch.setattr('asa.runtime_worker.init_chat_model', init)
    config = Settings(_env_file=None, ai_model='test-model', ai_api_key='fake',
                      anthropic_models=['test-model'], anthropic_api_key='fake',
                      openai_web_search_models=['test-model'],
                      anthropic_web_search_models=['test-model'], automation_ai_enabled=True)
    result = generate(RunRepository(config), {
        'provider': provider, 'model': 'test-model', 'model_selected': True, 'web_search': True,
        'output_schema': {'type': 'string'},
        'definition': {'instructions': 'Search', 'limits': {'seconds': 60}}}, 'test')
    assert '[Source](https://example.com)' in result
    assert len(requests) == 1
    client.close()
