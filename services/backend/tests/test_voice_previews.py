from asa.audio_media import pcm_wav
from asa.config import Settings
from asa.voice_previews import prepare_previews, preview_catalog


def test_previews_cached_and_never_regenerated(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, audio_preview_dir=str(tmp_path),
                        audio_ai_enabled=True, audio_api_key='test-only')
    calls = []

    def generate(key, spec):
        calls.append(spec)
        return pcm_wav(b'\0\0' * 24000), spec['cue']['text']

    monkeypatch.setattr('asa.voice_previews.synthesize', generate)
    prepare_previews(settings, allow_paid_call=True)
    catalog = preview_catalog(settings)
    assert len(catalog['openai-realtime']) == 10
    assert all(v['ready'] and v['description'] for v in catalog['openai-realtime'].values())
    assert len({s['cue']['text'] for s in calls}) == 1
    prepare_previews(settings, allow_paid_call=True)
    assert len(calls) == 10


def test_unapproved_or_uncertain_generation_never_retries(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, audio_preview_dir=str(tmp_path),
                        audio_ai_enabled=True, audio_api_key='test-only')
    calls = []

    def fail(key, spec):
        calls.append(spec)
        raise TimeoutError()

    monkeypatch.setattr('asa.voice_previews.synthesize', fail)
    prepare_previews(settings, allow_paid_call=False)
    assert not calls
    prepare_previews(settings, allow_paid_call=True)
    prepare_previews(settings, allow_paid_call=True)
    assert len(calls) == 10
    assert all(not v['ready'] for v in preview_catalog(settings)['openai-realtime'].values())
