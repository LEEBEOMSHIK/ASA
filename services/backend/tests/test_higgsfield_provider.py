from uuid import uuid4

import httpx
import pytest

from asa.config import Settings
from asa.higgsfield_provider import estimate_request, safe_media_url, upload_media
from asa.video_connection import check
from asa.video_providers import generation_request, provider_connection, task_result


def settings():
    return Settings(_env_file=None, higgsfield_api_key='id:secret', workspace_id=uuid4())


def spec(**changes):
    return dict(prompt='A fox', duration_seconds=7, aspect_ratio='9:16', resolution='720p',
                audio=True, **changes)


def test_profile_merge_preserves_custom_settings():
    cfg = settings()
    profile = cfg.video_model_profiles['wan3'].model_copy(update={'label': 'custom'})
    custom = Settings(_env_file=None, video_model_profiles={'wan3': profile})
    assert custom.video_model_profiles['wan3'].label == 'custom'
    assert custom.video_model_profiles['hf-wan3'].usd_per_second == .075
    custom_hf = cfg.video_model_profiles['hf-wan3'].model_copy(update={'enabled': False})
    assert not Settings(_env_file=None, video_model_profiles={
        'hf-wan3': custom_hf}).video_model_profiles['hf-wan3'].enabled


def test_provider_specific_bodies_and_pinned_endpoint():
    cfg = settings()
    model = cfg.video_model_profiles['hf-wan3'].model_dump()
    url, headers, body = generation_request(cfg, model, spec(), b'',
                                            start_image_url='https://cdn.example.com/start.png')
    assert url == 'https://api.higgsfield.ai/alibaba/wan-3.0/image-to-video'
    assert headers == {'Authorization': 'Key id:secret'}
    assert body['generate_audio'] and body['image_url'].endswith('start.png')
    refs = {'character_image_ids': ['id'], 'audio': [{}], 'video': [{}]}
    media = [{'type': kind, 'url': 'https://cdn.example.com/ref'}
             for kind in ('reference_image', 'reference_audio', 'reference_video')]
    url, _, body = generation_request(cfg, model, spec(reference_inputs=refs), b'', media,
                                      start_image_url='https://cdn.example.com/start.png')
    assert url.endswith('/reference-to-video')
    assert len(body['image_urls']) == 2 and len(body['video_urls']) == 1
    with pytest.raises(ValueError, match='endpoint_changed'):
        provider_connection(cfg, {**model, 'provider_endpoint': 'https://evil.example'})
    with pytest.raises(ValueError, match='missing'):
        generation_request(cfg, model, spec(reference_inputs=refs), b'', [],
                           start_image_url='https://cdn.example.com/start.png')


@pytest.mark.parametrize('url', ['http://example.com/x', 'https://127.0.0.1/x',
                                'https://localhost/x', 'https://user:pass@example.com/x',
                                'data:image/png;base64,AA', 'https://[::1]/x'])
def test_reject_unsafe_media_urls(url):
    with pytest.raises(ValueError):
        safe_media_url(url)


def test_upload_separates_storage_credentials_and_preserves_headers(monkeypatch):
    seen = []
    def handler(request):
        seen.append(request)
        if request.url.host == 'api.higgsfield.ai':
            assert request.headers['Authorization'] == 'Key id:secret'
            return httpx.Response(200, json={'upload_url': 'https://storage.example.com/signed',
                'public_url': 'https://cdn.example.com/ref',
                'upload_headers': {'Content-Type': 'audio/wav', 'x-upload-token': 'signed'}})
        assert 'authorization' not in request.headers
        assert request.headers['x-upload-token'] == 'signed'
        assert request.content == b'wav'
        return httpx.Response(200)
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs:
                        original(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr('asa.higgsfield_provider.socket.getaddrinfo',
                        lambda *a, **k: [(2, 1, 6, '', ('8.8.8.8', 443))])
    cfg = settings()
    assert upload_media(cfg, cfg.video_model_profiles['hf-wan3'].model_dump(), b'wav',
                        'audio/wav') == 'https://cdn.example.com/ref'
    assert len(seen) == 2


def test_estimate_is_non_generating_and_validates_amount():
    cfg = settings()
    def handler(request):
        assert request.url.path == '/estimate/alibaba/wan-3.0/image-to-video'
        return httpx.Response(200, json={'usd': '.525'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert estimate_request(client, cfg, cfg.video_model_profiles['hf-wan3'].model_dump(),
                                spec(), 'https://cdn.example.com/ref') == .525


@pytest.mark.parametrize('data,expected', [({'usd': '.15'}, 'authenticated'),
                                          ({'usd': 'nan'}, 'unreachable'),
                                          ({}, 'unreachable')])
def test_auth_probe_no_user_material(monkeypatch, data, expected):
    def post(url, **kwargs):
        assert url.endswith('/estimate/alibaba/wan-3.0/text-to-video')
        assert kwargs['headers'] == {'Authorization': 'Key id:secret'}
        assert not any(k.endswith('_urls') for k in kwargs['json'])
        return httpx.Response(200, json=data)
    monkeypatch.setattr(httpx, 'post', post)
    cfg = settings()
    assert check(cfg, cfg.workspace_id, 'higgsfield')['status'] == expected


@pytest.mark.parametrize('status,expected', [('queued','PENDING'), ('in_progress','RUNNING'),
                                           ('failed','FAILED'), ('nsfw','FAILED'),
                                           ('canceled','CANCELED')])
def test_status_mapping(status, expected):
    assert task_result('higgsfield', {'status': status}) == (expected, None)


def test_completed_has_video_url():
    assert task_result('higgsfield', {'status': 'completed',
                       'video': {'url': 'https://cdn.example.com/a.mp4'}}) == (
                           'SUCCEEDED', 'https://cdn.example.com/a.mp4')


@pytest.mark.parametrize('failure', ['private_dns', 'auth_header', 'redirect'])
def test_upload_rejects_unsafe_storage_before_sending_bytes(monkeypatch, failure):
    seen = []
    def handler(request):
        seen.append(request)
        assert request.url.host == 'api.higgsfield.ai'
        if failure == 'redirect':
            return httpx.Response(307, headers={'Location': 'https://evil.example.com'})
        return httpx.Response(200, json={
            'upload_url': 'https://storage.example.com/signed',
            'public_url': 'https://cdn.example.com/ref',
            'upload_headers': {'Authorization': 'leaked'} if failure == 'auth_header' else {},
        })
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs:
                        original(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setattr('asa.higgsfield_provider.socket.getaddrinfo',
                        lambda *a, **k: [(2, 1, 6, '', (
                            '127.0.0.1' if failure == 'private_dns' else '8.8.8.8', 443))])
    cfg = settings()
    with pytest.raises((ValueError, httpx.HTTPStatusError)):
        upload_media(cfg, cfg.video_model_profiles['hf-wan3'].model_dump(), b'wav', 'audio/wav')
    assert len(seen) == 1
