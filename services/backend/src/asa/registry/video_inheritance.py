"""Resolve unchanged clips to original jobs without copying assets or creating work."""
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from asa.registry.audio_service import load
from asa.registry.schemas import RegistryError
from asa.registry.video_plan_approvals import fingerprints
from asa.registry.video_planning import generation_input
from asa.video_continuity import reference_valid
from asa.video_contracts import VideoPreparation
from asa.voice_directions import answer_contract


def resolve(conn: Any, workspace: UUID, request: UUID, version: int) -> dict[str, Any]:
    inputs = conn.execute('SELECT input FROM customer_requests WHERE workspace_id=%s AND id=%s',
                          (workspace, request)).fetchone()
    if not inputs:
        raise RegistryError(404, 'video_answer_missing')
    cache: dict[int, Any] = {}

    def context(number: int) -> Any:
        if number not in cache:
            audio = load(conn, workspace, request, number)
            plan = VideoPreparation.model_validate(audio['answer'])
            contract = answer_contract(conn, workspace, request, number) or {}
            original = contract.get('original_request', inputs['input'])
            ctx = {'work_visual_style': contract.get('work_visual_style'),
                   'scene_images': original.get('scene_images') or {}}
            keys = fingerprints(plan, audio['settings'], ctx)
            if audio['settings'].enabled and audio['settings'].delivery_mode != 'video':
                plan.audio = False
            cache[number] = (plan, audio['settings'], ctx, keys)
        return cache[number]

    plan, audio, ctx, keys = context(version)
    previous = conn.execute('SELECT max(version) AS version FROM script_versions '
                            'WHERE workspace_id=%s AND request_id=%s AND version<%s',
                            (workspace, request, version)).fetchone()
    previous_keys: dict[str, str] = {}
    if previous and previous['version']:
        try:
            previous_keys = context(previous['version'])[3]
        except (RegistryError, ValidationError, KeyError, ValueError):
            pass
    rows = conn.execute(
        "SELECT id,clip_id,status,paused,error_code,created_at,updated_at,superseded_by,"
        "progress_stage,provider_status,diagnostics,request_id,answer_version,generation_input,"
        "encode(sha256(video),'hex') AS video_sha256,"
        "(SELECT finished_at FROM ai_usage_events u WHERE "
        "u.workspace_id=video_clip_jobs.workspace_id AND u.id=video_clip_jobs.id) AS finished_at,"
        "(CASE WHEN generation_input->'reference_inputs'->'video' IS NOT NULL "
        "AND jsonb_array_length(generation_input->'reference_inputs'->'video')>0 "
        "THEN model_snapshot->>'usd_per_second_with_video' "
        "ELSE model_snapshot->>'usd_per_second' END)::numeric * "
        "(generation_input->>'duration_seconds')::integer AS estimate FROM video_clip_jobs "
        "WHERE workspace_id=%s AND request_id=%s AND answer_version<=%s "
        "ORDER BY answer_version DESC,created_at DESC",
        (workspace, request, version)).fetchall()
    active: dict[str, dict[str, Any]] = {}
    for clip in plan.clips:
        for row in rows:
            if row['clip_id'] != clip.clip_id or row['superseded_by']:
                continue
            inherited = row['answer_version'] != version
            if inherited:
                try:
                    old_keys = context(row['answer_version'])[3]
                    if old_keys.get(clip.clip_id) != keys[clip.clip_id]:
                        continue
                    spec = row['generation_input']
                    expected = generation_input(plan, clip, spec['resolution'],
                        audio if audio.delivery_mode == 'video' else None,
                        ctx['work_visual_style'])
                    # Older snapshots omitted these default values.
                    defaults = {'voice_direction_prompt': '', 'work_visual_style': None,
                                'connection_type': 'cut', 'previous_clip_id': ''}
                    if any(spec.get(k, defaults.get(k)) != v for k, v in expected.items()):
                        continue
                except (RegistryError, ValidationError, KeyError, ValueError):
                    continue
                if not reference_valid(row, active):
                    continue
            row['inherited'] = inherited
            active[clip.clip_id] = row
            break
    selected = {r['id'] for r in active.values()}
    history = [dict(r, inherited=r['answer_version'] != version) for r in rows
               if r['id'] not in selected and r['clip_id'] in keys]
    for row in [*active.values(), *history]:
        row['reference_valid'] = reference_valid(row, active)
    return {'jobs': list(active.values()), 'previous_attempts': history,
            'changed_clips': [c.clip_id for c in plan.clips if c.clip_id not in active
                              and (any(r['clip_id'] == c.clip_id for r in rows)
                                   or (c.clip_id in previous_keys and
                                       previous_keys[c.clip_id] != keys[c.clip_id]))]}


def selected_job(conn: Any, workspace: UUID, request: UUID, version: int,
                 clip_id: str) -> dict[str, Any] | None:
    return next((r for r in resolve(conn, workspace, request, version)['jobs']
                 if r['clip_id'] == clip_id), None)
