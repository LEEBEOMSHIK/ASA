"""Local video worker. Submit once, persist task ID, then poll that task only."""

import argparse
import re
import subprocess
from io import BytesIO
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
import psycopg
from PIL import Image
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from asa.config import Settings
from asa.registry.schemas import RegistryError
from asa.registry.video_asset_reviews import process_review, recover_reviews
from asa.video_continuity import last_frame, source_video
from asa.video_management import allowed, lock_policy, policy
from asa.video_providers import generation_request, provider_connection, task_result, validate_input
from asa.worker_control import accepting_work, run_worker

MAX_VIDEO_BYTES = 64 * 1024 * 1024


def safe_diagnostics(stage: str, exc: Exception | None = None,
                     response: httpx.Response | None = None) -> dict[str, Any]:
    """Store machine identifiers only, never exception text or response messages."""
    category = "provider_failure"
    if isinstance(exc, httpx.HTTPStatusError):
        category, response = "http_status", exc.response
    elif isinstance(exc, httpx.TimeoutException):
        category = "timeout"
    elif isinstance(exc, httpx.TransportError):
        category = "transport"
    elif exc is not None:
        category = "invalid_response"
    result: dict[str, Any] = {"stage": stage, "category": category}
    if response is None:
        return result
    result["http_status"] = response.status_code
    try:
        data = response.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    output = data.get("output")
    output = output if isinstance(output, dict) else {}
    candidates = {
        "provider_code": output.get("code") or data.get("code") or data.get("failureCode"),
        "request_id": data.get("request_id") or response.headers.get("x-request-id")
        or response.headers.get("x-dashscope-request-id"),
    }
    for name, value in candidates.items():
        if (isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value)
                and not value.lower().startswith(("sk-", "bearer", "api_key", "apikey"))):
            result[name] = value
    return result


def fetch_video(url: str) -> bytes:
    if urlsplit(url).scheme != "https":
        raise ValueError("invalid_video_url")
    # Use a separate client: signed output URLs must never receive provider credentials.
    data = bytearray()
    with httpx.stream("GET", url, timeout=90) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            if len(data) + len(chunk) > MAX_VIDEO_BYTES:
                raise ValueError("video_too_large")
            data.extend(chunk)
    if data[4:8] != b"ftyp":
        raise ValueError("invalid_mp4")
    return bytes(data)


