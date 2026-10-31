"""Local image worker. Owns long external calls; uncertain jobs are never replayed."""

import argparse
import threading
import time
from typing import Any

from psycopg.types.json import Jsonb

from asa.config import Settings
from asa.database import changes, release_lock
from asa.registry.characters import CharacterRepository
from asa.registry.image_reviews import enqueue_automatic, process_review
from asa.telemetry import redact
from asa.tools.character_images import IMAGE_RATES, generate_image, image_cost, image_prompt


def heartbeat(repo: CharacterRepository) -> None:
    with repo._connect() as conn:
        conn.execute(
            "INSERT INTO image_worker_status(workspace_id) VALUES (%s) "
            "ON CONFLICT(workspace_id) DO UPDATE SET seen_at=now()",
            (repo.workspace_id,),
        )


def tick(settings: Settings) -> bool:
    if not settings.image_ai_enabled:
        return False
    repo = CharacterRepository(settings.database_url, settings.workspace_id)
    with repo._connect() as lock:
        acquired = lock.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS ok",
            (f"asa-image:{repo.workspace_id}",),
        ).fetchone()
        lock.commit()
        if not acquired or not acquired["ok"]:
            return False
        try:
            heartbeat(repo)
            stop = threading.Event()

            def pulse_review() -> None:
                while not stop.wait(30):
                    try:
                        heartbeat(repo)
                    except Exception:
                        pass

            thread = threading.Thread(target=pulse_review, daemon=True)
            thread.start()
            try:
                return process_review(repo, settings) or process(repo, settings)
            finally:
                stop.set()
                thread.join(timeout=1)
        finally:
            release_lock(lock, f"asa-image:{repo.workspace_id}")


def process(repo: CharacterRepository, settings: Settings) -> bool:
    with repo._connect() as conn:
        stale = conn.execute(
            "UPDATE character_image_jobs SET status='unknown',"
            "error_code='worker_interrupted',finished_at=now() "
            "WHERE workspace_id=%s AND status='running' RETURNING id",
            (repo.workspace_id,),
        ).fetchall()
        for row in stale:
            conn.execute(
                "UPDATE ai_usage_events SET status='failed',error_code='worker_interrupted',"
                "finished_at=now() WHERE workspace_id=%s AND id=%s",
                (repo.workspace_id, row["id"]),
            )
        job = conn.execute(
            "SELECT * FROM character_image_jobs WHERE workspace_id=%s "
            "AND status='queued' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED",
            (repo.workspace_id,),
        ).fetchone()
        if not job:
            return False
        conn.execute(
            "UPDATE character_image_jobs SET status='running',started_at=now() "
            "WHERE workspace_id=%s AND id=%s",
            (repo.workspace_id, job["id"]),
        )
        prompt = image_prompt(job["character"], job["change"])
        conn.execute(
            "INSERT INTO ai_usage_events(workspace_id,id,run_id,request_id,source,name,step_id,"
            "step_name,provider,model,original_request,messages,pricing,requested_at,cost_state) "
            "VALUES (%s,%s,%s,%s,'character',%s,%s,%s,'openai',%s,%s,%s,%s,%s,'usage_unknown')",
            (
                repo.workspace_id,
                job["id"],
                str(job["project_id"]),
                str(job["id"]),
                job["character"]["name"],
                job["character_id"],
                "캐릭터 이미지",
                job["model"],
                Jsonb(
                    redact(
                        {
                            "character": job["character"],
                            "change": job["change"],
                            "base_id": str(job["base_id"]) if job["base_id"] else None,
                        },
                        settings,
                    )
                ),
                Jsonb(redact(prompt, settings)),
                Jsonb(
                    {
                        **IMAGE_RATES,
                        "label": "OpenAI Images · USD/1M tokens · 2026-10-30",
                        "source": "https://developers.openai.com/api/docs/pricing",
                    }
                ),
                job["created_at"],
            ),
        )
        reference = None
        if job["base_id"]:
            base = conn.execute(
                "SELECT image FROM character_image_jobs WHERE workspace_id=%s AND id=%s",
                (repo.workspace_id, job["base_id"]),
            ).fetchone()
            assert base and base["image"]
            reference = bytes(base["image"])
    started = time.perf_counter()
    usage: dict[str, Any] | None = None
    image = None
    status, error = "succeeded", None
    try:
        image, usage = generate_image(settings, job["model"], prompt, reference)
    except Exception as exc:
        status, error = "unknown", "image_call_uncertain"
        code = getattr(exc, "status_code", None)
        if code in (400, 401, 403, 404, 422, 429):
            status, error = "failed", f"image_provider_{code}"
    duration = round((time.perf_counter() - started) * 1000)
    known_price = job["model"] in ("gpt-image-2.5-sunburst", "gpt-image-2.5-flare")
    cost = image_cost(usage) if known_price else None
    with repo._connect() as conn:
        conn.execute(
            "UPDATE character_image_jobs SET status=%s,error_code=%s,image=%s,usage=%s,"
            "estimated_usd=%s,finished_at=now() WHERE workspace_id=%s AND id=%s",
            (status, error, image, Jsonb(usage), cost, repo.workspace_id, job["id"]),
        )
        conn.execute(
            "UPDATE ai_usage_events SET status=%s,error_code=%s,usage=%s,estimated_usd=%s,"
            "cost_state=%s,duration_ms=%s,finished_at=now(),response=%s "
            "WHERE workspace_id=%s AND id=%s",
            (
                "succeeded" if status == "succeeded" else "failed",
                error,
                Jsonb(usage),
                cost,
                "estimated"
                if cost is not None
                else "usage_unknown"
                if usage is None
                else "rate_missing",
                duration,
                Jsonb({"image_id": str(job["id"]), "version": job["version"]}),
                repo.workspace_id,
                job["id"],
            ),
        )
        if status == "succeeded":
            try:
                with conn.transaction():
                    enqueue_automatic(repo, job["id"], settings, conn)
            except Exception:
                # A failed optional review must never discard the completed image.
                conn.execute(
                    "UPDATE character_image_jobs SET review_error_code='review_enqueue_failed' "
                    "WHERE workspace_id=%s AND id=%s",
                    (repo.workspace_id, job["id"]),
                )
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    hub = changes(settings.database_url)
    scope = str(settings.workspace_id)
    while True:
        version = hub.version(scope, "image")
        try:
            worked = tick(settings)
        except Exception:
            print("Image worker temporarily unavailable; retrying.", flush=True)
            if args.once:
                raise
            time.sleep(5)
            continue
        if args.once:
            break
        if not worked:
            hub.wait(scope, "image", version, 30)


if __name__ == "__main__":
    main()
