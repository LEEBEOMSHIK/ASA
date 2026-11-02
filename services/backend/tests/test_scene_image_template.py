import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from asa.registry.schemas import AgentDraft
from asa.registry.service import validate_definition


def test_scene_image_contract_accepts_confirmed_character_envelope():
    path = Path(__file__).resolve().parents[3] / 'docs/agent-templates/scene-image-planner.json'
    draft = AgentDraft.model_validate_json(path.read_text(encoding='utf-8'))
    assert validate_definition(draft, {}) == []
    # An extra arbitrary nesting layer remains rejected.
    nested = json.loads(json.dumps(draft.input_schema))
    deeper = {'type': 'object', 'properties': {'wrapped': nested}}
    invalid = draft.model_copy(update={'input_schema': deeper})
    assert any(i.code == 'schema_depth' for i in validate_definition(invalid, {}))


def test_long_user_instructions_can_keep_existing_text_and_add_reference_rules():
    path = Path(__file__).resolve().parents[3] / 'docs/agent-templates/scene-image-planner.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['instructions'] = 'a' * 12000
    assert len(AgentDraft.model_validate(data).instructions) == 12000
    data['instructions'] += 'a'
    with pytest.raises(ValidationError):
        AgentDraft.model_validate(data)
