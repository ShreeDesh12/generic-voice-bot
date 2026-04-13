import logging
import time
import streamlit as st
import config
from content.parser import ContentParser
from llm.factory import LLMFactory
from voice.listener import VoiceListener
from voice.speaker import VoiceSpeaker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


st.set_page_config(page_title="Portfolio Voice Bot", page_icon="🎙️", layout="wide")
st.title("🎙️ Portfolio Voice Bot")

# --- Session State Initialization ---
if "context" not in st.session_state:
    st.session_state.context = ""
if "contact_details" not in st.session_state:
    st.session_state.contact_details = {}
if "messages" not in st.session_state:
    st.session_state.messages = []
if "listener" not in st.session_state:
    st.session_state.listener = None
if "speaker" not in st.session_state:
    st.session_state.speaker = None
if "llm" not in st.session_state:
    st.session_state.llm = None
if "is_listening" not in st.session_state:
    st.session_state.is_listening = False
if "last_audio" not in st.session_state:
    st.session_state.last_audio = None
if "voice_mode" not in st.session_state:
    st.session_state.voice_mode = "Auto Voice Detection"
if "last_audio_id" not in st.session_state:
    st.session_state.last_audio_id = None

# --- Sidebar: Content Input & Configuration ---
with st.sidebar:
    st.header("📄 Portfolio Link")

    url_input = st.text_input("Enter portfolio or LinkedIn URL:")
    if st.button("Parse Portfolio") and url_input:
        with st.spinner("Fetching and parsing portfolio..."):
            try:
                text, contacts = ContentParser.parse_portfolio(url_input)
                st.session_state.context = text
                st.session_state.contact_details = contacts
                logger.info(
                    "Parsed portfolio '%s': %d characters, contacts: %s",
                    url_input,
                    len(text),
                    contacts,
                )
                st.success(f"Parsed {len(text)} characters from portfolio.")
                if not contacts:
                    st.warning(
                        "No contact details found on the portfolio page."
                    )
            except ValueError as e:
                logger.error("Portfolio validation failed for '%s': %s", url_input, e)
                st.error(str(e))
            except Exception as e:
                logger.error("Failed to parse portfolio '%s': %s", url_input, e)
                st.error(f"Error: {e}")

    # Display extracted contact details
    if st.session_state.contact_details:
        st.divider()
        st.subheader("📇 Contact Details")
        for key, value in st.session_state.contact_details.items():
            st.text(f"{key.title()}: {value}")

    st.divider()
    st.header("⚙️ Settings")

    providers = LLMFactory.available_providers()
    selected_provider = st.selectbox(
        "LLM Provider",
        providers,
        index=providers.index(config.LLM_PROVIDER)
        if config.LLM_PROVIDER in providers
        else 0,
    )

    if st.session_state.context:
        st.info(
            f"Context loaded: {len(st.session_state.context)} chars"
        )
    else:
        st.warning("No portfolio loaded. Please provide a portfolio link.")

# --- Initialize LLM ---
try:
    if st.session_state.llm is None:
        logger.info("Initializing LLM provider: %s", selected_provider)
        st.session_state.llm = LLMFactory.create(selected_provider)
        logger.info("LLM provider '%s' initialized successfully", selected_provider)
except Exception as e:
    logger.error("Failed to initialize LLM provider '%s': %s", selected_provider, e)
    st.error(f"Failed to initialize LLM: {e}")


# --- Helper Functions ---
def process_query(user_text: str):
    """Send user text to LLM and get response, then TTS."""
    logger.info("Processing query: %s", user_text[:100])
    st.session_state.messages.append({"role": "user", "content": user_text})

    with st.spinner("Thinking..."):
        try:
            response = st.session_state.llm.generate_portfolio(
                prompt=user_text,
                context=st.session_state.context,
                contact_details=st.session_state.contact_details,
            )
            logger.info("LLM response received: %d characters", len(response))
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            response = f"LLM Error: {e}"

    st.session_state.messages.append({"role": "assistant", "content": response})

    # TTS playback — store audio in session state so it survives rerun
    if st.session_state.speaker:
        try:
            logger.info("Converting response to speech (%d chars)", len(response))
            audio_bytes = st.session_state.speaker.speak(response)
            st.session_state.last_audio = audio_bytes
            logger.info("TTS complete: %d bytes of audio generated", len(audio_bytes))
        except Exception as e:
            logger.error("TTS conversion failed: %s", e)
            st.warning(f"TTS Error: {e}")
    else:
        logger.warning("No speaker initialized — skipping TTS")


