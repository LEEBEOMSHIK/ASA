from typing import Any, Literal

from fastapi import APIRouter, Depends

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.characters import image_worker_online
from asa.registry.schemas import RegistryError
from asa.registry.script_queue import ScriptQueue
from asa.worker_control import WorkerControl, WorkerKind


def worker_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/agent-worker")
    control = WorkerControl(settings)

    def can_manage(p: Principal) -> bool:
        return bool(settings.environment == "development" and
                    p.workspace_id == settings.workspace_id and
                    {"owner", "admin"}.intersection(p.roles))

    @router.get("/status")
    def status(p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        if p.workspace_id != settings.workspace_id:
            raise RegistryError(403, "workspace_forbidden")
        queue = ScriptQueue(settings)
        with queue._connect() as conn:
            online = queue.worker_online(conn)
            image_online = image_worker_online(conn, queue.workspace_id)
        items = [control.status("script"), control.status("image")]
        # Old processes must be restarted with the updated lifecycle before UI control.
        for item, alive in zip(items, (online, image_online), strict=True):
            if item["state"] == "stopped" and alive:
                item["state"] = "external"
        items.append(control.status("audio"))
        return {"online": online, "image_online": image_online,
                "can_manage": can_manage(p), "workers": items}

    @router.post("/{kind}/{action}")
    def action(kind: WorkerKind, action: Literal["start", "stop"],
               p: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        if not can_manage(p):
            raise RegistryError(403, "worker_control_forbidden")
        item = next(item for item in status(p)["workers"] if item["kind"] == kind)
        if item["state"] == "external":
            raise RegistryError(409, "worker_restart_required")
        if action == "start":
            control.start(kind)
        else:
            control.stop(kind)
        return status(p)

    return router
