import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from asa.api import create_app
from asa.config import Settings
from asa.registry.repository import RegistryRepository, migrate
from asa.registry.schemas import AgentDraft

ORIGIN = {"Origin": "http://testserver"}
KEY = "test-only-owner-key-" + "x" * 32


def test_monitoring_capture_trace_filters_isolation(client, db):
    from datetime import UTC, datetime, timedelta

    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage

    from asa.telemetry import call_config, trace_call

    login(client)
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        ai_api_key='private-value', ai_prices={
                            'openai:test': {'label': 'test-rate', 'input': '2', 'output': '8'}})
    context = dict(run_id=str(uuid4()), request_id=str(uuid4()), source='automation',
                   requested_by='local-owner', automation_id=str(uuid4()), name='고양이 자동화',
                   revision=2, step_id='writer:1',
                   step_name='대본 작성', provider='openai', model='test',
                   original_request='고양이')
    model = FakeMessagesListChatModel(responses=[AIMessage(content='answer', usage_metadata={
        'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120})])
    with trace_call(settings, context) as capture:
        model.invoke([('system', 'Write safely'), ('human', 'private-value')], **call_config())
    url = f'/api/v1/admin/ai-usage/{capture.id}'
    detail = client.get(url).json()
    assert detail['original_request'] == '고양이'
    assert detail['messages'][0][1]['content'] == '[REDACTED]'
    assert detail['usage']['input_tokens'] == 100
    assert float(detail['estimated_usd']) == pytest.approx(0.00036)
    assert detail['duration_ms'] >= 0
    assert detail['pricing']['label'] == 'test-rate'
    assert detail['requested_by'] == 'local-owner'
    # Parsing failure after a response must preserve tokens and estimated charges.
    with pytest.raises(ValueError), trace_call(
        settings, {**context, 'step_id': 'writer:2', 'name': '이름 변경'}
    ):
        model.invoke('second', **call_config())
        raise ValueError('private provider error')
    with pytest.raises(TimeoutError), trace_call(settings, {**context, 'step_id': 'writer:3'}):
        raise TimeoutError('private provider error')
    data = client.get('/api/v1/admin/ai-usage').json()
    assert data['summary']['calls'] == 3
    assert len(data['automations']) == 1
    assert data['automations'][0]['calls'] == 3
    assert data['summary']['runs'] == 1
    assert data['summary']['failed'] == 2
    assert data['summary']['usage_unknown'] == 1
    assert data['summary']['cost_unknown'] == 1
    assert 'messages' not in data['items'][0]
    assert 'original_request' not in data['items'][0]
    filtered = client.get('/api/v1/admin/ai-usage?q=고양이&status=succeeded').json()
    assert filtered['summary']['calls'] == 1
    assert client.get('/api/v1/admin/ai-usage?provider=anthropic').json()['summary']['calls'] == 0
    future = (datetime.now(UTC)+timedelta(days=2)).isoformat()
    later = (datetime.now(UTC)+timedelta(days=3)).isoformat()
    assert client.get('/api/v1/admin/ai-usage', params={'start': future, 'end': later}).json()[
        'summary']['calls'] == 0
    assert client.get('/api/v1/admin/ai-usage?start=2026-01-01').status_code == 422
    other = uuid4()
    migrate(db[0], other)
    with TestClient(create_app(Settings(_env_file=None, database_url=db[0], workspace_id=other,
                    owner_access_key=KEY, allowed_origins=['http://testserver']))) as foreign:
        assert foreign.get('/api/v1/admin/ai-usage').status_code == 401
        login(foreign)
        assert foreign.get(url).status_code == 404
        assert foreign.get('/api/v1/admin/ai-usage').json()['summary']['calls'] == 0


def test_monitoring_rejects_non_admin(db, monkeypatch):
    from asa.auth.session import OwnerSessions, Principal

    monkeypatch.setattr(OwnerSessions, 'principal', lambda self: Principal(
        user_id='member', workspace_id=db[1], roles=('member',)))
    with TestClient(create_app(Settings(_env_file=None, database_url=db[0]))) as member:
        assert member.get('/api/v1/admin/ai-usage').status_code == 403
        assert member.get(f'/api/v1/admin/ai-usage/{uuid4()}').status_code == 403


@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
def test_monitoring_real_sdk_usage_without_network(client, db, monkeypatch, provider):
    if provider == "anthropic":
        import httpx2 as httpx
    else:
        import httpx
    from langchain.chat_models import init_chat_model

    from asa.registry.runtime import RunRepository
    from asa.runtime_worker import generate
    from asa.telemetry import trace_call

    login(client)
    requests = []

    def respond(request):
        requests.append(request)
        if provider == 'openai':
            return httpx.Response(200, json={
                'id': 'chatcmpl-test', 'object': 'chat.completion', 'created': 1, 'model': 'test',
                'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {
                    'role': 'assistant', 'content': '{"value":"hello"}'}}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120,
                          'prompt_tokens_details': {'cached_tokens': 30}}})
        return httpx.Response(200, json={
            'id': 'msg_test', 'type': 'message', 'role': 'assistant', 'model': 'test',
            'stop_reason': 'tool_use', 'stop_sequence': None,
            'usage': {'input_tokens': 70, 'output_tokens': 20, 'cache_read_input_tokens': 30},
            'content': [{'type': 'tool_use', 'id': 'tool_1', 'name': 'AutomationAnswer',
                         'input': {'value': 'hello'}}]})

    transport = httpx.Client(transport=httpx.MockTransport(respond))
    if provider == 'anthropic':
        monkeypatch.setattr('langchain_anthropic.chat_models._get_default_httpx_client',
                            lambda **kwargs: transport)

    def init(model, **kwargs):
        if provider == 'openai':
            kwargs['http_client'] = transport
        return init_chat_model(model, **kwargs)

    monkeypatch.setattr('asa.runtime_worker.init_chat_model', init)
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        ai_api_key='fake', anthropic_api_key='fake', ai_prices={
                            f'{provider}:test': {'label': 'synthetic', 'input': 2, 'output': 8,
                                                'cache_read': 1}})
    context = dict(run_id=str(uuid4()), request_id=str(uuid4()), source='cli', name='SDK test',
                   step_id='ai', step_name='AI', provider=provider, model='test')
    with trace_call(settings, context) as capture:
        result = generate(RunRepository(settings), {
            'provider': provider, 'model': 'test', 'output_schema': {'type': 'string'},
            'definition': {'instructions': 'Write', 'limits': {'seconds': 60}}}, 'hello')
    assert result == 'hello' and len(requests) == 1
    detail = client.get(f'/api/v1/admin/ai-usage/{capture.id}').json()
    assert detail['usage']['input_tokens'] == 100
    assert detail['usage']['output_tokens'] == 20
    assert detail['usage']['cache_read'] == 30
    assert float(detail['estimated_usd']) == pytest.approx(0.00033)
    assert 'hello' in str(detail['response'])
    assert detail['duration_ms'] is not None
    transport.close()


