import base64
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from asa.registry.schemas import RegistryError
from asa.registry.video_reference import VideoSource, canonical_url, decode_video


def test_template_and_real_frame_attachments(monkeypatch):
    from asa import video_analysis
    from asa.registry.schemas import AgentDraft
    from asa.registry.service import validate_definition
    draft = AgentDraft.model_validate_json((Path(__file__).resolve().parents[3] /
        'docs/agent-templates/video-style-analyst.json').read_text(encoding='utf-8'))
    assert validate_definition(draft, {}) == []
    prepared = {'source_label':'test.mp4','duration_seconds':2,'sampling_interval_seconds':1,
                'frames':[{'seconds':0.5,'jpeg':'YWJj'},{'seconds':1.5,'jpeg':'ZGVm'}]}
    monkeypatch.setattr(video_analysis, 'prepare', lambda *args: prepared)
    content = video_analysis.video_content(None, {'video':{'format':'asa_video_reference_v1',
                                             'source_id':str(uuid4())}}, None)
    assert len([c for c in content if c['type']=='image_url']) == 2
    assert '음성·음악을 분석하지 않았습니다' in content[0]['text']
    assert content[2]['image_url']['url'] == 'data:image/jpeg;base64,YWJj'


def test_source_read_is_workspace_scoped():
    from asa.registry.video_reference import read_source
    workspace, source = uuid4(), uuid4()
    class Connection:
        def execute(self, query, params):
            assert 'workspace_id=%s' in query
            assert params == (workspace, source)
            return SimpleNamespace(fetchone=lambda: None)
    repo = SimpleNamespace(workspace_id=workspace, _connect=lambda:nullcontext(Connection()))
    with pytest.raises(RegistryError, match='video_source_missing'):
        read_source(repo,str(source))


def test_multiple_or_forged_sources_rejected():
    from asa.video_analysis import video_sources
    with pytest.raises(RegistryError, match='video_source_limit'):
        video_sources([{'format':'asa_video_reference_v1','source_id':str(uuid4())}
                       for _ in range(5)])
    with pytest.raises(RegistryError, match='video_source_missing'):
        video_sources({'format':'asa_video_reference_v1','source_id':str(uuid4()),'url':'x'})


def test_public_links_are_canonical_and_restricted():
    assert canonical_url('https://youtu.be/abcdefghijk?t=30') == 'https://www.youtube.com/watch?v=abcdefghijk'
    assert canonical_url('https://www.instagram.com/reel/Abc_12-/') == 'https://www.instagram.com/reel/Abc_12-/'
    for url in ['http://youtube.com/watch?v=abcdefghijk', 'https://youtube.com.evil.test/a',
                'https://127.0.0.1/a', 'https://user@youtube.com/watch?v=abcdefghijk',
                'https://youtube.com/playlist?list=anything', 'file:///etc/passwd']:
        with pytest.raises(RegistryError):
            canonical_url(url)


def test_video_source_requires_exactly_one_source():
    with pytest.raises(ValueError):
        VideoSource()
    with pytest.raises(ValueError):
        VideoSource(url='https://youtu.be/abcdefghijk', data='YQ==')


def test_upload_rejects_non_video_data():
    for raw in [b'<html>hi</html>', b'#EXTM3U\nhttp://localhost/secret', b'']:
        with pytest.raises(RegistryError):
            decode_video(base64.b64encode(raw).decode())


def test_four_sources_are_ordered_and_frame_budget_is_bounded(monkeypatch):
    from asa import video_analysis
    sources = [{'format': 'asa_video_reference_v1', 'source_id': str(uuid4()),
                'note': f'reference {i}'} for i in range(4)]
    assert video_analysis.video_sources(sources) == [s['source_id'] for s in sources]
    monkeypatch.setattr(video_analysis, 'prepare', lambda *args: {
        'source_label': 'video', 'duration_seconds': 24,
        'frames': [{'seconds': i, 'jpeg': 'YWJj'} for i in range(24)]})
    content = video_analysis.video_content(None, sources, None)
    assert sum(c['type'] == 'image_url' for c in content) == 48
    assert any('참고 영상 4' in c.get('text', '') for c in content)


def test_partial_failure_is_reported_and_all_failure_blocks_ai(monkeypatch):
    from asa import video_analysis
    sources = [{'format': 'asa_video_reference_v1', 'source_id': str(uuid4())}
               for _ in range(2)]
    def prepare(repo, source, settings):
        if source == sources[0]['source_id']:
            raise RegistryError(422, 'video_link_unavailable')
        return {'source_label': 'ok.mp4', 'duration_seconds': 1,
                'frames': [{'seconds': 0.5, 'jpeg': 'YWJj'}]}
    monkeypatch.setattr(video_analysis, 'prepare', prepare)
    content = video_analysis.video_content(None, sources, None)
    assert '참고 영상 1: 분석 실패' in content[0]['text']
    assert sum(c['type'] == 'image_url' for c in content) == 1
    with pytest.raises(RegistryError, match='video_all_unavailable'):
        video_analysis.video_content(None, sources[:1], None)


def test_multi_video_schema_rejects_empty_and_unfinished_sources():
    import json

    from asa.registry.history import valid_input
    schema = json.loads((Path(__file__).resolve().parents[3] /
        'docs/agent-templates/video-style-analyst.json').read_text(encoding='utf-8'))['input_schema']
    assert not valid_input({'video': []}, schema)
    assert not valid_input({'video': [{}]}, schema)
    assert not valid_input({'video': [{'format': 'asa_video_upload_pending'}]}, schema)
    assert valid_input({'video': [{'format': 'asa_video_reference_v1',
        'source_id': str(uuid4()), 'note': '색감 참고'} for _ in range(4)]}, schema)
