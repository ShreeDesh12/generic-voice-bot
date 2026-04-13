"""Tests to verify that LLM text output is converted to voice via TTS."""

import pytest
from unittest.mock import MagicMock, patch


def make_session_state(**overrides):
    """Create a mock Streamlit session_state with defaults."""
    defaults = {
        "context": "some context",
        "contact_details": {"email": "test@example.com"},
        "messages": [],
        "listener": None,
        "speaker": None,
        "llm": None,
        "is_listening": False,
        "last_audio": None,
        "voice_mode": "Tap & Say",
        "last_audio_id": None,
    }
    defaults.update(overrides)

    state = MagicMock()
    for k, v in defaults.items():
        setattr(state, k, v)
    state.__contains__ = lambda self, key: key in defaults
    state.__getitem__ = lambda self, key: defaults[key]
    return state


class TestProcessQueryTTS:
    """Verify that process_query converts LLM response to speech."""

    @patch("app.st")
    def test_tts_called_with_llm_response(self, mock_st):
        """When speaker exists, speak() should be called with the LLM response."""
        mock_llm = MagicMock()
        mock_llm.generate_portfolio.return_value = "The answer is 42."

        mock_speaker = MagicMock()
        mock_speaker.speak.return_value = b"audio-bytes"

        mock_st.session_state = make_session_state(
            llm=mock_llm,
            speaker=mock_speaker,
        )
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock(return_value=False)

        from app import process_query
        process_query("What is the meaning of life?")

        # LLM was called
        mock_llm.generate_portfolio.assert_called_once_with(
            prompt="What is the meaning of life?",
            context="some context",
            contact_details={"email": "test@example.com"},
        )

        # TTS was called with the LLM response
        mock_speaker.speak.assert_called_once_with("The answer is 42.")

        # Audio bytes stored in session state for playback
        assert mock_st.session_state.last_audio == b"audio-bytes"

    @patch("app.st")
    def test_tts_skipped_when_no_speaker(self, mock_st):
        """When speaker is None, TTS should be silently skipped."""
        mock_llm = MagicMock()
        mock_llm.generate_portfolio.return_value = "response"

        mock_st.session_state = make_session_state(
            llm=mock_llm,
            speaker=None,
        )
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock(return_value=False)

        from app import process_query
        process_query("test")

        # LLM still responds
        mock_llm.generate_portfolio.assert_called_once()

        # No audio stored
        assert mock_st.session_state.last_audio is None

    @patch("app.st")
    def test_tts_error_shows_warning(self, mock_st):
        """When TTS fails, a warning should be shown but response still saved."""
        mock_llm = MagicMock()
        mock_llm.generate_portfolio.return_value = "good response"

        mock_speaker = MagicMock()
        mock_speaker.speak.side_effect = Exception("ElevenLabs API down")

        messages_list = []
        mock_st.session_state = make_session_state(
            llm=mock_llm,
            speaker=mock_speaker,
        )
        mock_st.session_state.messages = messages_list
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock(return_value=False)

        from app import process_query
        process_query("test")

        # Warning displayed for TTS failure
        mock_st.warning.assert_called_once()
        assert "TTS Error" in mock_st.warning.call_args[0][0]

        # Response still added to messages despite TTS failure
        assert {"role": "assistant", "content": "good response"} in messages_list

    @patch("app.st")
    def test_llm_error_still_passed_to_tts(self, mock_st):
        """When LLM fails, error message should still go through TTS."""
        mock_llm = MagicMock()
        mock_llm.generate_portfolio.side_effect = Exception("API quota exceeded")

        mock_speaker = MagicMock()
        mock_speaker.speak.return_value = b"error-audio"

        mock_st.session_state = make_session_state(
            llm=mock_llm,
            speaker=mock_speaker,
        )
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock(return_value=False)

        from app import process_query
        process_query("test")

        # TTS is called with the error message
        tts_text = mock_speaker.speak.call_args[0][0]
        assert "LLM Error" in tts_text

    @patch("app.st")
    def test_messages_appended_in_correct_order(self, mock_st):
        """User message should be appended before assistant response."""
        mock_llm = MagicMock()
        mock_llm.generate_portfolio.return_value = "bot reply"

        messages_list = []
        mock_st.session_state = make_session_state(
            llm=mock_llm,
            speaker=None,
        )
        mock_st.session_state.messages = messages_list
        mock_st.spinner.return_value.__enter__ = MagicMock()
        mock_st.spinner.return_value.__exit__ = MagicMock(return_value=False)

        from app import process_query
        process_query("user question")

        assert len(messages_list) == 2
        assert messages_list[0] == {"role": "user", "content": "user question"}
        assert messages_list[1] == {"role": "assistant", "content": "bot reply"}


class TestSpeakerInitialization:
    """Test that the speaker (TTS) initialization handles failures properly."""

    @patch("voice.speaker.ElevenLabs")
    @patch("voice.speaker.config")
    def test_speaker_init_succeeds_with_valid_key(self, mock_config, mock_eleven):
        mock_config.ELEVENLABS_API_KEY = "valid-key"
        mock_config.ELEVENLABS_VOICE_ID = "Rachel"

        from voice.speaker import VoiceSpeaker
        speaker = VoiceSpeaker()
        assert speaker is not None

    @patch("voice.speaker.config")
    def test_speaker_init_fails_without_key(self, mock_config):
        mock_config.ELEVENLABS_API_KEY = ""

        from voice.speaker import VoiceSpeaker
        with pytest.raises(ValueError, match="ELEVENLABS_API_KEY is required"):
            VoiceSpeaker()

    @patch("voice.speaker.ElevenLabs")
    @patch("voice.speaker.config")
    def test_speak_produces_audio_bytes(self, mock_config, mock_eleven):
        mock_config.ELEVENLABS_API_KEY = "key"
        mock_config.ELEVENLABS_VOICE_ID = "Rachel"

        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"a", b"b", b"c"])
        mock_eleven.return_value = mock_client

        from voice.speaker import VoiceSpeaker
        speaker = VoiceSpeaker()
        result = speaker.speak("Hello")

        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result == b"abc"
