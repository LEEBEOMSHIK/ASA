"""Non-generating provider authentication checks, scoped to workspace and credentials."""
import hashlib
import re
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Any
from uuid import UUID

import httpx

from asa.config import Settings
from asa.video_providers import connection_state, endpoint

TTL = 300
_results: dict[str, tuple[float, dict[str, Any]]] = {}
_lock = Lock()


def _key(settings: Settings, workspace: UUID, provider: str) -> str:
    secret = (settings.higgsfield_api_key if provider == 'higgsfield' else
              settings.wan_api_key if provider == 'alibaba' else settings.runway_api_key)
    return hashlib.sha256((str(workspace) + provider + endpoint(settings, provider)
                           + secret.get_secret_value()).encode()).hexdigest()


def current(settings: Settings, workspace: UUID, provider: str) -> dict[str, Any]:
    configured = connection_state(settings, provider)
    if configured != 'configured':
        return {'status': configured, 'checked_at': None}
    with _lock:
        cached = _results.get(_key(settings, workspace, provider))
        if cached and monotonic() - cached[0] < TTL:
            return dict(cached[1])
    return {'status': 'unchecked', 'checked_at': None}


def check(settings: Settings, workspace: UUID, provider: str) -> dict[str, Any]:
    configured = connection_state(settings, provider)
    if configured != 'configured':
        return {'status': configured, 'checked_at': None}
    secret = (settings.higgsfield_api_key if provider == 'higgsfield' else
              settings.wan_api_key if provider == 'alibaba' else settings.runway_api_key)
    scheme = 'Key' if provider == 'higgsfield' else 'Bearer'
    headers = {'Authorization': f'{scheme} {secret.get_secret_value()}'}
    params: dict[str, int] = {}
    path = '/tasks' if provider == 'alibaba' else '/organization'
    if provider == 'alibaba':
        params = {'page_size': 1}
    else:
        headers['X-Runway-Version'] = '2024-11-06'
    result: dict[str, Any] = {'status': 'unreachable',
                             'checked_at': datetime.now(timezone.utc).isoformat()}
    try:
        if provider == 'higgsfield':
            # Non-generating price probe: no user media or prompt leaves the server.
            response = httpx.post(endpoint(settings, provider) +
                                  '/estimate/alibaba/wan-3.0/text-to-video',
                                  headers={'Authorization': headers['Authorization']},
                                  json={'prompt': 'Connection check', 'duration': 2,
                                        'resolution': '720p', 'aspect_ratio': '16:9',
                                        'generate_audio': False},
                                  timeout=8, follow_redirects=False)
        else:
            response = httpx.get(endpoint(settings, provider) + path, headers=headers,
                                 params=params, timeout=8, follow_redirects=False)
        result['http_status'] = response.status_code
        if response.status_code == 200:
            # An HTML proxy/login page must not be mistaken for successful authentication.
            data = response.json()
            if provider == 'higgsfield':
                from asa.higgsfield_provider import estimate_usd
                estimate_usd(data)
                result['status'] = 'authenticated'
            elif isinstance(data, dict) and not data.get('code') and (
                provider != 'alibaba' or isinstance(data.get('data'), list)
                or (data.get('total_page') == 0 and data.get('page_no') == 1
                    and isinstance(data.get('request_id'), str))
            ):
                result['status'] = 'authenticated'
        elif response.status_code in (401, 403):
            result['status'] = 'denied'
        try:
            data = response.json()
            if isinstance(data, dict):
                code = data.get('code')
                if code in {'InvalidApiKey', 'invalid_api_key', 'AccessDenied',
                            'Forbidden', 'Unauthorized', 'Throttling'}:
                    result['provider_code'] = code
                request_id = data.get('request_id')
                if isinstance(request_id, str) and re.fullmatch(
                    r'[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}', request_id
                ):
                    result['request_id'] = request_id
        except ValueError:
            pass
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        pass
    with _lock:
        for key in list(_results):
            if monotonic() - _results[key][0] >= TTL:
                del _results[key]
        if len(_results) >= 256:
            _results.pop(next(iter(_results)))
        _results[_key(settings, workspace, provider)] = (monotonic(), result)
    return dict(result)
