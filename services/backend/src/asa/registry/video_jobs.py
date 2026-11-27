"""Queue clips from a saved agent answer; the browser submits only selected clip IDs."""

import subprocess
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, ValidationError

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry import video_inheritance, video_plan_approvals
from asa.registry.media_response import media_response
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError
from asa.registry.video_planning import catalog_estimate, prepare
from asa.registry.video_retry import (
    RetryConfirmation,
    original_metadata,
    require_admin,
    retry_reason,
    target_fingerprint,
)
from asa.video_continuity import approved_source, last_frame, source_video
from asa.video_contracts import VideoPreparation
from asa.video_management import allowed, lock_policy, policy
from asa.video_providers import connection_state, endpoint, supported_model, validate_input
from asa.wan_regions import active_settings


class ClipSelection(BaseModel):
    clip_ids: list[str] = Field(min_length=1, max_length=100)


class PlanApproval(ClipSelection):
    fingerprints: dict[str, str]


def video_job_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/video-clips")
    path = "/{request_id}/{version}"

    @router.get(path)
    def jobs(
        request_id: UUID, version: int, principal: Principal = Depends(sessions.principal)
    ) -> dict[str, Any]:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            from asa.registry.audio_service import load as load_audio
            from asa.voice_directions import clip_audio_prompt, validate_timeline

            controls = policy(conn, settings, repo.workspace_id)
            resolved = active_settings(conn, settings, repo.workspace_id)
            current_audio = load_audio(conn, repo.workspace_id, request_id, version)
            voice_settings = current_audio['settings']
            delivery: dict[str, Any] = {'mode': voice_settings.delivery_mode, 'clips': [],
                                        'speakers': [], 'error': None}
            if voice_settings.delivery_mode == 'video':
                model_key = current_audio['answer'].get('model_key')
                selected_model = settings.video_model_profiles.get(model_key)
                delivery['supports_audio'] = bool(selected_model and selected_model.supports_audio)
                delivery['speakers'] = [
                    {'id': s.id, 'name': s.name, 'role': s.role, 'enabled': s.video_enabled,
                     'instructions': s.voice.instructions, 'language': s.voice.language,
                     'speed': s.voice.speed} for s in voice_settings.speakers]
                try:
                    validate_timeline(voice_settings,
                                      current_audio['answer']['clips'][-1]['source_end_seconds'])
                except RegistryError as exc:
                    delivery['error'] = exc.code
                for clip in current_audio['answer'].get('clips', []):
                    try:
                        prompt = clip_audio_prompt(voice_settings, clip['source_start_seconds'],
                                                   clip['source_end_seconds'])
                        if prompt and not delivery['supports_audio']:
                            delivery['error'] = 'video_audio_unsupported'
                        delivery['clips'].append({'clip_id': clip['clip_id'], 'prompt': prompt})
                    except RegistryError as exc:
                        delivery['error'] = exc.code
            inherited = video_inheritance.resolve(conn, repo.workspace_id, request_id, version)
            rows = inherited['jobs'] + inherited['previous_attempts']
            request = conn.execute(
                'SELECT input FROM customer_requests WHERE workspace_id=%s AND id=%s',
                (repo.workspace_id, request_id)).fetchone()
            if not request:
                raise RegistryError(404, 'video_answer_missing')
            plan_approvals = video_plan_approvals.status(
                conn, repo.workspace_id, request_id, version,
                current_audio['answer'], request['input'])
            stage = conn.execute('SELECT head_version FROM script_stages '
                                 'WHERE workspace_id=%s AND request_id=%s',
                                 (repo.workspace_id, request_id)).fetchone()
            review = conn.execute('SELECT annotations,validation FROM video_review_annotations '
                                  'WHERE workspace_id=%s AND request_id=%s AND answer_version=%s',
                                  (repo.workspace_id, request_id, version)).fetchone()
            for row in rows:
                row['voice_direction_prompt'] = row['generation_input'].get(
                    'voice_direction_prompt')
                row.pop("generation_input")
                row.pop("video_sha256")
            online = (
                conn.execute(
                    "SELECT 1 FROM pg_stat_activity WHERE datname=current_database() "
                    "AND application_name=%s LIMIT 1",
                    (f"asa-video-{repo.workspace_id}",),
                ).fetchone()
                is not None
            )
        from asa.video_reference_delivery import require_audio_delivery

        reference_delivery: dict[str, Any] = {'configured': True, 'error': None}
        selected_profile = settings.video_model_profiles.get(
            current_audio['answer'].get('model_key'))
        if not selected_profile or selected_profile.provider != 'higgsfield':
            try:
                require_audio_delivery(settings)
            except RegistryError as exc:
                reference_delivery = {'configured': False, 'error': exc.code}
        from asa.higgsfield_models import validate_spec
        model_issues = {}
        if selected_profile and selected_profile.provider == 'higgsfield':
            answer = current_audio['answer']
            for clip in answer.get('clips', []):
                try:
                    validate_spec(selected_profile.model_dump(), {
                        'duration_seconds': clip['duration_seconds'],
                        'audio': answer.get('audio', False),
                        'reference_inputs': (clip.get('reference_inputs') or [None])[0],
                    })
                except ValueError as exc:
                    model_issues[clip['clip_id']] = str(exc)
        return {
            'model_issues': model_issues,
            'model_provider': selected_profile.provider if selected_profile else None,
            'model_label': selected_profile.label if selected_profile else None,
            'estimates': {clip['clip_id']: catalog_estimate(
                selected_profile, clip['duration_seconds'],
                bool(clip.get('reference_inputs') and clip['reference_inputs'][0].get('video')))
                for clip in current_audio['answer'].get('clips', [])} if selected_profile else {},
            'reference_delivery': reference_delivery,
            'review_annotations': review['annotations'] if review else [],
            'review_validation': review['validation'] if review else None,
            'voice_delivery': delivery,
            'plan_approvals': plan_approvals,
            'is_latest': bool(stage and stage['head_version'] == version),
            "jobs": inherited["jobs"],
            "changed_clips": inherited["changed_clips"],
            "previous_attempts": inherited["previous_attempts"],
            "worker_online": online,
            "rates": {
                key: model.usd_per_second
                for key, model in settings.video_model_profiles.items()
                if model.enabled
            },
            "enabled": controls["enabled"]
            and any(allowed(controls, m.provider) and
                    connection_state(resolved, m.provider) == "configured"
                    for m in settings.video_model_profiles.values() if m.enabled),
            "available_models": [key for key, m in settings.video_model_profiles.items()
                                 if m.enabled and supported_model(m.model_dump())
                                 and allowed(controls, m.provider)
                                 and connection_state(resolved, m.provider) == "configured"],
        }

    @router.post(path)
    def enqueue(
        request_id: UUID,
        version: int,
        body: ClipSelection,
        principal: Principal = Depends(sessions.principal),
    ) -> dict[str, int]:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            count = enqueue_in_transaction(conn, repo, request_id, version, body)
        return {"queued": count}

    def enqueue_in_transaction(
        conn: Any, repo: RegistryRepository, request_id: UUID, version: int,
        body: ClipSelection, retry: RetryConfirmation | None = None,
        original: dict[str, Any] | None = None, principal: Principal | None = None,
        dry_run: bool = False,
    ) -> int:
        lock_policy(conn, repo.workspace_id)
        controls = policy(conn, settings, repo.workspace_id)
        resolved = active_settings(conn, settings, repo.workspace_id)
        if not controls["enabled"]:
            raise RegistryError(409, "video_generation_disabled")
        row = conn.execute(
            "SELECT v.answer,r.input FROM script_versions v JOIN customer_requests r "
            "ON r.workspace_id=v.workspace_id AND r.id=v.request_id "
            "WHERE v.workspace_id=%s AND v.request_id=%s AND v.version=%s FOR UPDATE OF r",
            (repo.workspace_id, request_id, version),
        ).fetchone()
        if not row:
            raise RegistryError(404, "video_answer_missing")
        stage = conn.execute(
            "SELECT head_version,approved_version FROM script_stages "
            "WHERE workspace_id=%s AND request_id=%s FOR SHARE",
            (repo.workspace_id, request_id),
        ).fetchone()
        if not stage or stage['head_version'] != version:
            raise RegistryError(409, "video_plan_approval_required")
        try:
            plan = VideoPreparation.model_validate(row["answer"])
        except ValidationError as exc:
            raise RegistryError(422, "video_plan_invalid") from exc
        from asa.registry.audio_service import load as load_audio
        audio_settings = load_audio(conn, repo.workspace_id, request_id, version,
                                    lock=True)["settings"]
        if audio_settings.enabled and audio_settings.delivery_mode != 'video':
            plan.audio = False
        from asa.voice_directions import answer_contract

        contract = answer_contract(conn, repo.workspace_id, request_id, version)
        if contract and contract.get('video_execution_settings'):
            from asa.video_settings import validate_answer
            try:
                validate_answer(row['answer'], contract['video_execution_settings'])
            except ValueError as exc:
                raise RegistryError(422, 'video_settings_mismatch') from exc
        inputs = contract.get('original_request', row['input']) if contract else row['input']
        from asa.registry import art_styles

        visual_style = contract.get('work_visual_style') if contract else None
        current_style = art_styles.resolve(conn, repo.workspace_id, inputs, request_id)
        art_styles.check_plan_style(visual_style, current_style)
        if plan.model_key != inputs.get("video_model"):
            raise RegistryError(422, "video_model_mismatch")
        selection = inputs.get("scene_images")
        if (
            not isinstance(selection, dict)
            or selection.get("format") != "asa_scene_selection_v1"
        ):
            raise RegistryError(422, "video_scene_reference_mismatch")
        source_images = {s["image_id"] for s in selection["scenes"]}
        if any(str(c.image_id) not in source_images for c in plan.clips):
            raise RegistryError(422, "video_scene_reference_mismatch")
        selected = set(body.clip_ids)
        if selected - {c.clip_id for c in plan.clips}:
            raise RegistryError(422, "video_plan_invalid")
        if original is None:
            existing_jobs = video_inheritance.resolve(
                conn, repo.workspace_id, request_id, version)['jobs']
            selected -= {r['clip_id'] for r in existing_jobs if r['inherited']}
            if not selected:
                return 0
        approvals = video_plan_approvals.status(
            conn, repo.workspace_id, request_id, version, row['answer'], row['input'])
        if any(not approvals[c]['approved'] for c in selected):
            raise RegistryError(409, 'video_clip_plan_approval_required')
        from asa.video_plan_quality import require_ready

        for clip in plan.clips:
            from asa.video_references import validate_requested

            validate_requested(clip.clip_id,
                               clip.reference_inputs[0].model_dump(mode='json')
                               if clip.reference_inputs else None,
                               inputs.get('video_references'))
            if clip.clip_id in selected:
                require_ready(clip.quality)
        prepared = prepare(repo, settings, plan, selection,
                           audio_settings if audio_settings.delivery_mode == 'video' else None,
                           visual_style, selected)
        model = prepared["model_snapshot"]
        if not supported_model(model):
            raise RegistryError(422, "video_model_unavailable")
        if (not allowed(controls, model["provider"]) or
                connection_state(resolved, model["provider"]) != "configured"):
            raise RegistryError(409, "video_generation_disabled")
        model["provider_endpoint"] = endpoint(resolved, model["provider"])
        for clip in prepared["clips"]:
            from asa.video_references import freeze

            freeze(conn, settings, repo.workspace_id, request_id,
                   clip['generation_input'], selection, model['provider'])
            try:
                validate_input(model, clip["generation_input"])
            except (KeyError, TypeError, ValueError) as exc:
                raise RegistryError(422, "video_model_unavailable") from exc
        if retry is not None and retry.expected_target != target_fingerprint(model, controls):
            raise RegistryError(409, 'video_retry_target_changed')
        if original is not None:
            selected_spec = next(c['generation_input'] for c in prepared['clips']
                                 if c['clip_id'] == original['clip_id'])
            # A retry must not silently change the approved clip or voice instructions.
            old_spec = dict(original['generation_input'])
            if selected_spec.get('connection_type') == 'continue':
                try:
                    selected_spec.update(approved_source(
                        conn, repo.workspace_id, request_id, version,
                        selected_spec['previous_clip_id']))
                except ValueError as exc:
                    raise RegistryError(409, str(exc)) from exc
            if old_spec != selected_spec:
                raise RegistryError(409, 'video_retry_input_changed')
        if dry_run:
            return 0
        if retry is not None and original is not None and principal is not None:
            from asa.video_connection import check
            if check(resolved, repo.workspace_id, model['provider'])['status'] != 'authenticated':
                raise RegistryError(409, 'video_retry_authentication_required')
            conn.execute('UPDATE video_clip_jobs SET superseded_by=%s '
                         'WHERE workspace_id=%s AND id=%s',
                         (retry.id, repo.workspace_id, original['id']))
            conn.execute('INSERT INTO video_retry_confirmations(workspace_id,id,original_job_id,'
                         'confirmed_by,evidence,target_fingerprint) VALUES(%s,%s,%s,%s,%s,%s)',
                         (repo.workspace_id, retry.id, original['id'],
                          principal.user_id, retry.audit_evidence, retry.expected_target))
        count = 0
        for clip in prepared["clips"]:
            if clip["clip_id"] not in selected:
                continue
            spec = clip["generation_input"]
            if spec.get("connection_type") == "continue":
                try:
                    spec.update(approved_source(conn, repo.workspace_id, request_id,
                                                version, spec["previous_clip_id"]))
                except ValueError as exc:
                    raise RegistryError(409, str(exc)) from exc
            count += conn.execute(
                "INSERT INTO video_clip_jobs(workspace_id,id,request_id,answer_version,"
                "clip_id,model_snapshot,generation_input,status) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,'queued') ON CONFLICT DO NOTHING",
                (
                    repo.workspace_id,
                    retry.id if retry else uuid4(),
                    request_id,
                    version,
                    clip["clip_id"],
                    Jsonb(model),
                    Jsonb(clip["generation_input"]),
                ),
            ).rowcount
        if retry is not None and count != 1:
            raise RegistryError(409, 'video_retry_conflict')
        conn.execute("SELECT pg_notify('asa_video_jobs',%s)", (str(repo.workspace_id),))
        return count

    @router.get(path + "/jobs/{job_id}/retry-review")
    def retry_review(request_id: UUID, version: int, job_id: UUID,
                     principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        require_admin(principal)
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            row = conn.execute('SELECT * FROM video_clip_jobs WHERE workspace_id=%s '
                               'AND request_id=%s AND answer_version<=%s AND id=%s',
                               (repo.workspace_id, request_id, version, job_id)).fetchone()
            if not row:
                raise RegistryError(404, 'video_job_missing')
            linked = video_inheritance.selected_job(
                conn, repo.workspace_id, request_id, version, row['clip_id'])
            if not linked or linked['id'] != job_id:
                raise RegistryError(409, 'video_retry_input_changed')
            resolved = active_settings(conn, settings, repo.workspace_id)
            plan = conn.execute('SELECT answer FROM script_versions WHERE workspace_id=%s '
                                'AND request_id=%s AND version=%s',
                                (repo.workspace_id, request_id, version)).fetchone()
            profile = settings.video_model_profiles.get(
                plan['answer'].get('model_key')) if plan else None
            target = ({'provider': profile.provider, 'model': profile.model,
                       'provider_endpoint': endpoint(resolved, profile.provider),
                       'region': resolved.wan_region if profile.provider == 'alibaba' else None,
                       'estimate': catalog_estimate(
                           profile, row['generation_input'].get('duration_seconds', 0),
                           bool((row['generation_input'].get('reference_inputs') or {})
                                .get('video')))['amount_usd']}
                      if profile else None)
            reason = retry_reason(row)
            controls = policy(conn, settings, repo.workspace_id)
            target_model = profile.model_dump() if profile else {}
            if profile:
                target_model['provider_endpoint'] = endpoint(resolved, profile.provider)
            fingerprint = target_fingerprint(target_model, controls)
            if reason is None and (profile is None or not profile.enabled or
                                   not allowed(controls, profile.provider) or
                                   connection_state(resolved, profile.provider) != 'configured'):
                reason = 'video_generation_disabled'
            if reason is None:
                try:
                    enqueue_in_transaction(conn, repo, request_id, version,
                                           ClipSelection(clip_ids=[row['clip_id']]),
                                           original=row, dry_run=True)
                except RegistryError as exc:
                    reason = exc.code
        return {'original': original_metadata(row), 'target': target,
                'target_fingerprint': fingerprint,
                'eligible': reason is None, 'reason': reason,
                'guidance': '원래 공급자·리전·계정의 요청 시간대 생성 및 과금 기록을 확인하세요. '
                '진행 중 작업과 생성 결과가 없음을 확인한 근거가 필요합니다. '
                '인증 성공이나 빈 작업 목록만으로는 미생성을 입증할 수 없습니다. '
                '작업 ID가 있으면 기존 작업 회수가 필요합니다. 비밀값은 입력하지 마세요.'}

    @router.post(path + "/jobs/{job_id}/retry")
    def retry_job(request_id: UUID, version: int, job_id: UUID, body: RetryConfirmation,
                  principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        require_admin(principal)
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            # Same lock order as enqueue and policy changes; serialize double clicks.
            lock_policy(conn, repo.workspace_id)
            row = conn.execute('SELECT * FROM video_clip_jobs WHERE workspace_id=%s '
                               'AND request_id=%s AND answer_version<=%s AND id=%s FOR UPDATE',
                               (repo.workspace_id, request_id, version, job_id)).fetchone()
            if not row:
                raise RegistryError(404, 'video_job_missing')
            body.validate_status(row['status'])
            existing = conn.execute('SELECT original_job_id,evidence,confirmed_by,'
                                    'target_fingerprint '
                                    'FROM video_retry_confirmations '
                                    'WHERE workspace_id=%s AND id=%s',
                                    (repo.workspace_id, body.id)).fetchone()
            if existing:
                if (existing['original_job_id'] != job_id
                        or existing['evidence'] != body.audit_evidence
                        or existing['confirmed_by'] != principal.user_id
                        or existing['target_fingerprint'] != body.expected_target):
                    raise RegistryError(409, 'video_retry_conflict')
                return {'queued': 1, 'job_id': body.id}
            linked = video_inheritance.selected_job(
                conn, repo.workspace_id, request_id, version, row['clip_id'])
            if not linked or linked['id'] != job_id:
                raise RegistryError(409, 'video_retry_input_changed')
            reason = retry_reason(row)
            if reason:
                raise RegistryError(409, reason)
            count = enqueue_in_transaction(conn, repo, request_id, version,
                                           ClipSelection(clip_ids=[row['clip_id']]),
                                           body, row, principal)
        return {'queued': count, 'job_id': body.id}

    def set_plan_approval(request_id: UUID, version: int, body: PlanApproval,
                          principal: Principal, approved: bool) -> dict[str, int]:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            row = conn.execute(
                'SELECT v.answer,r.input FROM script_versions v JOIN customer_requests r '
                'ON r.workspace_id=v.workspace_id AND r.id=v.request_id '
                'WHERE v.workspace_id=%s AND v.request_id=%s AND v.version=%s FOR UPDATE OF r',
                (repo.workspace_id, request_id, version)).fetchone()
            if not row:
                raise RegistryError(404, 'video_answer_missing')
            stage = conn.execute('SELECT head_version FROM script_stages '
                                 'WHERE workspace_id=%s AND request_id=%s FOR SHARE',
                                 (repo.workspace_id, request_id)).fetchone()
            if not stage or stage['head_version'] != version:
                raise RegistryError(409, 'video_plan_approval_required')
            try:
                approvals = video_plan_approvals.status(
                    conn, repo.workspace_id, request_id, version, row['answer'], row['input'])
            except ValidationError as exc:
                raise RegistryError(422, 'video_plan_invalid') from exc
            selected = set(body.clip_ids)
            if selected - approvals.keys():
                raise RegistryError(422, 'video_plan_invalid')
            if any(body.fingerprints.get(c) != approvals[c]['fingerprint'] for c in selected):
                raise RegistryError(409, 'video_clip_plan_changed')
            for clip_id in selected:
                conn.execute(
                    'INSERT INTO video_clip_plan_approvals(workspace_id,request_id,answer_version,'
                    'clip_id,fingerprint,approved_by,approved) VALUES(%s,%s,%s,%s,%s,%s,%s) '
                    'ON CONFLICT(workspace_id,request_id,answer_version,clip_id) DO UPDATE '
                    'SET fingerprint=EXCLUDED.fingerprint,approved_by=EXCLUDED.approved_by,'
                    'approved=EXCLUDED.approved,approved_at=now()',
                    (repo.workspace_id, request_id, version, clip_id,
                     approvals[clip_id]['fingerprint'], principal.user_id, approved))
        return {'approved' if approved else 'revoked': len(selected)}

    @router.post(path + "/plan-approve")
    def approve_plan(request_id: UUID, version: int, body: PlanApproval,
                     principal: Principal = Depends(sessions.principal)) -> dict[str, int]:
        return set_plan_approval(request_id, version, body, principal, True)

    @router.post(path + "/plan-revoke")
    def revoke_plan(request_id: UUID, version: int, body: PlanApproval,
                    principal: Principal = Depends(sessions.principal)) -> dict[str, int]:
        return set_plan_approval(request_id, version, body, principal, False)

    @router.post(path + "/approve")
    def approve(
        request_id: UUID,
        version: int,
        body: ClipSelection,
        principal: Principal = Depends(sessions.principal),
    ) -> dict[str, int]:
        selected = set(body.clip_ids)
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            # Serialize with new generation and retry actions on this request.
            conn.execute('SELECT id FROM customer_requests WHERE workspace_id=%s AND id=%s '
                         'FOR UPDATE', (repo.workspace_id, request_id)).fetchone()
            candidates = [r for r in video_inheritance.resolve(
                conn, repo.workspace_id, request_id, version)['jobs'] if r['clip_id'] in selected]
            for candidate in candidates:
                if candidate["generation_input"].get("connection_type") == "continue":
                    try:
                        source_video(conn, repo.workspace_id, candidate)
                    except ValueError as exc:
                        raise RegistryError(409, str(exc)) from exc
            result = conn.execute(
                "UPDATE video_clip_jobs SET status='approved',updated_at=now() "
                "WHERE workspace_id=%s AND request_id=%s "
                "AND superseded_by IS NULL AND id=ANY(%s) "
                "AND status IN ('review','approved') AND video IS NOT NULL",
                (repo.workspace_id, request_id, [r["id"] for r in candidates]),
            )
            if result.rowcount != len(selected):
                raise RegistryError(409, "video_review_changed")
        return {"approved": len(selected)}

    @router.get("/asset/{job_id}/video")
    def asset(
        job_id: UUID, request: Request, principal: Principal = Depends(sessions.principal)
    ) -> Response:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        keys = (repo.workspace_id, job_id)
        range_header = request.headers.get("range", "")
        with repo._connect() as conn:
            response = media_response(
                conn, "SELECT video AS media,'video/mp4' AS media_type "
                "FROM video_clip_jobs WHERE workspace_id=%s "
                "AND id=%s AND status IN ('review','approved')",
                keys, range_header, "video_asset_missing",
            )
            if response is None:
                response = media_response(
                    conn, "SELECT video AS media,'video/mp4' AS media_type "
                    "FROM retained_work_videos WHERE workspace_id=%s AND id=%s",
                    keys, range_header, "video_asset_missing",
                )
        if response is None:
            raise RegistryError(404, "video_asset_missing")
        return response

    @router.get("/asset/{job_id}/last-frame")
    def frame(job_id: UUID, principal: Principal = Depends(sessions.principal)) -> Response:
        repo = RegistryRepository(settings.database_url, principal.workspace_id)
        with repo._connect() as conn:
            row = conn.execute(
                "SELECT video FROM video_clip_jobs WHERE workspace_id=%s AND id=%s "
                "AND status='approved'", (repo.workspace_id, job_id),
            ).fetchone()
        if not row or not row["video"]:
            raise RegistryError(404, "video_asset_missing")
        try:
            png = last_frame(bytes(row["video"]), settings.ffmpeg_path)
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            raise RegistryError(409, "video_frame_extraction_failed") from exc
        return Response(content=png, media_type="image/png")

    return router
