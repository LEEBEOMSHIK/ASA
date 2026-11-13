"""Scene answer adapter for the shared image queue. Never rewrites source material."""

import json
import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from asa.registry.schemas import RegistryError


class Shot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_id: str = Field(min_length=1, max_length=100)
    shot_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    source_excerpt: str = Field(max_length=2000)
    character_ids: list[str] = Field(max_length=12)
    reference_image_ids: list[str] = Field(max_length=12)
    composition: str = Field(max_length=2500)
    image_prompt: str = Field(min_length=1, max_length=4000)
    continuity: str = Field(max_length=2000)
    video_notes: str = Field(max_length=1000)
    review_notes: str = Field(max_length=1500)
    ready: bool


class ScenePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(max_length=2000)
    shots: list[Shot] = Field(min_length=1, max_length=100)
    checks: list[str] = Field(max_length=100)

    @model_validator(mode="after")
    def unique(self) -> "ScenePlan":
        keys = [(s.scene_id, s.shot_id) for s in self.shots]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate_scene_shot")
        return self


def items(plan: ScenePlan) -> list[dict[str, Any]]:
    return [
        dict(
            id=f"scene_{n}",
            name=s.title[:100],
            facts=s.source_excerpt,
            appearance=s.composition or s.title,
            proposed=s.continuity,
            scene_ids=s.scene_id,
            image_prompt=s.image_prompt,
        )
        for n, s in enumerate(plan.shots, 1)
    ]


def characters(value: Any) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("format") in ("asa_character_selection_v1", "asa_character_handoff_v1"):
                for c in node.get("characters", []):
                    result[c["id"]] = c
            else:
                for child in node.values():
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return list(result.values())


def readiness(context: dict[str, Any]) -> dict[str, list[str]]:
    available = {c["id"]: c for c in characters(context["input"])}
    problems = {}
    for n, shot in enumerate(context["plan"]["shots"], 1):
        notes = []
        missing = [cid for cid in shot["character_ids"] if cid not in available]
        if missing:
            notes.append("기준 이미지가 없는 캐릭터: " + ", ".join(missing))
        allowed = {c["image_id"] for c in available.values()}
        if set(shot["reference_image_ids"]) - allowed:
            notes.append(
                "요청에 선택하지 않은 참조 이미지가 있습니다. 이미지 연결을 확인해 주세요."
            )
        # AI readiness/continuity opinions are advisory; only reference validation blocks.
        problems[f"scene_{n}"] = notes
    return problems


def source_views(context: dict[str, Any]) -> dict[str, Any]:
    """Read-only source slices; never present generated prose as original material."""
    source = context["input"]
    script = source.get("script", "")
    scenes = source.get("scenes", "")
    script = script if isinstance(script, str) else json.dumps(script, ensure_ascii=False)
    scenes = scenes if isinstance(scenes, str) else json.dumps(scenes, ensure_ascii=False)
    headings = list(re.finditer(r"(?m)^#{1,6}\s+(?:장면\s*|씬\s*)?(\d+)[.\s:：]", scenes))
    available = {c["id"]: c for c in characters(source)}
    result = {}
    for n, shot in enumerate(context["plan"]["shots"], 1):
        number = re.fullmatch(r"(?:scene[_ -]?|장면\s*|씬\s*)?(\d+)", shot["scene_id"], re.I)
        matches = [i for i, h in enumerate(headings) if number and int(h[1]) == int(number[1])]
        scene_text = ""
        if len(matches) == 1:
            i = matches[0]
            scene_text = scenes[
                headings[i].start() : headings[i + 1].start()
                if i + 1 < len(headings)
                else len(scenes)
            ]
        excerpt = shot.get("source_excerpt", "")
        # Prefer the original scene's explicit script anchors over the AI's shorter excerpt.
        anchor_line = next((line for line in scene_text.splitlines() if "대응 대본" in line), "")
        anchors = re.findall(r'[“"]([^”"\n]+)[”"]', anchor_line)
        if len(anchors) == 2 and all(script.count(a) == 1 for a in anchors):
            start, end = script.index(anchors[0]), script.index(anchors[1])
            if end >= start:
                excerpt = script[start : end + len(anchors[1])]
        exact = bool(excerpt and excerpt in script)
        result[f"scene_{n}"] = {
            "script": excerpt if exact else script,
            "script_matched": exact,
            "scene": scene_text or scenes,
            "scene_matched": bool(scene_text),
            "characters": [
                {
                    "id": cid,
                    "name": available.get(cid, {}).get("name", cid),
                    "image_id": available.get(cid, {}).get("image_id"),
                    "role": "cast" if cid in shot["character_ids"] else "reference_only",
                }
                for cid in dict.fromkeys(
                    [
                        *shot["character_ids"],
                        *[
                            c["id"]
                            for c in available.values()
                            if c.get("image_id") in shot.get("reference_image_ids", [])
                        ],
                    ]
                )
            ],
        }
    return result


