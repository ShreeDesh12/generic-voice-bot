import logging

from voice.tts_base import TTSProvider

logger = logging.getLogger(__name__)


class TTSFactory:
    """Factory for creating TTS provider instances."""

    _providers: dict[str, type[TTSProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: type[TTSProvider]):
        cls._providers[name] = provider_class
        logger.info("Registered TTS provider: %s", name)

    @classmethod
    def create(cls, name: str, **kwargs) -> TTSProvider:
        if name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(f"Unknown TTS provider '{name}'. Available: {available}")
        return cls._providers[name](**kwargs)

    @classmethod
    def available_providers(cls) -> list[str]:
        return list(cls._providers.keys())
