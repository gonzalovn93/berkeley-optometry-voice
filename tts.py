import os
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
