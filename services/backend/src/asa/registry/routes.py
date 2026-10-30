from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.model_catalog import effective_settings, read_catalog, validate_selection
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
        config = effective_settings(
            settings.model_copy(update={"workspace_id": principal.workspace_id})
        )
        return [
            {
                "id": "default",
                "name": "작업 공간 기본 모델",
                "provider": config.ai_provider,
                "model": config.ai_model or None,
                "configured": bool(
                    config.ai_model and config.key_for(config.ai_provider).get_secret_value()
                ),
                "execution_available": False,
            }
        ]

    @router.get("/ai-models")
    def ai_models(principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        config = settings.model_copy(update={"workspace_id": principal.workspace_id})
        catalog = read_catalog(config)
        provider, _, model = catalog.default.partition(":")
        providers = [
            {
                "id": p,
                "label": label,
                "configured": bool(config.key_for(p).get_secret_value().strip()),
                "web_search_available": True,
            }
            for p, label in [("openai", "OpenAI"), ("anthropic", "Claude")]
        ]
        return {
            "models": [
                {"id": m.id, "label": m.label, "provider": m.provider, "web_search": m.web_search}
                for m in catalog.models
                if m.enabled
            ],
            "providers": providers,
            "default_model": model or None,
            "default_provider": provider or "openai",
            "configured": any(p["configured"] for p in providers),
        }

    def check_model(body: AgentDraft, repository: RegistryRepository) -> None:
        config = effective_settings(
            settings.model_copy(update={"workspace_id": repository.workspace_id})
        )
        validate_selection(config, body.provider, body.model)

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
        check_model(body, repository)
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
        check_model(body, repository)
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
        check_model(AgentDraft.model_validate(repository.get(str(agent_id))["draft"]), repository)
        return repository.publish(str(agent_id), expected)

    return router
