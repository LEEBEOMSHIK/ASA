import pytest

from asa.config import Settings
from asa.video_providers import provider_connection
from asa.wan_regions import regional_settings


def test_legacy_credentials_never_cross_regions():
    cfg = Settings(_env_file=None, wan_api_key='legacy', wan_workspace_id='old')
    assert regional_settings(cfg, 'ap-southeast-1').wan_api_key.get_secret_value() == 'legacy'
    assert regional_settings(cfg, 'ap-northeast-1').wan_api_key.get_secret_value() == ''


def test_frozen_endpoint_selects_its_own_credentials():
    cfg = Settings(_env_file=None, wan_api_key='legacy', wan_workspace_id='old',
                   wan_tokyo_api_key='tokyo-secret', wan_tokyo_workspace_id='tokyo')
    model = cfg.video_model_profiles['wan3'].model_dump()
    model['provider_endpoint'] = 'https://tokyo.ap-northeast-1.maas.aliyuncs.com/api/v1'
    base, headers = provider_connection(cfg, model)
    assert base == model['provider_endpoint']
    assert headers['Authorization'] == 'Bearer tokyo-secret'
    model['provider_endpoint'] = 'https://untrusted.example/api/v1'
    with pytest.raises(ValueError, match='endpoint_changed'):
        provider_connection(cfg, model)


def test_partial_regional_profile_does_not_mix_legacy_credentials():
    cfg = Settings(_env_file=None, wan_api_key='legacy', wan_workspace_id='old',
                   wan_singapore_workspace_id='new')
    assert regional_settings(cfg, 'ap-southeast-1').wan_api_key.get_secret_value() == ''


def test_legacy_other_region_frozen_endpoint_is_preserved():
    cfg = Settings(_env_file=None, wan_api_key='legacy', wan_workspace_id='old',
                   wan_region='cn-beijing')
    model = cfg.video_model_profiles['wan3'].model_dump()
    model['provider_endpoint'] = 'https://old.cn-beijing.maas.aliyuncs.com/api/v1'
    assert provider_connection(cfg, model)[1]['Authorization'] == 'Bearer legacy'
    assert regional_settings(cfg, 'ap-southeast-1').wan_api_key.get_secret_value() == ''
