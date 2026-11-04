"""Local Runway worker. Submit once, persist task ID, then poll that task only."""
import base64
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
import psycopg
from psycopg.rows import dict_row

from asa.config import Settings

API = "https://api.dev.runwayml.com/v1"
MAX_VIDEO_BYTES = 64 * 1024 * 1024


def fetch_video(url: str) -> bytes:
    if urlsplit(url).scheme != "https":
        raise ValueError("invalid_video_url")
    # Use a separate client: signed output URLs must never receive the Runway key.
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


def process(conn: Any, client: httpx.Client, workspace: UUID) -> bool:
    row = conn.execute(
        "SELECT * FROM video_clip_jobs WHERE workspace_id=%s AND status IN ('queued','running') "
        "AND next_poll<=now() ORDER BY next_poll,id LIMIT 1", (workspace,),
    ).fetchone()
    if not row:
        return False
    key = (workspace, row["id"])
    if row["status"] == "queued":
        spec = row["generation_input"]
        asset = conn.execute("SELECT image FROM character_image_jobs WHERE workspace_id=%s "
                             "AND id=%s AND status='succeeded'", (workspace, spec["start_image_id"])
                             ).fetchone()
        if not asset or not asset["image"] or len(asset["image"]) > 3_700_000:
            conn.execute("UPDATE video_clip_jobs SET status='failed',error_code='reference_size',"
                         "updated_at=now() WHERE workspace_id=%s AND id=%s", key)
            return True
        image = base64.b64encode(asset["image"]).decode("ascii")
        body = {"model": row["model_snapshot"]["model"], "promptText": spec["prompt"],
                "promptImage": "data:image/png;base64," + image,
                "ratio": {"9:16": "720:1280", "16:9": "1280:720"}[spec["aspect_ratio"]],
                "duration": spec["duration_seconds"]}
        conn.execute("UPDATE video_clip_jobs SET status='submitting',updated_at=now() "
                     "WHERE workspace_id=%s AND id=%s", key)
        try:
            response = client.post(f"{API}/image_to_video", json=body)
            response.raise_for_status()
            task = UUID(response.json()["id"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            rejected = isinstance(exc, httpx.HTTPStatusError) and (
                400 <= exc.response.status_code < 500 and exc.response.status_code != 408)
            conn.execute("UPDATE video_clip_jobs SET status=%s,error_code=%s,updated_at=now() "
                         "WHERE workspace_id=%s AND id=%s",
                         ("failed" if rejected else "unknown",
                          "provider_rejected" if rejected else "submission_uncertain", *key))
            return True
        conn.execute("UPDATE video_clip_jobs SET status='running',provider_task=%s,"
                     "next_poll=now()+interval '5 seconds',updated_at=now() "
                     "WHERE workspace_id=%s AND id=%s", (task, *key))
        return True
    conn.execute("UPDATE video_clip_jobs SET next_poll=now()+interval '10 seconds' "
                 "WHERE workspace_id=%s AND id=%s", key)
    try:
        response = client.get(f"{API}/tasks/{row['provider_task']}")
        if response.status_code == 404:
            conn.execute("UPDATE video_clip_jobs SET status='unknown',error_code='task_missing',"
                         "updated_at=now() WHERE workspace_id=%s AND id=%s", key)
            return True
        response.raise_for_status()
        task_result = response.json()
        if task_result["status"] in ("FAILED", "CANCELED", "CANCELLED"):
            conn.execute("UPDATE video_clip_jobs SET status='failed',error_code='provider_failed',"
                         "updated_at=now() WHERE workspace_id=%s AND id=%s", key)
        elif task_result["status"] == "SUCCEEDED":
            video = fetch_video(task_result["output"][0])
            conn.execute("UPDATE video_clip_jobs SET status='review',video=%s,updated_at=now() "
                         "WHERE workspace_id=%s AND id=%s", (video, *key))
    except httpx.HTTPError:
        # Reconcile the same provider task after a transient failure.
        pass
    except (KeyError, IndexError, ValueError, TypeError):
        conn.execute("UPDATE video_clip_jobs SET status='unknown',error_code='output_invalid',"
                     "updated_at=now() WHERE workspace_id=%s AND id=%s", key)
    return True


def main() -> None:
    settings = Settings()
    token = settings.runway_api_key.get_secret_value()
    if not settings.video_ai_enabled or not token or not settings.database_url:
        raise SystemExit("ASA_DATABASE_URL, ASA_VIDEO_AI_ENABLED and ASA_RUNWAY_API_KEY required")
    workspace = settings.workspace_id
    with psycopg.connect(settings.database_url, autocommit=True, row_factory=dict_row,
                         application_name=f"asa-video-{workspace}") as conn:
        locked = conn.execute("SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS acquired",
                              (f"asa-video:{workspace}",)).fetchone()
        if not locked or not locked["acquired"]:
            raise SystemExit("A video worker already owns this workspace")
        conn.execute("LISTEN asa_video_jobs")
        conn.execute("UPDATE video_clip_jobs SET status='unknown',error_code='worker_interrupted',"
                     "updated_at=now() WHERE workspace_id=%s AND status='submitting'", (workspace,))
        with httpx.Client(headers={"Authorization": f"Bearer {token}",
                                   "X-Runway-Version": "2024-11-06"}, timeout=60) as client:
            while True:
                if not process(conn, client, workspace):
                    pending = conn.execute("SELECT 1 FROM video_clip_jobs WHERE workspace_id=%s "
                                           "AND status='running' LIMIT 1", (workspace,)).fetchone()
                    next(conn.notifies(timeout=5 if pending else 60, stop_after=1), None)


if __name__ == "__main__":
    main()
