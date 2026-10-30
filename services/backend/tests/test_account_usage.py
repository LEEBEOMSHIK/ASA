from datetime import UTC, datetime

import httpx
import pytest

from asa.config import Settings
from asa.registry.account_usage import OpenAIUsage


def test_missing_key_does_not_report_zero():
    result = OpenAIUsage(Settings(_env_file=None)).read()
    assert result['error_code'] == 'not_configured'
    assert result['data'] is None


def test_official_totals_pagination_and_stale_cache():
    calls = []
    failing = False
    now = datetime(2026, 10, 31, 12, tzinfo=UTC)
    tick = [1000.0]

    def handler(request):
        calls.append(request)
        assert request.headers['authorization'] == 'Bearer test-admin'
        assert request.url.params['project_ids'] == 'proj-test'
        if failing:
            return httpx.Response(403, json={'error': 'private error'})
        if request.url.path.endswith('costs'):
            second = 'page' in request.url.params
            rows = [{'amount': {'value': '0.2' if second else '0.1', 'currency': 'usd'}}]
            return httpx.Response(200, json={'data': [{'start_time': 1793404800,
                'results': rows}], 'has_more': not second,
                'next_page': None if second else 'next'})
        return httpx.Response(200, json={'data': [{'start_time': 1793404800,
            'results': [{'model': 'test', 'input_tokens': 100, 'output_tokens': 20,
                         'input_cached_tokens': 30, 'num_model_requests': 2}]}],
            'has_more': False})

    settings = Settings(_env_file=None, openai_admin_api_key='test-admin',
                        openai_usage_project_id='proj-test')
    service = OpenAIUsage(settings, transport=httpx.MockTransport(handler),
                          clock=lambda: tick[0], now=lambda: now)
    result = service.read()
    assert result['data']['costs']['month'] == '0.3'
    assert result['data']['tokens']['input_tokens'] == 100
    assert result['data']['tokens']['input_cached_tokens'] == 30
    assert len(calls) == 3
    service.read(force=True)
    assert len(calls) == 3
    tick[0] += 901
    failing = True
    result = service.read()
    assert result['stale'] is True and result['error_code'] == 'permission_denied'
    assert result['data']['costs']['month'] == '0.3'
    assert 'private' not in str(result)


@pytest.mark.parametrize('status,code', [(401, 'invalid_key'), (403, 'permission_denied'),
                                       (429, 'rate_limited'), (500, 'provider_unavailable')])
def test_errors_do_not_become_zero(status, code):
    service = OpenAIUsage(Settings(_env_file=None, openai_admin_api_key='secret'),
        transport=httpx.MockTransport(lambda r: httpx.Response(status, json={})))
    result = service.read()
    assert result['error_code'] == code
    assert result['data'] is None
    assert 'secret' not in str(result)


@pytest.mark.parametrize('payload', [None, {'data': [None], 'has_more': False},
                                    {'data': [], 'has_more': True, 'next_page': 'same'}])
def test_malformed_or_cyclic_pagination_is_unknown(payload):
    service = OpenAIUsage(Settings(_env_file=None, openai_admin_api_key='secret'),
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    assert service.read()['error_code'] == 'invalid_response'


def test_empty_success_is_zero():
    service = OpenAIUsage(Settings(_env_file=None, openai_admin_api_key='secret'),
        transport=httpx.MockTransport(lambda r: httpx.Response(200,
            json={'data': [], 'has_more': False})))
    result = service.read()
    assert result['error_code'] is None
    assert result['data']['costs']['today'] == '0'


def test_official_usage_requires_owner_in_configured_workspace():
    from uuid import uuid4
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from asa.auth.session import OwnerSessions, Principal
    from asa.registry.monitoring import monitoring_router

    settings = Settings(_env_file=None)
    sessions = OwnerSessions(settings)
    app = FastAPI()
    app.include_router(monitoring_router(settings, sessions))
    client = TestClient(app)
    url = '/api/v1/admin/ai-usage/openai-account'
    assert client.get(url).status_code == 401
    for roles, workspace in [(('admin',), settings.workspace_id), (('owner',), uuid4())]:
        app.dependency_overrides[sessions.principal] = lambda: Principal('test', workspace, roles)
        assert client.get(url).status_code == 403
    app.dependency_overrides[sessions.principal] = lambda: Principal('test', settings.workspace_id)
    assert client.get(url).json()['error_code'] == 'not_configured'
