from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
from test_registry_db import client as client_fixture
from test_registry_db import db as db_fixture
from test_registry_db import script_work

client = client_fixture
db = db_fixture


def test_automatic_works_follow_saved_content_and_media_without_writes(client, db):
    headers, work, _ = script_work(client)
    child, separate, project, image = uuid4(), uuid4(), uuid4(), uuid4()
    story = "전체 대본 원문을 유지합니다. " * 40
    with psycopg.connect(db[0]) as conn:
        for rid, inputs in ((child, {"script": story}), (separate, {"topic": "같은 제목"})):
            conn.execute(
                "INSERT INTO customer_requests(workspace_id,id,agent_id,version,"
                "input,requested_by) "
                "SELECT workspace_id,%s,agent_id,version,%s,requested_by "
                "FROM customer_requests WHERE workspace_id=%s AND id=%s",
                (rid, Jsonb(inputs), db[1], work["id"]),
            )
        for rid, answer in (
            (work["id"], {"script": story}),
            (child, {"scenes": ["장면"]}),
            (separate, {"script": "다른 원문"}),
        ):
            conn.execute(
                "INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)", (db[1], rid)
            )
            conn.execute(
                "INSERT INTO script_versions(workspace_id,request_id,version,operation_id,"
                "title,narration,source,answer) VALUES (%s,%s,1,%s,'같은 제목','','ai',%s)",
                (db[1], rid, uuid4(), Jsonb(answer)),
            )
        conn.execute(
            "INSERT INTO character_projects(workspace_id,id,request_id,name,characters) "
            "VALUES (%s,%s,%s,'images','[]')",
            (db[1], project, child),
        )
        conn.execute(
            "INSERT INTO character_image_jobs(workspace_id,id,project_id,character_id,version,"
            "model,character,change,status,image) "
            "VALUES (%s,%s,%s,'c',1,'test','{}','','succeeded',%s)",
            (db[1], image, project, b"image"),
        )
    result = client.get("/api/v1/library").json()
    assert len(result["works"]) == 2
    for collection in result["works"]:
        assert collection["source_label"]
        assert collection["created_at"]
        assert "context" in collection
    assert result["unassigned"] == 0
    rows = {i["id"]: i for i in result["items"]}
    parent = rows[f"answer:{work['id']}:1"]
    assert parent["work_id"] == rows[f"answer:{child}:1"]["work_id"]
    assert parent["work_id"] == rows[f"image:{image}"]["work_id"]
    assert parent["work_id"] != rows[f"answer:{separate}:1"]["work_id"]
    scoped = client.get("/api/v1/library?work=" + parent["work_id"] + "&kind=script").json()
    assert scoped["total"] == 1
    assert scoped["counts"]["script"] == 1
    assert scoped["counts"]["scene"] == 1
    assert scoped["counts"]["character_image"] == 1
    assert scoped["items"][0]["excerpt"].startswith("전체 대본 원문을 유지합니다.")
    assert "answer" not in scoped["items"][0]
    with psycopg.connect(db[0]) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM library_works WHERE workspace_id=%s", (db[1],)
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM library_assignments WHERE workspace_id=%s", (db[1],)
            ).fetchone()[0]
            == 0
        )
    # Explicit exceptions may still target an automatically discovered work.
    item = rows[f"answer:{separate}:1"]
    assert (
        client.put(
            "/api/v1/library/assignment",
            headers=headers,
            json={
                "subject": item["subject"],
                "work_id": parent["work_id"],
                "revision": 0,
            },
        ).status_code
        == 200
    )
    assert client.get("/api/v1/library?work=" + parent["work_id"]).json()["total"] == 4


