"""Consume local composition jobs within the existing audio worker lifetime lock."""

from asa.config import Settings
from asa.database import connection
from asa.editing_contracts import EditPlan
from asa.editing_media import render
from asa.worker_control import accepting_work


def recover(settings: Settings) -> None:
    with connection(settings.database_url) as conn:
        conn.execute(
            "UPDATE editing_jobs SET status='failed',error_code='editing_interrupted',"
            "finished_at=now() WHERE workspace_id=%s AND status='running'",
            (settings.workspace_id,),
        )


def tick(settings: Settings) -> bool:
    with connection(settings.database_url, dictionary=True) as conn:
        if not accepting_work(conn, settings.workspace_id, "audio"):
            return False
        job = conn.execute(
            "SELECT * FROM editing_jobs WHERE workspace_id=%s AND status='queued' "
            "ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED",
            (settings.workspace_id,),
        ).fetchone()
        if not job:
            return False
        conn.execute(
            "UPDATE editing_jobs SET status='running',started_at=now() "
            "WHERE workspace_id=%s AND id=%s",
            (settings.workspace_id, job["id"]),
        )
        rows = conn.execute(
            "SELECT source_id,data FROM editing_job_assets WHERE workspace_id=%s AND job_id=%s",
            (settings.workspace_id, job["id"]),
        ).fetchall()
    error, media = None, None
    try:
        media = render(
            EditPlan.model_validate(job["plan"]),
            {r["source_id"]: bytes(r["data"]) for r in rows},
            settings.ffmpeg_path,
        )
    except Exception as exc:
        code = str(exc)
        error = (
            code
            if code
            in {
                "editing_media_invalid",
                "editing_source_too_short",
                "editing_caption_font_missing",
                "editing_caption_too_long",
                "editing_render_failed",
            }
            else "editing_render_failed"
        )
    with connection(settings.database_url) as conn:
        conn.execute(
            "UPDATE editing_jobs SET status=%s,error_code=%s,media=%s,finished_at=now() "
            "WHERE workspace_id=%s AND id=%s",
            ("failed" if error else "review", error, media, settings.workspace_id, job["id"]),
        )
    return True
