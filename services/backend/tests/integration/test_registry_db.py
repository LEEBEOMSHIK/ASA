import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID, uuid4

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


def test_character_images_queue_edit_approval_and_isolation(db, monkeypatch):
    from psycopg.types.json import Jsonb

    from asa.image_worker import tick
    from asa.registry.characters import Character, CharacterRepository, ImageRequest
    from asa.registry.schemas import RegistryError

    dsn, workspace = db
    repo = CharacterRepository(dsn, workspace)
    project = uuid4()
    char = Character(id='hana', name='하나', facts='7살', appearance='노란 우비',
                     proposed='의상 제안', scene_ids='1,2', image_prompt='정면 전신')
    with repo._connect() as conn:
        conn.execute('INSERT INTO character_projects(workspace_id,id,request_id,name,characters) '
                     'VALUES (%s,%s,%s,%s,%s)',
                     (workspace, project, uuid4(), 'test', Jsonb([char.model_dump()])))
    settings = Settings(_env_file=None, database_url=dsn, workspace_id=workspace,
                        image_ai_enabled=True, ai_api_key='test-only')
    body = ImageRequest(id=uuid4(), character=char, model='gpt-image-2.5-sunburst')
    row = repo.enqueue(project, body, settings)
    assert repo.enqueue(project, body, settings)['id'] == row['id']
    with pytest.raises(RegistryError, match='image_already_running'):
        repo.enqueue(project, body.model_copy(update={'id': uuid4()}), settings)
    calls = []
    prompts = []
    image = b'\x89PNG\r\n\x1a\nmock'

    def fake(settings, model, prompt, reference):
        calls.append(reference)
        prompts.append(prompt)
        return image, {'input_tokens': 100, 'output_tokens': 10,
                       'input_tokens_details': {'text_tokens': 100, 'image_tokens': 0}}

    monkeypatch.setattr('asa.image_worker.generate_image', fake)
    assert tick(settings)
    assert not tick(settings)
    assert calls == [None]
    repo.approve(body.id, None, 1)
    edited = char.model_copy(update={'facts': '수정한 대본 정보', 'proposed': '수정한 AI 제안',
                                     'appearance': '초록 우비', 'image_prompt': '측면 전신'})
    edit = body.model_copy(update={'id': uuid4(), 'base_id': body.id, 'change': '모자 파란색',
                                   'character': edited})
    repo.enqueue(project, edit, settings)
    assert tick(settings)
    assert calls == [None, image]
    import json
    sent = json.loads(prompts[1].split('\nCHARACTER_DATA:\n', 1)[1])
    assert sent['reference_context'] == {'facts': '수정한 대본 정보', 'proposed': '수정한 AI 제안'}
    assert sent['primary_settings'] == {'appearance': '초록 우비', 'image_prompt': '측면 전신'}
    assert sent['requested_change'] == '모자 파란색'
    state = repo.project(project)
    assert state['approved']['hana'] == str(body.id)
    assert len(state['jobs']) == 2
    assert state['jobs'][0]['version'] == 2
    assert state['jobs'][0]['character'] == edited.model_dump()
    assert state['jobs'][1]['character'] == char.model_dump()
    with pytest.raises(RegistryError, match='image_approval_changed'):
        repo.approve(edit.id, None, 2)
    repo.approve(edit.id, body.id, 2)
    assert repo.project(project)['approved']['hana'] == str(edit.id)
    with repo._connect() as conn:
        usage = conn.execute('SELECT * FROM ai_usage_events WHERE workspace_id=%s',
                             (workspace,)).fetchall()
        assert len(usage) == 2 and all(x['estimated_usd'] > 0 for x in usage)
        assert all(x['source'] == 'character' for x in usage)
    other = CharacterRepository(dsn, uuid4())
    with pytest.raises(RegistryError):
        other.project(project)
    with pytest.raises(RegistryError):
        other.approve(body.id, None, 1)
    # Lost calls are marked unknown and never repeated after restart.
    third = edit.model_copy(update={'id': uuid4()})
    repo.enqueue(project, third, settings)
    with repo._connect() as conn:
        conn.execute("UPDATE character_image_jobs SET status='running' WHERE id=%s", (third.id,))
    assert not tick(settings)
    assert len(calls) == 2
    assert repo.project(project)['jobs'][0]['status'] == 'unknown'


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
            'provider': provider, 'model': 'test', 'input_schema': {'type': 'string'},
            'output_schema': {'type': 'string'},
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


def test_generic_answer_approval_setting_is_versioned_and_resets(client):
    headers = login(client)
    draft = {**definition(), "output_schema": {"type": "string"}}
    agent = client.post("/api/v1/agents", json=draft, headers=headers).json()
    agent_url = f"/api/v1/agents/{agent['id']}"
    assert client.post(agent_url + "/publish", headers={
        **headers, "If-Match": '"1"'}).status_code == 201
    changed = client.patch(agent_url + "/draft", json={**draft, "requires_approval": True},
                           headers={**headers, "If-Match": '"1"'})
    assert changed.status_code == 200
    assert client.post(agent_url + "/publish", headers={
        **headers, "If-Match": '"2"'}).status_code == 201
    for version in (1, 2):
        work = client.post("/api/v1/work-requests", headers=headers, json={
            "id": str(uuid4()), "agent_id": agent["id"], "version": version,
            "input": {"topic": "장면 구성 검토"},
        }).json()
        url = f"/api/v1/work-requests/{work['id']}"
        stage = url + "/script"
        assert client.get(stage).json()["requires_approval"] is (version == 2)
        saved = client.post(stage + "/versions", headers=headers, json={
            "id": str(uuid4()), "expected_revision": 0, "answer": "첫 답변"})
        assert saved.status_code == 201
        progress = client.get(url).json()["work_progress"]
        if version == 1:
            assert progress is None
            continue
        assert progress["status"] == "review"
        assert progress["kind"] == "answer"
        assert client.post(stage + "/approve", headers=headers, json={
            "expected_revision": 1, "version": 1}).status_code == 200
        assert client.get(url).json()["work_progress"]["status"] == "complete"
        assert client.post(stage + "/versions", headers=headers, json={
            "id": str(uuid4()), "expected_revision": 2, "answer": "수정한 답변",
            "base_version": 1}).status_code == 201
        assert client.get(url).json()["work_progress"]["status"] == "review"
        assert client.post(stage + "/approve", headers=headers, json={
            "expected_revision": 1, "version": 1}).status_code == 409
        recent = client.get("/api/v1/work-requests").json()["items"]
        assert next(w for w in recent if w["id"] == work["id"])[
            "work_progress"]["status"] == "review"


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
    assert client.get(f"/api/v1/work-requests/{work['id']}").json()["result"]["title"] == "짧은 제목"
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


