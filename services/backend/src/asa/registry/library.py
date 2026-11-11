"""Read existing production records without copying media or changing approvals."""

from typing import Any
from uuid import UUID, uuid5

from asa.registry.library_excerpt import excerpt
from asa.registry.library_lineage import production_roots
from asa.registry.library_presentation import annotate, visible_items
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError
from asa.registry.work_titles import attach_titles, explicit_title

# The source picker intentionally restricts registered agents. The library also
# retains outputs from direct AI and built-in automation nodes.
AUTOMATION_ITEMS = """
 SELECT r.id::text,(s.ordinality-1)::int step_index,1 version,r.created_at::text,
 coalesce(s.step->>'label',s.step->>'id','자동화 결과') name,
 r.definition->>'name' automation_name,s.step->'output' answer
 FROM automation_runs r
 CROSS JOIN LATERAL jsonb_array_elements(r.steps) WITH ORDINALITY s(step,ordinality)
 WHERE r.workspace_id=%s AND s.step->>'status'='succeeded'
 AND s.step->'output' IS NOT NULL AND s.step->'output'<>'null'::jsonb
"""


def asset_category(item: dict[str, Any]) -> str:
    """Classify each stored artifact, independently of its originating agent."""
    if item["kind"] == "image":
        return {"character": "character_image", "scene": "scene_image"}.get(
            item["subtype"], "reference_image"
        )
    if item["kind"] == "audio":
        return "music" if item["subtype"] == "music" else "speech"
    return str(item["kind"])


def answer_kind(answer: Any, saved_agent_name: str = "") -> str:
    if not isinstance(answer, dict):
        return "document"
    for keys, kind in (
        ({"clips"}, "prompt"),
        ({"scenes", "shots"}, "scene"),
        ({"characters"}, "character"),
        ({"script", "narration"}, "script"),
    ):
        if keys.intersection(answer):
            return kind
    # Old text-only answers have no contract. Use the immutable saved role,
    # never today's editable agent name; unknown roles remain visible as documents.
    for token, kind in (
        ("비디오 프롬프트", "prompt"),
        ("장면", "scene"),
        ("씬", "scene"),
        ("캐릭터", "character"),
        ("대본", "script"),
    ):
        if token in saved_agent_name:
            return kind
    return "document"


def family_roots(rows: list[dict[str, Any]]) -> dict[str, str]:
    parents = {r["id"]: r.get("source_id") for r in rows}
    result: dict[str, str] = {}
    for key in parents:
        path: list[str] = []
        current = key
        while current not in result and current not in path:
            path.append(current)
            parent = parents.get(current)
            if parent not in parents:
                break
            current = parent
        root = result.get(current) or (
            min(path[path.index(current) :]) if parents.get(current) in path else current
        )
        result.update(dict.fromkeys(path, root))
    return result


