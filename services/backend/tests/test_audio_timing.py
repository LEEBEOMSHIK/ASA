import io
import wave

import pytest

from asa.audio_media import pcm_wav
from asa.audio_timing import assemble_preview, summarize


def test_timeline_union_gaps_and_missing():
    jobs = [dict(id='a', cue_id='a', purpose='timing', excluded_reason=None,
                 has_media=True, status='review', start=1, end=3, duration=1,
                 speaker_name='아이')]
    result = summarize(jobs, ['a'], 5, 5)
    assert result['duration'] == 5 and result['speech_seconds'] == 1
    assert result['gap_seconds'] == 4 and result['preview_ready']
    assert result['gaps'] == [{'start': 0, 'end': 1}, {'start': 2, 'end': 5}]
    assert not summarize(jobs, ['a', 'b'], 5, 3)['preview_ready']
    jobs.append({**jobs[0], 'id': 'b', 'cue_id': 'b', 'start': 1.5})
    result = summarize(jobs, ['a', 'b'], 5, 5)
    assert result['overlap_seconds'] == .5 and result['gap_seconds'] == 3.5
    assert not result['preview_ready']


def test_target_never_pads_measured_preview():
    job = dict(id='a', cue_id='a', purpose='timing', excluded_reason=None,
               has_media=True, status='review', start=0, end=26, duration=26)
    result = summarize([job], ['a'], 30, 29.5)
    assert result['duration'] == 29.5 and result['shortfall'] == .5
    assert result['gap_seconds'] == 3.5
    assert summarize([job], ['a', 'b'], 30, 29.5)['shortfall'] is None


def test_preview_preserves_leading_middle_and_trailing_silence():
    clip = pcm_wav(b'\x01\x00' * 24000)
    output = assemble_preview([(clip, 1), (clip, 3)], 5)
    with wave.open(io.BytesIO(output)) as wav:
        assert wav.getnframes() == 5 * 24000
        pcm = wav.readframes(wav.getnframes())
    assert pcm[:48000] == bytes(48000)
    assert pcm[48000:96000] == b'\x01\x00' * 24000
    assert pcm[96000:144000] == bytes(48000)
    assert pcm[-48000:] == bytes(48000)
    with pytest.raises(ValueError):
        assemble_preview([(clip, 4.5)], 5)
