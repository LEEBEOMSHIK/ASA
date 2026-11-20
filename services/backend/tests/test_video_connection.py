from uuid import uuid4

import httpx

from asa.config import Settings
from asa.video_connection import check, current


def settings():
    return Settings(workspace_id=uuid4(), wan_api_key="sk-ws-test", wan_workspace_id="ws-test")


def test_read_only_probe_and_expiry(monkeypatch):
    s = settings()
    def get(url, **kwargs):
        assert url.endswith('/api/v1/tasks')
        assert kwargs['params'] == {'page_size': 1}
        return httpx.Response(200, json={'data': []})
    monkeypatch.setattr(httpx, 'get', get)
    assert current(s, s.workspace_id, 'alibaba')['status'] == 'unchecked'
    assert check(s, s.workspace_id, 'alibaba')['status'] == 'authenticated'
    assert current(s, s.workspace_id, 'alibaba')['status'] == 'authenticated'
    changed = s.model_copy(update={'wan_region': 'ap-northeast-1'})
    assert current(changed, s.workspace_id, 'alibaba')['status'] == 'unchecked'
    assert current(s, uuid4(), 'alibaba')['status'] == 'unchecked'
    monkeypatch.setattr('asa.video_connection.monotonic', lambda: 10**20)
    assert current(s, s.workspace_id, 'alibaba')['status'] == 'unchecked'


def test_denied_and_secret_response_not_exposed(monkeypatch):
    s = settings()
    monkeypatch.setattr(httpx, 'get', lambda *a, **k: httpx.Response(401, json={
        'code': 'InvalidApiKey', 'message': 'sk-ws-test secret prompt',
        'request_id': '12345678-1234-1234-1234-123456789012'}))
    result = check(s, s.workspace_id, 'alibaba')
    assert result['status'] == 'denied'
    assert result['provider_code'] == 'InvalidApiKey'
    assert 'secret' not in str(result) and 'sk-ws-test' not in str(result)


def test_network_error_never_reports_ready(monkeypatch):
    s = settings()
    def get(*a, **k):
        raise httpx.ConnectError('sensitive')
    monkeypatch.setattr(httpx, 'get', get)
    assert check(s, s.workspace_id, 'alibaba')['status'] == 'unreachable'


def test_empty_task_page_can_omit_data(monkeypatch):
    s = settings()
    monkeypatch.setattr(httpx, 'get', lambda *a, **k: httpx.Response(200, json={
        'page_no': 1, 'page_size': 1, 'total_page': 0, 'request_id': str(uuid4())}))
    assert check(s, s.workspace_id, 'alibaba')['status'] == 'authenticated'
