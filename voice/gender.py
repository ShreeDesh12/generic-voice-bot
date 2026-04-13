import logging

import gender_guesser.detector as gender_detector

logger = logging.getLogger(__name__)

_detector = gender_detector.Detector()

# ElevenLabs voice IDs
VOICE_FEMALE = "Rachel"  # default female voice
VOICE_MALE = "TxGEqnHWrfWFTfGW9XjX"  # "Josh" male voice


def detect_gender(first_name: str) -> str:
    """Detect gender from a first name.

    Returns:
        "female", "male", or "unknown".
    """
    if not first_name:
        return "unknown"

    result = _detector.get_gender(first_name.strip().title())
    logger.info("Gender detection for '%s': %s", first_name, result)

    if result in ("female", "mostly_female"):
        return "female"
    elif result in ("male", "mostly_male"):
        return "male"
    return "unknown"


def voice_id_for_gender(gender: str) -> str:
    """Map gender to an ElevenLabs voice ID."""
    if gender == "female":
        return VOICE_FEMALE
    elif gender == "male":
        return VOICE_MALE
    # Default to male for unknown
    return VOICE_MALE
