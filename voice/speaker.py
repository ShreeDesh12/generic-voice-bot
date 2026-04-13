"""Backward-compatible VoiceSpeaker that delegates to the TTS factory."""

import logging

import config

# Register all providers by importing them
import voice.tts_edge  # noqa: F401
import voice.tts_elevenlabs  # noqa: F401
import voice.tts_gtts  # noqa: F401
from voice.tts_factory import TTSFactory

logger = logging.getLogger(__name__)


class VoiceSpeaker:
    """Thin wrapper that creates a TTS provider via the factory."""

    def __init__(self, voice_id: str | None = None, gender: str | None = None):
        self._provider = TTSFactory.create(config.TTS_PROVIDER, voice_id=voice_id, gender=gender)

    def speak(self, text: str) -> bytes:
        return self._provider.speak(text)

    def speak_and_play(self, text: str):
        self._provider.speak_and_play(text)
