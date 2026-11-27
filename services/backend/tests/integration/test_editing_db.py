import json
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
from test_registry_db import client as client_fixture
from test_registry_db import db as db_fixture
from test_registry_db import login

from asa.auth.permissions import can_request
from asa.config import Settings
from asa.editing_worker import recover, tick

client = client_fixture
db = db_fixture


def seed(client, db):
    headers = login(client)
    draft = json.loads(
        (Path(__file__).parents[4] / "docs/agent-templates/video-editor.json").read_text(
            encoding="utf-8"
        )
    )
    saved = client.post("/api/v1/agents", json=draft, headers=headers)
    assert saved.status_code == 201, saved.text
    agent = saved.json()
    assert (
        client.post(
            f"/api/v1/agents/{agent['id']}/publish", headers={**headers, "If-Match": '"1"'}
        ).status_code
        == 201
    )
    source = "video:" + str(uuid4())
    inputs = {
        "editing_sources": json.dumps([{"id": source}]),
        "aspect_ratio": "9:16",
        "resolution": "720p",
    }
    work = client.post(
        "/api/v1/work-requests",
        headers=headers,
        json={"id": str(uuid4()), "agent_id": agent["id"], "version": 1, "input": inputs},
    ).json()
    plan = {
        "format": "asa_edit_plan_v1",
        "title": "test",
        "summary": "",
        "aspect_ratio": "9:16",
        "resolution": "720p",
        "segments": [
            {
                "source_id": source,
                "start": 0,
                "duration": 1,
                "motion": "static",
                "transition": "cut",
                "volume": 1,
                "caption": "",
            }
        ],
        "tracks": [],
    }
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "INSERT INTO script_stages(workspace_id,request_id,head_version) VALUES (%s,%s,1)",
            (db[1], work["id"]),
        )
        conn.execute(
            "INSERT INTO script_versions(workspace_id,request_id,version,operation_id,"
            "title,narration,source,answer) VALUES (%s,%s,1,%s,'','','ai',%s)",
            (db[1], work["id"], uuid4(), Jsonb(plan)),
        )
    return headers, work, plan


def test_editing_approval_idempotency_snapshot_and_worker(client, db, monkeypatch):
    from asa import editing_worker
    from asa.registry import editing

    headers, work, plan = seed(client, db)
    path = f"/api/v1/work-requests/{work['id']}/editing"
    operation = {"id": str(uuid4()), "version": 1}
    assert client.post(path + "/compose", json=operation, headers=headers).status_code == 409
    with psycopg.connect(db[0]) as conn:
        conn.execute("UPDATE script_stages SET approved_version=1 WHERE workspace_id=%s", (db[1],))
    assert client.post(path + "/compose", json=operation, headers=headers).status_code == 409
    source = plan["segments"][0]["source_id"]
    monkeypatch.setattr(editing, "sources", lambda *a: [{"id": source, "title": "source"}])
    monkeypatch.setattr(editing, "source_bytes", lambda *a: b"original")
    result = client.post(path + "/compose", json=operation, headers=headers)
    assert result.status_code == 200, result.text
    again = client.post(path + "/compose", json={**operation, "id": str(uuid4())}, headers=headers)
    assert again.json() == result.json()
    assert client.post(path + "/compose", json=operation).status_code == 403

    def render(plan, assets, executable):
        assert assets[source] == b"original"
        return b"rendered"

    monkeypatch.setattr(editing_worker, "render", render)
    config = Settings(_env_file=None, database_url=db[0], workspace_id=db[1])
    assert tick(config)
    job = result.json()["id"]
    assert client.get(path).json()["jobs"][0]["status"] == "review"
    media_path = f"/api/v1/editing/jobs/{job}/media"
    full = client.get(media_path)
    assert full.content == b"rendered"
    assert full.headers["accept-ranges"] == "bytes"
    for header, selected, content_range in [
        ("bytes=1-3", b"end", "bytes 1-3/8"),
        ("bytes=5-", b"red", "bytes 5-7/8"),
        ("bytes=-2", b"ed", "bytes 6-7/8"),
    ]:
        part = client.get(media_path, headers={"Range": header})
        assert part.status_code == 206
        assert part.content == selected
        assert part.headers["content-range"] == content_range
    invalid = client.get(media_path, headers={"Range": "bytes=8-"})
    assert invalid.status_code == 416 and invalid.headers["content-range"] == "bytes */8"
    assert (
        client.post(f"/api/v1/editing/jobs/{job}/approve", json={}, headers=headers).status_code
        == 200
    )
    assert not tick(config)
    other = Settings(_env_file=None, database_url=db[0], workspace_id=uuid4())
    assert not tick(other)
    assert not can_request(("home.view",), "POST", path + "/compose")
    assert not can_request(("home.view",), "POST", f"/api/v1/editing/jobs/{job}/approve")
    assert can_request(("home.view", "home.generate"), "POST", path + "/compose")


