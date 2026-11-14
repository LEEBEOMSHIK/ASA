from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from test_registry_db import db as database_fixture

from asa.config import Settings
from asa.worker_control import WorkerControl, run_worker

db = database_fixture


@pytest.mark.parametrize("kind", ["script", "image", "audio", "video"])
def test_stop_finishes_current_job_and_does_not_take_next(db, monkeypatch, kind):
    settings = Settings(
        _env_file=None,
        database_url=db[0],
        workspace_id=db[1],
        environment="development",
        script_ai_enabled=True,
        image_ai_enabled=True,
    )
    control = WorkerControl(settings)
    launches = []
    monkeypatch.setattr(control, "launch", lambda kind, token: launches.append(token))
    control.start(kind)
    control.start(kind)
    assert len(launches) == 1
    entered, finish = Event(), Event()
    calls = []

    def tick():
        calls.append(1)
        entered.set()
        assert finish.wait(10)
        return True

    with ThreadPoolExecutor() as pool:
        future = pool.submit(run_worker, settings, kind, tick, launches[0])
        assert entered.wait(10)
        control.stop(kind)
        assert control.status(kind)["state"] == "stopping"
        assert not future.done()
        finish.set()
        future.result(timeout=10)
    assert calls == [1]
    assert control.status(kind)["state"] == "stopped"
    other = "image" if kind == "script" else "script"
    assert control.status(other)["state"] == "stopped"


def test_cancel_start_before_child_arrives(db, monkeypatch):
    settings = Settings(
        _env_file=None,
        database_url=db[0],
        workspace_id=db[1],
        environment="development",
        script_ai_enabled=True,
    )
    control = WorkerControl(settings)
    tokens = []
    monkeypatch.setattr(control, "launch", lambda kind, token: tokens.append(token))
    control.start("script")
    control.stop("script")
    calls = []
    run_worker(settings, "script", lambda: calls.append(1), tokens[0])
    assert not calls
    assert control.status("script")["state"] == "stopped"


def test_worker_routes_permissions_validation_and_csrf(db, monkeypatch):
    from uuid import uuid4

    from fastapi.testclient import TestClient
    from test_registry_db import KEY, ORIGIN, login

    from asa.api import create_app
    from asa.auth.session import OwnerSessions, Principal

    settings = Settings(
        _env_file=None,
        database_url=db[0],
        workspace_id=db[1],
        environment="development",
        script_ai_enabled=True,
        owner_access_key=KEY,
        allowed_origins=["http://testserver"],
    )
    launches = []
    monkeypatch.setattr(WorkerControl, "launch", lambda self, kind, token: launches.append(token))
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/v1/agent-worker/script/start", json={}).status_code == 401
        headers = login(client)
        assert (
            client.post("/api/v1/agent-worker/script/start", json={}, headers=ORIGIN).status_code
            == 403
        )
        assert (
            client.post("/api/v1/agent-worker/other/start", json={}, headers=headers).status_code
            == 422
        )
        assert (
            client.post("/api/v1/agent-worker/script/start", json={}, headers=headers).status_code
            == 200
        )
        assert (
            client.post("/api/v1/agent-worker/image/start", json={}, headers=headers).status_code
            == 409
        )
        assert len(launches) == 1
    for roles, workspace in [(("member",), db[1]), (("owner",), uuid4())]:
        monkeypatch.setattr(
            OwnerSessions, "principal", lambda self: Principal("u", workspace, roles)
        )
        with TestClient(create_app(settings)) as client:
            assert client.post("/api/v1/agent-worker/script/stop", json={}).status_code == 403
    monkeypatch.setattr(OwnerSessions, "principal", lambda self: Principal("u", db[1]))
    with TestClient(
        create_app(settings.model_copy(update={"environment": "production"}))
    ) as client:
        assert client.post("/api/v1/agent-worker/script/start", json={}).status_code == 403


def test_failed_spawn_can_retry_and_stale_child_cannot_stop_new_instance(db, monkeypatch):
    from asa.registry.schemas import RegistryError

    settings = Settings(
        _env_file=None,
        database_url=db[0],
        workspace_id=db[1],
        environment="development",
        script_ai_enabled=True,
    )
    control = WorkerControl(settings)
    tokens = []

    def fail(kind, token):
        tokens.append(token)
        raise OSError("secret path must not be exposed")

    monkeypatch.setattr(control, "launch", fail)
    with pytest.raises(RegistryError) as error:
        control.start("script")
    assert error.value.code == "worker_start_failed"
    assert control.status("script")["state"] == "failed"
    monkeypatch.setattr(control, "launch", lambda kind, token: tokens.append(token))
    control.start("script")
    control.finish("script", tokens[0])
    assert control.status("script")["state"] == "starting"


@pytest.mark.parametrize("kind", ["script", "image", "audio", "video"])
def test_real_empty_worker_process_start_and_stop(db, kind):
    import time

    settings = Settings(
        _env_file=None,
        database_url=db[0],
        workspace_id=db[1],
        environment="development",
        script_ai_enabled=True,
        image_ai_enabled=True,
    )
    control = WorkerControl(settings)
    control.start(kind)
    try:
        deadline = time.monotonic() + 25
        while control.status(kind)["state"] != "running" and time.monotonic() < deadline:
            time.sleep(0.1)
        assert control.status(kind)["state"] == "running"
    finally:
        control.stop(kind)
        deadline = time.monotonic() + 15
        while control.status(kind)["state"] != "stopped" and time.monotonic() < deadline:
            time.sleep(0.1)
    assert control.status(kind)["state"] == "stopped"


def test_stop_before_concrete_claim_preserves_queued_work(db, monkeypatch):
    from asa.registry.script_stage import ScriptRepository

    settings = Settings(
        _env_file=None,
        database_url=db[0],
        workspace_id=db[1],
        environment="development",
        script_ai_enabled=True,
    )
    control = WorkerControl(settings)
    tokens = []
    monkeypatch.setattr(control, "launch", lambda kind, token: tokens.append(token))
    control.start("script")
    entered, proceed = Event(), Event()
    repo = ScriptRepository(db[0], db[1])
    touched = []
    monkeypatch.setattr(repo, "_request", lambda *args: touched.append(True))

    def tick():
        entered.set()
        assert proceed.wait(10)
        assert repo.claim(str(db[1]), str(db[1]), "test", "test") is None
        return False

    with ThreadPoolExecutor() as pool:
        future = pool.submit(run_worker, settings, "script", tick, tokens[0])
        assert entered.wait(10)
        control.stop("script")
        proceed.set()
        future.result(timeout=10)
    assert touched == []


def test_stop_serializes_with_first_start_transaction(db):
    import time
    from uuid import uuid4

    from asa.database import connection

    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1])
    control = WorkerControl(settings)
    entered = Event()

    def stop():
        entered.set()
        control.stop("script")

    with ThreadPoolExecutor() as pool:
        with connection(db[0]) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (control.key("script") + ":control",),
            )
            future = pool.submit(stop)
            assert entered.wait(5)
            time.sleep(0.1)
            assert not future.done()
            conn.execute(
                "INSERT INTO local_worker_controls(workspace_id,kind,token,desired,state) "
                "VALUES (%s,'script',%s,true,'starting')",
                (db[1], uuid4()),
            )
        future.result(timeout=5)
    assert control.status("script")["state"] == "stopping"
