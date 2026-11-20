"""Explicit video provider contracts; no network access or credential exposure to UI."""

import base64
from typing import Any

from asa.config import Settings

RUNWAY_API = "https://api.dev.runwayml.com/v1"


def connection_state(settings: Settings, provider: str) -> str:
    if provider == "runway":
        return "configured" if settings.runway_api_key.get_secret_value() else "missing_key"
    if provider == "higgsfield":
        return "configured" if settings.higgsfield_api_key.get_secret_value() else "missing_key"
    if provider == "alibaba":
        if not settings.wan_api_key.get_secret_value():
            return "missing_key"
        return "configured" if settings.wan_workspace_id else "missing_workspace"
    return "unsupported"


def supported_model(model: dict[str, Any]) -> bool:
    from asa.higgsfield_models import RESOLUTION_RATES
    if model.get("provider") == "higgsfield":
        return model.get("resolution") in RESOLUTION_RATES.get(model.get("model", ""), {})
    return (model.get("provider"), model.get("model"), model.get("resolution")) in {
        ("higgsfield", "alibaba/wan-3.0", "720p"),
        ("runway", "gen4.5", "720p"),
        ("alibaba", "wan3.0-video", "720p"),
    }


def endpoint(settings: Settings, provider: str) -> str:
    if provider == "higgsfield":
        return "https://api.higgsfield.ai"
    if provider == "runway":
        return RUNWAY_API
    if provider == "alibaba" and settings.wan_workspace_id:
        return f"https://{settings.wan_workspace_id}.{settings.wan_region}.maas.aliyuncs.com/api/v1"
    raise ValueError("provider_configuration_missing")


def provider_connection(settings: Settings, model: dict[str, Any]) -> tuple[str, dict[str, str]]:
    provider = model["provider"]
    if provider == 'alibaba':
        from asa.wan_regions import REGIONS, regional_settings

        frozen = model.get('provider_endpoint')
        if frozen:
            candidates = [regional_settings(settings, region)
                          for region in dict.fromkeys([*REGIONS, settings.wan_region])]
            matches = [candidate for candidate in candidates if candidate.wan_workspace_id
                       and endpoint(candidate, provider) == frozen]
            if not matches:
                raise ValueError('endpoint_changed')
            settings = matches[0]
        else:
            settings = regional_settings(settings, settings.wan_region)
    if not supported_model(model) or connection_state(settings, provider) != "configured":
        raise ValueError("provider_configuration_missing")
    base = endpoint(settings, provider)
    if model.get("provider_endpoint", base) != base:
        raise ValueError("endpoint_changed")
    if provider == "higgsfield":
        return base, {"Authorization": f"Key {settings.higgsfield_api_key.get_secret_value()}"}
    token = settings.runway_api_key if provider == "runway" else settings.wan_api_key
    return base, {"Authorization": f"Bearer {token.get_secret_value()}"}


def validate_input(model: dict[str, Any], spec: dict[str, Any]) -> None:
    if not supported_model(model) or spec["resolution"] != model.get("resolution"):
        raise ValueError("video_model_unavailable")
    if spec["aspect_ratio"] not in {"9:16", "16:9"}:
        raise ValueError("video_aspect_ratio_unsupported")
    wan = model["provider"] in {"alibaba", "higgsfield"}
    if spec.get('reference_inputs') is not None and (
        not wan or spec.get('connection_type', 'cut') != 'cut'
    ):
        raise ValueError('video_reference_mode_unsupported')
    if model["provider"] == "higgsfield":
        from asa.higgsfield_models import validate_spec
        validate_spec(model, spec)
    duration = spec["duration_seconds"]
    if type(duration) is not int or duration not in (range(2, 31) if wan else [5, 10]):
        raise ValueError("video_duration_unsupported")
    if not wan and spec["audio"]:
        raise ValueError("video_audio_unsupported")
    if not spec["prompt"].strip() or len(spec["prompt"]) > (20000 if wan else 1000):
        raise ValueError("video_prompt_limit")


def generation_request(
    settings: Settings, model: dict[str, Any], spec: dict[str, Any], image: bytes,
    reference_media: list[dict[str, str]] | None = None,
    *, start_image_url: str | None = None,
) -> tuple[str, dict[str, str], dict[str, Any]]:
    validate_input(model, spec)
    base, headers = provider_connection(settings, model)
    if model["provider"] == "higgsfield":
        from asa.higgsfield_provider import request_body
        path, body = request_body(spec, start_image_url, reference_media, model=model["model"])
        return base + "/" + path, headers, body
    url = "data:image/png;base64," + base64.b64encode(image).decode("ascii")
    reference_mode = spec.get('reference_inputs') is not None
    media = [{'type': 'reference_image' if reference_mode else 'first_frame', 'url': url}]
    if reference_media:
        if not reference_mode or any(m.get('type') not in {
            'reference_image', 'reference_audio'} for m in reference_media):
            raise ValueError('video_reference_media_invalid')
        media.extend(reference_media)
    if sum(m['type'] == 'reference_image' for m in media) > 10 or sum(
        m['type'] == 'reference_audio' for m in media) > 5:
        raise ValueError('video_reference_media_limit')
    if reference_mode:
        refs = spec['reference_inputs']
        if (sum(m['type'] == 'reference_image' for m in media)
                != 1 + len(refs.get('character_image_ids', [])) or
                sum(m['type'] == 'reference_audio' for m in media)
                != len(refs.get('audio', []))):
            raise ValueError('video_reference_media_missing')
    if model["provider"] == "alibaba":
        return (
            base + "/services/aigc/video-generation/video-synthesis",
            {
                **headers,
                "X-DashScope-Async": "enable",
            },
            {
                "model": model["model"],
                "input": {"prompt": spec["prompt"], "media": media},
                "parameters": {
                    "resolution": "720P",
                    "ratio": spec["aspect_ratio"],
                    "duration": spec["duration_seconds"],
                    "audio": spec["audio"],
                    "prompt_extend": False,
                },
            },
        )
    return (
        base + "/image_to_video",
        {**headers, "X-Runway-Version": "2024-11-06"},
        {
            "model": model["model"],
            "promptText": spec["prompt"],
            "promptImage": url,
            "ratio": {"9:16": "720:1280", "16:9": "1280:720"}[spec["aspect_ratio"]],
            "duration": spec["duration_seconds"],
        },
    )


def task_result(provider: str, data: dict[str, Any]) -> tuple[str, str | None]:
    if provider == "higgsfield":
        statuses = {"queued": "PENDING", "in_progress": "RUNNING", "completed": "SUCCEEDED",
                    "failed": "FAILED", "nsfw": "FAILED", "canceled": "CANCELED"}
        status = statuses.get(data.get("status", ""))
        if status is None:
            raise ValueError("invalid_task_status")
        url = None
        if status == "SUCCEEDED":
            from asa.higgsfield_provider import safe_media_url
            url = safe_media_url(data["video"]["url"])
        return status, url
    result = data["output"] if provider == "alibaba" else data
    status = result["task_status"] if provider == "alibaba" else result["status"]
    if status not in {
        "PENDING",
        "THROTTLED",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELED",
        "CANCELLED",
        "UNKNOWN",
    }:
        raise ValueError("invalid_task_status")
    url = None
    if status == "SUCCEEDED":
        url = result["video_url"] if provider == "alibaba" else result["output"][0]
        if not isinstance(url, str):
            raise ValueError("invalid_video_url")
    return status, url
