import base64
import struct
import zlib

import pytest
from pydantic import ValidationError

from asa.registry.branding import Branding


def png_logo(width: int = 2, height: int = 2) -> str:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))
    raw = b"\x89PNG\r\n\x1a\n"
    raw += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    raw += chunk(b"IDAT", zlib.compress((b"\x00" + b"\x80\x40\xff\xff" * width) * height))
    raw += chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def test_branding_validates_raster_and_name() -> None:
    logo = png_logo()
    value = Branding(revision=0, name="  나의 스튜디오  ", logo=logo)
    assert value.name == "나의 스튜디오"
    assert value.logo == logo
    assert Branding(revision=1, name="기본", logo=None).logo is None


@pytest.mark.parametrize("logo", [
    "data:image/svg+xml;base64,PHN2Zz4=", "https://example.com/logo.png",
    "data:image/png;base64,not-valid", png_logo(97, 1), png_logo()[:-8],
])
def test_branding_rejects_invalid_logo(logo: str) -> None:
    with pytest.raises(ValidationError):
        Branding(revision=0, name="스튜디오", logo=logo)


def test_branding_rejects_blank_name_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Branding(revision=0, name="  ")
    with pytest.raises(ValidationError):
        Branding.model_validate({"revision": 0, "name": "이름", "workspace_id": "other"})