def test_monitoring_pagination_totals_and_unknown_cost(client, db):
    from psycopg.types.json import Jsonb

    login(client)
    with psycopg.connect(db[0]) as conn:
        for index in range(27):
            conn.execute('INSERT INTO ai_usage_events(workspace_id,id,run_id,request_id,source,'
                         'name,step_id,step_name,provider,model,usage) '
                         'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                         (db[1], uuid4(), 'run', 'request', 'schedule', '예약', str(index),
                          '반복', 'anthropic', 'test', Jsonb(None)))
    first = client.get('/api/v1/admin/ai-usage').json()
    second = client.get('/api/v1/admin/ai-usage?offset=25').json()
    assert first['summary']['calls'] == second['summary']['calls'] == 27
    assert first['summary']['estimated_usd'] is None
    assert first['summary']['incomplete'] == 27
    assert len(first['items']) == 25 and first['has_more']
    assert len(second['items']) == 2 and not second['has_more']
    assert {r['id'] for r in first['items']}.isdisjoint(r['id'] for r in second['items'])


def script_work(client):
    headers = login(client)
    agent = client.post("/api/v1/agents", json=definition(), headers=headers).json()
    client.post(f"/api/v1/agents/{agent['id']}/publish", headers={**headers, "If-Match": '"1"'})
    work = client.post("/api/v1/work-requests", headers=headers, json={
        "id": str(uuid4()), "agent_id": agent["id"], "version": 1,
        "input": {"topic": "고양이"},
    }).json()
    return headers, work, f"/api/v1/work-requests/{work['id']}/script"


def runtime_flow(client, review=False):
    headers = login(client)
    body = {"id": str(uuid4()), "revision": 0, "draft": {"name": "실행 검증", "steps": [
        {"id": "inspect", "label": "길이 검사", "tool_id": "asa.text.inspect:1",
         "review_after": review, "bindings": {"text": {"source": "input"},
         "limit": {"source": "literal", "value": 10}}}]}}
    assert client.post("/api/v1/automations", json=body, headers=headers).status_code == 200
    return headers, body


def test_runtime_pinned_idempotent_review_and_isolation(client, db):
    from asa.registry.runtime import RunRepository
    from asa.runtime_worker import tick

    headers, saved = runtime_flow(client, True)
    body = {"id": str(uuid4()), "revision": 1, "prompt": "대본"}
    url = f"/api/v1/automations/{saved['id']}/runs"
    assert client.post(url, json=body, headers=ORIGIN).status_code == 403
    assert client.post(url, json=body, headers=headers).status_code == 201
    assert client.post(url, json=body, headers=headers).status_code == 201
    assert client.post(url, json={**body, "prompt": "다름"}, headers=headers).status_code == 409
    saved["draft"]["steps"][0]["bindings"]["limit"]["value"] = 1
    assert client.post("/api/v1/automations", json={**saved, "revision": 1},
                       headers=headers).status_code == 200
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1])
    repo = RunRepository(settings)
    assert tick(repo)
    detail_url = f"/api/v1/automation-runs/{body['id']}"
    detail = client.get(detail_url).json()
    assert detail["status"] == "waiting_review"
    assert detail["steps"][0]["output"]["characters"] == 2
    assert detail["steps"][0]["output"]["limit"] == 10
    assert client.post(detail_url + "/approve", json={"next_step": 1},
                       headers=headers).status_code == 200
    assert tick(repo)
    assert client.get(detail_url).json()["status"] == "succeeded"
    assert not tick(repo)

    other = uuid4()
    migrate(db[0], other)
    with TestClient(create_app(Settings(_env_file=None, database_url=db[0], workspace_id=other,
                    owner_access_key=KEY, allowed_origins=["http://testserver"]))) as foreign:
        login(foreign)
        assert foreign.get(detail_url).status_code == 404


def test_runtime_external_failure_budget_and_restart(client, db, monkeypatch):
    from uuid import UUID

    from asa.registry.runtime import RunInput, RunRepository
    from asa.runtime_worker import tick

    headers = login(client)
    agent = client.post("/api/v1/agents", json=definition(), headers=headers).json()
    client.post(f"/api/v1/agents/{agent['id']}/publish",
                headers={**headers, "If-Match": '"1"'})
    aid = uuid4()
    draft = {"name": "외부 응답 모의 검증", "steps": [{"id": "writer", "label": "작가",
        "tool_id": f"agent:{agent['id']}:1", "bindings": {"topic": {"source": "input"}}}]}
    client.post("/api/v1/automations", headers=headers,
                json={"id": str(aid), "revision": 0, "draft": draft})
    blocked = client.post(f"/api/v1/automations/{aid}/runs", headers=headers,
                          json={"id": str(uuid4()), "revision": 1, "prompt": "주제"})
    assert blocked.status_code == 422
    repo = RunRepository(Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
        automation_ai_enabled=True, ai_model="mock-only", ai_api_key="not-a-real-key",
        automation_daily_ai_calls=1))
    calls = []

    def broken(*_):
        calls.append(1)
        raise TimeoutError("secret-provider-response")

    monkeypatch.setattr("asa.runtime_worker.generate", broken)
    first = uuid4()
    repo.enqueue(aid, RunInput(id=first, revision=1, prompt="주제"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: tick(repo), range(2)))
    assert outcomes.count(True) == 1 and len(calls) == 1
    result = repo.detail(first)
    assert result["status"] == "needs_attention"
    assert "secret-provider-response" not in str(result)
    second = uuid4()
    repo.enqueue(aid, RunInput(id=second, revision=1, prompt="다음"))
    assert tick(repo)
    assert repo.detail(second)["status"] == "failed" and len(calls) == 1
    third = uuid4()
    repo.enqueue(aid, RunInput(id=third, revision=1, prompt="중단"))
    with psycopg.connect(db[0]) as conn:
        conn.execute("UPDATE automation_runs SET status='running' WHERE id=%s", (third,))
    assert not tick(repo)
    assert repo.detail(UUID(str(third)))["status"] == "needs_attention" and len(calls) == 1


