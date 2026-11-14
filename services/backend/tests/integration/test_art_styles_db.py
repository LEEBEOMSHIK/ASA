import json
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_registry_db import client as client_fixture
from test_registry_db import db as db_fixture
from test_registry_db import script_work

from asa.config import Settings
from asa.registry import art_styles
from asa.registry.characters import Character, CharacterRepository, ImageRequest
from asa.registry.schemas import RegistryError

client = client_fixture
db = db_fixture


def test_shared_style_is_scoped_versioned_and_frozen(client, db, monkeypatch):
    headers, work, _ = script_work(client)
    root = UUID(work["id"])
    linked, other = uuid4(), uuid4()
    projects = [uuid4() for _ in range(3)]
    char = Character(
        id="child",
        name="아이",
        facts="",
        proposed="2D",
        appearance="red coat",
        scene_ids="1",
        image_prompt="2D pencil",
    )
    repo = CharacterRepository(*db)
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        for request, source in [(linked, root), (other, None)]:
            conn.execute(
                "INSERT INTO customer_requests(workspace_id,id,agent_id,version,input,"
                "source_id) SELECT workspace_id,%s,agent_id,version,input,%s "
                "FROM customer_requests WHERE workspace_id=%s AND id=%s",
                (request, source, db[1], root),
            )
        for project, request in zip(projects, [root, linked, other], strict=True):
            conn.execute(
                "INSERT INTO character_projects(workspace_id,id,request_id,name,characters) "
                "VALUES(%s,%s,%s,'test',%s)",
                (db[1], project, request, Jsonb([char.model_dump()])),
            )
    paths = [f"/api/v1/characters/projects/{p}/art-style" for p in projects]
    first = client.get(paths[0]).json()
    assert client.get(paths[1]).json() == first
    assert client.get(paths[2]).json()["work_id"] != first["work_id"]
    body = {**first, "prompt": "watercolor", "media_type": "animation_2d"}
    assert client.put(paths[0], json=body).status_code == 403
    saved = client.put(paths[0], json=body, headers=headers)
    assert saved.status_code == 200, saved.text
    assert client.get(paths[1]).json()["prompt"] == "watercolor"
    assert client.put(paths[1], json=body, headers=headers).status_code == 409
    assert client.get(paths[2]).json()["prompt"] == ""
    assert client.get(f"/api/v1/characters/projects/{uuid4()}/art-style").status_code == 404
    settings = Settings(
        _env_file=None,
        database_url=db[0],
        workspace_id=db[1],
        image_ai_enabled=True,
        ai_api_key="test-only",
    )
    request = ImageRequest(id=uuid4(), character=char, model="gpt-image-2.5-sunburst")
    job = repo.enqueue(projects[0], request, settings)
    assert job["art_style"]["prompt"] == "watercolor"
    assert job["art_style"]["media_type"] == "animation_2d"
    assert job["character"] == char.model_dump()
    # A scene project in the same production shares the style, not its own copy.
    from asa.registry import scene_images

    with psycopg.connect(db[0]) as conn:
        conn.execute("UPDATE character_projects SET kind='scene' WHERE id=%s", (projects[1],))
    monkeypatch.setattr(scene_images, "snapshot", lambda *a, **kw: {"scene_id": "1"})
    scene_job = repo.enqueue(
        projects[1],
        ImageRequest(id=uuid4(), character=char, model="gpt-image-2.5-sunburst"),
        settings,
    )
    assert scene_job["art_style"] == job["art_style"]
    assert scene_job["scene_context"] == {"scene_id": "1"}
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        conn.execute("UPDATE character_image_jobs SET status='succeeded',image=%s WHERE id=%s",
                     (b'image', job['id']))
        selection = {'format': 'asa_scene_selection_v1',
                     'scenes': [{'image_id': str(job['id'])}]}
        assert art_styles.resolve(conn, db[1], selection) == job['art_style']
        with pytest.raises(RegistryError, match='work_visual_source_invalid'):
            art_styles.resolve(conn, uuid4(), selection)
        art_styles.check_plan_style(job['art_style'], job['art_style'])
        with pytest.raises(RegistryError, match='work_visual_plan_changed'):
            art_styles.check_plan_style(job['art_style'],
                                        {**job['art_style'], 'media_type': 'live_action'})
    assert (
        client.put(
            paths[1], json={**saved.json(), "prompt": "oil paint"}, headers=headers
        ).status_code
        == 200
    )
    assert repo.enqueue(projects[0], request, settings)["art_style"]["prompt"] == "watercolor"
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        assert art_styles.load(conn, uuid4(), root)["work_id"] is None
        with pytest.raises(RegistryError, match="art_style_work_changed"):
            art_styles.save(conn, db[1], other, art_styles.StyleEdit.model_validate(body))


def test_common_style_overrides_only_style_and_preserves_legacy_prompt():
    from asa.registry.scene_images import prompt as scene_prompt
    from asa.tools.character_images import image_prompt

    char = {"name": "아이", "appearance": "red coat", "image_prompt": "2D pencil"}
    for original in [
        image_prompt(char, "photorealistic"),
        scene_prompt({}, char, "photorealistic"),
    ]:
        assert art_styles.apply_style(original, None) == original
        assert art_styles.apply_style(original, {"prompt": ""}) == original
        result = art_styles.apply_style(original, {"prompt": "watercolor"})
        assert result.endswith(original)
        assert "HIGHEST priority" in result and "watercolor" in result
        assert "red coat" in result and "Ignore conflicting style" in result


