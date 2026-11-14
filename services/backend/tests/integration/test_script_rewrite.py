import json
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from test_registry_db import client, db, definition, login  # noqa: F401

from asa.models import AgentAnswer
from asa.registry.script_stage import GenerateScript, ScriptRepository, execute_attempt


def test_rewrite_preserves_input_and_adds_version_with_latest_instructions(client, db):  # noqa: F811
    headers = login(client)
    original = definition()
    original['output_schema'] = {'type': 'object', 'properties': {
        'text': {'type': 'string', 'maxLength': 100}}, 'required': ['text']}
    agent = client.post('/api/v1/agents', json=original, headers=headers).json()
    client.post(f"/api/v1/agents/{agent['id']}/publish",
                headers={**headers, 'If-Match': '"1"'})
    rid = str(uuid4())
    client.post('/api/v1/work-requests', headers=headers, json={
        'id': rid, 'agent_id': agent['id'], 'version': 1, 'input': {'topic': '원본 자료'}})
    repo = ScriptRepository(*db)
    first = uuid4()
    repo.queue(rid, GenerateScript(id=first, expected_revision=0, base_version=0,
                                 instruction='처음', request_input={'topic': '현재 저장 입력'}))
    execute_attempt(repo, rid, str(first), lambda _: AgentAnswer(value={'text': '이전 답변'}))
    previous = repo.get(rid)
    current_revision = client.get(f"/api/v1/agents/{agent['id']}").json()['revision']
    saved = client.put(f"/api/v1/agents/{agent['id']}/save", headers={
        **headers, 'If-Match': f'"{current_revision}"'},
        json={**original, 'instructions': '최신 지침으로 작성'})
    assert saved.status_code == 200, saved.text
    command = {'id': str(uuid4()), 'expected_revision': previous['revision'], 'base_version': 1}
    url = f'/api/v1/work-requests/{rid}/script/rewrite'
    response = client.post(url, headers=headers, json=command)
    assert response.status_code == 201, response.text
    assert client.post(url, headers=headers, json=command).status_code == 201
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        attempt = conn.execute('SELECT prompt FROM script_attempts WHERE id=%s',
                               (command['id'],)).fetchone()
        prompt = json.loads(attempt['prompt'])
        assert prompt['rewrite_latest'] is True
        assert prompt['submitted_request'] == {'topic': '현재 저장 입력'}
        assert prompt['agent_instructions'] == '최신 지침으로 작성'
        assert prompt['previous_answer'] == {'text': '이전 답변'}
        assert conn.execute('SELECT input FROM customer_requests WHERE id=%s',
                            (rid,)).fetchone()['input'] == {'topic': '원본 자료'}
    execute_attempt(repo, rid, command['id'], lambda _: AgentAnswer(value={'text': '새 답변'}))
    result = repo.get(rid)
    assert result['head_version'] == 2
    assert [v['answer'] for v in result['versions']] == [{'text': '새 답변'}, {'text': '이전 답변'}]
    stale = client.post(url, headers=headers, json={**command, 'id': str(uuid4())})
    assert stale.status_code == 409
    for extra in ({'instruction': '임의 변경'}, {'request_input': {'topic': '변조'}}):
        assert client.post(url, headers=headers, json={**command, **extra}).status_code == 422