def test_input_widgets_roundtrip_and_request_validation(client):
    headers = login(client)
    draft = definition()
    draft['input_schema'] = {'type': 'object', 'properties': {
        'mood': {'type': 'string', 'enum': ['오싹', '신비'],
                 'x-widget': 'radio', 'default': '오싹', 'description': '분위기'},
        'fear': {'type': 'integer', 'minimum': 1, 'maximum': 5,
                 'x-widget': 'slider', 'default': 2},
        'subject': {'type': 'string', 'enum': ['자동', '유령'], 'x-widget': 'select'},
    }, 'required': ['mood', 'fear']}
    agent = client.post('/api/v1/agents', json=draft, headers=headers).json()
    published = client.post(f"/api/v1/agents/{agent['id']}/publish",
                            headers={**headers, 'If-Match': '"1"'})
    assert published.status_code == 201
    stored = client.get(f"/api/v1/agents/{agent['id']}").json()
    assert stored['draft']['input_schema'] == draft['input_schema']
    body = {'id': str(uuid4()), 'agent_id': agent['id'], 'version': 1,
            'input': {'mood': '신비', 'fear': 4}}
    assert client.post('/api/v1/work-requests', json=body, headers=headers).status_code == 201
    for invalid in [{'mood': '미등록', 'fear': 4}, {'mood': '신비', 'fear': 6},
                    {'mood': '신비', 'fear': 2.5}, {'mood': '신비'}]:
        response = client.post('/api/v1/work-requests', headers=headers,
                               json={**body, 'id': str(uuid4()), 'input': invalid})
        assert response.status_code == 422


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
    from asa.database import close_database
    close_database(scoped)
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
        assert c.get("/api/v1/session").json()["roles"] == ["owner"]
        assert c.get("/api/v1/admin/models").status_code == 200
        assert c.get("/api/v1/admin/ai-usage").status_code == 200
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
            'default_model': 'default', 'default_provider': 'openai', 'configured': True,
            'providers': [
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


def test_admin_model_catalog_selection_and_runtime(client, db):
    from asa.registry.automations import AutomationRepository, SaveAutomation
    from asa.registry.runtime import RunRepository
    from asa.registry.schemas import RegistryError

    assert client.get('/api/v1/admin/models').status_code == 401
    headers = login(client)
    payload = {'revision': 0, 'default': 'anthropic:claude-test', 'models': [
        {'provider': 'anthropic', 'id': 'claude-test', 'label': 'Test Claude',
         'enabled': True, 'price': {'label': 'test-rate', 'input': '3', 'output': '15'}}]}
    saved = client.put('/api/v1/admin/models', json=payload, headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()['revision'] == 1
    assert client.put('/api/v1/admin/models', json=payload, headers=headers).status_code == 409
    catalog = client.get('/api/v1/ai-models').json()
    assert catalog['default_provider'] == 'anthropic'
    assert catalog['models'][0]['id'] == 'claude-test'
    bad = {**definition(), 'provider': 'openai', 'model': 'not-allowed'}
    assert client.post('/api/v1/agents', json=bad, headers=headers).status_code == 422
    agent = client.post('/api/v1/agents', json={**definition(), 'provider': 'anthropic',
                        'model': 'claude-test'}, headers=headers).json()
    aid = agent['id']
    published = client.post(f'/api/v1/agents/{aid}/publish', headers={
        **headers, 'If-Match': str(agent['revision'])})
    assert published.status_code == 201, published.text
    tools = client.get('/api/v1/tools').json()
    tool = next(t for t in tools if t.get('agent_id') == aid)
    automation_id = uuid4()
    repo = AutomationRepository(db[0], db[1])
    repo.save(SaveAutomation.model_validate({'id': automation_id, 'revision': 0, 'draft': {
        'name': 'model snapshot', 'steps': [{'id': 'writer', 'label': 'writer',
         'tool_id': tool['id'], 'bindings': {'topic': {'source': 'input'}}}]}}))
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        automation_ai_enabled=True, anthropic_api_key='test-key')
    runtime = RunRepository(settings)
    _, manifest = runtime.snapshot(automation_id, 1)
    assert manifest[0]['provider'] == 'anthropic'
    assert manifest[0]['model'] == 'claude-test'
    assert runtime.ai_ready()
    assert runtime.settings.ai_prices['anthropic:claude-test'].input == 3
    disabled = {**payload, 'revision': 1, 'default': '',
                'models': [{**payload['models'][0], 'enabled': False}]}
    assert client.put('/api/v1/admin/models', json=disabled, headers=headers).status_code == 200
    assert client.get('/api/v1/ai-models').json()['models'] == []
    assert not RunRepository(settings).model_available(manifest[0])
    with pytest.raises(RegistryError):
        RunRepository(settings).snapshot(automation_id, 1)
    # The published agent retains its selected model after policy changes.
    assert client.get(f'/api/v1/agents/{aid}').json()['versions'][0]['definition'][
        'model'] == 'claude-test'
    other = uuid4()
    migrate(db[0], other)
    from asa.registry.model_catalog import read_catalog
    assert read_catalog(settings.model_copy(update={'workspace_id': other})).models == []


def test_model_catalog_admin_permission_and_validation(db, monkeypatch):
    from pydantic import ValidationError

    from asa.auth.session import OwnerSessions, Principal
    from asa.registry.model_catalog import Catalog

    with pytest.raises(ValidationError):
        Catalog.model_validate({'default': 'openai:missing', 'models': []})
    entry = {'provider': 'openai', 'id': 'test', 'label': 'Test'}
    with pytest.raises(ValidationError):
        Catalog.model_validate({'models': [entry, entry]})
    monkeypatch.setattr(OwnerSessions, 'principal', lambda self: Principal(
        user_id='member', workspace_id=db[1], roles=('member',)))
    with TestClient(create_app(Settings(_env_file=None, database_url=db[0],
                                       workspace_id=db[1]))) as member:
        assert member.get('/api/v1/admin/models/discover/openai').status_code == 403
        assert member.get('/api/v1/admin/models/metadata/openai?model=test').status_code == 403
        assert member.get('/api/v1/admin/models').status_code == 403
        assert member.put('/api/v1/admin/models', json={'models': []}).status_code == 403
        assert member.post('/api/v1/admin/models', json={'revision': 0, 'model': entry}).status_code == 403
        assert member.get('/api/v1/ai-models').status_code == 200


def test_model_discovery_admin_routes(client, monkeypatch):
    from asa.registry import model_catalog
    from asa.registry.model_discovery import ModelMetadata

    assert client.get('/api/v1/admin/models/discover/openai').status_code == 401
    headers = login(client)
    monkeypatch.setattr(model_catalog, 'discover', lambda config, provider: {
        'models': [{'id': 'test', 'label': 'Test', 'provider': provider}]})
    monkeypatch.setattr(model_catalog, 'metadata', lambda provider, model: ModelMetadata(
        checked_at='2026-10-29T00:00:00Z', web_search_supported=True,
        sources=['https://developers.openai.com/api/docs/models/test']))
    assert client.get('/api/v1/admin/models/discover/openai').json()['models'][0]['id'] == 'test'
    meta = client.get('/api/v1/admin/models/metadata/openai?model=test').json()
    assert meta['web_search_supported'] is True
    saved = client.put('/api/v1/admin/models', headers=headers, json={
        'models': [{'provider': 'openai', 'id': 'test', 'label': 'Test', 'metadata': meta}]})
    assert saved.status_code == 200
    assert client.get('/api/v1/admin/models').json()['models'][0]['metadata'] == meta
    assert client.get('/api/v1/admin/models/discover/unknown').status_code == 422

def test_register_model_is_immediate_and_preserves_saved_catalog(client):
    url = '/api/v1/admin/models'
    entry = {'provider': 'openai', 'id': 'first', 'label': 'First'}
    assert client.post(url, json={'revision': 0, 'model': entry}).status_code == 401
    headers = login(client)
    first = client.post(url, headers=headers, json={'revision': 0, 'model': entry})
    assert first.status_code == 201, first.text
    assert client.get(url).json()['models'][0]['id'] == 'first'
    saved = first.json()
    saved['default'] = 'openai:first'
    assert client.put(url, headers=headers, json=saved).status_code == 200
    second = {'provider': 'anthropic', 'id': 'second', 'label': 'Second'}
    assert client.post(url, headers=headers, json={'revision': 1, 'model': second}).status_code == 409
    result = client.post(url, headers=headers, json={'revision': 2, 'model': second})
    assert result.status_code == 201
    reread = client.get(url).json()
    assert reread['default'] == 'openai:first'
    assert [m['label'] for m in reread['models']] == ['First', 'Second']
    assert client.post(url, headers=headers, json={'revision': 3, 'model': second}).status_code == 409
    # Adding a model cannot submit unrelated unsaved edits or change the default.
    assert client.post(url, headers=headers, json={'revision': 3, 'model': entry,
                       'default': ''}).status_code == 422


def test_script_queue_duplicate_concurrent_and_recovery(client, db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from asa.registry.history import HistoryRepository, WorkRequest
    from asa.registry.script_queue import ScriptQueue
    from asa.models import Script
    headers = login(client)
    agent = client.post('/api/v1/agents', json=definition(), headers=headers).json()
    client.post(f"/api/v1/agents/{agent['id']}/publish",
                headers={**headers, 'If-Match': '"1"'})
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        ai_model='test', ai_api_key='fake', script_ai_enabled=True)
    queue = ScriptQueue(settings)
    history = HistoryRepository(db[0], db[1])
    ids = [uuid4() for _ in range(3)]
    for rid in ids:
        history.save(WorkRequest(id=rid, agent_id=agent['id'], version=1,
                                 input={'topic': str(rid)}))
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda _: queue.submit(str(ids[0])), range(4)))
    for rid in ids[1:]:
        queue.submit(str(rid))
    assert len(queue.get(str(ids[0]))['attempts']) == 1
    started, release = Event(), Event()
    calls = []
    def slow(prompt):
        calls.append(prompt)
        started.set()
        assert release.wait(5)
        return Script(title='Title', narration='Narration')
    with ThreadPoolExecutor(2) as pool:
        running = pool.submit(queue.tick, slow)
        assert started.wait(5)
        assert not queue.tick(slow)
        release.set()
        assert running.result()
    assert len(calls) == 1
    assert history.detail(ids[0])['status'] == 'succeeded'
    queue.cancel(str(ids[1]), ids[1])
    assert queue.tick(lambda _: Script(title='Third', narration='Third result'))
    assert not queue.tick(slow)
    assert history.detail(ids[1])['status'] == 'cancelled'
    assert history.detail(ids[2])['result']['title'] == 'Third'
    # Simulate a process dying after claiming, without automatically calling again.
    rid = uuid4()
    history.save(WorkRequest(id=rid, agent_id=agent['id'], version=1, input={'topic': 'recover'}))
    queue.submit(str(rid))
    queue.claim(str(rid), str(rid), 'openai', 'test')
    assert not queue.tick(slow)
    assert queue.get(str(rid))['attempts'][0]['status'] == 'unknown'
    assert history.detail(rid)['status'] == 'failed'
    assert len(calls) == 1
    with queue._connect() as conn:
        assert conn.execute('SELECT count(*) n FROM ai_usage_events WHERE workspace_id=%s',
                            (db[1],)).fetchone()['n'] == 2
    other = ScriptQueue(settings.model_copy(update={'workspace_id': uuid4()}))
    with pytest.raises(Exception):
        other.submit(str(ids[0]))


