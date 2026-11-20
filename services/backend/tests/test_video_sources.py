from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from asa.registry.schemas import RegistryError
from asa.registry.video_sources import sources


def test_sources_use_original_job_contract_and_allowlist(monkeypatch):
    workspace, request, image, cast = uuid4(), uuid4(), uuid4(), uuid4()
    job = {'id': uuid4(), 'clip_id': 'c1', 'answer_version': 2,
           'generation_input': {'start_image_id': str(image)}, 'status': 'review'}
    monkeypatch.setattr('asa.registry.video_sources.video_inheritance.resolve',
                        lambda *a: {'jobs': [job]})
    versions = []
    def contract(conn, ws, req, version):
        assert ws == workspace and req == request
        versions.append(version)
        return {'secret': 'hidden', 'original_request': {'script': 'old script',
                'scenes': 'old scenes', 'private_field': 'hidden', 'scene_images': {'scenes': [{
                'image_id': str(image), 'name': 'Scene', 'settings': '{"facts":"original"}',
                'character_settings': '[{"image_id":"'+str(cast)+'","name":"Cast"}]'}]}}}
    monkeypatch.setattr('asa.registry.video_sources.answer_contract', contract)
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'present': 1}
    result = sources(conn, workspace, request, 5, 'c1')
    assert versions == [2]
    assert result['answer_version'] == 2 and result['inherited']
    assert result['script'] == 'old script'
    assert result['generation_images'][0]['image_id'] == str(image)
    assert result['planning_images'][0]['image_id'] == str(cast)
    assert 'hidden' not in str(result)
    assert all(workspace in call.args[1] for call in conn.execute.call_args_list)


def test_sources_missing_contract_does_not_fall_back_to_current_input(monkeypatch):
    monkeypatch.setattr('asa.registry.video_sources.video_inheritance.resolve',
                        lambda *a: {'jobs': [{'id': uuid4(), 'clip_id': 'c', 'answer_version': 1,
                        'generation_input': {}, 'status': 'review'}]})
    monkeypatch.setattr('asa.registry.video_sources.answer_contract', lambda *a: None)
    result = sources(MagicMock(), uuid4(), uuid4(), 2, 'c')
    assert result['snapshot_available'] is False
    assert result['script'] == '' and result['scenes'] == ''


def test_sources_unknown_clip_is_not_found(monkeypatch):
    monkeypatch.setattr('asa.registry.video_sources.video_inheritance.resolve',
                        lambda *a: {'jobs': []})
    with pytest.raises(RegistryError):
        sources(MagicMock(), uuid4(), uuid4(), 1, 'unowned')

def test_sources_foreign_asset_identifiers_are_omitted(monkeypatch):
    image = uuid4()
    monkeypatch.setattr('asa.registry.video_sources.video_inheritance.resolve',
                        lambda *a: {'jobs': [{'id': uuid4(), 'clip_id': 'c', 'answer_version': 1,
                        'generation_input': {'start_image_id': str(image)}, 'status': 'review'}]})
    monkeypatch.setattr('asa.registry.video_sources.answer_contract', lambda *a: {
        'original_request': {'scene_images': {'scenes': [{'image_id': str(image),
        'character_settings': '[{"image_id":"'+str(image)+'","name":"foreign"}]'}]}}})
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    result = sources(conn, uuid4(), uuid4(), 1, 'c')
    assert result['generation_images'] == []
    assert result['planning_images'] == []
    assert str(image) not in str(result)

def test_reference_images_are_not_mislabeled_as_first_frames(monkeypatch):
    image = uuid4()
    monkeypatch.setattr('asa.registry.video_sources.video_inheritance.resolve',
                        lambda *a: {'jobs': [{'id': uuid4(), 'clip_id': 'c', 'answer_version': 1,
                        'generation_input': {'start_image_id': str(image),
                        'reference_inputs': {'character_image_ids': []},
                        'reference_images': [{'image_id': str(image), 'role': 'scene',
                                              'sha256': 'frozen'}]}, 'status': 'review'}]})
    monkeypatch.setattr('asa.registry.video_sources.answer_contract', lambda *a: None)
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {'sha256': 'frozen'}
    result = sources(conn, uuid4(), uuid4(), 1, 'c')
    assert result['generation_mode'] == 'reference'
    assert result['generation_images'][0]['role'] == 'scene'
    conn.execute.return_value.fetchone.return_value = {'sha256': 'changed'}
    assert sources(conn, uuid4(), uuid4(), 1, 'c')['generation_images'] == []

@pytest.mark.parametrize(('value', 'fallback'), [('[]', {}), ('{}', []), ('null', {}),
                                                ('"text"', {}), ('1', [])])
def test_decoded_rejects_wrong_serialized_shape(value, fallback):
    from asa.registry.video_sources import decoded
    assert decoded(value, fallback) == fallback

def test_exact_historical_job_uses_its_original_contract(monkeypatch):
    current, old = uuid4(), uuid4()
    def job(ident, version):
        return {'id': ident, 'clip_id': 'c', 'answer_version': version,
                'generation_input': {}, 'status': 'review'}
    monkeypatch.setattr('asa.registry.video_sources.video_inheritance.resolve',
                        lambda *a: {'jobs': [job(current, 5)],
                                    'previous_attempts': [job(old, 2)]})
    monkeypatch.setattr('asa.registry.video_sources.answer_contract',
                        lambda conn, ws, req, ver: {'original_request': {'script': f'v{ver}'}})
    args = MagicMock(), uuid4(), uuid4(), 5, 'c'
    assert sources(*args)['script'] == 'v5'
    assert sources(*args, job_id=old)['script'] == 'v2'
    assert sources(*args, job_id=old)['answer_version'] == 2
    with pytest.raises(RegistryError):
        sources(*args, job_id=uuid4())
    with pytest.raises(RegistryError):
        sources(*args[:-1], 'other-clip', job_id=old)
