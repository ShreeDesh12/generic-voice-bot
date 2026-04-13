import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "Rachel")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge")
TTS_EDGE_GENDER = os.getenv("TTS_EDGE_GENDER", "female")  # female, male
TTS_EDGE_RATE = os.getenv("TTS_EDGE_RATE", "+15%")  # e.g. +20%, -10%, +0%
MAX_CONTEXT_LENGTH = int(os.getenv("MAX_CONTEXT_LENGTH", "50000"))

# PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://voicebot:voicebot@localhost:5432/voicebot",
)

# OAuth (Google)
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "change-me-in-production")

# Email / SMTP
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

# Drop-off
DROPOFF_TIMEOUT_MINUTES = int(os.getenv("DROPOFF_TIMEOUT_MINUTES", "5"))
