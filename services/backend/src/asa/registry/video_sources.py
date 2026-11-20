"""Read-only, allowlisted generation-time sources for an active video result."""
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry import video_inheritance
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError
from asa.voice_directions import answer_contract


def decoded(value: Any, fallback: Any) -> Any:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, type(fallback)) else fallback
        except (ValueError, TypeError):
            return fallback
    return value if isinstance(value, type(fallback)) else fallback


def sources(conn: Any, workspace: UUID, request: UUID, version: int,
            clip_id: str, job_id: UUID | None = None) -> dict[str, Any]:
    resolved = video_inheritance.resolve(conn, workspace, request, version)
    candidates = resolved['jobs'] + (resolved.get('previous_attempts', []) if job_id else [])
    job = next((j for j in candidates if j['clip_id'] == clip_id
                and (job_id is None or str(j['id']) == str(job_id))), None)
    if not job:
        raise RegistryError(404, 'video_source_missing')
    original_version = job['answer_version']
    contract = answer_contract(conn, workspace, request, original_version)
    original = (contract or {}).get('original_request') or {}
    spec = job['generation_input']
    selection = original.get('scene_images') or {}
    scenes = selection.get('scenes', []) if isinstance(selection, dict) else []
    scene: dict[str, Any] = next(
        (s for s in scenes if s.get('image_id') == spec.get('start_image_id')), {})

    def image(value: Any, name: str, role: str,
              expected_sha256: str | None = None) -> dict[str, Any] | None:
        try:
            ident = UUID(str(value))
        except (ValueError, TypeError):
            return None
        # Never expose an asset identifier/URL from an unchecked stored contract.
        row = conn.execute(
            "SELECT encode(sha256(image),'hex') AS sha256 FROM character_image_jobs "
            "WHERE workspace_id=%s AND id=%s "
            "AND status='succeeded' AND image IS NOT NULL UNION ALL "
            "SELECT encode(sha256(image),'hex') AS sha256 FROM character_reference_uploads "
            "WHERE workspace_id=%s AND id=%s "
            "AND image IS NOT NULL LIMIT 1", (workspace, ident, workspace, ident)).fetchone()
        if not row or (expected_sha256 and row['sha256'] != expected_sha256):
            return None
        return {'image_id': str(ident), 'name': name, 'role': role,
                'url': f'/api/v1/characters/images/{ident}/asset'}

    generation_images = []
    reference_mode = bool(spec.get('reference_inputs'))
    if reference_mode:
        for reference in spec.get('reference_images', []):
            item = image(reference.get('image_id'),
                         '씬 참조' if reference.get('role') == 'scene' else '캐릭터 참조',
                         str(reference.get('role') or 'reference'), reference.get('sha256'))
            if item:
                generation_images.append(item)
    elif spec.get('connection_type') == 'continue':
        # The exact sent first frame was extracted from the preceding video.
        parent = conn.execute(
            "SELECT id FROM video_clip_jobs WHERE workspace_id=%s AND request_id=%s "
            "AND id=%s AND status='approved' AND encode(sha256(video),'hex')=%s",
            (workspace, request, spec.get('source_job_id'),
             spec.get('source_video_sha256'))).fetchone()
        if parent:
            generation_images.append({'image_id': str(parent['id']),
                'name': '앞 영상 마지막 프레임', 'role': 'first_frame',
                'url': f"/api/v1/video-clips/asset/{parent['id']}/last-frame"})
    else:
        item = image(spec.get('start_image_id'), scene.get('name') or '시작 이미지', 'first_frame')
        if item:
            generation_images.append(item)
    planning_images = []
    for character in decoded(scene.get('character_settings'), []):
        if isinstance(character, dict):
            item = image(character.get('image_id'), str(character.get('name') or '캐릭터'), 'cast')
            if item:
                planning_images.append(item)
    scene_settings = decoded(scene.get('settings'), {})
    audio = spec.get('reference_audio') or {}
    videos = []
    video = spec.get('reference_video')
    if video:
        row = conn.execute(
            "SELECT clip_id,answer_version FROM video_clip_jobs WHERE workspace_id=%s "
            "AND request_id=%s AND id=%s AND status IN ('review','approved') "
            "AND encode(sha256(video),'hex')=%s AND answer_version=%s",
            (workspace, request, video['job_id'], video['source_sha256'],
             video['source_answer_version'])).fetchone()
        if row:
            videos.append({'job_id': video['job_id'], 'clip_id': row['clip_id'],
                           'source_answer_version': row['answer_version']})
    return {'generation_mode': 'reference' if reference_mode else 'first_frame',
            'video_references': videos,
            'audio_reference': {k: v for k, v in audio.items() if k in {
                'speaker_id', 'start_seconds', 'end_seconds', 'source_answer_version'}},
            'answer_version': original_version, 'inherited': original_version != version,
            'snapshot_available': bool(contract and 'original_request' in contract),
            'script': original.get('script') if isinstance(original.get('script'), str) else '',
            'scenes': original.get('scenes') if isinstance(original.get('scenes'), str) else '',
            'scene_name': str(scene.get('name') or ''),
            'scene_settings': {k: v for k, v in scene_settings.items()
                               if k in {'facts', 'proposed', 'image_prompt'}
                               and isinstance(v, str)},
            'generation_images': generation_images, 'planning_images': planning_images}


def video_source_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix='/api/v1/video-clips')

    @router.get('/{request_id}/{version}/sources/{clip_id}')
    def get_sources(request_id: UUID, version: int, clip_id: str, job_id: UUID | None = None,
                    principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            return sources(conn, repo.workspace_id, request_id, version, clip_id, job_id)

    return router
