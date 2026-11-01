"""Validate a review connection by transport and model capabilities, not agent role."""
from functools import lru_cache
from time import time
from typing import Any

from asa.config import Settings
from asa.registry.model_catalog import effective_settings, validate_selection
from asa.registry.model_discovery import ModelMetadata, Provider, metadata
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError


@lru_cache(maxsize=128)
def image_metadata(provider: Provider, model: str, bucket: int) -> ModelMetadata:
    return metadata(provider, model)


def validate_review_model(config: Settings, definition: dict[str, Any]) -> ModelMetadata:
    provider = definition.get("provider") or config.ai_provider
    model = definition.get("model") or config.ai_model
    validate_selection(config, provider, model)
    if not model:
        raise RegistryError(422, "invalid_model_selection")
    info = image_metadata(provider, model, int(time() // 300))
    if info.image_input_supported is not True:
        code = ("review_model_image_unsupported" if info.image_input_supported is False
                else "review_model_image_unknown")
        raise RegistryError(422, code)
    return info


def connection_status(repo: RegistryRepository, settings: Settings, ref: str) -> dict[str, Any]:
    parts = ref.split(":")
    if len(parts) != 3 or parts[0] != "agent" or not parts[2].isdigit():
        raise RegistryError(422, "review_not_configured")
    with repo._connect() as conn:
        row = conn.execute(
            "SELECT definition FROM registry_versions WHERE workspace_id=%s "
            "AND agent_id::text=%s ORDER BY version DESC LIMIT 1",
            (repo.workspace_id, parts[1]),
        ).fetchone()
        if not row:
            raise RegistryError(404, "tool_not_found")
        definition = row["definition"]
        if definition.get("tools"):
            raise RegistryError(422, "review_tools_unsupported")
        config = effective_settings(settings.model_copy(update={"workspace_id": repo.workspace_id}),
                                    conn)
    info = validate_review_model(config, definition)
    return {"compatible": True, "image_input": "generated_image_and_character_settings",
            "provider": definition.get("provider") or config.ai_provider,
            "model": definition.get("model") or config.ai_model,
            "checked_at": info.checked_at, "sources": info.sources}
