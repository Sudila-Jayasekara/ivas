"""
Text-to-Speech Service using Microsoft Edge TTS

This service generates lifelike audio from text using the free Microsoft Edge
TTS API. It returns the audio data as a base64 encoded MP3 string to be sent
via WebSockets.
"""

import base64
import bs4
import edge_tts
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default Voice. You can find more voices by running `edge-tts --list-voices`
# en-US-AriaNeural is a female American voice.
# en-US-ChristopherNeural is a male American voice.
# en-GB-SoniaNeural is a female British voice.
DEFAULT_VOICE = "en-US-AriaNeural"

def strip_html_tags(text: str) -> str:
    """Removes HTML tags from the given string, leaving only text."""
    try:
        if not text:
            return text
        soup = bs4.BeautifulSoup(text, "html.parser")
        return soup.get_text(separator=" ").strip()
    except Exception:
        # Fallback if beautifulsoup fails for some reason
        import re
        return re.sub(r'<[^>]+>', '', text)


async def generate_audio_b64(text: str, voice: str = DEFAULT_VOICE) -> Optional[str]:
    """
    Generates TTS audio from the provided text using Edge TTS.

    Args:
        text (str): The text to be spoken.
        voice (str): The name of the Edge TTS voice to use.

    Returns:
        Optional[str]: Base64 encoded MP3 audio data, or None if generation fails.
    """
    if not text or not text.strip():
        return None

    # Clean text to prevent TTS from reading out HTML layout tags
    clean_text = strip_html_tags(text)
    
    # Optional: Edge TTS can sometimes fail on extremely short chunks or empty strings
    if len(clean_text) < 2:
        return None

    try:
        communicate = edge_tts.Communicate(clean_text, voice)
        audio_bytes = bytearray()
        
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.extend(chunk["data"])

        if not audio_bytes:
            logger.warning("Edge TTS returned no audio data for text: %s", clean_text[:50])
            return None

        # Encode bytes to base64 string
        b64_encoded = base64.b64encode(audio_bytes).decode('utf-8')
        return b64_encoded

    except Exception as e:
        logger.error("Failed to generate Edge TTS audio: %s", e)
        return None
