"""Immutable, workspace-scoped uploaded character references."""
import base64
import binascii
from io import BytesIO
from typing import Any
from uuid import UUID, uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from asa.registry.schemas import RegistryError


class UploadReference(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    data: str | None = Field(default=None, max_length=7000000)
    existing_upload: UUID | None = None
    filename: str = Field(default='image', max_length=200)
    character_image: UUID | None = None
    name: str = Field(min_length=1, max_length=100)
    appearance: str = Field(min_length=1, max_length=3000)
    image_prompt: str = Field(default='', max_length=4000)

    @model_validator(mode='after')
    def source(self) -> 'UploadReference':
        if bool(self.data) == bool(self.existing_upload):
            raise ValueError('one_image_source_required')
        return self


def decode_image(value: str) -> bytes:
    try:
        if len(value) > 7000000:
            raise ValueError
        raw = base64.b64decode(value, validate=True)
        if len(raw) > 5 * 1024 * 1024:
            raise ValueError
        with Image.open(BytesIO(raw)) as image:
            if (image.format not in ('PNG', 'JPEG', 'WEBP') or
                    image.width * image.height > 16000000 or
                    getattr(image, 'n_frames', 1) != 1):
                raise ValueError
            image.load()
            normalized = ImageOps.exif_transpose(image).convert('RGBA')
            normalized.thumbnail((2048, 2048))
            # Fresh image strips EXIF, comments and other source metadata.
            clean = Image.frombytes('RGBA', normalized.size, normalized.tobytes())
            output = BytesIO()
            clean.save(output, format='PNG')
            return output.getvalue()
    except (ValueError, OSError, binascii.Error, UnidentifiedImageError,
            Image.DecompressionBombError) as exc:
        raise RegistryError(422, 'character_upload_invalid') from exc


def save_upload(repo: Any, body: UploadReference) -> dict[str, Any]:
    from asa.registry.character_library import selected_handoff

    image_id = uuid4()
    character: dict[str, Any] = {
        'id': 'upload_' + image_id.hex, 'facts': '', 'proposed': '', 'scene_ids': ''}
    if body.character_image:
        existing = selected_handoff(repo, [body.character_image])['characters'][0]
        character = {key: existing[key] for key in (
            'id', 'facts', 'proposed', 'scene_ids')}
    character.update(name=body.name, appearance=body.appearance,
                     image_prompt=body.image_prompt)
    image = decode_image(body.data) if body.data else None
    with repo._connect() as conn:
        if body.existing_upload:
            previous = conn.execute('SELECT image FROM character_reference_uploads '
                                    'WHERE workspace_id=%s AND id=%s',
                                    (repo.workspace_id, body.existing_upload)).fetchone()
            if not previous:
                raise RegistryError(404, 'character_selection_missing')
            image = bytes(previous['image'])
        conn.execute('INSERT INTO character_reference_uploads '
                     '(id,workspace_id,character,image,filename) VALUES (%s,%s,%s,%s,%s)',
                     (image_id, repo.workspace_id, Jsonb(character), image, body.filename))
    return selected_handoff(repo, [image_id])


def uploaded_character(row: dict[str, Any]) -> dict[str, Any]:
    return {**row['character'], 'image_id': str(row['id']), 'image_version': 1,
            'image_change': '사용자가 업로드하고 연결한 참고 이미지',
            'project_id': str(row['id']), 'source_request_id': '', 'source_version': 1}
