"""Read-only timing summaries and gap-preserving local PCM previews."""
import io
import wave
from typing import Any

from asa.audio_media import pcm_wav


def summarize(jobs: list[dict[str, Any]], expected: list[str], target: float | None,
              planned_end: float) -> dict[str, Any]:
    chosen: dict[str, dict[str, Any]] = {}
    for job in jobs:
        if (job['purpose'] == 'timing' and not job['excluded_reason'] and job['has_media']
                and job['status'] in ('review', 'approved') and job['duration']):
            chosen.setdefault(job['cue_id'], job)
    clips = sorted(chosen.values(), key=lambda j: j['start'])
    measured_end = max((j['start'] + j['duration'] for j in clips), default=0)
    duration = max(planned_end, measured_end)
    cursor, occupied = 0.0, 0.0
    gaps = []
    for job in clips:
        start, end = job['start'], job['start'] + job['duration']
        if start > cursor:
            gaps.append({'start': cursor, 'end': start})
        occupied += max(0, end - max(cursor, start))
        cursor = max(cursor, end)
    if cursor < duration:
        gaps.append({'start': cursor, 'end': duration})
    speech = sum(j['duration'] for j in clips)
    missing = len(set(expected) - chosen.keys())
    overlap = max(0, speech - occupied)
    return dict(target=target, duration=duration, speech_seconds=round(speech, 3),
                queued=sum(j['status'] == 'queued' for j in jobs),
                running=sum(j['status'] == 'running' for j in jobs),
                gap_seconds=round(duration-occupied, 3), overlap_seconds=round(overlap, 3),
                missing=missing, excluded=sum(bool(j['excluded_reason']) for j in jobs),
                shortfall=round(max(0, target-duration), 3) if target and not missing else None,
                overrun=round(max(0, duration-target), 3) if target else 0,
                preview_ready=bool(clips) and not missing and overlap < .00001
                and 0 < duration <= 3600, gaps=gaps, clips=clips)


def assemble_preview(clips: list[tuple[bytes, float]], duration: float) -> bytes:
    if not 0 < duration <= 3600:
        raise ValueError('audio_timeline_invalid')
    pcm = bytearray(round(duration * 24000) * 2)
    previous_end = 0
    for media, start in sorted(clips, key=lambda c: c[1]):
        with wave.open(io.BytesIO(media)) as source:
            fmt = (source.getnchannels(), source.getsampwidth(), source.getframerate())
            if fmt != (1, 2, 24000):
                raise ValueError('audio_preview_format')
            frames = source.readframes(source.getnframes())
        offset = round(start * 24000) * 2
        if offset < previous_end or offset + len(frames) > len(pcm):
            raise ValueError('audio_timeline_invalid')
        pcm[offset:offset+len(frames)] = frames
        previous_end = offset + len(frames)
    return pcm_wav(bytes(pcm))
