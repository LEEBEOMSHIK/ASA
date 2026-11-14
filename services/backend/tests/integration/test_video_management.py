import pytest
from fastapi.testclient import TestClient
from test_registry_db import KEY, login
from test_registry_db import client as client_fixture
from test_registry_db import db as database_fixture

from asa.api import create_app
from asa.config import Settings
from asa.worker_control import WorkerControl

db = database_fixture
client = client_fixture


def test_management_enable_is_configuration_only_and_revision_checked(db, monkeypatch):
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        environment="development", owner_access_key=KEY,
                        allowed_origins=["http://testserver"], video_ai_enabled=False)
    launches = []
    monkeypatch.setattr(WorkerControl, "launch", lambda *args: launches.append(args))
    with TestClient(create_app(settings)) as client:
        path = "/api/v1/video-management"
        assert client.get(path).status_code == 401
        headers = login(client)
        data = client.get(path).json()
        assert data["enabled"] is False
        payload = {"enabled": True, "revision": data["revision"],
                   "providers": {"runway": True, "alibaba": True}}
        assert client.put(path, json=payload).status_code == 403
        result = client.put(path, json=payload, headers=headers)
        assert result.status_code == 200, result.text
        assert result.json()["enabled"] is True
        assert client.get("/api/v1/video-planning/models").json()["enabled"] is True
        assert launches == []
        assert client.put(path, json=payload, headers=headers).status_code == 409
        payload["revision"] = result.json()["revision"]
        payload["enabled"] = False
        assert client.put(path, json=payload, headers=headers).status_code == 200
        assert launches == []
        monkeypatch.setattr(WorkerControl, "status", lambda *args: {"state": "external"})
        payload["revision"] += 1
        assert client.put(path, json=payload, headers=headers).status_code == 409


@pytest.mark.parametrize("role", ["member", "viewer"])
def test_management_requires_admin(db, monkeypatch, role):
    from asa.auth.session import OwnerSessions, Principal
    monkeypatch.setattr(OwnerSessions, "principal", lambda self: Principal("u", db[1], (role,)))
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                        environment="development")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/video-management").json()["can_manage"] is False
        assert client.put("/api/v1/video-management", json={"enabled": True, "revision": 0,
                          "providers": {"runway": True, "alibaba": True}}).status_code == 403


def test_disabled_queue_requires_resume_but_running_result_is_collected(client, db, monkeypatch):
    import httpx
    import psycopg
    from psycopg.rows import dict_row
    from test_registry_db import test_wan_queue_worker_lifecycle as seed

    from asa import video_worker

    seed(client, db, monkeypatch, "success")
    cfg = Settings(_env_file=None, database_url=db[0], workspace_id=db[1],
                   owner_access_key=KEY, allowed_origins=["http://testserver"],
                   environment="development", video_ai_enabled=True,
                   wan_api_key="test-wan", wan_workspace_id="ws-test")
    calls = []

    def respond(request):
        calls.append(request.method)
        return httpx.Response(200, json={"output": {
            "task_id": "managed-task", "task_status": "SUCCEEDED",
            "video_url": "https://example.com/video.mp4"}})

    with psycopg.connect(db[0], autocommit=True, row_factory=dict_row) as conn:
        conn.execute("UPDATE video_clip_jobs SET status='queued',next_poll=now()")
        with TestClient(create_app(cfg)) as api_client:
            headers = login(api_client)
            path = "/api/v1/video-management"

            def set_enabled(value):
                state = api_client.get(path).json()
                result = api_client.put(path, headers=headers, json={
                    "enabled": value, "revision": state["revision"],
                    "providers": state["providers"]})
                assert result.status_code == 200, result.text
                return result.json()

            with httpx.Client(transport=httpx.MockTransport(respond)) as http:
                assert set_enabled(False)["counts"]["paused"] == 1
                assert not video_worker.process(conn, http, db[1], cfg)
                assert set_enabled(True)["counts"]["paused"] == 1
                assert not video_worker.process(conn, http, db[1], cfg)
                assert calls == []
                assert api_client.post(path + "/resume", headers=headers).status_code == 200
                assert video_worker.process(conn, http, db[1], cfg)
                assert calls == ["POST"]
                set_enabled(False)
                conn.execute("UPDATE video_clip_jobs SET next_poll=now()")
                assert video_worker.process(conn, http, db[1], cfg)
                assert calls == ["POST", "GET"]
                assert conn.execute("SELECT status FROM video_clip_jobs").fetchone()[
                    "status"] == "review"
