"""
Text-to-Speech Service — Realistic Human Voice

Primary:  OpenAI TTS HD  (tts-1-hd) — ultra-realistic neural voices.
Fallback: Microsoft Edge TTS (free, decent neural voices).

The service returns base64-encoded MP3 audio for WebSocket / REST delivery.
"""

import asyncio
import base64
import bs4
import edge_tts
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ── Edge TTS defaults ───────────────────────────────────────────────
EDGE_DEFAULT_VOICE = "en-US-AriaNeural"


def strip_html_tags(text: str) -> str:
    """Removes HTML tags from the given string, leaving only text."""
    try:
        if not text:
            return text
        soup = bs4.BeautifulSoup(text, "html.parser")
        return soup.get_text(separator=" ").strip()
    except Exception:
        import re
        return re.sub(r'<[^>]+>', '', text)


# ── OpenAI TTS HD ──────────────────────────────────────────────────

async def _generate_openai(clean_text: str) -> Optional[str]:
    """Generate MP3 audio via OpenAI TTS-1-HD (realistic human voice)."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.audio.speech.create(
            model=settings.openai_tts_model,
            voice=settings.openai_tts_voice,
            input=clean_text,
            response_format="mp3",
        )
        audio_bytes = response.content
        if not audio_bytes:
            logger.warning("OpenAI TTS returned empty audio")
            return None

        return base64.b64encode(audio_bytes).decode("utf-8")

    except Exception as e:
        logger.error("OpenAI TTS failed: %s", e)
        return None


# ── Edge TTS (free fallback) ───────────────────────────────────────

async def _generate_edge(clean_text: str, voice: str = EDGE_DEFAULT_VOICE) -> Optional[str]:
    """Generate MP3 audio via Microsoft Edge TTS (free neural voices)."""
    try:
        communicate = edge_tts.Communicate(clean_text, voice)
        audio_bytes = bytearray()

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.extend(chunk["data"])

        if not audio_bytes:
            logger.warning("Edge TTS returned no audio for: %s", clean_text[:50])
            return None

        return base64.b64encode(audio_bytes).decode("utf-8")

    except Exception as e:
        logger.error("Edge TTS failed: %s", e)
        return None


# ── Public API ──────────────────────────────────────────────────────

async def generate_audio_b64(text: str, voice: str = EDGE_DEFAULT_VOICE) -> Optional[str]:
    """
    Generate realistic TTS audio from text.

    Uses OpenAI TTS-HD when an API key is configured (best quality),
    otherwise falls back to Edge TTS neural voices.

    Returns:
        Base64-encoded MP3 string, or None on failure.
    """
    if not text or not text.strip():
        return None

    clean_text = strip_html_tags(text)
    if len(clean_text) < 2:
        return None

    # Try OpenAI first if configured
    if settings.tts_provider == "openai" and settings.openai_api_key:
        result = await _generate_openai(clean_text)
        if result:
            return result
        logger.warning("OpenAI TTS failed, falling back to Edge TTS")

    # Fallback to Edge TTS
    return await _generate_edge(clean_text, voice)
