"""Reusable neutral voice previews. CLI generation is explicit and never retried automatically."""
import argparse
import array
import io
import json
import math
import statistics
import wave
from pathlib import Path
from typing import Any

from asa.audio_contracts import AudioSettings
from asa.audio_provider import synthesize, transcript_matches
from asa.config import Settings
from asa.registry.audio_service import SAMPLE_TEXT, sample_spec, speech_key

DELIVERY = '자연스러운 한국어로 편안하게 읽으세요. 감정이나 캐릭터 연기를 과장하지 마세요.'


def preview_spec(settings: Settings, model_key: str, voice: str) -> dict[str, Any]:
    data = AudioSettings.model_validate({'speakers': [{
        'id': 'preview', 'name': '기본 음색', 'role': 'narrator',
        'voice': {'model_key': model_key, 'voice': voice, 'language': '한국어',
                  'speed': 1, 'instructions': DELIVERY}}]})
    return sample_spec(settings, data, 'preview')


def preview_paths(settings: Settings, model_key: str, voice: str) -> tuple[Path, Path]:
    key = speech_key(preview_spec(settings, model_key, voice))
    root = Path(settings.audio_preview_dir) / str(settings.workspace_id)
    return root / (key + '.json'), root / (key + '.wav')


def describe_audio(media: bytes) -> dict[str, Any]:
    with wave.open(io.BytesIO(media)) as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 24000):
            raise ValueError('preview_format')
        duration = source.getnframes() / 24000
        if not 0 < duration <= 30:
            raise ValueError('preview_duration')
        samples = array.array('h', source.readframes(source.getnframes()))
    # Downsample only for a rough descriptive pitch estimate, never modify playback.
    values = list(samples[::6])
    pitches = []
    for start in range(0, len(values)-240, 120):
        frame = values[start:start+240]
        mean = sum(frame)/len(frame)
        signal = [v-mean for v in frame]
        energy = sum(v*v for v in signal)
        if energy/240 < 100000:
            continue
        correlations = []
        for lag in range(10, 51):
            a, b = signal[:-lag], signal[lag:]
            scale = math.sqrt(sum(v*v for v in a)*sum(v*v for v in b))
            correlations.append(sum(x*y for x, y in zip(a, b))/scale if scale else 0)
        peaks = [i for i in range(1, len(correlations)-1)
                 if correlations[i] > .65
                 and correlations[i] > correlations[i-1]
                 and correlations[i] >= correlations[i+1]]
        if peaks:
            best = max(peaks, key=lambda i: correlations[i])
            pitches.append(4000/(best+10))
    pitch = round(statistics.median(pitches)) if len(pitches) >= 5 else None
    tone = ('낮은 음역 · 묵직한 느낌' if pitch < 145 else
            '중간 음역 · 균형 잡힌 높이' if pitch < 205 else
            '높은 음역 · 가벼운 느낌') if pitch else '음역 특징은 직접 들어 확인해 주세요'
    return {'duration': round(duration, 2), 'pitch_hz': pitch,
            'description': f'{tone} · 같은 문장 {duration:.1f}초'}


def preview_info(settings: Settings, model_key: str, voice: str) -> dict[str, Any]:
    metadata, media = preview_paths(settings, model_key, voice)
    try:
        value = json.loads(metadata.read_text(encoding='utf-8'))
        ready = value.get('status') == 'ready' and media.is_file()
        return {**value, 'ready': ready}
    except (OSError, ValueError):
        return {'ready': False, 'status': 'missing', 'description': '기본 샘플 준비 전'}


def preview_catalog(settings: Settings) -> dict[str, Any]:
    return {key: {voice: preview_info(settings, key, voice) for voice in model.voices}
            for key, model in settings.audio_model_profiles.items() if model.enabled}


def prepare_previews(settings: Settings, *, allow_paid_call: bool = False) -> None:
    if (not allow_paid_call or not settings.audio_ai_enabled
            or not settings.audio_key().get_secret_value()):
        return
    for key, model in settings.audio_model_profiles.items():
        if not model.enabled:
            continue
        for voice in model.voices:
            metadata, media = preview_paths(settings, key, voice)
            metadata.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive checkpoint prevents two bootstrap processes making the same paid call.
            try:
                with metadata.open('x', encoding='utf-8') as out:
                    json.dump({'status': 'started'}, out)
            except FileExistsError:
                continue
            try:
                spec = preview_spec(settings, key, voice)
                data, transcript = synthesize(settings.audio_key().get_secret_value(), spec)
                if not transcript_matches(SAMPLE_TEXT, transcript):
                    raise ValueError('preview_transcript')
                result = describe_audio(data)
                media.write_bytes(data)
                value = {**result, 'status': 'ready', 'model': model.model,
                         'text': SAMPLE_TEXT, 'language': '한국어', 'instructions': DELIVERY}
            except Exception as exc:
                # Never expose provider responses or credentials and never retry uncertain calls.
                value = {'status': 'failed', 'description': '기본 샘플 준비 실패',
                         'error_type': type(exc).__name__,
                         'error_code': str(exc) if str(exc) in (
                             'preview_transcript', 'preview_duration', 'preview_format',
                             'audio_provider_rejected', 'audio_response_incomplete') else 'unknown'}
            metadata.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            print(f'{key}/{voice}: {value["status"]}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-paid-call', action='store_true')
    args = parser.parse_args()
    prepare_previews(Settings(), allow_paid_call=args.allow_paid_call)
