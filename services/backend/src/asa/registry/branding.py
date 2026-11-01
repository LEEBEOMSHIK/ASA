"""Workspace-scoped navigation branding; only administrators may edit."""
import base64
import binascii
import struct
import zlib
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry.repository import RegistryRepository
from asa.registry.schemas import RegistryError


class Branding(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    revision: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=40)
    logo: str | None = Field(default=None, max_length=50000)

    @field_validator("logo")
    @classmethod
    def validate_logo(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            prefix = "data:image/png;base64,"
            if not value.startswith(prefix):
                raise ValueError
            raw = base64.b64decode(value[len(prefix):], validate=True)
            if raw[:8] != b"\x89PNG\r\n\x1a\n":
                raise ValueError
            offset, pixels, width, height, channels = 8, b"", 0, 0, 0
            ended = False
            while offset < len(raw):
                size = struct.unpack_from(">I", raw, offset)[0]
                kind = raw[offset + 4:offset + 8]
                data = raw[offset + 8:offset + 8 + size]
                crc = struct.unpack_from(">I", raw, offset + 8 + size)[0]
                if zlib.crc32(kind + data) != crc:
                    raise ValueError
                if offset == 8:
                    if kind != b"IHDR" or size != 13:
                        raise ValueError
                    width, height, depth, color, compression, filtering, interlace = struct.unpack(
                        ">IIBBBBB", data)
                    if (not 1 <= width <= 96 or not 1 <= height <= 96 or depth != 8
                            or color not in (2, 6) or compression or filtering or interlace):
                        raise ValueError
                    channels = 3 if color == 2 else 4
                elif kind == b"IDAT":
                    pixels += data
                elif kind == b"IEND":
                    if size or offset + 12 != len(raw):
                        raise ValueError
                    ended = True
                elif kind not in (b"sRGB", b"gAMA", b"cHRM", b"pHYs"):
                    raise ValueError
                offset += 12 + size
            decoder = zlib.decompressobj()
            expected = height * (1 + width * channels)
            decoded = decoder.decompress(pixels, expected + 1)
            if not ended or len(decoded) != expected or not decoder.eof or decoder.unused_data:
                raise ValueError
        except (ValueError, binascii.Error, struct.error, zlib.error) as exc:
            raise ValueError("로고 이미지가 올바르지 않습니다. 파일을 다시 선택하세요.") from exc
        return value


def read(repo: RegistryRepository) -> dict[str, Any]:
    with repo._connect() as conn:
        row = conn.execute(
            "SELECT revision,name,logo FROM workspace_branding WHERE workspace_id=%s",
            (repo.workspace_id,),
        ).fetchone()
        return dict(row) if row else Branding(revision=0, name="AI Shorts Studio").model_dump()


def save(repo: RegistryRepository, body: Branding) -> dict[str, Any]:
    with repo._connect() as conn:
        conn.execute("INSERT INTO workspace_branding(workspace_id) VALUES (%s) "
                     "ON CONFLICT DO NOTHING", (repo.workspace_id,))
        row = conn.execute("SELECT revision FROM workspace_branding "
                           "WHERE workspace_id=%s FOR UPDATE", (repo.workspace_id,)).fetchone()
        if row is None or row["revision"] != body.revision:
            raise RegistryError(409, "branding_conflict")
        conn.execute("UPDATE workspace_branding SET revision=revision+1,name=%s,logo=%s "
                     "WHERE workspace_id=%s", (body.name, body.logo, repo.workspace_id))
        return {**body.model_dump(), "revision": body.revision + 1}


def branding_router(settings: Settings, sessions: OwnerSessions) -> APIRouter:
    router = APIRouter(prefix="/api/v1/branding")

    @router.get("")
    def get(principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        return read(RegistryRepository(settings.database_url, principal.workspace_id))

    @router.put("")
    def put(body: Branding, principal: Principal = Depends(sessions.principal)) -> dict[str, Any]:
        if not {"owner", "admin"}.intersection(principal.roles):
            raise HTTPException(403, "admin_required")
        return save(RegistryRepository(settings.database_url, principal.workspace_id), body)

    return router