def test_existing_answers_library_and_collection_conflict(client, db):
    assert client.get("/api/v1/library").status_code == 401
    headers, work, _ = script_work(client)
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)", (db[1], work["id"])
        )
        for version in (1, 2):
            conn.execute(
                "INSERT INTO script_versions(workspace_id,"
                "request_id,version,operation_id,title,narration,source,answer) "
                "VALUES (%s,%s,%s,%s,'같은 제목','','ai',%s)",
                (db[1], work["id"], version, uuid4(), Jsonb({"script": f"원문{version}"})),
            )
    result = client.get("/api/v1/library?kind=script").json()
    assert result["total"] == 2
    first = result["items"][0]
    assert first["version"] == 2
    assert client.get("/api/v1/library?kind=audio").json()["total"] == 0
    assert client.get("/api/v1/library/items/" + first["id"]).json()["content"]["script"] == "원문2"
    assert client.get("/api/v1/library/items/answer:" + str(uuid4()) + ":1").status_code == 404
    body = {"name": "작품 하나"}
    assert client.post("/api/v1/library/works", json=body).status_code == 403
    project = client.post("/api/v1/library/works", json=body, headers=headers).json()
    change = {"subject": first["subject"], "work_id": project["id"], "revision": 0}
    assert client.put("/api/v1/library/assignment", json=change, headers=headers).status_code == 200
    assert client.put("/api/v1/library/assignment", json=change, headers=headers).status_code == 409
    linked = client.get("/api/v1/library?work=" + project["id"]).json()
    assert linked["total"] == 2
    assert all(x["work_name"] == "작품 하나" for x in linked["items"])
    assert client.get("/api/v1/library?work=unassigned").json()["total"] == 0
    change.update(revision=1, work_id=None)
    assert client.put("/api/v1/library/assignment", json=change, headers=headers).status_code == 200
    assert client.get("/api/v1/library?work=unassigned").json()["total"] == 2
    change.update(revision=2, work_id=str(uuid4()))
    assert client.put("/api/v1/library/assignment", json=change, headers=headers).status_code == 404
    change.update(subject="request:" + str(uuid4()))
    assert client.put("/api/v1/library/assignment", json=change, headers=headers).status_code == 404
    with psycopg.connect(db[0]) as conn:
        assert conn.execute(
            "SELECT answer FROM script_versions WHERE workspace_id=%s AND "
            "request_id=%s AND version=2",
            (db[1], work["id"]),
        ).fetchone()[0] == {"script": "원문2"}


def test_media_sources_and_foreign_workspace_do_not_leak(client, db):
    from asa.registry.repository import migrate

    headers, work, _ = script_work(client)
    other = uuid4()
    migrate(db[0], other)
    music, foreign, reference = uuid4(), uuid4(), uuid4()
    with psycopg.connect(db[0]) as conn:
        for wid, asset in ((db[1], music), (other, foreign)):
            conn.execute(
                "INSERT INTO audio_assets(workspace_id,"
                "id,name,data,duration,sha256) VALUES (%s,%s,'music',%s,2,'hash')",
                (wid, asset, b"private bytes"),
            )
        conn.execute(
            "INSERT INTO video_references(workspace_id,id,url,filename) VALUES "
            "(%s,%s,'https://www.youtube.com/watch?v=abcdefghijk','reference')",
            (db[1], reference),
        )
    result = client.get("/api/v1/library").json()
    assert {i["id"] for i in result["items"]} == {
        "music:" + str(music),
        "reference:" + str(reference),
    }
    assert all("private bytes" not in str(i) for i in result["items"])
    assert client.get("/api/v1/library/items/music:" + str(foreign)).status_code == 404
    assert (
        client.put(
            "/api/v1/library/assignment",
            headers=headers,
            json={"subject": "music:" + str(foreign), "work_id": None, "revision": 0},
        ).status_code
        == 404
    )
    assert (
        client.get("/api/v1/library/items/reference:" + str(reference))
        .json()["content"]["url"]
        .startswith("https://")
    )
    assert client.get("/api/v1/library/references/" + str(uuid4()) + "/media").status_code == 404
    # A reference with one production owner is automatically included. A shared
    # reference remains unassigned rather than merging the two independent works.
    with psycopg.connect(db[0]) as conn:
        inputs = Jsonb(
            {"video": [{"format": "asa_video_reference_v1", "source_id": str(reference)}]}
        )
        conn.execute(
            "UPDATE customer_requests SET input=%s WHERE workspace_id=%s AND id=%s",
            (inputs, db[1], work["id"]),
        )
    referenced = client.get("/api/v1/library/items/reference:" + str(reference)).json()
    assert referenced["automatic"] and referenced["work_id"]
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "INSERT INTO customer_requests(workspace_id,id,agent_id,version,input,requested_by) "
            "SELECT workspace_id,%s,agent_id,version,input,requested_by "
            "FROM customer_requests WHERE workspace_id=%s AND id=%s",
            (uuid4(), db[1], work["id"]),
        )
    assert client.get("/api/v1/library/items/reference:" + str(reference)).json()["work_id"] is None


