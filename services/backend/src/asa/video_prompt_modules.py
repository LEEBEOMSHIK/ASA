"""Versioned, opt-in video direction modules; no model calls or user-path loading."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MediaType = Literal["animation_2d", "animation_3d", "live_action"]


class VideoPromptModules(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool = False
    editor_managed: bool = False
    selection_required: bool = False
    common_instructions: str = Field(default="", max_length=65536)
    style_instructions: dict[MediaType, Annotated[str, Field(max_length=65536)]] = Field(
        default_factory=dict
    )
    mode: Literal["auto", "manual"] = "auto"
    profile_id: MediaType | None = None
    # Field names refer to registered agent inputs, never filesystem paths.
    user_style_field: str | None = Field(default=None, min_length=1, max_length=100)
    confirmed_style_field: str | None = Field(default=None, min_length=1, max_length=100)
    reference_style_field: str | None = Field(default=None, min_length=1, max_length=100)
    metadata_style_field: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def always_select_style(self) -> "VideoPromptModules":
        if self.selection_required:
            self.enabled = True
            self.editor_managed = True
            self.mode = "auto"
            self.profile_id = None
            self.user_style_field = "video_style"
            self.confirmed_style_field = None
            self.reference_style_field = None
            self.metadata_style_field = None
        return self


def normalize_video_definition(value: dict[str, Any]) -> dict[str, Any]:
    """Default video prompt settings on edit/save, never mutate queued definitions."""
    config = value.get("video_prompt_modules") or {}
    schema = value.get("input_schema") or {}
    props = schema.get("properties") if isinstance(schema, dict) else None
    video = isinstance(props, dict) and any(
        isinstance(node, dict) and node.get("x-video-model") is True for node in props.values()
    )
    if not isinstance(config, dict) or not (video or config.get("editor_managed")):
        return value
    if not isinstance(props, dict) or schema.get("type") != "object":
        return value  # Ordinary schema validation supplies the field error.
    style = {"type": "string", "description": "영상 스타일", "x-widget": "select",
             "enum": ["animation_2d", "animation_3d", "live_action"]}
    existing = props.get("video_style")
    if existing is not None and (
        not isinstance(existing, dict) or existing.get("type") != "string"
        or existing.get("enum") != style["enum"]
    ):
        raise ValueError(
            "video_style 항목은 영상 스타일 선택용입니다. 기존 항목 이름을 변경하세요."
        )
    required = schema.get("required", [])
    if not isinstance(required, list) or any(not isinstance(key, str) for key in required):
        return value
    return {**value, "video_prompt_modules": {**config, "selection_required": True},
            "input_schema": {**schema, "properties": {**props, "video_style": style},
                             "required": list(dict.fromkeys([*required, "video_style"]))}}


@dataclass(frozen=True)
class Module:
    profile_id: str
    version: str
    display_name: str
    media_type: str | None
    instruction_source: str
    enabled: bool = False
    compatible_modes: tuple[str, ...] = ("text_to_video", "image_to_video")
    selection_priority: int = 0
    description: str = ""


# Trusted deployment registry. Instruction bodies must be supplied and reviewed before enabling.
MODULE_ROOT = Path(__file__).parent / "prompt_modules"
REGISTRY = (
    Module("common", "pending", "공통 연출 지침", None, "director.md"),
    Module("animation_2d", "pending", "2D 애니메이션", "animation_2d", "animation-2d.md"),
    Module("animation_3d", "pending", "3D 애니메이션", "animation_3d", "animation-3d.md"),
    Module("live_action", "pending", "실사", "live_action", "live-action.md"),
)
MEDIA_TYPES = frozenset({"animation_2d", "animation_3d", "live_action"})


def _media(value: Any) -> str | None:
    # Only explicit structured metadata is accepted. "cinematic"/"film" isn't live action.
    if isinstance(value, dict):
        value = value.get("media_type")
    return value if isinstance(value, str) and value in MEDIA_TYPES else None


def _load(module: Module, root: Path) -> str:
    base = root.resolve()
    path = (base / module.instruction_source).resolve()
    if not path.is_relative_to(base) or path.suffix != ".md":
        raise ValueError("module_source_not_allowed")
    body = path.read_text(encoding="utf-8").strip()
    if not body or len(body) > 131072:
        raise ValueError("module_body_invalid")
    return body


def build_prompt_bundle(
    definition: dict[str, Any],
    inputs: Any,
    *,
    registry: tuple[Module, ...] = REGISTRY,
    root: Path = MODULE_ROOT,
    catalog: dict[str, Any] | None = None,
    work_media_type: MediaType | None = None,
) -> dict[str, Any]:
    """Freeze composition at enqueue time, so retries never read newer module bodies."""
    config = VideoPromptModules.model_validate(definition.get("video_prompt_modules") or {})
    if work_media_type:
        config = config.model_copy(update={"enabled": True, "mode": "auto", "profile_id": None})
    # Agent schemas may accept scalar or array roots, which have no mapped fields.
    style_inputs = inputs if isinstance(inputs, dict) else {}
    warnings: list[str] = []
    candidates: list[tuple[str, str]] = []
    if work_media_type:
        candidates.append(("work", work_media_type))
    if config.enabled:
        if config.mode == "manual" and config.profile_id:
            candidates.append(("manual", config.profile_id))
        for source, field in (
            ("user", config.user_style_field),
            ("confirmed", config.confirmed_style_field),
            ("reference", config.reference_style_field),
            ("metadata", config.metadata_style_field),
        ):
            media = _media(style_inputs.get(field)) if field else None
            if media:
                candidates.append((source, media))
        if config.mode == "manual" and not config.profile_id:
            warnings.append("manual_profile_missing")
            candidates = []
    chosen = candidates[0][1] if candidates else None
    if config.selection_required and not chosen:
        from asa.registry.schemas import RegistryError
        raise RegistryError(422, "video_style_required")
    if config.enabled and not chosen:
        warnings.append("media_type_unresolved")
    conflicts = [{"source": source, "media_type": media} for source, media in candidates
                 if media != chosen]
    if conflicts:
        warnings.append("style_conflict_review_required")
    selected: list[dict[str, Any]] = []
    bodies: list[str] = []
    frozen = catalog if catalog is not None else freeze_module_catalog(
        definition, registry=registry, root=root
    )
    if config.selection_required and not frozen.get(chosen or "", {}).get("body", "").strip():
        from asa.registry.schemas import RegistryError
        raise RegistryError(422, "video_style_instructions_missing")
    if config.enabled:
        for profile_id in ["common", *([chosen] if chosen else [])]:
            entry = frozen.get(profile_id)
            if entry is None:
                warnings.append(f"module_unavailable:{profile_id}")
                continue
            if not entry.get("body"):
                warnings.append(f"module_body_unavailable:{profile_id}")
                continue
            body = entry["body"]
            selected.append({"profile_id": profile_id, "version": entry["version"],
                             "sha256": entry["sha256"]})
            bodies.append(body)
    # A specialist must never run without the shared contract. Preserve legacy behavior.
    if not any(item["profile_id"] == "common" for item in selected):
        selected, bodies = [], []
    common_from_agent = (frozen.get("common", {}).get("source") == "agent_instructions")
    instructions = "\n\n".join(
        bodies if selected and common_from_agent else [*bodies, definition["instructions"]]
    )
    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "enabled": config.enabled,
        "media_type": chosen,
        "selection_source": candidates[0][0] if candidates else None,
        "selection_mode": config.mode,
        "style_profile_ids": [item["profile_id"] for item in selected],
        "modules": selected,
        "conflicts": conflicts,
        "warnings": warnings,
        "fallback": not bool(selected),
        "instructions": instructions,
    }
    canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    snapshot["prompt_bundle_version"] = hashlib.sha256(canonical.encode()).hexdigest()
    return snapshot


def bundled_instructions(contract: dict[str, Any]) -> str:
    """Old queued requests remain executable; new ones use their immutable snapshot."""
    bundle = contract.get("video_prompt_bundle")
    if isinstance(bundle, dict) and isinstance(bundle.get("instructions"), str):
        return str(bundle["instructions"])
    if "agent_instructions" in contract:
        return str(contract["agent_instructions"])
    return str(contract["definition"]["instructions"])


def freeze_module_catalog(
    definition: dict[str, Any],
    *,
    registry: tuple[Module, ...] = REGISTRY,
    root: Path = MODULE_ROOT,
) -> dict[str, Any]:
    """Capture trusted bodies before queueing; runtime input selects from this snapshot."""
    config = VideoPromptModules.model_validate(definition.get("video_prompt_modules") or {})
    if not config.enabled:
        return {}
    if config.editor_managed:
        bodies: dict[str, str] = {"common": definition["instructions"]}
        for style, instruction in config.style_instructions.items():
            bodies[style] = instruction
        return {
            key: {"version": hashlib.sha256(body.encode()).hexdigest(), "body": body,
                  "source": "agent_instructions" if key == "common" else "style_instructions",
                  "sha256": hashlib.sha256(body.encode()).hexdigest()}
            for key, body in bodies.items() if body.strip()
        }
    frozen: dict[str, Any] = {}
    for module in registry:
        if not module.enabled:
            continue
        try:
            body = _load(module, root)
        except (OSError, ValueError, UnicodeError):
            body = ""
        frozen[module.profile_id] = {
            "version": module.version, "body": body,
            "sha256": hashlib.sha256(body.encode()).hexdigest(),
        }
    return frozen


def prepare_video_prompt_tool(tool: dict[str, Any], value: Any) -> dict[str, Any]:
    """Legacy queued tools retain their original behavior without loading new files."""
    if "video_prompt_catalog" not in tool:
        return tool
    definition = tool["definition"]
    return {
        **tool,
        "video_prompt_bundle": build_prompt_bundle(
            definition, value if isinstance(value, dict) else {},
            catalog=tool["video_prompt_catalog"],
        ),
    }
