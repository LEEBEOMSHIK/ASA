"""Versioned, bounded edit instructions. No paths, URLs or executable expressions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SOURCE = r"^(video|reference|image|audio|music):[0-9a-fA-F-]{36}$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Segment(Strict):
    label: str = Field(default="", max_length=120)
    source_id: str = Field(pattern=SOURCE)
    start: float = Field(ge=0, le=3600)
    duration: float = Field(ge=0.1, le=600)
    motion: Literal["static", "zoom_in", "zoom_out"]
    transition: Literal["cut", "fade"]
    volume: float = Field(ge=0, le=2)
    caption: str = Field(max_length=160)


class Track(Strict):
    label: str = Field(default="", max_length=120)
    source_id: str = Field(pattern=SOURCE)
    start: float = Field(ge=0, le=600)
    offset: float = Field(ge=0, le=3600)
    duration: float = Field(ge=0.1, le=600)
    volume: float = Field(ge=0, le=2)


class EditPlan(Strict):
    format: Literal["asa_edit_plan_v1"]
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(max_length=2000)
    aspect_ratio: Literal["9:16", "16:9", "1:1"]
    resolution: Literal["720p", "1080p"]
    segments: list[Segment] = Field(min_length=1, max_length=32)
    tracks: list[Track] = Field(max_length=16)

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.segments)

    @model_validator(mode="after")
    def timeline(self) -> "EditPlan":
        if self.duration > 600 or any(
            t.start + t.duration > self.duration + 0.001 for t in self.tracks
        ):
            raise ValueError("editing_timeline_limit")
        for s in self.segments:
            if s.source_id.startswith("image:"):
                if s.start != 0:
                    raise ValueError("editing_image_start")
            elif not s.source_id.startswith(("video:", "reference:")) or s.motion != "static":
                raise ValueError("editing_segment_kind")
        if any(not t.source_id.startswith(("audio:", "music:")) for t in self.tracks):
            raise ValueError("editing_track_kind")
        return self


def validate_answer(value: object, inputs: dict) -> EditPlan:
    import json
    plan = EditPlan.model_validate(value)
    try:
        sources = {s["id"]: s for s in json.loads(inputs.get("editing_sources", "[]"))}
        entries: list[Segment | Track] = [*plan.segments, *plan.tracks]
        for item in entries:
            source = sources[item.source_id]
            duration = source.get("duration")
            start = item.start if isinstance(item, Segment) else item.offset
            if duration is not None and not item.source_id.startswith("image:"):
                if start+item.duration > float(duration)+.06:
                    raise ValueError("editing_source_too_short")
        if (plan.aspect_ratio != inputs.get("aspect_ratio")
                or plan.resolution != inputs.get("resolution")):
            raise ValueError("editing_output_settings_changed")
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("editing_source_missing") from exc
    return plan
