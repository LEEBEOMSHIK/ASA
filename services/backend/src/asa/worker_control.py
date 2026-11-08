"""Local worker lifecycle. Stop requests are observed only between complete jobs."""

import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

import psycopg

from asa.config import Settings
from asa.database import connection
from asa.registry.schemas import RegistryError

WorkerKind = Literal["script", "image", "audio"]
MODULES = {
    "script": "asa.script_queue_worker", "image": "asa.image_worker", "audio": "asa.audio_worker"
}


def accepting_work(conn: psycopg.Connection[Any], workspace_id: UUID, kind: WorkerKind) -> bool:
    """Hold the control row until the same transaction commits a concrete job claim."""
    row = conn.execute(
        "SELECT desired FROM local_worker_controls WHERE workspace_id=%s AND kind=%s FOR UPDATE",
        (workspace_id, kind),
    ).fetchone()
    return row is None or bool(row["desired"])


class WorkerControl:
    def __init__(self, settings: Settings):
        self.settings = settings

    def key(self, kind: WorkerKind) -> str:
        return f"asa-worker-lifecycle:{self.settings.workspace_id}:{kind}"

    def status(self, kind: WorkerKind) -> dict[str, Any]:
        with connection(self.settings.database_url, dictionary=True) as conn:
            row = conn.execute(
                "SELECT *,seen_at>now()-interval '20 seconds' AS fresh,"
                "requested_at>now()-interval '60 seconds' AS starting "
                "FROM local_worker_controls WHERE workspace_id=%s AND kind=%s",
                (self.settings.workspace_id, kind),
            ).fetchone()
        enabled = (True if kind == "audio" else self.settings.script_ai_enabled if kind == "script"
                   else self.settings.image_ai_enabled)
        state = "stopped"
        if row:
            state = row["state"]
            if state not in {"stopped", "failed"} and not row["fresh"]:
                if not (state in {"starting", "stopping"} and row["starting"]):
                    state = "offline"
        return {"kind": kind, "state": state, "enabled": enabled,
                "busy": bool(row and row["busy"] and state in {"running", "stopping"})}

    def start(self, kind: WorkerKind) -> None:
        if not self.status(kind)["enabled"]:
            raise RegistryError(409, "worker_generation_disabled")
        token = uuid4()
        with connection(self.settings.database_url) as conn:
            # Serialize API requests, including the interval before the child starts.
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                         (self.key(kind) + ":control",))
            row = conn.execute(
                "SELECT state,requested_at>now()-interval '60 seconds' FROM local_worker_controls "
                "WHERE workspace_id=%s AND kind=%s FOR UPDATE",
                (self.settings.workspace_id, kind),
            ).fetchone()
            if row and row[0] in {"starting", "stopping"} and row[1]:
                if row[0] == "stopping":
                    raise RegistryError(409, "worker_stopping")
                return
            free = conn.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0))",
                                (self.key(kind),)).fetchone()
            if not free or not free[0]:
                return
            conn.execute(
                "INSERT INTO local_worker_controls(workspace_id,kind,token,desired,state) "
                "VALUES (%s,%s,%s,true,'starting') ON CONFLICT(workspace_id,kind) DO UPDATE SET "
                "token=excluded.token,desired=true,state='starting',busy=false,seen_at=NULL,"
                "requested_at=now()",
                (self.settings.workspace_id, kind, token),
            )
        try:
            self.launch(kind, token)
        except OSError:
            self.finish(kind, token, failed=True)
            raise RegistryError(503, "worker_start_failed") from None

    def launch(self, kind: WorkerKind, token: UUID) -> None:
        env = os.environ.copy()
        env.update(ASA_DATABASE_URL=self.settings.database_url,
                   ASA_WORKSPACE_ID=str(self.settings.workspace_id),
                   ASA_SCRIPT_AI_ENABLED=str(self.settings.script_ai_enabled).lower(),
                   ASA_IMAGE_AI_ENABLED=str(self.settings.image_ai_enabled).lower(),
                   ASA_AUDIO_AI_ENABLED=str(self.settings.audio_ai_enabled).lower())
        command = [sys.executable, "-m", MODULES[kind], "--control-token", str(token)]
        if kind == "script":
            command.append("--allow-paid-call")
        # No shell, arbitrary command, secret in argv, or visible console window.
        process = subprocess.Popen(
            command, cwd=Path(__file__).resolve().parents[4], env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
        threading.Thread(target=process.wait, daemon=True).start()

    def stop(self, kind: WorkerKind) -> None:
        with connection(self.settings.database_url) as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                         (self.key(kind) + ":control",))
            conn.execute(
                "UPDATE local_worker_controls SET desired=false,"
                "state=CASE WHEN state IN ('stopped','failed') THEN 'stopped' ELSE 'stopping' END "
                "WHERE workspace_id=%s AND kind=%s", (self.settings.workspace_id, kind),
            )

    def finish(self, kind: WorkerKind, token: UUID, *, failed: bool = False) -> None:
        with connection(self.settings.database_url) as conn:
            updated = conn.execute(
                "UPDATE local_worker_controls SET desired=false,state=%s,busy=false,seen_at=now() "
                "WHERE workspace_id=%s AND kind=%s AND token=%s",
                ("failed" if failed else "stopped", self.settings.workspace_id, kind, token),
            ).rowcount
            if not updated or kind == "audio":
                return
            # A clean exit must not look online for the legacy heartbeat timeout.
            table = "script_worker_status" if kind == "script" else "image_worker_status"
            from psycopg import sql
            conn.execute(sql.SQL("DELETE FROM {} WHERE workspace_id=%s").format(
                sql.Identifier(table)), (self.settings.workspace_id,))


