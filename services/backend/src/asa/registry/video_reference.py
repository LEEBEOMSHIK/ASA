"""Workspace-scoped video sources. Network/decoding work happens only in workers."""
import base64
import binascii
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from asa.registry.schemas import RegistryError

FORMAT = 'asa_video_reference_v1'
MAX_BYTES = 20 * 1024 * 1024
ERRORS = {
    'video_all_unavailable': ('모든 영상을 읽지 못했습니다. '
                              '링크를 확인하거나 파일로 다시 요청하세요.'),
    'video_link_invalid': 'YouTube 영상·Shorts 또는 Instagram Reels의 HTTPS 링크를 입력하세요.',
    'video_link_unavailable': '공개 링크의 영상을 읽지 못했습니다. 영상 파일을 업로드해 주세요.',
    'video_upload_invalid': 'MP4·MOV·WebM 영상 파일을 20MB 이하로 올려 주세요.',
    'video_decode_failed': '영상 화면을 읽을 수 없습니다. MP4로 변환해 다시 올려 주세요.',
    'video_duration_limit': '분석할 영상은 5분 이하로 잘라 올려 주세요.',
    'video_decoder_unavailable': '영상 처리기가 준비되지 않았습니다. 관리자에게 문의해 주세요.',
    'video_preparation_timeout': '영상 준비 시간이 초과됐습니다. 짧은 영상 파일로 다시 요청하세요.',
    'video_source_missing': '연결한 영상 자료가 없습니다. 영상을 다시 선택해 주세요.',
    'video_source_limit': '한 번에 최대 5개 영상을 분석할 수 있습니다.',
}


class VideoSource(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str | None = Field(default=None, max_length=2048)
    data: str | None = Field(default=None, max_length=28_000_000)
    filename: str = Field(default='video', max_length=200)

    @model_validator(mode='after')
    def one_source(self) -> 'VideoSource':
        if bool(self.url) == bool(self.data):
            raise ValueError('one_video_source_required')
        return self


def canonical_url(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
        if (parsed.scheme != 'https' or parsed.username or parsed.password
                or parsed.port not in (None, 443)):
            raise ValueError
        host = parsed.hostname
        parts = parsed.path.strip('/').split('/')
        video_id = ''
        if host == 'youtu.be' and len(parts) == 1:
            video_id = parts[0]
        elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
            if parsed.path == '/watch':
                video_id = parse_qs(parsed.query).get('v', [''])[0]
            elif len(parts) == 2 and parts[0] in ('shorts', 'embed'):
                video_id = parts[1]
        elif host in ('instagram.com', 'www.instagram.com'):
            if len(parts) == 2 and parts[0] in ('reel', 'reels'):
                if re.fullmatch(r'[A-Za-z0-9_-]{3,100}', parts[1]):
                    return f'https://www.instagram.com/reel/{parts[1]}/'
        if re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
            return f'https://www.youtube.com/watch?v={video_id}'
    except ValueError:
        pass
    raise RegistryError(422, 'video_link_invalid')


def decode_video(value: str) -> bytes:
    try:
        raw = base64.b64decode(value, validate=True)
        # Container signature gate; full decoder validation follows in the worker.
        if not 16 <= len(raw) <= MAX_BYTES:
            raise ValueError
        if raw[4:8] != b'ftyp' and raw[:4] != b'\x1aE\xdf\xa3':
            raise ValueError
        return raw
    except (ValueError, binascii.Error) as exc:
        raise RegistryError(422, 'video_upload_invalid') from exc


def save_source(repo: Any, body: VideoSource) -> dict[str, str]:
    url = canonical_url(body.url) if body.url else None
    raw = decode_video(body.data) if body.data else None
    source_id = uuid4()
    with repo._connect() as conn:
        conn.execute('INSERT INTO video_references(id,workspace_id,url,video,filename) '
                     'VALUES (%s,%s,%s,%s,%s)',
                     (source_id, repo.workspace_id, url, raw, body.filename))
    return {'format': FORMAT, 'source_id': str(source_id)}


def read_source(repo: Any, source_id: str) -> dict[str, Any]:
    try:
        identifier = UUID(source_id)
    except (ValueError, TypeError) as exc:
        raise RegistryError(422, 'video_source_missing') from exc
    with repo._connect() as conn:
        row = conn.execute('SELECT * FROM video_references WHERE workspace_id=%s AND id=%s',
                           (repo.workspace_id, identifier)).fetchone()
    if not row:
        raise RegistryError(404, 'video_source_missing')
    return dict(row)
