"""Shared, administrator-managed visual presets. Saved works retain their own snapshot."""
import base64
from io import BytesIO
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from PIL import Image
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.character_uploads import decode_image
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError
from asa.video_prompt_modules import MediaType

DEFAULTS = [
    ('watercolor', 'animation_2d', '수채화 동화풍',
     '따뜻한 파스텔 색감, 종이 질감, 번지는 수채화와 부드러운 연필선.'),
    ('2d', 'animation_2d', '2D 애니메이션',
     '선명한 윤곽선, 단순한 면 채색, 부드러운 색감의 2D 애니메이션.'),
    ('3d', 'animation_3d', '3D 애니메이션',
     '둥근 입체 형태, 부드러운 재질, 은은한 조명의 3D 애니메이션.'),
    ('realistic', 'live_action', '실사 영화풍',
     '사실적인 피부와 재질, 자연스러운 조명, 영화 촬영 같은 실사 표현.'),
    ('comic', 'animation_2d', '웹툰·만화풍',
     '깔끔한 펜선, 선명한 색 대비, 절제된 셀 음영의 웹툰·만화 표현.'),
    ('clay', 'animation_3d', '클레이·스톱모션풍',
     '손으로 빚은 점토 질감, 미니어처 세트와 따뜻한 조명의 스톱모션 표현.'),
]
BUILTIN_IMAGES = {f'/art-style-examples/{row[0]}.png' for row in DEFAULTS}


class Preset(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    media_type: MediaType
    label: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=2000)
    image: str | None = Field(default=None, max_length=2000000)
    enabled: bool = True

    @field_validator('id')
    @classmethod
    def reserved(cls, value: str) -> str:
        if value in {'custom', 'existing'}:
            raise ValueError('reserved_style_id')
        return value

    @field_validator('image')
    @classmethod
    def validate_image(cls, value: str | None) -> str | None:
        if value is None or value in BUILTIN_IMAGES:
            return value
        prefix, separator, data = value.partition(',')
        if not separator or prefix not in {
            'data:image/png;base64', 'data:image/jpeg;base64', 'data:image/webp;base64'
        }:
            raise ValueError('PNG·JPEG·WebP 예시 이미지를 선택하세요.')
        try:
            raw = decode_image(data)
            with Image.open(BytesIO(raw)) as image:
                image.thumbnail((640, 640))
                output = BytesIO()
                image.save(output, format='PNG')
            return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()
        except RegistryError as exc:
            raise ValueError('예시 이미지가 올바르지 않습니다.') from exc


class Catalog(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0, strict=True)
    items: list[Preset] = Field(max_length=30)

    @model_validator(mode='after')
    def unique_and_bounded(self) -> 'Catalog':
        if len({p.id for p in self.items}) != len(self.items):
            raise ValueError('화풍 항목 ID가 중복되었습니다.')
        if sum(len(p.image or '') for p in self.items) > 8000000:
            raise ValueError('예시 이미지 전체 크기를 줄여 주세요. 최대 8MB입니다.')
        return self


def read(repo: RegistryRepository) -> dict[str, Any]:
    with repo._connect() as conn:
        row = conn.execute('SELECT revision,items FROM art_style_catalog WHERE workspace_id=%s',
                           (repo.workspace_id,)).fetchone()
        if row:
            return dict(row)
    return {'revision': 0, 'items': [dict(id=key, media_type=media, label=label,
        description=prompt, image=f'/art-style-examples/{key}.png', enabled=True)
        for key, media, label, prompt in DEFAULTS]}


def save(repo: RegistryRepository, body: Catalog) -> dict[str, Any]:
    with repo._connect() as conn:
        conn.execute('INSERT INTO art_style_catalog(workspace_id) VALUES(%s) '
                     'ON CONFLICT DO NOTHING', (repo.workspace_id,))
        row = conn.execute('SELECT revision FROM art_style_catalog WHERE workspace_id=%s '
                           'FOR UPDATE', (repo.workspace_id,)).fetchone()
        if row is None or row['revision'] != body.revision:
            raise RegistryError(409, 'art_catalog_conflict')
        items = [p.model_dump() for p in body.items]
        conn.execute('UPDATE art_style_catalog SET revision=revision+1,items=%s '
                     'WHERE workspace_id=%s', (Jsonb(items), repo.workspace_id))
    return {'revision': body.revision + 1, 'items': items}


def catalog_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix='/api/v1/art-style-catalog')

    @router.get('')
    def get(principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        return read(RegistryRepository(settings.database_url, principal.workspace_id))

    @router.put('')
    def put(body: Catalog, principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        if not {'owner', 'admin'}.intersection(principal.roles):
            raise HTTPException(403, 'admin_required')
        return save(RegistryRepository(settings.database_url, principal.workspace_id), body)

    return router
