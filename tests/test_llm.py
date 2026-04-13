import pytest
from unittest.mock import patch, MagicMock
from llm.base import LLMProvider
from llm.factory import LLMFactory


# --- LLMProvider base class ---

class TestLLMProviderBase:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            LLMProvider()

    def test_concrete_subclass_must_implement_generate(self):
        class IncompleteProvider(LLMProvider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_concrete_subclass_works(self):
        class MockProvider(LLMProvider):
            def generate(self, prompt: str, context: str) -> str:
                return f"response to {prompt}"

        provider = MockProvider()
        assert provider.generate("hello", "ctx") == "response to hello"


# --- LLMFactory ---

class TestLLMFactory:
    def setup_method(self):
        self._original_providers = LLMFactory._providers.copy()

    def teardown_method(self):
        LLMFactory._providers = self._original_providers

    def test_register_and_create(self):
        class FakeProvider(LLMProvider):
            def generate(self, prompt, context):
                return "fake"

        LLMFactory.register("fake", FakeProvider)
        provider = LLMFactory.create("fake")
        assert isinstance(provider, FakeProvider)
        assert provider.generate("q", "c") == "fake"

    def test_create_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            LLMFactory.create("nonexistent_provider_xyz")

    def test_available_providers_includes_registered(self):
        class FakeProvider2(LLMProvider):
            def generate(self, prompt, context):
                return ""

        LLMFactory.register("fake2", FakeProvider2)
        assert "fake2" in LLMFactory.available_providers()

    def test_gemini_is_registered(self):
        assert "gemini" in LLMFactory.available_providers()

    def test_create_passes_kwargs(self):
        class KwargsProvider(LLMProvider):
            def __init__(self, **kwargs):
                self.value = kwargs.get("value")

            def generate(self, prompt, context):
                return str(self.value)

        LLMFactory.register("kwargs_test", KwargsProvider)
        provider = LLMFactory.create("kwargs_test", value=42)
        assert provider.value == 42


# --- GeminiProvider ---

class TestGeminiProvider:
    @patch("llm.gemini_provider.genai")
    @patch("llm.gemini_provider.config")
    def test_init_with_api_key(self, mock_config, mock_genai):
        mock_config.GOOGLE_API_KEY = "test-key"
        from llm.gemini_provider import GeminiProvider

        provider = GeminiProvider()
        mock_genai.configure.assert_called_once_with(api_key="test-key")
        mock_genai.GenerativeModel.assert_called_once_with("gemma-3-1b-it")

    @patch("llm.gemini_provider.genai")
    @patch("llm.gemini_provider.config")
    def test_init_with_explicit_api_key(self, mock_config, mock_genai):
        mock_config.GOOGLE_API_KEY = ""
        from llm.gemini_provider import GeminiProvider

        provider = GeminiProvider(api_key="explicit-key")
        mock_genai.configure.assert_called_with(api_key="explicit-key")

    @patch("llm.gemini_provider.genai")
    @patch("llm.gemini_provider.config")
    def test_init_raises_without_api_key(self, mock_config, mock_genai):
        mock_config.GOOGLE_API_KEY = ""
        from llm.gemini_provider import GeminiProvider

        with pytest.raises(ValueError, match="GOOGLE_API_KEY is required"):
            GeminiProvider()

    @patch("llm.gemini_provider.genai")
    @patch("llm.gemini_provider.config")
    def test_generate_calls_model(self, mock_config, mock_genai):
        mock_config.GOOGLE_API_KEY = "test-key"
        mock_response = MagicMock()
        mock_response.text = "Generated answer"
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        from llm.gemini_provider import GeminiProvider

        provider = GeminiProvider()
        result = provider.generate("What is AI?", "AI is artificial intelligence.")
        assert result == "Generated answer"
        mock_model.generate_content.assert_called_once()

        # Verify prompt includes context
        call_args = mock_model.generate_content.call_args[0][0]
        assert "AI is artificial intelligence." in call_args
        assert "What is AI?" in call_args
