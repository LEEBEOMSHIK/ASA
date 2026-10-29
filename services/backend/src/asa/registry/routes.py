from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import AgentDraft


def registry_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def repo(principal: Principal = Depends(sessions.principal)) -> RegistryRepository:
        return RegistryRepository(settings.database_url, principal.workspace_id)

    def revision(if_match: str | None = Header(default=None)) -> int:
        if if_match is None:
            raise HTTPException(428, "if_match_required")
        value = if_match.strip('"')
        if not value.isdigit() or len(value) > 9 or int(value) < 1:
            raise HTTPException(422, "invalid_revision")
        return int(value)

    @router.get("/model-profiles")
    def profiles(principal: Principal = Depends(sessions.principal)) -> list[dict[str, Any]]:
        return [
            {
                "id": "default",
                "name": "기본 서버 모델",
                "provider": settings.ai_provider,
                "model": settings.ai_model or None,
                "configured": bool(settings.ai_model and settings.ai_api_key.get_secret_value()),
                "execution_available": False,
            }
        ]

    @router.get("/ai-models")
    def ai_models(principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        providers = [{"id": provider, "label": label,
                      "configured": bool(settings.key_for(provider).get_secret_value().strip()),
                      "web_search_available": True}
                     for provider, label in [("openai", "OpenAI"), ("anthropic", "Claude")]]
        return {
            "models": [{"id": m, "label": m, "provider": p["id"],
                        "web_search": settings.search_supported(str(p["id"]), m)}
                       for p in providers for m in settings.models_for(str(p["id"]))],
            "providers": providers,
            "default_model": settings.ai_model or None,
            "configured": any(p["configured"] for p in providers),
        }

    @router.get("/tools")
    def tools(repository: RegistryRepository = Depends(repo)) -> list[dict[str, Any]]:
        return repository.tools()

    @router.get("/tools/{tool_id}")
    def tool(tool_id: str, repository: RegistryRepository = Depends(repo)) -> dict[str, Any]:
        for item in repository.tools():
            if item["id"] == tool_id:
                return item
        raise HTTPException(404, "tool_not_found")

    @router.get("/agents")
    def agents(repository: RegistryRepository = Depends(repo)) -> list[dict[str, Any]]:
        return repository.list_agents()

    @router.post("/agents", status_code=201)
    def create(body: AgentDraft, repository: RegistryRepository = Depends(repo)) -> dict[str, Any]:
        return repository.create(body)

    @router.get("/agents/{agent_id}")
    def get(agent_id: UUID, repository: RegistryRepository = Depends(repo)) -> dict[str, Any]:
        return repository.get(str(agent_id))

    @router.patch("/agents/{agent_id}/draft")
    def update(
        agent_id: UUID,
        body: AgentDraft,
        expected: int = Depends(revision),
        repository: RegistryRepository = Depends(repo),
    ) -> dict[str, Any]:
        return repository.update(str(agent_id), expected, body)

    @router.post("/agents/{agent_id}/validate")
    def validate(agent_id: UUID, repository: RegistryRepository = Depends(repo)) -> dict[str, Any]:
        return {"issues": repository.validate(str(agent_id))}

    @router.post("/agents/{agent_id}/publish", status_code=201)
    def publish(
        agent_id: UUID,
        expected: int = Depends(revision),
        repository: RegistryRepository = Depends(repo),
    ) -> dict[str, Any]:
        return repository.publish(str(agent_id), expected)

    return router
