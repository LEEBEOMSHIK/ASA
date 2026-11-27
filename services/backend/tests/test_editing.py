import io
import math
import wave
from array import array
from uuid import uuid4

import pytest
from PIL import Image, ImageDraw
from pydantic import ValidationError

from asa.audio_media import command, pcm_wav
from asa.editing_contracts import EditPlan
from asa.editing_media import probe, render
from asa.video_analysis import run


def plan():
    return {
        "format": "asa_edit_plan_v1",
        "title": "테스트",
        "summary": "검토",
        "aspect_ratio": "9:16",
        "resolution": "720p",
        "segments": [
            {
                "source_id": "image:" + str(uuid4()),
                "start": 0,
                "duration": 0.5,
                "motion": "zoom_in",
                "transition": "fade",
                "volume": 1,
                "caption": "안녕: [test];",
            }
        ],
        "tracks": [],
    }


def test_edit_plan_bounds():
    data = plan()
    assert EditPlan.model_validate(data).duration == 0.5
    for value in [float("nan"), -1, 601]:
        data = plan()
        data["segments"][0]["duration"] = value
        with pytest.raises(ValidationError):
            EditPlan.model_validate(data)
    data = plan()
    data["segments"][0]["source_id"] = "https://example.com/file"
    with pytest.raises(ValidationError):
        EditPlan.model_validate(data)
    data = plan()
    data["tracks"] = [
        {
            "source_id": "audio:" + str(uuid4()),
            "start": 0.4,
            "offset": 0,
            "duration": 0.5,
            "volume": 0.3,
        }
    ]
    with pytest.raises(ValidationError):
        EditPlan.model_validate(data)


def test_render_images_and_video_without_audio(tmp_path):
    data = plan()
    buf = io.BytesIO()
    Image.new("RGB", (90, 160), "blue").save(buf, format="PNG")
    p = EditPlan.model_validate(data)
    first = render(p, {p.segments[0].source_id: buf.getvalue()}, "ffmpeg")
    assert first[4:8] == b"ftyp"
    original = tmp_path / "original.mp4"
    original.write_bytes(first)
    silent = tmp_path / "silent.mp4"
    assert (
        run(
            command("ffmpeg") + ["-i", str(original), "-an", "-c:v", "copy", str(silent)], 30
        ).returncode
        == 0
    )
    source = "video:" + str(uuid4())
    data["segments"] = [
        {
            **data["segments"][0],
            "source_id": source,
            "motion": "static",
            "caption": "",
            "transition": "cut",
        },
        data["segments"][0],
    ]
    audio_id = "music:" + str(uuid4())
    wav = io.BytesIO()
    with wave.open(wav, "wb") as sound:
        sound.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        sound.writeframes(b"\x00\x01" * 48000)
    data["tracks"] = [
        {"source_id": audio_id, "start": 0.2, "offset": 0.1, "duration": 0.5, "volume": 0.2}
    ]
    second = render(
        EditPlan.model_validate(data),
        {
            source: silent.read_bytes(),
            p.segments[0].source_id: buf.getvalue(),
            audio_id: wav.getvalue(),
        },
        "ffmpeg",
    )
    assert second[4:8] == b"ftyp"
    final = tmp_path / "final.mp4"
    final.write_bytes(second)
    duration, audio = probe(final, "ffmpeg")
    assert audio and 0.9 <= duration <= 1.15


def test_audio_cues_stay_on_schedule_after_multiple_cuts(tmp_path):
    data = plan()
    segment = data["segments"][0]
    segment.update(duration=0.75, motion="static", transition="cut", caption="")
    data["segments"] = [segment.copy() for _ in range(8)]
    source_id = "music:" + str(uuid4())
    cue_starts = [0.25, 5.5]
    data["tracks"] = [
        {"source_id": source_id, "start": start, "offset": 0, "duration": 0.4, "volume": 0.6}
        for start in cue_starts
    ]
    tone = array("h", (int(16000 * math.sin(i * math.tau * 420 / 24000)) for i in range(9600)))
    image = io.BytesIO()
    Image.new("RGB", (90, 160), "blue").save(image, format="PNG")
    output = tmp_path / "timed.mp4"
    output.write_bytes(render(
        EditPlan.model_validate(data),
        {segment["source_id"]: image.getvalue(), source_id: pcm_wav(tone.tobytes())},
        "ffmpeg",
    ))

    # Decode on the presentation clock so repeated or overlapping packets
    # cannot hide cumulative drift in the cue positions.
    result = run(command("ffmpeg") + [
        "-i", str(output), "-map", "0:a:0", "-vn",
        "-af", "aresample=24000:async=1000:min_hard_comp=0.001:first_pts=0",
        "-ac", "1", "-f", "s16le", "pipe:1",
    ], 30)
    assert result.returncode == 0
    samples = array("h")
    samples.frombytes(result.stdout)
    hop = 120
    audible = [
        i * hop / 24_000
        for i in range(len(samples) // hop)
        if max(abs(s) for s in samples[i * hop:(i + 1) * hop]) > 3000
        and (
            i == 0 or max(abs(s) for s in samples[(i - 1) * hop:i * hop]) <= 3000
        )
    ]
    assert audible == pytest.approx(cue_starts, abs=0.02)


@pytest.mark.parametrize("motion", ["zoom_in", "zoom_out"])
def test_image_zoom_moves_at_a_steady_subpixel_rate(tmp_path, motion):
    data = plan()
    data["segments"][0].update(duration=2, motion=motion, transition="cut", caption="")
    image = Image.new("RGB", (720, 1280), "black")
    ImageDraw.Draw(image).rectangle((150, 510, 350, 770), fill="white")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    validated = EditPlan.model_validate(data)
    output = tmp_path / "zoom.mp4"
    assets = {validated.segments[0].source_id: buf.getvalue()}
    output.write_bytes(render(validated, assets, "ffmpeg"))
    frames = run(command("ffmpeg") + [
        "-i", str(output), "-an", "-vf", "crop=720:2:0:638,format=gray",
        "-fps_mode", "passthrough", "-f", "rawvideo", "pipe:1",
    ], 30)
    assert frames.returncode == 0
    rows = [frames.stdout[n:n + 720] for n in range(0, len(frames.stdout), 1440)]
    assert len(rows) == 48
    centers = [sum(x * brightness for x, brightness in enumerate(row)) / sum(row) for row in rows]
    steps = [current - previous for previous, current in zip(centers, centers[1:])]
    assert abs(centers[-1] - centers[0]) > 5
    # A smooth zoom moves the bright target by about 0.14 pixels per frame.
    average = sum(steps) / len(steps)
    assert max(abs(step - average) for step in steps) < 0.25
