import asyncio
import io
import logging

import config
from voice.tts_base import TTSProvider
from voice.tts_factory import TTSFactory

logger = logging.getLogger(__name__)

# Voice mapping: gender -> Edge TTS voice name
EDGE_VOICES = {
    "female": "en-US-JennyNeural",
    "male": "en-US-GuyNeural",
    "unknown": "en-US-GuyNeural",
}


class EdgeTTSProvider(TTSProvider):
    """Microsoft Edge TTS provider (free, no API key, supports gender & speed)."""

    def __init__(self, voice_id: str | None = None, gender: str | None = None, **kwargs):
        if voice_id and voice_id in EDGE_VOICES.values():
            self.voice = voice_id
        else:
            g = gender or getattr(config, "TTS_EDGE_GENDER", "female")
            self.voice = EDGE_VOICES.get(g, "en-US-JennyNeural")
        # Speed: e.g. "+20%" for faster, "-10%" for slower
        self.rate = getattr(config, "TTS_EDGE_RATE", "+15%")
        logger.info("Edge TTS initialized (voice: %s, rate: %s)", self.voice, self.rate)

    def speak(self, text: str) -> bytes:
        logger.info("Edge TTS converting %d characters", len(text))
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside FastAPI's event loop — run in a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, self._generate(text)).result()
        return asyncio.run(self._generate(text))

    async def _generate(self, text: str) -> bytes:
        import edge_tts

        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        audio_bytes = buf.getvalue()
        logger.info("Edge TTS produced %d bytes", len(audio_bytes))
        return audio_bytes


TTSFactory.register("edge", EdgeTTSProvider)