def test_runtime_daily_coalesces_missed_and_skips_active(client, db):
    from datetime import UTC, datetime, timedelta
    from uuid import UUID

    from asa.registry.runtime import RunRepository, ScheduleInput

    _, saved = runtime_flow(client)
    repo = RunRepository(Settings(_env_file=None, database_url=db[0], workspace_id=db[1]))
    aid = UUID(saved["id"])
    repo.save_schedule(aid, ScheduleInput(revision=1, schedule_revision=0, enabled=True,
                                        kind="daily", time="09:00", prompt="주제"))
    future = datetime.now(UTC) + timedelta(days=5)
    assert repo.dispatch_due(future) == 1
    assert repo.dispatch_due(future) == 0
    assert repo.dispatch_due(future + timedelta(days=1)) == 0
    assert len(repo.runs(aid)) == 1
    assert "건너" in repo.schedule(aid)["note"]
    repo.disable_schedule(aid)
    assert repo.dispatch_due(future + timedelta(days=9)) == 0


def test_runtime_schedule_dedup_and_cancel(client, db):
    from datetime import UTC, datetime, timedelta

    from asa.registry.runtime import RunRepository
    from asa.runtime_worker import tick

    headers, saved = runtime_flow(client)
    url = f"/api/v1/automations/{saved['id']}/schedule"
    due = datetime.now(UTC) + timedelta(hours=1)
    body = {"revision": 1, "schedule_revision": 0, "enabled": True, "kind": "once",
            "at": due.isoformat(), "time": "09:00", "prompt": "예약 테스트"}
    assert client.put(url, json=body, headers=headers).status_code == 200
    assert client.put(url, json=body, headers=headers).status_code == 409
    repo = RunRepository(Settings(_env_file=None, database_url=db[0], workspace_id=db[1]))
    assert repo.dispatch_due(due + timedelta(minutes=1)) == 1
    assert repo.dispatch_due(due + timedelta(minutes=1)) == 0
    runs = client.get(f"/api/v1/automations/{saved['id']}/runs").json()
    assert len(runs) == 1
    assert client.post(f"/api/v1/automation-runs/{runs[0]['id']}/cancel",
                       headers=headers).status_code == 200
    assert not tick(repo)


def test_runtime_stale_review_cannot_approve_next_stage(client, db):
    from asa.registry.runtime import RunRepository
    from asa.runtime_worker import tick

    headers, saved = runtime_flow(client, True)
    second = {**saved["draft"]["steps"][0], "id": "second"}
    saved["draft"]["steps"].append(second)
    client.post("/api/v1/automations", json={**saved, "revision": 1}, headers=headers)
    run_id = str(uuid4())
    client.post(f"/api/v1/automations/{saved['id']}/runs", headers=headers,
                json={"id": run_id, "revision": 2, "prompt": "검증"})
    repo = RunRepository(Settings(_env_file=None, database_url=db[0], workspace_id=db[1]))
    assert tick(repo)

    url = f"/api/v1/automation-runs/{run_id}/approve"
    assert client.post(url, headers=headers, json={"next_step": 1}).status_code == 200
    assert tick(repo)
    assert client.post(url, headers=headers, json={"next_step": 1}).status_code == 409
    assert client.post(url, headers=headers, json={"next_step": 2}).status_code == 200
    assert tick(repo)


def test_runtime_mock_agent_output_reaches_tool(client, db, monkeypatch):
    from asa.registry.runtime import RunInput, RunRepository
    from asa.runtime_worker import tick

    headers = login(client)
    agent = client.post("/api/v1/agents", json=definition(), headers=headers).json()
    client.post(f"/api/v1/agents/{agent['id']}/publish",
                headers={**headers, "If-Match": '"1"'})
    aid, rid = uuid4(), uuid4()
    draft = {"name": "모의 AI 연결", "steps": [
        {"id": "writer", "label": "대본", "tool_id": f"agent:{agent['id']}:1",
         "bindings": {"topic": {"source": "input"}}},
        {"id": "inspect", "label": "검사", "tool_id": "asa.text.inspect:1", "bindings": {
            "text": {"source": "writer", "field": "script"},
            "limit": {"source": "literal", "value": 10}}}]}
    client.post("/api/v1/automations", headers=headers,
                json={"id": str(aid), "revision": 0, "draft": draft})
    repo = RunRepository(Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
        automation_ai_enabled=True, ai_model="mock-only", ai_api_key="not-a-real-key"))
    calls = []

    def fake(_, tool, actual):
        calls.append(actual)
        assert tool["definition"]["instructions"] == "따뜻한 대본 작성"
        return {"script": "고양이 대본"}

    monkeypatch.setattr("asa.runtime_worker.generate", fake)
    repo.enqueue(aid, RunInput(id=rid, revision=1, prompt="고양이"))
    assert tick(repo) and not tick(repo)
    result = repo.detail(rid)
    assert result["status"] == "succeeded"
    assert result["steps"][1]["output"]["characters"] == 6
    assert calls == [{"topic": "고양이"}]


def test_automation_storage_conflict_and_workspace_boundary(client, db):
    headers = login(client)
    draft = {"name": "연결 테스트", "steps": [{"id": "inspect", "label": "검사",
        "tool_id": "asa.text.inspect:1", "bindings": {"text": {"source": "input"},
        "limit": {"source": "literal", "value": 3}}}]}
    body = {"id": str(uuid4()), "revision": 0, "draft": draft}
    assert client.post("/api/v1/automations", json=body, headers=ORIGIN).status_code == 403
    saved = client.post("/api/v1/automations", json=body, headers=headers)
    assert saved.status_code == 200
    assert saved.json()["revision"] == 1
    assert client.post("/api/v1/automations", json=body, headers=headers).json()["revision"] == 1
    assert len(client.get("/api/v1/automations").json()) == 1
    update = {**body, "revision": 1, "draft": {**draft, "name": "수정"}}
    assert client.post("/api/v1/automations", json=update, headers=headers).json()["revision"] == 2
    assert client.post("/api/v1/automations", json=update, headers=headers).status_code == 409
    assert client.post("/api/v1/automations/validate", json=draft,
                       headers=headers).json()["issues"] == []
    result = client.post("/api/v1/automations/preview", headers=headers,
                         json={"draft": draft, "prompt": "안녕하세요"}).json()
    assert result["paid_calls"] == 0
    assert result["results"][0]["output"]["characters"] == 5
    agent = client.post("/api/v1/agents", json=definition(), headers=headers).json()
    client.post(f"/api/v1/agents/{agent['id']}/publish",
                headers={**headers, "If-Match": '"1"'})
    foreign_draft = {"name": "격리", "steps": [{"id": "writer", "label": "작가",
        "tool_id": f"agent:{agent['id']}:1", "bindings": {"topic": {"source": "input"}}}]}
    other = uuid4()
    migrate(db[0], other)
    with TestClient(create_app(Settings(_env_file=None, database_url=db[0],
                    owner_access_key=KEY, workspace_id=other,
                    allowed_origins=["http://testserver"]))) as foreign:
        foreign_headers = login(foreign)
        assert foreign.get("/api/v1/automations").json() == []
        assert foreign.post("/api/v1/automations", json=update,
                            headers=foreign_headers).status_code == 404
        assert foreign.post("/api/v1/automations/validate", json=foreign_draft,
                            headers=foreign_headers).json()["issues"]


