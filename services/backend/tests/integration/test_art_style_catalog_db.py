import base64
from io import BytesIO
from uuid import UUID, uuid4

import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from psycopg.rows import dict_row
from test_registry_db import client as client_fixture
from test_registry_db import db as db_fixture
from test_registry_db import script_work

from asa.auth.session import OwnerSessions, Principal
from asa.config import Settings
from asa.registry import art_styles
from asa.registry.art_style_catalog import catalog_router, read
from asa.registry.repository import RegistryRepository

client = client_fixture
db = db_fixture
PATH = '/api/v1/art-style-catalog'


def test_shared_catalog_preserves_existing_work_and_validates_images(client, db):
    assert client.get(PATH).status_code == 401
    headers, work, _ = script_work(client)
    initial = client.get(PATH).json()
    assert len(initial['items']) == 6 and initial['revision'] == 0
    first = initial['items'][0]
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        prior = art_styles.load(conn, db[1], UUID(work['id']))
        saved_work = art_styles.save(conn, db[1], UUID(work['id']),
            art_styles.StyleEdit.model_validate({**prior, 'prompt': first['description'],
                                                 'media_type': first['media_type']}))
    output = BytesIO()
    Image.new('RGB', (900, 600), 'red').save(output, format='PNG')
    first.update(description='새 수채화 지침',
                 image='data:image/png;base64,' + base64.b64encode(output.getvalue()).decode())
    assert client.put(PATH, json=initial).status_code == 403
    result = client.put(PATH, json=initial, headers=headers)
    assert result.status_code == 200, result.text
    assert client.put(PATH, json=initial, headers=headers).status_code == 409
    stored = client.get(PATH).json()
    image = stored['items'][0]['image']
    with Image.open(BytesIO(base64.b64decode(image.split(',')[1]))) as decoded:
        assert decoded.size == (640, 427)
        assert not decoded.info
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        assert art_styles.load(conn, db[1], UUID(work['id'])) == saved_work
    # Another workspace has its own default catalog, never this edited content.
    assert read(RegistryRepository(db[0], uuid4()))['revision'] == 0
    for invalid in ['https://outside.invalid/image.png', 'data:image/svg+xml;base64,PHN2Zz4=',
                    'data:image/png;base64,aW52YWxpZA==']:
        stored['items'][0]['image'] = invalid
        assert client.put(PATH, json=stored, headers=headers).status_code == 422
    stored['items'][0]['image'] = None
    stored['items'][1]['id'] = stored['items'][0]['id']
    assert client.put(PATH, json=stored, headers=headers).status_code == 422


def test_reader_cannot_edit_shared_catalog(db):
    settings = Settings(_env_file=None, database_url=db[0], workspace_id=db[1])
    app = FastAPI()
    sessions = OwnerSessions(settings)
    app.include_router(catalog_router(settings, sessions))
    # Exercise the real route's role check with a signed-in non-administrator principal.
    app.dependency_overrides[sessions.principal] = lambda: Principal('reader', db[1], ('user',))
    with TestClient(app) as c:
        result = c.get(PATH)
        assert result.status_code == 200
        assert c.put(PATH, json=result.json()).status_code == 403
