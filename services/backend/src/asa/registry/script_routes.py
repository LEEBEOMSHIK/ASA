from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.script_stage import (
    ApproveScript,
    GenerateScript,
    SaveScript,
    ScriptRepository,
)


def script_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/work-requests/{request_id}/script")

    def repo(principal: Principal = Depends(sessions.principal)) -> ScriptRepository:
        return ScriptRepository(settings.database_url, principal.workspace_id)

    @router.get("")
    def get(request_id: UUID, repository: ScriptRepository = Depends(repo)) -> dict[str, Any]:
        result = repository.get(str(request_id))
        result["model_configured"] = bool(settings.ai_model.strip()
                                          and settings.ai_api_key.get_secret_value().strip())
        return result

    @router.post("/versions", status_code=201)
    def save(request_id: UUID, body: SaveScript,
             repository: ScriptRepository = Depends(repo)) -> dict[str, Any]:
        return repository.save(str(request_id), body)

    @router.post("/generate", status_code=201)
    def generate(request_id: UUID, body: GenerateScript,
                 repository: ScriptRepository = Depends(repo)) -> dict[str, Any]:
        return repository.queue(str(request_id), body)

    @router.post("/approve")
    def approve(request_id: UUID, body: ApproveScript,
                repository: ScriptRepository = Depends(repo)) -> dict[str, Any]:
        return repository.approve(str(request_id), body)

    @router.post("/attempts/{attempt_id}/cancel")
    def cancel(request_id: UUID, attempt_id: UUID,
               repository: ScriptRepository = Depends(repo)) -> dict[str, Any]:
        return repository.cancel(str(request_id), attempt_id)

    return router