def test_script_versions_approval_and_scoped_regeneration(client, db):
    headers, work, url = script_work(client)
    initial = client.get(url)
    assert initial.status_code == 200
    assert initial.json()["versions"] == []
    body = {"id": str(uuid4()), "expected_revision": 0, "title": "첫 제목",
            "narration": "첫 대본"}
    assert client.post(url + "/versions", json=body, headers=ORIGIN).status_code == 403
    saved = client.post(url + "/versions", json=body, headers=headers)
    assert saved.status_code == 201
    assert saved.json()["head_version"] == 1
    assert client.post(url + "/versions", json=body, headers=headers).json()["head_version"] == 1
    assert client.post(url + "/approve", json={"expected_revision": 1, "version": 1},
                       headers=headers).json()["approved_version"] == 1
    attempt_id = str(uuid4())
    request = {"id": attempt_id, "expected_revision": 2, "base_version": 1,
               "instruction": "더 짧게"}
    queued = client.post(url + "/generate", json=request, headers=headers)
    assert queued.status_code == 201
    assert queued.json()["attempts"][0]["status"] == "queued"
    assert client.post(url + "/versions", json={**body, "id": str(uuid4()),
                       "expected_revision": 3}, headers=headers).status_code == 409
    from asa.models import Script
    from asa.registry.script_stage import ScriptRepository, execute_attempt

    repo = ScriptRepository(db[0], db[1])
    calls = []

    def generate(prompt):
        calls.append(prompt)
        return Script(title="짧은 제목", narration="짧은 대본")

    assert execute_attempt(repo, work["id"], attempt_id, generate)
    assert not execute_attempt(repo, work["id"], attempt_id, generate)
    assert len(calls) == 1 and "더 짧게" in calls[0] and "첫 대본" in calls[0]
    result = client.get(url).json()
    assert result["head_version"] == 2 and result["approved_version"] is None
    assert [v["narration"] for v in result["versions"]] == ["짧은 대본", "첫 대본"]
    assert result["attempts"][0]["status"] == "succeeded"
    assert client.get(f"/api/v1/work-requests/{work['id']}").json()["result"] is None
    assert client.post(url + "/versions", json={**body, "id": str(uuid4())},
                       headers=headers).status_code == 409


def test_script_stage_isolation_and_failed_execution_preserves_draft(client, db):
    headers, work, url = script_work(client)
    body = {"id": str(uuid4()), "expected_revision": 0, "title": "보존", "narration": "보존"}
    client.post(url + "/versions", json=body, headers=headers)
    attempt_id = str(uuid4())
    client.post(url + "/generate", headers=headers, json={
        "id": attempt_id, "expected_revision": 1, "base_version": 1, "instruction": "수정",
    })
    from asa.registry.script_stage import ScriptRepository, execute_attempt

    def broken(_):
        raise TimeoutError("private-provider-message")

    execute_attempt(ScriptRepository(db[0], db[1]), work["id"], attempt_id, broken)
    state = client.get(url).json()
    assert state["head_version"] == 1
    assert state["attempts"][0]["status"] == "unknown"
    assert "private-provider-message" not in str(state)
    other = uuid4()
    migrate(db[0], other)
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=other,
                        owner_access_key=KEY, allowed_origins=["http://testserver"])
    with TestClient(create_app(settings)) as foreign:
        foreign_headers = login(foreign)
        assert foreign.get(url).status_code == 404
        denied = foreign.post(url + "/versions", json=body, headers=foreign_headers)
        assert denied.status_code == 404


def test_customer_history_pagination_keeps_all_old_requests(client, db):
    headers = login(client)
    agent = client.post("/api/v1/agents", json=definition(), headers=headers).json()
    client.post(f"/api/v1/agents/{agent['id']}/publish", headers={**headers, "If-Match": '"1"'})
    ids = [uuid4() for _ in range(45)]
    with psycopg.connect(db[0]) as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO customer_requests(workspace_id,id,agent_id,version,input) "
                "VALUES (%s,%s,%s,1,'{}'::jsonb)",
                [(db[1], request_id, agent["id"]) for request_id in ids],
            )
    pages = [client.get(f"/api/v1/work-requests?offset={offset}").json()
             for offset in (0, 20, 40)]
    assert [len(page["items"]) for page in pages] == [20, 20, 5]
    assert [page["has_more"] for page in pages] == [True, True, False]
    actual = [item["id"] for page in pages for item in page["items"]]
    assert actual == sorted(map(str, ids), reverse=True)
    assert client.get("/api/v1/work-requests?offset=45").json() == {
        "items": [], "has_more": False,
    }