def index(repo: RegistryRepository, user_id: str) -> dict[str, Any]:
    """Only metadata is indexed. Bodies and binary assets load on explicit detail."""
    wid = repo.workspace_id
    with repo._connect() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        requests = conn.execute(
            "SELECT r.id::text,r.source_id::text,r.input,r.created_at::text,"
            "v.definition->>'name' source_label,v.definition->'input_schema' schema "
            "FROM customer_requests r JOIN registry_versions v "
            "USING(workspace_id,agent_id,version) "
            "WHERE r.workspace_id=%s",
            (wid,),
        ).fetchall()
        attach_titles(conn, wid, user_id, requests)
        names = {r["id"]: r["display_title"] for r in requests}
        roots = family_roots(requests)
        answers = conn.execute(
            "SELECT request_id::text,coalesce(answer,jsonb_build_object('title',title,"
            "'narration',narration)) answer FROM script_versions WHERE workspace_id=%s",
            (wid,),
        ).fetchall()
        automation_sources = conn.execute(AUTOMATION_ITEMS, (wid,)).fetchall()
        titled_automations: set[str] = set()
        for source in automation_sources:
            rid = "automation:" + source["id"]
            if rid not in names:
                requests.append(
                    dict(
                        id=rid,
                        input={},
                        created_at=source["created_at"],
                        source_label=source["automation_name"],
                        context="",
                    )
                )
                names[rid] = explicit_title(source["answer"]) or source["automation_name"]
            if rid not in titled_automations and (title := explicit_title(source["answer"])):
                names[rid] = title
                titled_automations.add(rid)
            answers.append(dict(request_id=rid, answer=source["answer"]))
        production = production_roots(requests, answers)
        # An original request may have no answer; a retry can supply its title.
        for request in requests:
            root = production.get(request["id"])
            if root and request.get("title_source") in {"answer", "custom"}:
                original = next((r for r in requests if r["id"] == root), {})
                if original.get("title_source") not in {"answer", "custom"}:
                    names[root] = request["display_title"]
        items = conn.execute(
            """
            SELECT 'answer:'||a.request_id||':'||a.version id,a.request_id::text,
            a.version,a.version answer_version,a.created_at::text,
            coalesce(nullif(a.title,''),v.definition->>'name','이름 없는 결과') title,
            v.definition->>'name' agent_name,
            CASE WHEN s.approved_version=a.version THEN 'approved' ELSE 'saved' END status,
            CASE WHEN jsonb_typeof(a.answer)='object' THEN
              ARRAY(SELECT jsonb_object_keys(a.answer)) ELSE ARRAY[]::text[] END keys,
            a.answer IS NULL legacy,
            coalesce(a.answer,jsonb_build_object('narration',a.narration)) preview_content
            FROM script_versions a JOIN customer_requests r
            ON r.workspace_id=a.workspace_id AND r.id=a.request_id
            JOIN registry_versions v ON v.workspace_id=r.workspace_id
            AND v.agent_id=r.agent_id AND v.version=r.version
            JOIN script_stages s ON s.workspace_id=a.workspace_id AND s.request_id=a.request_id
            WHERE a.workspace_id=%s
        """,
            (wid,),
        ).fetchall()
        contents = {}
        for item in items:
            contents[item["id"]] = item.pop("preview_content")
            item["excerpt"] = excerpt(contents[item["id"]])
            keys = item.pop("keys")
            item["kind"] = (
                "script"
                if item.pop("legacy")
                else answer_kind(dict.fromkeys(keys), item["agent_name"] or "")
            )
            item["title"] = names.get(item["request_id"], item["title"])
            item["subtype"] = "답변"
        images = conn.execute(
            """
            SELECT 'image:'||j.id id,p.request_id::text,p.source_version answer_version,
            j.version,j.created_at::text,j.character->>'name' title,
            CASE WHEN coalesce(pref.excluded,false) THEN 'excluded'
            WHEN p.approved->>j.character_id=j.id::text OR
            coalesce(p.approved_versions->j.character_id,'[]'::jsonb) ? j.id::text
            THEN 'approved' ELSE 'review' END status,p.kind subtype,
            '/api/v1/characters/images/'||j.id||'/asset' media_url,'image' kind
            FROM character_image_jobs j JOIN character_projects p
            ON p.workspace_id=j.workspace_id AND p.id=j.project_id
            LEFT JOIN work_item_preferences pref ON pref.workspace_id=p.workspace_id
            AND pref.request_id=p.request_id AND pref.source_version=p.source_version
            AND pref.item_id=j.character_id
            AND pref.kind=CASE WHEN p.kind='scene' THEN 'scene_images' ELSE 'character_images' END
            WHERE j.workspace_id=%s AND j.status='succeeded' AND j.image IS NOT NULL
            UNION ALL
            SELECT 'upload:'||id,NULL,1,1,created_at::text,character->>'name','uploaded',
            'reference','/api/v1/characters/images/'||id||'/asset','image'
            FROM character_reference_uploads WHERE workspace_id=%s
        """,
            (wid, wid),
        ).fetchall()
        items.extend(images)
        items.extend(
            conn.execute(
                """
            SELECT 'reference:'||id id,NULL::text request_id,1 answer_version,1 version,
            created_at::text,filename title,'uploaded' status,'video_reference' subtype,
            'video' kind,CASE WHEN video IS NOT NULL
            THEN '/api/v1/library/references/'||id||'/media' END media_url
            FROM video_references WHERE workspace_id=%s
        """,
                (wid,),
            ).fetchall()
        )
        # Include successful automation step outputs, not just interactive agent work.
        automated = conn.execute(
            "SELECT id,step_index,version,created_at::text,name,"
            "automation_name,answer,CASE WHEN jsonb_typeof(answer)='object' THEN "
            "ARRAY(SELECT jsonb_object_keys(answer)) ELSE ARRAY[]::text[] END keys "
            "FROM (" + AUTOMATION_ITEMS + ") a",
            (wid,),
        ).fetchall()
        for entry in automated:
            contents[f"automation:{entry['id']}:{entry['step_index']}"] = entry["answer"]
            items.append(
                dict(
                    id=f"automation:{entry['id']}:{entry['step_index']}",
                    request_id=None,
                    answer_version=1,
                    version=1,
                    created_at=entry["created_at"],
                    title=entry["name"],
                    status="saved",
                    subtype="automation",
                    kind=answer_kind(dict.fromkeys(entry["keys"]), entry["name"] or ""),
                    source_name=entry["automation_name"],
                    subject="automation:" + entry["id"],
                    excerpt=excerpt(entry["answer"]),
                )
            )
        items.extend(
            conn.execute(
                """
            SELECT 'video:'||id id,request_id::text,answer_version,1 version,
            created_at::text,clip_id title,status,'clip' subtype,'video' kind,
            CASE WHEN video IS NOT NULL AND status IN ('review','approved')
            THEN '/api/v1/video-clips/asset/'||id||'/video' END media_url
            FROM video_clip_jobs WHERE workspace_id=%s
            UNION ALL
            SELECT 'video:'||v.id,v.request_id::text,v.answer_version,1,d.deleted_at::text,
            v.clip_id,'retained','clip','video',
            '/api/v1/video-clips/asset/'||v.id||'/video'
            FROM retained_work_videos v JOIN work_deletions d
            ON d.workspace_id=v.workspace_id AND d.request_id=v.request_id
            WHERE v.workspace_id=%s
            UNION ALL
            SELECT 'audio:'||id,request_id::text,answer_version,1,created_at::text,
            CASE WHEN kind='compose' THEN '최종 합성 영상'
            ELSE coalesce(nullif(cue_id,''),'음성') END,
            status,kind,CASE WHEN kind='compose' THEN 'video' ELSE 'audio' END,
            CASE WHEN media IS NOT NULL AND status IN ('review','approved')
            THEN '/api/v1/audio/jobs/'||id||'/media' END
            FROM audio_jobs WHERE workspace_id=%s
            UNION ALL
            SELECT 'music:'||id,NULL,1,1,created_at::text,name,'uploaded','music','audio',
            '/api/v1/audio/assets/'||id||'/media' FROM audio_assets WHERE workspace_id=%s
        """,
                (wid, wid, wid, wid),
            ).fetchall()
        )
        works = conn.execute(
            "SELECT id::text,name,revision FROM library_works "
            "WHERE workspace_id=%s ORDER BY name,id",
            (wid,),
        ).fetchall()
        scene_projects = {
            (row["request_id"], row["source_version"])
            for row in conn.execute(
                "SELECT request_id::text,source_version FROM character_projects "
                "WHERE workspace_id=%s AND kind='scene'", (wid,)
            ).fetchall()
        }
        bindings = conn.execute(
            "SELECT subject,work_id::text,revision FROM library_assignments WHERE workspace_id=%s",
            (wid,),
        ).fetchall()
    by_subject = {b["subject"]: b for b in bindings}
    by_work = {w["id"]: w for w in works}
    sources = {r["id"]: r for r in requests}
    reference_uses: dict[str, set[str | None]] = {}
    for request in requests:
        for value in (request.get("input") or {}).values():
            for entry in value if isinstance(value, list) else []:
                if isinstance(entry, dict) and entry.get("format") == "asa_video_reference_v1":
                    key = "reference:" + str(entry.get("source_id", ""))
                    reference_uses.setdefault(key, set()).add(production.get(request["id"]))

    def item_root(item: dict[str, Any]) -> str | None:
        rid = item.get("request_id")
        root = production.get(rid) if rid else production.get(item.get("subject", ""))
        usage = reference_uses.get(item["id"], set())
        return root or (next(iter(usage)) if len(usage) == 1 and None not in usage else None)

    for item in items:
        rid = item.get("request_id")
        root = item_root(item)
        if not root:
            continue
        auto_id = str(uuid5(UUID(str(wid)), "library:" + root))
        if auto_id not in by_work:
            work = dict(
                id=auto_id,
                name=names.get(root) or item.get("source_name") or "제목 없는 작품",
                revision=0,
            )
            works.append(work)
            by_work[auto_id] = work
        by_work[auto_id].update(
            automatic=True,
            origin=f"/works/{root}" if root in roots else None,
            source_label=sources[root].get("source_label", ""),
            created_at=sources[root].get("created_at"),
            context=sources[root].get("context", ""),
        )
    for item in items:
        rid = item.get("request_id")
        subject = "request:" + roots.get(rid, rid) if rid else item.get("subject", item["id"])
        root = item_root(item)
        binding = by_subject.get(subject)
        inherited = by_subject.get("request:" + root) if root and rid else None
        effective = binding if binding is not None else inherited
        work_id = (
            effective.get("work_id")
            if effective is not None
            else (str(uuid5(UUID(str(wid)), "library:" + root)) if root else None)
        )
        work = by_work.get(work_id, {})
        item.update(
            subject=subject,
            assignment_revision=(binding or {}).get("revision", 0),
            automatic=effective is None and bool(work),
            work_id=work.get("id"),
            work_name=work.get("name"),
            source_name=names.get(
                rid, item.get("source_name") or ("삭제된 작업" if rid else "직접 업로드")
            ),
            origin=f"/works/{rid}/answers/{item['answer_version']}" if rid in names else None,
        )
        item["category"] = asset_category(item)
        item.setdefault("media_url", None)
        item["title"] = item.get("title") or "이름 없는 자료"
    annotate(items, contents, requests, scene_projects)
    for work in works:
        work["count"] = sum(i["work_id"] == work["id"] for i in visible_items(items))
    return {"items": items, "works": [w for w in works if w["count"] or not w.get("automatic")]}


