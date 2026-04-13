import io
import logging
import queue
import speech_recognition as sr

logger = logging.getLogger(__name__)


class VoiceListener:
    """Microphone listener with auto-listen using speech_recognition."""

    def __init__(self, use_microphone: bool = True):
        self.recognizer = sr.Recognizer()
        self.transcript_queue: queue.Queue[str] = queue.Queue()
        self._stop_fn = None
        self.is_listening = False
        self.microphone = None

        if use_microphone:
            logger.info("Initializing microphone and calibrating for ambient noise")
            self.microphone = sr.Microphone()
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            logger.info("Microphone ready")

    def _callback(self, recognizer: sr.Recognizer, audio: sr.AudioData):
        """Background callback that processes audio chunks."""
        try:
            text = recognizer.recognize_google(audio)
            if text.strip():
                logger.info("Background STT recognized: %s", text[:80])
                self.transcript_queue.put(text)
        except sr.UnknownValueError:
            logger.debug("Background STT: speech not recognized")
        except sr.RequestError as e:
            logger.error("Background STT request error: %s", e)
            self.transcript_queue.put(f"[STT Error: {e}]")

    def start(self):
        """Start background listening."""
        if self.is_listening:
            return
        logger.info("Starting background listening")
        self._stop_fn = self.recognizer.listen_in_background(
            self.microphone, self._callback
        )
        self.is_listening = True

    def stop(self):
        """Stop background listening."""
        if self._stop_fn is not None:
            logger.info("Stopping background listening")
            self._stop_fn(wait_for_stop=False)
            self._stop_fn = None
        self.is_listening = False

    def listen_once(self) -> str | None:
        """Record a single phrase and return the transcript. Requires microphone."""
        if self.microphone is None:
            logger.warning("listen_once called without microphone")
            return "[STT Error: No microphone available]"
        try:
            logger.info("Listening for single phrase...")
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=15)
            text = self.recognizer.recognize_google(audio)
            logger.info("listen_once recognized: %s", text[:80] if text else "(empty)")
            return text.strip() if text.strip() else None
        except sr.WaitTimeoutError:
            logger.debug("listen_once timed out waiting for speech")
            return None
        except sr.UnknownValueError:
            logger.debug("listen_once: speech not recognized")
            return None
        except sr.RequestError as e:
            logger.error("listen_once STT request error: %s", e)
            return f"[STT Error: {e}]"

    def transcribe_audio_bytes(self, audio_bytes: bytes) -> str | None:
        """Transcribe audio bytes (WAV) from browser recording."""
        logger.info("Transcribing %d bytes of audio", len(audio_bytes))
        try:
            audio_file = sr.AudioFile(io.BytesIO(audio_bytes))
            with audio_file as source:
                audio = self.recognizer.record(source)
            text = self.recognizer.recognize_google(audio)
            logger.info("Transcription result: %s", text[:80] if text else "(empty)")
            return text.strip() if text.strip() else None
        except sr.UnknownValueError:
            logger.debug("transcribe_audio_bytes: speech not recognized")
            return None
        except sr.RequestError as e:
            logger.error("transcribe_audio_bytes STT request error: %s", e)
            return f"[STT Error: {e}]"

    def get_transcript(self) -> str | None:
        """Get the next transcript from the queue, or None if empty."""
        try:
            return self.transcript_queue.get_nowait()
        except queue.Empty:
            return None
