from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    model_calls: int = Field(default=10, ge=1, le=20)
    tool_calls: int = Field(default=20, ge=0, le=40)
    depth: int = Field(default=2, ge=0, le=3)
    seconds: int = Field(default=300, ge=1, le=900)


class AgentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=400)
    instructions: str = Field(min_length=1, max_length=8000)
    model_profile: str = Field(default="default", min_length=1, max_length=80)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    tools: list[str] = Field(default_factory=list, max_length=40)
    limits: Limits = Field(default_factory=Limits)


class ValidationIssue(BaseModel):
    code: str
    field_path: str
    message: str


class RegistryError(Exception):
    def __init__(self, status: int, code: str, issues: list[ValidationIssue] | None = None):
        self.status = status
        self.code = code
        self.issues = issues or []
        super().__init__(code)
