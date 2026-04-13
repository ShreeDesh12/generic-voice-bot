import logging

import config
from voice.tts_base import TTSProvider
from voice.tts_factory import TTSFactory

logger = logging.getLogger(__name__)


class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs text-to-speech provider (paid)."""

    def __init__(self, voice_id: str | None = None, **kwargs):
        from elevenlabs.client import ElevenLabs

        if not config.ELEVENLABS_API_KEY:
            raise ValueError("ELEVENLABS_API_KEY is required for ElevenLabs TTS.")
        self.voice_id = voice_id or config.ELEVENLABS_VOICE_ID
        self.client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)
        logger.info("ElevenLabs TTS initialized (voice: %s)", self.voice_id)

    def speak(self, text: str) -> bytes:
        logger.info("ElevenLabs TTS converting %d characters", len(text))
        audio_generator = self.client.text_to_speech.convert(
            voice_id=self.voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
        )
        audio_bytes = b"".join(audio_generator)
        logger.info("ElevenLabs TTS produced %d bytes", len(audio_bytes))
        return audio_bytes

    def speak_and_play(self, text: str):
        from elevenlabs import play

        audio = self.client.text_to_speech.convert(
            voice_id=self.voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
        )
        play(audio)


TTSFactory.register("elevenlabs", ElevenLabsTTSProvider)