def test_retained_videos_and_excluded_image_versions(client, db):
    _, work, _ = script_work(client)
    deleted, video, project, image = uuid4(), uuid4(), uuid4(), uuid4()
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "INSERT INTO work_deletions(workspace_id,"
            "request_id,name,actor,summary) VALUES (%s,%s,'old','tester','{}')",
            (db[1], deleted),
        )
        conn.execute(
            "INSERT INTO retained_work_videos(workspace_id,"
            "id,request_id,clip_id,answer_version,video) VALUES (%s,%s,%s,'one',1,%s)",
            (db[1], video, deleted, b"video"),
        )
        conn.execute(
            "INSERT INTO character_projects(workspace_id,"
            "id,request_id,name,characters,approved) VALUES (%s,%s,%s,'images','[]',%s)",
            (db[1], project, work["id"], Jsonb({"c": str(image)})),
        )
        conn.execute(
            "INSERT INTO character_image_jobs(workspace_id,"
            "id,project_id,character_id,version,model,"
            "character,change,status,image) VALUES (%s,%s,%s,'c',1,'test',%s,'','succeeded',%s)",
            (db[1], image, project, Jsonb({"id": "c", "name": "character"}), b"image"),
        )
        conn.execute(
            "INSERT INTO work_item_preferences(workspace_id,"
            "request_id,source_version,kind,item_id,excluded) VALUES "
            "(%s,%s,1,'character_images','c',true)",
            (db[1], work["id"]),
        )
    rows = {i["id"]: i for i in client.get("/api/v1/library").json()["items"]}
    assert rows["video:" + str(video)]["status"] == "retained"
    assert rows["video:" + str(video)]["origin"] is None
    assert rows["image:" + str(image)]["status"] == "excluded"
    assert client.get(rows["video:" + str(video)]["media_url"]).content == b"video"


def test_direct_automation_outputs_and_pagination(client, db):
    script_work(client)
    automation, run = uuid4(), uuid4()
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "INSERT INTO automation_drafts(workspace_id,id,draft) VALUES (%s,%s,'{}')",
            (db[1], automation),
        )
        steps = [
            {"id": str(i), "label": "직접 AI", "status": "succeeded", "output": f"결과{i}"}
            for i in range(26)
        ]
        conn.execute(
            "INSERT INTO automation_runs(workspace_id,id,automation_id,revision,"
            "definition,manifest,prompt,status,steps) VALUES "
            "(%s,%s,%s,1,%s,'[]','','succeeded',%s)",
            (db[1], run, automation, Jsonb({"name": "자동화"}), Jsonb(steps)),
        )
    first = client.get("/api/v1/library").json()
    second = client.get("/api/v1/library?offset=24").json()
    assert first["total"] == 26 and first["has_more"]
    assert len(first["items"]) == 24 and len(second["items"]) == 2
    assert not {i["id"] for i in first["items"]}.intersection(i["id"] for i in second["items"])
    assert client.get(f"/api/v1/library/items/automation:{run}:0").json()["content"] == "결과0"

    pages = [
        client.get(f"/api/v1/library?limit=12&offset={offset}").json() for offset in (0, 12, 24)
    ]
    assert [len(page["items"]) for page in pages] == [12, 12, 2]
    assert [page["has_more"] for page in pages] == [True, True, False]
    assert len({item["id"] for page in pages for item in page["items"]}) == 26
    assert len(client.get("/api/v1/library?limit=48").json()["items"]) == 26
    for invalid in (0, 49):
        assert client.get(f"/api/v1/library?limit={invalid}").status_code == 422


