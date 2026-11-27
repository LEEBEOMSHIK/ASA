from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from test_registry_db import ORIGIN, login
from test_registry_db import client as client_fixture
from test_registry_db import db as database_fixture

from asa.registry.repository import migrate

db = database_fixture
client = client_fixture
BASE = "/api/v1/admin/access"
PASSWORD = "test-only-password-123"


def create_account(client, headers, permissions):
    role, user = str(uuid4()), str(uuid4())
    body = {"name": "Test role", "permissions": permissions, "revision": 0}
    assert client.put(f"{BASE}/roles/{role}", json=body, headers=headers).status_code == 200
    account = {
        "username": "test-user",
        "display_name": "Test user",
        "role_id": role,
        "password": PASSWORD,
        "revision": 0,
        "enabled": True,
    }
    response = client.put(f"{BASE}/users/{user}", json=account, headers=headers)
    assert response.status_code == 200, response.text
    return role, user, body, account


def user_login(client):
    response = client.post(
        "/api/v1/session/user", json={"username": "test-user", "password": PASSWORD}, headers=ORIGIN
    )
    assert response.status_code == 200, response.text
    return {**ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]}


def test_account_permissions_live_revocation_and_password_reset(client, db):
    assert client.get(BASE).status_code == 401
    headers = login(client)
    role, user, role_body, account = create_account(client, headers, ["home.view"])
    data = client.get(BASE).json()
    assert PASSWORD not in str(data) and "password_hash" not in str(data)
    with TestClient(client.app) as member:
        member_headers = user_login(member)
        assert member.get("/api/v1/work-requests").status_code == 200
        assert member.get(BASE).status_code == 403
        assert (
            member.post("/api/v1/work-requests", json={}, headers=member_headers).status_code == 403
        )
        assert (
            member.put("/api/v1/admin/models", json={}, headers=member_headers).status_code == 403
        )
        # A live session receives grants and loses them without logging in again.
        update = {**role_body, "revision": 1, "permissions": ["agents.view"]}
        assert client.put(f"{BASE}/roles/{role}", json=update, headers=headers).status_code == 200
        assert member.get("/api/v1/work-requests").status_code == 403
        assert member.get("/api/v1/agents").status_code == 200
        assert client.put(f"{BASE}/roles/{role}", json=update, headers=headers).status_code == 409
        # Password replacement invalidates existing sessions.
        account.update(revision=1, password="another-test-password-456")
        assert client.put(f"{BASE}/users/{user}", json=account, headers=headers).status_code == 200
        assert member.get("/api/v1/session").status_code == 401
    with psycopg.connect(db[0]) as conn:
        row = conn.execute("SELECT password_hash FROM access_users WHERE id=%s", (user,)).fetchone()
        assert row and PASSWORD not in row[0]
    migrate(*db)
    assert client.get(BASE).json()["users"][0]["id"] == user
    assert client.get("/api/v1/session").json()["roles"] == ["owner"]


def test_delegated_manager_cannot_escalate_or_modify_own_role(client):
    headers = login(client)
    role, user, body, account = create_account(client, headers, ["access.view", "access.edit"])
    with TestClient(client.app) as manager:
        member_headers = user_login(manager)
        assert manager.get(BASE).status_code == 200
        assert (
            manager.put(
                f"{BASE}/roles/{role}", json={**body, "revision": 1}, headers=member_headers
            ).status_code
            == 403
        )
        assert (
            manager.put(
                f"{BASE}/roles/{uuid4()}",
                json={**body, "permissions": ["models.view"]},
                headers=member_headers,
            ).status_code
            == 403
        )
        assert (
            manager.put(
                f"{BASE}/users/{user}", json={**account, "revision": 1}, headers=member_headers
            ).status_code
            == 403
        )
        role_body = {**body, "revision": 1, "enabled": False}
        assert (
            client.put(f"{BASE}/roles/{role}", json=role_body, headers=headers).status_code == 200
        )
        assert manager.get("/api/v1/session").status_code == 401
        # An account can still be disabled after its role has been stopped.
        assert (
            client.put(
                f"{BASE}/users/{user}",
                json={**account, "revision": 1, "enabled": False},
                headers=headers,
            ).status_code
            == 200
        )


def test_workspace_isolation_and_account_disable(client, db):
    headers = login(client)
    role, user, body, account = create_account(client, headers, ["home.view"])
    other = uuid4()
    migrate(db[0], other)
    with psycopg.connect(db[0]) as conn:
        foreign_role = str(uuid4())
        conn.execute(
            "INSERT INTO access_roles(workspace_id,id,name,permissions) "
            "VALUES (%s,%s,'Foreign role','[\"home.view\"]')",
            (other, foreign_role),
        )
    assert (
        client.put(
            f"{BASE}/users/{user}",
            json={**account, "revision": 1, "role_id": foreign_role},
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"{BASE}/roles/{foreign_role}", json={**body, "revision": 1}, headers=headers
        ).status_code
        == 409
    )
    assert foreign_role not in {role}
    with TestClient(client.app) as member:
        user_login(member)
        assert (
            client.put(
                f"{BASE}/users/{user}",
                json={**account, "revision": 1, "enabled": False},
                headers=headers,
            ).status_code
            == 200
        )
        assert member.get("/api/v1/session").status_code == 401
        assert (
            member.post(
                "/api/v1/session/user",
                json={"username": "test-user", "password": PASSWORD},
                headers=ORIGIN,
            ).status_code
            == 401
        )

def test_audit_pagination_filters_and_workspace_isolation(client, db):
    headers = login(client)
    role, user, _, _ = create_account(client, headers, ["home.view"])
    with psycopg.connect(db[0]) as conn:
        conn.execute("DELETE FROM access_audit WHERE workspace_id=%s", (db[1],))
        for _ in range(105):
            conn.execute(
                "INSERT INTO access_audit(workspace_id,actor,event,target) VALUES (%s,%s,%s,%s)",
                (db[1], "local-owner", "user_saved", user),
            )
        conn.execute(
            "INSERT INTO access_audit(workspace_id,actor,event,target,created_at) "
            "VALUES (%s,%s,%s,%s,now()-interval '100 days')",
            (db[1], "local-development", "role_saved", role),
        )
        other = uuid4()
        conn.execute("INSERT INTO registry_workspaces(id) VALUES (%s)", (other,))
        conn.execute(
            "INSERT INTO access_audit(workspace_id,actor,event,target) "
            "VALUES (%s,'hidden','user_saved','hidden')",
            (other,),
        )
    path = BASE + "/audit"
    first = client.get(path).json()
    assert first["total"] == 106 and first["pages"] == 11 and len(first["items"]) == 10
    last = client.get(path, params={"page": 999}).json()
    assert last["page"] == 11 and len(last["items"]) == 6
    second = client.get(path, params={"page": 2}).json()
    assert set(e["id"] for e in first["items"]).isdisjoint(e["id"] for e in second["items"])
    assert client.get(path, params={"q": "Test user"}).json()["filtered_total"] == 105
    assert client.get(path, params={"q": "%"}).json()["filtered_total"] == 0
    assert client.get(path, params={"event": "role_saved"}).json()["filtered_total"] == 1
    assert client.get(path, params={"days": 90}).json()["filtered_total"] == 105
    assert client.get(path, params={"days": 3}).status_code == 422
    assert client.get(path, params={"page": 0}).status_code == 422
    assert client.get(path, params={"event": "bad"}).status_code == 422
    with TestClient(client.app) as member:
        assert member.get(path).status_code == 401
        user_login(member)
        assert member.get(path).status_code == 403
