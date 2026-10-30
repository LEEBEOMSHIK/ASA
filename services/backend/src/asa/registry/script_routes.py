from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from starlette.responses import StreamingResponse

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.model_catalog import effective_settings
from asa.registry.script_queue import ScriptQueue
from asa.registry.script_stage import (
    ApproveScript,
    GenerateScript,
    SaveScript,
)
from asa.registry.sse import snapshot_stream


def script_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/work-requests/{request_id}/script")

    def repo(principal: Principal = Depends(sessions.principal)) -> ScriptQueue:
        return ScriptQueue(settings.model_copy(update={"workspace_id": principal.workspace_id}))

    @router.get("")
    def get(request_id: UUID, repository: ScriptQueue = Depends(repo)) -> dict[str, Any]:
        result = repository.progress(str(request_id))
        config = effective_settings(
            settings.model_copy(update={"workspace_id": repository.workspace_id})
        )
        with repository._connect() as conn:
            agent = repository._request(conn, str(request_id))["definition"]
        provider = agent.get("provider") or config.ai_provider
        model = agent.get("model") or config.ai_model
        result["model_configured"] = bool(
            model in config.models_for(provider)
            and config.key_for(provider).get_secret_value().strip()
        )
        return result

    @router.get("/events")
    def events(request_id: UUID, request: Request,
               repository: ScriptQueue = Depends(repo)) -> StreamingResponse:
        def load() -> dict[str, Any]:
            sessions.principal(request)
            return get(request_id, repository)
        return snapshot_stream(request, load, repository.dsn, repository.workspace_id)

    @router.post("/start", status_code=201)
    def start(request_id: UUID, repository: ScriptQueue = Depends(repo)) -> dict[str, Any]:
        return repository.submit(str(request_id))

    @router.post("/versions", status_code=201)
    def save(
        request_id: UUID, body: SaveScript, repository: ScriptQueue = Depends(repo)
    ) -> dict[str, Any]:
        return repository.save(str(request_id), body)

    @router.post("/generate", status_code=201)
    def generate(
        request_id: UUID, body: GenerateScript, repository: ScriptQueue = Depends(repo)
    ) -> dict[str, Any]:
        if settings.script_ai_enabled:
            return repository.submit(str(request_id), body)
        return repository.queue(str(request_id), body)

    @router.post("/approve")
    def approve(
        request_id: UUID, body: ApproveScript, repository: ScriptQueue = Depends(repo)
    ) -> dict[str, Any]:
        return repository.approve(str(request_id), body)

    @router.post("/attempts/{attempt_id}/cancel")
    def cancel(
        request_id: UUID, attempt_id: UUID, repository: ScriptQueue = Depends(repo)
    ) -> dict[str, Any]:
        return repository.cancel(str(request_id), attempt_id)

    return router
