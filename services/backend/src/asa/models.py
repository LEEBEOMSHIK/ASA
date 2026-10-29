from typing import Annotated

from pydantic import BaseModel, ConfigDict, StrictBool, StringConstraints

PromptText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class DraftRequest(BaseModel):
    prompt: PromptText


class Script(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    narration: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=6000)
    ]


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: StrictBool
