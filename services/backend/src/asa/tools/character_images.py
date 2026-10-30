"""Image API adapter; no automatic retries, no remote image fetching."""

import base64
import hashlib
import json
from decimal import Decimal
from typing import Any, cast

from openai import OpenAI

from asa.config import Settings

# Official Images pricing verified 2026-10-30. USD / million tokens.
IMAGE_RATES = {"text_input": "5", "image_input": "8", "image_output": "30"}


def image_cost(usage: Any, rates: dict[str, str] | None = None) -> Decimal | None:
    if not isinstance(usage, dict):
        return None
    details = usage.get("input_tokens_details") or {}
    numbers = [
        usage.get("input_tokens"),
        usage.get("output_tokens"),
        details.get("text_tokens"),
        details.get("image_tokens"),
    ]
    if any(type(n) is not int or n < 0 for n in numbers):
        return None
    incoming, outgoing, text, image = cast(list[int], numbers)
    if incoming != text + image:
        return None
    out_details = usage.get("output_tokens_details") or {}
    if out_details.get("text_tokens", 0) or out_details.get("image_tokens", outgoing) != outgoing:
        return None
    r = rates or IMAGE_RATES
    return (
        text * Decimal(r["text_input"])
        + image * Decimal(r["image_input"])
        + outgoing * Decimal(r["image_output"])
    ) / Decimal(1_000_000)


def image_prompt(character: dict[str, Any], change: str) -> str:
    if not character.get("name") or not character.get("appearance"):
        raise ValueError("character_definition_required")
    return (
        "Create one character reference sheet, clean background, full body and face detail. "
        "Only this character. No captions or watermarks. Follow the character specification. "
        "If a reference image is supplied, preserve its face, proportions, style and clothes "
        "except the explicitly requested change. Do not invent unrelated changes.\n"
        + json.dumps(character, ensure_ascii=False)
        + (
            "\nRequested change (takes precedence only for changed attributes): " + change
            if change
            else ""
        )
    )


def generate_image(
    settings: Settings, model: str, prompt: str, reference: bytes | None
) -> tuple[bytes, dict[str, Any] | None]:
    client: Any = OpenAI(
        api_key=settings.ai_api_key.get_secret_value(),
        timeout=settings.image_timeout_seconds,
        max_retries=0,
    )
    args = dict(
        model=model,
        prompt=prompt,
        n=1,
        size="1024x1024",
        quality="medium",
        output_format="png",
        safety_identifier=hashlib.sha256(str(settings.workspace_id).encode()).hexdigest(),
    )
    try:
        result = (
            client.images.edit(image=("reference.png", reference, "image/png"), **args)
            if reference
            else client.images.generate(**args)
        )
        if not result.data or not result.data[0].b64_json:
            raise ValueError("image_missing")
        image = base64.b64decode(result.data[0].b64_json, validate=True)
        if not image.startswith(b"\x89PNG\r\n\x1a\n") or len(image) > 20_000_000:
            raise ValueError("invalid_image_output")
        return image, result.usage.model_dump() if result.usage else None
    finally:
        client.close()
