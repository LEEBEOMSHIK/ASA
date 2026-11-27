import io
import json
import wave

import httpx
import pytest

from asa import audio_provider
from asa.audio_contracts import AudioModel
from asa.audio_media import pcm_wav, wav_duration
from asa.config import Settings


def test_audio_providers_are_independently_enabled():
    settings = Settings(_env_file=None, audio_ai_enabled=True,
                        audio_typecast_api_key="test-typecast")
    assert not settings.audio_provider_ready("openai")
    assert not settings.audio_provider_ready("typecast")
    assert "provider" not in AudioModel().model_dump()
    settings = Settings(
        _env_file=None, audio_ai_enabled=True, audio_typecast_api_key="test-typecast",
        audio_api_key="test-openai",
    )
    assert settings.audio_provider_ready("openai")
    assert not settings.audio_provider_ready("typecast")
    settings.audio_transcription_model = "gpt-transcribe"
    assert settings.audio_provider_ready("typecast")
    assert not settings.audio_provider_ready("unknown")
    assert AudioModel(provider="typecast").model_dump()["provider"] == "typecast"
    settings.audio_ai_enabled = False
    assert not settings.audio_provider_ready("typecast")


@pytest.mark.parametrize("transcription_status", [200, 500])
def test_typecast_uses_wav_as_independent_transcription_input(monkeypatch, transcription_status):
    source = pcm_wav(b"\x00\x10" * 24000)
    spec = {"model": {"provider": "typecast", "model": "ssfm-v30"},
            "speaker": {"voice": {"voice": "tc_test", "speed": 1.05,
                                  "language": "한국어", "instructions": "별도 지시"}},
            "cue": {"text": "원본 대사입니다", "emotion": "기쁨"}}
    requests = []

    def respond(request):
        requests.append((request.url.host, request.url.path))
        if request.url.host == "api.typecast.ai":
            assert request.headers["X-API-KEY"] == "typecast-test"
            assert "Authorization" not in request.headers
            payload = json.loads(request.content)
            assert payload["text"] == spec["cue"]["text"]
            assert payload["voice_id"] == "tc_test"
            assert payload["model"] == "ssfm-v30"
            assert payload["language"] == "kor"
            assert payload["output"] == {"audio_format": "wav", "audio_tempo": 1.05}
            assert payload["prompt"] == {"emotion_type": "smart"}
            return httpx.Response(200, headers={"Content-Type": "audio/wav"}, content=source)
        assert request.headers["Authorization"] == "Bearer openai-test"
        assert "X-API-KEY" not in request.headers
        assert b"gpt-transcribe" in request.content
        assert b'name="prompt"' not in request.content
        assert b"RIFF" in request.content
        assert spec["cue"]["text"].encode() not in request.content
        assert spec["speaker"]["voice"]["instructions"].encode() not in request.content
        return httpx.Response(transcription_status, json={"text": "다르게 읽었습니다"})

    client_type = httpx.Client
    monkeypatch.setattr(audio_provider.httpx, "Client", lambda **kwargs: client_type(
        transport=httpx.MockTransport(respond), **kwargs))

    media, transcript = audio_provider.synthesize_typecast(
        "typecast-test", "openai-test", "gpt-transcribe", spec, "ffmpeg")
    assert wav_duration(media) == 1
    with wave.open(io.BytesIO(media), "rb") as stream:
        assert stream.getnchannels() == 1
        assert stream.getframerate() == 24000
    assert requests == [("api.typecast.ai", "/v1/text-to-speech"),
                        ("api.openai.com", "/v1/audio/transcriptions")]
    assert transcript == ("다르게 읽었습니다" if transcription_status == 200 else None)
    assert not audio_provider.transcript_matches(spec["cue"]["text"], transcript or "")
