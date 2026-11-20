from copy import deepcopy
from uuid import uuid4

from asa.registry.history import valid_input
from asa.registry.repository import RegistryRepository
from asa.registry.video_model_schema import runtime_input_schema


def legacy_schema():
    return {'type': 'object', 'required': ['video_model'], 'properties': {
        'video_model': {'type': 'string', 'x-video-model': True,
                        'enum': ['runway-gen45', 'wan3'], 'default': 'wan3'},
        'other': {'type': 'string', 'enum': ['wan3']},
    }}


def test_display_and_validation_share_legacy_model_choices_without_mutation():
    stored = legacy_schema()
    before = deepcopy(stored)
    display = runtime_input_schema(stored)
    assert display['properties']['video_model']['enum'][:6] == [
        'runway-gen45', 'wan3', 'hf-wan3', 'hf-seedance25', 'hf-seedance20', 'hf-kling4']
    assert 'hf-seedance20-4k' in display['properties']['video_model']['enum']
    assert display['properties']['video_model']['default'] == 'wan3'
    for model in display['properties']['video_model']['enum']:
        assert valid_input({'video_model': model}, stored)
    assert not valid_input({'video_model': 'unknown'}, stored)
    assert not valid_input({'video_model': 'wan3', 'other': 'hf-wan3'}, stored)
    assert stored == before
    assert runtime_input_schema(display) == display


def test_non_wan_and_unmarked_selectors_keep_restrictions():
    for node in [{'type': 'string', 'enum': ['wan3']},
                 {'type': 'string', 'enum': ['runway-gen45'], 'x-video-model': True}]:
        assert runtime_input_schema(node) == node
        assert not valid_input('hf-wan3', node)


def test_catalog_returns_runtime_schema_without_altering_persisted_definition():
    stored = legacy_schema()
    before = deepcopy(stored)
    row = {'agent_id': str(uuid4()), 'version': 1, 'alias': 'test', 'definition': {
        'name': 'Video', 'description': '', 'input_schema': stored,
        'output_schema': {'type': 'string'}, 'tools': [],
    }}
    class Connection:
        def execute(self, *args):
            return self

        def fetchall(self):
            return [row]

    tools = RegistryRepository('', uuid4())._tools(Connection())
    agent = next(tool for tool in tools if tool.get('agent_id') == row['agent_id'])
    assert 'hf-wan3' in agent['input_schema']['properties']['video_model']['enum']
    assert stored == before
