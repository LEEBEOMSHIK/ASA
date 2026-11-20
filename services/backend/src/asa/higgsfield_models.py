"""Reviewed Higgsfield adapters; capabilities do not mutate historical model snapshots."""
from typing import Any

from asa.video_contracts import VideoModelProfile

MODELS = {
    'alibaba/wan-3.0': (2, 30, True),
    'bytedance/seedance-2.5': (4, 30, True),
    'bytedance/seedance-2.0': (4, 15, True),
    'kling-video/v4.0': (3, 30, False),
}
EXTRA_MODELS = {
    'hf-seedance25': ('bytedance/seedance-2.5', 'Seedance 2.5', .2647, .3264),
    'hf-seedance20': ('bytedance/seedance-2.0', 'Seedance 2.0', .1735, .2128),
    'hf-kling4': ('kling-video/v4.0', 'Kling 4.0', .1257, .1544),
}


# USD per output second: without / with video reference. Official model
# playground pricing, verified 2026-11-20; image/audio alone use the first rate.
RESOLUTION_RATES = {
    'alibaba/wan-3.0': {'480p': (.0375, .0747), '720p': (.075, .1493),
                       '1080p': (.15, .3011)},
    'bytedance/seedance-2.5': {'480p': (.1177, .1387), '720p': (.2647, .3264),
                             '1080p': (.6518, .7858)},
    'bytedance/seedance-2.0': {'480p': (.0804, .0991), '720p': (.1735, .2128),
                             '1080p': (.4293, .5183), '4k': (.8907, 1.0669)},
    'kling-video/v4.0': {'720p': (.1257, .1544), '1080p': (.1879, .2336)},
}


def resolution_profiles(existing: dict[str, VideoModelProfile]) -> dict[str, VideoModelProfile]:
    """Separate profiles preserve existing keys and historical job fingerprints."""
    result = {}
    for key in ['hf-wan3', *EXTRA_MODELS]:
        base = existing.get(key)
        if base is None or base.provider != 'higgsfield':
            continue
        for resolution, (rate, video_rate) in RESOLUTION_RATES.get(base.model, {}).items():
            if resolution == '720p':
                continue
            result[f'{key}-{resolution}'] = base.model_copy(update={
                'resolution': resolution, 'usd_per_second': rate,
                'usd_per_second_with_video': video_rate,
            })
    return result


def profiles() -> dict[str, VideoModelProfile]:
    return {key: VideoModelProfile(
        provider='higgsfield', model=model, label=label, revision='1', enabled=True,
        durations=list(range(MODELS[model][0], MODELS[model][1] + 1)),
        aspect_ratios=['9:16', '16:9'], resolution='720p', max_prompt_chars=20000,
        supports_audio=MODELS[model][2], usd_per_second=rate,
        usd_per_second_with_video=video_rate,
        documentation_url=f'https://open.higgsfield.ai/models/{model}/reference-to-video/api-reference',
        verified_on='2026-11-20',
    ) for key, (model, label, rate, video_rate) in EXTRA_MODELS.items()}


def reference_support(model: dict[str, Any]) -> dict[str, bool]:
    hf = model.get('provider') == 'higgsfield' and model.get('model') in MODELS
    wan = model.get('provider') == 'alibaba' and model.get('model') == 'wan3.0-video'
    return {'image': hf or wan, 'audio': wan or (hf and MODELS[model['model']][2]),
            'video': hf}


def validate_spec(model: dict[str, Any], spec: dict[str, Any]) -> None:
    name = model.get('model')
    if name not in MODELS or model.get('resolution') not in RESOLUTION_RATES[name]:
        raise ValueError('video_model_unavailable')
    if spec.get('resolution', model['resolution']) != model['resolution']:
        raise ValueError('video_resolution_unsupported')
    low, high, audio = MODELS[name]
    duration = spec['duration_seconds']
    if type(duration) is not int or not low <= duration <= high:
        raise ValueError('video_duration_unsupported')
    refs = spec.get('reference_inputs')
    if refs and refs.get('audio') and not audio:
        raise ValueError('video_reference_audio_unsupported')
    if spec.get('audio') and not audio:
        raise ValueError('video_audio_unsupported')