def detail(repo: RegistryRepository, user_id: str, item_id: str) -> dict[str, Any]:
    data = index(repo, user_id)
    item = next((i for i in data["items"] if i["id"] == item_id), None)
    if item is None:
        raise RegistryError(404, "library_item_missing")
    item = dict(item)
    representative = item.get("duplicate_of") or item["id"]
    item["related_items"] = [i for i in data["items"] if i.get("parent_scene_id") == representative]
    item["duplicate_items"] = [
        i for i in data["items"]
        if (i.get("duplicate_of") or i["id"]) == representative
    ]
    item["parent_scene"] = next(
        (i for i in data["items"] if i["id"] == item.get("parent_scene_id")), None
    )
    item["content"] = None
    if item_id.startswith("reference:"):
        with repo._connect() as conn:
            row = conn.execute(
                "SELECT url FROM video_references WHERE workspace_id=%s AND id=%s",
                (repo.workspace_id, UUID(item_id.split(":")[1])),
            ).fetchone()
        if row and row["url"]:
            item["content"] = {"url": row["url"]}
    if item_id.startswith("automation:"):
        with repo._connect() as conn:
            row = conn.execute(
                "SELECT answer FROM (" + AUTOMATION_ITEMS + ") a WHERE id=%s AND step_index=%s",
                (repo.workspace_id, item_id.split(":")[1], int(item_id.split(":")[2])),
            ).fetchone()
        if row:
            item["content"] = row["answer"]
    if item_id.startswith("answer:"):
        with repo._connect() as conn:
            row = conn.execute(
                "SELECT answer,title,narration FROM script_versions "
                "WHERE workspace_id=%s AND request_id=%s AND version=%s",
                (repo.workspace_id, UUID(item["request_id"]), item["version"]),
            ).fetchone()
        if not row:
            raise RegistryError(404, "library_item_missing")
        item["content"] = (
            row["answer"]
            if row["answer"] is not None
            else {"title": row["title"], "narration": row["narration"]}
        )
    item["versions"] = [
        i
        for i in data["items"]
        if i["subject"] == item["subject"] and i["category"] == item["category"]
        and not i.get("duplicate_of")
        and bool(i.get("is_scene_plan")) == bool(item.get("is_scene_plan"))
    ]
    return item
