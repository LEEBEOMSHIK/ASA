"""Provider-neutral video planning contracts. No paid calls or automatic retries."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VideoModelProfile(BaseModel):
    """One verified provider/model/mode/resolution combination, not a model family."""

    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=160)
    revision: str = Field(min_length=1, max_length=80)
    enabled: bool = False
    durations: list[int] = Field(min_length=1, max_length=120)
    aspect_ratios: list[str] = Field(min_length=1, max_length=10)
    resolution: str = Field(min_length=1, max_length=40)
    max_prompt_chars: int = Field(gt=0, le=32000)
    supports_audio: bool = False
    usd_per_second: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    supports_extension: bool = False
    documentation_url: str = Field(pattern=r"^https://", max_length=500)
    verified_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def validate_durations(self) -> "VideoModelProfile":
        if any(d <= 0 or d > 120 for d in self.durations):
            raise ValueError("video_duration_out_of_range")
        if len(set(self.durations)) != len(self.durations):
            raise ValueError("video_duplicate_duration")
        return self


class VideoClip(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clip_id: str = Field(min_length=1, max_length=100)
    scene_id: str = Field(min_length=1, max_length=100)
    shot_id: str = Field(min_length=1, max_length=100)
    image_id: UUID
    # Source timeline and provider duration differ when the provider uses fixed lengths.
    source_start_seconds: int = Field(ge=0, le=86400)
    source_end_seconds: int = Field(gt=0, le=86400)
    duration_seconds: int = Field(gt=0, le=120)
    prompt: str = Field(min_length=1, max_length=32000)
    source_excerpt: str = Field(max_length=8000)
    continuity_in: str = Field(max_length=2000)
    continuity_out: str = Field(max_length=2000)
    split_reason: str = Field(max_length=1000)
    style_application: str = Field(default="", max_length=700)
    edit_notes: str = Field(default="", max_length=700)

    @model_validator(mode="after")
    def validate_span(self) -> "VideoClip":
        span = self.source_end_seconds - self.source_start_seconds
        if span <= 0 or span > self.duration_seconds:
            raise ValueError("video_clip_timeline_invalid")
        return self


class VideoPreparation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_key: str = Field(min_length=1, max_length=100)
    model_revision: str = Field(min_length=1, max_length=80)
    aspect_ratio: str = Field(min_length=1, max_length=20)
    audio: bool = False
    mode: Literal["image_to_video"] = "image_to_video"
    clips: list[VideoClip] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_sequence(self) -> "VideoPreparation":
        if len({c.clip_id for c in self.clips}) != len(self.clips):
            raise ValueError("video_duplicate_clip")
        previous_end = 0
        for clip in self.clips:
            if clip.source_start_seconds != previous_end:
                raise ValueError("video_timeline_gap_or_overlap")
            previous_end = clip.source_end_seconds
        return self


def duration_plan(seconds: int, allowed: list[int]) -> list[dict[str, int]]:
    """Propose durations with minimal padding, then minimal calls; never split prose."""
    if not 1 <= seconds <= 3600 or not allowed or any(d <= 0 or d > 120 for d in allowed):
        raise ValueError("video_duration_plan_invalid")
    bound = seconds + max(allowed)
    best: dict[int, list[int]] = {0: []}
    for total in range(1, bound):
        candidates = [best[total - d] + [d] for d in sorted(set(allowed), reverse=True)
                      if total - d in best]
        if candidates:
            best[total] = min(candidates, key=len)
    target = next(total for total in range(seconds, bound) if total in best)
    remaining = seconds
    result = []
    for duration in best[target]:
        used = min(remaining, duration)
        result.append({"duration_seconds": duration, "usable_seconds": used,
                       "trim_seconds": duration - used})
        remaining -= used
    return result
