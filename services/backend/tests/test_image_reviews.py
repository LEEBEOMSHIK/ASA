import base64

import pytest

from asa.config import Settings
from asa.registry.image_reviews import review_image
from asa.telemetry import redact


def test_image_review_passes_actual_images_and_user_contract(monkeypatch):
    settings=Settings(_env_file=None,ai_api_key='test-only')
    definition={'provider':'openai','model':'test','limits':{'seconds':90},
                'instructions':'user instructions','output_schema':{'type':'string'}}
    seen={}
    class Model:
        def with_structured_output(self,schema):
            seen['schema']=schema
            return self
        def invoke(self,messages,**kwargs):
            seen['messages']=messages
            return {
                "value": "review result",
                "report": {
                    "summary": "ok",
                    "requirements": [],
                    "issues": [],
                    "edit_instruction": "",
                    "human_checks": [],
                },
            }

    monkeypatch.setattr('asa.registry.image_reviews.init_chat_model',lambda *a,**k:Model())
    assert (
        review_image(settings, definition, {"appearance": "green"}, "blue hat", b"image", b"base")[
            "answer"
        ]
        == "review result"
    )
    assert seen['schema']['properties']['value']==definition['output_schema']
    assert seen['messages'][0].content=='user instructions'
    content=seen['messages'][2].content
    assert 'green' in content[0]['text'] and 'blue hat' in content[0]['text']
    assert content[1]['image_url']['url'].endswith(base64.b64encode(b'image').decode())
    assert content[2]['image_url']['url'].endswith(base64.b64encode(b'base').decode())
    safe=redact(content,settings)
    assert safe[1]['image_url']['url']=='[IMAGE BYTES OMITTED]'
    definition['output_schema']={'type':'integer'}
    with pytest.raises(ValueError,match='review_output_invalid'):
        review_image(settings,definition,{},'',b'image',None)


@pytest.mark.parametrize('supported,code', [
    (False, 'review_model_image_unsupported'), (None, 'review_model_image_unknown'),
])
def test_review_rejects_unsupported_or_unknown_image_model(monkeypatch, supported, code):
    from asa.registry.model_discovery import ModelMetadata
    from asa.registry.review_connection import validate_review_model
    from asa.registry.schemas import RegistryError
    monkeypatch.setattr(
        "asa.registry.review_connection.image_metadata",
        lambda *a: ModelMetadata(checked_at="test", image_input_supported=supported),
    )
    settings = Settings(_env_file=None, ai_model='test', ai_models=['test'])
    with pytest.raises(RegistryError, match=code):
        validate_review_model(settings, {})


def test_review_default_model_rechecked_and_disabled_model_rejected(monkeypatch):
    from asa.registry.model_discovery import ModelMetadata
    from asa.registry.review_connection import validate_review_model
    from asa.registry.schemas import RegistryError
    seen = []
    def info(provider, model, bucket):
        seen.append(model)
        return ModelMetadata(checked_at='test', image_input_supported=True)
    monkeypatch.setattr('asa.registry.review_connection.image_metadata', info)
    config = Settings(_env_file=None, ai_model='first', ai_models=['first', 'second'])
    validate_review_model(config, {})
    validate_review_model(config.model_copy(update={'ai_model':'second'}), {})
    assert seen == ['first', 'second']
    with pytest.raises(RegistryError, match='invalid_model_selection'):
        validate_review_model(config, {'provider':'openai','model':'disabled'})


@pytest.mark.parametrize('provider,line,expected', [
    ('openai', '- Input modalities: text, image', True),
    ('openai', '- Input modalities: text', False),
    ('anthropic', '| Input → output | Text and images → text |', True),
    ('anthropic', '| Input → output | Text → text |', False),
    ('openai', '', None),
])
def test_image_support_requires_exact_official_model(provider,line,expected):
    from asa.registry.model_discovery import parse_document
    doc = 'Model ID: `test-model`\n' + line
    assert parse_document(provider, 'test-model', doc).image_input_supported is expected
    assert parse_document(provider, 'other-model', doc).image_input_supported is None


def test_review_report_is_required_and_preserves_user_answer(monkeypatch):
    from asa.registry.history import valid_input
    from asa.registry.review_report import REPORT_SCHEMA
    report = {'summary':'검토', 'requirements':[{'label':'모자', 'status':'unknown',
              'evidence':'가려짐'}], 'issues':[], 'edit_instruction':'', 'human_checks':['확인']}
    assert valid_input(report, REPORT_SCHEMA)
    assert not valid_input({**report, 'requirements':[{'label':'모자', 'status':'pass',
                          'evidence':'가려짐'}]}, REPORT_SCHEMA)
    payload = {'value':'사용자 형식 답변', 'report':report}
    class Model:
        def with_structured_output(self, schema):
            assert 'report' in schema['required']
            return self
        def invoke(self, *args, **kwargs):
            return payload
    monkeypatch.setattr('asa.registry.image_reviews.init_chat_model', lambda *a, **k: Model())
    settings = Settings(_env_file=None, ai_api_key='test-only')
    definition = {'provider':'openai', 'model':'test', 'limits':{'seconds':90},
                  'instructions':'사용자 지침', 'output_schema':{'type':'string'}}
    result = review_image(settings, definition, {}, '', b'image', None)
    assert result == {'format':'image_review_v1', 'answer':'사용자 형식 답변', 'report':report}
    del payload['report']
    with pytest.raises(ValueError, match='review_report_invalid'):
        review_image(settings, definition, {}, '', b'image', None)