def test_customer_history_persistence_retry_and_validation(client, db):
    assert client.get("/api/v1/work-requests").status_code == 401
    headers = login(client)
    agent = client.post("/api/v1/agents", json=definition(), headers=headers).json()
    client.post(f"/api/v1/agents/{agent['id']}/publish", headers={**headers, "If-Match": '"1"'})
    body = {"id": str(uuid4()), "agent_id": agent["id"], "version": 1,
            "input": {"topic": "이력 테스트"}}
    assert client.post("/api/v1/work-requests", json=body, headers=ORIGIN).status_code == 403
    created = client.post("/api/v1/work-requests", json=body, headers=headers)
    assert created.status_code == 201
    saved = created.json()
    assert saved["status"] == "saved" and saved["result"] is None
    assert saved["input"] == body["input"]
    duplicate = client.post("/api/v1/work-requests", json=body, headers=headers)
    assert duplicate.json()["id"] == body["id"]
    assert len(client.get("/api/v1/work-requests").json()["items"]) == 1
    assert client.post("/api/v1/work-requests", json={**body, "input": {"topic": "변경"}},
                       headers=headers).status_code == 409
    assert client.post("/api/v1/work-requests", json={**body, "id": str(uuid4()),
                       "input": {"topic": 42}}, headers=headers).status_code == 422
    assert client.post("/api/v1/work-requests", json={**body, "status": "succeeded"},
                       headers=headers).status_code == 422
    repeated = {**body, "id": str(uuid4()), "source_id": saved["id"]}
    assert client.post("/api/v1/work-requests", json=repeated, headers=headers).status_code == 201
    with psycopg.connect(db[0]) as conn:
        conn.execute("UPDATE customer_requests SET status='succeeded', result=%s "
                     "WHERE workspace_id=%s AND id=%s",
                     (psycopg.types.json.Jsonb({"script": "테스트 결과"}), db[1], saved["id"]))
    detail = client.get(f"/api/v1/work-requests/{saved['id']}").json()
    assert detail["result"] == {"script": "테스트 결과"}
    assert detail["status"] == "succeeded"
    assert detail["agent"]["version"] == 1
    other = uuid4()
    migrate(db[0], other)
    foreign_settings = Settings(
        _env_file=None, database_url=db[0], owner_access_key=KEY,
        workspace_id=other, allowed_origins=["http://testserver"],
    )
    with TestClient(create_app(foreign_settings)) as foreign:
        foreign_headers = login(foreign)
        assert foreign.get("/api/v1/work-requests").json()["items"] == []
        assert foreign.get(f"/api/v1/work-requests/{saved['id']}").status_code == 404
        assert foreign.post("/api/v1/work-requests", json=body,
                            headers=foreign_headers).status_code == 404
        own = foreign.post("/api/v1/agents", json=definition(), headers=foreign_headers).json()
        foreign.post(f"/api/v1/agents/{own['id']}/publish",
                     headers={**foreign_headers, "If-Match": '"1"'})
        assert foreign.post("/api/v1/work-requests", headers=foreign_headers,
                            json={**body, "agent_id": own["id"],
                                  "source_id": saved["id"]}).status_code == 404
    with psycopg.connect(db[0]) as conn:
        conn.execute("UPDATE registry_sessions SET workspace_id=%s", (other,))
    assert client.get(f"/api/v1/work-requests/{saved['id']}").status_code == 401


@pytest.fixture()
def db():
    env = dotenv_values(Path(__file__).resolve().parents[4] / ".env")
    dsn = os.environ.get("ASA_TEST_DATABASE_URL") or env.get("ASA_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("ASA_TEST_DATABASE_URL required for PostgreSQL integration")
    schema = "asa_test_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    scoped = make_conninfo(dsn, options=f"-csearch_path={schema}")
    workspace = uuid4()
    migrate(scoped, workspace)
    yield scoped, workspace
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture()
def client(db):
    dsn, workspace = db
    settings = Settings(
        _env_file=None,
        database_url=dsn,
        owner_access_key=KEY,
        workspace_id=workspace,
        allowed_origins=["http://testserver"],
    )
    with TestClient(create_app(settings)) as client:
        yield client


def login(client):
    response = client.post("/api/v1/session", json={"access_key": KEY}, headers=ORIGIN)
    assert response.status_code == 200
    return {**ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]}


def definition():
    return {
        "name": "대본 작가",
        "description": "나의 채널",
        "instructions": "따뜻한 대본 작성",
        "model_profile": "default",
        "tools": [],
        "input_schema": {"type": "object", "properties": {"topic": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"script": {"type": "string"}}},
    }


def test_owner_login_csrf_and_untrusted_workspace(client):
    assert client.get("/api/v1/agents").status_code == 401
    assert client.post("/api/v1/session", json={"access_key": KEY}).status_code == 403
    headers = login(client)
    assert client.post("/api/v1/agents", json=definition(), headers=ORIGIN).status_code == 403
    evil = {**definition(), "workspace_id": str(uuid4())}
    assert client.post("/api/v1/agents", json=evil, headers=headers).status_code == 422


@pytest.mark.parametrize("environment,enabled", [("production", True), ("development", False)])
def test_test_login_disabled_outside_opted_in_development(db, environment, enabled):
    settings = Settings(
        _env_file=None,
        database_url=db[0],
        workspace_id=db[1],
        owner_access_key=KEY,
        environment=environment,
        dev_login_enabled=enabled,
        allowed_origins=["http://127.0.0.1:3001"],
    )
    with TestClient(
        create_app(settings), base_url="http://127.0.0.1:8127", client=("127.0.0.1", 12345)
    ) as c:
        assert c.get("/api/v1/session/options").json() == {"test_login_available": False}
        assert (
            c.post(
                "/api/v1/session/test", json={}, headers={"Origin": "http://127.0.0.1:3001"}
            ).status_code
            == 404
        )


def test_development_login_session_csrf_logout_and_network_boundary(db):
    settings = Settings(
        _env_file=None,
        database_url=db[0],
        workspace_id=db[1],
        owner_access_key=KEY,
        environment="development",
        dev_login_enabled=True,
        allowed_origins=["http://127.0.0.1:3001", "https://external.example"],
    )
    app = create_app(settings)
    origin = {"Origin": "http://127.0.0.1:3001"}
    with TestClient(app, base_url="http://127.0.0.1:8127", client=("127.0.0.1", 12345)) as c:
        assert c.get("/api/v1/session/options").json() == {"test_login_available": True}
        assert c.post("/api/v1/session/test", json={}).status_code == 403
        assert (
            c.post(
                "/api/v1/session/test", json={}, headers={"Origin": "https://external.example"}
            ).status_code
            == 403
        )
        result = c.post("/api/v1/session/test", json={}, headers=origin)
        assert result.status_code == 200
        assert KEY not in result.text
        assert "HttpOnly" in result.headers["set-cookie"]
        assert c.get("/api/v1/agents").status_code == 200
        assert c.post("/api/v1/agents", json=definition(), headers=origin).status_code == 403
        headers = {**origin, "X-CSRF-Token": result.json()["csrf_token"]}
        old_cookie = c.cookies.get("asa_session")
        assert c.delete("/api/v1/session", headers=headers).status_code == 204
        c.cookies.set("asa_session", old_cookie)
        assert c.get("/api/v1/session").status_code == 401
    with TestClient(app, base_url="http://127.0.0.1:8127", client=("192.0.2.1", 12345)) as c:
        assert c.get("/api/v1/session/options").json() == {"test_login_available": False}
        assert c.post("/api/v1/session/test", json={}, headers=origin).status_code == 404