def run_worker(settings: Settings, kind: WorkerKind, tick: Callable[[], bool],
               token: UUID | None = None, *, once: bool = False) -> None:
    control = WorkerControl(settings)
    # Dedicated connection, never returned to a pool with a session lock held.
    with psycopg.connect(settings.database_url, autocommit=True) as lock:
        acquired = lock.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0))",
                                (control.key(kind),)).fetchone()
        if not acquired or not acquired[0]:
            return
        if token is None:
            token = uuid4()
            lock.execute(
                "INSERT INTO local_worker_controls(workspace_id,kind,token,desired,state) "
                "VALUES (%s,%s,%s,true,'running') ON CONFLICT(workspace_id,kind) DO UPDATE SET "
                "token=excluded.token,desired=true,state='running',busy=false,requested_at=now()",
                (settings.workspace_id, kind, token),
            )
        stopped = threading.Event()

        def pulse() -> None:
            while not stopped.wait(5):
                try:
                    with connection(settings.database_url) as conn:
                        conn.execute("UPDATE local_worker_controls SET seen_at=now() "
                                     "WHERE workspace_id=%s AND kind=%s AND token=%s",
                                     (settings.workspace_id, kind, token))
                except Exception:
                    pass  # Never retry an in-flight external call because a heartbeat failed.

        thread = threading.Thread(target=pulse, daemon=True)
        thread.start()
        failed = False
        try:
            while True:
                # This reservation and stop update serialize. Reserved work drains on stop.
                row = lock.execute(
                    "UPDATE local_worker_controls SET state='running',busy=true,seen_at=now() "
                    "WHERE workspace_id=%s AND kind=%s AND token=%s AND desired RETURNING token",
                    (settings.workspace_id, kind, token),
                ).fetchone()
                if not row:
                    break
                try:
                    worked = tick()
                except Exception:
                    if once:
                        raise
                    worked = False
                    print("Worker polling failed; uncertain calls are not replayed.", flush=True)
                lock.execute("UPDATE local_worker_controls SET busy=false WHERE workspace_id=%s "
                             "AND kind=%s AND token=%s", (settings.workspace_id, kind, token))
                if once:
                    break
                if not worked:
                    time.sleep(1)
        except BaseException:
            failed = True
            raise
        finally:
            stopped.set()
            thread.join(timeout=6)
            control.finish(kind, token, failed=failed)
