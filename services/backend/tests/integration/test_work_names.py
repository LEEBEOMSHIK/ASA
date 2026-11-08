from uuid import UUID, uuid4

import pytest
from psycopg.types.json import Jsonb
from test_registry_db import client as client_fixture
from test_registry_db import db as database_fixture
from test_registry_db import script_work

from asa.registry.history import HistoryRepository
from asa.registry.schemas import RegistryError

client = client_fixture
db = database_fixture


def test_names_sync_conflict_reset_user_scope_and_preserve_content(client, db):
    headers, work, _ = script_work(client)
    repo = HistoryRepository(*db)
    with repo._connect() as conn:
        conn.execute(
            "INSERT INTO script_stages(workspace_id,request_id) VALUES (%s,%s)", (db[1], work["id"])
        )
        conn.execute(
            "INSERT INTO script_versions(workspace_id,request_id,version,operation_id,"
            "title,narration,source,answer) VALUES (%s,%s,1,%s,'','','ai',%s)",
            (db[1], work["id"], uuid4(), Jsonb("제목: 검증 작품\n원문 그대로")),
        )
    path = "/api/v1/work-requests/" + work["id"]
    original = client.get(path).json()
    assert original["display_title"] == "검증 작품"
    assert client.put(path + "/name", json={"name": "내 이름", "revision": 0}).status_code == 403
    for invalid in ["", "   ", "x" * 121]:
        assert (
            client.put(
                path + "/name", json={"name": invalid, "revision": 0}, headers=headers
            ).status_code
            == 422
        )
    saved = client.put(path + "/name", json={"name": "  내 작품  ", "revision": 0}, headers=headers)
    assert saved.status_code == 200
    assert saved.json()["display_title"] == "내 작품"
    assert saved.json()["input"] == original["input"]
    assert saved.json()["version"] == original["version"]
    assert client.get("/api/v1/work-requests").json()["items"][0]["display_title"] == "내 작품"
    assert (
        client.put(
            path + "/name", json={"name": "늦은 변경", "revision": 0}, headers=headers
        ).status_code
        == 409
    )
    repo.requested_by = "different-user"
    assert repo.history(0)["items"][0]["display_title"] == "검증 작품"
    with pytest.raises(RegistryError):
        HistoryRepository(db[0], uuid4()).detail(UUID(work["id"]))
    assert (
        client.put(
            "/api/v1/work-requests/" + str(uuid4()) + "/name",
            json={"name": "다른 작업", "revision": 0},
            headers=headers,
        ).status_code
        == 404
    )
    reset = client.put(path + "/name", json={"name": None, "revision": 1}, headers=headers)
    assert reset.status_code == 200
    assert reset.json()["display_title"] == "검증 작품"
    assert reset.json()["name_revision"] == 2
    with repo._connect() as conn:
        assert (
            conn.execute(
                "SELECT answer FROM script_versions WHERE workspace_id=%s AND request_id=%s",
                (db[1], work["id"]),
            ).fetchone()["answer"]
            == "제목: 검증 작품\n원문 그대로"
        )
