"""Human clip-plan approvals, independent of generated-video approvals and paid work."""
import hashlib
import json
from typing import Any
from uuid import UUID

from asa.audio_contracts import AudioSettings
from asa.registry.audio_service import load
from asa.video_contracts import VideoPreparation
from asa.voice_directions import answer_contract


def fingerprints(plan: VideoPreparation, audio: AudioSettings,
                 context: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for clip in plan.clips:
        clip_snapshot = clip.model_dump(mode='json')
        # A newly optional field must not invalidate historical plan approvals.
        if not clip.reference_inputs:
            clip_snapshot.pop('reference_inputs', None)
        cues = [c for c in audio.cues if c.start < clip.source_end_seconds
                and c.end > clip.source_start_seconds]
        speakers = {c.speaker_id for c in cues}
        value = {
            'clip': clip_snapshot,
            'model': [plan.model_key, plan.model_revision, plan.aspect_ratio,
                      plan.mode, plan.audio],
            'style': context.get('work_visual_style'),
            'scene': [s for s in context.get('scene_images', {}).get('scenes', [])
                      if s.get('image_id') == str(clip.image_id)],
            'audio': {'mode': audio.delivery_mode, 'enabled': audio.enabled,
                      'cues': [c.model_dump(mode='json') for c in cues],
                      'speakers': [s.model_dump(mode='json') for s in audio.speakers
                                   if s.id in speakers]},
            'previous': (result.get(clip.previous_clip_id)
                         if clip.connection_type == 'continue' else None),
        }
        result[clip.clip_id] = hashlib.sha256(
            json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return result


def status(conn: Any, workspace: UUID, request: UUID, version: int,
           answer: dict[str, Any], inputs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    plan = VideoPreparation.model_validate(answer)
    contract = answer_contract(conn, workspace, request, version) or {}
    original = contract.get('original_request', inputs)
    context = {'work_visual_style': contract.get('work_visual_style'),
               'scene_images': original.get('scene_images') or {}}
    keys = fingerprints(plan, load(conn, workspace, request, version)['settings'], context)
    rows = conn.execute(
        'SELECT clip_id,fingerprint,answer_version,approved FROM video_clip_plan_approvals '
        'WHERE workspace_id=%s AND request_id=%s AND answer_version<=%s '
        'ORDER BY answer_version DESC',
        (workspace, request, version)).fetchall()
    return {clip_id: {'fingerprint': key, 'approved': next((row['approved']
        for row in rows if row['clip_id'] == clip_id and (row['fingerprint'] == key or
            (row['fingerprint'] is None and row['answer_version'] == version))), False)}
        for clip_id, key in keys.items()}