def test_script_queue_api_usage_failure_and_model_snapshot(client, db):
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.outputs import ChatGeneration, LLMResult
    from asa.registry.history import HistoryRepository, WorkRequest
    from asa.registry.script_queue import ScriptQueue
    from asa.models import Script
    from asa.telemetry import call_config
    headers, work, url = script_work(client)
    assert client.post(url + '/start', headers=headers, json={}).status_code == 409
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        ai_model='test', ai_api_key='fake', script_ai_enabled=True,
                        owner_access_key=KEY, allowed_origins=['http://testserver'],
                        ai_prices={'openai:test': {'label': 'test', 'input': 2, 'output': 8}})
    queue = ScriptQueue(settings)
    with TestClient(create_app(settings)) as api_client:
        auth = login(api_client)
        assert api_client.post(url + '/start', headers=ORIGIN, json={}).status_code == 403
        first = api_client.post(url + '/start', headers=auth, json={})
        assert first.status_code == 201
        assert api_client.post(url + '/start', headers=auth, json={}).status_code == 201
        assert len(api_client.get(url).json()['attempts']) == 1
        assert api_client.get(url).json()['request_input'] == work['input']
        def response(prompt):
            callback = call_config()['config']['callbacks'][0]
            callback.on_chat_model_start({}, [[HumanMessage(content=prompt)]])
            callback.on_llm_end(LLMResult(generations=[[ChatGeneration(message=AIMessage(
                content='result', usage_metadata={'input_tokens': 100, 'output_tokens': 20,
                                                 'total_tokens': 120}))]]))
            return Script(title='Test result', narration='Test narration')
        # A changed default does not change the pinned queued model if still permitted.
        queue.settings = settings.model_copy(update={'ai_model': 'new', 'ai_models': ['test']})
        assert queue.tick(response)
        with queue._connect() as conn:
            event = conn.execute('SELECT * FROM ai_usage_events WHERE workspace_id=%s',
                                 (db[1],)).fetchone()
        assert event['model'] == 'test' and event['request_id'] == work['id']
        assert event['status'] == 'succeeded' and event['duration_ms'] is not None
        assert event['usage']['input_tokens'] == 100
        assert float(event['estimated_usd']) == pytest.approx(0.00036)
        assert api_client.get(url).json()['versions'][0]['title'] == 'Test result'
        assert api_client.post(url + '/start', headers=auth, json={}).status_code == 201
        assert not queue.tick(response)
    history = HistoryRepository(db[0], db[1])
    ids = [uuid4(), uuid4()]
    for rid in ids:
        history.save(WorkRequest(id=rid, agent_id=work['agent_id'], version=work['version'],
                                 input={'topic': 'new'}))
        queue.submit(str(rid))
    def failed(_):
        raise TimeoutError('must not be logged')
    assert queue.tick(failed)
    assert queue.get(str(ids[0]))['attempts'][0]['status'] == 'unknown'
    assert queue.get(str(ids[0]))['attempts'][0]['error_code'] == 'ai_timeout'
    item = next(item for item in history.history(0)['items'] if item['id'] == str(ids[0]))
    assert item['status'] == 'failed' and item['error_code'] == 'ai_timeout'
    assert '시간 초과' in history.detail(ids[0])['error']

    assert queue.tick(response)
    assert history.detail(ids[1])['status'] == 'succeeded'
    assert not queue.tick(response)


