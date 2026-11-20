import pytest

from asa.config import Settings
from asa.higgsfield_models import reference_support
from asa.registry.video_planning import catalog_estimate
from asa.video_providers import generation_request, validate_input


@pytest.mark.parametrize('key,name,rate,video_rate,low,high,audio', [
    ('hf-wan3', 'alibaba/wan-3.0', .075, .1493, 2, 30, True),
    ('hf-seedance25', 'bytedance/seedance-2.5', .2647, .3264, 4, 30, True),
    ('hf-seedance20', 'bytedance/seedance-2.0', .1735, .2128, 4, 15, True),
    ('hf-kling4', 'kling-video/v4.0', .1257, .1544, 3, 30, False),
])
def test_model_routes_capabilities_and_costs(key, name, rate, video_rate, low, high, audio):
    cfg = Settings(_env_file=None, higgsfield_api_key='test:secret')
    profile = cfg.video_model_profiles[key]
    model = profile.model_dump()
    spec = dict(prompt='Keep the original action', duration_seconds=5, aspect_ratio='9:16',
                resolution='720p', audio=audio)
    start = 'https://cdn.example.com/start.png'
    url, _, body = generation_request(cfg, model, spec, b'', start_image_url=start)
    assert url == f'https://api.higgsfield.ai/{name}/image-to-video'
    assert body['prompt'] == spec['prompt'] and body['image_url'] == start
    assert ('enable_thinking' in body) == (key == 'hf-wan3')
    assert ('generate_audio' in body) == audio
    assert ('aspect_ratio' in body) == (key == 'hf-wan3')
    refs = {'character_image_ids': ['character'], 'audio': [{}] if audio else [], 'video': [{}]}
    media = [{'type': kind, 'url': 'https://cdn.example.com/reference'} for kind in
             ['reference_image', 'reference_video', *(['reference_audio'] if audio else [])]]
    url, _, body = generation_request(cfg, model, {**spec, 'reference_inputs': refs}, b'', media,
                                      start_image_url=start)
    assert url == f'https://api.higgsfield.ai/{name}/reference-to-video'
    assert len(body['image_urls']) == 2 and len(body['video_urls']) == 1
    assert ('audio_urls' in body) == audio
    assert reference_support(model) == {'image': True, 'audio': audio, 'video': True}
    assert catalog_estimate(profile, 5)['amount_usd'] == round(5 * rate, 6)
    assert catalog_estimate(profile, 5, True)['amount_usd'] == round(5 * video_rate, 6)
    for duration in [low, high]:
        validate_input(model, {**spec, 'duration_seconds': duration})
    for duration in [low - 1, high + 1, 5.0, True]:
        with pytest.raises(ValueError, match='duration'):
            validate_input(model, {**spec, 'duration_seconds': duration})


def test_kling_rejects_audio_instead_of_silently_dropping_it():
    cfg = Settings(_env_file=None)
    model = cfg.video_model_profiles['hf-kling4'].model_dump()
    spec = dict(prompt='original', duration_seconds=5, aspect_ratio='16:9',
                resolution='720p', audio=False)
    with pytest.raises(ValueError, match='video_audio_unsupported'):
        validate_input(model, {**spec, 'audio': True})
    with pytest.raises(ValueError, match='video_reference_audio_unsupported'):
        validate_input(model, {**spec, 'reference_inputs': {'audio': [{}]}})
