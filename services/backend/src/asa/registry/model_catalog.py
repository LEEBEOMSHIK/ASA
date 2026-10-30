"""Workspace model policy; credentials remain in server configuration."""

from contextlib import nullcontext
from typing import Any, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from asa.auth.session import OwnerSessions, Principal
from asa.config import ModelPrice, Settings
from asa.registry.model_discovery import ModelMetadata, Provider, discover, metadata
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError


class ModelEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    provider: Literal["openai", "anthropic"]
    id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
    label: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    web_search: bool = False
    price: ModelPrice | None = None
    metadata: ModelMetadata | None = None


class RegisterModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    model: ModelEntry


class Catalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(default=0, ge=0)
    models: list[ModelEntry] = Field(default_factory=list, max_length=100)
    default: str = ""

    @model_validator(mode="after")
    def valid(self) -> "Catalog":
        keys = [f"{m.provider}:{m.id}" for m in self.models]
        if len(keys) != len(set(keys)):
            raise ValueError("같은 공급자의 모델 ID가 중복됩니다.")
        if self.default and self.default not in {
            f"{m.provider}:{m.id}" for m in self.models if m.enabled
        }:
            raise ValueError("기본 모델은 활성 모델 중에서 선택하세요.")
        return self


def read_catalog(settings: Settings,
                 connection: psycopg.Connection[dict[str, Any]] | None = None) -> Catalog:
    if settings.database_url:
        context = (nullcontext(connection) if connection is not None else
                   RegistryRepository(settings.database_url, settings.workspace_id)._connect())
        with context as conn:
            row = conn.execute(
                "SELECT revision,definition FROM workspace_model_catalog WHERE workspace_id=%s",
                (settings.workspace_id,),
            ).fetchone()
        if row:
            return Catalog.model_validate({**row["definition"], "revision": row["revision"]})
    providers: tuple[Literal["openai", "anthropic"], ...] = ("openai", "anthropic")
    return Catalog(
        models=[
            ModelEntry(
                provider=p,
                id=m,
                label=m,
                web_search=settings.search_supported(p, m),
                price=settings.ai_prices.get(f"{p}:{m}"),
            )
            for p in providers
            for m in settings.models_for(p)
        ],
        default=f"{settings.ai_provider}:{settings.ai_model}" if settings.ai_model else "",
    )


def effective_settings(settings: Settings,
                       connection: psycopg.Connection[dict[str, Any]] | None = None) -> Settings:
    catalog = read_catalog(settings, connection)
    active = [m for m in catalog.models if m.enabled]
    provider, _, model = catalog.default.partition(":")
    return settings.model_copy(
        update={
            "ai_provider": provider or "openai",
            "ai_model": model,
            "ai_models": [m.id for m in active if m.provider == "openai"],
            "anthropic_models": [m.id for m in active if m.provider == "anthropic"],
            "openai_web_search_models": [
                m.id for m in active if m.provider == "openai" and m.web_search
            ],
            "anthropic_web_search_models": [
                m.id for m in active if m.provider == "anthropic" and m.web_search
            ],
            "ai_prices": {f"{m.provider}:{m.id}": m.price for m in catalog.models if m.price},
        }
    )


def validate_selection(settings: Settings, provider: str | None, model: str | None) -> None:
    if (provider is None) != (model is None) or (
        model is not None and model not in settings.models_for(provider or "openai")
    ):
        raise RegistryError(422, "invalid_model_selection")


def model_catalog_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/admin/models")

    def scoped(principal: Principal = Depends(sessions.principal)) -> Settings:
        if not {"owner", "admin"}.intersection(principal.roles):
            raise HTTPException(403, "admin_required")
        return settings.model_copy(update={"workspace_id": principal.workspace_id})

    @router.get("")
    def get(config: Settings = Depends(scoped)) -> dict[str, Any]:
        return {
            **read_catalog(config).model_dump(mode="json"),
            "providers": [
                {"id": p, "configured": bool(config.key_for(p).get_secret_value().strip())}
                for p in ("openai", "anthropic")
            ],
        }

    @router.get("/discover/{provider}")
    def discover_models(provider: Provider, config: Settings = Depends(scoped)) -> dict[str, Any]:
        return discover(config, provider)

    @router.get("/metadata/{provider}")
    def model_metadata(
        provider: Provider, model: str, config: Settings = Depends(scoped)
    ) -> ModelMetadata:
        return metadata(provider, model)

    @router.post("", status_code=201)
    def register(body: RegisterModel, config: Settings = Depends(scoped)) -> dict[str, Any]:
        with RegistryRepository(config.database_url, config.workspace_id)._connect() as conn:
            conn.execute(
                "SELECT id FROM registry_workspaces WHERE id=%s FOR UPDATE", (config.workspace_id,)
            )
            catalog = read_catalog(config, conn)
            if body.revision != catalog.revision:
                raise RegistryError(409, "revision_conflict")
            if any(
                m.provider == body.model.provider and m.id == body.model.id for m in catalog.models
            ):
                raise RegistryError(409, "model_already_registered")
            if len(catalog.models) >= 100:
                raise RegistryError(422, "model_catalog_full")
            catalog = Catalog(
                revision=catalog.revision + 1,
                default=catalog.default,
                models=[*catalog.models, body.model],
            )
            conn.execute(
                "INSERT INTO workspace_model_catalog(workspace_id,revision,definition) "
                "VALUES (%s,%s,%s) ON CONFLICT(workspace_id) DO UPDATE SET "
                "revision=EXCLUDED.revision,definition=EXCLUDED.definition",
                (
                    config.workspace_id,
                    catalog.revision,
                    Jsonb(catalog.model_dump(mode="json", exclude={"revision"})),
                ),
            )
        return catalog.model_dump(mode="json")

    @router.put("")
    def save(body: Catalog, config: Settings = Depends(scoped)) -> dict[str, Any]:
        with RegistryRepository(config.database_url, config.workspace_id)._connect() as conn:
            conn.execute(
                "SELECT id FROM registry_workspaces WHERE id=%s FOR UPDATE", (config.workspace_id,)
            )
            row = conn.execute(
                "SELECT revision FROM workspace_model_catalog WHERE workspace_id=%s",
                (config.workspace_id,),
            ).fetchone()
            if body.revision != (row["revision"] if row else 0):
                raise RegistryError(409, "revision_conflict")
            revision = body.revision + 1
            conn.execute(
                "INSERT INTO workspace_model_catalog(workspace_id,revision,definition) "
                "VALUES (%s,%s,%s) ON CONFLICT(workspace_id) DO UPDATE SET "
                "revision=EXCLUDED.revision,definition=EXCLUDED.definition",
                (
                    config.workspace_id,
                    revision,
                    Jsonb(body.model_dump(mode="json", exclude={"revision"})),
                ),
            )
        return {**body.model_dump(mode="json"), "revision": revision}

    return router
