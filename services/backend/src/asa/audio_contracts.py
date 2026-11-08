"""Versioned audio plans. Display names never identify speakers or assets."""

import hashlib
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")]
Time = Annotated[float, Field(ge=0, le=3600, allow_inf_nan=False)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Voice(Strict):
    model_key: str = Field(default="openai-realtime", min_length=1, max_length=100)
    voice: str = Field(default="marin", min_length=1, max_length=100)
    instructions: str = Field(default="", max_length=1000)
    language: str = Field(default="한국어", min_length=1, max_length=80)
    speed: float = Field(default=1, ge=0.75, le=1.25, allow_inf_nan=False)


class Speaker(Strict):
    id: Identifier
    name: str = Field(min_length=1, max_length=100)
    role: Literal["character", "narrator"] = "character"
    voice: Voice = Field(default_factory=Voice)


class Cue(Strict):
    id: Identifier
    speaker_id: Identifier
    text: str = Field(min_length=1, max_length=1500)
    start: Time
    end: Time
    emotion: str = Field(default="", max_length=300)


class Music(Strict):
    asset_id: UUID | None = None
    offset: Time = 0
    start: Time = 0
    end: Time | None = None
    volume: float = Field(default=0.15, ge=0, le=1, allow_inf_nan=False)
    loop: bool = False
    fade: float = Field(default=1, ge=0, le=10, allow_inf_nan=False)
    duck: bool = True


class AudioSettings(Strict):
    enabled: bool = False
    speakers: list[Speaker] = Field(default_factory=list, max_length=30)
    cues: list[Cue] = Field(default_factory=list, max_length=200)
    music: Music = Field(default_factory=Music)

    @model_validator(mode="after")
    def validate_plan(self) -> "AudioSettings":
        ids = {s.id for s in self.speakers}
        if len(ids) != len(self.speakers) or len({c.id for c in self.cues}) != len(self.cues):
            raise ValueError("audio_duplicate_id")
        previous: dict[str, float] = {}
        for cue in sorted(self.cues, key=lambda c: c.start):
            if cue.speaker_id not in ids or cue.end <= cue.start:
                raise ValueError("audio_cue_invalid")
            if previous.get(cue.speaker_id, 0) > cue.start:
                raise ValueError("audio_cue_overlap")
            previous[cue.speaker_id] = cue.end
        if self.music.end is not None and self.music.end <= self.music.start:
            raise ValueError("audio_music_timing")
        return self


def fingerprint(data: object) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def cue_fingerprint(cue: Cue, speaker: Speaker) -> str:
    return fingerprint(
        {
            "text": cue.text,
            "emotion": cue.emotion,
            "speaker_id": speaker.id,
            "voice": speaker.voice.model_dump(),
        }
    )


def validate_measured(cue: Cue, seconds: float) -> None:
    if seconds <= 0 or seconds > cue.end - cue.start + 0.02:
        raise ValueError("audio_timing_adjustment_required")


class AudioModel(Strict):
    model: str = Field(default="gpt-realtime-2.1-mini", min_length=1, max_length=100)
    label: str = "OpenAI Realtime · 음성"
    voices: list[str] = Field(
        default_factory=lambda: [
            "marin",
            "cedar",
            "alloy",
            "ash",
            "ballad",
            "coral",
            "echo",
            "sage",
            "shimmer",
            "verse",
        ],
        min_length=1,
        max_length=30,
    )
    enabled: bool = True
