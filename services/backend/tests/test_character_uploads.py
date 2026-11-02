import base64
from io import BytesIO

import pytest
from PIL import Image
from pydantic import ValidationError

from asa.registry.character_uploads import UploadReference, decode_image
from asa.registry.schemas import RegistryError


def test_reject_non_image_and_oversize():
    for value in ['not-base64', base64.b64encode(b'<svg/>').decode(), 'A' * 7000001]:
        with pytest.raises(RegistryError):
            decode_image(value)


@pytest.mark.parametrize('kind', ['PNG', 'JPEG', 'WEBP'])
def test_decode_and_normalize(kind):
    source = BytesIO()
    Image.new('RGB', (2400, 1200), 'blue').save(source, format=kind)
    result = decode_image(base64.b64encode(source.getvalue()).decode())
    with Image.open(BytesIO(result)) as image:
        assert image.format == 'PNG'
        assert image.size == (2048, 1024)
        assert not image.getexif()


def test_requires_character_and_exactly_one_source():
    with pytest.raises(ValidationError):
        UploadReference(name=' ', appearance='blue', data='a')
    with pytest.raises(ValidationError):
        UploadReference(name='하나', appearance='blue')