def test_scene_grouping_preserves_all_original_detail_endpoints(client, db):
    _, work, _ = script_work(client)
    automation, run = uuid4(), uuid4()
    scene = "원본 씬 구성은 바뀌지 않습니다. " * 20
    plan = {"shots": [{"description": "같은 씬의 이미지 제작 계획"}]}
    steps = [
        {"id": "scene", "label": "장면 구성", "status": "succeeded", "output": scene},
        {"id": "end", "label": "장면 구성 결과", "status": "succeeded", "output": scene},
    ]
    with psycopg.connect(db[0]) as conn:
        conn.execute("INSERT INTO automation_drafts(workspace_id,id,draft) VALUES (%s,%s,'{}')",
                     (db[1], automation))
        conn.execute(
            "INSERT INTO automation_runs(workspace_id,id,automation_id,revision,"
            "definition,manifest,prompt,status,steps) VALUES "
            "(%s,%s,%s,1,%s,'[]','','succeeded',%s)",
            (db[1], run, automation, Jsonb({"name": "작품"}), Jsonb(steps)),
        )
        conn.execute("UPDATE customer_requests SET input=%s WHERE workspace_id=%s AND id=%s",
                     (Jsonb({"scenes": scene}), db[1], work["id"]))
        conn.execute("INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)",
                     (db[1], work["id"]))
        conn.execute(
            "INSERT INTO script_versions(workspace_id,request_id,version,operation_id,"
            "title,narration,source,answer) VALUES (%s,%s,1,%s,'계획','','ai',%s)",
            (db[1], work["id"], uuid4(), Jsonb(plan)),
        )
    listed = client.get("/api/v1/library?kind=scene&limit=12").json()
    assert listed["total"] == listed["counts"]["scene"] == 1
    canonical = listed["items"][0]
    assert canonical["duplicate_count"] == 2 and canonical["related_count"] == 1
    detail = client.get("/api/v1/library/items/" + canonical["id"]).json()
    assert len(detail["duplicate_items"]) == 2
    assert len(detail["versions"]) == 1
    assert len(detail["related_items"]) == 1
    assert client.get(f"/api/v1/library/items/automation:{run}:1").json()["content"] == scene
    linked = client.get(f"/api/v1/library/items/answer:{work['id']}:1").json()
    assert linked["content"] == plan and linked["parent_scene"]["id"] == canonical["id"]
    with psycopg.connect(db[0]) as conn:
        assert conn.execute("SELECT steps FROM automation_runs WHERE workspace_id=%s AND id=%s",
                            (db[1], run)).fetchone()[0] == steps


def test_artifact_categories_share_work_but_keep_separate_media(client, db):
    _, work, _ = script_work(client)
    speech, music = uuid4(), uuid4()
    with psycopg.connect(db[0]) as conn:
        for version, category in enumerate(("character", "scene"), start=1):
            project, image = uuid4(), uuid4()
            conn.execute(
                "INSERT INTO character_projects(workspace_id,id,request_id,name,characters,"
                "kind,source_version) "
                "VALUES (%s,%s,%s,'assets','[]',%s,%s)",
                (db[1], project, work["id"], category, version),
            )
            conn.execute(
                "INSERT INTO character_image_jobs(workspace_id,id,project_id,character_id,version,"
                "model,character,change,status,image) "
                "VALUES (%s,%s,%s,'c',1,'test','{}','','succeeded',%s)",
                (db[1], image, project, b"image"),
            )
        conn.execute(
            "INSERT INTO audio_jobs(workspace_id,id,request_id,answer_version,kind,"
            "fingerprint,input,status,media) VALUES (%s,%s,%s,1,'speech','test','{}','review',%s)",
            (db[1], speech, work["id"], b"audio"),
        )
        conn.execute(
            "INSERT INTO audio_assets(workspace_id,id,name,data,duration,sha256) "
            "VALUES (%s,%s,'music',%s,2,'hash')",
            (db[1], music, b"music"),
        )
    all_items = client.get("/api/v1/library").json()
    assert all_items["total"] == 4
    categories = {"character_image", "scene_image", "speech", "music"}
    assert {i["category"] for i in all_items["items"]} == categories
    linked = []
    for category in categories:
        result = client.get(f"/api/v1/library?kind={category}").json()
        assert result["total"] == result["counts"][category] == 1
        item = result["items"][0]
        detail = client.get("/api/v1/library/items/" + item["id"]).json()
        assert detail["category"] == category
        assert {v["category"] for v in detail["versions"]} == {category}
        assert item["media_url"]
        if category != "music":
            linked.append(item["work_id"])
    assert len(set(linked)) == 1 and linked[0]
    assert client.get("/api/v1/library?work=" + linked[0]).json()["total"] == 3
    assert client.get("/api/v1/library?kind=image").json()["total"] == 2
    assert client.get("/api/v1/library?kind=audio").json()["total"] == 2
