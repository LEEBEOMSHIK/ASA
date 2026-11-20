import json
from pathlib import Path

from asa.registry.schemas import AgentDraft
from asa.registry.service import validate_definition


def test_reference_mode_template_has_explicit_bounded_inputs():
    path = Path(__file__).resolve().parents[3] / 'docs/agent-templates/video-prompt-planner.json'
    draft = AgentDraft.model_validate(json.loads(path.read_text(encoding='utf-8')))
    assert validate_definition(draft, {}) == []
    references = draft.input_schema['properties']['video_references']
    assert references['properties']['clip_ids']['maxItems'] == 100
    field = draft.output_schema['properties']['clips']['items']['properties']['reference_inputs']
    assert field['type'] == 'array' and field['maxItems'] == 1
    assert field['items']['properties']['audio']['maxItems'] == 1
    assert 'Audio 1' in draft.instructions
    assert '첫 프레임' in draft.instructions


def test_reference_video_template_preserves_explicit_selection():
    path = Path(__file__).resolve().parents[3] / 'docs/agent-templates/video-prompt-planner.json'
    draft = AgentDraft.model_validate(json.loads(path.read_text(encoding='utf-8')))
    incoming = draft.input_schema['properties']['video_references']['properties']['video']
    outgoing = draft.output_schema['properties']['clips']['items']['properties'][
        'reference_inputs']['items']['properties']['video']
    assert incoming == outgoing
    assert incoming['maxItems'] == 1
    assert incoming['items']['required'] == ['job_id']
    assert 'Video 1' in draft.instructions
    assert validate_definition(draft, {}) == []


def test_malformed_properties_return_validation_issue_instead_of_crashing():
    path = Path(__file__).resolve().parents[3] / 'docs/agent-templates/video-prompt-planner.json'
    value = json.loads(path.read_text(encoding='utf-8'))
    value['input_schema'] = {'type': 'object', 'properties': []}
    draft = AgentDraft.model_validate(value)
    assert validate_definition(draft, {})
