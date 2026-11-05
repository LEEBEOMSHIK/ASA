import json

from asa.config import Settings
from asa.providers import make_agent_generator


def test_scene_plan_has_separate_output_budget(monkeypatch):
    captured = []
    prompts = []
    class Model:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages, **kwargs):
            prompts.extend(messages)
            return {'value': {'summary': 'ready', 'shots': [], 'checks': []}}
    def init(*args, **kwargs):
        captured.append(kwargs)
        return Model()
    monkeypatch.setattr('asa.providers.init_chat_model', init)
    schema = {'type': 'object', 'properties': {
        'summary': {'type': 'string'}, 'shots': {'type': 'array', 'items': {'type': 'string'}},
        'checks': {'type': 'array', 'items': {'type': 'string'}}}}
    generate = make_agent_generator(Settings(_env_file=None, ai_model='test', ai_api_key='fake',
                                            script_output_tokens=8192))
    generate(json.dumps({'agent_instructions': 'Keep all scenes.', 'output_schema': schema,
                         'original_request': {}}))
    assert captured[-1]['max_tokens'] == 24576
    system = '\n'.join(m[1] for m in prompts if m[0] == 'system')
    assert '설정 충돌처럼' not in system
    assert '생성 차단 근거가 아닙니다' in system
    assert '참고용 비등장 인물 이미지도 포함' in system
    assert '동일 소품의 이동' in system
    assert '최종 판단은 사용자' in system


def test_output_failure_codes_are_safe_and_specific():
    from asa.registry.script_stage import output_error_code
    class LengthFinishReasonError(Exception):
        pass
    assert output_error_code(LengthFinishReasonError('secret')) == 'ai_output_limit'
    assert output_error_code(ValueError('invalid_agent_output')) == 'ai_output_invalid'
    assert output_error_code(RuntimeError('secret')) == 'ai_call_failed'


def test_scene_sources_preserve_original_and_resolve_only_shot_cast():
    from copy import deepcopy

    from asa.registry.scene_images import source_views
    scene = '### 2. 책 속 — 20초\n- 화면: 차례로 보여 준다.\n\n'
    context = {'input': {'script': '앞 문장.\n돼지의 바지가 사라졌어요.\n끝.',
                         'scenes': '### 1. 시작\n첫 장면\n' + scene + '### 3. 끝\n마지막',
                         'characters': {'format': 'asa_character_selection_v1',
                                        'characters': [{'id': 'pig', 'name': '돼지',
                                                        'image_id': 'image-pig'},
                                                       {'id': 'other', 'name': '다른 인물'}]}},
               'plan': {'shots': [{'scene_id': '2', 'source_excerpt': '돼지의 바지가 사라졌어요.',
                                   'character_ids': ['pig', 'missing']}]}}
    before = deepcopy(context)
    view = source_views(context)['scene_1']
    assert view['scene'] == scene
    assert view['script'] == '돼지의 바지가 사라졌어요.'
    assert view['script_matched'] and view['scene_matched']
    assert [c['id'] for c in view['characters']] == ['pig', 'missing']
    assert view['characters'][1]['image_id'] is None
    assert context == before
    context['plan']['shots'][0].update(scene_id='unknown', source_excerpt='AI가 바꾼 문장')
    fallback = source_views(context)['scene_1']
    assert fallback['script'] == context['input']['script']
    assert fallback['scene'] == context['input']['scenes']
    assert not fallback['script_matched'] and not fallback['scene_matched']


def test_scene_source_uses_original_script_anchors_without_rewriting():
    from asa.registry.scene_images import source_views
    script = '머리말\n시작 문장\n[효과음] 쿵!\n끝 문장\n뒷말'
    context = {'input': {'script': script,
                         'scenes': '### 1. 시작\n- **대응 대본:** “시작 문장” ~ “끝 문장”\n'},
               'plan': {'shots': [{'scene_id': '1', 'source_excerpt': '시작 문장',
                                   'character_ids': []}]}}
    view = source_views(context)['scene_1']
    assert view['script'] == '시작 문장\n[효과음] 쿵!\n끝 문장'
    assert view['script_matched']


def test_ai_scene_opinion_does_not_block_but_missing_references_do():
    from asa.registry.scene_images import readiness

    context = {"input": {"cast": {"format": "asa_character_selection_v1",
               "characters": [{"id": "ghost", "image_id": "image-1"}]}},
               "plan": {"shots": [{"character_ids": ["ghost"],
               "reference_image_ids": ["image-1"], "ready": False,
               "review_notes": "필수 소품 충돌: 무늬 확인 필요"}]}}
    assert readiness(context) == {"scene_1": []}
    context["plan"]["shots"][0]["character_ids"] = ["missing"]
    assert len(readiness(context)["scene_1"]) == 1


def test_scene_non_cast_reference_is_attached_without_adding_cast(monkeypatch):
    from copy import deepcopy
    from asa.registry.scene_images import readiness, snapshot, prompt
    from asa.registry.schemas import RegistryError
    import pytest

    cast = {"id": "ghost", "image_id": "00000000-0000-0000-0000-000000000001"}
    prop = {"id": "friend", "image_id": "00000000-0000-0000-0000-000000000002"}
    unused = {"id": "unused", "image_id": "00000000-0000-0000-0000-000000000003"}
    context = {"input": {"script": "모자만 참고", "scenes": "친구는 등장하지 않는다",
               "cast": {"format": "asa_character_selection_v1", "characters": [cast, prop, unused]}},
               "plan": {"shots": [{"character_ids": ["ghost"],
               "reference_image_ids": [prop["image_id"]], "ready": False,
               "review_notes": "모자의 형태만 참고"}]}}
    before = deepcopy(context)
    seen = []
    def selected(repo, refs, overrides):
        seen.extend(r['image_id'] for r in refs)
        assert overrides == {}
        return {"format": "asa_character_selection_v1", "characters": [cast, prop]}
    monkeypatch.setattr("asa.registry.scene_images.resolve_references", selected)
    monkeypatch.setattr("asa.tools.character_handoff.image_content", lambda repo, value: [])
    assert readiness(context) == {"scene_1": []}
    result = snapshot(None, context, "scene_1")
    assert seen == [cast["image_id"], prop["image_id"]]
    assert [r["role"] for r in result["reference_roles"]] == ["cast", "reference_only"]
    assert result["shot"]["character_ids"] == ["ghost"]
    assert "Never depict a reference_only character" in prompt(result, {}, "")
    assert context == before
    context["plan"]["shots"][0]["reference_image_ids"] = ["unselected"]
    assert readiness(context)["scene_1"]
    with pytest.raises(RegistryError):
        snapshot(None, context, "scene_1")
