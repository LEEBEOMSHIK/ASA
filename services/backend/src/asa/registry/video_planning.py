"""Authenticated, non-generating video request preparation."""

import json
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.repository import RegistryRepository
from asa.registry.scene_selection import selected_scenes
from asa.registry.schemas import RegistryError
from asa.video_contracts import VideoModelProfile, VideoPreparation, duration_plan
from asa.video_management import policy
from asa.video_providers import connection_state, supported_model


def profile(settings: Settings, key: str, revision: str) -> VideoModelProfile:
    model = settings.video_model_profiles.get(key)
    if model is None or not model.enabled:
        raise RegistryError(422, "video_model_unavailable")
    if model.revision != revision:
        raise RegistryError(409, "video_model_changed")
    return model


def prepare(
    repo: RegistryRepository,
    settings: Settings,
    body: VideoPreparation,
    source_selection: dict[str, Any] | None = None,
    voice_settings: Any = None,
    visual_style: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model = profile(settings, body.model_key, body.model_revision)
    if voice_settings:
        from asa.voice_directions import validate_timeline

        validate_timeline(voice_settings, body.clips[-1].source_end_seconds)
    if body.aspect_ratio not in model.aspect_ratios:
        raise RegistryError(422, "video_aspect_ratio_unsupported")
    if body.audio and not model.supports_audio:
        raise RegistryError(422, "video_audio_unsupported")
    ids = list(dict.fromkeys(clip.image_id for clip in body.clips))
    # Server resolves current approval, exclusion and workspace ownership; no client URLs.
    if source_selection is None:
        selected = selected_scenes(repo, ids)
    else:
        try:
            sources = {s["image_id"]: s for s in source_selection["scenes"]}
            requested = [sources[str(i)] for i in ids]
            bases = [UUID(s.get("base_image_id", s["image_id"])) for s in requested]
            overrides = {
                UUID(s["base_image_id"]): UUID(s["image_id"])
                for s in requested
                if s.get("base_image_id")
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise RegistryError(422, "video_scene_reference_mismatch") from exc
        selected = (
            selected_scenes(repo, bases, overrides) if overrides else selected_scenes(repo, bases)
        )
        if selected["scenes"] != requested:
            raise RegistryError(409, "video_scene_reference_mismatch")
    images = {scene["image_id"]: scene for scene in selected["scenes"]}
    prepared = []
    for clip in body.clips:
        from asa.voice_directions import clip_audio_prompt

        voice_prompt = (clip_audio_prompt(voice_settings, clip.source_start_seconds,
                                         clip.source_end_seconds) if voice_settings else '')
        if voice_prompt and not model.supports_audio:
            raise RegistryError(422, 'video_audio_unsupported')
        image = images[str(clip.image_id)]
        if (clip.scene_id, clip.shot_id) != (image["scene_id"], image["shot_id"]):
            raise RegistryError(422, "video_scene_reference_mismatch")
        if clip.duration_seconds not in model.durations:
            raise RegistryError(422, "video_duration_unsupported")
        if not clip.prompt.strip():
            raise RegistryError(422, "video_prompt_limit")
        prompt = "\n\n".join(
            part
            for part in (
                clip.prompt.strip(),
                f"시작 상태 / Start: {clip.continuity_in}" if clip.continuity_in else "",
                f"종료 상태 / End: {clip.continuity_out}" if clip.continuity_out else "",
                voice_prompt,
            )
            if part
        )
        from asa.registry.art_styles import apply_style

        prompt = apply_style(prompt, visual_style)
        if not prompt or len(prompt) > model.max_prompt_chars:
            raise RegistryError(422, "video_prompt_limit")
        prepared.append(
            {
                "clip_id": clip.clip_id,
                "scene_id": clip.scene_id,
                "shot_id": clip.shot_id,
                "source_excerpt": clip.source_excerpt,
                "source_start_seconds": clip.source_start_seconds,
                "source_end_seconds": clip.source_end_seconds,
                "trim_seconds": clip.duration_seconds
                - (clip.source_end_seconds - clip.source_start_seconds),
                "split_reason": clip.split_reason,
                # This is an internal snapshot, never sent wholesale to the provider.
                "reference_snapshot": image,
                "generation_input": {
                    "prompt": prompt,
                    "duration_seconds": clip.duration_seconds,
                    "aspect_ratio": body.aspect_ratio,
                    "resolution": model.resolution,
                    "audio": bool(voice_prompt) or body.audio,
                    "voice_direction_prompt": voice_prompt,
                    "work_visual_style": visual_style,
                    "start_image_id": str(clip.image_id),
                    "connection_type": clip.connection_type,
                    "previous_clip_id": clip.previous_clip_id,
                },
            }
        )
    return {
        "format": "asa_video_preparation_v1",
        "status": "prepared_not_submitted",
        "model_key": body.model_key,
        "model_snapshot": model.model_dump(),
        "clips": prepared,
        "generation_started": False,
    }


def planner_constraints(settings: Settings, contract: dict[str, Any]) -> str | None:
    """Opt-in schema marker. Never infer video behavior from an agent's name."""
    properties = contract.get("input_schema", {}).get("properties", {})
    fields = [key for key, value in properties.items() if value.get("x-video-model") is True]
    if not fields:
        return None
    if len(fields) != 1:
        raise RegistryError(422, "video_model_field_invalid")
    original = contract.get("original_request", {})
    key = original.get(fields[0]) if isinstance(original, dict) else None
    model = settings.video_model_profiles.get(key) if isinstance(key, str) else None
    if model is None or not model.enabled:
        raise RegistryError(422, "video_model_unavailable")
    return (
        "선택한 영상 모델의 서버 검증 설정입니다: "
        + json.dumps({"model_key": key, **model.model_dump()}, ensure_ascii=False)
        + "\n이 설정의 허용 길이로 클립을 계획하세요. 전체 대본·장면을 분석하되 원문을 "
        "줄이거나 장면을 생략하지 마세요. 원본 장면/컷/확정 이미지 ID와 분할 이유, "
        "시작·종료 상태를 보존하세요. 클립별 영상 프롬프트에는 해당 클립의 동작·카메라·"
        "유지 조건만 포함하세요. 전체 대본과 모든 캐릭터를 매번 반복하지 마세요. "
        "모델의 고정 생성 길이로 생기는 여분 시간은 편집 대상이며 원본 시간을 늘리지 "
        "않습니다. 후속 클립은 자동으로 이전 영상을 기억하지 않습니다. 연장 API 호출과 "
        "독립 클립 생성을 혼동하지 마세요. 실제 영상 생성은 여기서 실행하지 않습니다."
        "각 클립에 connection_type(cut 또는 continue)와 previous_clip_id를 출력하세요. "
        "첫 클립과 독립 컷은 cut, previous_clip_id는 빈 문자열이며 확정 씬 이미지로 시작합니다. "
        "같은 동작을 이어갈 때만 continue와 바로 앞 clip_id를 지정합니다. 앞 영상이 사용자 "
        "확정되기 전 다음 연속 클립은 생성할 수 없습니다. 확정 영상의 마지막 프레임을 "
        "시작 이미지로 사용하므로 예상 종료 모습과 실제 종료 모습을 혼동하지 마세요. "
        "앞 클립에 잘라낼 여분 시간이 있으면 마지막 프레임과 편집 종료점이 다르므로 "
        "continue를 지정하지 마세요. 연속 구간은 생성 길이와 사용 길이를 일치시키세요. "
        "음성·음악은 별도 생성·확정 후 컷 연결과 합성합니다. "
        "자막·공급자 연장 API는 미구현이며 edit_notes에 "
        "후반 작업으로 구분하세요."
    )


class DurationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_key: str = Field(min_length=1, max_length=100)
    model_revision: str = Field(min_length=1, max_length=80)
    seconds: int = Field(ge=1, le=3600)


def video_planning_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/video-planning")

    @router.get("/models")
    def models(principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            controls = policy(conn, settings, repo.workspace_id)
            online = (
                conn.execute(
                    "SELECT 1 FROM pg_stat_activity WHERE datname=current_database() "
                    "AND application_name=%s LIMIT 1",
                    (f"asa-video-{repo.workspace_id}",),
                ).fetchone()
                is not None
            )
        return {
            "models": [
                {"key": key, **model.model_dump(),
                 "connection_state": (connection_state(settings, model.provider)
                                      if controls["providers"].get(model.provider, False)
                                      else "disabled"),
                 "generation_supported": supported_model(model.model_dump())}
                for key, model in settings.video_model_profiles.items()
                if model.enabled
            ],
            "worker_online": online,
            "key_configured": bool(settings.runway_api_key.get_secret_value()),
            "enabled": controls["enabled"],
            "generation_available": controls["enabled"] and any(
                controls["providers"].get(m.provider, False) and
                connection_state(settings, m.provider) == "configured"
                for m in settings.video_model_profiles.values() if m.enabled),
        }

    @router.post("/runway-connection")
    def runway_connection(principal: Principal = Depends(sessions.principal)) -> dict[str, str]:
        key = settings.runway_api_key.get_secret_value()
        if not key:
            return {"status": "missing"}
        try:
            response = httpx.get(
                "https://api.dev.runwayml.com/v1/organization",
                headers={"Authorization": f"Bearer {key}", "X-Runway-Version": "2024-11-06"},
                timeout=5,
            )
        except httpx.HTTPError:
            return {"status": "unreachable"}
        if response.status_code == 200:
            return {"status": "authenticated"}
        return {"status": "denied" if response.status_code in (401, 403) else "unreachable"}

    @router.post("/durations")
    def durations(
        body: DurationRequest, principal: Principal = Depends(sessions.principal)
    ) -> dict[str, Any]:
        model = profile(settings, body.model_key, body.model_revision)
        return {
            "clips": duration_plan(body.seconds, model.durations),
            "notice": "길이 배분 제안입니다. 대사와 동작의 분할은 별도로 검토하세요.",
        }

    @router.post("/prepare")
    def preparation(
        body: VideoPreparation, principal: Principal = Depends(sessions.principal)
    ) -> dict[str, Any]:
        return prepare(
            RegistryRepository(settings.database_url, principal.workspace_id), settings, body
        )

    return router
