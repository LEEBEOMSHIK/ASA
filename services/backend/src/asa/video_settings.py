"""Resolve execution settings once at acceptance, never from worker-time policy."""
from typing import Any

from asa.config import Settings
from asa.registry.schemas import RegistryError


def validate_defaults(settings: Settings, defaults: dict[str, Any]) -> None:
    for family, value in defaults.items():
        if not isinstance(value, dict) or set(value) != {'model_key', 'duration_seconds'}:
            raise RegistryError(422, 'video_defaults_invalid')
        if not isinstance(value['model_key'], str):
            raise RegistryError(422, 'video_defaults_invalid')
        model = settings.video_model_profiles.get(value['model_key'])
        if not model or not model.enabled or family != f'{model.provider}:{model.model}':
            raise RegistryError(422, 'video_defaults_invalid')
        duration = value['duration_seconds']
        if type(duration) is not int or (duration != 0 and duration not in model.durations):
            raise RegistryError(422, 'video_duration_unsupported')


def resolve_settings(settings: Settings, controls: dict[str, Any], inputs: dict[str, Any],
                     field: str) -> tuple[dict[str, Any], dict[str, Any]]:
    model = settings.video_model_profiles.get(inputs.get(field, ''))
    if not model or not model.enabled:
        raise RegistryError(422, 'video_model_unavailable')
    key = inputs[field]
    duration = inputs.get('video_duration_seconds', 0)
    source = 'user' if controls['user_details_enabled'] else 'admin'
    if source == 'admin':
        default = controls.get('model_defaults', {}).get(f'{model.provider}:{model.model}')
        if default:
            key, duration = default['model_key'], default['duration_seconds']
        else:
            # The configured default is the original profile, not the user's variant.
            key = next((k for k, m in settings.video_model_profiles.items()
                        if m.enabled and m.provider == model.provider and m.model == model.model
                        and m.resolution == '720p'), key)
            duration = 0
        chosen = settings.video_model_profiles.get(key)
        if (not chosen or not chosen.enabled or chosen.provider != model.provider
                or chosen.model != model.model):
            raise RegistryError(422, 'video_defaults_invalid')
        model = chosen
    if type(duration) is not int or (duration != 0 and duration not in model.durations):
        raise RegistryError(422, 'video_duration_unsupported')
    effective = {**inputs, field: key}
    if duration or 'video_duration_seconds' in inputs:
        effective['video_duration_seconds'] = duration
    return effective, {'source': source, 'policy_revision': controls['revision'],
                       'model_key': key, 'model_revision': model.revision,
                       'resolution': model.resolution, 'duration_seconds': duration}


def validate_answer(answer: dict[str, Any], snapshot: dict[str, Any]) -> None:
    if not snapshot:
        return  # Historical answers retain their original contract.
    if (answer.get('model_key') != snapshot['model_key']
            or answer.get('model_revision') != snapshot['model_revision']
            or (snapshot['duration_seconds'] and any(
                clip.get('duration_seconds') != snapshot['duration_seconds']
                for clip in answer.get('clips', [])))):
        raise ValueError('video_settings_mismatch')