def test_publish_snapshot_revision_conflict_and_tool_binding(client):
    headers = login(client)
    created = client.post("/api/v1/agents", json=definition(), headers=headers)
    assert created.status_code == 201
    agent = created.json()
    url = f"/api/v1/agents/{agent['id']}"
    h = {**headers, "If-Match": '"1"'}
    published = client.post(url + "/publish", headers=h)
    assert published.status_code == 201
    assert published.json()["version"] == 1
    assert client.post(url + "/publish", headers=h).status_code == 201
    changed = {**definition(), "name": "수정된 작가"}
    assert client.patch(url + "/draft", json=changed, headers=h).status_code == 200
    assert client.patch(url + "/draft", json=changed, headers=h).status_code == 409
    detail = client.get(url).json()
    assert detail["draft"]["name"] == "수정된 작가"
    assert detail["versions"][0]["definition"]["name"] == "대본 작가"
    assert len(detail["versions"]) == 1
    tools = client.get("/api/v1/tools").json()
    assert any(t["id"] == f"agent:{agent['id']}:1" for t in tools)


def test_cross_workspace_read_and_tool_reference_are_denied(client, db):
    dsn, _ = db
    other = uuid4()
    migrate(dsn, other)
    repo = RegistryRepository(dsn, other)
    foreign = repo.create(AgentDraft.model_validate(definition()))
    repo.publish(foreign["id"], 1)
    headers = login(client)
    assert client.get(f"/api/v1/agents/{foreign['id']}").status_code == 404
    assert client.get(f"/api/v1/tools/agent:{foreign['id']}:1").status_code == 404
    bad = {**definition(), "tools": [f"agent:{foreign['id']}:1"]}
    own = client.post("/api/v1/agents", json=bad, headers=headers).json()
    result = client.post(
        f"/api/v1/agents/{own['id']}/publish", headers={**headers, "If-Match": '"1"'}
    )
    assert result.status_code == 422


def test_tool_detail_uses_published_version_and_requires_login(client):
    assert client.get("/api/v1/tools/asa.text.inspect:1").status_code == 401
    headers = login(client)
    builtin = client.get("/api/v1/tools/asa.text.inspect:1")
    assert builtin.status_code == 200
    assert builtin.json()["input_schema"]["required"] == ["text", "limit"]
    agent = client.post("/api/v1/agents", json=definition(), headers=headers).json()
    url = f"/api/v1/agents/{agent['id']}"
    client.post(url + "/publish", headers={**headers, "If-Match": '"1"'})
    client.patch(url + "/draft", json={**definition(), "name": "수정한 초안"},
                 headers={**headers, "If-Match": '"1"'})
    detail = client.get(f"/api/v1/tools/agent:{agent['id']}:1")
    assert detail.status_code == 200
    assert detail.json()["name"] == definition()["name"]
    assert detail.json()["version"] == 1
    assert client.get("/api/v1/tools/does-not-exist").status_code == 404


def test_concurrent_publish_creates_one_version(db):
    repo = RegistryRepository(*db)
    agent = repo.create(AgentDraft.model_validate(definition()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: repo.publish(agent["id"], 1), range(2)))
    assert [r["version"] for r in results] == [1, 1]
    assert len(repo.get(agent["id"])["versions"]) == 1