def test_editing_foreign_sources_and_recovery(client, db):
    import pytest

    from asa.database import connection
    from asa.registry.editing import source_bytes
    from asa.registry.schemas import RegistryError

    headers, work, plan = seed(client, db)
    with connection(db[0], dictionary=True) as conn:
        with pytest.raises(RegistryError):
            source_bytes(conn, db[1], plan["segments"][0]["source_id"])
    job = uuid4()
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "INSERT INTO editing_jobs(workspace_id,id,request_id,answer_version,plan,status) "
            "VALUES (%s,%s,%s,1,%s,'running')",
            (db[1], job, work["id"], Jsonb(plan)),
        )
    recover(Settings(_env_file=None, database_url=db[0], workspace_id=db[1]))
    rows = client.get(f"/api/v1/work-requests/{work['id']}/editing").json()["jobs"]
    assert rows[0]["status"] == "failed"
    assert rows[0]["error_code"] == "editing_interrupted"
    assert client.get(f"/api/v1/editing/jobs/{uuid4()}/media").status_code == 404


def test_editing_manual_lineage_and_deletion(client, db, monkeypatch):
    from asa.registry import editing

    headers, work, plan = seed(client, db)
    source = "video:" + str(uuid4())
    plan["segments"][0]["source_id"] = source
    attempt = uuid4()
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "UPDATE customer_requests SET status='succeeded' WHERE workspace_id=%s", (db[1],)
        )
        conn.execute(
            "INSERT INTO script_attempts(workspace_id,request_id,id,instruction,status,"
            "prompt,model_profile,result_version) VALUES (%s,%s,%s,'','succeeded',%s,'default',2)",
            (
                db[1],
                work["id"],
                attempt,
                json.dumps({"original_request": {"editing_sources": json.dumps([{"id": source}])}}),
            ),
        )
        for version, base, op, origin in [(2, 1, attempt, "ai"), (3, 2, uuid4(), "manual")]:
            conn.execute(
                "INSERT INTO script_versions(workspace_id,request_id,version,base_version,"
                "operation_id,title,narration,source,answer) VALUES (%s,%s,%s,%s,%s,'','',%s,%s)",
                (db[1], work["id"], version, base, op, origin, Jsonb(plan)),
            )
        conn.execute(
            "UPDATE script_stages SET head_version=3,approved_version=3 WHERE workspace_id=%s",
            (db[1],),
        )
    monkeypatch.setattr(editing, "sources", lambda *a: [{"id": source, "title": "new source"}])
    monkeypatch.setattr(editing, "source_bytes", lambda *a: b"original")
    result = client.post(
        f"/api/v1/work-requests/{work['id']}/editing/compose",
        headers=headers,
        json={"id": str(uuid4()), "version": 3},
    )
    assert result.status_code == 200, result.text
    job = result.json()["id"]
    management = f"/api/v1/admin/work-history/{work['id']}"
    assert client.get(management + "/preview").json()["blockers"]
    with psycopg.connect(db[0]) as conn:
        conn.execute(
            "UPDATE editing_jobs SET status='review',media=%s WHERE workspace_id=%s",
            (b"rendered", db[1]),
        )
    preview = client.get(management + "/preview?delete_assets=true").json()
    assert preview["summary"]["videos"] == 1 and not preview["blockers"]
    removed = client.post(
        management + "/delete",
        headers=headers,
        json={"token": preview["token"], "delete_assets": True},
    )
    assert removed.status_code == 200, removed.text
    assert client.get(f"/api/v1/editing/jobs/{job}/media").status_code == 404
    with psycopg.connect(db[0]) as conn:
        assert conn.execute("SELECT count(*) FROM editing_job_assets").fetchone()[0] == 0


def test_editing_uploaded_video_sources(client, db, monkeypatch):
    import base64

    import pytest

    from asa.database import connection
    from asa.editing_contracts import EditPlan
    from asa.registry import editing
    from asa.registry.schemas import RegistryError

    headers, work, plan = seed(client, db)
    monkeypatch.setattr(editing, "probe", lambda *a: (5.0, True))
    raw = b"\x00\x00\x00\x18ftyp" + b"0" * 20
    response = client.post(
        "/api/v1/editing/uploads",
        headers=headers,
        json={"filename": "outside.mp4", "data": base64.b64encode(raw).decode()},
    )
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["id"].startswith("reference:") and item["duration"] == 5
    with connection(db[0], dictionary=True) as conn:
        assert editing.source_bytes(conn, db[1], item["id"]) == raw
        with pytest.raises(RegistryError):
            editing.source_bytes(conn, uuid4(), item["id"])
    plan["segments"][0]["source_id"] = item["id"]
    assert EditPlan.model_validate(plan).segments[0].source_id == item["id"]
    listing = client.get("/api/v1/editing/sources?kind=video&q=outside").json()
    assert listing["total"] == 1 and listing["items"][0]["duration"] == 5
    assert client.get("/api/v1/editing/sources?kind=video&origin=studio").json()["total"] == 0
    uploaded = client.get("/api/v1/editing/sources?kind=video&origin=upload").json()
    assert [source["id"] for source in uploaded["items"]] == [item["id"]]
    assert (
        client.post(
            "/api/v1/editing/uploads", headers=headers, json={"url": "https://example.com/file.mp4"}
        ).status_code
        == 422
    )
    monkeypatch.setattr(editing, "probe", lambda *a: (601.0, True))
    assert (
        client.post(
            "/api/v1/editing/uploads",
            headers=headers,
            json={"data": base64.b64encode(raw).decode()},
        ).status_code
        == 422
    )
