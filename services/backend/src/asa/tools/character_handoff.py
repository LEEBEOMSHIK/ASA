"""Explicit, workspace-scoped handoff of approved character image snapshots."""
from typing import Any
from uuid import UUID

from asa.registry.schemas import RegistryError

HANDOFF_ID = "asa.characters.approved:1"
FORMAT = "asa_character_handoff_v1"


def handoff(project: dict[str, Any]) -> dict[str, Any]:
    excluded = set(project["excluded"])
    states = {i["id"]: i["state"] for i in project["work_progress"]["items"]}
    characters = []
    for character in project["characters"]:
        cid = character["id"]
        if cid in excluded:
            continue
        job = next((j for j in project["jobs"]
                    if j["character_id"] == cid and j["id"] == project["approved"].get(cid)
                    and j["status"] == "succeeded"), None)
        if not job or states.get(cid) != "approved":
            raise RegistryError(409, "character_handoff_not_ready")
        # The confirmed image's immutable settings, never unsaved UI edits or plan defaults.
        characters.append({**job["character"], "image_id": job["id"],
                           "image_version": job["version"], "image_change": job["change"]})
    return {"format": FORMAT, "project_id": project["id"],
            "source_request_id": project["request_id"],
            "source_version": project["source_version"], "characters": characters}


def read_handoff(repo: Any, project_id: str) -> dict[str, Any]:
    from asa.registry.characters import CharacterRepository
    source = CharacterRepository(repo.dsn, repo.workspace_id)
    with source._connect() as conn:
        # Consistent read across approval, exclusions and image records.
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        return handoff(source.project(UUID(project_id), conn))


def handoff_tool() -> dict[str, Any]:
    props = {k: {"type": "string"} for k in (
        "id", "name", "facts", "appearance", "proposed", "scene_ids", "image_prompt",
        "image_id", "image_change")}
    props["image_version"] = {"type": "integer"}
    return {
        "id": HANDOFF_ID, "name": "확정 캐릭터 가져오기", "kind": "asa", "version": 1,
        "description": "사용하는 캐릭터의 확정 설정과 기준 이미지만 다음 단계에 전달합니다.",
        "usage": "캐릭터 결과의 프로젝트 ID를 입력하고 이 도구의 전체 결과를 다음 AI 입력에 "
                 "연결하세요. 필요한 캐릭터가 모두 확정되어야 실행됩니다. 대본·장면은 별도로 "
                 "원문을 연결하세요. 이미지 입력 지원 모델이 필요합니다.",
        "available": True, "execution_available": True, "dependencies": [],
        "side_effect": "read", "cost": "free", "unavailable_reason": "",
        "input_schema": {"type": "object", "properties": {
            "project_id": {"type": "string", "description": "캐릭터 결과의 프로젝트 ID"}},
            "required": ["project_id"]},
        "output_schema": {"type": "object", "properties": {
            "format": {"type": "string"}, "project_id": {"type": "string"},
            "source_request_id": {"type": "string"}, "source_version": {"type": "integer"},
            "characters": {"type": "array", "maxItems": 12,
                           "items": {"type": "object", "properties": props}}}},
    }


def image_content(repo: Any, value: Any) -> list[dict[str, Any]]:
    """Attach assets only for explicit handoff envelopes; never fetch arbitrary URLs."""
    import base64
    images: dict[str, dict[str, Any]] = {}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("format") == FORMAT:
                # Revalidate against the source so forged/excluded/unconfirmed data cannot pass.
                current = read_handoff(repo, node["project_id"])
                if node != current:
                    raise RegistryError(409, "character_handoff_changed")
                for char in current["characters"]:
                    images[char["image_id"]] = char
            else:
                for child in node.values():
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    if len(images) > 12:
        raise RegistryError(422, "character_handoff_image_limit")
    if not images:
        return []
    content: list[dict[str, Any]] = []
    with repo._connect() as conn:
        for image_id, char in images.items():
            row = conn.execute(
                "SELECT image FROM character_image_jobs WHERE workspace_id=%s "
                "AND id=%s AND status='succeeded'", (repo.workspace_id, UUID(image_id)),
            ).fetchone()
            if not row or not row["image"]:
                raise RegistryError(409, "character_handoff_image_missing")
            content.extend([
                {"type": "text", "text": f"캐릭터 {char['name']} ({char['id']}) "
                 f"확정 기준 이미지 v{char['image_version']}"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," +
                 base64.b64encode(bytes(row["image"])).decode()}},
            ])
    return content