def test_published_schema_contains_effective_limits(db):
    repo = RegistryRepository(*db)
    value = definition()
    value["input_schema"] = {
        "type": "object",
        "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {}}}},
    }
    agent = repo.create(AgentDraft.model_validate(value))
    schema = repo.publish(agent["id"], 1)["definition"]["input_schema"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["items"]["maxItems"] == 100
    assert schema["properties"]["items"]["items"]["additionalProperties"] is False


def test_free_output_roundtrip_and_published_version_survives_mode_change(client):
    headers = login(client)
    value = {**definition(), "output_schema": {"type": "string"}}
    created = client.post("/api/v1/agents", json=value, headers=headers)
    assert created.status_code == 201
    url = f"/api/v1/agents/{created.json()['id']}"
    published = client.post(url + "/publish", headers={**headers, "If-Match": '"1"'})
    assert published.status_code == 201
    assert published.json()["definition"]["output_schema"]["type"] == "string"
    assert published.json()["definition"]["output_schema"]["maxLength"] == 65536
    changed = client.patch(
        url + "/draft", json=definition(), headers={**headers, "If-Match": '"1"'}
    )
    assert changed.status_code == 200
    saved = client.get(url).json()
    assert saved["draft"]["output_schema"]["type"] == "object"
    assert saved["versions"][0]["definition"]["output_schema"]["type"] == "string"


def test_invalid_definition_and_self_tool_reference_cannot_publish(client):
    headers = login(client)
    agent = client.post("/api/v1/agents", json=definition(), headers=headers).json()
    url = f"/api/v1/agents/{agent['id']}"
    client.post(url + "/publish", headers={**headers, "If-Match": '"1"'})
    self_ref = {**definition(), "tools": [f"agent:{agent['id']}:1"]}
    client.patch(url + "/draft", json=self_ref, headers={**headers, "If-Match": '"1"'})
    result = client.post(url + "/validate", headers=headers)
    assert result.status_code == 200
    assert any(issue["code"] == "agent_cycle" for issue in result.json()["issues"])
    assert client.post(url + "/publish", headers={**headers, "If-Match": '"2"'}).status_code == 422

def test_graph_runtime_inline_ai_repeat_durable_review(client, db, monkeypatch):
    from asa.registry.runtime import RunInput, RunRepository
    from asa.runtime_worker import tick
    headers = login(client)
    aid = uuid4()
    nodes = [
        {'id':'start','label':'Start','kind':'start'},
        {'id':'loop','label':'Loop','kind':'repeat',
         'items':{'source':'literal','value':['a','b']}},
        {'id':'ai','label':'AI','kind':'ai','instructions':'Echo', 'review_after':True,
         'bindings':{'$':{'source':'loop','field':'item'}}},
        {'id':'end','label':'End','kind':'end','bindings':{'$':{'source':'loop','field':'results'}}}]
    edges = [{'id':str(i),'source':s,'target':t,'port':p} for i,(s,t,p) in enumerate([
        ('start','loop','next'),('loop','ai','item'),('ai','loop','next'),('loop','end','done')])]
    draft = {'name':'Graph','graph':{'nodes':nodes,'edges':edges}}
    assert client.post('/api/v1/automations', headers=headers,
                       json={'id':str(aid),'revision':0,'draft':draft}).status_code == 200
    repo = RunRepository(Settings(_env_file=None,database_url=db[0],workspace_id=db[1],
        automation_ai_enabled=True,ai_model='mock',ai_api_key='fake'))
    calls=[]
    def fake(_, tool, value):
        calls.append(value)
        return value.upper()
    monkeypatch.setattr('asa.runtime_worker.generate',fake)
    rid=uuid4()
    repo.enqueue(aid,RunInput(id=rid,revision=1,prompt='input'))
    assert tick(repo)
    first=repo.detail(rid)
    assert first['status']=='waiting_review' and calls==['a']
    repo.transition(rid,True,first['next_step'])
    assert tick(repo)
    second=repo.detail(rid)
    assert second['status']=='waiting_review' and calls==['a','b']
    from asa.registry.schemas import RegistryError
    with pytest.raises(RegistryError):
        repo.transition(rid,True,first['next_step'])
    repo.transition(rid,True,second['next_step'])
    assert tick(repo)
    result=repo.detail(rid)
    assert result['status']=='succeeded'
    assert result['steps'][-1]['output']==['A','B']
    assert calls==['a','b']
    assert len({r['id'] for r in result['steps']})==len(result['steps'])

def test_graph_call_budget_and_model_snapshot(db, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from asa.registry.automations import AutomationRepository, SaveAutomation
    from asa.registry.runtime import RunInput, RunRepository, ScheduleInput
    from asa.runtime_worker import tick
    aid=uuid4()
    nodes=[{'id':'start','label':'Start','kind':'start'},
        {'id':'loop','label':'Loop','kind':'repeat',
         'items':{'source':'literal','value':['x']*20}},
        {'id':'ai','label':'AI','kind':'ai','instructions':'Echo',
         'bindings':{'$':{'source':'loop','field':'item'}}},
        {'id':'extra','label':'Extra','kind':'ai','instructions':'Echo',
         'bindings':{'$':{'source':'input'}}},
        {'id':'end','label':'End','kind':'end'}]
    edges=[{'id':str(i),'source':s,'target':t,'port':p} for i,(s,t,p) in enumerate([
        ('start','loop','next'),('loop','ai','item'),('ai','loop','next'),
        ('loop','extra','done'),('extra','end','next')])]
    AutomationRepository(*db).save(SaveAutomation.model_validate({'id':aid,'revision':0,
        'draft':{'name':'Budget','graph':{'nodes':nodes,'edges':edges}}}))
    settings=Settings(_env_file=None,database_url=db[0],workspace_id=db[1],
        automation_ai_enabled=True,ai_model='mock',ai_api_key='fake',automation_daily_ai_calls=100)
    repo=RunRepository(settings)
    connection_errors = []
    connect = repo._connect

    def observed_connect():
        try:
            return connect()
        except psycopg.Error as error:
            connection_errors.append(type(error).__name__)
            raise

    monkeypatch.setattr(repo, '_connect', observed_connect)
    calls=[]
    def fake(*_):
        calls.append(1)
        return 'answer'
    monkeypatch.setattr('asa.runtime_worker.generate',fake)
    rid=uuid4()
    repo.enqueue(aid,RunInput(id=rid,revision=1,prompt='input'))
    assert tick(repo)
    result=repo.detail(rid)
    assert result['status']=='failed' and len(calls)==20, {
        'connection_errors': connection_errors, 'error': result['error'],
        'last_node': result['steps'][-1]['node_id'], 'calls': len(calls)}
    assert result['steps'][-1]['node_id']=='extra'
    assert not tick(repo) and len(calls)==20
    with psycopg.connect(db[0]) as conn:
        assert conn.execute('SELECT count(*) FROM automation_ai_calls WHERE run_id=%s',
                            (rid,)).fetchone()[0]==20
    due=datetime.now(UTC)+timedelta(hours=1)
    repo.save_schedule(aid,ScheduleInput(revision=1,schedule_revision=0,enabled=True,
        kind='once',at=due,prompt='input'))
    changed=RunRepository(settings.model_copy(update={'ai_model':'changed'}))
    assert changed.dispatch_due(due+timedelta(minutes=1))==0
    assert not changed.schedule(aid)['enabled']


def test_graph_uncertain_call_not_retried(db,monkeypatch):
    from asa.registry.automations import AutomationRepository, SaveAutomation
    from asa.registry.runtime import RunInput, RunRepository
    from asa.runtime_worker import tick
    aid=uuid4()
    graph={'nodes':[{'id':'start','label':'Start','kind':'start'},
        {'id':'ai','label':'AI','kind':'ai','instructions':'Echo',
         'bindings':{'$':{'source':'input'}}},
        {'id':'end','label':'End','kind':'end'}],
        'edges':[{'id':'a','source':'start','target':'ai','port':'next'},
                 {'id':'b','source':'ai','target':'end','port':'next'}]}
    AutomationRepository(*db).save(SaveAutomation.model_validate({'id':aid,'revision':0,
        'draft':{'name':'Uncertain','graph':graph}}))
    repo=RunRepository(Settings(_env_file=None,database_url=db[0],workspace_id=db[1],
        automation_ai_enabled=True,ai_model='mock',ai_api_key='fake'))
    calls=[]
    def broken(*_):
        calls.append(1)
        raise TimeoutError('private provider text')
    monkeypatch.setattr('asa.runtime_worker.generate',broken)
    rid=uuid4()
    repo.enqueue(aid,RunInput(id=rid,revision=1,prompt='input'))
    assert tick(repo)
    result=repo.detail(rid)
    assert result['status']=='needs_attention'
    assert 'private provider text' not in str(result)
    assert not tick(repo) and len(calls)==1


def selected_model_graph(model='selected'):
    return {'name': 'Models', 'graph': {
        'nodes': [
            {'id': 'start', 'label': 'Start', 'kind': 'start'},
            {'id': 'ai', 'label': 'AI', 'kind': 'ai', 'model': model,
             'instructions': 'Echo', 'bindings': {'$': {'source': 'input'}}},
            {'id': 'end', 'label': 'End', 'kind': 'end'}],
        'edges': [
            {'id': 'a', 'source': 'start', 'target': 'ai', 'port': 'next'},
            {'id': 'b', 'source': 'ai', 'target': 'end', 'port': 'next'}]}}


def test_graph_catalog_save_and_preview_model_validation(db):
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        owner_access_key=KEY, allowed_origins=['http://testserver'],
                        ai_model='default', ai_models=['selected', 'default'], ai_api_key='private')
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/v1/ai-models').status_code == 401
        headers = login(client)
        catalog = client.get('/api/v1/ai-models').json()
        assert catalog == {'models': [
            {'id': 'default', 'label': 'default', 'provider': 'openai', 'web_search': False},
            {'id': 'selected', 'label': 'selected', 'provider': 'openai', 'web_search': False}],
            'default_model': 'default', 'configured': True, 'providers': [
                {'id': 'openai', 'label': 'OpenAI', 'configured': True,
                 'web_search_available': True},
                {'id': 'anthropic', 'label': 'Claude', 'configured': False,
                 'web_search_available': True}]}
        draft = selected_model_graph('unknown')
        body = {'id': str(uuid4()), 'revision': 0, 'draft': draft}
        assert client.post('/api/v1/automations', headers=headers, json=body).status_code == 422
        assert client.post('/api/v1/automations/preview', headers=headers,
                           json={'draft': draft, 'prompt': 'x'}).status_code == 422
        draft['graph']['nodes'][1]['model'] = 'selected'
        draft['graph']['edges'] = []  # Incomplete wiring remains saveable as a draft.
        assert client.post('/api/v1/automations', headers=headers, json=body).status_code == 200
        draft['graph']['nodes'].append({'id': 'extra', 'kind': 'end', 'label': 'End'})
        body['revision'] = 1
        assert client.post('/api/v1/automations', headers=headers, json=body).status_code == 422
        saved = client.get('/api/v1/automations').json()[0]
        assert len(saved['draft']['graph']['nodes']) == 3


def test_selected_model_snapshot_worker_and_removed_schedule(db, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from asa.registry.automations import AutomationRepository, SaveAutomation
    from asa.registry.runtime import RunInput, RunRepository, ScheduleInput
    from asa.registry.schemas import RegistryError
    from asa.runtime_worker import tick

    aid = uuid4()
    AutomationRepository(*db).save(SaveAutomation.model_validate({
        'id': aid, 'revision': 0, 'draft': selected_model_graph()}))
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        automation_ai_enabled=True, ai_model='default', ai_models=['selected'],
                        ai_api_key='fake')
    repo = RunRepository(settings)
    definition, manifest = repo.snapshot(aid, 1)
    assert definition['graph']['nodes'][1]['model'] == 'selected'
    assert manifest[0]['model'] == 'selected' and manifest[0]['model_selected'] is True
    calls = []

    class MockModel:
        def with_structured_output(self, schema):
            return self

        def invoke(self, messages, **kwargs):
            return {'value': 'answer'}

    def init(model, **kwargs):
        calls.append(model)
        return MockModel()

    monkeypatch.setattr('asa.runtime_worker.init_chat_model', init)
    rid = uuid4()
    repo.enqueue(aid, RunInput(id=rid, revision=1, prompt='input'))
    changed = RunRepository(settings.model_copy(update={'ai_model': 'new-default'}))
    assert tick(changed)
    assert repo.detail(rid)['status'] == 'succeeded'
    assert calls == ['selected']
    due = datetime.now(UTC) + timedelta(hours=1)
    repo.save_schedule(aid, ScheduleInput(revision=1, schedule_revision=0, enabled=True,
                                        kind='daily', time='09:00', prompt='input'))
    assert changed.dispatch_due(due + timedelta(days=1)) == 1
    assert tick(changed)
    assert calls == ['selected', 'selected']
    removed = RunRepository(settings.model_copy(update={'ai_models': []}))
    assert removed.dispatch_due(due + timedelta(days=2)) == 0
    assert removed.schedule(aid)['enabled'] is False
    with pytest.raises(RegistryError) as error:
        removed.enqueue(aid, RunInput(id=uuid4(), revision=1, prompt='input'))
    assert error.value.code == 'invalid_definition'
    queued = uuid4()
    repo.enqueue(aid, RunInput(id=queued, revision=1, prompt='input'))
    assert tick(removed)
    assert removed.detail(queued)['status'] == 'failed'
    assert calls == ['selected', 'selected']


def test_claude_graph_snapshot_and_catalog(db):
    from asa.registry.runtime import RunRepository
    from asa.registry.schemas import RegistryError

    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        owner_access_key=KEY, allowed_origins=['http://testserver'],
                        ai_model='openai-test', anthropic_models=['claude-test'],
                        anthropic_api_key='private-claude-key', automation_ai_enabled=True)
    with TestClient(create_app(settings)) as client:
        headers = login(client)
        catalog = client.get('/api/v1/ai-models').json()
        assert {'id': 'claude-test', 'label': 'claude-test', 'provider': 'anthropic',
                'web_search': False} in catalog[
            'models']
        assert 'private-claude-key' not in str(catalog)
        draft = selected_model_graph('claude-test')
        draft['graph']['nodes'][1]['provider'] = 'anthropic'
        automation_id = uuid4()
        response = client.post('/api/v1/automations', headers=headers,
                               json={'id': str(automation_id), 'revision': 0, 'draft': draft})
        assert response.status_code == 200
        repo = RunRepository(settings)
        _, manifest = repo.snapshot(automation_id, 1)
        assert manifest[0]['provider'] == 'anthropic'
        assert manifest[0]['model'] == 'claude-test'
        assert manifest[0]['model_selected'] is True
        assert 'private-claude-key' not in str(manifest)
        settings.anthropic_models = []
        with pytest.raises(RegistryError):
            repo.snapshot(automation_id, 1)

