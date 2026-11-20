import hashlib
import logging
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from asa.config import Settings
from asa.registry.schemas import RegistryError
from asa.video_reference_delivery import (
    audio_url,
    reference_delivery_router,
    require_audio_delivery,
    verify_token,
)


def configured():
    return Settings(_env_file=None, video_reference_public_origin='https://media.example.com',
                    video_reference_signing_key=SecretStr('x' * 40))


def test_delivery_requires_explicit_https_and_secret():
    with pytest.raises(RegistryError, match='video_reference_delivery_unconfigured'):
        require_audio_delivery(Settings(_env_file=None))
    for origin in ('http://media.example.com', 'https://localhost',
                   'https://127.0.0.1', 'https://user:pass@media.example.com',
                   'https://media.example.com/path'):
        settings = configured()
        settings.video_reference_public_origin = origin
        with pytest.raises(RegistryError):
            require_audio_delivery(settings)


def test_token_binds_workspace_job_hash_and_expires(monkeypatch):
    monkeypatch.setattr('asa.video_reference_delivery.time.time', lambda: 1000)
    settings, workspace, job = configured(), uuid4(), {'id': uuid4()}
    ref = {'audio_sha256': 'a' * 64}
    url = audio_url(settings, workspace, job, ref)
    assert url.startswith('https://media.example.com/api/v1/video-reference-audio/')
    assert '.wav?' in url
    token = parse_qs(urlsplit(url).query)['token'][0]
    assert verify_token(settings, job['id'], token) == (workspace, 'a' * 64)
    with pytest.raises(RegistryError):
        verify_token(settings, uuid4(), token)
    with pytest.raises(RegistryError):
        verify_token(settings, job['id'], token[:-1] + ('b' if token[-1] != 'b' else 'c'))
    monkeypatch.setattr('asa.video_reference_delivery.time.time', lambda: 5000)
    with pytest.raises(RegistryError):
        verify_token(settings, job['id'], token)


def test_endpoint_only_delivers_matching_frozen_audio(monkeypatch):
    settings, workspace, job = configured(), uuid4(), {'id': uuid4()}
    audio = b'RIFF-frozen-reference-wave'
    ref = {'audio_sha256': hashlib.sha256(audio).hexdigest(), 'job_id': str(uuid4())}
    request_id = uuid4()
    row = {'request_id': request_id, 'generation_input': {'reference_audio': ref}}
    calls = []

    class Conn:
        def execute(self, sql, params):
            assert 'workspace_id=%s AND id=%s' in sql
            assert params == (workspace, job['id'])
            return SimpleNamespace(fetchone=lambda: row)

    @contextmanager
    def connect(*args, **kwargs):
        yield Conn()

    def resolve(conn, ws, req, reference, ffmpeg):
        calls.append((ws, req, reference))
        return audio

    monkeypatch.setattr('asa.video_reference_delivery.connection', connect)
    monkeypatch.setitem(sys.modules, 'asa.video_references', SimpleNamespace(resolve_audio=resolve))
    app = FastAPI()
    app.include_router(reference_delivery_router(settings))
    client = TestClient(app)
    parts = urlsplit(audio_url(settings, workspace, job, ref))
    path = parts.path + '?' + parts.query
    response = client.get(path)
    assert response.status_code == 200
    assert response.content == audio
    assert response.headers['cache-control'] == 'private, no-store'
    assert calls == [(workspace, request_id, ref)]
    row['generation_input'] = {'reference_audio': {**ref, 'audio_sha256': 'b' * 64}}
    assert client.get(path).status_code == 404
    assert len(calls) == 1
    row['generation_input'] = {'reference_audio': ref}
    audio = b'changed-extracted-wave'
    assert client.get(path).status_code == 404
    assert len(calls) == 2
    row.clear()
    assert client.get(path).status_code == 404
    assert len(calls) == 2


def test_access_log_omits_signed_audio_url():
    reference_delivery_router(configured())
    logger = logging.getLogger('uvicorn.access')
    record = logging.LogRecord('uvicorn.access', logging.INFO, '', 0,
                              'GET /api/v1/video-reference-audio/id.wav?token=secret', (), None)
    assert not logger.filter(record)
