import json

import pytest

from asa.config import Settings
from asa.providers import make_agent_generator
from asa.registry.schemas import RegistryError


@pytest.mark.parametrize('streaming', [False, True])
def test_agent_reference_images_and_full_sources_reach_model(monkeypatch, streaming):
    from asa.registry import review_connection
    from asa.tools import character_handoff

    sent = []
    image = {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,YQ=='}}
    original = {'script': '시작\n전체 대본\n끝', 'scenes': '장면 1\n장면 2',
                'characters': {'format': character_handoff.FORMAT, 'project_id': 'p'}}
    repo = object()

    def resolve(source, value):
        assert source is repo
        assert value == original
        return [image]

    class Model:
        def with_structured_output(self, schema):
            return self

        def invoke(self, messages, **kwargs):
            sent.extend(messages)
            return {'value': '계획'}

        def stream(self, messages, **kwargs):
            yield self.invoke(messages)

    monkeypatch.setattr(character_handoff, 'image_content', resolve)
    monkeypatch.setattr(review_connection, 'validate_review_model', lambda *a: None)
    monkeypatch.setattr('asa.providers.init_chat_model', lambda *a, **kw: Model())
    progress = []
    generate = make_agent_generator(
        Settings(_env_file=None, ai_model='test', ai_api_key='fake'),
        progress.append if streaming else None, reference_repo=repo)
    contract = {'agent_instructions': '장면 설계', 'original_request': original,
                'previous_answer': '이전 계획', 'revision_request': '구도 수정',
                'output_schema': {'type': 'string'}}
    assert generate(json.dumps(contract)).value == '계획'
    content = sent[-1].content
    assert content[-1] == image
    text = json.loads(content[0]['text'])
    assert text['original_request'] == original
    assert text['previous_answer'] == '이전 계획'
    assert text['revision_request'] == '구도 수정'


def test_agent_refuses_unverified_image_model_before_paid_request(monkeypatch):
    from asa.registry import review_connection
    from asa.tools import character_handoff

    monkeypatch.setattr(character_handoff, 'image_content', lambda *a: [{'type': 'image_url'}])

    def reject(*args):
        raise RegistryError(422, 'review_model_image_unsupported')

    monkeypatch.setattr(review_connection, 'validate_review_model', reject)
    monkeypatch.setattr('asa.providers.init_chat_model', lambda *a, **kw: object())
    generate = make_agent_generator(
        Settings(_env_file=None, ai_model='test', ai_api_key='fake'), reference_repo=object())
    with pytest.raises(RegistryError, match='review_model_image_unsupported'):
        generate(json.dumps({'original_request': {}, 'output_schema': {'type': 'string'}}))
