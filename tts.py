import os
import re
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

VOICE = "nova"
MODEL = "gpt-4o-mini-tts"
INSTRUCTIONS = (
    "You are Maya, a warm and professional medical receptionist at an optometry clinic. "
    "Speak calmly and clearly, with a friendly but not overly casual tone. "
    "Pace yourself naturally — this is a phone call, not a rush."
)

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── Filler audio ───────────────────────────────────────────────────────────
# Pre-generated on first use, then cached for the process lifetime.
# Played instantly when a tool call is detected, masking the 1-2 seconds
# of dead silence while the tool executes and Claude generates a follow-up.

_filler_audio: bytes | None = None
_FILLER_TEXT = "Mm-hmm, let me check on that."
_SILENCE_GAP = b"\x00" * 14400  # 300 ms of silence at 24 kHz 16-bit mono


def synthesize(text: str) -> bytes:
    """
    Converts text to PCM audio bytes via OpenAI TTS.
    Returns raw PCM int16 bytes at 24kHz for direct playback.
    """
    response = _client.audio.speech.create(
        model=MODEL,
        voice=VOICE,
        input=text,
        instructions=INSTRUCTIONS,
        response_format="pcm",  # Raw PCM int16, 24kHz by default
    )

    return response.content


# ── Sentence splitting ─────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """Split text on sentence-ending punctuation for parallel TTS."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s for s in sentences if s.strip()]


def synthesize_parallel(text: str) -> bytes:
    """
    Split text into sentences and synthesize each in parallel via
    ThreadPoolExecutor.  Cuts TTS wall-clock time from O(n) to O(1)
    for multi-sentence responses (typical Maya response: 2-3 sentences).
    """
    sentences = _split_sentences(text)
    if len(sentences) <= 1:
        return synthesize(text)

    with ThreadPoolExecutor(max_workers=min(len(sentences), 4)) as pool:
        audio_chunks = list(pool.map(synthesize, sentences))

    return b"".join(audio_chunks)


# ── Filler audio ───────────────────────────────────────────────────────────

def get_filler_audio() -> bytes:
    """
    Returns pre-generated filler audio + silence gap.
    Lazy-initialized on first call so startup isn't blocked.
    """
    global _filler_audio
    if _filler_audio is None:
        _filler_audio = synthesize(_FILLER_TEXT) + _SILENCE_GAP
    return _filler_audio
