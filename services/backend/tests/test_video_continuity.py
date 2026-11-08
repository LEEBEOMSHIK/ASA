from hashlib import sha256
from uuid import uuid4

import pytest

from asa.video_continuity import approved_source, source_video
from asa.video_contracts import VideoPreparation


def clip(index, **changes):
    return dict(clip_id=str(index), scene_id="scene", shot_id="shot", image_id=str(uuid4()),
                source_start_seconds=index * 5, source_end_seconds=(index + 1) * 5,
                duration_seconds=5, prompt="walk", source_excerpt="", continuity_in="",
                continuity_out="", split_reason="", **changes)


def plan(clips):
    return VideoPreparation(model_key="wan3", model_revision="1", aspect_ratio="9:16",
                            clips=clips)


def test_legacy_plan_and_sequential_continuation():
    assert plan([clip(0)]).clips[0].connection_type == "cut"
    assert plan([clip(0), clip(1, connection_type="continue", previous_clip_id="0")])


@pytest.mark.parametrize("clips", [
    [clip(0, connection_type="continue", previous_clip_id="0")],
    [clip(0), clip(1, connection_type="continue", previous_clip_id="missing")],
    [clip(0), clip(1, connection_type="continue", previous_clip_id="1")],
    [clip(0, previous_clip_id="other")],
])
def test_reject_invalid_dependencies(clips):
    with pytest.raises(ValueError):
        plan(clips)


def test_continuation_cannot_use_trimmed_away_final_frame():
    first = clip(0)
    first["duration_seconds"] = 10  # Only five seconds are used in the timeline.
    with pytest.raises(ValueError, match="requires_trim"):
        plan([first, clip(1, connection_type="continue", previous_clip_id="0")])


class Connection:
    def __init__(self, row):
        self.row = row
        self.params = None

    def execute(self, query, params):
        assert "status='approved'" in query
        assert "workspace_id=%s AND request_id=%s" in query
        self.params = params
        return self

    def fetchone(self):
        return self.row


def test_source_requires_approval_and_pins_content_and_scope():
    conn = Connection(None)
    with pytest.raises(ValueError, match="approval_required"):
        approved_source(conn, "ws", "req", 2, "0")
    assert conn.params == ("ws", "req", 2, "0")
    conn.row = {"id": "parent", "video": b"original"}
    snapshot = approved_source(conn, "ws", "req", 2, "0")
    assert snapshot["source_video_sha256"] == sha256(b"original").hexdigest()
    child = {"request_id": "req", "answer_version": 2,
             "generation_input": {"previous_clip_id": "0", **snapshot}}
    assert source_video(conn, "ws", child) == b"original"
    conn.row["video"] = b"changed"
    with pytest.raises(ValueError, match="reference_changed"):
        source_video(conn, "ws", child)


def test_extract_actual_final_frame(tmp_path):
    from io import BytesIO

    import imageio_ffmpeg
    from PIL import Image

    from asa.video_analysis import run
    from asa.video_continuity import last_frame

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for i, color in enumerate(("red", "blue")):
        Image.new("RGB", (240, 400), color).save(tmp_path / f"{i}.png")
    path = tmp_path / "test.mp4"
    result = run([ffmpeg, "-y", "-framerate", "1", "-i", str(tmp_path / "%d.png"),
                  "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], 30)
    assert result.returncode == 0
    image = Image.open(BytesIO(last_frame(path.read_bytes(), ffmpeg)))
    red, green, blue = image.getpixel((100, 100))
    assert blue > 240 and red < 10 and green < 10


def test_instruction_upgrade_preserves_content_and_is_idempotent():
    from asa.video_continuity_instructions import MARKER, upgrade_definition

    original = {"instructions": "original common",
                "video_prompt_modules": {"style_instructions": {
                    "animation_2d": "2d original", "animation_3d": "3d original",
                    "live_action": "live original"}},
                "output_schema": {"properties": {"clips": {"items": {
                    "type": "object", "properties": {}, "required": []}}}}}
    updated = upgrade_definition(original)
    assert updated["instructions"].startswith(original["instructions"])
    assert MARKER not in original["instructions"]
    assert upgrade_definition(updated) == updated
    for key, body in original["video_prompt_modules"]["style_instructions"].items():
        assert updated["video_prompt_modules"]["style_instructions"][key].startswith(body)
