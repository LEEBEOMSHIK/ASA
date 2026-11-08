import pytest

from asa.audio_contracts import AudioSettings
from asa.config import Settings
from asa.registry import audio_service as service
from asa.registry.schemas import RegistryError


def test_timing_audio_cannot_be_approved():
    with pytest.raises(RegistryError, match='audio_timing_only'):
        service.approve_speech(Settings(_env_file=None), AudioSettings(),
                               {'input': {'purpose': 'timing'}, 'cue_id': 'missing'})


def test_sample_spec_is_separate_from_production_and_tracks_voice():
    data = AudioSettings(speakers=[{'id': 'narrator', 'name': '나레이션', 'role': 'narrator'}])
    settings = Settings(_env_file=None)
    spec = service.sample_spec(settings, data, 'narrator')
    assert spec['purpose'] == 'sample'
    assert spec['cue']['text']
    original = service.speech_key(spec)
    data.speakers[0].voice.instructions = '차분한 이야기꾼'
    assert service.speech_key(service.sample_spec(settings, data, 'narrator')) != original