def test_script_queue_limits_disabled_and_legacy_not_consumed(client, db):
    from asa.registry.script_queue import ScriptQueue
    from asa.registry.script_stage import GenerateScript, ScriptRepository
    from asa.registry.schemas import RegistryError
    from asa.registry.history import HistoryRepository, WorkRequest
    from asa.models import Script
    _, work, _ = script_work(client)
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        ai_model='test', ai_api_key='fake', script_ai_enabled=True,
                        script_queue_limit=1, script_daily_ai_calls=1)
    queue = ScriptQueue(settings)
    queue.submit(work['id'])
    rid = uuid4()
    history = HistoryRepository(db[0], db[1])
    history.save(WorkRequest(id=rid, agent_id=work['agent_id'], version=work['version'],
                             input={'topic': 'second'}))
    with pytest.raises(RegistryError, match='script_queue_full'):
        queue.submit(str(rid))
    assert queue.tick(lambda _: Script(title='First', narration='First'))
    queue.submit(str(rid))
    assert queue.tick(lambda _: pytest.fail('daily limit must prevent the call'))
    assert queue.get(str(rid))['attempts'][0]['status'] == 'failed'
    legacy = uuid4()
    history.save(WorkRequest(id=legacy, agent_id=work['agent_id'], version=work['version'],
                             input={'topic': 'manual'}))
    ScriptRepository(db[0], db[1]).queue(str(legacy), GenerateScript(
        id=uuid4(), expected_revision=0, base_version=0, instruction='legacy'))
    assert not queue.tick(lambda _: pytest.fail('legacy work must not be consumed'))
    assert queue.get(str(legacy))['attempts'][0]['status'] == 'queued'


def test_manual_script_result_updates_customer_history(client):
    headers, work, url = script_work(client)
    result = client.post(url + '/versions', headers=headers, json={
        'id': str(uuid4()), 'expected_revision': 0, 'title': 'Edited', 'narration': 'Edited script'})
    assert result.status_code == 201
    detail = client.get(f"/api/v1/work-requests/{work['id']}").json()
    assert detail['result'] == {'title': 'Edited', 'narration': 'Edited script'}


def test_script_read_keeps_completion_in_one_snapshot(client, db, monkeypatch):
    from asa.models import Script
    from asa.registry.script_stage import GenerateScript, ScriptRepository

    _, work, _ = script_work(client)
    repo = ScriptRepository(db[0], db[1])
    rid, aid = work['id'], str(uuid4())
    repo.queue(rid, GenerateScript(id=aid, expected_revision=0, base_version=0,
                                  instruction='write'))
    attempt = repo.claim(rid, aid, 'openai', 'test')
    original = repo._connect

    class InterleavedConnection:
        def __enter__(self):
            self.context = original()
            self.conn = self.context.__enter__()
            return self

        def __exit__(self, *args):
            return self.context.__exit__(*args)

        def execute(self, query, *args):
            cursor = self.conn.execute(query, *args)
            if 'FROM script_versions' in query:
                ScriptRepository(db[0], db[1]).finish(
                    rid, attempt, Script(title='Ready', narration='Ready script'))
            return cursor

    monkeypatch.setattr(repo, '_connect', InterleavedConnection)
    snapshot = repo.get(rid)
    assert snapshot['versions'] == []
    assert snapshot['attempts'][0]['status'] == 'running'
    complete = ScriptRepository(db[0], db[1]).get(rid)
    assert complete['attempts'][0]['status'] == 'succeeded'
    assert complete['versions'][0]['title'] == 'Ready'


