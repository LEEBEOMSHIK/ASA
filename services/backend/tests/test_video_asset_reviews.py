import pytest
from pydantic import ValidationError

from asa.registry.video_asset_reviews import ReviewResult, safe_result


def test_audio_and_lipsync_never_report_observed_success():
    result = ReviewResult(summary='검수', checks=[
        dict(category='audio', verdict='pass', expected='대사', observed='들림',
             timestamp_seconds=1),
        dict(category='lipsync', verdict='issue', expected='입모양', observed='어긋남',
             timestamp_seconds=1),
        dict(category='visual', verdict='issue', expected='인물', observed='다름',
             timestamp_seconds=2),
    ], limitations=[])
    safe = safe_result(result, duration=3, reference_available=False)
    assert safe['checks'][0]['verdict'] == 'unverified'
    assert safe['checks'][1]['verdict'] == 'unverified'
    assert safe['checks'][2]['verdict'] == 'issue'
    assert any(c['category'] == 'continuity' and c['verdict'] == 'unverified'
               for c in safe['checks'])
    assert safe['limitations']


def test_review_schema_rejects_unknown_fields_and_out_of_bounds_time():
    with pytest.raises(ValidationError):
        ReviewResult(summary='ok', checks=[], limitations=[], approved=True)
    with pytest.raises(ValueError):
        safe_result(ReviewResult(summary='ok', checks=[dict(category='visual', verdict='pass',
            expected='x', observed='x', timestamp_seconds=30)], limitations=[]),
            duration=3, reference_available=True)


def test_model_sees_only_frozen_input_and_bounded_frames(monkeypatch):
    from asa.config import Settings
    from asa.registry import video_asset_reviews as reviews
    messages = []
    options = []
    class FakeModel:
        def with_structured_output(self, schema):
            assert schema is ReviewResult
            return self
        def invoke(self, data, **kwargs):
            messages.extend(data)
            return {
                'summary': '정지 표본 검수', 'checks': [], 'limitations': [],
                'speech_suggestions': [
                    dict(text='어디 있었어?', start_sample=0, end_sample=1,
                         observed='입을 열고 몸을 앞으로 기울인다', delivery='가볍게 놀라 묻는다',
                         basis='mouth'),
                    dict(text='어디 있었어?', start_sample=0, end_sample=9,
                         observed='범위 초과', delivery='크게', basis='mouth'),
                    dict(text='처음 본 사람이었다.', start_sample=0, end_sample=1,
                         observed='입 모양', delivery='차분하게', basis='mouth'),
                    dict(text='어디 있었어!', start_sample=0, end_sample=1,
                         observed='텍스트 불일치', delivery='급하게', basis='event'),
                ],
            }
    def model(*args, **kwargs):
        options.append(kwargs)
        return FakeModel()
    def frames(path, directory, ffmpeg, *, max_bytes):
        assert path.read_bytes() == b'video'
        assert max_bytes == 64 * 1024 * 1024
        return {'duration_seconds': 3, 'sampling_interval_seconds': 1,
                'frames': [{'seconds': 0.5, 'jpeg': 'fake-frame'},
                           {'seconds': 1.5, 'jpeg': 'other-frame'}]}
    monkeypatch.setattr(reviews, 'init_chat_model', model)
    monkeypatch.setattr(reviews, 'extract_frames', frames)
    result = reviews.review_video(Settings(_env_file=None, ffmpeg_path='mock-ffmpeg'), {
        'reference_image': b'reference', 'source_video': None,
        'generation_input': {'prompt': 'frozen prompt', 'voice_direction_prompt': 'frozen voice'},
        'speech_candidates': [
            {'text': '어디 있었어?', 'role': 'character'},
            {'text': '처음 본 사람이었다.', 'role': 'narrator'},
        ],
        'definition': {'instructions': 'review only', 'provider': 'openai', 'model': 'mock'},
    }, b'video')
    assert options[0]['max_retries'] == 0
    assert 'frozen prompt' in str(messages[-1].content)
    assert 'frozen voice' in str(messages[-1].content)
    assert 'fake-frame' in str(messages[-1].content)
    assert '표본 0' in str(messages[-1].content)
    assert all(c['verdict'] == 'unverified' for c in result['checks'])
    assert result['speech_suggestions'] == [
        dict(text='어디 있었어?', start_seconds=0.5, end_seconds=1.5,
             observed='입을 열고 몸을 앞으로 기울인다',
             delivery='가볍게 놀라 묻는다', basis='mouth'),
    ]


def test_speech_candidates_are_from_the_exact_saved_clip_and_role():
    from asa.registry.video_asset_reviews import speech_candidates

    class Connection:
        def execute(self, query, params):
            assert 'WHERE workspace_id=%s AND request_id=%s AND version=%s' in query
            assert params == ('workspace', 'request', 2)
            return self

        def fetchone(self):
            return {'answer': {
                'clips': [{'clip_id': 'c1', 'source_start_seconds': 2, 'source_end_seconds': 5}],
                'audio_plan': {'speakers': [{'id': 'narrator', 'name': '해설', 'role': 'narrator'}],
                               'cues': [
                                   dict(id='c1', speaker_id='narrator', text='먼 곳에서 시작했다.',
                                        start=0, end=2),
                                   dict(id='c2', speaker_id='narrator', text='문이 열렸다.',
                                        start=2, end=4),
                                   dict(id='c3', speaker_id='narrator', text='그 다음 이야기였다.',
                                        start=4, end=6),
                               ]},
            }}

    assert speech_candidates(Connection(), 'workspace', {
        'request_id': 'request', 'answer_version': 2, 'clip_id': 'c1',
        'generation_input': {'audio': False, 'prompt': '원문처럼 보이는 가짜 대사'},
    }) == [{
        'text': '문이 열렸다.', 'speaker_name': '해설', 'role': 'narrator',
        'planned_start_seconds': 0.0, 'planned_end_seconds': 2.0,
    }]
