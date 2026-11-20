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
            return ReviewResult(summary='정지 표본 검수', checks=[], limitations=[])
    def model(*args, **kwargs):
        options.append(kwargs)
        return FakeModel()
    def frames(path, directory, ffmpeg, *, max_bytes):
        assert path.read_bytes() == b'video'
        assert max_bytes == 64 * 1024 * 1024
        return {'duration_seconds': 3, 'sampling_interval_seconds': 1,
                'frames': [{'seconds': 0.5, 'jpeg': 'fake-frame'}]}
    monkeypatch.setattr(reviews, 'init_chat_model', model)
    monkeypatch.setattr(reviews, 'extract_frames', frames)
    result = reviews.review_video(Settings(_env_file=None, ffmpeg_path='mock-ffmpeg'), {
        'reference_image': b'reference', 'source_video': None,
        'generation_input': {'prompt': 'frozen prompt', 'voice_direction_prompt': 'frozen voice'},
        'definition': {'instructions': 'review only', 'provider': 'openai', 'model': 'mock'},
    }, b'video')
    assert options[0]['max_retries'] == 0
    assert 'frozen prompt' in str(messages[-1].content)
    assert 'frozen voice' in str(messages[-1].content)
    assert 'fake-frame' in str(messages[-1].content)
    assert all(c['verdict'] == 'unverified' for c in result['checks'])