def process(conn: Any, client: httpx.Client, workspace: UUID, settings: Settings) -> bool:
    row = conn.execute(
        "SELECT * FROM video_clip_jobs WHERE superseded_by IS NULL AND workspace_id=%s "
        "AND status IN ('queued','running') "
        "AND (status='running' OR NOT paused) AND next_poll<=now() "
        "ORDER BY (status='running') DESC,next_poll,id LIMIT 1",
        (workspace,),
    ).fetchone()
    if not row:
        return process_review(conn, workspace, settings)
    key = (workspace, row["id"])
    model = row["model_snapshot"]
    try:
        base, headers = provider_connection(settings, model)
    except ValueError as exc:
        if str(exc) == "endpoint_changed":
            conn.execute(
                "UPDATE video_clip_jobs SET status='unknown',"
                "error_code='endpoint_changed',"
                "updated_at=now() WHERE workspace_id=%s AND id=%s",
                key,
            )
        else:
            conn.execute(
                "UPDATE video_clip_jobs SET next_poll=now()+interval '60 seconds',"
                "error_code='provider_configuration_missing' "
                "WHERE workspace_id=%s AND id=%s",
                key,
            )
        return True
    if row["status"] == "queued":
        spec = row["generation_input"]
        asset = conn.execute(
            "SELECT image FROM character_image_jobs WHERE workspace_id=%s "
            "AND id=%s AND status='succeeded'",
            (workspace, spec["start_image_id"]),
        ).fetchone()
        if spec.get("connection_type") == "continue":
            try:
                video = source_video(conn, workspace, row)
                asset = {"image": last_frame(video, settings.ffmpeg_path)}
            except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
                code = (str(exc) if isinstance(exc, ValueError)
                        else "video_frame_extraction_failed")
                conn.execute(
                    "UPDATE video_clip_jobs SET status='failed',error_code=%s,"
                    "updated_at=now() WHERE workspace_id=%s AND id=%s", (code, *key),
                )
                return True
        max_image_bytes = (20_000_000 if model["provider"] in {'alibaba', 'higgsfield'}
                           else 3_700_000)
        if not asset or not asset["image"] or len(asset["image"]) > max_image_bytes:
            conn.execute(
                "UPDATE video_clip_jobs SET status='failed',error_code='reference_size',"
                "updated_at=now() WHERE workspace_id=%s AND id=%s",
                key,
            )
            return True
        try:
            reference_media = None
            upload_media_inputs: list[tuple[str, bytes, str]] = []
            if model['provider'] == 'higgsfield':
                from asa.video_references import resolve_upload_media

                validate_input(model, spec)
                resolved_image, upload_media_inputs = resolve_upload_media(
                    conn, settings, workspace, row)
                if spec.get('connection_type') != 'continue':
                    asset = {'image': resolved_image}
            elif spec.get('reference_inputs') is not None:
                from asa.video_references import resolve_media

                resolved_image, reference_media = resolve_media(conn, settings, workspace, row)
                asset = {'image': resolved_image}
            if model["provider"] == "alibaba":
                with Image.open(BytesIO(bytes(asset["image"]))) as reference:
                    if reference.format != "PNG" or not all(
                        240 <= d <= 8000 for d in reference.size
                    ):
                        raise ValueError("invalid_reference")
                    if max(reference.size) / min(reference.size) > 8:
                        raise ValueError("invalid_reference")
                    if "A" in reference.getbands() or "transparency" in reference.info:
                        if reference.convert("RGBA").getchannel("A").getextrema() != (255, 255):
                            raise ValueError("transparent_reference")
            if model['provider'] != 'higgsfield':
                url, headers, body = generation_request(
                    settings, model, spec, bytes(asset['image']), reference_media)
        except (KeyError, TypeError, ValueError, OSError, RegistryError, subprocess.TimeoutExpired):
            conn.execute(
                "UPDATE video_clip_jobs SET status='failed',error_code='input_invalid',"
                "updated_at=now() WHERE workspace_id=%s AND id=%s",
                key,
            )
            return True
        # Serialize the final reservation with disable/stop, without holding a DB
        # transaction during the external request. Reserved submissions may finish.
        with conn.transaction():
            lock_policy(conn, workspace)
            if not allowed(policy(conn, settings, workspace), model["provider"]):
                conn.execute("UPDATE video_clip_jobs SET paused=true WHERE workspace_id=%s "
                             "AND id=%s AND status='queued'", key)
                return False
            if not accepting_work(conn, workspace, "video"):
                return False
            claimed = conn.execute(
                "UPDATE video_clip_jobs SET status='submitting',progress_stage='submitting',"
                "updated_at=now() "
                "WHERE workspace_id=%s AND id=%s AND status='queued' AND NOT paused",
                key,
            )
            if not claimed.rowcount:
                return False
        response = None
        submission_started = False
        try:
            if model['provider'] == 'higgsfield':
                from asa.higgsfield_provider import upload_media

                image_url = upload_media(settings, model, bytes(asset['image']), 'image/png')
                reference_media = [{'type': kind, 'url': upload_media(settings, model, data, mime)}
                                   for kind, data, mime in upload_media_inputs]
                url, headers, body = generation_request(
                    settings, model, spec, bytes(asset['image']), reference_media,
                    start_image_url=image_url)
                headers['Idempotency-Key'] = str(row['id'])
            submission_started = True
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            task = (data['output']['task_id'] if model['provider'] == 'alibaba' else
                    data['request_id'] if model['provider'] == 'higgsfield' else data['id'])
            if not isinstance(task, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", task):
                raise ValueError("invalid_task_id")
        except (httpx.HTTPError, KeyError, TypeError, ValueError, OSError) as exc:
            rejected = isinstance(exc, httpx.HTTPStatusError) and (
                400 <= exc.response.status_code < 500 and exc.response.status_code != 408
            )
            conn.execute(
                "UPDATE video_clip_jobs SET status=%s,error_code=%s,diagnostics=%s,"
                "updated_at=now() "
                "WHERE workspace_id=%s AND id=%s",
                (
                    "failed" if rejected or not submission_started else "unknown",
                    ('reference_upload_failed' if not submission_started else
                     'provider_rejected' if rejected else 'submission_uncertain'),
                    Jsonb(safe_diagnostics('submitting' if submission_started else 'uploading',
                                          exc, response)),
                    *key,
                ),
            )
            return True
        conn.execute(
            "UPDATE video_clip_jobs SET status='running',provider_task=%s,error_code=NULL,"
            "diagnostics='{}',progress_stage='provider_pending',"
            "next_poll=now()+interval '5 seconds',updated_at=now() "
            "WHERE workspace_id=%s AND id=%s",
            (task, *key),
        )
        return True
    conn.execute(
        "UPDATE video_clip_jobs SET next_poll=now()+interval '15 seconds' "
        "WHERE workspace_id=%s AND id=%s",
        key,
    )
    response = None
    phase = "polling"
    try:
        task_id = str(row["provider_task"])
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", task_id):
            raise ValueError("invalid_task_id")
        if model["provider"] == "runway":
            headers["X-Runway-Version"] = "2024-11-06"
        poll_url = (f'{base}/requests/{task_id}/status' if model['provider'] == 'higgsfield'
                    else f'{base}/tasks/{task_id}')
        response = client.get(poll_url, headers=headers)
        if response.status_code == 404:
            conn.execute(
                "UPDATE video_clip_jobs SET status='unknown',error_code='task_missing',"
                "diagnostics=%s,updated_at=now() WHERE workspace_id=%s AND id=%s",
                (Jsonb(safe_diagnostics("polling", response=response)), *key),
            )
            return True
        response.raise_for_status()
        status, video_url = task_result(model["provider"], response.json())
        conn.execute(
            "UPDATE video_clip_jobs SET provider_status=%s,progress_stage=%s,"
            "error_code=NULL,diagnostics='{}',updated_at=now() WHERE workspace_id=%s AND id=%s",
            (status, "provider_running" if status == "RUNNING" else "provider_pending", *key),
        )
        if status == "UNKNOWN":
            conn.execute(
                "UPDATE video_clip_jobs SET status='unknown',error_code='task_missing',"
                "diagnostics=%s,updated_at=now() WHERE workspace_id=%s AND id=%s",
                (Jsonb(safe_diagnostics("polling", response=response)), *key),
            )
        elif status in ("FAILED", "CANCELED", "CANCELLED"):
            conn.execute(
                "UPDATE video_clip_jobs SET status='failed',error_code='provider_failed',"
                "diagnostics=%s,updated_at=now() WHERE workspace_id=%s AND id=%s",
                (Jsonb(safe_diagnostics("provider_running", response=response)), *key),
            )
        elif status == "SUCCEEDED" and video_url:
            phase = "downloading"
            conn.execute(
                "UPDATE video_clip_jobs SET progress_stage='downloading',updated_at=now() "
                "WHERE workspace_id=%s AND id=%s", key,
            )
            response = None
            video = fetch_video(video_url)
            conn.execute(
                "UPDATE video_clip_jobs SET status='review',progress_stage='review',"
                "video=%s,updated_at=now() "
                "WHERE workspace_id=%s AND id=%s",
                (video, *key),
            )
    except httpx.HTTPError as exc:
        # Reconcile the same task only: never repeat the paid submission.
        conn.execute(
            "UPDATE video_clip_jobs SET error_code=%s,diagnostics=%s,updated_at=now() "
            "WHERE workspace_id=%s AND id=%s",
            ("download_failed" if phase == "downloading" else "poll_failed",
             Jsonb(safe_diagnostics(phase, exc, response)), *key),
        )
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        conn.execute(
            "UPDATE video_clip_jobs SET status='unknown',error_code='output_invalid',"
            "diagnostics=%s,updated_at=now() WHERE workspace_id=%s AND id=%s",
            (Jsonb(safe_diagnostics(phase, exc, response)), *key),
        )
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-token", type=UUID)
    args = parser.parse_args()
    settings = Settings()
    if not settings.database_url:
        raise SystemExit("ASA_DATABASE_URL required")
    workspace = settings.workspace_id
    with psycopg.connect(
        settings.database_url,
        autocommit=True,
        row_factory=dict_row,
        application_name=f"asa-video-{workspace}",
    ) as conn:
        locked = conn.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS acquired",
            (f"asa-video:{workspace}",),
        ).fetchone()
        if not locked or not locked["acquired"]:
            raise SystemExit("A video worker already owns this workspace")
        conn.execute("LISTEN asa_video_jobs")
        recover_reviews(conn, workspace)
        conn.execute(
            "UPDATE video_clip_jobs SET status='unknown',error_code='worker_interrupted',"
            "updated_at=now() WHERE workspace_id=%s AND status='submitting'",
            (workspace,),
        )
        with httpx.Client(timeout=60) as client:
            run_worker(settings, "video", lambda: process(conn, client, workspace, settings),
                       args.control_token)


if __name__ == "__main__":
    main()
