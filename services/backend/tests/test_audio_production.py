import io
import wave

import pytest
from pydantic import ValidationError

from asa.audio_contracts import AudioSettings, cue_fingerprint, validate_measured
from asa.audio_media import normalize_audio


def plan():
    return {
        "enabled": True,
        "speakers": [{"id": "child", "name": "이루리"}],
        "cues": [{"id": "line1", "speaker_id": "child", "text": "안녕!", "start": 0, "end": 2}],
    }


def test_audio_references_overlap_and_finite_time():
    data = plan()
    assert AudioSettings.model_validate(data).speakers[0].id == "child"
    for cue in [{"speaker_id": "missing"}, {"end": float("nan")}, {"end": 0}]:
        changed = plan()
        changed["cues"][0].update(cue)
        with pytest.raises(ValidationError):
            AudioSettings.model_validate(changed)
    data["cues"].append({**data["cues"][0], "id": "line2"})
    with pytest.raises(ValidationError, match="overlap"):
        AudioSettings.model_validate(data)


def test_fingerprint_tracks_voice_and_text_but_not_timing():
    a = AudioSettings.model_validate(plan())
    before = cue_fingerprint(a.cues[0], a.speakers[0])
    a.cues[0].start, a.cues[0].end = 2, 4
    assert before == cue_fingerprint(a.cues[0], a.speakers[0])
    a.speakers[0].voice.voice = "cedar"
    assert before != cue_fingerprint(a.cues[0], a.speakers[0])
    with pytest.raises(ValueError, match="audio_timing"):
        validate_measured(a.cues[0], 2.2)
    validate_measured(a.cues[0], 1.5)


def test_upload_decodes_and_measures_real_audio():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"\0\0" * 24000)
    audio, duration = normalize_audio(stream.getvalue(), "ffmpeg")
    assert duration == pytest.approx(1, abs=0.02)
    assert audio.startswith(b"RIFF")
    with pytest.raises(ValueError):
        normalize_audio(b"invalid", "ffmpeg")


def test_speech_protocol_and_exact_transcript(monkeypatch):
    import base64
    import json

    from asa import audio_provider
    from asa.audio_media import wav_duration
    from asa.config import Settings
    from asa.registry.audio_service import speech_key, speech_spec

    data = AudioSettings.model_validate(plan())
    spec = speech_spec(Settings(_env_file=None), data, "line1")
    events = iter(
        [
            {"type": "session.updated"},
            {
                "type": "response.output_audio.delta",
                "delta": base64.b64encode(b"\0\0" * 24000).decode(),
            },
            {"type": "response.output_audio_transcript.done", "transcript": "안녕!"},
            {"type": "response.done", "response": {"status": "completed"}},
        ]
    )
    sent = []

    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def send(self, text):
            sent.append(json.loads(text))

        def recv(self, **kwargs):
            return json.dumps(next(events))

    monkeypatch.setattr(audio_provider, "connect", lambda *a, **k: Socket())
    media, transcript = audio_provider.synthesize("test-only", spec)
    assert wav_duration(media) == 1
    assert audio_provider.transcript_matches("안녕!", transcript)
    assert not audio_provider.transcript_matches("안녕!", "안녕 반가워!")
    assert [e["type"] for e in sent] == [
        "session.update",
        "conversation.item.create",
        "response.create",
    ]
    assert sent[1]["item"]["content"][0]["text"] == "안녕!"
    first = speech_key(spec)
    spec["cue"]["id"] = "line2"
    assert speech_key(spec) != first


def test_composition_decodes_video_and_keeps_speech_window(tmp_path):
    from asa.audio_contracts import Music
    from asa.audio_media import command, compose, pcm_wav, wav_duration
    from asa.video_analysis import run

    source = tmp_path / "clip.mp4"
    result = run(
        command("ffmpeg")
        + [
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x64:r=24",
            "-t",
            "1",
            "-c:v",
            "libx264",
            str(source),
        ],
        30,
    )
    assert result.returncode == 0
    voice = pcm_wav(b"\0\0" * 12000)
    output = compose(
        [(source.read_bytes(), 1), (source.read_bytes(), 1)],
        [(voice, 0.5)],
        voice,
        Music(loop=True, offset=0.1),
        "ffmpeg",
    )
    final = tmp_path / "final.mp4"
    final.write_bytes(output)
    extracted = tmp_path / "extracted.wav"
    result = run(
        command("ffmpeg") + ["-i", str(final), "-vn", "-ac", "1", "-ar", "24000", str(extracted)],
        30,
    )
    assert result.returncode == 0
    assert wav_duration(extracted.read_bytes()) == pytest.approx(2, abs=0.1)
    with pytest.raises(ValueError, match="audio_timing"):
        compose([(source.read_bytes(), 1)], [(voice, 0.8)], None, Music(), "ffmpeg")
    with pytest.raises(ValueError, match="audio_video_too_short"):
        compose([(source.read_bytes(), 2)], [], None, Music(), "ffmpeg")


def test_audio_template_upgrade_is_additive_and_valid():
    import json
    from pathlib import Path

    from asa.audio_instructions import upgrade_definition
    from asa.registry.schemas import AgentDraft
    from asa.registry.service import validate_definition

    path = Path(__file__).parents[3] / "docs/agent-templates/video-prompt-planner.json"
    draft = json.loads(path.read_text(encoding="utf-8"))
    result = upgrade_definition(draft)
    assert upgrade_definition(result) == result
    assert result["input_schema"] == draft["input_schema"]
    errors = validate_definition(AgentDraft.model_validate(result), {})
    assert not [e for e in errors if e.code.startswith("schema")], errors
