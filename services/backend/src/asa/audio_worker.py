"""Local audio queue consumer. No automatic replay of an uncertain speech request."""

import argparse
from typing import Any
from uuid import UUID

from asa.audio_contracts import Music, fingerprint
from asa.audio_media import compose, wav_duration
from asa.audio_provider import synthesize, transcript_matches
from asa.config import Settings
from asa.database import connection
from asa.registry import audio_service as service
from asa.registry.schemas import RegistryError
from asa.worker_control import accepting_work, run_worker


class AudioWorker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.recovered = False

    def tick(self) -> bool:
        settings, workspace = self.settings, self.settings.workspace_id
        with connection(settings.database_url, dictionary=True) as conn:
            if not self.recovered:
                conn.execute(
                    "UPDATE audio_jobs SET status='unknown',error_code='worker_interrupted',"
                    "updated_at=now() WHERE workspace_id=%s AND status='running'",
                    (workspace,),
                )
                self.recovered = True
            if not accepting_work(conn, workspace, "audio"):
                return False
            count = conn.execute(
                "SELECT count(*) AS n FROM audio_jobs WHERE workspace_id=%s "
                "AND kind='speech' AND started_at>=date_trunc('day',now())",
                (workspace,),
            ).fetchone()
            can_speak = bool(
                settings.audio_ai_enabled
                and settings.audio_key().get_secret_value()
                and count
                and count["n"] < settings.audio_daily_calls
            )
            job = conn.execute(
                "SELECT * FROM audio_jobs WHERE workspace_id=%s AND status='queued' "
                "AND (kind='compose' OR %s) ORDER BY created_at,id LIMIT 1 FOR UPDATE SKIP LOCKED",
                (workspace, can_speak),
            ).fetchone()
            if not job:
                return False
            conn.execute(
                "UPDATE audio_jobs SET status='running',started_at=now(),updated_at=now() "
                "WHERE workspace_id=%s AND id=%s",
                (workspace, job["id"]),
            )
        # Commit before a paid call; run_worker holds the lifetime advisory lock.
        try:
            with connection(settings.database_url, dictionary=True) as conn:
                current = service.load(conn, workspace, job["request_id"], job["answer_version"])
                if job["kind"] == "speech":
                    if job["input"].get("purpose") != "sample" and not current["settings"].enabled:
                        raise RegistryError(409, "audio_disabled")
                    spec = service.job_speech_spec(settings, current["settings"], job)
                    if job['input'].get('purpose') == 'production':
                        service.require_selected_voice(conn, settings, current['settings'],
                                                       spec['cue']['speaker_id'])
                    if service.speech_key(spec) != job["fingerprint"]:
                        raise RegistryError(409, "audio_source_changed")
                else:
                    spec = service.composition_spec(
                        conn,
                        settings,
                        workspace,
                        job["request_id"],
                        job["answer_version"],
                        current,
                        job["input"]["remove_original"],
                    )
                    if fingerprint(spec) != job["fingerprint"]:
                        raise RegistryError(409, "audio_source_changed")
                    videos = [
                        (self.asset(conn, "video_clip_jobs", "video", v["id"]), v["duration"])
                        for v in spec["videos"]
                    ]
                    voices = [
                        (self.asset(conn, "audio_jobs", "media", a["id"]), a["start"])
                        for a in spec["speech"]
                    ]
                    music = (
                        self.asset(conn, "audio_assets", "data", spec["music"]["id"])
                        if spec["music"]
                        else None
                    )
            error = None
            transcript = ""
            if job["kind"] == "speech":
                media, transcript = synthesize(
                    settings.audio_key().get_secret_value(), job["input"]
                )
                seconds = wav_duration(media)
                if not transcript_matches(job["input"]["cue"]["text"], transcript):
                    error = "audio_transcript_mismatch"
            else:
                media = compose(
                    videos,
                    voices,
                    music,
                    Music.model_validate(spec["settings"]["music"]),
                    settings.ffmpeg_path,
                )
                seconds = sum(v["duration"] for v in spec["videos"])
            with connection(settings.database_url, dictionary=True) as conn:
                conn.execute(
                    "UPDATE audio_jobs SET status='review',media=%s,duration=%s,"
                    "transcript=%s,error_code=%s,updated_at=now() WHERE workspace_id=%s AND id=%s",
                    (media, seconds, transcript, error, workspace, job["id"]),
                )
                if job['input'].get('purpose') == 'timing':
                    from asa.scene_timing import finish_timing
                    finish_timing(conn, settings, str(job['request_id']), job['answer_version'])
        except Exception as exc:
            # Error details may contain credentials or user scripts. Store only allowlisted codes.
            code = exc.code if isinstance(exc, RegistryError) else "audio_processing_failed"
            if isinstance(exc, ValueError) and str(exc) in {
                "audio_video_too_short",
                "audio_music_timing",
                "audio_timing_adjustment_required",
            }:
                code = str(exc)
            status = (
                "failed"
                if isinstance(exc, RegistryError) or job["kind"] == "compose"
                else "unknown"
            )
            with connection(settings.database_url) as conn:
                conn.execute(
                    "UPDATE audio_jobs SET status=%s,error_code=%s,updated_at=now() "
                    "WHERE workspace_id=%s AND id=%s",
                    (status, code, workspace, job["id"]),
                )
        return True

    def asset(self, conn: Any, table: str, column: str, asset_id: str) -> bytes:
        from psycopg import sql

        row = conn.execute(
            sql.SQL("SELECT {} AS data FROM {} WHERE workspace_id=%s AND id=%s").format(
                sql.Identifier(column), sql.Identifier(table)
            ),
            (self.settings.workspace_id, asset_id),
        ).fetchone()
        if not row or not row["data"]:
            raise RegistryError(404, "audio_asset_missing")
        return bytes(row["data"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-token", type=UUID)
    args = parser.parse_args()
    settings = Settings()
    run_worker(settings, "audio", AudioWorker(settings).tick, args.control_token)


if __name__ == "__main__":
    main()
