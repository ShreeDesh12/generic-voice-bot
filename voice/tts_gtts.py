import io
import logging

from voice.tts_base import TTSProvider
from voice.tts_factory import TTSFactory

logger = logging.getLogger(__name__)


class GTTSProvider(TTSProvider):
    """Google Text-to-Speech provider (free, no API key needed)."""

    def __init__(self, **kwargs):
        logger.info("gTTS provider initialized")

    def speak(self, text: str) -> bytes:
        from gtts import gTTS

        logger.info("gTTS converting %d characters", len(text))
        tts = gTTS(text=text, lang="en")
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        audio_bytes = buf.getvalue()
        logger.info("gTTS produced %d bytes", len(audio_bytes))
        return audio_bytes


TTSFactory.register("gtts", GTTSProvider)
