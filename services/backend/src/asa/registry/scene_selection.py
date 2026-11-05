"""Verified scene image snapshots for video prompt inputs."""

import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from asa.registry.schemas import RegistryError

FORMAT = "asa_scene_selection_v1"


class SceneSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_ids: list[UUID] = Field(min_length=1, max_length=32)
    version_overrides: dict[UUID, UUID] = Field(default_factory=dict, max_length=32)


def selected_scenes(
    repo: Any, image_ids: list[UUID], version_overrides: dict[UUID, UUID] | None = None
) -> dict[str, Any]:
    from asa.registry.characters import CharacterRepository

    if not 1 <= len(image_ids) <= 32 or len(set(image_ids)) != len(image_ids):
        raise RegistryError(422, "scene_selection_invalid")
    overrides = version_overrides or {}
    if not set(overrides).issubset(image_ids):
        raise RegistryError(422, "scene_selection_invalid")
    if any(base != selected for base, selected in overrides.items()):
        raise RegistryError(422, "scene_single_confirmed_version_required")
    requested = list(set(image_ids))
    source = CharacterRepository(repo.dsn, repo.workspace_id)
    with source._connect() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        rows = conn.execute(
            "SELECT id,project_id,character_id,scene_context FROM "
            "character_image_jobs WHERE workspace_id=%s AND id=ANY(%s) "
            "AND status='succeeded' AND image IS NOT NULL",
            (repo.workspace_id, requested),
        ).fetchall()
        indexed = {row["id"]: row for row in rows}
        if len(indexed) != len(requested):
            raise RegistryError(404, "scene_selection_missing")
        projects = {r["project_id"]: source.project(r["project_id"], conn) for r in rows}
        scenes = []
        for image_id in image_ids:
            row = indexed[image_id]
            project = projects[row["project_id"]]
            cid = row["character_id"]
            state = next(
                (i["state"] for i in project["work_progress"]["items"] if i["id"] == cid), None
            )
            if project["kind"] != "scene" or not row["scene_context"]:
                raise RegistryError(422, "scene_selection_invalid")
            if state != "approved" or project["approved"].get(cid) != str(image_id):
                raise RegistryError(409, "scene_selection_not_ready")
            job = next(j for j in project["jobs"] if j["id"] == str(image_id))
            context = row["scene_context"]
            scenes.append(
                {
                    "id": cid,
                    "name": job["character"]["name"],
                    "image_id": str(image_id),
                    "image_version": job["version"],
                    "image_change": job["change"],
                    "scene_id": context["shot"]["scene_id"],
                    "shot_id": context["shot"]["shot_id"],
                    "settings": json.dumps(job["character"], ensure_ascii=False),
                    "scene_plan": json.dumps(context["shot"], ensure_ascii=False),
                    "aspect_ratio": context["aspect_ratio"],
                    "character_count": len(context["references"]["characters"]),
                    "character_settings": json.dumps(
                        context["references"]["characters"], ensure_ascii=False
                    ),
                    "reference_roles": json.dumps(
                        context.get("reference_roles", []), ensure_ascii=False
                    ),
                    "project_id": project["id"],
                    "source_request_id": project["request_id"],
                    "source_version": project["source_version"],
                }
            )
    return {"format": FORMAT, "scenes": scenes}
