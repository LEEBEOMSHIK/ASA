"""Read-only grouping; every original item stays addressable by its existing ID."""

import json
from typing import Any

from asa.registry.library_lineage import fingerprint


def visible_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [i for i in items if not i.get("duplicate_of") and not i.get("parent_scene_id")]


def annotate(
    items: list[dict[str, Any]],
    contents: dict[str, Any],
    requests: list[dict[str, Any]],
    scene_projects: set[tuple[str, int]],
) -> None:
    sources = {r["id"]: r.get("input") or {} for r in requests}
    groups: dict[tuple[str, str, str | None], str] = {}
    for item in items:
        for key in ("duplicate_of", "parent_scene_id", "is_scene_plan"):
            item.pop(key, None)
        item.update(related_count=0, duplicate_count=1)
    automated = sorted(
        (i for i in items if i["id"].startswith("automation:")),
        key=lambda i: (i["id"].split(":")[1], int(i["id"].split(":")[2])),
    )
    for item in automated:
        body = contents.get(item["id"])
        if body in (None, "", {}, []):
            continue
        group_key = (
            item["id"].split(":")[1], json.dumps(body, sort_keys=True), item.get("work_id")
        )
        if group_key in groups:
            item["duplicate_of"] = groups[group_key]
        else:
            groups[group_key] = item["id"]
    by_id = {i["id"]: i for i in items}
    for item in items:
        if item.get("duplicate_of"):
            by_id[item["duplicate_of"]]["duplicate_count"] += 1
        rid = item.get("request_id")
        body = contents.get(item["id"])
        inputs = sources.get(rid, {})
        if item["kind"] == "scene" and (
            (rid, item.get("answer_version")) in scene_projects
            or (isinstance(body, dict) and "shots" in body and "scenes" in inputs)
        ):
            item["is_scene_plan"] = True
    for plan in items:
        if not plan.get("is_scene_plan") or not plan.get("work_id"):
            continue
        key = fingerprint(sources.get(plan.get("request_id"), {}).get("scenes"))
        if not key:
            continue
        matches: set[str] = set()
        for scene in items:
            if scene["kind"] != "scene" or scene.get("is_scene_plan"):
                continue
            if scene.get("work_id") != plan["work_id"]:
                continue
            body = contents.get(scene["id"])
            values = [body, *(body.values() if isinstance(body, dict) else [])]
            if any(fingerprint(value) == key for value in values):
                matches.add(scene.get("duplicate_of") or scene["id"])
        if len(matches) == 1:
            parent = matches.pop()
            plan["parent_scene_id"] = parent
            by_id[parent]["related_count"] += 1
