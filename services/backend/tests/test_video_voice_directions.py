from uuid import uuid4

import pytest

from asa.audio_contracts import AudioSettings
from asa.registry.schemas import RegistryError
from asa.voice_directions import (
    apply_snapshot,
    clip_audio_prompt,
    merge_directions,
    snapshot_speaker,
    validate_timeline,
)


@pytest.mark.parametrize("role", ["narrator", "character"])
def test_auto_narration_keeps_text_but_ignores_hidden_custom_direction(role):
    original = AudioSettings.model_validate(
        {
            "speakers": [
                {
                    "id": "narrator",
                    "name": "나레이션",
                    "role": role,
                    "video_enabled": False,
                    "voice": {"instructions": "숨겨둔 목소리", "speed": 1.25, "language": "영어"},
                }
            ]
        }
    )
    saved = snapshot_speaker(original.speakers[0])
    result = apply_snapshot(
        {
            "speakers": [{"id": "narrator", "name": "나레이션"}],
            "cues": [
                {
                    "id": "one",
                    "speaker_id": "narrator",
                    "text": "숲 속에 살았어요",
                    "start": 0,
                    "end": 2,
                }
            ],
        },
        {"speakers": [saved]},
    )
    prompt = clip_audio_prompt(AudioSettings.model_validate(result), 0, 5)
    assert "숲 속에 살았어요" in prompt
    assert "이야기" in prompt and "이미지" in prompt and "자동" in prompt
    assert "숨겨둔 목소리" not in prompt and "1.25" not in prompt
    assert original.speakers[0].voice.instructions == "숨겨둔 목소리"
    assert not original.speakers[0].video_enabled


def test_custom_narration_snapshot_keeps_user_direction():
    original = AudioSettings.model_validate(
        {
            "speakers": [
                {
                    "id": "narrator",
                    "name": "나레이션",
                    "role": "narrator",
                    "voice": {"instructions": "차분한 중저음"},
                }
            ]
        }
    )
    assert snapshot_speaker(original.speakers[0])["voice"]["instructions"] == "차분한 중저음"


def test_merge_preserves_legacy_voice_and_samples():
    sample = uuid4()
    original = AudioSettings.model_validate(
        {
            "speakers": [
                {
                    "id": "hero",
                    "name": "주인공",
                    "sample_job_id": str(sample),
                    "voice": {"voice": "cedar"},
                }
            ]
        }
    )
    updated = merge_directions(
        original,
        [
            {
                "id": "hero",
                "instructions": "밝고 높은 목소리",
                "language": "한국어",
                "speed": 1,
                "enabled": True,
            }
        ],
    )
    assert updated.speakers[0].voice.voice == "cedar"
    assert updated.speakers[0].sample_job_id == sample
    assert updated.speakers[0].voice.instructions == "밝고 높은 목소리"
    assert original.speakers[0].voice.instructions == ""


def test_clip_prompt_has_only_clip_cues_and_relative_times():
    settings = AudioSettings.model_validate(
        {
            "speakers": [
                {"id": "hero", "name": "주인공", "voice": {"instructions": "높고 밝게"}},
                {"id": "narrator", "name": "나레이션", "role": "narrator"},
            ],
            "cues": [
                {
                    "id": "one",
                    "speaker_id": "hero",
                    "text": "안녕",
                    "start": 5,
                    "end": 7,
                    "emotion": "놀라서",
                },
                {
                    "id": "two",
                    "speaker_id": "narrator",
                    "text": "다음 장면",
                    "start": 10,
                    "end": 12,
                },
            ],
        }
    )
    prompt = clip_audio_prompt(settings, 5, 10)
    assert "안녕" in prompt and "높고 밝게" in prompt and "놀라서" in prompt
    assert "0.00–2.00" in prompt
    assert "다음 장면" not in prompt and "marin" not in prompt


def test_crossing_cue_blocks_instead_of_duplicate_speech():
    settings = AudioSettings.model_validate(
        {
            "speakers": [{"id": "hero", "name": "주인공"}],
            "cues": [{"id": "one", "speaker_id": "hero", "text": "안녕", "start": 4, "end": 7}],
        }
    )
    with pytest.raises(RegistryError, match="video_voice_cue_crosses_clip"):
        clip_audio_prompt(settings, 5, 10)


def test_disabled_narration_is_not_spoken():
    settings = AudioSettings.model_validate(
        {
            "speakers": [
                {"id": "narrator", "name": "나레이션", "role": "narrator", "video_enabled": False}
            ],
            "cues": [
                {
                    "id": "one",
                    "speaker_id": "narrator",
                    "text": "삭제하지 않는 원문",
                    "start": 0,
                    "end": 2,
                }
            ],
        }
    )
    assert clip_audio_prompt(settings, 0, 5) == ""


def test_unmatched_speaker_cannot_silently_drop_saved_description():
    with pytest.raises(RegistryError, match="video_voice_speaker_mismatch"):
        apply_snapshot(
            {"speakers": [{"id": "renamed", "name": "아이"}]},
            {"speakers": [{"id": "child", "name": "아이"}]},
        )


def test_speech_beyond_video_is_not_silently_omitted():
    data = AudioSettings.model_validate(
        {
            "speakers": [{"id": "hero", "name": "주인공"}],
            "cues": [{"id": "one", "speaker_id": "hero", "text": "안녕", "start": 6, "end": 8}],
        }
    )
    with pytest.raises(RegistryError, match="audio_timeline_invalid"):
        validate_timeline(data, 5)
