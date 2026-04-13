from abc import ABC, abstractmethod


class TTSProvider(ABC):
    """Abstract base class for text-to-speech providers."""

    @abstractmethod
    def speak(self, text: str) -> bytes:
        """Convert text to speech and return MP3 audio bytes."""

    def speak_and_play(self, text: str):
        """Convert text to speech and play it directly."""
        import subprocess
        import tempfile

        audio_bytes = self.speak(text)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_bytes)
            subprocess.run(["afplay", f.name])
