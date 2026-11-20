"""Higgsfield upload and request contracts; never follows provider/storage redirects."""
import ipaddress
import math
import socket
from typing import Any
from urllib.parse import urlsplit

import httpx

from asa.config import Settings

API = "https://api.higgsfield.ai"
MODEL = "alibaba/wan-3.0"


def safe_media_url(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid_media_url")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in (None, 443) or parsed.fragment):
        raise ValueError("invalid_media_url")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("invalid_media_url")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError("invalid_media_url")
    return value


def upload_media(settings: Settings, model: dict[str, Any], data: bytes, content_type: str) -> str:
    from asa.video_providers import provider_connection
    if model.get("provider") != "higgsfield" or content_type not in {
        "image/png", "audio/wav", "video/mp4"
    } or not data or len(data) > 64 * 1024 * 1024:
        raise ValueError("video_reference_media_invalid")
    base, headers = provider_connection(settings, model)
    with httpx.Client(timeout=90, follow_redirects=False, trust_env=False) as client:
        response = client.post(base + "/files/generate-upload-url", headers=headers,
                               json={"content_type": content_type})
        response.raise_for_status()
        ticket = response.json()
    upload_url = safe_media_url(ticket["upload_url"])
    public_url = safe_media_url(ticket["public_url"])
    # Resolve before sending bytes, rejecting private/network-local destinations.
    host = urlsplit(upload_url).hostname
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("invalid_media_url")
    upload_headers = ticket.get("upload_headers")
    if not isinstance(upload_headers, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) or "\r" in k + v or "\n" in k + v
        or k.lower() in {"authorization", "cookie", "host", "proxy-authorization"}
        for k, v in upload_headers.items()
    ):
        raise ValueError("invalid_upload_headers")
    # New client intentionally carries neither the API key nor API cookies/default headers.
    with httpx.Client(timeout=90, follow_redirects=False, trust_env=False) as storage:
        response = storage.put(upload_url, headers=upload_headers, content=data)
        response.raise_for_status()
    return public_url


def request_body(spec: dict[str, Any], start_image_url: str | None,
                 reference_media: list[dict[str, str]] | None = None,
                 *, model: str = MODEL) -> tuple[str, dict[str, Any]]:
    from asa.higgsfield_models import validate_spec
    validate_spec({"model": model, "resolution": spec["resolution"]}, spec)
    image = safe_media_url(start_image_url)
    body: dict[str, Any] = {"prompt": spec["prompt"], "duration": spec["duration_seconds"],
                            "resolution": spec["resolution"], "aspect_ratio": spec["aspect_ratio"],
                            "generate_audio": spec["audio"], "enable_thinking": False}
    if model != MODEL:
        body.pop("enable_thinking")
    if model == "kling-video/v4.0":
        body.pop("generate_audio")
    refs = spec.get("reference_inputs")
    if refs is None:
        if reference_media:
            raise ValueError("video_reference_media_invalid")
        if model != MODEL:
            body.pop("aspect_ratio")  # I2V framing is inherited from the start image.
        return model + "/image-to-video", {**body, "image_url": image}
    grouped: dict[str, list[str]] = {"reference_image": [image], "reference_audio": [],
                                   "reference_video": []}
    for media in reference_media or []:
        if media.get("type") not in grouped:
            raise ValueError("video_reference_media_invalid")
        grouped[media["type"]].append(safe_media_url(media["url"]))
    if (len(grouped["reference_image"]) != 1 + len(refs.get("character_image_ids", []))
            or len(grouped["reference_audio"]) != len(refs.get("audio", []))
            or len(grouped["reference_video"]) != len(refs.get("video", []))):
        raise ValueError("video_reference_media_missing")
    if (len(grouped["reference_image"]) > 10 or len(grouped["reference_audio"]) > 5
            or len(grouped["reference_video"]) > 5):
        raise ValueError("video_reference_media_limit")
    body["image_urls"] = grouped["reference_image"]
    if model != "kling-video/v4.0":
        body["audio_urls"] = grouped["reference_audio"]
    if grouped["reference_video"] or model == MODEL:
        body["video_urls"] = grouped["reference_video"]
    return model + "/reference-to-video", body


def estimate_request(client: httpx.Client, settings: Settings, model: dict[str, Any],
                     spec: dict[str, Any], start_image_url: str,
                     reference_media: list[dict[str, str]] | None = None) -> float:
    from asa.video_providers import generation_request
    url, headers, body = generation_request(settings, model, spec, b"",
                                            reference_media, start_image_url=start_image_url)
    response = client.post(API + "/estimate/" + url.removeprefix(API + "/"),
                           headers=headers, json=body, follow_redirects=False)
    response.raise_for_status()
    return estimate_usd(response.json())


def estimate_usd(data: Any) -> float:
    if not isinstance(data, dict) or isinstance(data.get("usd"), bool):
        raise ValueError("invalid_estimate")
    value = float(data["usd"])
    if not math.isfinite(value) or value < 0:
        raise ValueError("invalid_estimate")
    return value