# --- Main Area: Conversation ---
st.subheader("Conversation")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Play audio after messages render (survives rerun)
if st.session_state.last_audio:
    st.audio(st.session_state.last_audio, format="audio/mp3", autoplay=True)
    st.session_state.last_audio = None

# --- Auto-initialize TTS for voice output ---
if st.session_state.speaker is None:
    try:
        st.session_state.speaker = VoiceSpeaker()
        logger.info("TTS speaker initialized (voice: %s)", config.ELEVENLABS_VOICE_ID)
    except Exception as e:
        logger.warning("TTS speaker not available: %s", e)

# --- Voice Controls ---
st.session_state.voice_mode = st.toggle(
    "Tap & Say",
    value=st.session_state.voice_mode == "Tap & Say",
    help="ON = Tap & Say (push to record) | OFF = Auto Voice Detection (continuous listening)",
)
st.session_state.voice_mode = "Tap & Say" if st.session_state.voice_mode else "Auto Voice Detection"
st.caption(f"Mode: **{st.session_state.voice_mode}**")

if st.session_state.voice_mode == "Tap & Say":
    # --- Tap & Say Mode (browser-based recording, works in Docker) ---
    # Stop background listening if it was active from auto mode
    if st.session_state.is_listening and st.session_state.listener:
        st.session_state.listener.stop()
        st.session_state.is_listening = False

    audio_data = st.audio_input("🎤 Tap to record your question")
    if audio_data is not None and audio_data.file_id != st.session_state.last_audio_id:
        st.session_state.last_audio_id = audio_data.file_id
        with st.spinner("Transcribing..."):
            if st.session_state.listener is None:
                st.session_state.listener = VoiceListener(use_microphone=False)
            transcript = st.session_state.listener.transcribe_audio_bytes(audio_data.read())
        if transcript and not transcript.startswith("[STT Error"):
            st.toast(f"Heard: {transcript}")
            if st.session_state.llm:
                process_query(transcript)
                st.rerun()
        elif transcript:
            st.warning(transcript)
        else:
            st.info("No speech detected. Try again.")

else:
    # --- Auto Voice Detection Mode (requires server-side microphone) ---
    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "🎤 Start Listening" if not st.session_state.is_listening else "⏹️ Stop Listening",
            use_container_width=True,
            type="primary" if not st.session_state.is_listening else "secondary",
        ):
            if not st.session_state.is_listening:
                try:
                    if st.session_state.listener is None:
                        st.session_state.listener = VoiceListener(use_microphone=True)
                    st.session_state.listener.start()
                    st.session_state.is_listening = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Microphone error: {e}")
                    st.info("Auto Voice Detection requires server-side mic access. Use **Tap & Say** mode in Docker.")
            else:
                if st.session_state.listener:
                    st.session_state.listener.stop()
                st.session_state.is_listening = False
                st.rerun()

    with col2:
        if st.session_state.is_listening:
            st.success("🎤 Listening...")
        else:
            st.info("🔇 Not listening")

    # --- Check for voice transcripts ---
    if st.session_state.is_listening and st.session_state.listener:
        transcript = st.session_state.listener.get_transcript()
        if transcript and not transcript.startswith("[STT Error"):
            st.toast(f"Heard: {transcript}")
            if st.session_state.llm:
                process_query(transcript)
                st.rerun()
        elif transcript:
            st.warning(transcript)

        # Poll for new transcripts
        time.sleep(0.5)
        st.rerun()

# --- Manual Text Input (Fallback) ---
st.divider()
user_input = st.chat_input("Or type your question here...")
if user_input and st.session_state.llm:
    process_query(user_input)
    st.rerun()
