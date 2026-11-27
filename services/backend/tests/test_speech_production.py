import pytest

from asa.audio_contracts import AudioSettings
from asa.registry.schemas import RegistryError
from asa.speech_production import production_settings, require_original_dialogue


def scene_timing() -> AudioSettings:
    return AudioSettings.model_validate({
        "purpose": "timing",
        "enabled": True,
        "timing_auto_align": True,
        "speakers": [
            {"id": "narrator", "name": "내레이터", "role": "narrator"},
            {"id": "person", "name": "인물", "role": "character"},
        ],
        "cues": [
            {"id": "n1", "speaker_id": "narrator", "text": "창문이 열렸다.", "start": 0, "end": 3},
            {"id": "p1", "speaker_id": "person", "text": "누구세요?", "start": 4, "end": 6},
        ],
    })


def test_production_uses_scene_dialogue_without_reusing_measurement_voices() -> None:
    scene = scene_timing()
    plan = production_settings(scene, "studio", ["voice-a", "voice-b"])
    assert plan.enabled and plan.purpose == "production" and not plan.timing_auto_align
    assert plan.cues == scene.cues
    assert [speaker.voice.voice for speaker in plan.speakers] == ["voice-a", "voice-b"]
    assert all(speaker.voice.model_key == "studio" and speaker.sample_job_id is None
               for speaker in plan.speakers)
    assert scene.purpose == "timing" and scene.timing_auto_align


def test_production_locks_dialogue_and_assignment_but_allows_delivery_changes() -> None:
    current = production_settings(scene_timing(), "studio", ["voice-a"])
    edited = current.model_copy(deep=True)
    edited.cues[0].emotion = "조용히"
    edited.cues[0].end = 3.5
    require_original_dialogue(current, edited)
    edited.cues[0].text = "문이 열렸다."
    with pytest.raises(RegistryError, match="speech_source_dialogue_changed"):
        require_original_dialogue(current, edited)


def test_silent_scene_cannot_create_a_production_plan() -> None:
    scene = scene_timing().model_copy(update={"cues": []})
    with pytest.raises(RegistryError, match="speech_source_unavailable"):
        production_settings(scene, "studio", ["voice-a"])
