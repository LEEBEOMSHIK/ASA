import json
from uuid import uuid4

import pytest
from test_registry_db import db as db
from test_registry_db import definition

from asa.config import Settings
from asa.models import AgentAnswer
from asa.registry.history import HistoryRepository, WorkRequest
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import AgentDraft, RegistryError
from asa.registry.script_queue import ScriptQueue
from asa.registry.script_stage import GenerateScript, SaveScript, ScriptRepository, execute_attempt


def setup_work(db):
    agents = RegistryRepository(*db)
    saved = agents.save_settings(AgentDraft.model_validate(definition()))
    history = HistoryRepository(*db)
    rid = uuid4()
    history.save(WorkRequest(id=rid, agent_id=saved['id'], version=1, input={'topic': 'sample'}))
    scripts = ScriptRepository(*db)
    first = scripts.save(str(rid), SaveScript(
        id=uuid4(), expected_revision=0, answer={'script': 'original'}))
    return agents, saved, scripts, str(rid), first


def test_retry_uses_latest_saved_and_keeps_attempt_and_old_answers(db):
    agents, saved, scripts, rid, first = setup_work(db)
    new = {**definition(), 'instructions': 'updated rules', 'output_schema': {'type': 'string'}}
    saved = agents.save_settings(AgentDraft.model_validate(new), saved['id'], saved['revision'])
    body = GenerateScript(id=uuid4(), expected_revision=first['revision'],
                          base_version=1, instruction='revise')
    queued = scripts.queue(rid, body)
    assert queued['attempts'][0]['agent_version'] == 2
    agents.save_settings(AgentDraft.model_validate({**new, 'instructions': 'later rules'}),
                         saved['id'], saved['revision'])
    assert scripts.queue(rid, body)['revision'] == queued['revision']
    prompts = []
    def generate(prompt):
        prompts.append(json.loads(prompt))
        return AgentAnswer(value='revised')
    assert execute_attempt(scripts, rid, str(body.id), generate)
    assert prompts[0]['agent_instructions'] == 'updated rules'
    assert prompts[0]['previous_answer'] == {'script': 'original'}
    versions = scripts.get(rid)['versions']
    assert [(v['agent_version'], v['output_schema']['type']) for v in versions] == [
        (2, 'string'), (1, 'object')]
    assert versions[1]['answer'] == {'script': 'original'}
    manual = scripts.save(
        rid,
        SaveScript(
            id=uuid4(),
            expected_revision=scripts.get(rid)["revision"],
            base_version=2,
            answer="manual revision",
        ),
    )
    assert manual['versions'][0]['agent_version'] == 2


def test_retry_validates_latest_inputs_and_preserves_original_request(db):
    agents, saved, scripts, rid, first = setup_work(db)
    new = {**definition(), 'input_schema': {'type': 'object', 'required': ['topic', 'tone'],
           'properties': {'topic': {'type': 'string'}, 'tone': {'type': 'string', 'minLength': 1}}}}
    agents.save_settings(AgentDraft.model_validate(new), saved['id'], saved['revision'])
    body = GenerateScript(id=uuid4(), expected_revision=first['revision'],
                          base_version=1, instruction='revise')
    with pytest.raises(RegistryError, match='retry_input_required'):
        scripts.queue(rid, body)
    assert scripts.get(rid)['attempts'] == []
    body = body.model_copy(update={'request_input': {'topic': 'sample', 'tone': 'calm'}})
    scripts.queue(rid, body)
    with scripts._connect() as conn:
        prompt = conn.execute('SELECT prompt FROM script_attempts WHERE id=%s',
                              (body.id,)).fetchone()['prompt']
        original = scripts._request(conn, rid)
    assert json.loads(prompt)['original_request']['tone'] == 'calm'
    assert original['input'] == {'topic': 'sample'}
    with pytest.raises(RegistryError, match='work_conflict'):
        scripts.queue(rid, body.model_copy(update={'request_input': {'topic': 'other'}}))


def test_initial_submission_stays_pinned_retry_resolves_model_and_idempotency(db):
    agents = RegistryRepository(*db)
    saved = agents.save_settings(AgentDraft.model_validate(definition()))
    rid = uuid4()
    HistoryRepository(*db).save(WorkRequest(
        id=rid, agent_id=saved['id'], version=1, input={'topic': 'sample'}))
    new = {**definition(), 'instructions': 'latest', 'provider': 'openai', 'model': 'second'}
    saved = agents.save_settings(AgentDraft.model_validate(new), saved['id'], saved['revision'])
    queue = ScriptQueue(Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                                 script_ai_enabled=True, ai_api_key='test-only',
                                 ai_model='first', ai_models=['first', 'second']))
    initial = queue.submit(str(rid))
    assert initial['attempts'][0]['agent_version'] == 1
    assert initial['attempts'][0]['model'] == 'first'
    assert execute_attempt(
        queue, str(rid), str(rid), lambda _: AgentAnswer(value={'script': 'old'}))
    body = GenerateScript(id=uuid4(), expected_revision=queue.get(str(rid))['revision'],
                          base_version=1, instruction='revise')
    queued = queue.submit(str(rid), body)
    assert queued['attempts'][0]['agent_version'] == 2
    assert queued['attempts'][0]['model'] == 'second'
    agents.save_settings(AgentDraft.model_validate({**new, 'model': 'not-allowed'}),
                         saved['id'], saved['revision'])
    assert queue.submit(str(rid), body)['attempts'][0] == queued['attempts'][0]
    assert queue.progress(str(rid))['agent_instructions'] == 'latest'
