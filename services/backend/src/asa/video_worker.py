"""Local video worker. Submit once, persist task ID, then poll that task only."""

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

from asa.config import Settings
from asa.video_continuity import last_frame, source_video
from asa.video_providers import generation_request, provider_connection, task_result

MAX_VIDEO_BYTES = 64 * 1024 * 1024


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
        "SELECT * FROM video_clip_jobs WHERE workspace_id=%s AND status IN ('queued','running') "
        "AND next_poll<=now() ORDER BY next_poll,id LIMIT 1",
        (workspace,),
    ).fetchone()
    if not row:
        return False
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
        max_image_bytes = 20_000_000 if model["provider"] == "alibaba" else 3_700_000
        if not asset or not asset["image"] or len(asset["image"]) > max_image_bytes:
            conn.execute(
                "UPDATE video_clip_jobs SET status='failed',error_code='reference_size',"
                "updated_at=now() WHERE workspace_id=%s AND id=%s",
                key,
            )
            return True
        try:
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
            url, headers, body = generation_request(settings, model, spec, bytes(asset["image"]))
        except (KeyError, TypeError, ValueError, OSError):
            conn.execute(
                "UPDATE video_clip_jobs SET status='failed',error_code='input_invalid',"
                "updated_at=now() WHERE workspace_id=%s AND id=%s",
                key,
            )
            return True
        conn.execute(
            "UPDATE video_clip_jobs SET status='submitting',updated_at=now() "
            "WHERE workspace_id=%s AND id=%s",
            key,
        )
        try:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            task = data["output"]["task_id"] if model["provider"] == "alibaba" else data["id"]
            if not isinstance(task, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", task):
                raise ValueError("invalid_task_id")
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            rejected = isinstance(exc, httpx.HTTPStatusError) and (
                400 <= exc.response.status_code < 500 and exc.response.status_code != 408
            )
            conn.execute(
                "UPDATE video_clip_jobs SET status=%s,error_code=%s,updated_at=now() "
                "WHERE workspace_id=%s AND id=%s",
                (
                    "failed" if rejected else "unknown",
                    "provider_rejected" if rejected else "submission_uncertain",
                    *key,
                ),
            )
            return True
        conn.execute(
            "UPDATE video_clip_jobs SET status='running',provider_task=%s,error_code=NULL,"
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
    try:
        task_id = str(row["provider_task"])
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", task_id):
            raise ValueError("invalid_task_id")
        if model["provider"] == "runway":
            headers["X-Runway-Version"] = "2024-11-06"
        response = client.get(f"{base}/tasks/{task_id}", headers=headers)
        if response.status_code == 404:
            conn.execute(
                "UPDATE video_clip_jobs SET status='unknown',error_code='task_missing',"
                "updated_at=now() WHERE workspace_id=%s AND id=%s",
                key,
            )
            return True
        response.raise_for_status()
        status, video_url = task_result(model["provider"], response.json())
        if status == "UNKNOWN":
            conn.execute(
                "UPDATE video_clip_jobs SET status='unknown',error_code='task_missing',"
                "updated_at=now() WHERE workspace_id=%s AND id=%s",
                key,
            )
        elif status in ("FAILED", "CANCELED", "CANCELLED"):
            conn.execute(
                "UPDATE video_clip_jobs SET status='failed',error_code='provider_failed',"
                "updated_at=now() WHERE workspace_id=%s AND id=%s",
                key,
            )
        elif status == "SUCCEEDED" and video_url:
            video = fetch_video(video_url)
            conn.execute(
                "UPDATE video_clip_jobs SET status='review',video=%s,updated_at=now() "
                "WHERE workspace_id=%s AND id=%s",
                (video, *key),
            )
    except httpx.HTTPError:
        # Reconcile the same provider task after a transient failure.
        pass
    except (KeyError, IndexError, ValueError, TypeError):
        conn.execute(
            "UPDATE video_clip_jobs SET status='unknown',error_code='output_invalid',"
            "updated_at=now() WHERE workspace_id=%s AND id=%s",
            key,
        )
    return True


def main() -> None:
    settings = Settings()
    if not settings.video_ai_enabled or not settings.database_url:
        raise SystemExit("ASA_DATABASE_URL and ASA_VIDEO_AI_ENABLED required")
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
        conn.execute(
            "UPDATE video_clip_jobs SET status='unknown',error_code='worker_interrupted',"
            "updated_at=now() WHERE workspace_id=%s AND status='submitting'",
            (workspace,),
        )
        with httpx.Client(timeout=60) as client:
            while True:
                if not process(conn, client, workspace, settings):
                    pending = conn.execute(
                        "SELECT 1 FROM video_clip_jobs WHERE workspace_id=%s "
                        "AND status='running' LIMIT 1",
                        (workspace,),
                    ).fetchone()
                    next(conn.notifies(timeout=5 if pending else 60, stop_after=1), None)


if __name__ == "__main__":
    main()