def test_work_test_label_is_explicit_metadata(client):
    headers, work, _ = script_work(client)
    assert work['is_test'] is False
    body = dict(id=str(uuid4()), agent_id=work['agent_id'], version=work['version'],
                input={'topic': 'ordinary text'}, is_test=True)
    saved = client.post('/api/v1/work-requests', headers=headers, json=body)
    assert saved.status_code == 201
    assert saved.json()['is_test'] is True
    assert next(i for i in client.get('/api/v1/work-requests').json()['items']
                if i['id'] == body['id'])['is_test'] is True
    assert client.post('/api/v1/work-requests', headers=headers,
                       json={**body, 'is_test': False}).status_code == 409
    normal = client.post('/api/v1/work-requests', headers=headers, json={
        **body, 'id': str(uuid4()), 'input': {'topic': '실행 연결 검증: user text'},
        'is_test': False})
    assert normal.json()['is_test'] is False
    repeated = client.post('/api/v1/work-requests', headers=headers, json={
        **body, 'id': str(uuid4()), 'source_id': body['id'], 'is_test': False})
    assert repeated.status_code == 201
    assert repeated.json()['is_test'] is False

@pytest.mark.parametrize('schema,answer', [({'type': 'string', 'maxLength': 200}, 'Detailed answer'), ({'type': 'object', 'properties': {'summary': {'type': 'string', 'maxLength': 200}, 'tags': {'type': 'array', 'items': {'type': 'string', 'maxLength': 50}, 'maxItems': 5}}, 'required': ['summary', 'tags']}, {'summary': 'Detailed', 'tags': ['one', 'two']})])
def test_agent_answer_contract_persistence_revision_and_validation(client, db, schema, answer):
    import json
    from asa.models import AgentAnswer
    from asa.registry.script_stage import ScriptRepository, GenerateScript, execute_attempt
    headers = login(client)
    draft = definition()
    draft['output_schema'] = schema
    draft['instructions'] = 'Act as an analyst, use the configured response format.'
    agent = client.post('/api/v1/agents', headers=headers, json=draft).json()
    assert client.post(f"/api/v1/agents/{agent['id']}/publish", headers={**headers, 'If-Match': '"1"'}).status_code == 201
    rid = str(uuid4())
    assert client.post('/api/v1/work-requests', headers=headers, json=dict(id=rid, agent_id=agent['id'], version=1, input={'topic': 'Analysis'})).status_code == 201
    repo = ScriptRepository(db[0], db[1])
    aid = str(uuid4())
    repo.queue(rid, GenerateScript(id=aid, expected_revision=0, base_version=0, instruction='Answer'))
    assert execute_attempt(repo, rid, aid, lambda _: AgentAnswer(value=answer))
    stage = repo.get(rid)
    assert stage['versions'][0]['answer'] == answer
    assert client.get(f'/api/v1/work-requests/{rid}').json()['result'] == answer
    aid2 = str(uuid4())
    repo.queue(rid, GenerateScript(id=aid2, expected_revision=stage['revision'], base_version=1, instruction='Improve'))
    def improve(prompt):
        contract = json.loads(prompt)
        assert contract['previous_answer'] == answer
        assert contract['output_schema']['type'] == schema['type']
        assert contract['agent_instructions'] == draft['instructions']
        assert 'scope' not in contract
        return AgentAnswer(value=answer)
    assert execute_attempt(repo, rid, aid2, improve)
    stage = repo.get(rid)
    assert stage['head_version'] == 2
    saved = client.post(f'/api/v1/work-requests/{rid}/script/versions', headers=headers, json=dict(id=str(uuid4()), expected_revision=stage['revision'], base_version=2, answer=answer))
    assert saved.status_code == 201
    assert saved.json()['versions'][0]['answer'] == answer
    stage = repo.get(rid)
    aid3 = str(uuid4())
    repo.queue(rid, GenerateScript(id=aid3, expected_revision=stage['revision'], base_version=3, instruction='Invalid'))
    assert execute_attempt(repo, rid, aid3, lambda _: AgentAnswer(value=123))
    assert repo.get(rid)['head_version'] == 3
    assert repo.get(rid)['attempts'][0]['status'] == 'unknown'


@pytest.mark.parametrize("timeout", [False, True])
def test_agent_sse_reconnect_isolation_and_persisted_partial(client, db, monkeypatch, timeout):
    from asa.registry.script_queue import ScriptQueue
    from asa.models import Script
    import asa.registry.sse as sse
    monkeypatch.setattr(sse, 'STREAM_LIFETIME', 0)
    headers, work, url = script_work(client)
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        ai_model='test', ai_api_key='fake', script_ai_enabled=True,
                        owner_access_key=KEY, allowed_origins=['http://testserver'])
    queue = ScriptQueue(settings)
    queue.submit(work['id'])
    calls = []

    def factory(config, publish):
        def generate(prompt):
            calls.append(prompt)
            publish({'understanding': '요청 이해', 'direction': '작성 방향', 'value': '부분 답변'})
            assert queue.get(work['id'])['attempts'][0]['live_output']['value'] == '부분 답변'
            if timeout:
                raise TimeoutError('private provider error')
            return Script(title='제목', narration='최종 답변')
        return generate

    monkeypatch.setattr('asa.registry.script_queue.make_agent_generator', factory)
    assert queue.tick()
    with TestClient(create_app(settings)) as browser:
        assert browser.get(url + '/events').status_code == 401
        login(browser)
        first = browser.get(url + '/events')
        assert first.status_code == 200
        assert first.headers['content-type'].startswith('text/event-stream')
        assert '요청 이해' in first.text and '부분 답변' in first.text
        assert browser.get(url + '/events', headers={'Last-Event-ID': 'old'}).text == first.text
        recent = browser.get('/api/v1/work-requests/events')
        assert work['id'] in recent.text
        assert ('failed' if timeout else 'succeeded') in recent.text
        if timeout:
            assert 'ai_timeout' in first.text
            assert 'private provider error' not in first.text
            assert queue.get(work['id'])['versions'] == []
        assert first.headers['content-encoding'] == 'identity'
        assert 'no-transform' in first.headers['cache-control']
        assert browser.get(f'/api/v1/work-requests/{uuid4()}/script/events').status_code == 404
        from asa.registry.schemas import RegistryError
        other_queue = ScriptQueue(settings.model_copy(update={'workspace_id': uuid4()}))
        with pytest.raises(RegistryError):
            other_queue.get(work['id'])
        assert len(calls) == 1
        assert len(queue.get(work['id'])['attempts']) == 1

