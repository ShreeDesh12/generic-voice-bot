from llm.base import LLMProvider


class LLMFactory:
    """Registry and factory for LLM providers."""

    _providers: dict[str, type[LLMProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: type[LLMProvider]):
        """Register an LLM provider class under a name."""
        cls._providers[name] = provider_class

    @classmethod
    def create(cls, name: str, **kwargs) -> LLMProvider:
        """Create an instance of a registered LLM provider."""
        if name not in cls._providers:
            available = ", ".join(cls._providers.keys()) or "none"
            raise ValueError(
                f"Unknown LLM provider '{name}'. Available: {available}"
            )
        return cls._providers[name](**kwargs)

    @classmethod
    def available_providers(cls) -> list[str]:
        """Return list of registered provider names."""
        return list(cls._providers.keys())


# Import providers to trigger registration
import llm.gemini_provider  # noqa: F401, E402
