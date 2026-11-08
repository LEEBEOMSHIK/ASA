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
    if not saved and isinstance(answer, dict) and isinstance(answer.get('characters'), list):
        speakers = seed.setdefault('speakers', [])
        if not any(s.get('role') == 'narrator' for s in speakers):
            used = {s['id'] for s in speakers}
            narrator_id = 'narrator'
            while narrator_id in used:
                narrator_id += '_'
            speakers.append({'id': narrator_id, 'name': '나레이션', 'role': 'narrator'})
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
    return {"cue": cue.model_dump(), "speaker": speaker.model_dump(mode="json"),
            "model": model.model_dump()}


def sample_spec(settings: Settings, data: AudioSettings, speaker_id: str) -> dict[str, Any]:
    speaker = next((s for s in data.speakers if s.id == speaker_id), None)
    if not speaker:
        raise RegistryError(404, 'audio_speaker_missing')
    cue = Cue(id=speaker.id, speaker_id=speaker.id,
              text='오늘은 어떤 이야기가 기다리고 있을까요? 우리 함께 시작해 봐요.',
              start=0, end=60)
    sample = data.model_copy(update={'cues': [cue]})
    return {**speech_spec(settings, sample, cue.id), 'purpose': 'sample'}


def job_speech_spec(settings: Settings, data: AudioSettings, job: dict[str, Any]) -> dict[str, Any]:
    if job['input'].get('purpose') == 'sample':
        return sample_spec(settings, data, job['cue_id'])
    spec = speech_spec(settings, data, job['cue_id'])
    if 'purpose' in job['input']:
        spec['purpose'] = job['input']['purpose']
    return spec


def require_selected_voice(conn: Any, settings: Settings, data: AudioSettings,
                           speaker_id: str) -> None:
    speaker = next(s for s in data.speakers if s.id == speaker_id)
    row = conn.execute('SELECT input,status,media,error_code,fingerprint FROM audio_jobs '
                       'WHERE workspace_id=%s AND id=%s',
                       (settings.workspace_id, speaker.sample_job_id)).fetchone()
    if (not row or row['input'].get('purpose') != 'sample' or row['status'] != 'approved'
            or not row['media'] or row['error_code']
            or row['fingerprint'] != speech_key(sample_spec(settings, data, speaker_id))):
        raise RegistryError(409, 'audio_voice_selection_required')


def speech_key(spec: dict[str, Any]) -> str:
    return fingerprint(
        {
            **({"purpose": spec["purpose"]} if "purpose" in spec else {}),
            "cue_id": spec["cue"]["id"],
            "text": spec["cue"]["text"],
            "emotion": spec["cue"]["emotion"],
            "speaker_id": spec["speaker"]["id"],
            "voice": spec["speaker"]["voice"],
            "model": spec["model"],
        }
    )


def review_speech(conn: Any, settings: Settings, request: UUID, version: int) -> dict[str, Any]:
    """Follow actual answer lineage, never titles, adjacent versions, or other requests."""
    workspace = settings.workspace_id
    versions = {row['version']: row['base_version'] for row in conn.execute(
        'SELECT version,base_version FROM script_versions WHERE workspace_id=%s AND request_id=%s',
        (workspace, request)).fetchall()}
    if version not in versions:
        raise RegistryError(404, 'audio_work_missing')
    source: int | None = version
    visited: set[int] = set()
    while source is not None and source in versions and source not in visited:
        visited.add(source)
        present = conn.execute(
            'SELECT EXISTS(SELECT 1 FROM audio_settings WHERE workspace_id=%s AND request_id=%s '
            'AND answer_version=%s) OR EXISTS(SELECT 1 FROM audio_jobs WHERE workspace_id=%s '
            "AND request_id=%s AND answer_version=%s AND kind='speech') AS present",
            (workspace, request, source, workspace, request, source)).fetchone()
        if present['present']:
            break
        source = versions[source]
    else:
        source = None
    if source is None:
        return {'answer_version': version, 'source_version': None, 'jobs': []}
    current = load(conn, workspace, request, source)
    jobs = conn.execute(
        'SELECT id,kind,cue_id,status,duration,transcript,error_code,fingerprint,input,'
        'created_at,media IS NOT NULL AS has_media FROM audio_jobs WHERE workspace_id=%s '
        "AND request_id=%s AND answer_version=%s AND kind='speech' ORDER BY created_at DESC,id",
        (workspace, request, source)).fetchall()
    output = []
    for job in jobs:
        snapshot = job.pop('input')
        if snapshot.get('purpose') == 'sample':
            continue
        purpose = snapshot.get('purpose', current['settings'].purpose)
        cue = snapshot['cue']
        reason = job['error_code']
        is_current = False
        try:
            spec = job_speech_spec(settings, current['settings'], {**job, 'input': snapshot})
            is_current = speech_key(spec) == job['fingerprint']
            if is_current:
                cue = spec['cue']
        except RegistryError:
            pass
        if not reason and not is_current:
            reason = 'audio_source_changed'
        if not reason and job['status'] in ('failed', 'unknown'):
            reason = 'audio_' + job['status']
        timing_ok = False
        if not reason and job['duration']:
            try:
                validate_measured(Cue.model_validate(cue), job['duration'])
                timing_ok = True
            except ValueError:
                pass
        job.pop('fingerprint')
        output.append({**job, 'text': snapshot['cue']['text'],
                       'speaker_name': snapshot['speaker']['name'],
                       'voice': snapshot['speaker']['voice']['voice'],
                       'start': cue['start'], 'end': cue['end'],
                       'excluded_reason': reason, 'timing_ok': timing_ok, 'purpose': purpose,
                       'can_approve': purpose == 'production' and not reason
                       and timing_ok and job['has_media']
                       and job['status'] == 'review'})
    from asa.audio_timing import summarize

    timing = None
    if current['settings'].purpose == 'timing':
        timing = summarize(output, [c.id for c in current['settings'].cues],
                           current['settings'].timing_duration_seconds,
                           current['settings'].timing_preview_seconds or
                           max((c.end for c in current['settings'].cues), default=0))
    return {'answer_version': version, 'source_version': source, 'timing': timing,
            'jobs': sorted(output, key=lambda job: (job['start'], job['cue_id']))}


def approve_speech(settings: Settings, data: AudioSettings, job: dict[str, Any]) -> None:
    if job.get('input', {}).get('purpose') in ('timing', 'sample') or data.purpose == 'timing':
        raise RegistryError(409, 'audio_timing_only')
    spec = job_speech_spec(settings, data, job)
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
    if data.purpose == "timing":
        raise RegistryError(409, "audio_timing_only")
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
        require_selected_voice(conn, settings.model_copy(update={'workspace_id': workspace}),
                               data, cue.speaker_id)
        spec = speech_spec(settings, data, cue.id)
        spec["purpose"] = "production"
        key = speech_key(spec)
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