def test_character_projects_follow_immutable_answer_versions(client, db):
    from psycopg.types.json import Jsonb
    from asa.registry.characters import CharacterRepository, ImportPlan
    from asa.registry.schemas import RegistryError

    headers, work, _ = script_work(client)
    dsn, workspace = db
    repo = CharacterRepository(dsn, workspace)
    char = dict(id='hana', name='Hana', facts='', appearance='yellow coat',
                proposed='', scene_ids='1', image_prompt='front view')
    with repo._connect() as conn:
        conn.execute('INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)',
                     (workspace, work['id']))
        for number, name in [(1, 'Hana'), (2, 'Updated Hana')]:
            conn.execute('INSERT INTO script_versions'
                         '(workspace_id,request_id,version,operation_id,title,narration,source,answer) '
                         "VALUES (%s,%s,%s,%s,'','','ai',%s)",
                         (workspace, work['id'], number, uuid4(),
                          Jsonb({'characters': [{**char, 'name': name}]})))
    first = ImportPlan(id=uuid4(), request_id=work['id'], name='Characters')
    p1 = repo.import_plan(first)
    assert repo.import_plan(first.model_copy(update={'id': uuid4()}))['id'] == p1['id']
    p2 = repo.import_plan(first.model_copy(update={'id': uuid4(), 'source_version': 2}))
    assert p2['id'] != p1['id']
    assert p1['characters'][0]['name'] == 'Hana'
    assert p2['characters'][0]['name'] == 'Updated Hana'
    assert p2['source_version'] == 2
    with pytest.raises(RegistryError, match='image_id_conflict'):
        repo.import_plan(first.model_copy(update={'source_version': 2}))
    with pytest.raises(RegistryError, match='character_plan_not_ready'):
        repo.import_plan(first.model_copy(update={'id': uuid4(), 'source_version': 3}))
    with pytest.raises(RegistryError):
        CharacterRepository(dsn, uuid4()).import_plan(first)
    entries = client.get('/api/v1/characters/projects').json()
    assert len(entries) == 2
    assert {p['source_version'] for p in entries} == {1, 2}
    assert all(p['request_id'] == work['id'] for p in entries)


def test_followup_history_scope_completion_and_version_isolation(client, db):
    from psycopg.types.json import Jsonb
    from asa.registry.characters import Character, CharacterRepository, ImageRequest, ImportPlan, ItemScope
    from asa.registry.history import HistoryRepository
    from asa.registry.schemas import RegistryError

    headers, work, _ = script_work(client)
    dsn, workspace = db
    repo = CharacterRepository(dsn, workspace)
    history = HistoryRepository(dsn, workspace)
    char = dict(id='hana', name='Hana', facts='', appearance='coat', proposed='', scene_ids='1', image_prompt='front')
    with repo._connect() as conn:
        conn.execute('INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)', (workspace, work['id']))
        conn.execute('INSERT INTO script_versions(workspace_id,request_id,version,operation_id,title,narration,source,answer) '
                     "VALUES (%s,%s,1,%s,'','','ai',%s)",
                     (workspace, work['id'], uuid4(), Jsonb({'characters': [char, {**char, 'id': 'other'}]})))
        conn.execute("UPDATE customer_requests SET status='succeeded' WHERE workspace_id=%s AND id=%s", (workspace, work['id']))
    # Even an answer never opened/imported has outstanding work.
    assert history.history(0)['items'][0]['work_progress']['counts']['pending'] == 2
    project = repo.import_plan(ImportPlan(id=uuid4(), request_id=work['id'], name='test'))
    pid = UUID(project['id'])
    settings = Settings(_env_file=None, database_url=dsn, workspace_id=workspace,
                        image_ai_enabled=True, ai_api_key='test-only')
    body = ImageRequest(id=uuid4(), character=Character(**char), model='gpt-image-2.5-sunburst')
    repo.enqueue(pid, body, settings)
    with pytest.raises(RegistryError, match='image_already_running'):
        repo.set_scope(pid, 'hana', ItemScope(excluded=True, expected=False))
    assert history.detail(UUID(work['id']))['work_progress']['counts']['queued'] == 1
    with repo._connect() as conn:
        conn.execute("UPDATE character_image_jobs SET status='succeeded',image=%s WHERE workspace_id=%s AND id=%s",
                     (b'fake', workspace, body.id))
    assert history.history(0)['items'][0]['work_progress']['status'] == 'review'
    repo.approve(body.id, None, 1)
    assert history.history(0)['items'][0]['work_progress']['status'] == 'pending'
    repo.set_scope(pid, 'other', ItemScope(excluded=True, expected=False))
    assert history.history(0)['items'][0]['work_progress']['status'] == 'complete'
    assert client.get(f"/api/v1/work-requests/{work['id']}").json()['work_progress']['counts']['excluded'] == 1
    with pytest.raises(RegistryError, match='work_scope_changed'):
        repo.set_scope(pid, 'other', ItemScope(excluded=False, expected=False))
    with pytest.raises(RegistryError, match='work_item_excluded'):
        repo.enqueue(pid, body.model_copy(update={'id': uuid4(), 'character': Character(**{**char, 'id': 'other'})}), settings)
    with pytest.raises(RegistryError):
        CharacterRepository(dsn, uuid4()).set_scope(pid, 'other', ItemScope(excluded=False, expected=True))
    repo.set_scope(pid, 'other', ItemScope(excluded=False, expected=True))
    assert history.history(0)['items'][0]['work_progress']['status'] == 'pending'
    # Revisions reopen review; user can explicitly retain the older approved image.
    edit = body.model_copy(update={'id': uuid4(), 'base_id': body.id, 'change': 'blue'})
    repo.enqueue(pid, edit, settings)
    assert history.history(0)['items'][0]['work_progress']['status'] == 'running'
    with repo._connect() as conn:
        conn.execute("UPDATE character_image_jobs SET status='succeeded',image=%s WHERE workspace_id=%s AND id=%s",
                     (b'fake', workspace, edit.id))
    assert repo.project(pid)['work_progress']['counts']['review'] == 1
    with pytest.raises(RegistryError, match="image_review_changed"):
        repo.approve(body.id, body.id, 1)
    repo.approve(body.id, body.id, 2)
    assert repo.project(pid)['work_progress']['counts']['approved'] == 1
    # A new answer must not inherit previous approval/exclusions.
    with repo._connect() as conn:
        conn.execute('INSERT INTO script_versions(workspace_id,request_id,version,operation_id,title,narration,source,answer) '
                     "VALUES (%s,%s,2,%s,'','','ai',%s)", (workspace, work['id'], uuid4(), Jsonb({'characters': [char]})))
    latest = history.history(0)['items'][0]['work_progress']
    assert latest['source_version'] == 2 and latest['counts']['pending'] == 1
    assert repo.project(pid)['work_progress']['counts']['approved'] == 1


