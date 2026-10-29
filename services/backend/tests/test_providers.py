import pytest

from asa.config import Settings
from asa.providers import make_script_generator


def test_provider_requires_explicit_model_and_key():
    settings = Settings(_env_file=None, ai_model="", ai_api_key="")
    with pytest.raises(ValueError, match="ASA_AI_MODEL"):
        make_script_generator(settings)
