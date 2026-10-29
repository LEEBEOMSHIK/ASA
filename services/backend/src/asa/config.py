from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASA_", env_file=".env", extra="ignore")
    database_url: str = ""
    ai_provider: Literal["openai"] = "openai"
    ai_model: str = ""
    ai_models: list[str] = Field(default_factory=list)
    ai_api_key: SecretStr = SecretStr("")
    openai_web_search_models: list[str] = Field(default_factory=list)
    anthropic_web_search_models: list[str] = Field(default_factory=list)
    anthropic_models: list[str] = Field(default_factory=list)
    anthropic_api_key: SecretStr = SecretStr("")
    ai_timeout_seconds: float = Field(default=60, gt=0, le=300)
    automation_ai_enabled: bool = False
    automation_daily_ai_calls: int = Field(default=20, ge=1, le=100)
    automation_output_tokens: int = Field(default=2048, ge=256, le=8192)
    search_provider: Literal["brave"] = "brave"
    search_api_key: SecretStr = SecretStr("")
    search_enabled: bool = False
    ffmpeg_path: str = "ffmpeg"
    owner_access_key: SecretStr = SecretStr("")
    workspace_id: UUID = UUID("a5a00000-0000-4000-8000-000000000001")
    allowed_origins: list[str] = [
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://localhost:3000",
        "http://localhost:3001",
    ]
    secure_cookie: bool = False
    environment: Literal["development", "production"] = "production"
    dev_login_enabled: bool = False

    def allowed_ai_models(self) -> list[str]:
        return list(dict.fromkeys(m for m in [self.ai_model, *self.ai_models] if m.strip()))

    def models_for(self, provider: str) -> list[str]:
        if provider == "openai":
            return self.allowed_ai_models()
        if provider == "anthropic":
            return list(dict.fromkeys(m for m in self.anthropic_models if m.strip()))
        return []

    def key_for(self, provider: str) -> SecretStr:
        if provider == "openai":
            return self.ai_api_key
        if provider == "anthropic":
            return self.anthropic_api_key
        raise ValueError("unsupported_provider")

    def search_supported(self, provider: str, model: str) -> bool:
        allowed = (self.openai_web_search_models if provider == "openai"
                   else self.anthropic_web_search_models if provider == "anthropic" else [])
        return model in allowed and model in self.models_for(provider)