def test_pool_reuses_connection_and_rolls_back(db):
    from asa.database import connection, close_database
    dsn, _ = db
    with connection(dsn) as conn:
        first = conn.info.backend_pid
    with pytest.raises(ValueError):
        with connection(dsn) as conn:
            conn.execute("CREATE TABLE should_rollback(id int)")
            raise ValueError('rollback')
    with connection(dsn) as conn:
        assert conn.info.backend_pid == first
        assert conn.execute("SELECT to_regclass('should_rollback')").fetchone()[0] is None
    close_database(dsn)


def test_notifications_commit_only_and_workspace_isolation(db):
    from asa.database import changes, close_database, connection
    dsn, workspace = db
    hub = changes(dsn)
    assert hub.ready.wait(5)
    baseline = hub.version(str(workspace), 'state')
    with psycopg.connect(dsn) as conn:
        conn.execute("INSERT INTO work_item_preferences(workspace_id,request_id,source_version,"
                     "kind,item_id,excluded) VALUES (%s,%s,1,'test','test',true)",
                     (workspace, uuid4()))
        assert hub.version(str(workspace), 'state') == baseline
        conn.rollback()
    assert hub.version(str(workspace), 'state') == baseline
    with connection(dsn) as conn:
        conn.execute("SELECT pg_notify('asa_changes', %s)", (str(workspace)+':state',))
    assert hub.wait(str(workspace), 'state', baseline, 3) != baseline
    assert hub.version(str(uuid4()), 'state') == hub.epoch
    close_database(dsn)


def test_queue_notification_wakes_idle_consumer_once(client, db):
    import threading
    from asa.database import changes
    from asa.models import Script
    from asa.registry.script_queue import ScriptQueue
    headers, work, url = script_work(client)
    config = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                      script_ai_enabled=True, ai_model='test', ai_api_key='fake')
    repo = ScriptQueue(config)
    hub = changes(db[0])
    assert hub.ready.wait(5)
    scope = str(db[1])
    version = hub.version(scope, 'script')
    calls = []
    assert not repo.tick(lambda p: calls.append(p))
    # An idle wait returns unchanged; no paid generator or repeated queue read.
    assert hub.wait(scope, 'script', version, 0.1) == version
    repo.submit(work['id'])
    assert hub.wait(scope, 'script', version, 3) != version
    def generate(prompt):
        calls.append(prompt)
        return Script(title='Test', narration='One response')
    assert repo.tick(generate)
    assert not repo.tick(generate)
    assert len(calls) == 1
    assert repo.get(work['id'])['attempts'][0]['status'] == 'succeeded'


def test_listener_reconnect_forces_snapshot_reconciliation(db):
    import time
    from asa.database import changes, connection
    hub = changes(db[0])
    assert hub.ready.wait(5)
    epoch = hub.epoch
    # Only the listener for this isolated test DSN/schema is terminated.
    with connection(db[0]) as conn:
        rows = conn.execute("SELECT pid FROM pg_stat_activity WHERE application_name='asa-listener' "
                            "AND query='LISTEN asa_changes'").fetchall()
    # Use a dedicated tagged listener PID instead of affecting other applications.
    assert hub.backend_pid
    with connection(db[0]) as conn:
        conn.execute('SELECT pg_terminate_backend(%s)', (hub.backend_pid,))
    deadline = time.monotonic()+12
    while time.monotonic()<deadline:
        if hub.ready.is_set() and hub.epoch > epoch and hub.backend_pid:
            break
        time.sleep(0.05)
    assert hub.ready.is_set() and hub.epoch > epoch


def test_image_and_automation_sse_require_auth_and_scope(client, db, monkeypatch):
    import asa.registry.sse as sse
    monkeypatch.setattr(sse, 'STREAM_LIFETIME', 0)
    for path in [f'/api/v1/characters/projects/{uuid4()}/events',
                 f'/api/v1/automation-runs/{uuid4()}/events']:
        assert client.get(path).status_code == 401
    login(client)
    assert client.get(f'/api/v1/characters/projects/{uuid4()}/events').status_code == 404
    assert client.get(f'/api/v1/automation-runs/{uuid4()}/events').status_code == 404


def test_pooled_concurrent_enqueue_does_not_exhaust_pool(client, db, monkeypatch):
    import threading
    import time
    from asa.registry.runtime import RunInput, RunRepository
    _, saved = runtime_flow(client)
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1])
    repos = [RunRepository(settings) for _ in range(8)]
    barrier = threading.Barrier(8)
    original = RunRepository.snapshot
    def slow_snapshot(self, *args):
        time.sleep(0.1)  # Give seven contenders time to borrow the other slots.
        return original(self, *args)
    monkeypatch.setattr(RunRepository, 'snapshot', slow_snapshot)
    def enqueue(repo):
        barrier.wait(timeout=5)
        return repo.enqueue(UUID(saved['id']), RunInput(id=uuid4(), revision=1, prompt='test'))
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(enqueue, repos))
    assert len({r['id'] for r in results}) == 8
    assert all(r['status'] == 'queued' for r in results)


def test_idle_schedule_deadline_and_sse_snapshot(client, db, monkeypatch):
    from datetime import UTC, datetime, timedelta
    from asa.registry.runtime import RunRepository, RunInput, ScheduleInput
    import asa.registry.sse as sse
    _, saved = runtime_flow(client)
    repo = RunRepository(Settings(_env_file=None, database_url=db[0], workspace_id=db[1]))
    assert repo.idle_seconds() == 30
    repo.save_schedule(UUID(saved['id']), ScheduleInput(revision=1, schedule_revision=0,
        enabled=True, kind='once', at=datetime.now(UTC)+timedelta(seconds=5), prompt='test'))
    assert 0 < repo.idle_seconds() <= 5
    with repo._connect() as conn:
        conn.execute("UPDATE automation_schedules SET next_at=now()-interval '1 second'")
    assert repo.idle_seconds() == 0
    run = repo.enqueue(UUID(saved['id']), RunInput(id=uuid4(), revision=1, prompt='test'))
    monkeypatch.setattr(sse, 'STREAM_LIFETIME', 0)
    response = client.get(f"/api/v1/automation-runs/{run['id']}/events")
    assert response.status_code == 200 and 'event: snapshot' in response.text
    assert 'queued' in response.text