def test_category_has_priority_over_conflicting_custom_style():
    result = art_styles.apply_style("legacy 3D description", {
        "media_type": "animation_2d", "prompt": "photorealistic texture"})
    assert "animation_2d" in result
    assert "takes precedence" in result
    assert art_styles.apply_style("old", {"media_type": "live_action", "prompt": ""}) != "old"


@pytest.mark.parametrize('media', ['animation_2d', 'animation_3d', 'live_action'])
def test_work_category_selects_same_specialist_even_with_legacy_manual_config(media):
    from asa.video_prompt_modules import build_prompt_bundle

    definition = {'instructions': 'COMMON', 'input_schema': {'properties': {
        'model': {'x-video-model': True}}}, 'video_prompt_modules': {
        'enabled': True, 'editor_managed': True, 'mode': 'manual',
        'profile_id': 'live_action', 'style_instructions': {
            'animation_2d': '2D_ONLY', 'animation_3d': '3D_ONLY', 'live_action': 'LIVE_ONLY'}}}
    inputs = art_styles.video_inputs(definition, {},
                                     {'media_type': media})
    assert inputs['video_style'] == media
    bundle = build_prompt_bundle(definition, inputs, work_media_type=media)
    assert bundle['media_type'] == media
    assert bundle['style_profile_ids'] == ['common', media]
    assert bundle['selection_source'] == 'work'


@pytest.mark.parametrize('selected', ['auto', 'animation_2d', 'animation_3d', 'live_action'])
def test_video_override_is_local_and_survives_common_style_changes(selected):
    from asa.video_prompt_modules import build_prompt_bundle

    common = {'work_id': 'work', 'media_type': 'live_action', 'prompt': 'photo', 'revision': 1}
    definition = {'instructions': 'COMMON', 'input_schema': {'properties': {
        'model': {'x-video-model': True}}}}
    inputs = {'video_style': selected}
    assert art_styles.video_inputs(definition, inputs, common) == inputs
    frozen = art_styles.video_style(inputs, common)
    assert frozen['scope'] == 'video'
    assert common['media_type'] == 'live_action' and common['prompt'] == 'photo'
    assert frozen['prompt'] == ''
    bundle = build_prompt_bundle(definition, inputs,
                                 work_media_type=frozen['media_type'],
                                 work_style_auto=selected == 'auto')
    assert bundle['media_type'] == (None if selected == 'auto' else selected)
    prompt = art_styles.apply_style('original scene', frozen)
    assert ('AUTOMATIC VISUAL STYLE' if selected == 'auto' else selected) in prompt
    art_styles.check_plan_style(frozen, {**common, 'media_type': 'animation_3d'})
    with pytest.raises(RegistryError):
        art_styles.check_plan_style(frozen, {**common, 'work_id': 'other'})


@pytest.mark.parametrize("automatic", [False, True])
@pytest.mark.parametrize('override', [None, 'animation_2d', 'auto'])
def test_queue_freezes_work_category_and_does_not_rewrite_original(
    client, db, monkeypatch, automatic, override
):
    from asa.registry.script_stage import GenerateScript, ScriptRepository

    _, work, _ = script_work(client)
    rid = UUID(work['id'])
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        style = art_styles.load(conn, db[1], rid)
        saved = art_styles.save(conn, db[1], rid, art_styles.StyleEdit.model_validate(
            {**style, 'media_type': None if automatic else 'animation_3d',
             'prompt': '' if automatic else 'clay texture'}))
        row = conn.execute('SELECT definition FROM registry_versions WHERE workspace_id=%s',
                           (db[1],)).fetchone()
        definition = row['definition']
        definition['input_schema']['properties']['video_style'] = {'type': 'string'}
        definition['input_schema']['properties']['model'] = {
            'type': 'string', 'x-video-model': True}
        definition['video_prompt_modules'] = {
            'enabled': True, 'editor_managed': True, 'mode': 'manual',
            'profile_id': 'live_action', 'style_instructions': {'animation_3d': '3D ONLY'}}
    monkeypatch.setattr(ScriptRepository, '_latest_request',
                        lambda self, conn, request: {**request, 'definition': definition})
    repo = ScriptRepository(*db)
    command = GenerateScript(id=uuid4(), expected_revision=0, base_version=0,
                             instruction='generate',
                             **({'request_input': {'topic': '고양이', 'video_style': override,
                                                  'video_art_style': 'soft watercolor'}}
                                if override else {}))
    repo.queue(str(rid), command)
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        frozen = json.loads(conn.execute('SELECT prompt FROM script_attempts WHERE id=%s',
                                         (command.id,)).fetchone()['prompt'])
        expected = art_styles.generation_style(saved)
        if override:
            expected = art_styles.video_style({'video_style': override,
                                               'video_art_style': 'soft watercolor'}, expected)
        assert frozen['work_visual_style'] == expected
        assert frozen['original_request']['video_style'] == (
            override or ('auto' if automatic else 'animation_3d'))
        assert frozen['video_prompt_bundle']['media_type'] == (
            expected['media_type'])
        if expected.get('mode') == 'auto':
            assert frozen['video_prompt_bundle']['selection_source'] == 'work_auto'
            assert 'AUTOMATIC VISUAL STYLE' in frozen['video_prompt_bundle']['instructions']
        assert conn.execute('SELECT input FROM customer_requests WHERE id=%s',
                            (rid,)).fetchone()['input'] == {'topic': '고양이'}
        art_styles.save(conn, db[1], rid, art_styles.StyleEdit.model_validate(
            {**saved, 'media_type': 'live_action'}))
    repo.queue(str(rid), command)
    with psycopg.connect(db[0], row_factory=dict_row) as conn:
        assert json.loads(conn.execute('SELECT prompt FROM script_attempts WHERE id=%s',
                                       (command.id,)).fetchone()['prompt']) == frozen
