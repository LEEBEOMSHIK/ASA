import pytest

from asa.config import Settings
from asa.registry.schemas import RegistryError
from asa.video_settings import resolve_settings, validate_answer


@pytest.mark.parametrize('enabled,key,duration,source', [
    (True, 'hf-wan3-480p', 8, 'user'),
    (False, 'hf-wan3-1080p', 5, 'admin'),
])
def test_source_precedence_and_frozen_answer(enabled, key, duration, source):
    cfg = Settings(_env_file=None)
    original = {'video_model': 'hf-wan3-480p', 'video_duration_seconds': 8}
    controls = {'revision': 4, 'user_details_enabled': enabled, 'model_defaults': {
        'higgsfield:alibaba/wan-3.0': {'model_key': 'hf-wan3-1080p', 'duration_seconds': 5}}}
    effective, snapshot = resolve_settings(cfg, controls, original, 'video_model')
    assert effective['video_model'] == key
    assert effective['video_duration_seconds'] == duration
    assert snapshot['source'] == source
    assert original['video_model'] == 'hf-wan3-480p'
    answer = {'model_key': key, 'model_revision': '1', 'clips': [{'duration_seconds': duration}]}
    validate_answer(answer, snapshot)
    with pytest.raises(ValueError, match='video_settings_mismatch'):
        validate_answer({**answer, 'clips': [{'duration_seconds': duration + 1}]}, snapshot)


def test_auto_user_choice_does_not_inherit_admin_duration():
    cfg = Settings(_env_file=None)
    controls = {'revision': 1, 'user_details_enabled': True, 'model_defaults': {
        'higgsfield:alibaba/wan-3.0': {'model_key': 'hf-wan3-1080p', 'duration_seconds': 10}}}
    effective, snapshot = resolve_settings(cfg, controls, {'video_model': 'hf-wan3'}, 'video_model')
    assert effective.get('video_duration_seconds', 0) == 0
    assert snapshot['model_key'] == 'hf-wan3'
    with pytest.raises(RegistryError):
        resolve_settings(cfg, controls, {'video_model': 'hf-wan3', 'video_duration_seconds': 99},
                         'video_model')