def resolve_references(
    repo: Any,
    refs: list[dict[str, Any]],
    overrides: dict[str, UUID],
) -> dict[str, Any]:
    """Resolve a scene-local choice without changing the character's approved baseline."""
    from asa.registry.character_library import SELECTION_FORMAT, versions

    if set(overrides) - {c["id"] for c in refs}:
        raise RegistryError(422, "scene_reference_override_invalid")
    resolved = []
    for ref in refs:
        # The server derives the allowed project/character from the original input image.
        choices = versions(repo, UUID(ref["image_id"]))
        if not choices or any(c["state"] == "excluded" for c in choices):
            raise RegistryError(409, "scene_reference_unavailable")
        chosen = next(
            (
                c
                for c in choices
                if (
                    c["id"] == str(overrides[ref["id"]])
                    if ref["id"] in overrides
                    else c["id"] == ref["image_id"]
                )
            ),
            None,
        )
        if chosen is None or chosen["character_id"] != ref["id"] or not chosen["confirmed"]:
            raise RegistryError(422, "scene_reference_override_invalid")
        resolved.append(
            {
                **chosen["character"],
                "image_id": chosen["id"],
                "image_change": chosen.get("image_change", ""),
                "image_version": chosen["version"],
                "project_id": chosen["project_id"],
                "source_request_id": chosen["request_id"],
                "source_version": chosen["source_version"],
                "selection": "scene_override" if ref["id"] in overrides else "approved_default",
            }
        )
    return {"format": SELECTION_FORMAT, "characters": resolved}


def snapshot(
    repo: Any,
    context: dict[str, Any],
    item_id: str,
    overrides: dict[str, UUID] | None = None,
) -> dict[str, Any]:
    if readiness(context).get(item_id, ["unknown"]):
        raise RegistryError(409, "scene_references_not_ready")
    shot = context["plan"]["shots"][int(item_id.split("_")[1]) - 1]
    # Cast identity references and non-cast prop/style references are distinct roles.
    refs = [
        c
        for c in characters(context["input"])
        if c["id"] in shot["character_ids"] or c["image_id"] in shot["reference_image_ids"]
    ]
    current = resolve_references(repo, refs, overrides or {})
    return {
        "shot": shot,
        "references": current,
        "reference_overrides": {k: str(v) for k, v in (overrides or {}).items()},
        "reference_roles": [
            {
                "image_id": c["image_id"],
                "character_id": c["id"],
                "role": "cast" if c["id"] in shot["character_ids"] else "reference_only",
            }
            for c in current["characters"]
        ],
        "aspect_ratio": context["input"].get("aspect_ratio", "9:16"),
        "source_input": context["input"],
    }


def reference_bytes(repo: Any, snapshot: dict[str, Any]) -> list[bytes]:
    # Only server-validated, persisted generation snapshots enter this internal loader.
    # Do not re-resolve current approvals: a later approval must not change a queued job.
    images = []
    with repo._connect() as conn:
        for ref in snapshot["references"]["characters"]:
            row = conn.execute(
                "SELECT image FROM character_image_jobs WHERE workspace_id=%s AND id=%s "
                "AND status='succeeded' AND image IS NOT NULL UNION ALL "
                "SELECT image FROM character_reference_uploads WHERE workspace_id=%s AND id=%s",
                (
                    repo.workspace_id,
                    UUID(ref["image_id"]),
                    repo.workspace_id,
                    UUID(ref["image_id"]),
                ),
            ).fetchone()
            if not row or not row["image"]:
                raise RegistryError(409, "character_handoff_image_missing")
            images.append(bytes(row["image"]))
    return images


def prompt(snapshot: dict[str, Any], settings: dict[str, Any], change: str) -> str:
    return (
        "Create ONE finished scene still, NOT a character sheet or collage. "
        "Follow the scene composition and original script. Preserve the identities, clothing "
        "in the attached character references. If a WORK ART STYLE POLICY is supplied, "
        "re-render references in its category and style rather than copying their rendering. "
        "Otherwise preserve reference style. Each reference is identified in order "
        "by references.characters below. reference_roles distinguishes cast from reference_only. "
        "Never depict a reference_only character merely because its image is attached. "
        "Use it only for the props, clothing, shapes or style required by the scene. "
        "Story transfers of a prop between characters preserve the same prop identity; "
        "do not treat a change of owner as a conflict. Follow the original script and scene. "
        "If a base scene is attached it is the FIRST image; "
        "apply only requested changes to that scene, preserving other content. "
        "Use current_scene_settings as the edited composition/prompt; never rewrite the script. "
        "The resolved references and their image_change/settings take precedence over older "
        "reference versions in source_input; keep the original script and scene unchanged. "
        "No watermark. Render only text explicitly required by the scene.\n"
        + json.dumps(
            {**snapshot, "current_scene_settings": settings, "requested_change": change},
            ensure_ascii=False,
        )
    )
