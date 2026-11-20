from copy import deepcopy

import pytest

from asa.video_review import validate


def test_exact_ai_spans_preserve_source_and_ignore_invalid_metadata():
    text = '😀 숨을 고른다.  시선을 거둔다. 안녕 안녕'
    texts = {'c:prompt': text}
    raw = {'spans': [
        dict(clip_id='c', section='prompt', quote='숨을 고른다.', kind='expression'),
        dict(clip_id='c', section='prompt', quote='고른다.', kind='action'),
        dict(clip_id='c', section='prompt', quote='없는 내용', kind='camera'),
        dict(clip_id='c', section='voice', quote='시선을 거둔다.', kind='gaze'),
        dict(clip_id='c', section='prompt', quote='안녕', kind='voice'),
        dict(clip_id='c', section='prompt', quote='시선을 거둔다.', kind='invalid'),
    ]}
    before = deepcopy(raw)
    spans = validate(raw, texts)
    assert len(spans) == 1
    assert spans[0]['kind'] == 'expression'
    assert spans[0]['source'] == text
    assert text[spans[0]['start']:spans[0]['end']] == spans[0]['quote']
    assert raw == before
    assert texts == {'c:prompt': text}


def test_no_keyword_fallback_and_stale_quote():
    assert validate(None, {'c:prompt': '카메라 줌, 미소, BGM'}) == []
    assert validate({'spans': [dict(clip_id='c', section='prompt', quote='old', kind='camera')]},
                    {'c:prompt': 'new'}) == []


@pytest.mark.parametrize('classification_fails', [False, True])
def test_video_classification_is_separate_and_does_not_rewrite_plan(
    monkeypatch, classification_fails,
):
    import json
    from uuid import uuid4

    from asa.config import Settings
    from asa.providers import make_agent_generator
    from asa.video_review import ReviewPartition

    plan = dict(model_key='test', model_revision='1', aspect_ratio='9:16', clips=[dict(
        clip_id='c', scene_id='s', shot_id='s', image_id=str(uuid4()),
        source_start_seconds=0, source_end_seconds=5, duration_seconds=5,
        prompt='a pause', source_excerpt='', continuity_in='', continuity_out='', split_reason='')])
    partition = dict(sections=[dict(key='c:prompt', parts=[dict(text='a pause', kind='action')]),
                              dict(key='c:edit_notes', parts=[])])
    calls = []

    class Model:
        def with_structured_output(self, schema, **kwargs):
            self.schema = schema
            return self

        def invoke(self, messages, **kwargs):
            calls.append(messages)
            if self.schema is ReviewPartition:
                if classification_fails:
                    raise RuntimeError('classification unavailable')
                return partition
            assert 'review_annotations' not in self.schema['properties']
            return {'value': plan}

    monkeypatch.setattr('asa.providers.init_chat_model', lambda *a, **k: Model())
    monkeypatch.setattr('asa.providers.valid_input', lambda value, schema: value == plan)
    monkeypatch.setattr('asa.registry.video_planning.planner_constraints', lambda *a: 'video')
    answer = make_agent_generator(Settings(_env_file=None, ai_model='test', ai_api_key='fake'))(
        json.dumps({'output_schema': {'type': 'object'}, 'agent_instructions': 'Plan',
                    'original_request': {}}))
    assert answer.value == plan
    assert answer.review_annotations == ({'sections': []} if classification_fails else partition)
    assert len(calls) == 2
    assert json.loads(calls[1][1][1]) == {'c:prompt': 'a pause', 'c:edit_notes': ''}


def test_partition_requires_every_character_and_section_without_keyword_inference():
    from asa.video_review import partition_result

    texts = {'c:prompt': '눈썹을 올리고 고개를 돌린다.', 'c:edit_notes': ''}
    raw = {'sections': [dict(key='c:prompt', parts=[
        dict(text='눈썹을 올리고', kind='expression'), dict(text=' ', kind='none'),
        dict(text='고개를 돌린다.', kind='action')]), dict(key='c:edit_notes', parts=[])]}
    spans, status = partition_result(raw, texts)
    assert status['complete']
    assert [s['kind'] for s in spans] == ['expression', 'action']
    assert all(texts[s['key']][s['start']:s['end']] == s['quote'] for s in spans)
    raw['sections'][0]['parts'].pop(1)
    spans, status = partition_result(raw, texts)
    assert not status['complete']
    assert spans == []
    assert 'c:prompt:source_mismatch' in status['issues']
    raw['sections'].pop()
    assert 'c:edit_notes:missing_or_duplicate' in partition_result(raw, texts)[1]['issues']


def test_partition_supports_repeated_phrases_and_rejects_duplicate_sections():
    from asa.video_review import partition_result

    texts = {'c:voice': '따뜻하게 따뜻하게'}
    section = dict(key='c:voice', parts=[dict(text='따뜻하게', kind='voice'),
                   dict(text=' ', kind='none'), dict(text='따뜻하게', kind='voice')])
    spans, status = partition_result({'sections': [section]}, texts)
    assert status['complete']
    assert [s['start'] for s in spans] == [0, 5]
    assert not partition_result({'sections': [section, section]}, texts)[1]['complete']
