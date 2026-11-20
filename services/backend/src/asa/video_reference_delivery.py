"""Short-lived bearer links for one frozen job's reference voice segment only."""

import hashlib
import hmac
import ipaddress
import logging
import re
import time
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response

from asa.config import Settings
from asa.database import connection
from asa.registry.schemas import RegistryError

PREFIX = '/api/v1/video-reference-audio/'


def require_audio_delivery(settings: Settings) -> None:
    """Configuration is explicit; this code never provisions public network exposure."""
    origin = urlsplit(settings.video_reference_public_origin)
    host = (origin.hostname or '').lower()
    invalid = (origin.scheme != 'https' or not host or origin.username or origin.password
               or origin.path not in ('', '/') or origin.query or origin.fragment
               or host == 'localhost' or host.endswith(('.localhost', '.local'))
               or len(settings.video_reference_signing_key.get_secret_value()) < 32)
    try:
        invalid = invalid or not ipaddress.ip_address(host).is_global
    except ValueError:
        pass
    if invalid:
        raise RegistryError(409, 'video_reference_delivery_unconfigured')


def _signature(settings: Settings, payload: str) -> str:
    return hmac.new(settings.video_reference_signing_key.get_secret_value().encode(),
                    payload.encode(), hashlib.sha256).hexdigest()


def audio_url(settings: Settings, workspace: UUID, job: dict[str, Any],
              reference: dict[str, Any]) -> str:
    require_audio_delivery(settings)
    digest = str(reference.get('audio_sha256', ''))
    if not re.fullmatch('[0-9a-f]{64}', digest):
        raise RegistryError(409, 'video_reference_audio_changed')
    job_id = UUID(str(job['id']))
    expires = int(time.time()) + settings.video_reference_url_ttl_seconds
    payload = f'{workspace}.{job_id}.{digest}.{expires}'
    token = f'{payload}.{_signature(settings, payload)}'
    return (f'{settings.video_reference_public_origin.rstrip("/")}{PREFIX}'
            f'{job_id}.wav?token={token}')


def verify_token(settings: Settings, job_id: UUID, token: str) -> tuple[UUID, str]:
    require_audio_delivery(settings)
    try:
        workspace, target, digest, expires, signature = token.split('.')
        payload = '.'.join((workspace, target, digest, expires))
        expiry = int(expires)
        now = int(time.time())
        if (not hmac.compare_digest(signature, _signature(settings, payload))
                or UUID(target) != job_id or expiry <= now
                or expiry > now + settings.video_reference_url_ttl_seconds
                or not re.fullmatch('[0-9a-f]{64}', digest)):
            raise ValueError('invalid token')
        return UUID(workspace), digest
    except (ValueError, TypeError):
        raise RegistryError(404, 'video_reference_audio_unavailable') from None


class _PrivateAudioAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Uvicorn access records include raw query strings. Never record bearer URLs.
        return PREFIX not in record.getMessage()


def reference_delivery_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    logger = logging.getLogger('uvicorn.access')
    if not any(isinstance(item, _PrivateAudioAccessFilter) for item in logger.filters):
        logger.addFilter(_PrivateAudioAccessFilter())

    @router.get(PREFIX + '{job_id}.wav', include_in_schema=False)
    def reference_audio(job_id: UUID, token: str = Query(max_length=400)) -> Response:
        # A provider cannot carry a user session. Its bearer token authorizes only this
        # job + workspace + audio digest, never a caller-selected source asset.
        from asa.video_references import resolve_audio

        try:
            workspace, digest = verify_token(settings, job_id, token)
            with connection(settings.database_url, dictionary=True) as conn:
                job = conn.execute(
                    'SELECT request_id,generation_input FROM video_clip_jobs '
                    'WHERE workspace_id=%s AND id=%s', (workspace, job_id)).fetchone()
                if not job:
                    raise ValueError('missing job')
                reference = job['generation_input'].get('reference_audio')
                if not isinstance(reference, dict) or reference.get('audio_sha256') != digest:
                    raise ValueError('changed audio')
                audio = resolve_audio(conn, workspace, job['request_id'], reference,
                                      settings.ffmpeg_path)
                if hashlib.sha256(audio).hexdigest() != digest:
                    raise ValueError('changed audio')
        except (RegistryError, ValueError):
            raise HTTPException(404, detail='video_reference_audio_unavailable') from None
        return Response(audio, media_type='audio/wav', headers={
            'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
            'Content-Disposition': 'inline; filename="reference.wav"',
            'Referrer-Policy': 'no-referrer'})

    return router
