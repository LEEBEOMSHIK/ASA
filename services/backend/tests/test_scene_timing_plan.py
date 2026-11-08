import pytest
from pydantic import ValidationError

from asa.scene_timing import SceneTimingPlan, timing_settings


def test_timing_plan_requires_exact_speaker_and_positive_intervals():
    plan = {'duration': 30, 'speakers': [{'id': 'n', 'name': '나레이션', 'role': 'narrator'}],
            'cues': [{'id': 'one', 'speaker_id': 'n', 'text': '안녕', 'start': 1,
                      'end': 3, 'emotion': ''}]}
    parsed = SceneTimingPlan.model_validate(plan)
    settings = timing_settings(parsed, 'openai-realtime', 'marin')
    assert settings.purpose == 'timing' and settings.timing_duration_seconds == 30
    assert settings.timing_preview_seconds == 3
    short = timing_settings(parsed.model_copy(update={'planned_duration': 5}),
                            'openai-realtime', 'marin')
    assert short.timing_duration_seconds == 30 and short.timing_preview_seconds == 5
    plan['cues'][0]['speaker_id'] = 'missing'
    with pytest.raises((ValidationError, ValueError)):
        timing_settings(SceneTimingPlan.model_validate(plan), 'openai-realtime', 'marin')


def test_provider_requires_structured_timing_and_resolves_schema_refs(monkeypatch):
    import json

    from asa.config import Settings
    from asa.providers import make_agent_generator

    plan = {'duration': 10, 'speakers': [{'id': 'n', 'name': '나레이션', 'role': 'narrator'}],
            'cues': [{'id': 'a', 'speaker_id': 'n', 'text': '안녕', 'start': 0, 'end': 2}]}
    result = {'value': '본문', 'timing_plan': plan}
    class Model:
        def with_structured_output(self, schema):
            assert 'timing_plan' in schema['required']
            def resolve(node):
                if isinstance(node, dict):
                    if '$ref' in node:
                        assert node['$ref'].split('/')[-1] in schema['$defs']
                    for child in node.values():
                        resolve(child)
                elif isinstance(node, list):
                    for child in node:
                        resolve(child)
            resolve(schema)
            return self
        def invoke(self, messages, **kwargs):
            return result
    monkeypatch.setattr('asa.providers.init_chat_model', lambda *a, **k: Model())
    generate = make_agent_generator(Settings(_env_file=None, ai_model='test', ai_api_key='fake'))
    prompt = json.dumps({'agent_instructions': '장면 계획', 'scene_timing': True,
                         'output_schema': {'type': 'string'}, 'original_request': '10초'})
    answer = generate(prompt)
    assert answer.value == '본문' and answer.timing_plan['duration'] == 10
