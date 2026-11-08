"""Conservative, read-only provenance recovery for saved production inputs."""

import json
from collections import defaultdict
from typing import Any


def fingerprint(value: Any) -> str:
    if isinstance(value, str):
        value = value.strip()
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            pass
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    # A title, a shared short direction, or an empty template is not provenance.
    return value if len(value) >= 80 else ""


def production_roots(
    requests: list[dict[str, Any]], answers: list[dict[str, Any]]
) -> dict[str, str | None]:
    known = {r["id"] for r in requests}
    owners: dict[str, set[str]] = defaultdict(set)
    for answer in answers:
        rid = answer["request_id"]
        if rid not in known:
            continue
        body = answer["answer"]
        values = [body, *(body.values() if isinstance(body, dict) else [])]
        for value in values:
            if key := fingerprint(value):
                owners[key].add(rid)
    parents: dict[str, set[str]] = defaultdict(set)
    for request in requests:
        current = request["id"]
        props = (request.get("schema") or {}).get("properties", {})
        for field, value in (request.get("input") or {}).items():
            if field not in {"script", "scenes"} and not props.get(field, {}).get(
                "x-previous-answer"
            ):
                continue
            # Image/character references can be shared between unrelated stories.
            if not isinstance(value, str):
                continue
            parents[current].update(owners.get(fingerprint(value), set()) - {current})
        # A retry can change its source story. Its current inputs take precedence
        # over the old request used to prefill the form.
        if not parents[current] and request.get("source_id") in known:
            parents[current].add(request["source_id"])
    resolved: dict[str, str | None] = {}

    def resolve(node: str, path: set[str]) -> str | None:
        if node in resolved:
            return resolved[node]
        if node in path:
            return None
        upstream = parents[node]
        if not upstream:
            resolved[node] = node
        else:
            roots = {resolve(parent, path | {node}) for parent in upstream}
            resolved[node] = next(iter(roots)) if len(roots) == 1 and None not in roots else None
        return resolved[node]

    return {request["id"]: resolve(request["id"], set()) for request in requests}
