import pytest

from asa.config import Settings
from asa.registry.video_planning import catalog_estimate
from asa.video_providers import generation_request, validate_input


@pytest.mark.parametrize('key,resolution,rate,video_rate', [
    ('hf-wan3-480p', '480p', .0375, .0747),
    ('hf-wan3-1080p', '1080p', .15, .3011),
    ('hf-seedance25-1080p', '1080p', .6518, .7858),
    ('hf-seedance25-480p', '480p', .1177, .1387),
    ('hf-seedance20-480p', '480p', .0804, .0991),
    ('hf-seedance20-1080p', '1080p', .4293, .5183),
    ('hf-seedance20-4k', '4k', .8907, 1.0669),
    ('hf-kling4-1080p', '1080p', .1879, .2336),
])
def test_resolution_reaches_request_and_cost(key, resolution, rate, video_rate):
    cfg = Settings(_env_file=None, higgsfield_api_key='test:secret')
    profile = cfg.video_model_profiles[key]
    spec = dict(prompt='original', duration_seconds=5, aspect_ratio='9:16',
                resolution=resolution, audio=False)
    validate_input(profile.model_dump(), spec)
    _, _, body = generation_request(cfg, profile.model_dump(), spec, b'',
                                    start_image_url='https://cdn.example.com/start.png')
    assert body['resolution'] == resolution
    assert profile.usd_per_second == rate
    assert profile.usd_per_second_with_video == video_rate
    assert catalog_estimate(profile, 5, False)['amount_usd'] == round(rate * 5, 6)
    assert catalog_estimate(profile, 5, True)['amount_usd'] == round(video_rate * 5, 6)
    refs = {'character_image_ids': [], 'audio': [], 'video': [{}]}
    _, _, reference_body = generation_request(
        cfg, profile.model_dump(), {**spec, 'reference_inputs': refs}, b'',
        [{'type': 'reference_video', 'url': 'https://cdn.example.com/previous.mp4'}],
        start_image_url='https://cdn.example.com/start.png')
    assert reference_body['resolution'] == resolution
    assert reference_body['video_urls'] == ['https://cdn.example.com/previous.mp4']
    with pytest.raises(ValueError):
        validate_input(profile.model_dump(), {**spec, 'resolution': '720p'})
