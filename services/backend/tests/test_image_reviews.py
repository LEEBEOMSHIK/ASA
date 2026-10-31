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
            return {'value':'review result'}
    monkeypatch.setattr('asa.registry.image_reviews.init_chat_model',lambda *a,**k:Model())
    assert review_image(settings,definition,{'appearance':'green'},'blue hat',b'image',b'base')=='review result'
    assert seen['schema']['properties']['value']==definition['output_schema']
    assert seen['messages'][0].content=='user instructions'
    content=seen['messages'][1].content
    assert 'green' in content[0]['text'] and 'blue hat' in content[0]['text']
    assert content[1]['image_url']['url'].endswith(base64.b64encode(b'image').decode())
    assert content[2]['image_url']['url'].endswith(base64.b64encode(b'base').decode())
    safe=redact(content,settings)
    assert safe[1]['image_url']['url']=='[IMAGE BYTES OMITTED]'
    definition['output_schema']={'type':'integer'}
    with pytest.raises(ValueError,match='review_output_invalid'):
        review_image(settings,definition,{},'',b'image',None)
