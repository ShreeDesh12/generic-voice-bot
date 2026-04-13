import os
import importlib
from unittest.mock import patch


class TestConfig:
    @patch.dict(os.environ, {
        "GOOGLE_API_KEY": "gkey",
        "ELEVENLABS_API_KEY": "ekey",
        "ELEVENLABS_VOICE_ID": "Josh",
        "LLM_PROVIDER": "openai",
        "MAX_CONTEXT_LENGTH": "1000",
    })
    def test_loads_env_values(self):
        with patch("dotenv.load_dotenv"):
            import config
            importlib.reload(config)

        assert config.GOOGLE_API_KEY == "gkey"
        assert config.ELEVENLABS_API_KEY == "ekey"
        assert config.ELEVENLABS_VOICE_ID == "Josh"
        assert config.LLM_PROVIDER == "openai"
        assert config.MAX_CONTEXT_LENGTH == 1000

    @patch.dict(os.environ, {}, clear=True)
    def test_defaults_when_env_empty(self):
        with patch("dotenv.load_dotenv"):
            import config
            importlib.reload(config)

        assert config.GOOGLE_API_KEY == ""
        assert config.ELEVENLABS_API_KEY == ""
        assert config.ELEVENLABS_VOICE_ID == "Rachel"
        assert config.LLM_PROVIDER == "gemini"
        assert config.MAX_CONTEXT_LENGTH == 50000
