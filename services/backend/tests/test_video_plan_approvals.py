from uuid import uuid4

from asa.audio_contracts import AudioSettings
from asa.registry.video_plan_approvals import fingerprints
from asa.video_contracts import VideoPreparation


def plan():
    image = str(uuid4())
    return VideoPreparation.model_validate({
        "model_key": "wan3", "model_revision": "1", "aspect_ratio": "9:16",
        "clips": [{"clip_id": f"clip{i}", "scene_id": "s1", "shot_id": f"s{i}",
                   "image_id": image, "source_start_seconds": (i-1)*5,
                   "source_end_seconds": i*5, "duration_seconds": 5,
                   "prompt": "A child smiles", "source_excerpt": "text",
                   "continuity_in": "", "continuity_out": "", "split_reason": ""}
                  for i in range(1, 4)]})


def test_only_changed_clip_loses_approval_unless_continuation():
    value = plan()
    value.clips[1].connection_type = "continue"
    value.clips[1].previous_clip_id = "clip1"
    before = fingerprints(value, AudioSettings(), {})
    value.clips[0].prompt = "A child waves"
    after = fingerprints(value, AudioSettings(), {})
    assert before["clip1"] != after["clip1"]
    assert before["clip2"] != after["clip2"]
    assert before["clip3"] == after["clip3"]


def test_shared_model_and_style_invalidate_every_clip():
    value = plan()
    before = fingerprints(value, AudioSettings(), {})
    value.model_revision = "2"
    assert all(v != fingerprints(value, AudioSettings(), {})[k] for k, v in before.items())
    styled = fingerprints(value, AudioSettings(), {"work_visual_style": {"type": "2d"}})
    assert all(v != styled[k] for k, v in fingerprints(value, AudioSettings(), {}).items())


def test_voice_change_only_invalidates_clips_using_speaker():
    value = plan()
    audio = AudioSettings.model_validate({"delivery_mode": "video", "enabled": True,
        "speakers": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
        "cues": [{"id": "one", "speaker_id": "a", "text": "Hello", "start": 0, "end": 3},
                 {"id": "two", "speaker_id": "b", "text": "Hi", "start": 5, "end": 8}]})
    before = fingerprints(value, audio, {})
    audio.speakers[0].voice.instructions = "Soft and warm"
    after = fingerprints(value, audio, {})
    assert before["clip1"] != after["clip1"]
    assert before["clip2"] == after["clip2"]
    assert before["clip3"] == after["clip3"]