@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
def test_native_search_run_preserves_citations_and_review(db, monkeypatch, provider):
    from asa.registry.runtime import RunRepository
    from asa.runtime_worker import tick

    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        owner_access_key=KEY, allowed_origins=['http://testserver'],
                        ai_model='test-model', ai_api_key='fake',
                        anthropic_models=['test-model'], anthropic_api_key='fake',
                        openai_web_search_models=['test-model'],
                        anthropic_web_search_models=['test-model'], automation_ai_enabled=True)
    calls = []

    def generate(repo, tool, value):
        calls.append(tool)
        assert tool['web_search'] is True
        assert tool['provider'] == provider
        return 'Answer [Source](https://example.com)'

    monkeypatch.setattr('asa.runtime_worker.generate', generate)
    with TestClient(create_app(settings)) as client:
        headers = login(client)
        draft = selected_model_graph('test-model')
        draft['graph']['nodes'][1].update(provider=provider, web_search=True, review_after=True)
        aid, rid = uuid4(), uuid4()
        assert client.post('/api/v1/automations', headers=headers, json={
            'id': str(aid), 'revision': 0, 'draft': draft}).status_code == 200
        assert client.post(f'/api/v1/automations/{aid}/runs', headers=headers, json={
            'id': str(rid), 'revision': 1, 'prompt': 'test'}).status_code == 201
        repo = RunRepository(settings)
        assert tick(repo)
        url = f'/api/v1/automation-runs/{rid}'
        result = client.get(url).json()
        assert result['status'] == 'waiting_review'
        assert '[Source](https://example.com)' in result['steps'][-1]['output']
        assert client.post(url + '/approve', headers=headers,
                           json={'next_step': result['next_step']}).status_code == 200
        assert tick(repo)
        assert client.get(url).json()['status'] == 'succeeded'
        assert len(calls) == 1
