import io
import queue
import pytest
from unittest.mock import patch, MagicMock
import speech_recognition as sr


# --- VoiceListener ---

class TestVoiceListener:
    @patch("voice.listener.sr.Recognizer")
    @patch("voice.listener.sr.Microphone")
    def test_init_with_microphone(self, mock_mic_cls, mock_recognizer_cls):
        mock_mic = MagicMock()
        mock_mic.__enter__ = MagicMock(return_value=mock_mic)
        mock_mic.__exit__ = MagicMock(return_value=False)
        mock_mic_cls.return_value = mock_mic

        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=True)
        assert listener.microphone is not None
        assert listener.is_listening is False
        listener.recognizer.adjust_for_ambient_noise.assert_called_once()

    def test_init_without_microphone(self):
        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)
        assert listener.microphone is None
        assert listener.is_listening is False

    def test_listen_once_without_microphone(self):
        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)
        result = listener.listen_once()
        assert result == "[STT Error: No microphone available]"

    def test_get_transcript_empty_queue(self):
        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)
        assert listener.get_transcript() is None

    def test_get_transcript_returns_queued_item(self):
        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)
        listener.transcript_queue.put("hello world")
        assert listener.get_transcript() == "hello world"

    def test_get_transcript_fifo_order(self):
        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)
        listener.transcript_queue.put("first")
        listener.transcript_queue.put("second")
        assert listener.get_transcript() == "first"
        assert listener.get_transcript() == "second"
        assert listener.get_transcript() is None

    def test_stop_when_not_listening(self):
        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)
        listener.stop()  # Should not raise
        assert listener.is_listening is False

    def test_stop_calls_stop_fn(self):
        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)
        mock_stop = MagicMock()
        listener._stop_fn = mock_stop
        listener.is_listening = True

        listener.stop()
        mock_stop.assert_called_once_with(wait_for_stop=False)
        assert listener.is_listening is False
        assert listener._stop_fn is None

    def test_start_does_not_restart_if_already_listening(self):
        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)
        listener.is_listening = True
        original_stop_fn = listener._stop_fn

        listener.start()
        assert listener._stop_fn is original_stop_fn

    @patch("voice.listener.sr.AudioFile")
    def test_transcribe_audio_bytes_success(self, mock_audio_file_cls):
        mock_source = MagicMock()
        mock_source.__enter__ = MagicMock(return_value=mock_source)
        mock_source.__exit__ = MagicMock(return_value=False)
        mock_audio_file_cls.return_value = mock_source

        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)

        with patch.object(listener.recognizer, "record") as mock_record, \
             patch.object(listener.recognizer, "recognize_google") as mock_recognize:
            mock_recognize.return_value = "transcribed text"
            result = listener.transcribe_audio_bytes(b"fake wav data")
            assert result == "transcribed text"

    @patch("voice.listener.sr.AudioFile")
    def test_transcribe_audio_bytes_unknown_value(self, mock_audio_file_cls):
        mock_source = MagicMock()
        mock_source.__enter__ = MagicMock(return_value=mock_source)
        mock_source.__exit__ = MagicMock(return_value=False)
        mock_audio_file_cls.return_value = mock_source

        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)

        with patch.object(listener.recognizer, "record"), \
             patch.object(listener.recognizer, "recognize_google", side_effect=sr.UnknownValueError()):
            result = listener.transcribe_audio_bytes(b"noise")
            assert result is None

    @patch("voice.listener.sr.AudioFile")
    def test_transcribe_audio_bytes_request_error(self, mock_audio_file_cls):
        mock_source = MagicMock()
        mock_source.__enter__ = MagicMock(return_value=mock_source)
        mock_source.__exit__ = MagicMock(return_value=False)
        mock_audio_file_cls.return_value = mock_source

        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)

        with patch.object(listener.recognizer, "record"), \
             patch.object(listener.recognizer, "recognize_google", side_effect=sr.RequestError("API down")):
            result = listener.transcribe_audio_bytes(b"data")
            assert result == "[STT Error: API down]"

    def test_callback_queues_recognized_text(self):
        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)
        mock_recognizer = MagicMock()
        mock_audio = MagicMock()
        mock_recognizer.recognize_google.return_value = "hello"

        listener._callback(mock_recognizer, mock_audio)
        assert listener.transcript_queue.get_nowait() == "hello"

    def test_callback_ignores_unknown_value(self):
        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)
        mock_recognizer = MagicMock()
        mock_recognizer.recognize_google.side_effect = sr.UnknownValueError()

        listener._callback(mock_recognizer, MagicMock())
        assert listener.transcript_queue.empty()

    def test_callback_queues_error_on_request_error(self):
        from voice.listener import VoiceListener
        listener = VoiceListener(use_microphone=False)
        mock_recognizer = MagicMock()
        mock_recognizer.recognize_google.side_effect = sr.RequestError("fail")

        listener._callback(mock_recognizer, MagicMock())
        result = listener.transcript_queue.get_nowait()
        assert "[STT Error:" in result


# --- VoiceSpeaker ---

class TestVoiceSpeaker:
    @patch("voice.speaker.config")
    def test_init_raises_without_api_key(self, mock_config):
        mock_config.ELEVENLABS_API_KEY = ""
        from voice.speaker import VoiceSpeaker
        with pytest.raises(ValueError, match="ELEVENLABS_API_KEY is required"):
            VoiceSpeaker()

    @patch("voice.speaker.ElevenLabs")
    @patch("voice.speaker.config")
    def test_init_success(self, mock_config, mock_eleven_cls):
        mock_config.ELEVENLABS_API_KEY = "test-key"
        mock_config.ELEVENLABS_VOICE_ID = "Rachel"

        from voice.speaker import VoiceSpeaker
        speaker = VoiceSpeaker()
        mock_eleven_cls.assert_called_once_with(api_key="test-key")
        assert speaker.voice_id == "Rachel"

    @patch("voice.speaker.ElevenLabs")
    @patch("voice.speaker.config")
    def test_speak_returns_bytes(self, mock_config, mock_eleven_cls):
        mock_config.ELEVENLABS_API_KEY = "test-key"
        mock_config.ELEVENLABS_VOICE_ID = "Rachel"

        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"chunk1", b"chunk2"])
        mock_eleven_cls.return_value = mock_client

        from voice.speaker import VoiceSpeaker
        speaker = VoiceSpeaker()
        result = speaker.speak("Hello world")
        assert result == b"chunk1chunk2"
        mock_client.text_to_speech.convert.assert_called_once_with(
            voice_id="Rachel",
            text="Hello world",
            model_id="eleven_multilingual_v2",
        )

    @patch("voice.speaker.play")
    @patch("voice.speaker.ElevenLabs")
    @patch("voice.speaker.config")
    def test_speak_and_play(self, mock_config, mock_eleven_cls, mock_play):
        mock_config.ELEVENLABS_API_KEY = "test-key"
        mock_config.ELEVENLABS_VOICE_ID = "Rachel"

        mock_audio = MagicMock()
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = mock_audio
        mock_eleven_cls.return_value = mock_client

        from voice.speaker import VoiceSpeaker
        speaker = VoiceSpeaker()
        speaker.speak_and_play("Test")
        mock_play.assert_called_once_with(mock_audio)