def test_standby_automation_worker_does_not_spin_on_overdue_schedule(client, db):
    from asa.registry.runtime import RunRepository
    from asa.runtime_worker import tick
    repo = RunRepository(Settings(_env_file=None, database_url=db[0], workspace_id=db[1]))
    with psycopg.connect(db[0]) as lock:
        lock.execute('SELECT pg_advisory_lock(hashtextextended(%s,0))',
                     (f'asa-runtime:{db[1]}',))
        assert not tick(repo)
        assert repo.worker_lock_busy
        assert repo.idle_seconds() == 30
    assert not tick(repo)
    assert not repo.worker_lock_busy


def test_image_review_queue_snapshot_auto_and_isolation(db, monkeypatch):
    from psycopg.types.json import Jsonb
    from asa.registry.characters import Character, CharacterRepository, ImageRequest
    from asa.registry.image_reviews import enqueue_review, enqueue_automatic, process_review
    from asa.registry.schemas import RegistryError
    dsn, workspace = db
    repo = CharacterRepository(dsn, workspace)
    reviewer = repo.create(AgentDraft.model_validate({**definition(), 'name': 'Image reviewer',
                         'purpose': 'image_review', 'output_schema': {'type': 'string'}}))
    repo.publish(reviewer['id'], 1)
    ref = f"agent:{reviewer['id']}:1"
    maker = repo.create(AgentDraft.model_validate({**definition(),
                       'after_tasks': {'image_review': {'agent_ref': ref, 'mode': 'automatic'}}}))
    repo.publish(maker['id'], 1)
    project, request = uuid4(), uuid4()
    char = Character(id='cloud', name='cloud', facts='facts', proposed='proposal',
                     appearance='coat', scene_ids='1', image_prompt='front')
    with repo._connect() as conn:
        conn.execute("INSERT INTO customer_requests(workspace_id,id,agent_id,version,input) "
                     "VALUES (%s,%s,%s,1,'{}')", (workspace,request,maker['id']))
        conn.execute('INSERT INTO character_projects(workspace_id,id,request_id,name,characters) '
                     'VALUES (%s,%s,%s,%s,%s)',
                     (workspace,project,request,'review test',Jsonb([char.model_dump()])))
    settings = Settings(_env_file=None,database_url=dsn,workspace_id=workspace,
                        image_ai_enabled=True,ai_api_key='test-only',ai_model='test-model',
                        ai_models=['test-model'], ai_prices={'openai:test-model':{'input':1,'output':2,'label':'test rate'}})
    # Effective model resolution is isolated from global admin catalog in this test.
    monkeypatch.setattr('asa.registry.image_reviews.effective_settings',lambda s,*a:s)
    image = ImageRequest(id=uuid4(),character=char,model='gpt-image-2.5-sunburst')
    repo.enqueue(project,image,settings)
    from asa.image_worker import tick
    monkeypatch.setattr('asa.image_worker.generate_image',lambda *a:(b'png-test',None))
    assert tick(settings)  # Image commit and automatic review enqueue share a transaction.
    enqueue_automatic(repo,image.id,settings)
    enqueue_automatic(repo,image.id,settings)
    snapshot = repo.project(project)
    assert len(snapshot['reviews']) == 1 and snapshot['review_config']['agent_ref'] == ref
    calls=[]
    def fake(config,definition,character,change,png,reference):
        from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
        from langchain_core.messages import AIMessage
        from asa.telemetry import call_config
        FakeMessagesListChatModel(responses=[AIMessage(content='검수 의견',usage_metadata={
            'input_tokens':100,'output_tokens':10,'total_tokens':110})]).invoke('test',**call_config())
        calls.append((definition,character,png))
        return '발이 설정과 다릅니다.'
    monkeypatch.setattr('asa.registry.image_reviews.review_image',fake)
    assert process_review(repo,settings)
    assert not process_review(repo,settings)
    assert calls[0][2] == b'png-test'
    assert repo.project(project)['approved'] == {}
    assert repo.project(project)['reviews'][0]['result'] == '발이 설정과 다릅니다.'
    changed = {**char.model_dump(),'appearance':'green coat'}
    review_id=uuid4()
    first=enqueue_review(repo,image.id,review_id,changed,settings)
    assert enqueue_review(repo,image.id,review_id,changed,settings)==first
    with pytest.raises(RegistryError,match='review_already_running'):
        enqueue_review(repo,image.id,uuid4(),changed,settings)
    with pytest.raises(RegistryError):
        enqueue_review(CharacterRepository(dsn,uuid4()),image.id,uuid4(),changed,settings)
    assert process_review(repo,settings)
    assert calls[-1][1]['appearance']=='green coat'
    # Frozen image settings are not overwritten by review criteria.
    assert repo.project(project)['jobs'][0]['character']['appearance']=='coat'
    with repo._connect() as conn:
        events=conn.execute("SELECT * FROM ai_usage_events WHERE step_name='이미지 검수'").fetchall()
        assert len(events)==2 and all(str(e['request_id'])==str(request) for e in events)
        assert all(e['usage']['input_tokens']==100 and e['estimated_usd']>0 for e in events)
    retry=enqueue_review(repo,image.id,uuid4(),changed,settings)
    with repo._connect() as conn:
        conn.execute("UPDATE asset_reviews SET status='running' WHERE id=%s", (retry['id'],))
    assert not process_review(repo,settings)
    assert repo.project(project)['reviews'][0]['status']=='unknown'
    # Interrupted review never prevents a human from approving the image.
    repo.approve(image.id,None,1)
    assert repo.project(project)['approved']['cloud']==str(image.id)


def test_agent_icon_saved_published_and_version_preserved(db):
    repo=RegistryRepository(*db)
    agent=repo.create(AgentDraft.model_validate({**definition(),'icon':'pen'}))
    assert repo.get(agent['id'])['draft']['icon']=='pen'
    v1=repo.publish(agent['id'],1)
    saved=repo.update(agent['id'],1,AgentDraft.model_validate({**definition(),'icon':'film'}))
    v2=repo.publish(agent['id'],saved['revision'])
    assert v1['definition']['icon']=='pen' and v2['definition']['icon']=='film'
    icons={t['version']:t['icon'] for t in repo.tools() if t.get('agent_id')==agent['id']}
    assert icons=={1:'pen',2:'film'}
