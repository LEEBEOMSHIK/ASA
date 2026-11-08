"""Audio business rules and immutable work snapshots; no external calls here."""

from typing import Any
from uuid import UUID

from asa.audio_contracts import AudioSettings, Cue, fingerprint, validate_measured
from asa.config import Settings
from asa.registry.schemas import RegistryError
from asa.video_continuity import source_video
from asa.video_contracts import VideoPreparation


def load(
    conn: Any, workspace: UUID, request: UUID, version: int, *, lock: bool = False
) -> dict[str, Any]:
    if lock:
        conn.execute(
            "SELECT id FROM customer_requests WHERE workspace_id=%s AND id=%s FOR UPDATE",
            (workspace, request),
        ).fetchone()
    row = conn.execute(
        "SELECT answer FROM script_versions WHERE workspace_id=%s AND request_id=%s AND version=%s",
        (workspace, request, version),
    ).fetchone()
    if not row:
        raise RegistryError(404, "audio_work_missing")
    saved = conn.execute(
        "SELECT revision,settings FROM audio_settings WHERE workspace_id=%s "
        "AND request_id=%s AND answer_version=%s",
        (workspace, request, version),
    ).fetchone()
    answer = row["answer"]
    seed: dict[str, Any] = {}
    if isinstance(answer, dict):
        if "audio_plan" in answer:
            seed = answer["audio_plan"] or {}
        elif isinstance(answer.get("characters"), list):
            seed = {"speakers": [{"id": c["id"], "name": c["name"]} for c in answer["characters"]]}
    return {
        "revision": saved["revision"] if saved else 0,
        "settings": AudioSettings.model_validate(saved["settings"] if saved else seed),
        "answer": answer,
    }


def validate_assets(conn: Any, workspace: UUID, data: AudioSettings) -> None:
    if data.music.asset_id:
        asset = conn.execute(
            "SELECT duration FROM audio_assets WHERE workspace_id=%s AND id=%s",
            (workspace, data.music.asset_id),
        ).fetchone()
        if not asset:
            raise RegistryError(404, "audio_asset_missing")
        if data.music.offset >= asset["duration"]:
            raise RegistryError(422, "audio_music_timing")


def speech_spec(settings: Settings, data: AudioSettings, cue_id: str) -> dict[str, Any]:
    cue = next((c for c in data.cues if c.id == cue_id), None)
    if not cue:
        raise RegistryError(422, "audio_cue_missing")
    speaker = next(s for s in data.speakers if s.id == cue.speaker_id)
    model = settings.audio_model_profiles.get(speaker.voice.model_key)
    if not model or not model.enabled or speaker.voice.voice not in model.voices:
        raise RegistryError(422, "audio_voice_unavailable")
    return {"cue": cue.model_dump(), "speaker": speaker.model_dump(), "model": model.model_dump()}


def speech_key(spec: dict[str, Any]) -> str:
    return fingerprint(
        {
            "cue_id": spec["cue"]["id"],
            "text": spec["cue"]["text"],
            "emotion": spec["cue"]["emotion"],
            "speaker_id": spec["speaker"]["id"],
            "voice": spec["speaker"]["voice"],
            "model": spec["model"],
        }
    )


def approve_speech(settings: Settings, data: AudioSettings, job: dict[str, Any]) -> None:
    spec = speech_spec(settings, data, job["cue_id"])
    if speech_key(spec) != job["fingerprint"]:
        raise RegistryError(409, "audio_source_changed")
    if job.get("error_code") or not job.get("duration"):
        raise RegistryError(409, job.get("error_code") or "audio_not_ready")
    validate_measured(Cue.model_validate(spec["cue"]), job["duration"])


def composition_spec(
    conn: Any,
    settings: Settings,
    workspace: UUID,
    request: UUID,
    version: int,
    current: dict[str, Any],
    remove_original: bool,
) -> dict[str, Any]:
    plan = VideoPreparation.model_validate(current["answer"])
    data: AudioSettings = current["settings"]
    if not data.enabled:
        raise RegistryError(409, "audio_disabled")
    duration = plan.clips[-1].source_end_seconds
    if any(c.end > duration for c in data.cues):
        raise RegistryError(422, "audio_timeline_invalid")
    validate_assets(conn, workspace, data)
    videos = []
    for clip in plan.clips:
        row = conn.execute(
            "SELECT *,encode(sha256(video),'hex') AS sha FROM video_clip_jobs "
            "WHERE workspace_id=%s AND request_id=%s AND answer_version=%s AND clip_id=%s "
            "FOR SHARE",
            (workspace, request, version, clip.clip_id),
        ).fetchone()
        if not row or row["status"] != "approved" or not row["video"]:
            raise RegistryError(409, "audio_video_approval_required")
        if row["generation_input"].get("connection_type") == "continue":
            source_video(conn, workspace, row)
        if row["generation_input"].get("audio") and not remove_original:
            raise RegistryError(409, "audio_original_removal_required")
        videos.append(
            {
                "id": str(row["id"]),
                "sha": row["sha"],
                "duration": clip.source_end_seconds - clip.source_start_seconds,
            }
        )
    speech = []
    for cue in data.cues:
        key = speech_key(speech_spec(settings, data, cue.id))
        job = conn.execute(
            "SELECT *,encode(sha256(media),'hex') AS sha FROM audio_jobs "
            "WHERE workspace_id=%s AND request_id=%s AND answer_version=%s "
            "AND kind='speech' AND fingerprint=%s AND status='approved' FOR SHARE",
            (workspace, request, version, key),
        ).fetchone()
        if not job or job["status"] != "approved" or not job["media"]:
            raise RegistryError(409, "audio_speech_approval_required")
        approve_speech(settings, data, job)
        speech.append({"id": str(job["id"]), "sha": job["sha"], "start": cue.start})
    music = None
    if data.music.asset_id:
        asset = conn.execute(
            "SELECT sha256 FROM audio_assets WHERE workspace_id=%s AND id=%s",
            (workspace, data.music.asset_id),
        ).fetchone()
        music = {"id": str(data.music.asset_id), "sha": asset["sha256"]}
    return {
        "settings_revision": current["revision"],
        "settings": data.model_dump(mode="json"),
        "videos": videos,
        "speech": speech,
        "music": music,
        "remove_original": remove_original,
    }
